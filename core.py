# -*- coding: utf-8 -*-
"""Catálogo de elementos, modelo del proyecto, skin.ini y exportación .osk."""
from __future__ import annotations

import copy
import json
import os
import random
import re
import zipfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFontDatabase, QImage

import gens
from gfx import BORDERS, FILLS, SHAPES, shade

FORMAT_VERSION = 3
ASPECTS = {"16:9": 16 / 9, "16:10": 16 / 10, "4:3": 4 / 3, "21:9": 21 / 9}
MODES = [("global", "Tema global"), ("std", "osu!standard"), ("taiko", "osu!taiko"),
         ("catch", "osu!catch"), ("mania", "osu!mania"), ("menu", "Menú de osu!"),
         ("home", "Imagen del menú"), ("pause", "Menú de pausa"), ("fail", "Pantalla de fallo"),
         ("results", "Resultados"), ("mods", "Mods, modos y botones"), ("ui", "Interfaz de juego (UI)"),
         ("config", "skin.ini")]
COMPATS = ["stable/lazer", "stable", "lazer", "legacy osu!", "totally"]
LEGACY_YEARS = [str(y) for y in range(2008, 2016)]
# versión de skin.ini aproximada por build antigua (2008-2015)
LEGACY_VERSION = {"2008": "1.0", "2009": "1.0", "2010": "2.0", "2011": "2.0", "2012": "2.2", "2013": "2.3", "2014": "2.4", "2015": "2.5"}


# ----------------------------------------------------------------------
# Definición de propiedades
# ----------------------------------------------------------------------
def P(key, label, kind, default, **kw):
    return dict(key=key, label=label, kind=kind, default=default, **kw)


def sec(label):
    return dict(key=None, label=label, kind="header", default=None)


def act(name, label):
    return dict(key=None, label=label, kind="action", default=None, action=name)


def I(key, label, default, lo, hi, unit=""):
    return P(key, label, "int", default, min=lo, max=hi, unit=unit)


def C(key, label, default):
    return P(key, label, "color", default)


def B(key, label, default):
    return P(key, label, "bool", default)


def CH(key, label, default, options):
    return P(key, label, "choice", default, options=options)


def sty(shape="círculo", fill_mode="sólido", color="#ffffff", color2="#8fd3ff", border_width=0,
        border_color="#ffffff", glow=0, glow_color="#53b9ff", shadow=0, opacity=100, roundness=50,
        rotation=0, grad_angle=90, border_style="sólido", size=100, with_shape=True, size_range=(10, 300)):
    out = [sec("Forma")]
    if with_shape:
        out += [CH("shape", "Forma", shape, SHAPES), P("shape_image", "Imagen (forma «imagen propia»)", "image", ""), B("shape_image_raw", "Usar la imagen con sus colores", False),
                I("roundness", "Redondeo", roundness, 0, 100, "%"), I("rotation", "Rotación", rotation, -180, 180, "°")]
    out += [I("size", "Tamaño", size, size_range[0], size_range[1], "%"),
            sec("Relleno"), CH("fill_mode", "Tipo de relleno", fill_mode, FILLS),
            C("color", "Color", color), C("color2", "Color 2 (degradado)", color2),
            I("grad_angle", "Ángulo del degradado", grad_angle, 0, 360, "°"),
            I("opacity", "Opacidad", opacity, 0, 100, "%"),
            sec("Borde"), I("border_width", "Grosor", border_width, 0, 40, "px"),
            C("border_color", "Color del borde", border_color),
            CH("border_style", "Estilo del borde", border_style, BORDERS),
            sec("Efectos"), I("glow", "Resplandor", glow, 0, 60, "px"), C("glow_color", "Color del resplandor", glow_color),
            I("shadow", "Sombra", shadow, 0, 40, "px")]
    return out


def ring(width=6, color="#ffffff", shape="círculo", opacity=100, size=100, glow=0, glow_color="#53b9ff"):
    return [sec("Aro"), CH("shape", "Forma", shape, SHAPES), P("shape_image", "Imagen (forma «imagen propia»)", "image", ""), B("shape_image_raw", "Usar la imagen con sus colores", False), I("roundness", "Redondeo", 50, 0, 100, "%"),
            I("rotation", "Rotación", 0, -180, 180, "°"), I("size", "Tamaño", size, 10, 300, "%"),
            I("width", "Grosor del aro", width, 0, 40, "px"), C("color", "Color", color),
            I("opacity", "Opacidad", opacity, 0, 100, "%"),
            CH("border_style", "Estilo", "sólido", BORDERS),
            sec("Efectos"), I("glow", "Resplandor", glow, 0, 60, "px"), C("glow_color", "Color del resplandor", glow_color),
            I("shadow", "Sombra", 0, 0, 40, "px")]


FONTS = ["Arial", "Segoe UI", "Verdana", "Georgia", "Consolas", "Impact", "Trebuchet MS"]


def txt(font="Arial", size=46, color="#ffffff", color2="#cfd8e8", fill_mode="sólido", outline_color="#303030",
        outline_width=2, shadow=0, glow=0, glow_color="#53b9ff", bold=True, italic=False, scale=True):
    out = [sec("Texto"), P("font", "Tipografía", "font", font), I("font_size", "Tamaño de letra", size, 8, 190, "px"),
           B("bold", "Negrita", bold), B("italic", "Cursiva", italic),
           sec("Color"), CH("fill_mode", "Relleno", fill_mode, ["sólido", "degradado"]),
           C("color", "Color", color), C("color2", "Color 2 (degradado)", color2),
           sec("Contorno y efectos"), I("outline_width", "Grosor del contorno", outline_width, 0, 12, "px"),
           C("outline_color", "Color del contorno", outline_color), I("shadow", "Sombra", shadow, 0, 20, "px"),
           I("glow", "Resplandor", glow, 0, 30, "px"), C("glow_color", "Color del resplandor", glow_color)]
    if scale:
        out.insert(1, I("size", "Escala del archivo", 100, 25, 300, "%"))
    return out


def E(id, name, mode, files, desc, props, theme=True, tint=False, theme_map=None, toggle=True, hd=False):
    props = list(props)
    if theme:
        props.insert(0, B("use_theme", "Seguir el tema global", False))
    e = dict(id=id, name=name, mode=mode, files=files, desc=desc, props=props, tint=tint,
             theme=theme, theme_map=theme_map or {}, toggle=toggle, hd=hd)
    e["specs"] = {p["key"]: p for p in props if p["key"]}
    return e


PRESETS = {
    "Neón cian": dict(accent="#00f0ff", accent2="#ff2fd6", accent3="#fff200", shape="círculo", fill_mode="degradado",
                      border_style="sólido", roundness=50, glow=16, font="Segoe UI", text_color="#ffffff"),
    "Cristal": dict(accent="#bfe6ff", accent2="#ffffff", accent3="#ffe9a8", shape="círculo", fill_mode="cristal",
                    border_style="sólido", roundness=50, glow=6, font="Segoe UI", text_color="#ffffff"),
    "Sakura": dict(accent="#ff9ecb", accent2="#ffe0ef", accent3="#ffd166", shape="corazón", fill_mode="degradado",
                   border_style="sólido", roundness=60, glow=4, font="Georgia", text_color="#ffffff"),
    "Hex minimal": dict(accent="#e6e9f0", accent2="#53b9ff", accent3="#ffd166", shape="hexágono", fill_mode="sólido",
                        border_style="sólido", roundness=50, glow=0, font="Segoe UI", text_color="#ffffff"),
    "Arcade retro": dict(accent="#ff5c33", accent2="#ffd400", accent3="#33ff99", shape="cuadrado redondeado",
                         fill_mode="degradado", border_style="doble", roundness=20, glow=0, font="Consolas",
                         text_color="#ffffff"),
    "Estelar": dict(accent="#ffd166", accent2="#ff7a59", accent3="#7df9ff", shape="estrella", fill_mode="degradado",
                    border_style="sólido", roundness=50, glow=10, font="Verdana", text_color="#ffffff"),
}
HARMONIES = ["análogo", "complementario", "triádico", "tetrádico", "monocromático"]

THEME_PROPS = [
    sec("Compatibilidad"),
    CH("compat", "Compatibilidad con", "stable/lazer", COMPATS),
    CH("legacy_year", "Build legacy (solo «legacy osu!»)", "2015", LEGACY_YEARS),
    sec("Estilo global (para todos los elementos que lo sigan)"),
    CH("shape", "Forma de círculos, notas y frutas", "círculo", SHAPES),
    CH("fill_mode", "Relleno", "sólido", FILLS), CH("border_style", "Estilo de borde", "sólido", BORDERS),
    I("roundness", "Redondeo", 50, 0, 100, "%"), I("glow", "Resplandor", 0, 0, 60, "px"),
    P("font", "Tipografía", "font", "Arial"),
    act("font_all", "Usar esta tipografía en TODO (elementos, lienzos y textos)"),
    sec("Paleta del tema"),
    C("accent", "Acento principal", "#53b9ff"), C("accent2", "Acento secundario", "#ff7ab6"),
    C("accent3", "Acento 3 (destacados)", "#ffd166"), C("text_color", "Color de texto", "#ffffff"),
    C("outline_color", "Color de contorno", "#202020"),
    sec("Temas listos"),
    CH("preset", "Tema", "Neón cian", list(PRESETS)), act("apply_preset", "Aplicar tema listo"),
    sec("Generador de paleta"),
    C("base_color", "Color base", "#53b9ff"), CH("harmony", "Armonía", "análogo", HARMONIES),
    act("apply_harmony", "Aplicar armonía (combos + tema)"), act("random_palette", "Paleta aleatoria"),
    sec("Aplicación"),
    act("theme_all_on", "Hacer que todos los elementos sigan el tema"),
    act("theme_all_off", "Que ningún elemento siga el tema"),
    sec("Recursos"),
    act("import_font", "Importar fuente (.ttf / .otf)…"),
]

HITS_COLORS = [C("color0", "Color MISS", "#ff4d4d"), C("color50", "Color 50", "#ffb347"),
               C("color100", "Color 100", "#6ad66a"), C("color300", "Color 300", "#53b9ff")]

ELEMENTS = [
    E("theme", "Estilo y paleta", "global", [], "Un solo lugar para cambiar la forma, el relleno, los bordes, la tipografía y la paleta "
      "de TODA la skin. Activa «Seguir el tema global» en cada elemento (o usa el botón de abajo).",
      THEME_PROPS, theme=False, toggle=False),
    # ---- standard --------------------------------------------------
    E("hitcircle", "Hit circle", "std", ["hitcircle.png"],
      "Cuerpo del círculo. osu! lo multiplica por el color del combo, déjalo blanco para que mande el combo.",
      sty(), tint=True),
    E("hitcircleoverlay", "Hit circle overlay", "std", ["hitcircleoverlay.png"],
      "Aro encima del círculo; no se tiñe con el combo.", ring(6)),
    E("approachcircle", "Approach circle", "std", ["approachcircle.png"],
      "Aro que se encoge hacia el círculo; se tiñe con el combo.", ring(4), tint=True),
    E("numbers", "Números del combo", "std", ["default-0.png … default-9.png"],
      "Dígitos del combo con la tipografía que elijas (se hornean en PNG, no hace falta instalar la fuente en otro PC).",
      txt()),
    E("sliderb", "Slider ball", "std", ["sliderb.png"], "Bola que recorre el slider.",
      sty(opacity=35, border_width=6)),
    E("sliderfollowcircle", "Slider follow circle", "std", ["sliderfollowcircle.png"],
      "Círculo que rodea la bola.", sty(opacity=15, border_width=6)),
    E("reversearrow", "Reverse arrow", "std", ["reversearrow.png"], "Flecha de los sliders con repetición.",
      sty(shape="flecha", rotation=90, size=100)),
    E("sliderscorepoint", "Slider tick", "std", ["sliderscorepoint.png"], "Puntos intermedios del slider.",
      sty(size=100)),
    E("cursor", "Cursor", "std", ["cursor.png"], "Cursor del jugador.",
      sty(fill_mode="vacío", border_width=4) + [B("dot", "Punto central", True)]),
    E("cursortrail", "Cursor trail", "std", ["cursortrail.png"], "Estela del cursor.",
      [C("color", "Color", "#ffffff"), I("opacity", "Opacidad", 100, 0, 100, "%"),
       I("hardness", "Dureza del centro", 0, 0, 95, "%"), I("size", "Tamaño", 100, 10, 300, "%")], theme=False),
    E("inputoverlay", "Contadores de teclado (K1 K2 M1 M2)", "std", ["inputoverlay-key.png", "inputoverlay-background.png"],
      "Tecla y marco del contador de pulsaciones que osu! dibuja a la derecha.",
      sty(shape="cuadrado redondeado", roundness=25, border_width=3, size=100)),
    E("hits", "Juicios (miss, 50, 100, 300)", "std", ["hit0.png", "hit50.png", "hit100.png", "hit300.png"],
      "Texto que aparece al golpear.", txt(size=64, outline_width=3) + [sec("Colores")] + HITS_COLORS),
    # ---- taiko -----------------------------------------------------
    E("taiko_circle", "Nota taiko (don/kat)", "taiko", ["taikohitcircle.png", "taikohitcircleoverlay.png"],
      "El cuerpo se tiñe de rojo (don) o azul (kat) dentro del juego, déjalo blanco.",
      sty(border_width=0) + [sec("Overlay"), C("overlay_color", "Color del aro", "#ffffff"),
                              I("overlay_width", "Grosor del aro", 6, 0, 30, "px")], tint=True),
    E("taiko_big", "Nota taiko grande", "taiko", ["taikobigcircle.png", "taikobigcircleoverlay.png"],
      "Versión grande (finisher).",
      sty() + [sec("Overlay"), C("overlay_color", "Color del aro", "#ffffff"),
               I("overlay_width", "Grosor del aro", 8, 0, 30, "px")], tint=True),
    E("taiko_roll", "Drumroll", "taiko", ["taiko-roll-middle.png", "taiko-roll-end.png"],
      "Tramo central y extremo del drumroll.", sty(color="#ffd166", border_width=3, border_color="#ffffff")),
    E("taiko_bar", "Pista y panel del tambor", "taiko", ["taiko-bar-left.png", "taiko-bar-right.png"],
      "Panel izquierdo (tambor) y carril por donde viajan las notas.",
      sty(fill_mode="degradado", color="#3a2a4a", color2="#1c1426", with_shape=False) +
      [sec("Carril"), C("lane_color", "Color del carril", "#2a2f3d"), C("lane_color2", "Color 2 del carril", "#161a24")]),
    E("taiko_drum", "Tambor (inner/outer)", "taiko", ["taiko-drum-inner.png", "taiko-drum-outer.png"],
      "Tambor que se ilumina al pulsar.",
      sty(color="#e63946", border_width=0) + [sec("Aro exterior"), C("outer_color", "Color", "#e6e6e6"),
                                              I("outer_width", "Grosor", 14, 0, 40, "px")]),
    # ---- catch -----------------------------------------------------
    E("catch_fruits", "Frutas", "catch", ["fruit-apple/grapes/pear/oranges/drop/bananas (+ -overlay).png"],
      "Seis frutas con el mismo estilo. El cuerpo se tiñe con el combo; el overlay trae contorno y detalles.",
      sty(border_width=0, with_shape=False, glow=0) + [C("detail_color", "Color de detalles (overlay)", "#ffffff")],
      tint=True),
    E("catch_catcher", "Catcher (plato)", "catch", ["fruit-catcher-idle/kiai/fail.png"],
      "El plato que mueve el jugador.",
      sty(color="#e8eefc", color2="#8aa0c8", fill_mode="degradado", border_width=3, with_shape=False) +
      [sec("Catcher"), CH("catcher_shape", "Forma", "plato", ["plato", "cuenco", "trapecio"]),
       C("kiai_color", "Color en kiai", "#ffd166"), C("fail_color", "Color al fallar", "#7a7f8c")]),
    # ---- mania -----------------------------------------------------
    E("mania_notes", "Notas (diseñador de formas)", "mania",
      ["mania-note1/2/S (+H, L, T).png", "versiones rotadas por columna"],
      "Elige cualquier forma para las notas: flecha, círculo, barra, diamante, estrella… Las formas direccionales "
      "(flecha, chevron, triángulo) giran solas según la columna.",
      [sec("Forma de la nota"), CH("note_shape", "Forma", "círculo", ["barra"] + SHAPES), P("shape_image", "Imagen (forma «imagen propia»)", "image", ""), B("shape_image_raw", "Usar la imagen con sus colores", False),
       B("rotate_by_column", "Rotar por columna (flechas)", True),
       I("note_height", "Alto de la barra", 38, 8, 140, "%"),
       I("roundness", "Redondeo", 50, 0, 100, "%"), I("rotation", "Rotación extra", 0, -180, 180, "°"),
       I("size", "Tamaño", 100, 20, 200, "%"),
       sec("Colores por tipo de columna"), C("color1", "Tipo 1", "#ffc0cb"),
       C("color2", "Tipo 2", "#ffc0cb"), C("colorS", "Centro (S)", "#ffc0cb"),
       sec("Relleno y borde"), CH("fill_mode", "Relleno", "sólido", FILLS),
       I("grad_angle", "Ángulo del degradado", 90, 0, 360, "°"), I("opacity", "Opacidad", 100, 0, 100, "%"),
       I("border_width", "Grosor del borde", 4, 0, 30, "px"), C("border_color", "Color del borde", "#ffffff"),
       CH("border_style", "Estilo del borde", "sólido", BORDERS),
       sec("Efectos"), I("glow", "Resplandor", 0, 0, 60, "px"), C("glow_color", "Color del resplandor", "#53b9ff"),
       I("shadow", "Sombra", 0, 0, 40, "px"),
       sec("Hold notes (LN)"), CH("tail_style", "Final del hold", "punta", ["punta", "igual", "plano", "ninguno"]),
       C("hold_head_color", "Color de la cabeza", "#faa8ff"), C("hold_body_color", "Color del cuerpo", "#8c8c92"),
       I("body_width", "Ancho del cuerpo", 83, 10, 100, "%"), I("body_opacity", "Opacidad del cuerpo", 100, 0, 100, "%")],
      theme_map={"note_shape": "shape"}),
    E("mania_keys", "Teclas (receptores)", "mania", ["mania-key1/2/S.png", "mania-key1/2/SD.png"],
      "Teclas de abajo, sueltas y pulsadas.",
      [sec("Forma"), CH("key_shape", "Forma", "círculo", SHAPES), P("shape_image", "Imagen (forma «imagen propia»)", "image", ""), B("shape_image_raw", "Usar la imagen con sus colores", False), I("roundness", "Redondeo", 50, 0, 100, "%"),
       I("key_height", "Alto de la tecla", 100, 30, 220, "%"), I("size", "Tamaño", 100, 20, 200, "%"),
       I("key_lift", "Subir receptores (desde abajo de la pantalla)", 0, 0, 400, "px"),
       B("show_note_icon", "Mostrar icono de nota", False), CH("icon_shape", "Icono", "flecha", SHAPES),
       sec("Colores"), C("color1", "Tipo 1", "#2b3042"), C("color2", "Tipo 2", "#233248"), C("colorS", "Centro", "#3a3350"),
       CH("fill_mode", "Relleno", "vacío", FILLS), I("grad_angle", "Ángulo", 90, 0, 360, "°"),
       I("opacity", "Opacidad", 100, 0, 100, "%"),
       sec("Borde"), I("border_width", "Grosor", 8, 0, 30, "px"), C("border_color", "Color", "#bdbdbd"),
       CH("border_style", "Estilo", "sólido", BORDERS),
       sec("Efectos"), I("pressed_glow", "Resplandor al pulsar", 14, 0, 50, "px"), I("shadow", "Sombra", 0, 0, 40, "px"),
       I("rotation", "Rotación", 0, -180, 180, "°")], theme=False),
    E("mania_stage", "Escenario", "mania", ["mania-stage-left/right/hint/light.png"],
      "Bordes del escenario, línea de golpeo y luz de columna.",
      [I("size", "Tamaño", 100, 20, 200, "%"), C("edge_color", "Color de los bordes", "#53b9ff"),
       C("hint_color", "Línea de golpeo", "#ffffff"), I("hint_glow", "Resplandor de la línea", 6, 0, 30, "px"),
       C("light_color", "Luz de columna", "#53b9ff"), I("light_opacity", "Opacidad de la luz", 45, 0, 100, "%")],
      theme=False),
    E("mania_lighting", "Explosión al golpear", "mania", ["lightingN.png", "lightingL.png"],
      "Destello al acertar una nota y al sostener un hold.",
      [I("size", "Tamaño", 100, 20, 200, "%"), C("color", "Color", "#7fd0ff"), C("hold_color", "Color del hold", "#ffd166"),
       I("opacity", "Opacidad", 90, 0, 100, "%"), I("hardness", "Dureza", 15, 0, 95, "%"),
       C("ring_color", "Color del anillo", "#ffffff"), I("ring_width", "Grosor del anillo", 4, 0, 20, "px")],
      theme=False),
    E("mania_hits", "Juicios de mania", "mania", ["mania-hit0/50/100/200/300/300g.png"], "Texto de juicios.",
      txt(size=64, outline_width=3) + [sec("Colores"), C("color0", "MISS", "#ff4d4d"), C("color50", "50", "#ffb347"),
                                       C("color100", "100", "#6ad66a"), C("color200", "200", "#53b9ff"),
                                       C("color300", "300", "#e6f6ff"), C("color300g", "MAX", "#ffe27a")]),
    E("combo_font", "Números del combo (contador)", "ui", ["combo-0.png … combo-9.png", "combo-x.png"],
      "El contador de combo de mania (y el de abajo a la izquierda en los otros modos). Tipografía, colores, contorno… "
      "o tus propias imágenes por dígito.",
      txt(size=56, outline_width=3) + [sec("Espaciado"), I("overlap", "Superposición de dígitos", 0, -20, 40, "px"),
                                       sec("Posición (arrástralo en el visualizador)"),
                                       I("off_x", "Mover a la derecha", 0, 0, 800, "px"), I("off_y", "Mover hacia arriba", 0, 0, 600, "px")]),
    E("mania_config", "Configuración de mania", "mania", ["[Mania] en skin.ini"],
      "Cantidad de teclas, ancho de columnas y posiciones.",
      [P("keys", "Teclas a incluir (ej: 4,7)", "text", "4,7"), I("column_width", "Ancho de columna", 70, 20, 100, "px"),
       I("hit_position", "HitPosition (línea de golpeo)", 402, 240, 470, "px"),
       CH("aspect", "Pantalla de referencia", "16:9", list(ASPECTS)),
       B("auto_center", "Centrar el escenario automáticamente", True),
       I("column_start", "ColumnStart (si no es automático)", 216, 0, 1200),
       I("column_spacing", "Espacio entre columnas", 0, 0, 30, "px"),
       I("light_position", "LightPosition", 413, 240, 480, "px"),
       I("score_position", "ScorePosition (juicios)", 325, 0, 480, "px"),
       I("combo_position", "ComboPosition (combo)", 150, 0, 480, "px"),
       sec("Fondo y líneas del escenario"),
       C("column_bg", "Fondo de las columnas", "#000000"), I("column_bg_opacity", "Opacidad del fondo", 100, 0, 100, "%"),
       I("column_line_width", "Grosor de líneas entre columnas (0 = sin líneas)", 2, 0, 8, "px"),
       I("edge_line_width", "Grosor de líneas de los bordes (0 = sin líneas)", 2, 0, 8, "px"),
       C("column_line_color", "Color de líneas", "#40ffffff"),
       C("bar_line_color", "Color de barras de compás", "#80ffffff"),
       B("judgement_line", "Mostrar línea de juicio", True), B("upside_down", "Scroll hacia arriba", False),
       B("keys_under_notes", "Notas por delante de los receptores", True),
       sec("Animaciones al golpear"), B("lighting_on", "Explosión al golpear (círculo grande)", True),
       B("light_on", "Resplandor de columna al pulsar", True), B("key_glow", "Brillo de la tecla al pulsar", True)],
      theme=False, toggle=False),
    # ---- menú ------------------------------------------------------
    E("menu_bg", "Fondo del menú principal", "home", ["menu-background.jpg"],
      "Imagen de fondo del menú principal de osu! (solo la ven los supporters). Reemplázala por tu imagen: se recorta a 1366x768.",
      [C("color", "Color 1", "#1a1033"), C("color2", "Color 2", "#0b1d3a"), I("angle", "Ángulo", 120, 0, 360, "°"),
       CH("pattern", "Patrón", "triángulos", ["triángulos", "puntos", "líneas", "hexágonos", "ninguno"]),
       C("pattern_color", "Color del patrón", "#ffffff"), I("pattern_opacity", "Opacidad del patrón", 8, 0, 100, "%"),
       I("density", "Cantidad", 70, 0, 300), I("seed", "Semilla", 7, 0, 9999), I("vignette", "Viñeta", 35, 0, 100, "%")],
      theme=False),
    E("menu_style", "Estilo rápido del menú", "menu", [],
      "Elige 4 colores, redondeo y letra, y pulsa «Aplicar»: se copian a botones, back, paneles, pestañas, mods y "
      "estrellas. Después puedes retocar cada elemento por separado.",
      [sec("Colores"), C("accent", "Acento (back, resaltados, estrellas)", "#ff4f9d"),
       C("base", "Base (botones y mods)", "#2c3040"), C("text", "Texto", "#ffffff"),
       C("border", "Borde", "#5b6382"), sec("Forma y letra"), I("roundness", "Redondeo", 18, 0, 100, "%"),
       I("border_width", "Grosor del borde", 2, 0, 20, "px"), P("font", "Tipografía", "font", "Arial"),
       act("menu_style_apply", "Aplicar a todo el menú")], theme=False, toggle=False),
    E("menu_back", "Botón «back»", "menu", ["menu-back.png"], "Botón de volver.",
      sty(shape="paralelogramo", color="#ff4f9d", color2="#c22c78", fill_mode="degradado") +
      txt(size=30, outline_width=0, scale=False)[:0] +
      [sec("Texto"), P("label", "Texto", "text", "back"), P("font", "Tipografía", "font", "Arial"),
       I("font_size", "Tamaño de letra", 30, 8, 90, "px"), C("text_color", "Color del texto", "#ffffff")]),
    E("sel_buttons", "Botones inferiores (Mode, Mods…)", "menu",
      ["selection-mode.png", "selection-mods.png", "selection-random.png", "selection-options.png"],
      "Los cuatro botones de la barra inferior de selección de canciones.",
      sty(shape="cuadrado redondeado", roundness=18, color="#2c3040", color2="#171a24", fill_mode="degradado",
          border_width=2, border_color="#5b6382") +
      [sec("Texto"), P("font", "Tipografía", "font", "Arial"), I("font_size", "Tamaño de letra", 30, 8, 90, "px"),
       C("text_color", "Color del texto", "#ffffff"), C("hover_color", "Color al pasar el ratón", "#53b9ff"),
       P("label_mode", "Texto «Mode»", "text", "Mode"),
       P("label_mods", "Texto «Mods»", "text", "Mods"), P("label_random", "Texto «Random»", "text", "Random"),
       P("label_options", "Texto «Options»", "text", "Beatmap Options")]),
    E("menu_panel", "Paneles de canciones", "menu", ["menu-button-background.png"],
      "Fondo de cada canción de la lista (osu! lo tiñe según el estado).",
      sty(shape="cuadrado redondeado", roundness=12, color="#ffffff", color2="#dfe6f5", fill_mode="degradado",
          border_width=2, border_color="#ffffff") +
      [sec("Colores del texto (skin.ini)"), C("active_text", "Canción seleccionada (SongSelectActiveText)", "#000000"),
       C("inactive_text", "Resto de canciones (SongSelectInactiveText)", "#ffffff")]),
    E("stars", "Estrellas de dificultad", "menu", ["star.png", "star2.png"],
      "star.png: las estrellas (o corazones…) de dificultad en los paneles. star2.png: partículas del menú.",
      sty(shape="estrella", color="#ffffff", color2="#ffe27a", fill_mode="sólido")),
    E("mode_icons", "Iconos de modo", "ui", ["mode-osu/taiko/fruits/mania(-med/-small).png"],
      "Iconos de cada modo: el grande sale de fondo en la selección, el pequeño en los paneles de dificultad.",
      [C("color", "Color", "#ffffff"), I("opacity", "Opacidad", 100, 0, 100, "%"), B("ring", "Aro exterior", True),
       I("ring_width", "Grosor del aro", 8, 1, 30, "px"),
       sec("Color de cada modo"), C("color_osu", "osu!", "#ffffff"), C("color_taiko", "osu!taiko", "#ffffff"),
       C("color_fruits", "osu!catch", "#ffffff"), C("color_mania", "osu!mania", "#ffffff")], theme=False),
    E("score_font", "Números de puntuación y precisión", "ui",
      ["score-0…9, score-comma/dot/percent/x.png", "scoreentry-0…9 (clasificación)"],
      "La puntuación y la precisión de arriba a la derecha, y los números de las barras de clasificación (izquierda).",
      txt(size=56, outline_width=2) + [sec("Espaciado"), I("overlap", "Superposición de dígitos", 0, -20, 40, "px"),
                                       sec("Posición (arrástralo en el visualizador)"),
                                       I("off_x", "Mover a la izquierda", 0, 0, 1200, "px"), I("off_y", "Mover hacia abajo", 0, 0, 700, "px"),
                                       sec("Clasificación"), I("entry_size", "Tamaño de los números de clasificación", 45, 20, 100, "%")]),
    E("hp_bar", "Barra de vida", "ui", ["scorebar-bg.png", "scorebar-colour.png"],
      "Fondo y relleno de la barra de vida (arriba a la izquierda; en mania va al lado del escenario). "
      "Moverla añade borde transparente, que es lo único que osu! permite.",
      [sec("Fondo"), C("bg_color", "Color", "#101420"), I("bg_opacity", "Opacidad", 70, 0, 100, "%"),
       I("roundness", "Redondeo", 50, 0, 100, "%"), I("border_width", "Borde", 2, 0, 12, "px"), C("border_color", "Color del borde", "#ffffff"),
       sec("Relleno"), C("color", "Color", "#53b9ff"), C("color2", "Color 2", "#ff7ab6"), I("glow", "Resplandor", 6, 0, 30, "px"),
       sec("Tamaño y posición"), I("length", "Largo", 100, 40, 160, "%"), I("thickness", "Grosor", 100, 40, 300, "%"),
       I("off_x", "Mover en X", 0, 0, 600, "px"), I("off_y", "Mover en Y", 0, 0, 600, "px")], theme=False, hd=True),
    E("skip", "Botón «Skip»", "ui", ["play-skip.png"],
      "El botón para saltar la intro (abajo a la derecha). Texto, botón, píldora, contorno o tu propia imagen.",
      [sec("Botón"), CH("btn_style", "Estilo", "píldora", ["texto", "botón", "píldora", "contorno"]),
       P("label", "Texto", "text", "Skip intro ▶"), C("color", "Color", "#3b6cff"), C("color2", "Color 2", "#1d3a9a"),
       I("roundness", "Redondeo", 50, 0, 100, "%"), I("btn_opacity", "Opacidad", 90, 0, 100, "%"),
       I("border_width", "Borde", 2, 0, 20, "px"), C("border_color", "Color del borde", "#ffffff"),
       I("glow", "Resplandor", 6, 0, 40, "px"), C("glow_color", "Color del resplandor", "#53b9ff"),
       sec("Letra"), P("font", "Tipografía", "font", "Arial"), I("font_size", "Tamaño de letra", 56, 8, 140, "px"),
       B("bold", "Negrita", True), B("italic", "Cursiva", False), C("text_color", "Color", "#ffffff"),
       I("outline_width", "Contorno", 0, 0, 12, "px"), C("outline_color", "Color del contorno", "#000000")], theme=False, hd=True),
    E("dialog_buttons", "Botones de diálogo", "mods", ["button-left.png", "button-middle.png", "button-right.png"],
      "Los botones grandes de los diálogos (Desactivar todos, Cerrar, Ver perfil…). osu! los tiñe de cada color y "
      "estira la parte del medio, así que déjalos blancos/grises.",
      [sec("Forma"), I("roundness", "Redondeo", 12, 0, 100, "%"), I("size", "Alto", 100, 50, 200, "%"),
       sec("Relleno"), CH("fill_mode", "Tipo", "degradado", FILLS), C("color", "Color", "#ffffff"),
       C("color2", "Color 2", "#c9c9c9"), I("grad_angle", "Ángulo", 90, 0, 360, "°"),
       I("opacity", "Opacidad", 100, 0, 100, "%"),
       sec("Borde"), I("border_width", "Grosor", 0, 0, 20, "px"), C("border_color", "Color", "#ffffff"),
       CH("border_style", "Estilo", "sólido", BORDERS), sec("Efectos"), B("gloss", "Brillo superior", True)],
      theme=False, hd=True),
    E("mod_icons", "Iconos de mods", "mods", ["selection-mod-*.png (EZ, HR, DT, HD, FL, 1K–9K…)"],
      "Todas las placas de mods con su abreviatura. Por defecto: verde reduce, rojo aumenta, azul especial, amarillo auto.",
      sty(shape="cuadrado redondeado", roundness=30, color="#2c3040", fill_mode="degradado", border_width=3,
          border_color="#ffffff") +
      [sec("Colores por tipo"), B("colors_by_type", "Un color por tipo de mod", True),
       C("color_reduce", "Reducen dificultad", "#3fae5b"), C("color_increase", "Aumentan dificultad", "#d6453a"),
       C("color_special", "Especiales", "#3a7bd6"), C("color_auto", "Automáticos", "#d6a53a"),
       sec("Texto"), P("font", "Tipografía", "font", "Arial"), I("font_size", "Tamaño de letra", 24, 8, 60, "px"),
       C("text_color", "Color del texto", "#ffffff")]),
    E("menu_logo", "Logo del menú", "menu", ["menu-osu.png"], "Círculo del menú principal.",
      sty(color="#ff66aa", color2="#d6338a", fill_mode="degradado", glow=10, glow_color="#ff66aa") +
      [sec("Texto"), P("label", "Texto", "text", "osu!"), P("font", "Tipografía", "font", "Arial"),
       I("font_size", "Tamaño de letra", 190, 20, 400, "px"), C("text_color", "Color del texto", "#ffffff")]),
    E("ranking", "Letras de ranking", "menu", ["ranking-X/XH/SH/S/A/B/C/D-small.png"],
      "Letras de rango de los puntajes.", txt(size=48, fill_mode="degradado", outline_width=2) +
      [B("custom_colors", "(reservado)", False)][:0]),
    E("menu_tab", "Pestañas (Group / Sort)", "menu", ["selection-tab.png"],
      "Pestañas de la esquina superior derecha; osu! las tiñe de rojo/blanco. No uses 1x1 px: su tamaño es el área de clic.",
      sty(shape="cuadrado redondeado", roundness=25, color="#ffffff", color2="#cfd6e6", fill_mode="degradado")),
    # ---- config ----------------------------------------------------
    # ---- pausa / fallo / resultados ---------------------------------------------
    E("pause_screen", "Pantalla de pausa", "pause", ["pause-overlay.png", "pause-continue/retry/back.png"],
      "Todo desde aquí: fondo, título y los 3 botones (texto, botón, píldora o contorno, en cualquier idioma). "
      "La pantalla de fallo usa estos mismos botones «reintentar» y «volver».",
      [sec("Fondo"), CH("bg_mode", "Tipo", "sólido", ["sólido", "degradado"]), C("bg_color", "Color", "#000000"),
       C("bg_color2", "Color 2", "#1d2b5a"), I("bg_angle", "Ángulo", 90, 0, 360, "°"),
       I("bg_opacity", "Oscurecer el juego", 70, 0, 100, "%"),
       sec("Título (opcional)"), P("title", "Título", "text", ""), I("title_size", "Tamaño", 64, 10, 190, "px"),
       C("title_color", "Color", "#ffffff"), P("subtitle", "Subtítulo", "text", ""),
       I("subtitle_size", "Tamaño del subtítulo", 28, 8, 120, "px"), C("subtitle_color", "Color del subtítulo", "#ff8fbf"),
       sec("Botones"), CH("btn_style", "Estilo", "texto", ["texto", "botón", "píldora", "contorno"]),
       B("bullet", "Viñeta «•» delante", True), P("label_continue", "Texto de continuar", "text", "Continuar"),
       P("label_retry", "Texto de reintentar", "text", "Reintentar"), P("label_back", "Texto de volver", "text", "Volver al menú"),
       sec("Letra"), P("font", "Tipografía", "font", "Arial"), I("font_size", "Tamaño de letra", 56, 8, 140, "px"),
       B("bold", "Negrita", False), B("italic", "Cursiva", False), C("text_color", "Color", "#ffffff"),
       I("outline_width", "Contorno", 0, 0, 12, "px"), C("outline_color", "Color del contorno", "#000000"),
       sec("Fondo del botón (estilos botón, píldora y contorno)"), C("color", "Color", "#3b6cff"),
       C("color2", "Color 2", "#1d3a9a"), I("roundness", "Redondeo", 30, 0, 100, "%"), I("btn_opacity", "Opacidad", 95, 0, 100, "%"),
       I("border_width", "Borde", 0, 0, 20, "px"), C("border_color", "Color del borde", "#ffffff"),
       I("glow", "Resplandor", 0, 0, 40, "px"), C("glow_color", "Color del resplandor", "#53b9ff")], theme=False),
    E("fail_screen", "Pantalla de fallo", "fail", ["fail-background.png"],
      "Fondo de la pantalla de fallo con texto grande en franja (como «FAIL»). Los botones son los de la pausa.",
      [sec("Fondo"), CH("bg_mode", "Tipo", "degradado", ["sólido", "degradado"]), C("bg_color", "Color", "#3a3a3a"),
       C("bg_color2", "Color 2", "#141414"), I("bg_angle", "Ángulo", 90, 0, 360, "°"),
       sec("Texto grande"), P("big_text", "Texto", "text", "FAIL"), P("font", "Tipografía", "font", "Arial"),
       I("font_size", "Tamaño", 150, 20, 400, "px"), B("bold", "Negrita", True), B("italic", "Cursiva", False),
       C("text_color", "Color", "#ffffff"), I("outline_width", "Contorno", 0, 0, 20, "px"), C("outline_color", "Color del contorno", "#000000"),
       I("text_angle", "Inclinación", -65, -180, 180, "°"), I("text_x", "Posición horizontal", 30, 0, 100, "%"),
       I("text_y", "Posición vertical", 45, 0, 100, "%"),
       sec("Franja"), B("stripe", "Mostrar franja", True), C("stripe_color", "Color", "#0a3aa8"),
       I("stripe_width", "Ancho", 230, 20, 600, "px"), I("stripe_opacity", "Opacidad", 100, 0, 100, "%"),
       sec("Subtítulo"), P("subtitle", "Texto", "text", ""), I("subtitle_size", "Tamaño", 30, 8, 120, "px")], theme=False),
    E("results_screen", "Pantalla de resultados", "results",
      ["ranking-panel/title/perfect/graph/accuracy/maxcombo/replay.png", "ranking-X/XH/SH/S/A/B/C/D.png"],
      "Panel, títulos, caja Perfect y letras grandes de nota, todo con un mismo estilo. osu! dibuja los números encima.",
      [sec("Paneles"), C("panel_color", "Color", "#000000"), I("panel_opacity", "Opacidad", 70, 0, 100, "%"),
       I("panel_round", "Redondeo", 0, 0, 60, "px"), I("panel_border", "Borde", 2, 0, 10, "px"),
       C("panel_border_color", "Color del borde", "#ffffff"),
       sec("Textos"), P("font", "Tipografía", "font", "Arial"), B("bold", "Negrita", True), B("italic", "Cursiva", False),
       C("text_color", "Color", "#ffffff"), I("outline_width", "Contorno", 0, 0, 12, "px"), C("outline_color", "Color del contorno", "#000000"),
       P("title_text", "Título", "text", "Results"), B("title_bg", "Fondo detrás del título", True),
       P("score_text", "Etiqueta de puntuación", "text", "Score"), P("perfect_text", "Caja Perfect", "text", "Perfect"),
       P("accuracy_text", "Precisión", "text", "Accuracy"), P("combo_text", "Combo", "text", "Combo"),
       P("replay_text", "Ver repetición", "text", "• Ver repetición"),
       sec("Letras grandes (SS, S, A, B…)"), I("letter_outline", "Contorno", 8, 0, 40, "px"),
       C("letter_outline_color", "Color del contorno", "#ffffff")] + [
          x for L, c1, c2 in gens.RANKS for x in (
              sec(f"Rango {L}"), P(f"letter_{L}", f"Texto del rango {L}", "text", "SS" if L in ("X", "XH") else L),
              C(f"letter_{L}_c1", "Color", c1), C(f"letter_{L}_c2", "Color 2", c2))], theme=False, hd=True),
    E("skin_ini", "skin.ini", "config", ["skin.ini"], "Opciones que osu!stable lee del skin.ini.",
      [P("name", "Nombre de la skin", "text", ""), P("author", "Autor", "text", ""), P("version", "Version", "text", "latest"),
       sec("Colores de combo"), C("combo1", "Combo 1", "#53b9ff"), C("combo2", "Combo 2", "#ff7ab6"),
       C("combo3", "Combo 3", "#ffd166"), C("combo4", "Combo 4", "#9be564"),
       sec("Sliders"), C("slider_border", "SliderBorder", "#f5f7fc"), B("use_track_override", "Usar SliderTrackOverride", True),
       C("slider_track", "SliderTrackOverride", "#232d3e"), B("allow_slider_ball_tint", "AllowSliderBallTint", True),
       sec("Fuentes"), I("hitcircle_overlap", "HitCircleOverlap", 12, -50, 100, "px"),
       sec("Cursor"), B("cursor_rotate", "CursorRotate", True),
       sec("osu!catch"), C("hyperdash", "HyperDash", "#ff3b3b"), C("hyperdash_fruit", "HyperDashFruit", "#ff7a59"),
       C("hyperdash_after", "HyperDashAfterImage", "#ff3b3b")], theme=False, toggle=False),
]
ELEMENT_BY_ID = {e["id"]: e for e in ELEMENTS}
ELEMENT_BY_ID["mode_icons"]["scene"] = "menu"          # escena del visualizador donde se ve mejor
ELEMENT_BY_ID["dialog_buttons"]["scene"] = "dialogs"
for _id in ("sel_buttons", "menu_back", "menu_panel", "ranking", "menu_tab", "mod_icons", "mode_icons"):
    ELEMENT_BY_ID[_id]["hd"] = True   # se exportan como nombre@2x.png (1 unidad de interfaz = 2 px)

GENERATORS = {
    "hitcircle": gens.g_hitcircle, "hitcircleoverlay": gens.g_hitcircleoverlay, "approachcircle": gens.g_approach,
    "numbers": gens.g_numbers, "sliderb": gens.g_sliderb, "sliderfollowcircle": gens.g_follow,
    "reversearrow": gens.g_reverse, "sliderscorepoint": gens.g_tick, "cursor": gens.g_cursor,
    "cursortrail": gens.g_trail, "combo_font": gens.g_combo_font, "inputoverlay": gens.g_inputoverlay, "hits": gens.g_hits,
    "taiko_circle": gens.g_taiko_circle, "taiko_big": gens.g_taiko_big, "taiko_roll": gens.g_taiko_roll,
    "taiko_bar": gens.g_taiko_bar, "taiko_drum": gens.g_taiko_drum,
    "catch_fruits": gens.g_fruits, "catch_catcher": gens.g_catcher,
    "mania_notes": gens.g_mania_notes, "mania_keys": gens.g_mania_keys, "mania_stage": gens.g_mania_stage,
    "mania_lighting": gens.g_mania_lighting, "mania_hits": gens.g_mania_hits,
    "menu_bg": gens.g_menu_bg, "menu_back": gens.g_menu_back, "sel_buttons": gens.g_sel_buttons,
    "menu_panel": gens.g_menu_panel, "menu_logo": gens.g_menu_logo, "ranking": gens.g_ranking,
    "menu_tab": gens.g_menu_tab, "score_font": gens.g_score_font, "hp_bar": gens.g_hp_bar, "skip": gens.g_skip, "dialog_buttons": gens.g_dialog_buttons, "stars": gens.g_stars, "mode_icons": gens.g_mode_icons, "mod_icons": gens.g_mod_icons,
    "pause_screen": gens.g_pause, "fail_screen": gens.g_fail, "results_screen": gens.g_results,
}
FIT_OVERRIDES = {"hitcircle", "hitcircleoverlay", "approachcircle", "sliderb", "sliderfollowcircle", "reversearrow",
                 "sliderscorepoint", "cursor", "cursortrail", "hits", "inputoverlay", "taiko_circle", "taiko_big",
                 "taiko_roll", "taiko_drum", "catch_fruits", "catch_catcher", "mania_notes", "mania_keys",
                 "mania_lighting", "mania_hits", "stars", "mod_icons", "mode_icons", "ranking", "menu_tab",
                 "menu_back", "sel_buttons", "skip", "menu_logo", "combo_font", "score_font"}
# osu! dibuja estas imágenes a su tamaño en píxeles: tu imagen se encoge (sin deformarse) al tamaño de la generada
RECOMMENDED = ["hitcircle", "hitcircleoverlay", "approachcircle", "numbers", "cursor"]

THEME_GEOM = ["shape", "fill_mode", "border_style", "roundness", "glow", "font"]
THEME_COLORS = {"color": "accent", "color2": "accent2", "border_color": "accent2", "glow_color": "accent",
                "outline_color": "outline_color", "text_color": "text_color", "colorS": "accent3",
                "overlay_color": "accent2", "detail_color": "accent2", "color1": "text_color"}


# ----------------------------------------------------------------------
# Utilidades sin Qt
# ----------------------------------------------------------------------
def hex_rgba(s: str):
    s = (s or "#ffffff").lstrip("#")
    try:
        if len(s) == 8:
            return int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16), int(s[0:2], 16)
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255
    except ValueError:
        return 255, 255, 255, 255


def rgb_str(s: str) -> str:
    r, g, b, _ = hex_rgba(s)
    return f"{r},{g},{b}"


def rgba_str(s: str) -> str:
    r, g, b, a = hex_rgba(s)
    return f"{r},{g},{b},{a}"


def safe_name(s: str, fallback: str = "skin") -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s).strip(" .")
    return s or fallback


def parse_keys(text: str) -> list[int]:
    out = []
    for part in re.split(r"[,\s;]+", str(text)):
        if part.isdigit() and 1 <= int(part) <= 20 and int(part) not in out:
            out.append(int(part))
    return sorted(out) or [4]


def _clean(s: str) -> str:
    return re.sub(r"[\r\n]", " ", str(s)).strip()


def image_bytes(img: QImage, filename: str) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if filename.lower().endswith((".jpg", ".jpeg")):
        img.convertToFormat(QImage.Format.Format_RGB32).save(buf, "JPG", 92)
    else:
        img.save(buf, "PNG")
    buf.close()
    return bytes(ba.data())


# ----------------------------------------------------------------------
# Paletas
# ----------------------------------------------------------------------
def harmony_colors(base: str, kind: str) -> list[str]:
    c = QColor(base)
    h, s, v, _ = c.getHsv()
    h = max(h, 0)
    s = max(120, s)
    v = max(170, v)
    if kind == "monocromático":
        vals = [(h, s, v), (h, max(60, s - 70), min(255, v)), (h, s, max(110, v - 80)), (h, max(40, s - 110), min(255, v + 20))]
    else:
        offs = {"análogo": [0, 30, -30, 60], "complementario": [0, 180, 20, 200],
                "triádico": [0, 120, 240, 60], "tetrádico": [0, 90, 180, 270]}[kind]
        vals = [((h + o) % 360, s, v) for o in offs]
    return [QColor.fromHsv(hh, ss, vv).name() for hh, ss, vv in vals]


def _blank(img: QImage) -> QImage:
    out = QImage(img.size(), QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    return out


# Punto fijo con el que osu! (y el visualizador) coloca cada archivo: (0,0) esquina sup. izq., (.5,.5) centro,
# (0,1) esquina inf. izq. Mover un objeto = añadir/recortar borde transparente para que el contenido se desplace.
ANCHORS = {"ranking-title.png": (.5, .5), "ranking-replay.png": (.5, .5), "mode-osu.png": (.5, .5),
           "pause-continue.png": (.5, .5), "pause-retry.png": (.5, .5), "pause-back.png": (.5, .5),
           "menu-back.png": (0, 1), "play-skip.png": (1, 1), "selection-mode.png": (0, 1), "selection-mods.png": (0, 1),
           "selection-random.png": (0, 1), "selection-options.png": (0, 1),
           **{f"ranking-{L}.png": (.5, .5) for L in ("XH", "X", "SH", "S", "A", "B", "C", "D")},
           **{f"ranking-{L}-small.png": (0, .5) for L in ("XH", "X", "SH", "S", "A", "B", "C", "D")}}


def place_image(img: QImage, dx: float, dy: float, scale: float, anchor) -> QImage:
    s = scale / 100
    if s != 1:
        img = img.scaled(max(1, round(img.width() * s)), max(1, round(img.height() * s)),
                         Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def axis(L, d, a):
        d = round(d)
        if a == 0:
            return L + d, d
        if a == 1:
            return L - d, 0
        return L + 2 * abs(d), d + abs(d)
    W2, ox = axis(img.width(), dx, anchor[0])
    H2, oy = axis(img.height(), dy, anchor[1])
    out = gens.new_img(max(1, W2), max(1, H2))
    p = gens.make_painter(out)
    p.drawImage(int(ox), int(oy), img)
    p.end()
    return out


# Qué propiedades pertenecen a cada objeto (al hacer clic en él se muestran solo esas)
_TXT = ["font", "bold", "italic", "text_color"]
FILE_PROPS = {
    "results_screen": {
        "ranking-panel.png": ["panel_color", "panel_opacity", "panel_round", "panel_border", "panel_border_color", "score_text"],
        "ranking-title.png": ["title_text", "title_bg"] + _TXT,
        "ranking-perfect.png": ["perfect_text", "panel_color", "panel_opacity"] + _TXT,
        "ranking-accuracy.png": ["accuracy_text"] + _TXT, "ranking-maxcombo.png": ["combo_text"] + _TXT,
        "ranking-replay.png": ["replay_text"] + _TXT, "ranking-graph.png": ["panel_color", "panel_opacity", "panel_round"],
        **{f"ranking-{L}.png": [f"letter_{L}", f"letter_{L}_c1", f"letter_{L}_c2", "letter_outline", "letter_outline_color", "font"]
           for L in ("XH", "X", "SH", "S", "A", "B", "C", "D")}},
    "pause_screen": {f: [k, "btn_style", "bullet", "font", "font_size", "text_color", "color", "color2", "roundness"]
                     for k, f in (("label_continue", "pause-continue.png"), ("label_retry", "pause-retry.png"),
                                  ("label_back", "pause-back.png"))},
    "mode_icons": {f"mode-{m}{suf}.png": [f"color_{m}", "opacity", "ring", "ring_width"]
                   for m in ("osu", "taiko", "fruits", "mania") for suf in ("", "-med", "-small")},
    "sel_buttons": {f"{f}.png": [k, "font", "font_size", "text_color", "color", "color2", "hover_color"]
                    for f, k in (("selection-mode", "label_mode"), ("selection-mods", "label_mods"),
                                 ("selection-random", "label_random"), ("selection-options", "label_options"))},
}


def hd_versions(pr) -> dict:
    """Versión @2x (doble de píxeles) de los elementos de juego, para que en 1080p+ se vean nítidos.
    Solo se exporta si sale exactamente al doble del SD; tus imágenes propias y los objetos movidos se dejan en SD."""
    out = {}
    cfg = pr.assets["mania_config"]
    for eid, gen in GENERATORS.items():
        el = ELEMENT_BY_ID[eid]
        if el.get("hd") or "size" not in el["specs"] or not _on(pr, eid) or pr.assets[eid].get("hidden"):
            continue
        if eid in ("score_font", "combo_font") and (pr.assets[eid]["off_x"] or pr.assets[eid]["off_y"]):
            continue
        if eid == "mania_lighting" and not cfg.get("lighting_on", True):
            continue
        v = pr.values(eid)
        v["size"] = v["size"] * 2
        sd = pr.images(eid)
        for name, img in gen(v, dict(pr.gen_ctx(), scale=2)).items():
            ref = sd.get(name)
            if (ref is None or name in pr.overrides.get(eid, {}) or name in pr.layout
                    or (name == "mania-stage-light.png" and not cfg.get("light_on", True))):
                continue
            if abs(img.width() - 2 * ref.width()) <= 2 and abs(img.height() - 2 * ref.height()) <= 2:
                out[hd_name(name)] = image_bytes(img, name)
    return out


# Para qué sirve cada efecto: (nombre de archivo, ¿animado?, explicación). Solo cosas que osu! sí reproduce.
EFFECT_EVENTS = {
    "hit300": ("hit300-{i}.png", True, "Juicio 300 animado (standard)"),
    "hit100": ("hit100-{i}.png", True, "Juicio 100 animado (standard)"),
    "hit50": ("hit50-{i}.png", True, "Juicio 50 animado (standard)"),
    "miss": ("hit0-{i}.png", True, "Fallo (miss) animado (standard)"),
    "lighting": ("lighting.png", False, "Destello al golpear un círculo (standard, con Hit Lighting activado)"),
    "particle300": ("particle300.png", False, "Partícula que sale al sacar 300 (standard)"),
    "particle100": ("particle100.png", False, "Partícula que sale al sacar 100 (standard)"),
    "particle50": ("particle50.png", False, "Partícula que sale al sacar 50 (standard)"),
    "sliderball": ("sliderb{i}.png", True, "Bola del slider animada"),
    "followpoint": ("followpoint-{i}.png", True, "Puntos que unen los círculos, animados"),
    "comboburst": ("comboburst.png", False, "Imagen que aparece al llegar a combos altos"),
    "section_pass": ("section-pass.png", False, "Aviso de sección bien hecha (en los descansos)"),
    "section_fail": ("section-fail.png", False, "Aviso de sección mal hecha (en los descansos)"),
    "mania_lighting": ("lightingN-{i}.png", True, "Explosión al golpear una nota de mania, animada"),
    "mania_hit300": ("mania-hit300-{i}.png", True, "Juicio 300 de mania animado"),
    "mania_hit300g": ("mania-hit300g-{i}.png", True, "Juicio MAX (300g) de mania animado"),
}


def new_effect(mode="nocode") -> dict:
    return {"id": _uid(), "name": "Efecto nuevo", "enabled": True, "event": "hit300", "mode": mode,
            "preset": "Destello", "color": "#ffffff", "color2": "#53b9ff", "size": 256, "frames": 12, "fps": 30,
            "amount": 12, "seed": 7, "text": "300",
            "code": ("# t va de 0 (inicio) a 1 (final); p es el pincel. Coordenadas de 0 a 1.\n"
                     "# p.circle(x, y, radio, color, alpha)   p.ring(x, y, radio, grosor, color, alpha)\n"
                     "# p.glow(x, y, radio, color, alpha)     p.star(x, y, radio, puntas, color, alpha, rot)\n"
                     "# p.line(x1, y1, x2, y2, grosor, color, alpha)   p.text(x, y, texto, tamaño, color, alpha)\n"
                     "def frame(t, p):\n"
                     "    p.glow(0.5, 0.5, 0.2 + 0.3 * t, '#ff66aa', 1 - t)\n"
                     "    p.ring(0.5, 0.5, 0.1 + 0.35 * t, 0.03, '#ffffff', 1 - t)\n")}


def effect_files(e: dict) -> dict:
    if not e.get("enabled", True) or e.get("event") not in EFFECT_EVENTS:
        return {}
    name, animated, _ = EFFECT_EVENTS[e["event"]]
    n = max(1, int(e.get("frames", 12))) if animated else 1
    out = {}
    for i in range(n):
        t = i / max(1, n - 1) if animated else 0.35
        img, _err = gens.render_effect(e, t)
        out[name.format(i=i)] = image_bytes(img, name)
    return out


# ---- Sonidos y mascota: cada hueco usa tu archivo o, si está vacío, el de osu! -------------
_HS = [(f"{b}-hit{h}", f"{b.capitalize()} · {h}") for b in ("normal", "soft", "drum")
       for h in ("normal", "clap", "whistle", "finish")]
SLOT_GROUPS = {
    "sounds_hit": ("Hitsounds (standard, mania y catch)", "std",
                   "osu! comparte estos sonidos entre standard, mania y catch.",
                   [(n, l, "sound") for n, l in _HS] +
                   [("normal-slidertick", "Tick del slider", "sound"), ("normal-sliderslide", "Slider deslizándose", "sound"),
                    ("spinnerspin", "Spinner girando", "sound"), ("combobreak", "Romper el combo", "sound")]),
    "sounds_taiko": ("Hitsounds de taiko", "taiko", "Sonidos propios de osu!taiko.",
                     [(f"taiko-normal-hit{h}", f"Taiko · {h}", "sound") for h in ("normal", "clap", "whistle", "finish")]),
    "sounds_game": ("Música y sonidos del juego", "ui", "Fallo, pausa, salir del juego (el «see you next time»), menús…",
                    [("failsound", "Al fallar (música de fallo)", "sound"), ("pause-loop", "Música del menú de pausa", "sound"),
                     ("seeya", "Al cerrar el juego («see you next time»)", "sound"), ("welcome", "Al abrir el juego", "sound"),
                     ("applause", "Aplausos de resultados", "sound"), ("menuback", "Volver atrás", "sound"),
                     ("menuclick", "Clic en el menú", "sound"), ("menuhit", "Elegir en el menú", "sound")]),
    "taiko_mascot": ("Mascota de taiko (GIF)", "taiko",
                     "Sube un GIF por estado: se separa en fotogramas pippidon<estado>0, 1, 2… como pide osu!.",
                     [("pippidonidle", "Bailando (normal)", "gif"), ("pippidonkiai", "Bailando en kiai", "gif"),
                      ("pippidonfail", "Al fallar", "gif"), ("pippidonclear", "Al pasar una sección", "gif")]),
}
SLOT_EXTS = (".wav", ".mp3", ".ogg")


def slot_files(pr) -> dict:
    out = {}
    for gid, (_t, mode, _d, slots) in SLOT_GROUPS.items():
        if not pr.modes.get(mode, True):
            continue
        for key, _label, kind in slots:
            v = pr.slots.get(key)
            if not v:
                continue
            if kind == "sound":
                f = pr.path / v
                if f.is_file():
                    out[key + f.suffix.lower()] = f.read_bytes()
            else:
                for i, rel in enumerate(v):
                    f = pr.path / rel
                    if f.is_file():
                        out[f"{key}{i}.png"] = f.read_bytes()
    return out


# osu! no deja mover los números, pero sí los dibuja desde una esquina fija: la puntuación desde arriba a la
# derecha y el combo desde abajo a la izquierda. Con borde transparente en cada dígito (y la superposición
# compensada en skin.ini) el número se desplaza: la puntuación hacia la izquierda/abajo, el combo hacia la
# derecha/arriba. En la otra dirección no se puede.
def digit_overlap(pr, eid) -> int:
    a = pr.assets[eid]
    return a["overlap"] + a.get("off_x", 0)


def pad_digits(pr, eid, out: dict) -> dict:
    a = pr.assets[eid]
    dx, dy = a.get("off_x", 0), a.get("off_y", 0)
    if not (dx or dy):
        return out
    prefix = "score-" if eid == "score_font" else "combo-"
    res = {}
    for name, img in out.items():
        if not name.startswith(prefix):
            res[name] = img
            continue
        W, H = img.width() + dx, img.height() + dy
        canvas = gens.new_img(W, H)
        p = gens.make_painter(canvas)
        if eid == "score_font":      # borde a la derecha y arriba
            p.drawImage(0, dy, img)
        else:                        # combo: borde a la izquierda y abajo
            p.drawImage(dx, 0, img)
        p.end()
        res[name] = canvas
    return res


def hd_name(name: str) -> str:
    stem, dot, ext = name.rpartition(".")
    return f"{stem}@2x.{ext}" if dot else name + "@2x"


def mania_layout(pr, K: int) -> dict:
    """Mismas reglas que osu!stable: las X se miden con una altura de 480 y el origen es el borde
    izquierdo de la pantalla, así que el ancho útil depende de la relación de aspecto."""
    cfg = pr.assets["mania_config"]
    w, sp = cfg["column_width"], cfg["column_spacing"]
    W = 480 * ASPECTS[cfg["aspect"]]
    w = max(8, min(w, int((W * 0.96 - (K - 1) * sp) / K)))   # 11K-20K: se estrecha solo para caber en pantalla
    total = K * w + (K - 1) * sp
    start = (W - total) / 2 if cfg["auto_center"] else cfg["column_start"]
    return {"start": start, "w": w, "sp": sp, "total": total, "W": W}


# ----------------------------------------------------------------------
# Proyecto
# ----------------------------------------------------------------------
class Project:
    def __init__(self, name: str, author: str, path):
        self.name, self.author, self.path = name, author, Path(path)
        self.dirty = False
        self.assets = {e["id"]: self._defaults(e) for e in ELEMENTS}
        self.assets["skin_ini"]["name"] = name
        self.assets["skin_ini"]["author"] = author
        self.customs: list[dict] = []     # {"name": "archivo.png", "file": "assets/xxx.png"}
        self.fonts: list[str] = []        # rutas relativas dentro del proyecto
        self.modes: dict = {}             # modo -> False si se usa la skin por defecto de osu!
        self.library: list[dict] = []     # recursos globales {"name","file"}
        self.scene_objs: dict = {}        # escena -> capas libres sobre el visualizador
        self.layout: dict = {}            # archivo -> {"dx","dy" (unidades de interfaz), "scale" %, "locked"}
        self.effects: list[dict] = []     # efectos (sin código o con código) -> fotogramas
        self.slots: dict = {}             # sonidos / mascota: clave -> ruta o [fotogramas] (vacío = el de osu!)
        self.overrides: dict[str, dict] = {}   # eid -> {archivo: ruta de imagen propia}
        self.canvases: list[dict] = []
        self.anims: list[dict] = []    # {"name","fps","frames":[rutas]}
        self.exported: list[str] = []
        self._cache: dict[str, dict] = {}
        self._img_cache: dict[str, QImage] = {}

    @staticmethod
    def _defaults(e):
        d = {"enabled": True, "hidden": False}
        d.update({p["key"]: copy.deepcopy(p["default"]) for p in e["props"] if p["key"]})
        return d

    # ---- valores ---------------------------------------------------
    def get(self, eid, key):
        return self.assets[eid][key]

    def theme(self):
        return self.assets["theme"]

    def values(self, eid) -> dict:
        v = dict(self.assets[eid])
        e = ELEMENT_BY_ID[eid]
        if e["theme"] and v.get("use_theme"):
            t = self.assets["theme"]
            for k in THEME_GEOM:
                if k in v:
                    v[k] = t[k]
            for k, tk in e["theme_map"].items():
                if k in v:
                    v[k] = t[tk]
            if not e["tint"]:
                for k, tk in THEME_COLORS.items():
                    if k in v:
                        v[k] = t[tk]
        cfg = self.assets["mania_config"]
        if eid == "mania_keys" and not cfg.get("key_glow", True):
            v["pressed_glow"] = 0
        for k, spec in e["specs"].items():       # imágenes del proyecto -> ruta absoluta para los generadores
            if spec["kind"] == "image" and v.get(k):
                v[k] = str(self.path / v[k])
        return v

    @staticmethod
    def _coerce(spec, value):
        kind = spec["kind"]
        if kind == "int":
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = spec["default"]
            return max(spec["min"], min(spec["max"], value))
        if kind == "color":
            c = QColor(value) if isinstance(value, str) else QColor()
            if not c.isValid():
                return spec["default"]
            return c.name(QColor.NameFormat.HexArgb) if c.alpha() < 255 else c.name()
        if kind == "bool":
            return bool(value)
        if kind == "choice":
            return value if value in spec["options"] else spec["default"]
        if kind == "font":
            return str(value)[:80] or spec["default"]
        if kind == "image":
            return str(value)[:240]
        return re.sub(r"[\r\n\t]", " ", str(value))[:100]

    def _invalidate(self, eid):
        if eid in ("theme", "mania_config"):
            self._cache.clear()
        else:
            self._cache.pop(eid, None)

    def _apply(self, eid, key, value):
        if eid not in ELEMENT_BY_ID:
            return
        if key == "enabled":
            self.assets[eid]["enabled"] = bool(value)
        elif key == "hidden":
            self.assets[eid]["hidden"] = bool(value)
        elif key in ELEMENT_BY_ID[eid]["specs"]:
            self.assets[eid][key] = self._coerce(ELEMENT_BY_ID[eid]["specs"][key], value)
        else:
            return
        self._invalidate(eid)

    def set(self, eid, key, value):
        self._apply(eid, key, value)
        self.dirty = True

    def set_many(self, eid, mapping: dict):
        for k, v in mapping.items():
            self._apply(eid, k, v)
        self.dirty = True

    def reset_element(self, eid):
        self.assets[eid] = self._defaults(ELEMENT_BY_ID[eid])
        if eid == "skin_ini":
            self.assets[eid]["name"], self.assets[eid]["author"] = self.name, self.author
        self._invalidate(eid)
        self.dirty = True

    def has_theme_all(self, flag: bool):
        for e in ELEMENTS:
            if e["theme"]:
                self.assets[e["id"]]["use_theme"] = flag
        self._cache.clear()
        self.dirty = True

    # ---- imágenes --------------------------------------------------
    def keys(self) -> list[int]:
        return parse_keys(self.assets["mania_config"]["keys"])

    def images(self, eid) -> dict:
        gen = GENERATORS.get(eid)
        if gen is None:
            return {}
        if eid not in self._cache:
            out = gen(self.values(eid), self.gen_ctx())
            for name, rel in self.overrides.get(eid, {}).items():
                f = self.path / rel
                if name in out and f.is_file():
                    img = QImage(str(f))
                    if not img.isNull():
                        if eid == "menu_bg":     # recorte tipo «cubrir» a 1366x768
                            img = img.scaled(out[name].size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                             Qt.TransformationMode.SmoothTransformation)
                            img = img.copy((img.width() - out[name].width()) // 2, (img.height() - out[name].height()) // 2,
                                           out[name].width(), out[name].height())
                        elif eid in FIT_OVERRIDES:      # tu imagen se ajusta al tamaño que osu! espera (sin deformarla)
                            img = img.scaled(out[name].size(), Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
                        out[name] = img
            cfg = self.assets["mania_config"]
            if self.assets[eid].get("hidden") or (eid == "mania_lighting" and not cfg.get("lighting_on", True)):
                out = {n: _blank(i) for n, i in out.items()}      # mismo tamaño, 100 % transparente
            if eid == "mania_stage" and not cfg.get("light_on", True) and "mania-stage-light.png" in out:
                out["mania-stage-light.png"] = _blank(out["mania-stage-light.png"])
            if eid in ("score_font", "combo_font"):
                out = pad_digits(self, eid, out)
            k = 2 if ELEMENT_BY_ID[eid].get("hd") else 1
            lays = dict(self.layout)
            if "scorebar-bg.png" in lays:          # la barra de vida se mueve entera (fondo + relleno)
                lays.setdefault("scorebar-colour.png", lays["scorebar-bg.png"])
            for n, lay in lays.items():      # objeto movido/escalado en el visualizador
                if n in out and (lay.get("dx") or lay.get("dy") or lay.get("scale", 100) != 100):
                    out[n] = place_image(out[n], lay.get("dx", 0) * k, lay.get("dy", 0) * k, lay.get("scale", 100),
                                         ANCHORS.get(n, (0, 0)))
            self._cache[eid] = out
        return self._cache[eid]

    def set_override(self, eid, name, rel):
        d = self.overrides.setdefault(eid, {})
        if rel:
            d[name] = rel
        else:
            d.pop(name, None)
        self._cache.pop(eid, None)
        self.dirty = True

    def gen_ctx(self) -> dict:
        return {"keys": self.keys(), "colw": self.assets["mania_config"]["column_width"]}

    def lay(self, name) -> dict:
        return self.layout.get(name, {})

    def set_lay(self, eid, name, **kw):
        d = self.layout.setdefault(name, {"dx": 0, "dy": 0, "scale": 100, "locked": False})
        d.update(kw)
        self._cache.pop(eid, None)
        self.dirty = True

    def ui_scale(self, eid) -> float:
        return 0.5 if ELEMENT_BY_ID[eid].get("hd") else 1.0

    def canvas(self, cid):
        return next((c for c in self.canvases if c["id"] == cid), None)

    def canvas_image(self, name: str):
        """Lienzo por nombre de archivo (p. ej. songselect-top.png), renderizado."""
        for c in self.canvases:
            if c["name"] == name:
                return gens.render_canvas(c, self.path), (0.5 if c["hd"] else 1.0)
        return None, 1.0

    def image(self, eid, name: str | None = None):
        if not self.assets[eid]["enabled"]:
            return None
        imgs = self.images(eid)
        if not imgs:
            return None
        return imgs.get(name) if name else next(iter(imgs.values()))

    def custom_image(self, name: str):
        for c in self.customs:
            if c["name"] == name:
                f = self.path / c["file"]
                if str(f) not in self._img_cache and f.is_file():
                    self._img_cache[str(f)] = QImage(str(f))
                return self._img_cache.get(str(f))
        return None

    # ---- fuentes ---------------------------------------------------
    def register_fonts(self):
        for rel in self.fonts:
            f = self.path / rel
            if f.is_file():
                QFontDatabase.addApplicationFont(str(f))

    # ---- persistencia ---------------------------------------------
    def to_json(self) -> dict:
        return {"format_version": FORMAT_VERSION, "name": self.name, "author": self.author,
                "assets": self.assets, "customs": self.customs, "fonts": self.fonts, "exported": self.exported,
                "overrides": self.overrides, "canvases": self.canvases, "anims": self.anims,
                "modes": self.modes, "library": self.library, "scene_objs": self.scene_objs, "layout": self.layout,
                "effects": self.effects, "slots": self.slots}

    # ---- deshacer / rehacer -----------------------------------------
    def snapshot(self) -> str:
        d = self.to_json()
        d.pop("exported", None)
        return json.dumps(d, sort_keys=True, ensure_ascii=False)

    def restore(self, text: str):
        d = json.loads(text)
        for eid, vals in d["assets"].items():
            if eid in self.assets:
                self.assets[eid] = copy.deepcopy(vals)
        for attr in ("customs", "fonts", "overrides", "canvases", "anims", "modes", "library", "scene_objs", "layout",
                     "effects", "slots"):
            setattr(self, attr, copy.deepcopy(d.get(attr, getattr(self, attr))))
        self._cache.clear()
        self.dirty = True

    def save(self):
        self.path.mkdir(parents=True, exist_ok=True)
        files = build_files(self)
        skin_dir = self.path / "skin"
        skin_dir.mkdir(exist_ok=True)
        for name, data in files.items():
            (skin_dir / name).write_bytes(data)
        for old in self.exported:
            if old not in files and (skin_dir / old).is_file():
                (skin_dir / old).unlink()
        self.exported = sorted(files)
        tmp = self.path / "project.json.tmp"
        tmp.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path / "project.json")
        self.dirty = False

    @classmethod
    def load(cls, folder) -> "Project":
        folder = Path(folder)
        data = json.loads((folder / "project.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("project.json no tiene el formato esperado.")
        if int(data.get("format_version", 1)) > FORMAT_VERSION:
            raise ValueError("Este proyecto es de una versión más nueva del creador.")
        pr = cls(str(data.get("name") or folder.name), str(data.get("author") or ""), folder)
        pr.fonts = [f for f in data.get("fonts", []) if isinstance(f, str)]
        pr.register_fonts()
        for eid, vals in (data.get("assets") or {}).items():
            if isinstance(vals, dict):
                for key, val in vals.items():
                    pr._apply(eid, key, val)
        pr.customs = [c for c in data.get("customs", []) if isinstance(c, dict) and "name" in c and "file" in c]
        pr.exported = [x for x in data.get("exported", []) if isinstance(x, str)]
        ov = data.get("overrides") or {}
        pr.overrides = {e: {n: r for n, r in d.items() if isinstance(r, str)} for e, d in ov.items()
                        if e in ELEMENT_BY_ID and isinstance(d, dict)}
        pr.canvases = [c for c in data.get("canvases", []) if isinstance(c, dict) and "layers" in c and "id" in c]
        pr.anims = [a for a in data.get("anims", []) if isinstance(a, dict) and "frames" in a and "name" in a]
        pr.modes = {k: bool(v) for k, v in (data.get("modes") or {}).items()}
        pr.layout = {k: v for k, v in (data.get("layout") or {}).items() if isinstance(v, dict)}
        pr.effects = [e for e in data.get("effects", []) if isinstance(e, dict) and "event" in e]
        pr.slots = {k: v for k, v in (data.get("slots") or {}).items() if isinstance(v, (str, list))}
        pr.library = [c for c in data.get("library", []) if isinstance(c, dict) and "name" in c and "file" in c]
        pr.scene_objs = {k: [x for x in v if isinstance(x, dict)] for k, v in (data.get("scene_objs") or {}).items()
                         if isinstance(v, list)}
        pr._cache.clear()
        pr.dirty = False
        return pr


# ----------------------------------------------------------------------
# skin.ini
# ----------------------------------------------------------------------
def _on(pr, eid):
    return pr.assets[eid]["enabled"] and pr.modes.get(ELEMENT_BY_ID[eid]["mode"], True)


def _blanked(pr, eid):
    """Elemento desmarcado dentro de un modo activo: se exporta transparente (no desaparece al default de osu!)."""
    return (not pr.assets[eid]["enabled"] and ELEMENT_BY_ID[eid]["toggle"]
            and pr.modes.get(ELEMENT_BY_ID[eid]["mode"], True) and eid != "menu_bg")


def _shown(pr, eid):
    return _on(pr, eid) or _blanked(pr, eid)


def _compat(pr):
    t = pr.assets["theme"]
    return t.get("compat", "stable/lazer"), t.get("legacy_year", "2015")


def canvas_mode(name: str):
    for mode, items in FIXED_SECTIONS.items():
        if any(n == name for _, n in items):
            return mode
    return None


def _visible_objs(pr, scene):
    return [L for L in pr.scene_objs.get(scene, []) if L.get("visible", True)]


def bake_mania_sides(pr) -> dict:
    """Objetos libres de mania -> mania-stage-left/right-<K>k@2x.png, del borde del escenario al de la pantalla.
    osu! estira StageLeft/Right SOLO en alto (a toda la pantalla) y deja su ancho natural: una imagen @2x de N px mide
    N/2 unidades de 768, o sea N/3.2 unidades de 480. Por eso se hornea a 3.2 px por unidad en ambos ejes (sin deformar)."""
    objs = _visible_objs(pr, "mania")
    if not objs:
        return {}
    gen = pr.images("mania_stage") if _on(pr, "mania_stage") else {}
    out = {}
    for K in pr.keys():
        lay = mania_layout(pr, K)
        sx, total, W = lay["start"], lay["total"], lay["W"]
        for side, x0, x1 in (("left", 0, sx), ("right", sx + total, W)):
            f = 3.2
            img = gens.new_img(max(1, round((x1 - x0) * f)), round(480 * f))
            p = gens.make_painter(img)
            cv = next((c for c in pr.canvases if c["name"] == f"mania-stage-{side}.png"), None)
            base = gens.render_canvas(cv, pr.path) if cv else gen.get(f"mania-stage-{side}.png")
            if base is not None and not base.isNull():
                bw = stage_side_width(base, bool(cv and cv["hd"])) * f
                p.drawImage(QRectF(img.width() - bw if side == "left" else 0, 0, bw, img.height()), base)
            p.scale(f, f)
            p.translate(-x0, 0)
            for L in objs:
                gens.draw_layer(p, L, pr.path)
            p.end()
            out[f"mania-stage-{side}-{K}k.png"] = img
    return out


def stage_side_width(img, hd=False) -> float:
    """Ancho (unidades de 480) con el que osu! dibuja mania-stage-left/right: ancho natural, alto estirado."""
    return img.width() * (0.5 if hd else 1.0) * 480 / 768


def bake_bottom(pr, base, base_hd):
    """Objetos libres de la selección de canciones -> songselect-bottom@2x, anclado abajo a la izquierda y tan alto
    como haga falta para llegar al objeto más alto."""
    objs = _visible_objs(pr, "menu")
    if not objs:
        return None
    W = 768 * ASPECTS[pr.assets["mania_config"]["aspect"]]
    top = max(0, min(L["y"] for L in objs))
    h_units = 768 - top
    img = gens.new_img(round(W * 2), round(h_units * 2))
    p = gens.make_painter(img)
    if base is not None and not base.isNull():
        k = 1 if base_hd else 2
        p.drawImage(QRectF(0, img.height() - base.height() * k, base.width() * k, base.height() * k), base)
    p.scale(2, 2)
    p.translate(0, -top)
    for L in objs:
        gens.draw_layer(p, L, pr.path)
    p.end()
    return img


def bake_scene(pr, scene, base=None):
    """Compone los objetos libres de una escena sobre su imagen de destino (1366x768)."""
    objs = [L for L in pr.scene_objs.get(scene, []) if L.get("visible", True)]
    if not objs:
        return None
    img = base.scaled(1366, 768) if base is not None else gens.new_img(1366, 768)
    p = gens.make_painter(img)
    p.scale(1366 / (768 * ASPECTS[pr.assets["mania_config"]["aspect"]]), 1)
    for L in objs:
        gens.draw_layer(p, L, pr.path)
    p.end()
    return img


def build_skin_ini(pr: Project) -> str:
    g = pr.assets["skin_ini"]
    kind, year = _compat(pr)
    version = {"lazer": "latest", "totally": "latest", "legacy osu!": LEGACY_VERSION[year]}.get(kind) or _clean(g["version"]) or "latest"
    std_on = pr.modes.get("std", True)
    L = ["[General]", f"Name: {_clean(g['name'])}", f"Author: {_clean(g['author'])}",
         f"Version: {version}",
         *([f"AllowSliderBallTint: {int(g['allow_slider_ball_tint'])}", f"CursorRotate: {int(g['cursor_rotate'])}"] if std_on else []),
         *([f"AnimationFramerate: {pr.anims[0]['fps']}"] if pr.anims else
           [f"AnimationFramerate: {e['fps']}" for e in pr.effects if e.get("enabled", True)
            and EFFECT_EVENTS[e["event"]][1]][:1])]
    colours = []
    if std_on:      # sin modo standard no se escribe nada suyo y osu! usa su skin por defecto
        colours += [f"Combo{i}: {rgb_str(g[f'combo{i}'])}" for i in range(1, 5)]
        colours.append(f"SliderBorder: {rgb_str(g['slider_border'])}")
        if g["use_track_override"]:
            colours.append(f"SliderTrackOverride: {rgb_str(g['slider_track'])}")
    if _on(pr, "menu_panel"):
        mp = pr.assets["menu_panel"]
        colours += [f"SongSelectActiveText: {rgb_str(mp['active_text'])}",
                    f"SongSelectInactiveText: {rgb_str(mp['inactive_text'])}"]
    if colours:
        L += ["", "[Colours]"] + colours
    fonts = []
    if std_on:
        if _on(pr, "numbers"):
            fonts.append("HitCirclePrefix: default")
        fonts.append(f"HitCircleOverlap: {g['hitcircle_overlap']}")
    if _on(pr, "combo_font"):
        fonts += ["ComboPrefix: combo", f"ComboOverlap: {digit_overlap(pr, 'combo_font')}"]
    if _on(pr, "score_font"):
        fonts += ["ScorePrefix: score", f"ScoreOverlap: {digit_overlap(pr, 'score_font')}"]
    if fonts:
        L += ["", "[Fonts]"] + fonts
    if (_on(pr, "catch_fruits") or _on(pr, "catch_catcher")) and not (kind == "legacy osu!" and int(year) < 2014):
        L += ["", "[CatchTheBeat]", f"HyperDash: {rgb_str(g['hyperdash'])}",
              f"HyperDashFruit: {rgb_str(g['hyperdash_fruit'])}", f"HyperDashAfterImage: {rgb_str(g['hyperdash_after'])}"]
    if pr.modes.get("mania", True) and not (kind == "legacy osu!" and int(year) < 2012) and (
            any(_on(pr, e) for e in ("mania_notes", "mania_keys", "mania_stage", "mania_lighting", "mania_hits")) or any(c["name"].startswith("mania-") for c in pr.canvases) or _visible_objs(pr, "mania")):
        for K in pr.keys():
            L += [""] + mania_section(pr, K)
    return "\r\n".join(L) + "\r\n"


def mania_section(pr: Project, K: int) -> list[str]:
    cfg = pr.assets["mania_config"]
    cols = gens.mania_columns(K)
    lay = mania_layout(pr, K)
    w = lay["w"]
    nv = pr.values("mania_notes")
    rotate = bool(nv.get("rotate_by_column", True))
    shape = nv["note_shape"]
    hp = cfg["hit_position"]
    L = ["[Mania]", f"Keys: {K}", f"ColumnStart: {round(lay['start'])}",
         "ColumnWidth: " + ",".join([str(w)] * K)]
    if K > 1:
        L.append("ColumnSpacing: " + ",".join([str(cfg["column_spacing"])] * (K - 1)))
    edge, mid = cfg.get("edge_line_width", 2), cfg["column_line_width"]
    bg = QColor(cfg.get("column_bg", "#000000"))
    bg_rgba = f"{bg.red()},{bg.green()},{bg.blue()},{round(255 * cfg.get('column_bg_opacity', 100) / 100)}"
    L += [f"Colour{i + 1}: {bg_rgba}" for i in range(K)]          # fondo de cada columna (alfa 0 = transparente)
    L += ["ColumnLineWidth: " + ",".join([str(edge)] + [str(mid)] * (K - 1) + [str(edge)]),
          f"ColourColumnLine: {rgba_str(cfg['column_line_color'])}",
          f"ColourBarline: {rgba_str(cfg['bar_line_color'])}",
          f"HitPosition: {hp}", f"LightPosition: {cfg['light_position']}",
          f"ScorePosition: {cfg['score_position']}", f"ComboPosition: {cfg['combo_position']}",
          f"JudgementLine: {int(cfg['judgement_line'])}",
          f"UpsideDown: {int(cfg['upside_down'])}", f"KeysUnderNotes: {int(cfg['keys_under_notes'])}"]
    for i, (t, d) in enumerate(cols):
        if _shown(pr, "mania_notes"):
            n = gens.note_name(t, d, rotate, shape)
            L += [f"NoteImage{i}: {n}", f"NoteImage{i}H: {n}H", f"NoteImage{i}L: {n}L", f"NoteImage{i}T: {n}T"]
        if _shown(pr, "mania_keys"):
            L += [f"KeyImage{i}: mania-key{t}", f"KeyImage{i}D: mania-key{t}D"]
    if _visible_objs(pr, "mania"):      # objetos de «Recursos» horneados a los lados del escenario
        L += [f"StageLeft: mania-stage-left-{K}k", f"StageRight: mania-stage-right-{K}k"]
    elif _shown(pr, "mania_stage"):
        L += ["StageLeft: mania-stage-left", "StageRight: mania-stage-right"]
    if _shown(pr, "mania_stage"):
        L += ["StageHint: mania-stage-hint", "StageLight: mania-stage-light"]
    if any(c["name"].startswith("mania-stage-bottom") for c in pr.canvases):
        L.append("StageBottom: mania-stage-bottom")
    if _shown(pr, "mania_lighting"):
        L += ["LightingN: lightingN", "LightingL: lightingL"]
    if _shown(pr, "mania_hits"):
        L += [f"Hit{n.upper() if n == '300g' else n}: mania-hit{n}" for n in ("0", "50", "100", "200", "300", "300g")]
    return L


# ----------------------------------------------------------------------
# Validación y exportación
# ----------------------------------------------------------------------
def build_files(pr: Project) -> dict[str, bytes]:
    files = {"skin.ini": build_skin_ini(pr).encode("utf-8")}
    kind = _compat(pr)[0]

    def put(name, img, hd):
        if hd and kind in ("legacy osu!", "totally"):      # build antigua: sin @2x, imagen a 1x
            files[name] = image_bytes(img.scaled(max(1, img.width() // 2), max(1, img.height() // 2),
                                                 Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation), name)
        if hd and kind != "legacy osu!":
            files[hd_name(name)] = image_bytes(img, name)
        elif not hd:
            files[name] = image_bytes(img, name)

    for eid in GENERATORS:
        if _on(pr, eid):
            for name, img in pr.images(eid).items():
                put(name, img, ELEMENT_BY_ID[eid].get("hd"))
        elif _blanked(pr, eid):      # quitado: se exporta vacío para que osu! no ponga el suyo por defecto
            for name, img in pr.images(eid).items():
                b = _blank(img)
                files[name] = image_bytes(b, name)
                if ELEMENT_BY_ID[eid].get("hd") or kind != "legacy osu!":
                    files[hd_name(name)] = image_bytes(b, name)
    if kind != "legacy osu!":
        files.update(hd_versions(pr))
    for cv in pr.canvases:
        m = canvas_mode(cv["name"])
        if m and not pr.modes.get(m, True):
            continue
        put(safe_name(cv["name"], "lienzo.png"), gens.render_canvas(cv, pr.path), cv["hd"])
    if pr.modes.get("mania", True):
        for name, img in bake_mania_sides(pr).items():
            put(name, img, True)
            if name not in files:      # también en SD para pantallas de menos de 800 px de alto
                files[name] = image_bytes(img.scaled(max(1, img.width() // 2), max(1, img.height() // 2),
                                                     Qt.AspectRatioMode.IgnoreAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation), name)
    for scene, (eid, target) in SCENE_TARGET.items():
        if not pr.modes.get(scene, True) or not pr.scene_objs.get(scene):
            continue
        cv = next((c for c in pr.canvases if c["name"] == target), None)
        if scene == "menu":       # selección: la barra inferior crece hacia arriba para llevar tus imágenes
            img = bake_bottom(pr, gens.render_canvas(cv, pr.path) if cv else None, bool(cv and cv["hd"]))
            if img is not None:
                put(target, img, True)
            continue
        base = gens.render_canvas(cv, pr.path) if cv else pr.images(eid).get(target)
        img = bake_scene(pr, scene, base)
        if img is not None:
            put(target, img, False)
    for e in pr.effects:
        files.update(effect_files(e))
    files.update(slot_files(pr))
    for an in pr.anims:
        base = safe_name(an["name"], "anim")
        for i, rel in enumerate(an["frames"]):
            f = pr.path / rel
            if f.is_file():
                files[f"{base}-{i}.png"] = f.read_bytes()
    for c in pr.customs:
        f = pr.path / c["file"]
        if f.is_file():
            files[safe_name(c["name"], "recurso.png")] = f.read_bytes()
    return files


def validate(pr: Project) -> list[tuple[str, str]]:
    out = []
    g = pr.assets["skin_ini"]
    if not g["name"].strip():
        out.append(("error", "El nombre de la skin está vacío (skin.ini)."))
    active = [e for e in GENERATORS if _on(pr, e)]
    if not active and not pr.customs:
        out.append(("error", "No hay ningún recurso activado."))
    seen = {}
    for e in active:
        for name, img in pr.images(e).items():
            if img.isNull():
                out.append(("error", f"{name} tiene dimensiones inválidas."))
            if name in seen:
                out.append(("warning", f"{name} lo generan «{seen[name]}» y «{e}»; se usa el último."))
            seen[name] = e
    for c in pr.customs:
        if c["name"] in seen:
            out.append(("warning", f"El recurso propio «{c['name']}» reemplaza al generado."))
        if not (pr.path / c["file"]).is_file():
            out.append(("error", f"Falta el archivo del recurso propio «{c['name']}»."))
    for e in RECOMMENDED:
        if not pr.assets[e]["enabled"]:
            out.append(("warning", f"«{ELEMENT_BY_ID[e]['name']}» está desactivado: osu! usará el de la skin por defecto."))
    return out


def export_osk(pr: Project, dest) -> list[str]:
    dest = Path(dest)
    if dest.suffix.lower() != ".osk":
        dest = dest.with_suffix(".osk")
    files = build_files(pr)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() is not None:
                raise RuntimeError("El ZIP generado está dañado.")
            missing = set(files) - set(z.namelist())
            if missing:
                raise RuntimeError("Faltan archivos en el .osk: " + ", ".join(sorted(missing)))
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return list(files)


# ----------------------------------------------------------------------
# Lienzos libres
# ----------------------------------------------------------------------
CANVAS_PRESETS = {
    "Barra superior de selección (songselect-top)": dict(name="songselect-top.png", w=2732, h=170, hd=True, accent=True),
    "Barra inferior de selección (songselect-bottom)": dict(name="songselect-bottom.png", w=2732, h=180, hd=True, accent=True),
    "Base del escenario de mania (mania-stage-bottom)": dict(name="mania-stage-bottom.png", w=512, h=128, hd=False, accent=False),
    "Mania · imagen izquierda del escenario (mania-stage-left)": dict(name="mania-stage-left.png", w=600, h=960, hd=False, accent=False),
    "Mania · imagen derecha del escenario (mania-stage-right)": dict(name="mania-stage-right.png", w=600, h=960, hd=False, accent=False),
    "Taiko · pista derecha (taiko-bar-right)": dict(name="taiko-bar-right.png", w=1366, h=420, hd=False, accent=False),
    "Taiko · panel izquierdo (taiko-bar-left)": dict(name="taiko-bar-left.png", w=260, h=420, hd=False, accent=False),
    "Lienzo libre (decoración / perfil / lo que quieras)": dict(name="decoracion.png", w=1024, h=512, hd=False, accent=False),
}

CANVAS_BY_NAME = {v["name"]: k for k, v in CANVAS_PRESETS.items()}
# secciones fijas del árbol: modo -> [(etiqueta, archivo del lienzo)]
FIXED_SECTIONS = {
    "mania": [("Recurso de escenario · izquierda", "mania-stage-left.png"), ("Recurso de escenario · derecha", "mania-stage-right.png"),
              ("Recurso de escenario · base", "mania-stage-bottom.png")],
    "taiko": [("Panel izquierdo (lienzo libre)", "taiko-bar-left.png"), ("Pista / banner (lienzo libre)", "taiko-bar-right.png")],
    "menu": [("Barra superior", "songselect-top.png"), ("Barra inferior / perfil", "songselect-bottom.png")],
}
FIXED_NAMES = {n for v in FIXED_SECTIONS.values() for _, n in v}
# escena -> (elemento, archivo) donde se hornean los objetos libres de «Recursos»
SCENE_TARGET = {"pause": ("pause_screen", "pause-overlay.png"), "fail": ("fail_screen", "fail-background.png"),
                "menu": ("", "songselect-bottom.png"),
                "home": ("menu_bg", "menu-background.jpg")}


def _uid() -> str:
    return "%08x" % random.getrandbits(32)


def new_layer(kind: str, cv: dict, **over) -> dict:
    w, h = (min(400, cv["w"] // 2), min(120, cv["h"] // 2)) if kind != "image" else (min(300, cv["w"] // 3), min(300, cv["h"]))
    L = dict(id=_uid(), kind=kind, name={"shape": "Forma", "text": "Texto", "image": "Imagen"}[kind],
             x=cv["w"] // 2 - w // 2, y=cv["h"] // 2 - h // 2, w=w, h=h, rot=0, visible=True,
             shape="cuadrado redondeado", roundness=20, fill_mode="sólido", color="#53b9ff", color2="#1d3a5a",
             grad_angle=90, opacity=100, border_width=0, border_color="#ffffff", border_style="sólido",
             glow=0, glow_color="#53b9ff", shadow=0,
             text="Texto", font="Arial", font_size=64, bold=True, italic=False, outline_width=0,
             outline_color="#000000", file="")
    L.update(over)
    return L


def new_canvas(preset: str) -> dict:
    p = CANVAS_PRESETS[preset]
    cv = dict(id=_uid(), name=p["name"], w=p["w"], h=p["h"], hd=p["hd"], bg_mode="transparente",
              bg_color="#0b0d14", bg_color2="#1b2030", bg_angle=90, layers=[])
    if p["accent"]:
        cv["layers"].append(new_layer("shape", cv, name="Fondo", x=0, y=0, w=cv["w"], h=cv["h"], shape="cuadrado redondeado",
                                      roundness=0, fill_mode="degradado", color="#05060a", color2="#12172a"))
        cv["layers"].append(new_layer("shape", cv, name="Línea de acento", x=0, y=cv["h"] - 10, w=cv["w"], h=8,
                                      roundness=0, color="#53b9ff"))
    return cv


_BORDER_SEC = [sec("Borde"), I("border_width", "Grosor", 0, 0, 60, "px"), C("border_color", "Color", "#ffffff"),
               CH("border_style", "Estilo", "sólido", BORDERS), sec("Efectos"), I("glow", "Resplandor", 0, 0, 80, "px"),
               C("glow_color", "Color del resplandor", "#53b9ff"), I("shadow", "Sombra", 0, 0, 60, "px")]
LAYER_SPECS = {
    "common": [P("name", "Nombre de la capa", "text", ""), B("visible", "Visible", True),
               sec("Posición y tamaño (px del lienzo)"), I("x", "X", 0, -4000, 8000), I("y", "Y", 0, -4000, 8000),
               I("w", "Ancho", 100, 2, 8000), I("h", "Alto", 100, 2, 8000), I("rot", "Rotación", 0, -180, 180, "°")],
    "shape": [sec("Forma"), CH("shape", "Forma", "cuadrado redondeado", SHAPES), I("roundness", "Redondeo", 20, 0, 100, "%"),
              sec("Relleno"), CH("fill_mode", "Tipo", "sólido", FILLS), C("color", "Color", "#53b9ff"),
              C("color2", "Color 2", "#1d3a5a"), I("grad_angle", "Ángulo", 90, 0, 360, "°"),
              I("opacity", "Opacidad", 100, 0, 100, "%")] + _BORDER_SEC,
    "text": [sec("Texto"), P("text", "Texto", "text", "Texto"), P("font", "Tipografía", "font", "Arial"),
             I("font_size", "Tamaño de letra", 64, 6, 600, "px"), B("bold", "Negrita", True), B("italic", "Cursiva", False),
             sec("Color"), CH("fill_mode", "Relleno", "sólido", ["sólido", "degradado"]), C("color", "Color", "#ffffff"),
             C("color2", "Color 2", "#cfd8e8"), sec("Contorno"), I("outline_width", "Grosor", 0, 0, 30, "px"),
             C("outline_color", "Color", "#000000"), I("shadow", "Sombra", 0, 0, 40, "px"),
             I("glow", "Resplandor", 0, 0, 60, "px"), C("glow_color", "Color del resplandor", "#53b9ff")],
    "image": [sec("Imagen"), I("opacity", "Opacidad", 100, 0, 100, "%")],
}
CANVAS_SPECS = [P("name", "Nombre del archivo", "text", "lienzo.png"), I("w", "Ancho (px)", 1024, 16, 4096),
                I("h", "Alto (px)", 512, 16, 4096), B("hd", "Exportar como @2x (1 unidad = 2 px)", False),
                CH("bg_mode", "Fondo", "transparente", ["transparente", "sólido", "degradado"]),
                C("bg_color", "Color de fondo", "#0b0d14"), C("bg_color2", "Color 2", "#1b2030"),
                I("bg_angle", "Ángulo", 90, 0, 360, "°")]


# ----------------------------------------------------------------------
# Acciones del panel de tema
# ----------------------------------------------------------------------
def _set_palette(pr: Project, cols: list[str]):
    pr.set_many("skin_ini", {"combo1": cols[0], "combo2": cols[1], "combo3": cols[2], "combo4": cols[3]})
    pr.set_many("theme", {"accent": cols[0], "accent2": cols[1], "accent3": cols[2]})


def action_apply_preset(pr: Project):
    t = pr.assets["theme"]
    pset = PRESETS[t["preset"]]
    pr.set_many("theme", {k: v for k, v in pset.items()})
    pr.set_many("skin_ini", {"combo1": pset["accent"], "combo2": pset["accent2"], "combo3": pset["accent3"],
                             "combo4": shade_hex(pset["accent"])})
    pr.has_theme_all(True)


def shade_hex(s: str) -> str:
    return QColor(s).lighter(130).name()


def action_apply_harmony(pr: Project):
    t = pr.assets["theme"]
    _set_palette(pr, harmony_colors(t["base_color"], t["harmony"]))


def action_random_palette(pr: Project):
    rng = random.Random()
    base = QColor.fromHsv(rng.randrange(360), rng.randrange(140, 256), rng.randrange(190, 256)).name()
    kind = rng.choice(HARMONIES)
    pr.set_many("theme", {"base_color": base, "harmony": kind})
    _set_palette(pr, harmony_colors(base, kind))


def action_font_all(pr):
    f = pr.get("theme", "font")
    for e in ELEMENTS:
        if e["id"] != "theme" and "font" in e["specs"]:
            pr.set(e["id"], "font", f)
    for layers in [c["layers"] for c in pr.canvases] + list(pr.scene_objs.values()):
        for L in layers:
            if L.get("kind") == "text":
                L["font"] = f
    pr.dirty = True


def action_menu_style(pr):
    m = pr.assets["menu_style"]
    a, b, t, bd = m["accent"], m["base"], m["text"], m["border"]
    common = {"roundness": m["roundness"], "use_theme": False}
    pr.set_many("menu_back", dict(common, color=a, color2=shade(a, 70), text_color=t, font=m["font"]))
    pr.set_many("sel_buttons", dict(common, color=b, color2=shade(b, 60), border_width=m["border_width"],
                                    border_color=bd, text_color=t, hover_color=a, font=m["font"]))
    pr.set_many("menu_panel", dict(common, border_width=m["border_width"]))
    pr.set_many("menu_tab", common)
    pr.set_many("mod_icons", dict(common, color=b, border_color=bd, text_color=t, font=m["font"],
                                  border_width=max(1, m["border_width"])))
    pr.set_many("stars", {"color": a, "use_theme": False})
    pr.set_many("ranking", {"font": m["font"]})


ACTIONS = {"apply_preset": action_apply_preset, "font_all": action_font_all, "menu_style_apply": action_menu_style, "apply_harmony": action_apply_harmony,
           "random_palette": action_random_palette,
           "theme_all_on": lambda pr: pr.has_theme_all(True), "theme_all_off": lambda pr: pr.has_theme_all(False)}