from __future__ import annotations

import json
import re
from pathlib import Path


_FENCED_BLOCK_RE = re.compile(r"```(?P<lang>[a-zA-Z0-9_-]*)\s*\n(?P<body>.*?)\n```", re.DOTALL)


def read_text_payload(path: Path) -> str:
    content = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() != ".md":
        return content
    block = _extract_first_code_block(content)
    return block if block is not None else content


def read_json_payload(path: Path) -> dict:
    payload = read_text_payload(path).strip()
    if path.suffix.lower() == ".md":
        payload = _normalize_json_payload(payload)
    return json.loads(payload)


def write_json_payload(path: Path, payload: dict, language: str = "json", title: str | None = None) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    if path.suffix.lower() == ".md":
        title_line = f"# {title}\n\n" if title else ""
        path.write_text(f"{title_line}```{language}\n{body}\n```\n", encoding="utf-8")
        return
    path.write_text(body, encoding="utf-8")


def parse_env_text(path: Path) -> str:
    payload = read_text_payload(path).strip()
    if path.suffix.lower() != ".md":
        return payload
    return _normalize_env_payload(payload)


def _extract_first_code_block(content: str) -> str | None:
    match = _FENCED_BLOCK_RE.search(content)
    if not match:
        return None
    return match.group("body")


def _normalize_json_payload(payload: str) -> str:
    stripped = payload.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    match = re.search(r"(\{.*\}|\[.*\])", stripped, re.DOTALL)
    return match.group(1) if match else stripped


def _normalize_env_payload(payload: str) -> str:
    lines: list[str] = []
    for raw in payload.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith("#") or "=" in line:
            lines.append(raw)
    return "\n".join(lines).strip()
