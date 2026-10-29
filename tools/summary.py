# -*- coding: utf-8 -*-
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import GRADES_JSON

rs = json.loads(GRADES_JSON.read_text(encoding="utf-8"))["results"]
print("需复核:")
for r in rs:
    if r.get("needs_review"):
        reason = r.get("review_reason") or r.get("deductions", "")
        print(f"  {r.get('seat') or '':4s} {r['name']:8s} {r['total']:3d} | {reason}")
totals = [r["total"] for r in rs]
print("成绩分布:")
for lo, hi, label in [(90, 100, "优秀90+"), (60, 89, "及格60-89"), (1, 59, "不及格1-59"), (0, 0, "零分")]:
    n = sum(1 for t in totals if lo <= t <= hi)
    print(f"  {label}: {n}")
print("均分", round(sum(totals) / len(totals), 1), "人数", len(rs))
