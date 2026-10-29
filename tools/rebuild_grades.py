# -*- coding: utf-8 -*-
"""仅用已有 vision_raw 重解析，重建 grades.json（不调用识图 API）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grade_exam import merge_multi, parse_json_loose

from paths import GRADES_JSON, SUBMISSIONS_OUT

ROOT = Path(__file__).resolve().parents[1]
SUBS = SUBMISSIONS_OUT
OUT = GRADES_JSON


def score_caps(scores: dict) -> dict:
    caps = {
        "A_classname": 20,
        "B_main_comment": 20,
        "C_student_class": 10,
        "D_fields": 10,
        "E_sayHello": 10,
        "F_instantiate": 15,
        "G_run": 15,
    }
    out = {}
    for k, cap in caps.items():
        out[k] = max(0, min(cap, int(scores.get(k, 0) or 0)))
    return out


def main() -> None:
    results = []
    for meta_path in sorted(SUBS.glob("*/meta.json")):
        dest = meta_path.parent
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        base = {
            "id": meta["id"],
            "name": meta["name"],
            "seat": meta.get("seat", ""),
            "source": meta["source"],
            "image_count": len(meta.get("images", [])),
            "extract_notes": meta.get("notes", []),
        }
        raw_path = dest / "vision_raw.txt"
        if not meta.get("images"):
            base.update(
                {
                    "scores": {k: 0 for k in [
                        "A_classname","B_main_comment","C_student_class","D_fields",
                        "E_sayHello","F_instantiate","G_run"
                    ]},
                    "total": 0,
                    "deductions": "无截图材料（仅填姓名等信息或空卷）",
                    "needs_review": True,
                    "review_reason": "未提取到图片",
                    "confidence": 0.0,
                    "visible": "",
                    "code_summary": "",
                    "console_output": "",
                }
            )
            results.append(base)
            (dest / "grade.json").write_text(
                json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"0   {meta['id']} (no image)")
            continue

        if not raw_path.exists():
            base.update(
                {
                    "scores": {k: 0 for k in [
                        "A_classname","B_main_comment","C_student_class","D_fields",
                        "E_sayHello","F_instantiate","G_run"
                    ]},
                    "total": 0,
                    "deductions": "缺少识图原始结果",
                    "needs_review": True,
                    "review_reason": "无 vision_raw",
                    "confidence": 0.0,
                }
            )
            results.append(base)
            print(f"?   {meta['id']} missing raw")
            continue

        raw = raw_path.read_text(encoding="utf-8")
        try:
            if '"_multi_raw"' in raw:
                # 外层先标准 json 解析，再清洗各图块（避免噪声行拆坏 JSON 字符串）
                try:
                    outer = json.loads(raw)
                except Exception:
                    outer = parse_json_loose(raw)
                from grade_exam import strip_vision_noise

                cleaned = [strip_vision_noise(c) for c in outer.get("_multi_raw", [])]
                graded = merge_multi(json.dumps({"_multi_raw": cleaned}, ensure_ascii=False))
            else:
                graded = parse_json_loose(raw)
                if "_multi_raw" in graded:
                    graded = merge_multi(json.dumps(graded, ensure_ascii=False))
            graded["scores"] = score_caps(graded.get("scores") or {})
            graded["total"] = sum(graded["scores"].values())
            if meta.get("notes"):
                graded["needs_review"] = True
                graded["review_reason"] = (
                    (graded.get("review_reason") or "") + "；" + "；".join(meta["notes"])
                ).strip("；")
            base.update(graded)
            print(f"{base['total']:3d} {meta['id']}")
        except Exception as e:
            base.update(
                {
                    "scores": {k: 0 for k in [
                        "A_classname","B_main_comment","C_student_class","D_fields",
                        "E_sayHello","F_instantiate","G_run"
                    ]},
                    "total": 0,
                    "deductions": f"JSON解析失败: {e}",
                    "needs_review": True,
                    "review_reason": "模型输出无法解析为JSON",
                    "confidence": 0.1,
                    "visible": raw[:300],
                    "code_summary": "",
                    "console_output": "",
                }
            )
            print(f"ERR {meta['id']}: {e}")

        (dest / "grade.json").write_text(
            json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        results.append(base)

    results.sort(key=lambda x: (x.get("seat") or "ZZZ", x.get("name") or ""))
    OUT.write_text(
        json.dumps({"results": results, "errors": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    totals = [r["total"] for r in results]
    print(
        f"\nSaved {OUT} n={len(results)} avg={sum(totals)/len(totals):.1f} "
        f"review={sum(1 for r in results if r.get('needs_review'))}"
    )


if __name__ == "__main__":
    main()
