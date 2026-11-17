"""Small text checks shared by feed parsing and translation."""
from __future__ import annotations

import re

_GARBLED = re.compile(r"(.{3,15}?)\1{3,}", re.S)  # "mainstremainstremainstre…": broken feed or model


def is_garbled(text: str | None) -> bool:
    return bool(text) and bool(_GARBLED.search(text.lower()))
