"""
ncompiler/ropes.py — Rope type (simplified as string alias)
Converted from compiler/ropes.nim
"""
from __future__ import annotations

Rope = str

def rope(s: str = "") -> Rope:
    return s

def newStringOfCap(cap: int) -> str:
    return ""
