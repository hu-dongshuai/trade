from __future__ import annotations

import re


def normalize_symbol_name(symbol: str, symbol_name: str | None = None) -> str | None:
    if not symbol_name:
        return None
    name = symbol_name.strip()
    if not name or name == symbol:
        return None
    if not re.search(r"[\u4e00-\u9fff]", name):
        return None
    return name


def display_symbol(symbol: str, symbol_name: str | None = None) -> str:
    normalized_name = normalize_symbol_name(symbol, symbol_name)
    if normalized_name:
        return f"{normalized_name}({symbol})"
    return symbol
