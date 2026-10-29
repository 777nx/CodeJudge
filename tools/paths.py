# -*- coding: utf-8 -*-
"""统一路径：支持源码运行与 PyInstaller 打包后的 exe 旁目录。"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT: Path | None = None
_SUBMISSIONS: Path | None = None


def default_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def set_root(path: Path | str) -> None:
    global _ROOT
    _ROOT = Path(path).resolve()


def get_root() -> Path:
    return _ROOT if _ROOT is not None else default_root()


def set_submissions_dir(path: Path | str) -> None:
    global _SUBMISSIONS
    _SUBMISSIONS = Path(path).resolve()


def submissions_dir() -> Path:
    if _SUBMISSIONS is not None:
        return _SUBMISSIONS
    root = get_root()
    preferred = root / "data" / "submissions"
    if preferred.exists():
        return preferred
    for p in sorted(root.iterdir()):
        if p.is_dir() and "期中考试" in p.name:
            return p
    return preferred


def work_dir() -> Path:
    return get_root() / "work"


def submissions_out() -> Path:
    return work_dir() / "submissions"


def grades_json() -> Path:
    return work_dir() / "grades.json"


def output_dir() -> Path:
    return get_root() / "output"


def grades_xlsx() -> Path:
    return output_dir() / "Java期中成绩表.xlsx"


def config_path() -> Path:
    return get_root() / "codejudge_config.json"


# 兼容旧代码中的常量写法（导入时按当前 root 计算；动态场景请调用函数）
ROOT = default_root()
WORK_DIR = ROOT / "work"
SUBMISSIONS_OUT = WORK_DIR / "submissions"
GRADES_JSON = WORK_DIR / "grades.json"
OUTPUT_DIR = ROOT / "output"
GRADES_XLSX = OUTPUT_DIR / "Java期中成绩表.xlsx"
