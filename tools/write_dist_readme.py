# -*- coding: utf-8 -*-
"""向打包目录写入说明文件（UTF-8 BOM，Windows 记事本可正常打开）。"""
from __future__ import annotations

import sys
from pathlib import Path

CONTENT = """CodeJudge 阅卷台 · 使用说明
==========================

1. 双击 CodeJudge.exe（单文件绿色版，可单独拷贝）
2. 选择学生答卷文件夹（含 .docx / 图片）
3. 填写阿里云百炼 API Key（DashScope）
4. 点击「开始批改」
5. 成绩表生成在 exe 同目录：
   output\\Java期中成绩表.xlsx

注意
----
- 需要联网（调用识图 API）
- 首次启动可能稍慢（程序自解压），属正常现象
- 旧版 .doc 建议安装 Microsoft Word；.docx 可直接处理
- API Key / work / output 会生成在 exe 同目录
- 请勿把含学生信息的目录公开外传
"""


def main(dist: str | Path | None = None) -> None:
    target = Path(dist) if dist else Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    # 使用纯英文文件名，避免资源管理器/控制台编码把文件名弄乱
    out = target / "README.txt"
    out.write_text(CONTENT, encoding="utf-8-sig")
    # 清理历史乱码文件名
    for p in target.glob("*.txt"):
        if p.name == "README.txt":
            continue
        name = p.name
        # 典型 mojibake：使用说明.txt 被当成 GBK 显示
        if "浣" in name or "说明" in name or name.endswith("璇存槑.txt"):
            try:
                p.unlink()
            except OSError:
                pass
    print(f"wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: write_dist_readme.py <dist_dir>")
    main(sys.argv[1])
