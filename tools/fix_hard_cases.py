# -*- coding: utf-8 -*-
"""修复多图合并失败与个别 JSON 解析失败的答卷。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade_exam import grade_one, merge_multi, parse_json_loose, strip_vision_noise

def _caps(scores: dict) -> dict:
    caps = {
        "A_classname": 20,
        "B_main_comment": 20,
        "C_student_class": 10,
        "D_fields": 10,
        "E_sayHello": 10,
        "F_instantiate": 15,
        "G_run": 15,
    }
    return {k: max(0, min(cap, int(scores.get(k, 0) or 0))) for k, cap in caps.items()}


from paths import GRADES_JSON, SUBMISSIONS_OUT

ROOT = Path(__file__).resolve().parents[1]
SUBS = SUBMISSIONS_OUT
GRADES = GRADES_JSON

# 可手动指定需优先处理的提交目录 id；默认留空，由下方自动扫描解析失败项
HARD: list[str] = []


def fix_multi_raw_file(raw_path: Path) -> dict:
    raw = raw_path.read_text(encoding="utf-8")
    data = json.loads(raw) if raw.lstrip().startswith("{") else None
    if not isinstance(data, dict) or "_multi_raw" not in data:
        # 尝试宽松
        data = parse_json_loose(raw)
    cleaned = []
    for chunk in data["_multi_raw"]:
        cleaned.append(strip_vision_noise(chunk))
    # 写成干净多图再 merge
    raw_path.write_text(
        json.dumps({"_multi_raw": cleaned}, ensure_ascii=False), encoding="utf-8"
    )
    graded = merge_multi(json.dumps({"_multi_raw": cleaned}, ensure_ascii=False))
    graded["scores"] = _caps(graded.get("scores") or {})
    graded["total"] = sum(graded["scores"].values())
    return graded


def main() -> None:
    grades = json.loads(GRADES.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in grades["results"]}

    for sid in HARD:
        dest = SUBS / sid
        meta = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        raw_path = dest / "vision_raw.txt"
        print(f"== {sid}")
        try:
            if raw_path.exists() and "_multi_raw" in raw_path.read_text(encoding="utf-8")[:200]:
                graded = fix_multi_raw_file(raw_path)
            else:
                # 单图：先重解析，失败则重新识图
                try:
                    graded = parse_json_loose(raw_path.read_text(encoding="utf-8"))
                    graded["scores"] = _caps(graded.get("scores") or {})
                    graded["total"] = sum(graded["scores"].values())
                except Exception:
                    print("  re-vision...")
                    r = grade_one(dest / "meta.json")
                    by_id[sid] = r
                    print(f"  -> {r['total']}")
                    continue
            base = {
                "id": meta["id"],
                "name": meta["name"],
                "seat": meta.get("seat", ""),
                "source": meta["source"],
                "image_count": len(meta.get("images", [])),
                "extract_notes": meta.get("notes", []),
            }
            base.update(graded)
            (dest / "grade.json").write_text(
                json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            by_id[sid] = base
            print(f"  -> {base['total']}")
        except Exception as e:
            print(f"  FAIL {e}; re-vision")
            r = grade_one(dest / "meta.json")
            by_id[sid] = r
            print(f"  -> {r['total']}")

    # 再扫一遍仍为解析失败的
    for dest in SUBS.iterdir():
        if not dest.is_dir():
            continue
        gpath = dest / "grade.json"
        if not gpath.exists():
            continue
        g = json.loads(gpath.read_text(encoding="utf-8"))
        if "JSON解析失败" not in str(g.get("deductions", "")):
            continue
        if g.get("image_count", 0) <= 0:
            continue
        sid = dest.name
        if sid in HARD:
            continue
        print(f"== retry parse {sid}")
        raw_path = dest / "vision_raw.txt"
        meta = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        try:
            graded = parse_json_loose(raw_path.read_text(encoding="utf-8"))
            graded["scores"] = _caps(graded.get("scores") or {})
            graded["total"] = sum(graded["scores"].values())
            base = {
                "id": meta["id"],
                "name": meta["name"],
                "seat": meta.get("seat", ""),
                "source": meta["source"],
                "image_count": len(meta.get("images", [])),
                "extract_notes": meta.get("notes", []),
            }
            base.update(graded)
            gpath.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
            by_id[sid] = base
            print(f"  -> {base['total']}")
        except Exception as e:
            print(f"  re-vision {e}")
            r = grade_one(dest / "meta.json")
            by_id[sid] = r
            print(f"  -> {r['total']}")

    ordered = sorted(by_id.values(), key=lambda x: (x.get("seat") or "ZZZ", x.get("name") or ""))
    GRADES.write_text(
        json.dumps({"results": ordered, "errors": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("done", len(ordered))


if __name__ == "__main__":
    main()
