# -*- coding: utf-8 -*-
"""Traducciones. Cada idioma es un .txt en la carpeta «languajes»:

    # comentario
    Texto original en español => Translated text

El texto original es el que está en el código. \\n representa un salto de línea. Si una línea no está
traducida se muestra el original. «english» es el idioma por defecto.
"""
from __future__ import annotations

from pathlib import Path

FOLDER = Path(__file__).resolve().parent / "languajes"
DEFAULT = "english"
_table: dict[str, str] = {}
current = DEFAULT


def available() -> list[str]:
    if not FOLDER.is_dir():
        return []
    return sorted(f.stem for f in FOLDER.glob("*.txt"))


def load(name: str):
    global _table, current
    _table, current = {}, name
    f = FOLDER / f"{name}.txt"
    if not f.is_file():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or " => " not in line:
            continue
        src, dst = line.split(" => ", 1)
        _table[src.replace("\\n", "\n")] = dst.replace("\\n", "\n")


def tr(s: str) -> str:
    if not s or not _table:
        return s
    t = _table.get(s)
    if t is not None:
        return t
    if "\n" in s:                      # mensajes de varias líneas: se traduce línea a línea
        return "\n".join(tr(x) for x in s.split("\n"))
    st = s.strip()
    if st != s and st in _table:      # conserva los espacios de los extremos
        return s.replace(st, _table[st])
    return s