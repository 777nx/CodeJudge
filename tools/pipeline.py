# -*- coding: utf-8 -*-
"""一键批改流水线：抽图 → 识图打分 → 导出 Excel。"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import extract_submissions
import export_excel
import grade_exam
import paths


LogFn = Callable[[str], None]


def _fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


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

    t0 = time.monotonic()
    _log("— 批改任务 —")
    _log(f"答卷：{paths.submissions_dir()}")
    _log(f"输出：{paths.get_root()}")
    _log("")

    _log("[1/3] 提取截图")
    t1 = time.monotonic()
    extract_submissions.main(log=_log)
    _log(f"  本步耗时 {_fmt_elapsed(time.monotonic() - t1)}")
    metas = list(paths.submissions_out().glob("*/meta.json"))
    if not metas:
        raise RuntimeError("未找到可批改答卷，请检查目录是否包含 Word/图片。")

    _log("")
    _log("[2/3] 识图评分（需联网，请稍候）")
    t2 = time.monotonic()
    grade_exam.main(log=_log)
    _log(f"  本步耗时 {_fmt_elapsed(time.monotonic() - t2)}")

    _log("")
    _log("[3/3] 导出成绩表")
    t3 = time.monotonic()
    xlsx = export_excel.main()
    _log(f"已生成：{xlsx.name}")
    _log(f"完整路径：{xlsx}")
    _log(f"  本步耗时 {_fmt_elapsed(time.monotonic() - t3)}")
    _log("")
    _log(f"全部完成。流水线总耗时 {_fmt_elapsed(time.monotonic() - t0)}")
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
