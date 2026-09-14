"""
ncompiler/nimpaths.py — Nim path constants
Converted from compiler/nimpaths.nim
"""
from __future__ import annotations

htmldocsDirname = "htmldocs"
dotdotMangle = "_._"

def interp(path: str, nimr: str) -> str:
    return path.replace("$nimr", nimr)
