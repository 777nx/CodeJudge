# -*- coding: utf-8 -*-
"""调用视觉模型按宽松细则批改，结果写入 work/grades.json"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from pathlib import Path

import paths
from vision_client import call_vision as vision_call

MAX_WORKERS = 3
_API_KEY: str | None = None


def set_api_key(key: str | None) -> None:
    global _API_KEY
    _API_KEY = (key or "").strip() or None

RUBRIC_PROMPT = """你是高校《Java程序设计》老师，正在批改期中实操卷。请严格只根据图片内容评分。

【试卷满分100】
第一题操作题40分：
A. 新建类，类名严格为 TestStudent（20分）——类名完全正确给20；接近但拼写错误给10；没有该类给0。
B. 含完整 main 方法，且有注释说明功能（20分）——有完整 main 给5；有任何能说明用途的注释（类注释或方法注释均可）给15；完全无注释则注释部分按扣15理解（即有main无注释最多5分）。宽松：中英文注释、简单说明都算有注释。

第二题编程题60分（在 TestStudent 中完成）：
C. 另外定义 Student 类（10）——有即可，可与 TestStudent 同文件。
D. name 与 age 两个成员变量（10）——有这两个字段即可，类型宽松。
E. sayHello 方法，用 println 输出含姓名和年龄的自我介绍（10）——大意是「大家好+姓名+年龄」即可满分，用词/标点不同不扣。
F. 在 TestStudent 中实例化并调用方法（15）——有 new 并调用 sayHello（或等价）即可。
G. 能运行且有控制台输出（15）——图中能看到运行成功/exit code 0/正确输出给满分；能看到代码逻辑正确但无运行截图给10；明显编译/运行失败给0-5。

【宽松总原则】能看出意图就倾向给分；缺某一项截图不整卷归零，按能核实的给分。

【输出要求】只输出一个 JSON 对象，不要 Markdown 代码围栏，字段如下：
{
  "visible": "简要描述图中可见内容",
  "has_project_structure": true/false,
  "has_code": true/false,
  "has_console": true/false,
  "code_summary": "能辨认的关键代码要点",
  "console_output": "能辨认的控制台输出，没有则空字符串",
  "scores": {
    "A_classname": 0-20,
    "B_main_comment": 0-20,
    "C_student_class": 0-10,
    "D_fields": 0-10,
    "E_sayHello": 0-10,
    "F_instantiate": 0-15,
    "G_run": 0-15
  },
  "total": 0-100,
  "deductions": "扣分说明，无则写无",
  "needs_review": true/false,
  "review_reason": "若需复核写原因，否则空字符串",
  "confidence": 0.0-1.0
}
若图片模糊/无关/空白：相应项给0，needs_review=true，confidence偏低。
"""


def call_vision(image_paths: list[Path]) -> str:
    """多图：串行调用后拼接；单图直接调用。"""
    parts = []
    for img in image_paths:
        prompt = RUBRIC_PROMPT
        if len(image_paths) > 1:
            prompt += (
                f"\n这是该生提交的第 {image_paths.index(img)+1}/{len(image_paths)} 张图。"
                "请先完整观察本图。"
            )
        text = vision_call(img, prompt, api_key=_API_KEY)
        parts.append(strip_vision_noise(text.strip()))
    if len(parts) == 1:
        return parts[0]
    return json.dumps({"_multi_raw": parts}, ensure_ascii=False)


def strip_vision_noise(text: str) -> str:
    """去掉 vision.js / dotenv 注入的噪声行。"""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("◇") or "injected env" in s:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def parse_json_loose(text: str) -> dict:
    text = strip_vision_noise(text.strip())
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # 噪声行已剔除后，第一个 { 即为根对象。
    # 注意：不能用 scores 前的 rfind('{')，因为 code_summary 里常含 Java 代码的 { }。
    start = text.find("{")
    if start < 0:
        raise ValueError("未找到 JSON 对象")
    # 用括号平衡截取完整根对象，避免被字符串内 } 截断过多/过少时仍尽量可用
    depth = 0
    in_str = False
    escape = False
    end = -1
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        end = text.rfind("}")
    text = text[start : end + 1]
    return json.loads(text)


def merge_multi(raw_text: str) -> dict:
    data = parse_json_loose(raw_text)
    if "_multi_raw" not in data:
        return data
    parsed = []
    for chunk in data["_multi_raw"]:
        try:
            parsed.append(parse_json_loose(strip_vision_noise(chunk)))
        except Exception:
            continue
    if not parsed:
        return {
            "visible": "多图解析失败",
            "scores": {
                "A_classname": 0,
                "B_main_comment": 0,
                "C_student_class": 0,
                "D_fields": 0,
                "E_sayHello": 0,
                "F_instantiate": 0,
                "G_run": 0,
            },
            "total": 0,
            "deductions": "识图结果无法解析",
            "needs_review": True,
            "review_reason": "多图JSON解析失败",
            "confidence": 0.2,
            "has_project_structure": False,
            "has_code": False,
            "has_console": False,
            "code_summary": "",
            "console_output": "",
        }

    keys = [
        "A_classname",
        "B_main_comment",
        "C_student_class",
        "D_fields",
        "E_sayHello",
        "F_instantiate",
        "G_run",
    ]
    scores = {k: max(int(p.get("scores", {}).get(k, 0) or 0) for p in parsed) for k in keys}
    total = sum(scores.values())
    return {
        "visible": " | ".join(str(p.get("visible", "")) for p in parsed),
        "has_project_structure": any(p.get("has_project_structure") for p in parsed),
        "has_code": any(p.get("has_code") for p in parsed),
        "has_console": any(p.get("has_console") for p in parsed),
        "code_summary": " || ".join(str(p.get("code_summary", "")) for p in parsed),
        "console_output": " || ".join(
            str(p.get("console_output", "")) for p in parsed if p.get("console_output")
        ),
        "scores": scores,
        "total": total,
        "deductions": "；".join(
            str(p.get("deductions", "")) for p in parsed if p.get("deductions") and p.get("deductions") != "无"
        )
        or "无",
        "needs_review": any(p.get("needs_review") for p in parsed),
        "review_reason": "；".join(
            str(p.get("review_reason", "")) for p in parsed if p.get("review_reason")
        ),
        "confidence": min(float(p.get("confidence", 0.5) or 0.5) for p in parsed),
    }


def grade_one(meta_path: Path) -> dict:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    dest = meta_path.parent
    images = [dest / n for n in meta.get("images", []) if (dest / n).exists()]
    result = {
        "id": meta["id"],
        "name": meta["name"],
        "seat": meta.get("seat", ""),
        "source": meta["source"],
        "image_count": len(images),
        "extract_notes": meta.get("notes", []),
    }
    if not images:
        result.update(
            {
                "scores": {
                    "A_classname": 0,
                    "B_main_comment": 0,
                    "C_student_class": 0,
                    "D_fields": 0,
                    "E_sayHello": 0,
                    "F_instantiate": 0,
                    "G_run": 0,
                },
                "total": 0,
                "deductions": "无截图材料",
                "needs_review": True,
                "review_reason": "未提取到图片",
                "confidence": 0.0,
                "visible": "",
                "code_summary": "",
                "console_output": "",
            }
        )
        return result

    raw = call_vision(images)
    raw_path = dest / "vision_raw.txt"
    raw_path.write_text(raw, encoding="utf-8")
    try:
        graded = merge_multi(raw) if '"_multi_raw"' in raw or raw.strip().startswith("{") and "_multi_raw" in raw else parse_json_loose(raw)
        if "_multi_raw" in graded:
            graded = merge_multi(raw)
    except Exception as e:
        graded = {
            "visible": raw[:500],
            "scores": {
                "A_classname": 0,
                "B_main_comment": 0,
                "C_student_class": 0,
                "D_fields": 0,
                "E_sayHello": 0,
                "F_instantiate": 0,
                "G_run": 0,
            },
            "total": 0,
            "deductions": f"JSON解析失败: {e}",
            "needs_review": True,
            "review_reason": "模型输出无法解析为JSON",
            "confidence": 0.1,
            "code_summary": "",
            "console_output": "",
        }

    # 规范化总分
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
    if meta.get("notes"):
        graded["needs_review"] = True
        graded["review_reason"] = (graded.get("review_reason") or "") + "；" + "；".join(meta["notes"])

    result.update(graded)
    (dest / "grade.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def main(log: Callable[[str], None] | None = None) -> None:
    def _log(msg: str) -> None:
        if log:
            log(msg)
        else:
            print(msg)

    subs = paths.submissions_out()
    metas = sorted(subs.glob("*/meta.json"))
    _log(f"开始评分：{len(metas)} 份，并发 {MAX_WORKERS}")
    results = []
    errors = []

    def job(mp: Path):
        r = grade_one(mp)
        _log(f"  {r['id']}: {r.get('total', 0)}  复核={r.get('needs_review')}")
        return r

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(job, m): m for m in metas}
        for fut in as_completed(futs):
            try:
                results.append(fut.result())
            except Exception as e:
                mp = futs[fut]
                errors.append({"meta": str(mp), "error": str(e)})
                _log(f"  ERROR {mp.parent.name}: {e}")

    results.sort(key=lambda x: (x.get("seat") or "ZZZ", x.get("name") or ""))
    out = paths.grades_json()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"results": results, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _log(f"已保存 {out} | 成功={len(results)} 失败={len(errors)}")


if __name__ == "__main__":
    main()
