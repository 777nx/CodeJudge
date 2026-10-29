# -*- coding: utf-8 -*-
"""CodeJudge 图形界面入口（可打包为 exe）。"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

# 保证 tools 可导入（源码与 PyInstaller 均适用）
if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
    # onefile 解压到临时目录 _MEIPASS；工作目录仍用 exe 所在目录
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
        # 先隐藏，布局并居中后再显示，避免左上角闪一下
        self.withdraw()
        self.title("CodeJudge — Java 实操卷批改")
        self.minsize(640, 460)

        paths.set_root(BASE)
        cfg = load_config()

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # 顶部时钟 / 已用时
        top = ttk.Frame(frm)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.var_clock = tk.StringVar(value="")
        self.var_elapsed = tk.StringVar(value="已用时：—")
        ttk.Label(top, textvariable=self.var_clock, foreground="#333").pack(side=tk.LEFT)
        ttk.Label(top, textvariable=self.var_elapsed, foreground="#0F766E").pack(side=tk.RIGHT)
        self._job_started_at: float | None = None
        self._tick_clock()

        ttk.Label(frm, text="答卷文件夹（含 Word/截图）").grid(row=1, column=0, sticky="w")
        self.var_dir = tk.StringVar(value=cfg.get("submissions_dir", ""))
        ent = ttk.Entry(frm, textvariable=self.var_dir)
        ent.grid(row=2, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(frm, text="浏览…", command=self.browse).grid(row=2, column=1, sticky="e")

        ttk.Label(frm, text="通义千问 API Key（阿里云百炼）").grid(row=3, column=0, sticky="w", pady=(12, 0))
        self.var_key = tk.StringVar(
            value=cfg.get("api_key", "") or os.environ.get("DASHSCOPE_API_KEY", "")
        )
        key_ent = ttk.Entry(frm, textvariable=self.var_key, show="*")
        key_ent.grid(row=4, column=0, sticky="ew", padx=(0, 8))
        self.show_key = tk.BooleanVar(value=False)

        def toggle_key() -> None:
            key_ent.configure(show="" if self.show_key.get() else "*")

        ttk.Checkbutton(frm, text="显示", variable=self.show_key, command=toggle_key).grid(
            row=4, column=1, sticky="w"
        )

        opt = ttk.Frame(frm)
        opt.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(opt, text="并发数").pack(side=tk.LEFT)
        self.var_workers = tk.StringVar(value=str(cfg.get("workers", 3)))
        spin = ttk.Spinbox(opt, from_=1, to=6, width=5, textvariable=self.var_workers)
        spin.pack(side=tk.LEFT, padx=8)
        ttk.Label(opt, text="（同时识图批改几份答卷）", foreground="#555").pack(side=tk.LEFT)

        tip_workers = ttk.Label(
            frm,
            text=(
                "提示：默认 3 较稳妥。数值越大通常越快，但也更容易触发 API 限流或超时；"
                "若日志出现失败/限流，请降到 2 或 1。一般不必超过 5。"
            ),
            foreground="#0F766E",
            wraplength=640,
            justify="left",
        )
        tip_workers.grid(row=6, column=0, columnspan=2, sticky="w", pady=(4, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, sticky="ew", pady=12)
        self.btn_run = ttk.Button(btns, text="开始批改", command=self.start)
        self.btn_run.pack(side=tk.LEFT)
        ttk.Button(btns, text="打开成绩目录", command=self.open_output).pack(side=tk.LEFT, padx=8)
        ttk.Button(btns, text="保存设置", command=self.save_settings).pack(side=tk.LEFT)

        ttk.Label(frm, text="运行日志").grid(row=8, column=0, sticky="w")
        self.log = scrolledtext.ScrolledText(frm, height=16, state="disabled", wrap=tk.WORD)
        self.log.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(4, 0))

        tip = (
            "说明：需联网调用识图 API；.docx 可直接处理；旧版 .doc 需要本机安装 Word。"
            "工作目录为本程序所在文件夹（生成 work/ 与 output/）。"
        )
        ttk.Label(frm, text=tip, wraplength=680, foreground="#666").grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(9, weight=1)

        if not self.var_dir.get():
            # 尝试自动发现
            try:
                d = paths.submissions_dir()
                if d.exists():
                    self.var_dir.set(str(d))
            except Exception:
                pass

        self._show_centered(720, 520)

    def _show_centered(self, width: int, height: int) -> None:
        """布局完成后再居中显示，避免窗口先出现在左上角。"""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()

    def browse(self) -> None:
        d = filedialog.askdirectory(title="选择答卷文件夹")
        if d:
            self.var_dir.set(d)

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        seconds = max(0, int(seconds))
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _tick_clock(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.var_clock.set(f"当前时间：{now}")
        if self._job_started_at is not None:
            elapsed = time.monotonic() - self._job_started_at
            self.var_elapsed.set(f"已用时：{self._fmt_elapsed(elapsed)}")
        self.after(1000, self._tick_clock)

    def append_log(self, msg: str) -> None:
        # 空行不加时间戳，避免刷屏
        if msg == "":
            line = "\n"
        else:
            ts = datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {msg}\n"
        self.log.configure(state="normal")
        self.log.insert(tk.END, line)
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

        save_config(
            {
                "submissions_dir": folder,
                "api_key": key,
                "workers": workers,
            }
        )
        self.btn_run.configure(state="disabled")
        self._job_started_at = time.monotonic()
        self.var_elapsed.set("已用时：00:00")
        self.append_log("")
        self.append_log("======== 开始批改 ========")
        self.append_log(f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.append_log(f"并发：{workers}")

        def worker() -> None:
            try:
                xlsx = run_pipeline(
                    Path(folder),
                    api_key=key,
                    work_root=BASE,
                    workers=workers,
                    log=lambda m: self.after(0, self.append_log, m),
                )

                def ok() -> None:
                    elapsed = (
                        time.monotonic() - self._job_started_at
                        if self._job_started_at is not None
                        else 0
                    )
                    self.append_log(f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    self.append_log(f"总耗时：{self._fmt_elapsed(elapsed)}")
                    self._job_started_at = None
                    self.var_elapsed.set(f"本次耗时：{self._fmt_elapsed(elapsed)}")
                    messagebox.showinfo(
                        "完成",
                        f"成绩表已生成：\n{xlsx}\n\n总耗时：{self._fmt_elapsed(elapsed)}",
                    )

                self.after(0, ok)
            except Exception as e:
                def fail() -> None:
                    elapsed = (
                        time.monotonic() - self._job_started_at
                        if self._job_started_at is not None
                        else 0
                    )
                    self.append_log(f"失败：{e}")
                    self.append_log("".join(traceback.format_exception(e)))
                    self.append_log(f"失败前已用时：{self._fmt_elapsed(elapsed)}")
                    self._job_started_at = None
                    self.var_elapsed.set(f"已用时：{self._fmt_elapsed(elapsed)}（失败）")
                    messagebox.showerror("失败", str(e))

                self.after(0, fail)
            finally:
                self.after(0, lambda: self.btn_run.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
