# -*- coding: utf-8 -*-
"""扫描学生答卷，提取截图到 work/submissions/<id>/"""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

from paths import ROOT, SUBMISSIONS_OUT, submissions_dir

SRC = submissions_dir()
OUT = SUBMISSIONS_OUT
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def basename_no_doc_ext(raw: str) -> str:
    """去掉 .doc/.docx；勿对 IP 文件夹用 Path.stem（会误切 .166_姓名）。"""
    s = Path(raw).name
    lower = s.lower()
    for ext in (".docx", ".doc"):
        if lower.endswith(ext):
            return s[: -len(ext)]
    return s


def parse_name(raw: str) -> str:
    """从文件/文件夹名尽量解析出姓名。"""
    s = basename_no_doc_ext(raw)
    s = s.strip().rstrip("、,，. ")
    # 去掉常见座位号/IP/班级前缀
    s = re.sub(r"^\d{1,3}(?:\.\d{1,3}){3}_", "", s)
    s = re.sub(r"^[CcGg]\d{1,3}_", "", s, flags=re.I)
    # 去掉年级+专业班级前缀（不含具体校名）
    s = re.sub(r"^\d{2}计算机(?:一班|1班|1)?", "", s)
    s = re.sub(r"^计算机(?:一班|1班|1)?", "", s)
    s = re.sub(r"^\d{1,3}号?", "", s)
    s = s.strip(" _-")
    # 取末尾连续中文（姓名）
    m = re.search(r"([\u4e00-\u9fff]{2,4})$", s)
    if m:
        return m.group(1)
    # 整段中文
    m = re.search(r"([\u4e00-\u9fff]{2,8})", s)
    if m:
        return m.group(1)
    return s or raw


def parse_seat(raw: str) -> str:
    m = re.search(r"(?<![A-Za-z0-9])([CcGg]\d{1,3})(?![0-9])", raw)
    return m.group(1).upper() if m else ""


def safe_id(name: str, source: str, used: set[str]) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", name, flags=re.ASCII) or "unknown"
    base = base.strip("_") or "unknown"
    seat = parse_seat(source)
    cand = f"{seat}_{base}" if seat else base
    if cand not in used:
        used.add(cand)
        return cand
    i = 2
    while f"{cand}_{i}" in used:
        i += 1
    cand = f"{cand}_{i}"
    used.add(cand)
    return cand


def extract_docx_images(docx: Path, dest: Path) -> list[str]:
    saved: list[str] = []
    with zipfile.ZipFile(docx) as z:
        media = [
            n
            for n in z.namelist()
            if (
                (n.startswith("word/media/") or n.startswith("word/embeddings/"))
                and Path(n).suffix.lower() in IMG_EXTS
            )
            or (
                n.startswith("word/")
                and Path(n).suffix.lower() in IMG_EXTS
            )
        ]
        # 去重保序
        seen = set()
        uniq = []
        for n in sorted(media):
            if n not in seen:
                seen.add(n)
                uniq.append(n)
        for i, n in enumerate(uniq, 1):
            data = z.read(n)
            ext = Path(n).suffix.lower() or ".png"
            out = dest / f"img_{i:02d}{ext}"
            out.write_bytes(data)
            saved.append(out.name)
    return saved


def extract_doc_via_word(doc: Path, dest: Path) -> list[str]:
    """用 Word COM 另存为 docx 再抽图；失败则返回空。"""
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return []
    tmp = dest / "_tmp.docx"
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        d = word.Documents.Open(str(doc.resolve()))
        # 16 = wdFormatXMLDocument
        d.SaveAs2(str(tmp.resolve()), FileFormat=16)
        d.Close(False)
        return extract_docx_images(tmp, dest)
    except Exception as e:
        (dest / "extract_error.txt").write_text(str(e), encoding="utf-8")
        return []
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass


def collect_entries() -> list[dict]:
    entries: list[dict] = []
    for p in sorted(SRC.iterdir(), key=lambda x: x.name.lower()):
        if p.name.startswith("."):
            continue
        if p.is_file() and p.suffix.lower() in {".docx", ".doc"}:
            entries.append(
                {
                    "name": parse_name(p.name),
                    "seat": parse_seat(p.name),
                    "source": str(p.relative_to(ROOT)),
                    "kind": "file",
                    "path": p,
                }
            )
        elif p.is_dir():
            files = list(p.rglob("*"))
            docs = [f for f in files if f.is_file() and f.suffix.lower() in {".docx", ".doc"}]
            imgs = [f for f in files if f.is_file() and f.suffix.lower() in IMG_EXTS]
            entries.append(
                {
                    "name": parse_name(p.name),
                    "seat": parse_seat(p.name),
                    "source": str(p.relative_to(ROOT)),
                    "kind": "dir",
                    "path": p,
                    "docs": docs,
                    "imgs": imgs,
                }
            )
    return entries


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    used: set[str] = set()
    manifest = []
    entries = collect_entries()

    for e in entries:
        sid = safe_id(e["name"], e["source"], used)
        dest = OUT / sid
        dest.mkdir(parents=True)
        images: list[str] = []
        notes: list[str] = []

        if e["kind"] == "file":
            p: Path = e["path"]
            if p.suffix.lower() == ".docx":
                images = extract_docx_images(p, dest)
            else:
                images = extract_doc_via_word(p, dest)
                if not images:
                    notes.append("旧版.doc提取失败或无图，需人工复核")
        else:
            # 目录：先拷贝裸图，再抽 doc/docx
            for i, img in enumerate(sorted(e.get("imgs", [])), 1):
                ext = img.suffix.lower()
                out = dest / f"raw_{i:02d}{ext}"
                shutil.copy2(img, out)
                images.append(out.name)
            for doc in sorted(e.get("docs", [])):
                if doc.suffix.lower() == ".docx":
                    more = extract_docx_images(doc, dest)
                else:
                    more = extract_doc_via_word(doc, dest)
                # 避免重名
                renumbered = []
                base = len(images)
                for j, name in enumerate(more, 1):
                    src = dest / name
                    new_name = f"doc_{base + j:02d}{Path(name).suffix.lower()}"
                    src.rename(dest / new_name)
                    renumbered.append(new_name)
                images.extend(renumbered)

        if not images:
            notes.append("未找到可用截图")

        meta = {
            "id": sid,
            "name": e["name"],
            "seat": e["seat"],
            "source": e["source"],
            "images": images,
            "notes": notes,
        }
        (dest / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest.append(meta)
        print(f"[OK] {sid}: {len(images)} images | {e['source']}")

    from paths import WORK_DIR

    man_path = WORK_DIR / "manifest.json"
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTotal students: {len(manifest)}")
    print(f"Manifest: {man_path}")


if __name__ == "__main__":
    main()
