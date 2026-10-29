# -*- coding: utf-8 -*-
"""统一路径：仓库内仅保留通用目录名，不含学校/班级标识。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def submissions_dir() -> Path:
    """答卷目录：优先 data/submissions；兼容本地未迁移的「*期中考试」文件夹。"""
    preferred = ROOT / "data" / "submissions"
    if preferred.exists():
        return preferred
    for p in sorted(ROOT.iterdir()):
        if p.is_dir() and "期中考试" in p.name:
            return p
    return preferred


def exam_dir() -> Path:
    preferred = ROOT / "data" / "exam"
    if preferred.exists():
        return preferred
    legacy = ROOT / "试卷"
    return legacy if legacy.exists() else preferred


def answer_dir() -> Path:
    preferred = ROOT / "data" / "answer"
    if preferred.exists():
        return preferred
    legacy = ROOT / "答案"
    return legacy if legacy.exists() else preferred


WORK_DIR = ROOT / "work"
SUBMISSIONS_OUT = WORK_DIR / "submissions"
GRADES_JSON = WORK_DIR / "grades.json"
OUTPUT_DIR = ROOT / "output"
GRADES_XLSX = OUTPUT_DIR / "Java期中成绩表.xlsx"
