# -*- coding: utf-8 -*-
"""对 JSON 解析失败或无图零分的答卷：优先重解析已有 vision_raw；必要时重新识图。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade_exam import grade_one, merge_multi, parse_json_loose
from paths import GRADES_JSON, SUBMISSIONS_OUT, WORK_DIR

ROOT = Path(__file__).resolve().parents[1]
WORK = WORK_DIR
SUBS = SUBMISSIONS_OUT
GRADES = GRADES_JSON


def try_reparse(dest: Path) -> dict | None:
    raw_path = dest / "vision_raw.txt"
    if not raw_path.exists():
        return None
    raw = raw_path.read_text(encoding="utf-8")
    try:
        if '"_multi_raw"' in raw or "_multi_raw" in raw[:200]:
            graded = merge_multi(raw)
        else:
            graded = parse_json_loose(raw)
            if "_multi_raw" in graded:
                graded = merge_multi(raw)
        return graded
    except Exception:
        return None


def main() -> None:
    data = json.loads(GRADES.read_text(encoding="utf-8"))
    results = {r["id"]: r for r in data["results"]}
    updated = 0
    re_vision = 0

    for meta_path in sorted(SUBS.glob("*/meta.json")):
        sid = meta_path.parent.name
        old = results.get(sid)
        if not old:
            continue
        need = (
            old.get("total", 0) == 0
            and (
                "JSON解析失败" in str(old.get("deductions", ""))
                or "无法解析" in str(old.get("deductions", ""))
                or old.get("image_count", 0) > 0
                and "无截图" not in str(old.get("deductions", ""))
            )
        )
        # 也处理：有图但 total=0 且 needs_review（多数是解析失败）
        if not need and old.get("image_count", 0) > 0 and old.get("total", 0) == 0:
            if "JSON" in str(old.get("deductions", "")) or old.get("needs_review"):
                need = True
        if not need:
            continue

        dest = meta_path.parent
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        graded = try_reparse(dest)
        if graded is None:
            print(f"[re-vision] {sid}")
            new_r = grade_one(meta_path)
            results[sid] = new_r
            re_vision += 1
            updated += 1
            continue

        scores = graded.get("scores") or {}
        for k, cap in [
            ("A_classname", 20),
            ("B_main_comment", 20),
            ("C_student_class", 10),
            ("D_fields", 10),
            ("E_sayHello", 10),
            ("F_instantiate", 15),
            ("G_run", 15),
        ]:
            v = int(scores.get(k, 0) or 0)
            scores[k] = max(0, min(cap, v))
        graded["scores"] = scores
        graded["total"] = sum(scores.values())

        new_r = {
            "id": meta["id"],
            "name": meta["name"],
            "seat": meta.get("seat", ""),
            "source": meta["source"],
            "image_count": len(meta.get("images", [])),
            "extract_notes": meta.get("notes", []),
        }
        new_r.update(graded)
        (dest / "grade.json").write_text(
            json.dumps(new_r, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        results[sid] = new_r
        updated += 1
        print(f"[reparse] {sid}: {new_r['total']}")

    ordered = sorted(results.values(), key=lambda x: (x.get("seat") or "ZZZ", x.get("name") or ""))
    GRADES.write_text(
        json.dumps({"results": ordered, "errors": data.get("errors", [])}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Updated {updated} (re-vision {re_vision})")


if __name__ == "__main__":
    main()
