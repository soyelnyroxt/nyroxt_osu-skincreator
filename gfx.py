# -*- coding: utf-8 -*-
"""Primitivas gráficas: formas, rellenos, bordes, resplandor y texto.

Todo lo que dibuja un elemento de la skin pasa por render_shape / render_text,
así que cambiar una forma o un estilo en el tema global afecta a todos los modos.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPolygonF,
                           QRadialGradient, QTransform)

SHAPES = ["círculo", "cuadrado redondeado", "píldora", "hexágono", "octágono",
          "diamante", "triángulo", "estrella", "flecha", "chevron", "cruz",
          "corazón", "paralelogramo", "gota"]
FILLS = ["sólido", "degradado", "cristal", "vacío"]
BORDERS = ["sólido", "doble", "punteado"]
DIRECTIONAL = {"flecha", "chevron", "triángulo"}


# ----------------------------------------------------------------------
def new_img(w: float, h: float) -> QImage:
    img = QImage(max(1, int(w)), max(1, int(h)), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    return img


def make_painter(img: QImage) -> QPainter:
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.Antialiasing
                     | QPainter.RenderHint.SmoothPixmapTransform
                     | QPainter.RenderHint.TextAntialiasing)
    return p


def col(s, opacity: float = 100) -> QColor:
    c = QColor(s) if isinstance(s, str) else QColor(s)
    if not c.isValid():
        c = QColor("#ffffff")
    c.setAlphaF(max(0.0, min(1.0, c.alphaF() * opacity / 100.0)))
    return c


def shade(s: str, factor: int = 140) -> str:
    """Versión más oscura (factor>100) o clara (factor<100) de un color."""
    c = QColor(s)
    c = c.darker(factor) if factor >= 100 else c.lighter(int(10000 / max(1, factor)))
    return c.name()


# ----------------------------------------------------------------------
def _poly(pts) -> QPainterPath:
    p = QPainterPath()
    p.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    p.closeSubpath()
    return p


def shape_path(shape: str, r: QRectF, roundness: float = 50, rot: float = 0.0) -> QPainterPath:
    x0, y0, w, h = r.left(), r.top(), r.width(), r.height()
    x1, y1 = x0 + w, y0 + h
    cx, cy = x0 + w / 2, y0 + h / 2
    p = QPainterPath()
    p.setFillRule(Qt.FillRule.WindingFill)
    if shape == "círculo":
        p.addEllipse(r)
    elif shape == "cuadrado redondeado":
        rad = min(w, h) / 2 * max(0.0, min(100.0, roundness)) / 100.0
        p.addRoundedRect(r, rad, rad)
    elif shape == "píldora":
        p.addRoundedRect(r, min(w, h) / 2, min(w, h) / 2)
    elif shape == "hexágono":
        p = _poly([(cx + w / 2 * math.cos(math.radians(a)), cy + h / 2 * math.sin(math.radians(a)))
                   for a in range(-90, 270, 60)])
    elif shape == "octágono":
        p = _poly([(cx + w / 2 * math.cos(math.radians(a)), cy + h / 2 * math.sin(math.radians(a)))
                   for a in [i * 45 + 22.5 for i in range(8)]])
    elif shape == "diamante":
        p = _poly([(cx, y0), (x1, cy), (cx, y1), (x0, cy)])
    elif shape == "triángulo":
        p = _poly([(cx, y0), (x1, y1), (x0, y1)])
    elif shape == "estrella":
        pts = []
        for i in range(10):
            a = math.radians(-90 + i * 36)
            f = 1.0 if i % 2 == 0 else 0.45
            pts.append((cx + w / 2 * f * math.cos(a), cy + h / 2 * f * math.sin(a)))
        p = _poly(pts)
    elif shape == "flecha":
        hb = y0 + h * 0.52
        p = _poly([(cx, y0), (x1, hb), (cx + w * 0.2, hb), (cx + w * 0.2, y1),
                   (cx - w * 0.2, y1), (cx - w * 0.2, hb), (x0, hb)])
    elif shape == "chevron":
        p = _poly([(cx, y0), (x1, y0 + h * 0.5), (x1, y1), (cx, y0 + h * 0.5),
                   (x0, y1), (x0, y0 + h * 0.5)])
    elif shape == "cruz":
        a, b = 0.33, 0.67
        p = _poly([(x0 + w * a, y0), (x0 + w * b, y0), (x0 + w * b, y0 + h * a), (x1, y0 + h * a),
                   (x1, y0 + h * b), (x0 + w * b, y0 + h * b), (x0 + w * b, y1), (x0 + w * a, y1),
                   (x0 + w * a, y0 + h * b), (x0, y0 + h * b), (x0, y0 + h * a), (x0 + w * a, y0 + h * a)])
    elif shape == "corazón":
        rr = w * 0.27
        p.addEllipse(QPointF(cx - rr, y0 + rr * 1.05), rr, rr)
        p.addEllipse(QPointF(cx + rr, y0 + rr * 1.05), rr, rr)
        p.addPath(_poly([(x0 + w * 0.03, y0 + rr * 1.5), (x1 - w * 0.03, y0 + rr * 1.5), (cx, y1)]))
    elif shape == "paralelogramo":
        s = w * 0.2
        p = _poly([(x0 + s, y0), (x1, y0), (x1 - s, y1), (x0, y1)])
    elif shape == "gota":
        rr = w * 0.36
        p.addEllipse(QPointF(cx, y1 - rr), rr, rr)
        p.addPath(_poly([(cx, y0), (cx + rr * 0.95, y1 - rr * 1.35), (cx - rr * 0.95, y1 - rr * 1.35)]))
    else:
        p.addEllipse(r)
    if rot:
        t = QTransform()
        t.translate(cx, cy)
        t.rotate(rot)
        t.translate(-cx, -cy)
        p = t.map(p)
    return p


# ----------------------------------------------------------------------
def paint_path(p: QPainter, path: QPainterPath, rect: QRectF, v: dict, k: float = 1.0,
               parts=("shadow", "glow", "fill", "border")):
    bw = v.get("border_width", 0) * k
    glow = v.get("glow", 0) * k
    shadow = v.get("shadow", 0) * k
    if "shadow" in parts and shadow > 0:
        sp = QPainterPath(path)
        sp.translate(0, shadow * 0.6)
        p.fillPath(sp, QColor(0, 0, 0, 95))
    if "glow" in parts and glow > 0:
        gc = col(v.get("glow_color", "#53b9ff"))
        n = 8
        for i in range(n, 0, -1):
            c = QColor(gc)
            c.setAlphaF(min(1.0, gc.alphaF() * 0.55 * (1 - (i - 1) / n) ** 2))
            pen = QPen(c, bw + glow * 2 * i / n)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, pen)
    mode = v.get("fill_mode", "sólido")
    if "fill" in parts and mode != "vacío":
        op = v.get("opacity", 100)
        c1 = col(v.get("color", "#ffffff"), op)
        c2 = col(v.get("color2", v.get("color", "#ffffff")), op)
        if mode == "degradado":
            a = math.radians(v.get("grad_angle", 90))
            R = max(rect.width(), rect.height()) / 2
            c = rect.center()
            g = QLinearGradient(c.x() - math.cos(a) * R, c.y() - math.sin(a) * R,
                                c.x() + math.cos(a) * R, c.y() + math.sin(a) * R)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.fillPath(path, QBrush(g))
        elif mode == "cristal":
            base = QColor(c1)
            base.setAlphaF(base.alphaF() * 0.6)
            p.fillPath(path, QBrush(base))
            p.save()
            p.setClipPath(path)
            g = QLinearGradient(0, rect.top(), 0, rect.center().y())
            g.setColorAt(0, QColor(255, 255, 255, 170))
            g.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(rect, QBrush(g))
            p.restore()
        else:
            p.fillPath(path, QBrush(c1))
    if "border" in parts and bw > 0:
        style = v.get("border_style", "sólido")
        pen = QPen(col(v.get("border_color", "#ffffff")), bw)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if style == "punteado":
            pen.setStyle(Qt.PenStyle.DashLine)
        p.strokePath(path, pen)
        if style == "doble":
            t = QTransform()
            c = rect.center()
            t.translate(c.x(), c.y())
            t.scale(0.78, 0.78)
            t.translate(-c.x(), -c.y())
            pen2 = QPen(col(v.get("border_color", "#ffffff")), max(1.0, bw * 0.5))
            p.strokePath(t.map(path), pen2)


def margin_for(v: dict, k: float) -> float:
    return v.get("border_width", 0) * k / 2 + v.get("glow", 0) * k + v.get("shadow", 0) * k + 2


def render_shape(W: float, H: float, v: dict, k: float = 1.0, shape: str | None = None,
                 rot: float | None = None) -> QImage:
    W, H = max(8, int(W)), max(8, int(H))
    img = new_img(W, H)
    p = make_painter(img)
    m = margin_for(v, k)
    rect = QRectF(m, m, W - 2 * m, H - 2 * m)
    if rect.width() < 2 or rect.height() < 2:
        rect = QRectF(1, 1, W - 2, H - 2)
    path = shape_path(shape or v.get("shape", "círculo"), rect, v.get("roundness", 50),
                      v.get("rotation", 0) if rot is None else rot)
    paint_path(p, path, rect, v, k)
    p.end()
    return img


def ring_vals(v: dict) -> dict:
    """Valores de estilo para elementos que son solo un aro (overlay, approach...)."""
    d = dict(v)
    d["fill_mode"] = "vacío"
    d["border_width"] = v.get("width", v.get("border_width", 6))
    d["border_color"] = v.get("color", "#ffffff")
    return d


# ----------------------------------------------------------------------
def text_path(text: str, v: dict, k: float, W: float, H: float, size_key: str = "font_size",
              default_size: int = 56) -> QPainterPath:
    font = QFont(v.get("font", "Arial"))
    font.setPixelSize(max(4, int(v.get(size_key, default_size) * k)))
    font.setBold(bool(v.get("bold", True)))
    font.setItalic(bool(v.get("italic", False)))
    path = QPainterPath()
    path.addText(0, 0, font, text)
    br = path.boundingRect()
    path.translate(W / 2 - br.center().x(), H / 2 - br.center().y())
    return path


def paint_text_path(p: QPainter, path: QPainterPath, v: dict, k: float):
    br = path.boundingRect()
    sh = v.get("shadow", 0) * k
    if sh > 0:
        sp = QPainterPath(path)
        sp.translate(sh * 0.5, sh * 0.7)
        p.fillPath(sp, QColor(0, 0, 0, 120))
    glow = v.get("glow", 0) * k
    if glow > 0:
        gc = col(v.get("glow_color", "#53b9ff"))
        for i in range(6, 0, -1):
            c = QColor(gc)
            c.setAlphaF(min(1.0, gc.alphaF() * 0.5 * (1 - (i - 1) / 6) ** 2))
            pen = QPen(c, glow * 2 * i / 6)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.strokePath(path, pen)
    ow = v.get("outline_width", 0) * k
    if ow > 0:
        pen = QPen(col(v.get("outline_color", "#202020")), ow * 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.strokePath(path, pen)
    if v.get("fill_mode") == "degradado":
        g = QLinearGradient(0, br.top(), 0, br.bottom())
        g.setColorAt(0, col(v.get("color", "#ffffff")))
        g.setColorAt(1, col(v.get("color2", "#ffffff")))
        p.fillPath(path, QBrush(g))
    else:
        p.fillPath(path, QBrush(col(v.get("color", "#ffffff"))))


def render_text(text: str, v: dict, W: float, H: float, k: float = 1.0, **kw) -> QImage:
    img = new_img(W, H)
    p = make_painter(img)
    paint_text_path(p, text_path(text, v, k, W, H, **kw), v, k)
    p.end()
    return img


def radial_glow(S: int, color: str, opacity: float = 100, hard: float = 0.0) -> QImage:
    img = new_img(S, S)
    p = make_painter(img)
    c0 = col(color, opacity)
    c1 = QColor(c0)
    c1.setAlpha(0)
    g = QRadialGradient(S / 2, S / 2, S / 2)
    g.setColorAt(0, c0)
    g.setColorAt(max(0.0, min(0.95, hard)), c0)
    g.setColorAt(1, c1)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QRectF(0, 0, S, S))
    p.end()
    return img