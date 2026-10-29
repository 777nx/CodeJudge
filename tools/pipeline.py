# -*- coding: utf-8 -*-
"""一键批改流水线：抽图 → 识图打分 → 导出 Excel。"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import extract_submissions
import export_excel
import grade_exam
import paths


LogFn = Callable[[str], None]


def run_pipeline(
    submissions: Path,
    *,
    api_key: str,
    work_root: Path | None = None,
    workers: int = 3,
    log: LogFn | None = None,
) -> Path:
    def _log(msg: str) -> None:
        if log:
            log(msg)
        else:
            print(msg)

    root = Path(work_root) if work_root else paths.default_root()
    paths.set_root(root)
    paths.set_submissions_dir(submissions)
    grade_exam.set_api_key(api_key)
    grade_exam.MAX_WORKERS = max(1, int(workers))

    _log(f"工作目录: {paths.get_root()}")
    _log(f"答卷目录: {paths.submissions_dir()}")
    _log("① 提取截图…")
    extract_submissions.main()
    metas = list(paths.submissions_out().glob("*/meta.json"))
    _log(f"   共 {len(metas)} 份答卷")
    if not metas:
        raise RuntimeError("未找到可批改答卷，请检查目录是否包含 Word/图片。")

    _log("② 识图评分（需联网）…")
    grade_exam.main(log=_log)

    _log("③ 导出 Excel…")
    xlsx = export_excel.main()
    _log(f"完成：{xlsx}")
    return Path(xlsx)


def load_config() -> dict:
    p = paths.config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    p = paths.config_path()
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
