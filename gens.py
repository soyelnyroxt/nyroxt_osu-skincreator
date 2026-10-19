# -*- coding: utf-8 -*-
"""Generadores de imágenes de cada elemento. Firma: gen(v, ctx) -> {archivo: QImage}."""
from __future__ import annotations

import math
import random

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainterPath, QPen, QPolygonF,
                           QRadialGradient)

from gfx import (DIRECTIONAL, col, make_painter, new_img, paint_path, paint_text_path,
                 radial_glow, render_shape, render_text, ring_vals, shade, shape_path,
                 text_path)


def sz(base: int, v: dict, lo: int = 12, hi: int = 1024) -> int:
    return max(lo, min(hi, round(base * v.get("size", 100) / 100)))


# ======================================================================
# osu!standard
# ======================================================================
def g_hitcircle(v, c):
    S = sz(128, v)
    return {"hitcircle.png": render_shape(S, S, v, S / 128)}


def g_hitcircleoverlay(v, c):
    S = sz(128, v)
    return {"hitcircleoverlay.png": render_shape(S, S, ring_vals(v), S / 128)}


def g_approach(v, c):
    S = sz(128, v)
    return {"approachcircle.png": render_shape(S, S, ring_vals(v), S / 128)}


def g_numbers(v, c):
    k = sz(64, v) / 64
    W, H = round(56 * k), round(64 * k)
    out = {}
    for d in range(10):
        out[f"default-{d}.png"] = render_text(str(d), v, W, H, k, default_size=46)
    return out


def g_score_font(v, c):
    """score-0..9, coma, punto, % y x (ScorePrefix) + scoreentry-* para la clasificación."""
    k = sz(64, v) / 64
    W, H = round(56 * k), round(72 * k)
    chars = {**{str(d): str(d) for d in range(10)}, "comma": ",", "dot": ".", "percent": "%", "x": "x"}
    out = {f"score-{n}.png": _trim_h(render_text(ch, v, W, H, k, default_size=56)) for n, ch in chars.items()}
    ke = k * v.get("entry_size", 45) / 100 * 0.6      # los de la clasificación son mucho más pequeños
    for n, ch in chars.items():
        if n != "percent":
            out[f"scoreentry-{n}.png"] = _trim_h(render_text(ch, v, round(56 * ke), round(72 * ke), ke, default_size=56))
    return out


def g_hp_bar(v, c):
    """scorebar-bg y scorebar-colour (@2x). off_x/off_y = borde transparente para moverla."""
    # osu! dibuja scorebar-bg en (0,0) y scorebar-colour en (5,16) (unidades 1x = 10,32 px en @2x):
    # el relleno NO lleva margen propio, y el fondo deja su hueco justo ahí.
    L, T = v.get("length", 100) / 100, v.get("thickness", 100) / 100
    CW, CH_ = round(1240 * L), max(8, round(34 * T))
    W, H = CW + 20, CH_ + 64
    ox, oy = v.get("off_x", 0) * 2, v.get("off_y", 0) * 2
    bg = new_img(W + ox, H + oy)
    p = make_painter(bg)
    bgv = dict(shape="píldora" if v.get("roundness", 50) >= 50 else "cuadrado redondeado", roundness=v.get("roundness", 50),
               fill_mode="sólido", color=v["bg_color"], opacity=v.get("bg_opacity", 70), border_width=v.get("border_width", 2),
               border_color=v.get("border_color", "#ffffff"), border_style="sólido", glow=0, shadow=0, rotation=0)
    p.drawImage(ox, oy, render_shape(W, H, bgv, 2.0))
    p.end()
    fill = new_img(CW + ox, CH_ + oy)
    p = make_painter(fill)
    fv = dict(shape="píldora", roundness=100, fill_mode="degradado", color=v["color"], color2=v["color2"], grad_angle=0,
              opacity=100, border_width=0, glow=v.get("glow", 6), glow_color=v["color"], shadow=0, rotation=0)
    p.drawImage(ox, oy, render_shape(CW, CH_, fv, 2.0))
    p.end()
    return {"scorebar-bg.png": bg, "scorebar-colour.png": fill}


def g_skip(v, c):
    W, H = 560, 200
    img = _box(W, H, v, v.get("btn_style", "píldora"))
    p = make_painter(img)
    _text_into(p, v.get("label", "Skip"), v, W, H, frac=0.85)
    p.end()
    return {"play-skip.png": img}


def g_combo_font(v, c):
    """combo-0..9 y combo-x: contador de combo (ComboPrefix en skin.ini), el de mania y el de abajo a la izquierda."""
    k = sz(64, v) / 64
    W, H = round(56 * k), round(72 * k)
    out = {f"combo-{d}.png": _trim_h(render_text(str(d), v, W, H, k, default_size=56)) for d in range(10)}
    out["combo-x.png"] = _trim_h(render_text("x", v, W, H, k, default_size=56))
    return out


def _trim_h(img, pad=2):
    """Quita el borde transparente de los lados: osu! junta los dígitos por el ancho del archivo."""
    w, h = img.width(), img.height()
    cols = [x for x in range(w) if any(img.pixelColor(x, y).alpha() > 8 for y in range(0, h, 2))]
    if not cols:
        return img
    x0, x1 = max(0, cols[0] - pad), min(w, cols[-1] + 1 + pad)
    return img.copy(x0, 0, x1 - x0, h)


def g_sliderb(v, c):
    S = sz(128, v)
    return {"sliderb.png": render_shape(S, S, v, S / 128)}


def g_follow(v, c):
    S = sz(256, v)
    return {"sliderfollowcircle.png": render_shape(S, S, v, S / 256)}


def g_reverse(v, c):
    S = sz(128, v)
    v2 = dict(v)
    v2["shape"] = v.get("shape", "flecha")
    return {"reversearrow.png": render_shape(S, S, v2, S / 128)}


def g_tick(v, c):
    S = sz(24, v, 8)
    return {"sliderscorepoint.png": render_shape(S, S, v, S / 24)}


def g_inputoverlay(v, c):
    S = sz(64, v)
    k = S / 64
    key = render_shape(S, S, v, k)
    # osu! dibuja el fondo girado 90°: por eso el archivo va en horizontal
    bg = render_shape(S * 4.6, S * 1.25, dict(v, shape="cuadrado redondeado", roundness=18, fill_mode="sólido",
                                              color="#0b0d14", opacity=85), k)
    return {"inputoverlay-key.png": key, "inputoverlay-background.png": bg}


def g_cursor(v, c):
    S = sz(64, v)
    k = S / 64
    img = render_shape(S, S, v, k)
    if v.get("dot", True):
        p = make_painter(img)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col(v.get("border_color", v["color"])))
        r = max(1.5, 3 * k)
        p.drawEllipse(QPointF(S / 2, S / 2), r, r)
        p.end()
    return {"cursor.png": img}


def g_trail(v, c):
    S = sz(32, v, 8)
    return {"cursortrail.png": radial_glow(S, v.get("color", "#ffffff"), v.get("opacity", 100), v.get("hardness", 0) / 100)}


def g_hits(v, c):
    k = v.get("size", 100) / 100
    out = {}
    for name, txt, key in (("hit0", "MISS", "color0"), ("hit50", "50", "color50"),
                           ("hit100", "100", "color100"), ("hit300", "300", "color300")):
        vv = dict(v, color=v[key], color2=shade(v[key], 170))
        out[f"{name}.png"] = render_text(txt, vv, 256 * k, 128 * k, k, default_size=64)
    return out


# ======================================================================
# osu!taiko
# ======================================================================
def g_taiko_circle(v, c):
    S = sz(128, v)
    return {"taikohitcircle.png": render_shape(S, S, v, S / 128),
            "taikohitcircleoverlay.png": render_shape(S, S, ring_vals(dict(v, width=v.get("overlay_width", 6),
                                                                           color=v.get("overlay_color", "#ffffff"))), S / 128)}


def g_taiko_big(v, c):
    S = sz(192, v)
    return {"taikobigcircle.png": render_shape(S, S, v, S / 192),
            "taikobigcircleoverlay.png": render_shape(S, S, ring_vals(dict(v, width=v.get("overlay_width", 8),
                                                                           color=v.get("overlay_color", "#ffffff"))), S / 192)}


def g_taiko_roll(v, c):
    S = sz(96, v)
    k = S / 96
    mid = render_shape(S, S, dict(v, shape="cuadrado redondeado", roundness=0, border_width=0, glow=0), k)
    end = render_shape(S, S, v, k)
    return {"taiko-roll-middle.png": mid, "taiko-roll-end.png": end}


def g_taiko_bar(v, c):
    k = v.get("size", 100) / 100
    vv = dict(v, shape="cuadrado redondeado", roundness=0)
    left = render_shape(256 * k, 256 * k, dict(vv, color=v["color"], color2=v["color2"]), k)
    right = render_shape(512 * k, 256 * k, dict(vv, color=v["lane_color"], color2=v["lane_color2"],
                                                border_width=0, glow=0), k)
    return {"taiko-bar-left.png": left, "taiko-bar-right.png": right}


def g_taiko_drum(v, c):
    S = sz(160, v)
    k = S / 160
    inner = render_shape(S, S, v, k)
    ov = dict(v, fill_mode="vacío", border_width=v.get("outer_width", 14), border_color=v.get("outer_color", "#e6e6e6"))
    outer = render_shape(S, S, ov, k)
    return {"taiko-drum-inner.png": inner, "taiko-drum-outer.png": outer}


# ======================================================================
# osu!catch
# ======================================================================
FRUITS = ["apple", "grapes", "pear", "oranges", "drop", "bananas"]


def fruit_path(kind: str, r: QRectF) -> QPainterPath:
    x0, y0, w, h = r.left(), r.top(), r.width(), r.height()
    cx, cy = x0 + w / 2, y0 + h / 2
    p = QPainterPath()
    p.setFillRule(Qt.FillRule.WindingFill)
    if kind == "apple":
        p.addEllipse(QRectF(x0, y0 + h * 0.1, w, h * 0.9))
    elif kind == "oranges":
        p.addEllipse(r)
    elif kind == "grapes":
        for dx, dy in [(-.27, -.25), (0, -.25), (.27, -.25), (-.14, .02), (.14, .02), (0, .29)]:
            p.addEllipse(QPointF(cx + dx * w, cy + dy * h), w * 0.17, w * 0.17)
    elif kind == "pear":
        p.addEllipse(QPointF(cx, cy + h * 0.2), w * 0.38, w * 0.38)
        p.addEllipse(QPointF(cx, cy - h * 0.25), w * 0.2, w * 0.2)
        poly = QPolygonF([QPointF(cx - w * 0.2, cy - h * 0.25), QPointF(cx + w * 0.2, cy - h * 0.25),
                          QPointF(cx + w * 0.36, cy + h * 0.2), QPointF(cx - w * 0.36, cy + h * 0.2)])
        p.addPolygon(poly)
    elif kind == "drop":
        rr = w * 0.3
        p.addEllipse(QPointF(cx, cy + h * 0.15), rr, rr)
        p.addPolygon(QPolygonF([QPointF(cx, y0 + h * 0.05), QPointF(cx + rr * 0.95, cy + h * 0.05),
                                QPointF(cx - rr * 0.95, cy + h * 0.05)]))
    elif kind == "bananas":
        outer = QPainterPath()
        outer.addEllipse(r)
        inner = QPainterPath()
        inner.addEllipse(QRectF(x0 + w * 0.22, y0 - h * 0.1, w * 0.95, h * 0.95))
        p = outer.subtracted(inner)
    return p


def _fruit_overlay(p, kind, r, v, k):
    x0, y0, w, h = r.left(), r.top(), r.width(), r.height()
    cx, cy = x0 + w / 2, y0 + h / 2
    pen = QPen(col(v.get("detail_color", "#ffffff")), max(1.5, 3 * k))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind in ("apple", "pear"):
        leaf = QPainterPath()
        leaf.addEllipse(QRectF(cx, y0 - h * 0.02, w * 0.28, h * 0.14))
        p.fillPath(leaf, col(v.get("detail_color", "#ffffff")))
        p.drawLine(QPointF(cx, y0 + h * 0.08), QPointF(cx - w * 0.02, y0 + h * 0.2))
    elif kind == "oranges":
        p.drawLine(QPointF(cx, y0 + h * 0.12), QPointF(cx, y0 + h * 0.88))
        p.drawLine(QPointF(x0 + w * 0.12, cy), QPointF(x0 + w * 0.88, cy))
    elif kind == "grapes":
        p.drawLine(QPointF(cx, y0 + h * 0.02), QPointF(cx, y0 + h * 0.12))
    elif kind == "drop":
        p.drawArc(QRectF(cx - w * 0.15, cy - h * 0.02, w * 0.2, h * 0.3), 120 * 16, 90 * 16)
    elif kind == "bananas":
        p.drawArc(QRectF(x0 + w * 0.1, y0 + h * 0.1, w * 0.7, h * 0.8), 100 * 16, 90 * 16)


def g_fruits(v, c):
    S = sz(128, v)
    k = S / 128
    out = {}
    for kind in FRUITS:
        m = max(2.0, v.get("border_width", 0) * k / 2 + v.get("glow", 0) * k + 3)
        rect = QRectF(m, m, S - 2 * m, S - 2 * m)
        path = QPainterPath()
        path.addEllipse(rect)      # por defecto todas son círculos; cámbialas con tu imagen
        body = new_img(S, S)
        p = make_painter(body)
        paint_path(p, path, rect, v, k, parts=("shadow", "glow", "fill"))
        p.end()
        ov = new_img(S, S)
        p = make_painter(ov)
        paint_path(p, path, rect, dict(v, border_width=max(v.get("border_width", 0), 3)), k, parts=("border",))
        p.end()
        out[f"fruit-{kind}.png"] = body
        out[f"fruit-{kind}-overlay.png"] = ov
    return out


def catcher_path(kind: str, r: QRectF) -> QPainterPath:
    x0, y0, w, h = r.left(), r.top(), r.width(), r.height()
    p = QPainterPath()
    if kind == "cuenco":
        p.moveTo(x0, y0 + h * 0.2)
        p.arcTo(QRectF(x0, y0 - h * 0.8, w, h * 1.8), 180, 180)
        p.closeSubpath()
    elif kind == "trapecio":
        p.addPolygon(QPolygonF([QPointF(x0, y0 + h * 0.2), QPointF(x0 + w, y0 + h * 0.2),
                                QPointF(x0 + w * 0.82, y0 + h), QPointF(x0 + w * 0.18, y0 + h)]))
        p.closeSubpath()
    else:  # plato
        p.moveTo(x0, y0 + h * 0.3)
        p.arcTo(QRectF(x0, y0 - h * 0.3, w, h * 1.3), 180, 180)
        p.closeSubpath()
    return p


def g_catcher(v, c):
    k = v.get("size", 100) / 100
    W, H = round(192 * k), round(110 * k)
    out = {}
    for name, color, glow, rot in (("idle", v["color"], 0, 0), ("kiai", v["kiai_color"], 16, 0),
                                  ("fail", v["fail_color"], 0, 12)):
        vv = dict(v, color=color, color2=shade(color, 150), glow=glow or v.get("glow", 0))
        m = vv.get("border_width", 0) * k / 2 + vv["glow"] * k + 4
        rect = QRectF(m, m, W - 2 * m, H - 2 * m)
        img = new_img(W, H)
        p = make_painter(img)
        if rot:
            p.translate(W / 2, H / 2)
            p.rotate(rot)
            p.translate(-W / 2, -H / 2)
        paint_path(p, catcher_path(v.get("catcher_shape", "plato"), rect), rect, vv, k)
        p.end()
        out[f"fruit-catcher-{name}.png"] = img
    return out


# ======================================================================
# osu!mania
# ======================================================================
def mania_columns(K: int):
    """[(tipo, dirección)] por columna: tipo '1','2' o 'S' (centro)."""
    half = K // 2
    types = ["1" if i % 2 == 0 else "2" for i in range(half)]
    types = types + (["S"] if K % 2 else []) + list(reversed(types))
    dirs = []
    for i in range(K):
        if i < half:
            dirs.append("left" if i % 2 == 0 else "down")
        elif K % 2 and i == half:
            dirs.append("up")
        else:
            j = K - 1 - i
            dirs.append("right" if j % 2 == 0 else "up")
    return list(zip(types, dirs))


ROT = {"up": 0, "right": 90, "down": 180, "left": 270}
TYPE_KEY = {"1": "color1", "2": "color2", "S": "colorS"}


def note_name(t: str, d: str, rotate: bool, shape: str) -> str:
    return f"mania-note{t}{d if rotate and shape in DIRECTIONAL else ''}"


def _note(v, t, d, rotate):
    W = sz(128, v, 24, 256)
    k = W / 128
    shape = v["note_shape"]
    color = v[TYPE_KEY[t]]
    draw_shape = "cuadrado redondeado" if shape == "barra" else shape
    vv = dict(v, shape=draw_shape, color=color, color2=shade(color, 160), border_color=v["border_color"])
    if shape == "barra":
        vv["roundness"] = min(40, v.get("roundness", 50))
    if shape in DIRECTIONAL:
        H = round(W * 0.9)
        rot = ROT[d] if rotate else 0
    elif shape == "barra":
        H = max(8, round(W * v["note_height"] / 100))
        rot = v.get("rotation", 0)
    else:                      # círculos y demás figuras: siempre proporcionadas, nunca aplastadas
        H = W
        rot = v.get("rotation", 0)
    return render_shape(W, H, vv, k, rot=rot), W, k


def _hold_body(v, t, W, k):
    color = v.get("hold_body_color") or v[TYPE_KEY[t]]
    img = new_img(W, 128)
    p = make_painter(img)
    bw = W * v["body_width"] / 100
    p.fillRect(QRectF((W - bw) / 2, 0, bw, 128), col(color, v["body_opacity"]))
    p.end()
    return img


def _hold_tail_point(v, t, W):
    """Final del hold en forma de punta. osu! dibuja el final (T) volteado en vertical, así que el archivo
    apunta hacia abajo para que en el juego apunte hacia arriba."""
    H = max(8, round(W * 1.0))          # alta: osu! la centra en el final del cuerpo y la punta debe sobresalir entera
    img = new_img(W, H)
    p = make_painter(img)
    bw = W * v["body_width"] / 100
    x0, x1 = (W - bw) / 2, (W + bw) / 2
    path = QPainterPath()
    path.addPolygon(QPolygonF([QPointF(x0, 0), QPointF(x0, H * 0.5), QPointF(W / 2, H * 0.92), QPointF(x1, H * 0.5), QPointF(x1, 0)]))
    p.fillPath(path, col(v.get("hold_body_color") or v[TYPE_KEY[t]], v["body_opacity"]))
    p.end()
    return img


def g_mania_notes(v, c):
    keys = c.get("keys", [4])
    rotate = bool(v.get("rotate_by_column", True)) and v["note_shape"] in DIRECTIONAL
    used = sorted({(t, d if rotate else "") for K in keys for (t, d) in mania_columns(K)})
    out = {}
    for t, d in used:
        name = note_name(t, d or "up", rotate, v["note_shape"])
        img, W, k = _note(v, t, d or "up", rotate)
        out[f"{name}.png"] = img
        hv = dict(v, **{TYPE_KEY[t]: v.get("hold_head_color", v[TYPE_KEY[t]])})
        out[f"{name}H.png"] = _note(hv, t, d or "up", rotate)[0]
        out[f"{name}L.png"] = _hold_body(v, t, W, k)
        tail = v.get("tail_style", "punta")
        if tail == "punta":
            out[f"{name}T.png"] = _hold_tail_point(v, t, W)
        elif tail == "igual":
            out[f"{name}T.png"] = img
        elif tail == "plano":
            out[f"{name}T.png"] = render_shape(W, max(8, round(W * 0.3)), dict(v, color=v[TYPE_KEY[t]], color2=shade(v[TYPE_KEY[t]], 160)),
                                               k, shape="píldora", rot=0)
        else:
            out[f"{name}T.png"] = new_img(2, 2)
    return out


def g_mania_keys(v, c):
    # osu! estira el ANCHO de la tecla a la columna pero deja su ALTO natural (px 1x = unidades de 768).
    # Para que no se deforme, el archivo se hace con el ancho real de la columna: ColumnWidth x 1.6 px.
    W = max(16, round(c.get("colw", 70) * 1.6 * c.get("scale", 1)))
    k = W / 128
    H = round(W * v["key_height"] / 100)
    out = {}
    for t in ("1", "2", "S"):
        base = v[TYPE_KEY[t]]
        for pressed in (False, True):
            color = shade(base, 70) if pressed else base
            vv = dict(v, shape=v["key_shape"], color=color, color2=shade(color, 200),
                      border_color=shade(v["border_color"], 140) if pressed else v["border_color"],
                      glow=v["pressed_glow"] if pressed else 0, glow_color=base)
            img = render_shape(W, H, vv, k)
            if v.get("show_note_icon", True):
                p = make_painter(img)
                icon = shape_path(v["icon_shape"], QRectF(W * 0.3, H * 0.28, W * 0.4, H * 0.44), 50)
                p.fillPath(icon, col("#ffffff", 45 if pressed else 25))
                p.end()
            lift = v.get("key_lift", 0)
            if lift:        # borde transparente abajo: osu! pega la tecla al fondo, así queda más arriba
                pad = round(lift * W / max(1, c.get("colw", 70)))
                tall = new_img(W, img.height() + pad)
                p = make_painter(tall)
                p.drawImage(0, 0, img)
                p.end()
                img = tall
            out[f"mania-key{t}{'D' if pressed else ''}.png"] = img
    return out


def g_mania_stage(v, c):
    k = v.get("size", 100) / 100
    out = {}
    for name in ("left", "right"):
        img = new_img(24 * k, 512)
        p = make_painter(img)
        g = QLinearGradient(0, 0, img.width(), 0)
        solid, clear = col(v["edge_color"]), col(v["edge_color"], 0)
        g.setColorAt(0, clear if name == "left" else solid)
        g.setColorAt(1, solid if name == "left" else clear)
        p.fillRect(img.rect(), QBrush(g))
        p.end()
        out[f"mania-stage-{name}.png"] = img
    hint = render_shape(256, 24 * k, dict(v, shape="píldora", color=v["hint_color"], color2=shade(v["hint_color"], 140),
                                         fill_mode="degradado", glow=v["hint_glow"], glow_color=v["hint_color"],
                                         border_width=0, grad_angle=90), 1.0)
    out["mania-stage-hint.png"] = hint
    light = new_img(128, 480)
    p = make_painter(light)
    g = QLinearGradient(0, 480, 0, 0)
    g.setColorAt(0, col(v["light_color"], v["light_opacity"]))
    g.setColorAt(1, col(v["light_color"], 0))
    p.fillRect(light.rect(), QBrush(g))
    p.end()
    out["mania-stage-light.png"] = light
    return out


def g_mania_lighting(v, c):
    S = sz(256, v, 32, 512)
    k = S / 256
    img = radial_glow(S, v["color"], v["opacity"], v["hardness"] / 100)
    if v["ring_width"] > 0:
        p = make_painter(img)
        pen = QPen(col(v["ring_color"]), v["ring_width"] * k)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        m = v["ring_width"] * k + 2
        p.drawEllipse(QRectF(S * 0.25, S * 0.25, S * 0.5, S * 0.5))
        p.end()
    return {"lightingN.png": img, "lightingL.png": radial_glow(S, v["hold_color"], v["opacity"], v["hardness"] / 100)}


def g_mania_hits(v, c):
    k = v.get("size", 100) / 100
    out = {}
    for name, txt, key in (("0", "MISS", "color0"), ("50", "50", "color50"), ("100", "100", "color100"),
                           ("200", "200", "color200"), ("300", "300", "color300"), ("300g", "MAX", "color300g")):
        vv = dict(v, color=v[key], color2=shade(v[key], 170))
        out[f"mania-hit{name}.png"] = render_text(txt, vv, 256 * k, 128 * k, k, default_size=64)
    return out


# ======================================================================
# Menú (las imágenes se exportan en @2x: 1 unidad de interfaz = 2 px)
# ======================================================================
def fit_text_path(text, tv, k, W, H, size_key="font_size", default_size=30, frac=0.86):
    """Texto centrado que se encoge solo si no cabe en el ancho (evita que se salga del botón)."""
    path = text_path(text, tv, k, W, H, size_key, default_size)
    bw = path.boundingRect().width()
    if bw > W * frac and bw > 0:
        tv = dict(tv)
        tv[size_key] = max(4.0, tv.get(size_key, default_size) * W * frac / bw)
        path = text_path(text, tv, k, W, H, size_key, default_size)
    return path


def g_menu_bg(v, c):
    W, H = 1366, 768                       # tamaño SD sugerido por la wiki; debe ser .jpg
    img = new_img(W, H)
    p = make_painter(img)
    a = math.radians(v["angle"])
    R = math.hypot(W, H) / 2
    g = QLinearGradient(W / 2 - math.cos(a) * R, H / 2 - math.sin(a) * R,
                        W / 2 + math.cos(a) * R, H / 2 + math.sin(a) * R)
    g.setColorAt(0, col(v["color"]))
    g.setColorAt(1, col(v["color2"]))
    p.fillRect(img.rect(), QBrush(g))
    rng = random.Random(v["seed"])
    pat = v["pattern"]
    pc = col(v["pattern_color"], v["pattern_opacity"])
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(pc)
    for _ in range(v["density"]):
        x, y, s = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(10, 70)
        if pat == "triángulos":
            p.drawPolygon(QPolygonF([QPointF(x, y - s), QPointF(x + s, y + s), QPointF(x - s, y + s)]))
        elif pat == "puntos":
            p.drawEllipse(QPointF(x, y), s / 3, s / 3)
        elif pat == "líneas":
            p.setPen(QPen(pc, 2))
            p.drawLine(QPointF(x, y), QPointF(x + s * 2, y - s * 2))
            p.setPen(Qt.PenStyle.NoPen)
        elif pat == "hexágonos":
            p.drawPath(shape_path("hexágono", QRectF(x - s, y - s, s * 2, s * 2)))
    if v["vignette"] > 0:
        rg = QRadialGradient(W / 2, H / 2, W * 0.7)
        rg.setColorAt(0, QColor(0, 0, 0, 0))
        rg.setColorAt(1, QColor(0, 0, 0, int(2.2 * v["vignette"])))
        p.fillRect(img.rect(), QBrush(rg))
    p.end()
    return {"menu-background.jpg": img}


def _labelled(v, text, W, H, S):
    img = render_shape(W, H, v, S)
    p = make_painter(img)
    tv = dict(v, color=v["text_color"], fill_mode="sólido", shadow=0, glow=0, outline_width=0, bold=True)
    paint_text_path(p, fit_text_path(text, tv, S, W, H, "font_size", 30), tv, S)
    p.end()
    return img


BUTTONS = [("selection-mode", "label_mode", 182), ("selection-mods", "label_mods", 146),
           ("selection-random", "label_random", 142), ("selection-options", "label_options", 144)]


def g_sel_buttons(v, c):
    k = sz(100, v, 30, 300) / 100
    S, H = 2 * k, round(170 * k)
    out = {}
    for fname, key, w in BUTTONS:
        W = round(w * k)
        out[f"{fname}.png"] = _labelled(v, v[key], W, H, S)
        vo = dict(v, color=shade(v["color"], 70), color2=shade(v["color2"], 70),
                  border_color=v["hover_color"], glow=max(v.get("glow", 0), 6), glow_color=v["hover_color"])
        out[f"{fname}-over.png"] = _labelled(vo, v[key], W, H, S)
    return out


def g_menu_back(v, c):
    k = sz(100, v, 30, 300) / 100
    S, W, H = 2 * k, round(434 * k), round(128 * k)
    img = render_shape(W, H, v, S)
    p = make_painter(img)
    tv = dict(v, color=v["text_color"], fill_mode="sólido", shadow=0, glow=0, outline_width=0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(col(v["text_color"]))
    p.drawEllipse(QPointF(W * .13, H * .5), H * .26, H * .26)
    p.setBrush(col(v["color"]))
    p.drawPolygon(QPolygonF([QPointF(W * .095, H * .5), QPointF(W * .145, H * .3), QPointF(W * .145, H * .7)]))
    pp = fit_text_path(v["label"], tv, S, W * 0.5, H, "font_size", 30)
    pp.translate(W * 0.4, 0)
    paint_text_path(p, pp, tv, S)
    p.end()
    return {"menu-back.png": img}


def g_menu_panel(v, c):
    k = sz(100, v, 30, 300) / 100
    return {"menu-button-background.png": render_shape(1600 * k, 190 * k, v, 2 * k)}


def g_menu_tab(v, c):
    k = sz(100, v, 30, 300) / 100
    return {"selection-tab.png": render_shape(280 * k, 44 * k, v, 2 * k)}


def g_menu_logo(v, c):
    S = sz(512, v, 64, 1024)
    k = S / 512
    img = render_shape(S, S, v, k)
    p = make_painter(img)
    tv = dict(v, color=v["text_color"], fill_mode="sólido", shadow=0, glow=0, outline_width=0, bold=True)
    paint_text_path(p, fit_text_path(v["label"], tv, k, S, S, "font_size", 190, 0.7), tv, k)
    p.end()
    return {"menu-osu.png": img}


MODS = [("easy", "EZ", "r"), ("nofail", "NF", "r"), ("halftime", "HT", "r"), ("hardrock", "HR", "i"),
        ("suddendeath", "SD", "i"), ("perfect", "PF", "i"), ("doubletime", "DT", "i"), ("nightcore", "NC", "i"),
        ("hidden", "HD", "i"), ("flashlight", "FL", "i"), ("fadein", "FI", "i"), ("relax", "RX", "s"),
        ("relax2", "AP", "s"), ("spunout", "SO", "s"), ("autoplay", "AT", "a"), ("cinema", "CN", "a"),
        ("scorev2", "V2", "a"), ("target", "TP", "s"), ("mirror", "MR", "s"), ("random", "RD", "s"), ("coop", "CO", "s")] + \
       [(f"key{n}", f"{n}K", "s") for n in range(1, 10)]
MOD_COLORS = {"r": "color_reduce", "i": "color_increase", "s": "color_special", "a": "color_auto"}


def g_dialog_buttons(v, c):
    """button-left / middle / right (@2x): un botón redondeado cortado en 3; osu! estira el centro y lo tiñe."""
    H = round(110 * v.get("size", 100) / 100)
    cap, mid = max(8, H // 3), 8
    W = cap * 2 + mid
    vv = dict(v, shape="cuadrado redondeado", glow=0, shadow=0, rotation=0)
    full = render_shape(W, H, vv, 2.0)
    if v.get("gloss", True):
        p = make_painter(full)
        g = QLinearGradient(0, 0, 0, H / 2)
        g.setColorAt(0, QColor(255, 255, 255, 90))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.setCompositionMode(p.CompositionMode.CompositionMode_SourceAtop)
        p.fillRect(QRectF(0, 0, W, H / 2), QBrush(g))
        p.end()
    return {"button-left.png": full.copy(0, 0, cap, H), "button-middle.png": full.copy(cap, 0, mid, H),
            "button-right.png": full.copy(cap + mid, 0, cap, H)}


def g_mod_icons(v, c):
    """selection-mod-*.png (@2x): una placa con la abreviatura; color por tipo de mod si se quiere."""
    k = sz(100, v, 30, 300) / 100
    W, H = round(128 * k), round(124 * k)
    out = {}
    for name, abbr, kind in MODS:
        base = v[MOD_COLORS[kind]] if v.get("colors_by_type", True) else v["color"]
        img = render_shape(W, H, dict(v, color=base, color2=shade(base, 60)), 2 * k)
        p = make_painter(img)
        tv = dict(v, color=v["text_color"], fill_mode="sólido", shadow=0, glow=0, outline_width=0, bold=True)
        paint_text_path(p, fit_text_path(abbr, tv, 2 * k, W, H, "font_size", 24, 0.7), tv, 2 * k)
        p.end()
        out[f"selection-mod-{name}.png"] = img
    return out


def g_stars(v, c):
    S = sz(64, v, 8, 256)
    star = render_shape(S, S, v, S / 64)
    soft = radial_glow(S, v["color"], 90, 0.35)
    return {"star.png": star, "star2.png": soft}


def _mode_glyph(p, mode, r: QRectF, v, k):
    cx, cy, R = r.center().x(), r.center().y(), r.width() / 2
    color = col(v.get(f"color_{mode}", v["color"]), v.get("opacity", 100))
    if v.get("ring", True):
        pen = QPen(color, v.get("ring_width", 8) * k)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), R * 0.86, R * 0.86)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    if mode == "osu":
        p.drawEllipse(QPointF(cx, cy), R * 0.42, R * 0.42)
    elif mode == "taiko":
        path = QPainterPath()
        path.moveTo(cx, cy - R * 0.5)
        path.arcTo(QRectF(cx - R * 0.5, cy - R * 0.5, R, R), 90, 180)
        path.closeSubpath()
        p.drawPath(path)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(color, max(1.0, v.get("ring_width", 8) * k * 0.6)))
        p.drawEllipse(QPointF(cx, cy), R * 0.5, R * 0.5)
    elif mode == "fruits":
        for dx, dy in ((0, -0.26), (-0.24, 0.16), (0.24, 0.16)):
            p.drawEllipse(QPointF(cx + dx * R, cy + dy * R), R * 0.2, R * 0.2)
    else:
        for i, hh in enumerate((0.7, 0.45, 0.7)):
            x = cx + (i - 1) * R * 0.32
            p.drawRoundedRect(QRectF(x - R * 0.1, cy + R * 0.38 - R * hh, R * 0.2, R * hh), R * 0.06, R * 0.06)


def g_mode_icons(v, c):
    """mode-*.png (grande, fondo de selección), -med (menú de modo) y -small (paneles), todos @2x."""
    out = {}
    for mode in ("osu", "taiko", "fruits", "mania"):
        for suffix, S in (("", 512), ("-med", 128), ("-small", 64)):
            img = new_img(S, S)
            p = make_painter(img)
            m = max(2, S * 0.04)
            _mode_glyph(p, mode, QRectF(m, m, S - 2 * m, S - 2 * m), v, S / 128)
            p.end()
            out[f"mode-{mode}{suffix}.png"] = img
    return out


RANKS = [("XH", "#e8f1ff", "#9fb4d6"), ("X", "#ffe27a", "#f0a500"), ("SH", "#e8f1ff", "#9fb4d6"),
         ("S", "#ffe27a", "#f0a500"), ("A", "#7dff8f", "#1fae3a"), ("B", "#8fd3ff", "#2b78d6"),
         ("C", "#d9a6ff", "#8a3fd6"), ("D", "#ff8c8c", "#d63030")]


def g_ranking(v, c):
    k = sz(64, v, 16, 256) / 64
    out = {}
    for letter, c1, c2 in RANKS:
        vv = dict(v, color=c1, color2=c2, fill_mode="degradado")
        txt = "SS" if letter in ("X", "XH") else letter
        W = H = 64 * k
        img = new_img(W, H)
        p = make_painter(img)
        path = fit_text_path(txt, vv, k, W, H, "font_size", 48, 0.9)
        paint_text_path(p, path, vv, k)
        p.end()
        out[f"ranking-{letter}-small.png"] = img
    return out


# ======================================================================
# Pantallas: pausa, fallo y resultados (todo desde propiedades simples)
# ======================================================================
def _bg_fill(p, W, H, v):
    op = v.get("bg_opacity", 100)
    if v.get("bg_mode") == "degradado":
        a = math.radians(v.get("bg_angle", 90))
        R = math.hypot(W, H) / 2
        g = QLinearGradient(W / 2 - math.cos(a) * R, H / 2 - math.sin(a) * R, W / 2 + math.cos(a) * R, H / 2 + math.sin(a) * R)
        g.setColorAt(0, col(v["bg_color"], op))
        g.setColorAt(1, col(v["bg_color2"], op))
        p.fillRect(QRectF(0, 0, W, H), QBrush(g))
    else:
        p.fillRect(QRectF(0, 0, W, H), col(v["bg_color"], op))


def _tv(v, size_key="font_size", color_key="text_color"):
    return dict(font=v.get("font", "Arial"), font_size=v.get(size_key, 48), bold=v.get("bold", True),
                italic=v.get("italic", False), color=v.get(color_key, "#ffffff"), fill_mode="sólido",
                outline_width=v.get("outline_width", 0), outline_color=v.get("outline_color", "#000000"),
                shadow=v.get("text_shadow", 0), glow=0)


def _text_into(p, text, v, W, H, x=0, y=0, size_key="font_size", color_key="text_color", frac=0.92):
    if not text:
        return
    tv = _tv(v, size_key, color_key)
    path = fit_text_path(text, tv, 1.0, W, H, size_key, 48, frac)
    path.translate(x, y)
    paint_text_path(p, path, tv, 1.0)


def _box(W, H, v, style):
    """Botón: 'texto' (sin fondo), 'botón', 'píldora' o 'contorno'."""
    if style == "texto":
        return new_img(W, H)
    vv = dict(shape="píldora" if style == "píldora" else "cuadrado redondeado", roundness=v.get("roundness", 30),
              fill_mode="vacío" if style == "contorno" else "degradado", color=v["color"], color2=v["color2"],
              grad_angle=90, opacity=v.get("btn_opacity", 100), border_width=max(3, v.get("border_width", 0)) if style == "contorno"
              else v.get("border_width", 0), border_color=v.get("border_color", "#ffffff"), border_style="sólido",
              glow=v.get("glow", 0), glow_color=v.get("glow_color", "#53b9ff"), shadow=0, rotation=0, size=100)
    return render_shape(W, H, vv, 1.0)


PAUSE_BUTTONS = [("label_continue", "pause-continue.png"), ("label_retry", "pause-retry.png"), ("label_back", "pause-back.png")]


def pause_button(v, text):
    W, H = 800, 140
    img = _box(W, H, v, v.get("btn_style", "texto"))
    p = make_painter(img)
    _text_into(p, ("• " if v.get("bullet") else "") + text, v, W, H)
    p.end()
    return img


def g_pause(v, c):
    W, H = 1366, 768
    bg = new_img(W, H)
    p = make_painter(bg)
    _bg_fill(p, W, H, v)
    _text_into(p, v.get("title", ""), v, W, 120, 0, 40, "title_size", "title_color")
    _text_into(p, v.get("subtitle", ""), v, W, 50, 0, 150, "subtitle_size", "subtitle_color")
    p.end()
    out = {"pause-overlay.png": bg}
    for key, name in PAUSE_BUTTONS:
        out[name] = pause_button(v, v[key])
    return out


def g_fail(v, c):
    W, H = 1366, 768
    img = new_img(W, H)
    p = make_painter(img)
    _bg_fill(p, W, H, v)
    p.save()
    p.translate(W * v.get("text_x", 30) / 100, H * v.get("text_y", 45) / 100)
    p.rotate(v.get("text_angle", -65))
    sw = v.get("stripe_width", 230)
    if v.get("stripe", True):
        p.fillRect(QRectF(-1600, -sw / 2, 3200, sw), col(v["stripe_color"], v.get("stripe_opacity", 100)))
    _text_into(p, v.get("big_text", "FAIL"), v, 1100, sw, -550, -sw / 2, "font_size", "text_color", 0.95)
    p.restore()
    _text_into(p, v.get("subtitle", ""), v, W, 60, 0, H - 120, "subtitle_size", "text_color")
    p.end()
    return {"fail-background.png": img}


def _panel(W, H, v):
    img = new_img(W, H)
    p = make_painter(img)
    r = QRectF(3, 3, W - 6, H - 6)
    path = QPainterPath()
    path.addRoundedRect(r, v.get("panel_round", 0) * 2, v.get("panel_round", 0) * 2)
    p.fillPath(path, col(v["panel_color"], v["panel_opacity"]))
    if v.get("panel_border", 0):
        p.setPen(QPen(col(v["panel_border_color"]), v["panel_border"] * 2))
        p.drawPath(path)
    p.end()
    return img


def g_results(v, c):
    """Archivos @2x: 1 unidad de interfaz = 2 px."""
    out = {}
    panel = new_img(1240, 980)
    p = make_painter(panel)
    p.drawImage(QRectF(0, 0, 1240, 140), _panel(1240, 140, v))
    p.drawImage(QRectF(0, 150, 1240, 830), _panel(1240, 830, v))
    _text_into(p, v.get("score_text", "Score"), dict(v, font_size=52), 300, 140, 20, 0)
    p.end()
    out["ranking-panel.png"] = panel
    title = _panel(640, 150, v) if v.get("title_bg", True) else new_img(640, 150)
    p = make_painter(title)
    _text_into(p, v.get("title_text", "Results"), dict(v, font_size=90), 640, 150)
    p.end()
    out["ranking-title.png"] = title
    for name, key, W, H, fs in (("ranking-perfect.png", "perfect_text", 860, 400, 110), ("ranking-accuracy.png", "accuracy_text", 520, 140, 70),
                                ("ranking-maxcombo.png", "combo_text", 520, 140, 70), ("ranking-replay.png", "replay_text", 520, 100, 56)):
        img = _panel(W, H, v) if name == "ranking-perfect.png" else new_img(W, H)
        p = make_painter(img)
        _text_into(p, v.get(key, ""), dict(v, font_size=fs), W, H)
        p.end()
        out[name] = img
    out["ranking-graph.png"] = _panel(1000, 360, v)
    for letter, c1, c2 in RANKS:
        img = new_img(960, 960)
        p = make_painter(img)
        vv = dict(_tv(v), color=v.get(f"letter_{letter}_c1", c1), color2=v.get(f"letter_{letter}_c2", c2),
                  fill_mode="degradado", outline_width=v.get("letter_outline", 8),
                  outline_color=v.get("letter_outline_color", "#ffffff"), font_size=700, shadow=10)
        text = v.get(f"letter_{letter}", "SS" if letter in ("X", "XH") else letter)
        paint_text_path(p, fit_text_path(text, vv, 1.0, 960, 960, "font_size", 700, 0.92), vv, 1.0)
        p.end()
        out[f"ranking-{letter}.png"] = img
    return out


# ======================================================================
# Lienzos libres (barras del menú, perfil, decoraciones…)
# ======================================================================
def draw_layer(p, L, base: Path):
    x, y, w, h = L["x"], L["y"], max(2, L["w"]), max(2, L["h"])
    kind = L["kind"]
    if kind == "shape":
        im = render_shape(w, h, L, 1.0, rot=0)
    elif kind == "text":
        im = render_text(L["text"], L, w, h, 1.0, default_size=48)
    else:
        f = base / L.get("file", "") if L.get("file") else None
        src = QImage(str(f)) if f is not None and f.is_file() else QImage()
        if src.isNull():
            return
        im = src.scaled(int(w), int(h), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    p.save()
    p.translate(x + w / 2, y + h / 2)
    p.rotate(L.get("rot", 0))
    if kind == "image":
        p.setOpacity(max(0.0, min(1.0, L.get("opacity", 100) / 100)))
    p.drawImage(QRectF(-w / 2, -h / 2, w, h), im)
    p.restore()


def render_canvas(cv: dict, base: Path) -> QImage:
    img = new_img(cv["w"], cv["h"])
    p = make_painter(img)
    if cv["bg_mode"] == "sólido":
        p.fillRect(img.rect(), col(cv["bg_color"]))
    elif cv["bg_mode"] == "degradado":
        a = math.radians(cv["bg_angle"])
        R = math.hypot(cv["w"], cv["h"]) / 2
        cx, cy = cv["w"] / 2, cv["h"] / 2
        g = QLinearGradient(cx - math.cos(a) * R, cy - math.sin(a) * R, cx + math.cos(a) * R, cy + math.sin(a) * R)
        g.setColorAt(0, col(cv["bg_color"]))
        g.setColorAt(1, col(cv["bg_color2"]))
        p.fillRect(img.rect(), QBrush(g))
    for L in cv["layers"]:
        if L.get("visible", True):
            draw_layer(p, L, base)
    p.end()
    return img


# ======================================================================
# Efectos: fotogramas generados (sin código o con un script de Python)
# ======================================================================
EFFECT_PRESETS = ["Destello", "Onda", "Estallido de partículas", "Lluvia de estrellas", "Pulso de texto", "Brillo giratorio"]


class Pincel:
    """API sencilla para los efectos con código. Coordenadas de 0 a 1 dentro del lienzo cuadrado."""

    def __init__(self, img: QImage):
        self.img, self.S = img, img.width()
        self.p = make_painter(img)

    def _c(self, color, alpha):
        c = col(color)
        c.setAlphaF(max(0.0, min(1.0, c.alphaF() * alpha)))
        return c

    def circle(self, x, y, r, color="#ffffff", alpha=1.0):
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(self._c(color, alpha))
        self.p.drawEllipse(QPointF(x * self.S, y * self.S), r * self.S, r * self.S)

    def ring(self, x, y, r, width=0.03, color="#ffffff", alpha=1.0):
        self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.setPen(QPen(self._c(color, alpha), max(0.5, width * self.S)))
        self.p.drawEllipse(QPointF(x * self.S, y * self.S), r * self.S, r * self.S)

    def glow(self, x, y, r, color="#ffffff", alpha=1.0):
        g = QRadialGradient(QPointF(x * self.S, y * self.S), max(1.0, r * self.S))
        g.setColorAt(0, self._c(color, alpha))
        g.setColorAt(1, self._c(color, 0))
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(QBrush(g))
        self.p.drawEllipse(QPointF(x * self.S, y * self.S), r * self.S, r * self.S)

    def star(self, x, y, r, points=5, color="#ffffff", alpha=1.0, rot=0.0):
        pts = []
        for k in range(points * 2):
            a = math.radians(rot) + math.pi * k / points - math.pi / 2
            rr = r if k % 2 == 0 else r * 0.45
            pts.append(QPointF((x + math.cos(a) * rr) * self.S, (y + math.sin(a) * rr) * self.S))
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.setBrush(self._c(color, alpha))
        self.p.drawPolygon(QPolygonF(pts))

    def line(self, x1, y1, x2, y2, width=0.02, color="#ffffff", alpha=1.0):
        pen = QPen(self._c(color, alpha), max(0.5, width * self.S))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.p.setPen(pen)
        self.p.drawLine(QPointF(x1 * self.S, y1 * self.S), QPointF(x2 * self.S, y2 * self.S))

    def rect(self, x, y, w, h, color="#ffffff", alpha=1.0):
        self.p.fillRect(QRectF(x * self.S, y * self.S, w * self.S, h * self.S), self._c(color, alpha))

    def text(self, x, y, txt, size=0.2, color="#ffffff", alpha=1.0, font="Arial"):
        v = dict(font=font, font_size=size * self.S, bold=True, color=color, fill_mode="sólido", outline_width=0, glow=0)
        path = text_path(str(txt), v, 1.0, self.S, self.S)
        path.translate((x - 0.5) * self.S, (y - 0.5) * self.S)
        self.p.setPen(Qt.PenStyle.NoPen)
        self.p.fillPath(path, self._c(color, alpha))

    def end(self):
        self.p.end()


def _preset(pz: "Pincel", preset, t, e):
    c1, c2, n = e.get("color", "#ffffff"), e.get("color2", "#53b9ff"), max(1, e.get("amount", 12))
    rnd = random.Random(e.get("seed", 7))
    fade = 1 - t
    if preset == "Destello":
        pz.glow(0.5, 0.5, 0.15 + 0.35 * t, c2, fade)
        pz.glow(0.5, 0.5, 0.08 + 0.2 * t, c1, fade)
    elif preset == "Onda":
        pz.ring(0.5, 0.5, 0.1 + 0.38 * t, 0.05 * fade + 0.005, c1, fade)
        pz.ring(0.5, 0.5, 0.05 + 0.28 * t, 0.02, c2, fade * 0.8)
    elif preset == "Estallido de partículas":
        for k in range(n):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(0.15, 0.45) * (0.2 + 0.8 * t)
            pz.circle(0.5 + math.cos(a) * d, 0.5 + math.sin(a) * d, 0.03 * fade + 0.004, c1 if k % 2 else c2, fade)
    elif preset == "Lluvia de estrellas":
        for k in range(n):
            x0 = rnd.uniform(0.1, 0.9)
            y = (rnd.uniform(-0.3, 0.6) + 0.6 * t)
            pz.star(x0, y, 0.05, 5, c1 if k % 2 else c2, fade, rot=360 * t)
    elif preset == "Pulso de texto":
        s = 0.18 * (1.4 - 0.4 * min(1.0, t * 3))
        pz.text(0.5, 0.5, e.get("text", "300"), s, c1, 1 - max(0.0, t - 0.6) / 0.4)
    else:  # Brillo giratorio
        pz.star(0.5, 0.5, 0.3 * (0.6 + 0.4 * fade), 4, c1, fade, rot=180 * t)
        pz.glow(0.5, 0.5, 0.2, c2, fade * 0.8)


def render_effect(e: dict, t: float, size: int | None = None):
    """Un fotograma del efecto en el instante t (0..1). Devuelve (imagen, error de código o None)."""
    S = size or max(16, int(e.get("size", 256)))
    img = new_img(S, S)
    pz = Pincel(img)
    err = None
    try:
        if e.get("mode") == "code":
            env = {"math": math, "random": random, "__builtins__": {"range": range, "min": min, "max": max, "abs": abs,
                                                                     "len": len, "int": int, "float": float, "round": round}}
            exec(compile(e.get("code", ""), "efecto", "exec"), env)
            if "frame" not in env:
                raise ValueError("El código tiene que definir: def frame(t, p): …")
            env["frame"](t, pz)
        else:
            _preset(pz, e.get("preset", "Destello"), t, e)
    except Exception as ex:          # el error se muestra en el panel; nunca rompe la app
        err = f"{type(ex).__name__}: {ex}"
    pz.end()
    return img, err