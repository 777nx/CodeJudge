# -*- coding: utf-8 -*-
"""CodeJudge 图形界面入口（可打包为 exe）。"""
from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# 保证 tools 可导入（源码与 PyInstaller 均适用）
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
    # onedir 时模块在 _internal；onefile 解压到 _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        sys.path.insert(0, str(meipass))
        sys.path.insert(0, str(Path(meipass) / "tools"))
    sys.path.insert(0, str(BASE))
    sys.path.insert(0, str(BASE / "tools"))
else:
    BASE = Path(__file__).resolve().parent
    sys.path.insert(0, str(BASE / "tools"))

import paths  # noqa: E402
from pipeline import load_config, run_pipeline, save_config  # noqa: E402


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CodeJudge — Java 实操卷批改")
        self.geometry("720x520")
        self.minsize(640, 460)

        paths.set_root(BASE)
        cfg = load_config()

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="答卷文件夹（含 Word/截图）").grid(row=0, column=0, sticky="w")
        self.var_dir = tk.StringVar(value=cfg.get("submissions_dir", ""))
        ent = ttk.Entry(frm, textvariable=self.var_dir)
        ent.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(frm, text="浏览…", command=self.browse).grid(row=1, column=1, sticky="e")

        ttk.Label(frm, text="通义千问 API Key（阿里云百炼）").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.var_key = tk.StringVar(
            value=cfg.get("api_key", "") or os.environ.get("DASHSCOPE_API_KEY", "")
        )
        key_ent = ttk.Entry(frm, textvariable=self.var_key, show="*")
        key_ent.grid(row=3, column=0, sticky="ew", padx=(0, 8))
        self.show_key = tk.BooleanVar(value=False)

        def toggle_key() -> None:
            key_ent.configure(show="" if self.show_key.get() else "*")

        ttk.Checkbutton(frm, text="显示", variable=self.show_key, command=toggle_key).grid(
            row=3, column=1, sticky="w"
        )

        opt = ttk.Frame(frm)
        opt.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(opt, text="并发数").pack(side=tk.LEFT)
        self.var_workers = tk.StringVar(value=str(cfg.get("workers", 3)))
        ttk.Spinbox(opt, from_=1, to=6, width=5, textvariable=self.var_workers).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Label(
            opt,
            text="工作目录=本程序所在文件夹（生成 work/ 与 output/）",
            foreground="#555",
        ).pack(side=tk.LEFT, padx=8)

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="ew", pady=12)
        self.btn_run = ttk.Button(btns, text="开始批改", command=self.start)
        self.btn_run.pack(side=tk.LEFT)
        ttk.Button(btns, text="打开成绩目录", command=self.open_output).pack(side=tk.LEFT, padx=8)
        ttk.Button(btns, text="保存设置", command=self.save_settings).pack(side=tk.LEFT)

        ttk.Label(frm, text="运行日志").grid(row=6, column=0, sticky="w")
        self.log = scrolledtext.ScrolledText(frm, height=16, state="disabled", wrap=tk.WORD)
        self.log.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(4, 0))

        tip = (
            "说明：需联网调用识图 API；.docx 可直接处理；旧版 .doc 需要本机安装 Word。"
            "请勿把含学生信息的目录上传到公开环境。"
        )
        ttk.Label(frm, text=tip, wraplength=680, foreground="#666").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(7, weight=1)

        if not self.var_dir.get():
            # 尝试自动发现
            try:
                d = paths.submissions_dir()
                if d.exists():
                    self.var_dir.set(str(d))
            except Exception:
                pass

    def browse(self) -> None:
        d = filedialog.askdirectory(title="选择答卷文件夹")
        if d:
            self.var_dir.set(d)

    def append_log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def save_settings(self) -> None:
        try:
            workers = int(self.var_workers.get())
        except ValueError:
            workers = 3
        save_config(
            {
                "submissions_dir": self.var_dir.get().strip(),
                "api_key": self.var_key.get().strip(),
                "workers": workers,
            }
        )
        messagebox.showinfo("提示", f"设置已保存到\n{paths.config_path()}")

    def open_output(self) -> None:
        out = paths.output_dir()
        out.mkdir(parents=True, exist_ok=True)
        os.startfile(str(out))  # type: ignore[attr-defined]

    def start(self) -> None:
        folder = self.var_dir.get().strip()
        key = self.var_key.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("错误", "请先选择有效的答卷文件夹")
            return
        if not key:
            messagebox.showerror("错误", "请填写 API Key（阿里云百炼 DashScope）")
            return
        try:
            workers = int(self.var_workers.get())
        except ValueError:
            workers = 3

        self.save_settings()
        self.btn_run.configure(state="disabled")
        self.append_log("======== 开始批改 ========")

        def worker() -> None:
            try:
                xlsx = run_pipeline(
                    Path(folder),
                    api_key=key,
                    work_root=BASE,
                    workers=workers,
                    log=lambda m: self.after(0, self.append_log, m),
                )
                self.after(
                    0,
                    lambda: messagebox.showinfo("完成", f"成绩表已生成：\n{xlsx}"),
                )
            except Exception as e:
                err = "".join(traceback.format_exception(e))
                self.after(0, self.append_log, err)
                self.after(0, lambda: messagebox.showerror("失败", str(e)))
            finally:
                self.after(0, lambda: self.btn_run.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
