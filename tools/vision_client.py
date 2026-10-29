# -*- coding: utf-8 -*-
"""通义千问多模态识图（纯 Python，无 Node 依赖）。"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = os.environ.get("VISION_MODEL", "qwen3.8-max")


def get_api_key(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    return (
        os.environ.get("DASHSCOPE_API_KEY", "").strip()
        or os.environ.get("CODEJUDGE_API_KEY", "").strip()
    )


def _mime(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {
        "jpg": "jpeg",
        "jpeg": "jpeg",
        "png": "png",
        "gif": "gif",
        "webp": "webp",
        "bmp": "bmp",
    }.get(ext, "jpeg")


def call_vision(
    image_path: Path,
    prompt: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout: int = 180,
    retries: int = 2,
) -> str:
    key = get_api_key(api_key)
    if not key:
        raise RuntimeError(
            "未配置 API Key。请在界面填写，或设置环境变量 DASHSCOPE_API_KEY。"
        )
    model = model or DEFAULT_MODEL
    base = (base_url or os.environ.get("DASHSCOPE_BASE_URL") or DEFAULT_BASE).rstrip("/")
    data = image_path.read_bytes()
    data_url = f"data:image/{_mime(image_path)};base64,{base64.b64encode(data).decode('ascii')}"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": False,
        "max_tokens": 2048,
    }
    body = json.dumps(payload).encode("utf-8")
    url = f"{base}/chat/completions"
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            obj = json.loads(raw)
            content = obj.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                raise RuntimeError(f"识图返回空内容: {raw[:300]}")
            return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        except Exception as e:
            last_err = e
            if isinstance(e, urllib.error.HTTPError):
                try:
                    detail = e.read().decode("utf-8", errors="replace")[:400]
                except Exception:
                    detail = str(e)
                last_err = RuntimeError(f"API HTTP {e.code}: {detail}")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"识图失败: {last_err}")
