#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nyroxt's osu! skin creator  v3
==============================
    pip install -r requirements.txt
    python main.py
"""
from __future__ import annotations

import json
import math
import random
import re
import shutil
import sys
import zipfile
from collections import deque
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QUrl, QMimeData, QPointF, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QBitmap, QDesktopServices, QIcon, QRegion, QPolygonF, QTransform, QBrush, QColor, QFont, QFontDatabase, QImage, QImageReader,
                           QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QCheckBox, QMenu, QPlainTextEdit, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter,
                               QStackedWidget, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget)

import core
import i18n
from i18n import tr
import presence
import gens
from core import (ACTIONS, ASPECTS, CANVAS_BY_NAME, CANVAS_PRESETS, CANVAS_SPECS, FILE_PROPS, FIXED_NAMES, FIXED_SECTIONS, ELEMENT_BY_ID, ELEMENTS, LAYER_SPECS, MODES,
                  Project, export_osk, mania_layout, stage_side_width, new_canvas, new_layer, safe_name, validate)

APP_NAME = "nyroxt's osu! skin creator"
APP_VERSION = "1.0"      # súbelo cada vez que publiques una versión (Release) en GitHub
REPO = "soyelnyroxt/nyroxt_osu-skincreator"
BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"

SCENES = [("std", "Gameplay · osu!standard"), ("taiko", "Gameplay · osu!taiko"),
          ("catch", "Gameplay · osu!catch"), ("mania", "Gameplay · osu!mania"),
          ("menu", "Selección de canciones"), ("pause", "Menú de pausa"),
          ("fail", "Pantalla de fallo"), ("results", "Resultados"),
          ("home", "Menú principal (imagen del menú)"), ("mods", "Selección de mods"),
          ("modes", "Selección de modo"), ("dialogs", "Botones de diálogo"), ("ui", "Interfaz de juego (UI)"),
          ("effects", "Efectos")]
LOOPS = {"std": 6600, "taiko": 6800, "catch": 7000, "mania": 8000, "menu": 1000, "canvas": 1000}
ACCENT = QColor("#ff4f9d")
UI_SCENES = ("menu", "pause", "fail", "results", "home", "mods", "modes", "dialogs", "ui", "effects")


# ======================================================================
# Widgets de edición
# ======================================================================
class IntEdit(QWidget):
    changed = Signal(int)

    def __init__(self, lo, hi, val, unit=""):
        super().__init__()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(lo, hi)
        self.spin = QSpinBox()
        self.spin.setRange(lo, hi)
        if unit:
            self.spin.setSuffix(" " + unit)
        self.slider.setValue(val)
        self.spin.setValue(val)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _from_slider(self, v):
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.changed.emit(v)

    def _from_spin(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(v)
        self.slider.blockSignals(False)
        self.changed.emit(v)


class ColorEdit(QPushButton):
    changed = Signal(str)

    def __init__(self, value: str, title: str):
        super().__init__()
        self.value, self.title = value, title
        self._paint()
        self.clicked.connect(self._pick)

    def _paint(self):
        c = QColor(self.value)
        lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        self.setText(c.name(QColor.NameFormat.HexArgb).upper() if c.alpha() < 255 else c.name().upper())
        self.setStyleSheet(f"background:{c.name()}; color:{'#000' if lum > 140 else '#fff'}; "
                           "border:1px solid #4a5060; padding:4px;")

    def _pick(self, _=False):
        c = QColorDialog.getColor(QColor(self.value), self, self.title, QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if c.isValid():
            self.value = c.name(QColor.NameFormat.HexArgb) if c.alpha() < 255 else c.name()
            self._paint()
            self.changed.emit(self.value)


def make_editor(spec, value, cb, font_cb=None) -> QWidget:
    kind = spec["kind"]
    if kind == "color":
        w = ColorEdit(value, spec["label"])
        w.changed.connect(cb)
    elif kind == "int":
        w = IntEdit(spec["min"], spec["max"], int(value), spec.get("unit", ""))
        w.changed.connect(cb)
    elif kind == "bool":
        w = QCheckBox()
        w.setChecked(bool(value))
        w.toggled.connect(cb)
    elif kind == "choice":
        w = QComboBox()
        for o in spec["options"]:
            w.addItem(tr(o), o)               # se ve traducido; el valor guardado no cambia
        w.setCurrentIndex(max(0, w.findData(value)))
        w.currentIndexChanged.connect(lambda i, ww=w: cb(ww.itemData(i)))
    elif kind == "font":
        box = QFontComboBox()
        box.setCurrentFont(QFont(value))
        box.currentFontChanged.connect(lambda f: cb(f.family()))
        if font_cb is None:
            return box
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(box, 1)
        add = QPushButton("＋")
        add.setToolTip("Importar fuente (.ttf / .otf)")
        add.setMaximumWidth(34)
        add.clicked.connect(font_cb)
        row.addWidget(add)
    elif kind == "image":          # devuelve la ruta elegida; el panel la copia dentro del proyecto
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        pick = QPushButton(Path(value).name if value else "Elegir imagen…")
        pick.setToolTip("PNG con transparencia: su silueta será la forma")

        def choose():
            f, _ = QFileDialog.getOpenFileName(w, "Imagen para la forma", "", "Imágenes (*.png *.jpg *.jpeg *.webp *.gif)")
            if f:
                pick.setText(Path(f).name)
                cb(f)
        pick.clicked.connect(choose)
        clear = QPushButton("✕")
        clear.setMaximumWidth(34)
        clear.setToolTip("Quitar imagen")
        clear.clicked.connect(lambda: (pick.setText("Elegir imagen…"), cb("")))
        row.addWidget(pick, 1)
        row.addWidget(clear)
    else:
        w = QLineEdit(str(value))
        w.textChanged.connect(cb)
    return w


def fill_form(form: QFormLayout, specs, getter, setter, font_cb=None, on_action=None):
    """Rellena un QFormLayout con los editores de una lista de propiedades."""
    for spec in specs:
        if spec["kind"] == "header":
            lab = QLabel(tr(spec["label"]))
            lab.setObjectName("sect")
            form.addRow(lab)
        elif spec["kind"] == "action":
            b = QPushButton(tr(spec["label"]))
            b.clicked.connect(lambda _=False, a=spec["action"]: on_action(a))
            form.addRow(b)
        else:
            form.addRow(tr(spec["label"]), make_editor(spec, getter(spec["key"]),
                                                   lambda v, s=spec: setter(s, v), font_cb))


def clear_form(form: QFormLayout):
    while form.rowCount():
        form.removeRow(0)


# ======================================================================
# Panel de propiedades de elementos
# ======================================================================
class PropertiesPanel(QWidget):
    edited = Signal(str)
    structure_changed = Signal()

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.eid: str | None = None
        self.custom: str | None = None
        self.anim: str | None = None
        self.file: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.title = QLabel("Selecciona un elemento")
        self.title.setObjectName("h2")
        self.title.setWordWrap(True)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setObjectName("muted")
        self.files = QLabel()
        self.files.setWordWrap(True)
        self.files.setObjectName("muted")
        self.thumb = QLabel()
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.enabled = QCheckBox("Mostrar en el juego (si lo quitas se exporta vacío: no se ve nada)")
        self.enabled.toggled.connect(self._on_enabled)
        self.hidden = QCheckBox("Ocultar: exportar transparente (el juego no muestra el original)")
        self.hidden.toggled.connect(self._on_hidden)
        self.ov_box = QWidget()
        ol = QVBoxLayout(self.ov_box)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(QLabel("Imágenes propias (reemplazan a la generada):"))
        self.ov_combo = QComboBox()
        ol.addWidget(self.ov_combo)
        self.ov_size = QLabel()
        self.ov_size.setObjectName("muted")
        self.ov_size.setWordWrap(True)
        ol.addWidget(self.ov_size)
        self.ov_combo.currentIndexChanged.connect(self._ov_size_text)
        orow = QHBoxLayout()
        b1 = QPushButton("Reemplazar con mi imagen…")
        b1.clicked.connect(self._ov_set)
        b2 = QPushButton("Quitar reemplazo")
        b2.clicked.connect(self._ov_clear)
        orow.addWidget(b1)
        orow.addWidget(b2)
        ol.addLayout(orow)
        self.host = QWidget()
        self.form = QFormLayout(self.host)
        self.form.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.host)
        self.reset_btn = QPushButton("Restaurar valores")
        self.reset_btn.clicked.connect(self._on_reset)
        self.remove_btn = QPushButton("Quitar")
        self.remove_btn.clicked.connect(self._remove)
        for w in (self.title, self.desc, self.files, self.thumb, self.enabled, self.hidden, self.ov_box):
            lay.addWidget(w)
        lay.addWidget(scroll, 1)
        lay.addWidget(self.reset_btn)
        lay.addWidget(self.remove_btn)

    def _mode(self, gen: bool, remove: bool):
        self.enabled.setVisible(False)
        self.hidden.setVisible(gen)
        self.ov_box.setVisible(gen)
        self.reset_btn.setVisible(gen)
        self.remove_btn.setVisible(remove)

    # ---- elemento ----------------------------------------------------
    def show_element(self, project, eid, file=None):
        self.project, self.eid, self.custom, self.anim = project, eid, None, None
        self.file = file
        clear_form(self.form)
        self._mode(False, False)
        if project is None or eid is None:
            self.title.setText("Selecciona un elemento")
            return
        el = ELEMENT_BY_ID[eid]
        gen = eid in gens_ids()
        self.title.setText(el["name"])
        self.desc.setText(el["desc"] + ("\nSe exporta como @2x (1 unidad de interfaz = 2 px)." if el.get("hd") else ""))
        self.files.setText(tr("Archivos:") + " " + ", ".join(el["files"]) if el["files"] else "")
        self._mode(gen, False)
        self.enabled.setVisible(el["toggle"])
        self.reset_btn.setVisible(True)
        self.sync_enabled()
        if gen:
            self.hidden.blockSignals(True)
            self.hidden.setChecked(project.get(eid, "hidden"))
            self.hidden.blockSignals(False)
            self._fill_overrides()
        props = el["props"]
        if file:          # solo este objeto: sus propiedades + posición, tamaño y bloqueo
            keys = FILE_PROPS.get(eid, {}).get(file)
            if keys:
                props = [sec(f"Solo «{file}»")] + [el["specs"][k] for k in keys if k in el["specs"]]
            self.title.setText(f"{el['name']} · {file}")
            i = self.ov_combo.findData(file)
            if i >= 0:
                self.ov_combo.setCurrentIndex(i)
            self._layout_rows(file)
        fill_form(self.form, props, lambda k: project.get(eid, k), self._commit,
                  font_cb=self.import_font, on_action=self._run_action)
        if file:
            b = QPushButton("Ver todas las opciones del elemento")
            b.clicked.connect(lambda: self.show_element(self.project, self.eid))
            self.form.addRow(b)
        self._update_thumb()

    def _layout_rows(self, file):
        pr, eid = self.project, self.eid
        lay = {"dx": 0, "dy": 0, "scale": 100, "locked": False, **pr.lay(file)}
        head = QLabel("Posición y tamaño (solo este objeto)")
        head.setObjectName("sect")
        self.form.addRow(head)
        for key, label, lo, hi, unit in (("dx", "Mover en X", -1366, 1366, "px"), ("dy", "Mover en Y", -768, 768, "px"),
                                         ("scale", "Tamaño", 10, 400, "%")):
            w = IntEdit(lo, hi, int(lay[key]), unit)
            w.changed.connect(lambda v, k=key: (pr.set_lay(eid, file, **{k: v}), self.edited.emit(eid)))
            self.form.addRow(label, w)
        lock = QCheckBox("Bloqueado (no se mueve ni se selecciona por error)")
        lock.setChecked(bool(lay["locked"]))
        lock.toggled.connect(lambda v: (pr.set_lay(eid, file, locked=v), self.edited.emit(eid)))
        self.form.addRow(lock)

    def sync_enabled(self):
        if self.project and self.eid:
            self.enabled.blockSignals(True)
            self.enabled.setChecked(self.project.get(self.eid, "enabled"))
            self.enabled.blockSignals(False)

    def _commit(self, spec, value):
        if spec["kind"] == "image" and value:
            pr = self.project
            (pr.path / "assets").mkdir(parents=True, exist_ok=True)
            dest = pr.path / "assets" / f"shape_{self.eid}_{spec['key']}_{safe_name(Path(value).name, 'forma.png')}"
            if Path(value).resolve() != dest.resolve():
                shutil.copyfile(value, dest)
            value = str(dest.relative_to(pr.path))
        self.project.set(self.eid, spec["key"], value)
        self._update_thumb()
        self.edited.emit(self.eid)

    def _run_action(self, name):
        if self.project is None:
            return
        if name == "import_font":
            self.import_font()
            return
        ACTIONS[name](self.project)
        self.show_element(self.project, self.eid)
        self.edited.emit("theme")
        self.structure_changed.emit()

    def import_font(self):
        if self.project is None:
            return
        f, _ = QFileDialog.getOpenFileName(self, "Importar fuente", "", "Fuentes (*.ttf *.otf)")
        if not f:
            return
        pr = self.project
        dest_dir = pr.path / "fonts"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / Path(f).name
        shutil.copyfile(f, dest)
        fid = QFontDatabase.addApplicationFont(str(dest))
        fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
        if not fams:
            QMessageBox.warning(self, APP_NAME, "No se pudo cargar esa fuente.")
            return
        rel = str(dest.relative_to(pr.path))
        if rel not in pr.fonts:
            pr.fonts.append(rel)
        pr.set("theme", "font", fams[0])
        QMessageBox.information(self, APP_NAME, f"Fuente «{fams[0]}» importada y aplicada al tema global.\n"
                                "Elígela en la tipografía de cualquier elemento o capa de texto.")
        if self.eid:
            self.show_element(pr, self.eid)
        self.edited.emit("theme")
        self.structure_changed.emit()

    def _on_enabled(self, checked):
        if self.project and self.eid:
            self.project.set(self.eid, "enabled", checked)
            self.edited.emit(self.eid)

    def _on_hidden(self, checked):
        if self.project and self.eid:
            self.project.set(self.eid, "hidden", checked)
            self._update_thumb()
            self.edited.emit(self.eid)

    def _on_reset(self):
        if self.project and self.eid:
            self.project.reset_element(self.eid)
            self.show_element(self.project, self.eid)
            self.edited.emit(self.eid)

    # ---- imágenes propias por archivo -------------------------------------
    def _fill_overrides(self):
        pr = self.project
        self.ov_combo.clear()
        done = pr.overrides.get(self.eid, {})
        for name in pr.images(self.eid):
            self.ov_combo.addItem(("★ " if name in done else "") + name, name)

    def _ov_size_text(self, _i=0):
        name = self.ov_combo.currentData()
        img = self.project.images(self.eid).get(name) if (self.project and self.eid and name) else None
        if img is None or img.isNull():
            self.ov_size.setText("")
            return
        hd = ELEMENT_BY_ID[self.eid].get("hd")
        w, h = img.width(), img.height()
        self.ov_size.setText(tr("Tamaño recomendado:") + f" {w} × {h} px" + (" " + tr("(ya es @2x)") if hd else
                             f"  ·  @2x: {w * 2} × {h * 2} px") + ". " + tr("Si es más grande se encoge sin deformarse."))

    def _ov_set(self):
        name = self.ov_combo.currentData()
        if not (self.project and self.eid and name):
            return
        f, _ = QFileDialog.getOpenFileName(self, f"Imagen para {name}", "", "Imágenes (*.png *.jpg *.jpeg)")
        if not f:
            return
        pr = self.project
        (pr.path / "assets").mkdir(parents=True, exist_ok=True)
        dest = pr.path / "assets" / f"ov_{self.eid}_{name}"
        shutil.copyfile(f, dest)          # QImage detecta el formato por el contenido
        pr.set_override(self.eid, name, str(dest.relative_to(pr.path)))
        self._fill_overrides()
        self._update_thumb()
        self.edited.emit(self.eid)

    def _ov_clear(self):
        name = self.ov_combo.currentData()
        if self.project and self.eid and name:
            self.project.set_override(self.eid, name, None)
            self._fill_overrides()
            self._update_thumb()
            self.edited.emit(self.eid)

    # ---- recursos propios y animaciones --------------------------------------
    def show_custom(self, project, name):
        self.project, self.eid, self.custom, self.anim = project, None, name, None
        clear_form(self.form)
        self._mode(False, True)
        self.remove_btn.setText("Quitar este recurso")
        self.title.setText(name)
        self.desc.setText("Recurso propio: se exporta tal cual con este nombre de archivo (por ejemplo "
                          "menu-background.jpg, pause-overlay.png, welcome_text.png…).")
        self.files.setText("")
        le = QLineEdit(name)
        le.editingFinished.connect(lambda: self._rename_custom(le.text()))
        self.form.addRow("Nombre del archivo", le)
        img = project.custom_image(name)
        self._show_image(img)

    def show_anim(self, project, name):
        self.project, self.eid, self.custom, self.anim = project, None, None, name
        clear_form(self.form)
        self._mode(False, True)
        self.remove_btn.setText("Quitar esta animación")
        an = next(a for a in project.anims if a["name"] == name)
        self.title.setText(f"Animación «{name}»")
        self.desc.setText(f"{len(an['frames'])} fotogramas separados del GIF. Se exportan como {name}-0.png … "
                          f"{name}-{len(an['frames']) - 1}.png y skin.ini recibe AnimationFramerate. "
                          "osu! solo anima los elementos que lo admiten (cursor, hitbursts, ranking, etc.): "
                          "usa como nombre base el del elemento que quieres animar.")
        self.files.setText("")
        le = QLineEdit(name)
        le.editingFinished.connect(lambda: self._rename_anim(le.text()))
        self.form.addRow("Nombre base", le)
        fps = IntEdit(1, 60, an["fps"], "fps")
        fps.changed.connect(lambda v: (an.__setitem__("fps", v), setattr(project, "dirty", True), self.edited.emit("")))
        self.form.addRow("Fotogramas por segundo", fps)
        f = project.path / an["frames"][0] if an["frames"] else None
        self._show_image(QImage(str(f)) if f is not None and f.is_file() else None)

    def _show_image(self, img):
        if img is not None and not img.isNull():
            self.thumb.setPixmap(QPixmap.fromImage(img).scaled(300, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                                               Qt.TransformationMode.SmoothTransformation))
            self.thumb.setVisible(True)
        else:
            self.thumb.setVisible(False)

    def _rename_custom(self, new):
        pr, new = self.project, safe_name(new, "")
        if not pr or not self.custom or not new or new == self.custom:
            return
        if any(c["name"] == new for c in pr.customs):
            QMessageBox.warning(self, APP_NAME, "Ya existe un recurso con ese nombre.")
            return
        for c in pr.customs:
            if c["name"] == self.custom:
                c["name"] = new
        pr.dirty = True
        self.custom = new
        self.structure_changed.emit()

    def _rename_anim(self, new):
        pr, new = self.project, safe_name(new, "")
        if not pr or not self.anim or not new or new == self.anim:
            return
        for a in pr.anims:
            if a["name"] == self.anim:
                a["name"] = new
        pr.dirty = True
        self.anim = new
        self.structure_changed.emit()

    def _remove(self):
        pr = self.project
        if not pr:
            return
        if self.custom:
            pr.customs = [c for c in pr.customs if c["name"] != self.custom]
        elif self.anim:
            pr.anims = [a for a in pr.anims if a["name"] != self.anim]
        pr.dirty = True
        self.custom = self.anim = None
        self.structure_changed.emit()

    def _update_thumb(self):
        imgs = list(self.project.images(self.eid).values()) if self.project and self.eid else []
        if not imgs:
            self.thumb.setVisible(False)
            return
        imgs = imgs[:24]
        th, gap, maxw = 48, 6, 320
        scaled = [i.scaledToHeight(th, Qt.TransformationMode.SmoothTransformation) for i in imgs]
        rows, cur, x = [], [], gap
        for i in scaled:
            if x + i.width() + gap > maxw and cur:
                rows.append(cur)
                cur, x = [], gap
            cur.append(i)
            x += i.width() + gap
        rows.append(cur)
        pm = QPixmap(maxw, len(rows) * (th + gap) + gap)
        pm.fill(QColor("#2a2d36"))
        p = QPainter(pm)
        y = gap
        for row in rows:
            x = gap
            for i in row:
                p.drawImage(x, y, i)
                x += i.width() + gap
            y += th + gap
        p.end()
        self.thumb.setPixmap(pm)
        self.thumb.setVisible(True)


def gens_ids():
    from core import GENERATORS
    return GENERATORS


def sec(label):
    return dict(key=None, label=label, kind="header", default=None)


# ======================================================================
# Panel de lienzos
# ======================================================================
class CanvasPanel(QWidget):
    changed = Signal()
    layer_selected = Signal(str)
    structure_changed = Signal()

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.cv: dict | None = None
        self.sel: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.title = QLabel("Lienzo")
        self.title.setObjectName("h2")
        self.hint = QLabel("Arrastra las capas en el visualizador para moverlas; el cuadro de la esquina las "
                           "redimensiona; Supr borra la capa seleccionada.")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("muted")
        self.host = QWidget()
        self.cform = QFormLayout(self.host)
        self.cform.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setMaximumHeight(170)
        self.list.currentRowChanged.connect(self._row)
        r1, r2 = QHBoxLayout(), QHBoxLayout()
        for text, fn in (("＋ Forma", lambda: self.add_layer("shape")), ("＋ Texto", lambda: self.add_layer("text")),
                         ("＋ Imagen…", lambda: self.add_layer("image"))):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: f())
            r1.addWidget(b)
        for text, fn in (("Duplicar", self.dup_layer), ("▲", lambda: self.move_layer(-1)), ("▼", lambda: self.move_layer(1)),
                         ("Eliminar", self.del_layer)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, f=fn: f())
            r2.addWidget(b)
        self.lhost = QWidget()
        self.lform = QFormLayout(self.lhost)
        self.lform.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        il.addWidget(self.host)
        il.addWidget(QLabel("Capas (de abajo hacia arriba)"))
        il.addWidget(self.list)
        il.addLayout(r1)
        il.addLayout(r2)
        il.addWidget(self.lhost)
        il.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(inner)
        self.remove_btn = QPushButton("Eliminar este lienzo")
        self.remove_btn.clicked.connect(self._remove_canvas)
        lay.addWidget(self.title)
        lay.addWidget(self.hint)
        lay.addWidget(scroll, 1)
        lay.addWidget(self.remove_btn)

    def show_canvas(self, project, cv, sel=None):
        self.project, self.cv = project, cv
        self.title.setText(f"Lienzo · {cv['name']}")
        self.host.setVisible(True)
        self.remove_btn.setVisible(True)
        clear_form(self.cform)
        fill_form(self.cform, CANVAS_SPECS, lambda k: cv[k], self._set_canvas)
        self._fill_list(sel)

    def show_objects(self, project, scene, w, h):
        """Modo «objetos libres de la escena»: mismas capas, sin ajustes de lienzo."""
        cv = dict(id="scene:" + scene, name="Objetos libres", w=int(w), h=int(h), hd=False,
                  layers=project.scene_objs.setdefault(scene, []))
        self.project, self.cv = project, cv
        self.title.setText("Objetos libres de esta escena")
        self.host.setVisible(False)
        self.remove_btn.setVisible(False)
        self._fill_list()

    def _set_canvas(self, spec, value):
        self.cv[spec["key"]] = Project._coerce(spec, value)
        self.project.dirty = True
        if spec["key"] == "name":
            self.title.setText(f"Lienzo · {self.cv['name']}")
            self.structure_changed.emit()
        self.changed.emit()

    def _fill_list(self, sel=None):
        self.list.blockSignals(True)
        self.list.clear()
        for L in self.cv["layers"]:
            it = QListWidgetItem(("" if L.get("visible", True) else "(oculta) ") + L.get("name", L["kind"]))
            it.setData(Qt.ItemDataRole.UserRole, L["id"])
            self.list.addItem(it)
        self.list.blockSignals(False)
        ids = [L["id"] for L in self.cv["layers"]]
        row = ids.index(sel) if sel in ids else (len(ids) - 1 if ids else -1)
        self.list.setCurrentRow(row)
        self._row(row)

    def layer(self):
        return next((L for L in self.cv["layers"] if L["id"] == self.sel), None) if self.cv else None

    def select(self, lid):
        if lid == self.sel:
            return
        ids = [L["id"] for L in self.cv["layers"]]
        if lid in ids:
            self.list.blockSignals(True)
            self.list.setCurrentRow(ids.index(lid))
            self.list.blockSignals(False)
        self._row(ids.index(lid) if lid in ids else -1, emit=False)

    def _row(self, row, emit=True):
        clear_form(self.lform)
        if not self.cv or row < 0 or row >= len(self.cv["layers"]):
            self.sel = None
            if emit:
                self.layer_selected.emit("")
            return
        L = self.cv["layers"][row]
        self.sel = L["id"]
        self.refresh_layer()
        if emit:
            self.layer_selected.emit(L["id"])

    def refresh_layer(self):
        clear_form(self.lform)
        L = self.layer()
        if L is None:
            return
        specs = LAYER_SPECS["common"] + LAYER_SPECS[L["kind"]]
        fill_form(self.lform, specs, lambda k: L.get(k), self._set_layer, font_cb=None)
        if L["kind"] == "image":
            b = QPushButton("Cambiar imagen…")
            b.clicked.connect(self._pick_image)
            self.lform.addRow(b)

    def _set_layer(self, spec, value):
        L = self.layer()
        if L is None:
            return
        L[spec["key"]] = Project._coerce(spec, value)
        self.project.dirty = True
        if spec["key"] in ("name", "visible"):
            it = self.list.currentItem()
            if it:
                it.setText(("" if L.get("visible", True) else "(oculta) ") + L.get("name", L["kind"]))
        self.changed.emit()

    def _pick_image(self):
        L = self.layer()
        if L is None:
            return
        f, _ = QFileDialog.getOpenFileName(self, "Imagen para la capa", "", "Imágenes (*.png *.jpg *.jpeg *.gif)")
        if not f:
            return
        pr = self.project
        (pr.path / "assets").mkdir(parents=True, exist_ok=True)
        dest = pr.path / "assets" / f"layer_{L['id']}_{safe_name(Path(f).name, 'img.png')}"
        shutil.copyfile(f, dest)
        L["file"] = str(dest.relative_to(pr.path))
        pr.dirty = True
        self.changed.emit()

    def add_layer(self, kind):
        if not self.cv:
            return
        over = {}
        if kind == "image":
            f, _ = QFileDialog.getOpenFileName(self, "Imagen para la capa", "", "Imágenes (*.png *.jpg *.jpeg *.gif)")
            if not f:
                return
            pr = self.project
            (pr.path / "assets").mkdir(parents=True, exist_ok=True)
            L0 = new_layer("image", self.cv)
            dest = pr.path / "assets" / f"layer_{L0['id']}_{safe_name(Path(f).name, 'img.png')}"
            shutil.copyfile(f, dest)
            img = QImage(str(dest))
            if not img.isNull():
                k = min(1.0, self.cv["w"] / 2 / img.width(), self.cv["h"] / img.height())
                L0.update(w=max(2, int(img.width() * k)), h=max(2, int(img.height() * k)))
                L0.update(x=self.cv["w"] // 2 - L0["w"] // 2, y=self.cv["h"] // 2 - L0["h"] // 2)
            L0["file"] = str(dest.relative_to(pr.path))
            L = L0
        else:
            if kind == "text":
                over["font"] = self.project.theme()["font"]
            L = new_layer(kind, self.cv, **over)
        self.cv["layers"].append(L)
        self.project.dirty = True
        self._fill_list(L["id"])
        self.changed.emit()

    def place_image(self, rel, cx=None, cy=None):
        """Añade una imagen de la carpeta global como capa libre (centrada en cx, cy si se indican)."""
        if not self.cv:
            return
        img = QImage(str(self.project.path / rel))
        w, h = (img.width(), img.height()) if not img.isNull() else (200, 200)
        k = min(1.0, self.cv["w"] / 2 / w, self.cv["h"] / 2 / h)
        w, h = max(2, int(w * k)), max(2, int(h * k))
        cx = self.cv["w"] / 2 if cx is None else cx
        cy = self.cv["h"] / 2 if cy is None else cy
        L = new_layer("image", self.cv, file=rel, w=w, h=h, x=int(cx - w / 2), y=int(cy - h / 2))
        self.cv["layers"].append(L)
        self.project.dirty = True
        self._fill_list(L["id"])
        self.changed.emit()

    def dup_layer(self):
        L = self.layer()
        if L is None:
            return
        import copy
        n = copy.deepcopy(L)
        n["id"] = new_layer("shape", self.cv)["id"]
        n["name"] = L.get("name", "") + " (copia)"
        n["x"] += 24
        n["y"] += 24
        self.cv["layers"].append(n)
        self.project.dirty = True
        self._fill_list(n["id"])
        self.changed.emit()

    def move_layer(self, d):
        L = self.layer()
        if L is None:
            return
        ls = self.cv["layers"]
        i = ls.index(L)
        j = i + d
        if 0 <= j < len(ls):
            ls[i], ls[j] = ls[j], ls[i]
            self.project.dirty = True
            self._fill_list(L["id"])
            self.changed.emit()

    def del_layer(self):
        L = self.layer()
        if L is None:
            return
        self.cv["layers"].remove(L)
        self.project.dirty = True
        self.sel = None
        self._fill_list()
        self.changed.emit()

    def _remove_canvas(self):
        pr = self.project
        if pr and self.cv:
            pr.canvases = [c for c in pr.canvases if c["id"] != self.cv["id"]]
            pr.dirty = True
            self.cv = None
            self.structure_changed.emit()


class SlotPanel(QWidget):
    """Sonidos y mascota: cada fila usa tu archivo o, vacía, el de osu! (no se exporta nada)."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.project = None
        self.gid = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.title = QLabel()
        self.title.setObjectName("h2")
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setObjectName("muted")
        self.host = QWidget()
        self.form = QFormLayout(self.host)
        self.form.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self.host)
        lay.addWidget(self.title)
        lay.addWidget(self.desc)
        lay.addWidget(scroll, 1)

    def show_group(self, project, gid):
        self.project, self.gid = project, gid
        title, _mode, desc, slots = core.SLOT_GROUPS[gid]
        self.title.setText(title)
        self.desc.setText(desc + " Fila vacía = se usa el de osu! por defecto.")
        clear_form(self.form)
        for key, label, kind in slots:
            v = project.slots.get(key)
            state = ("✔ " + (Path(v).name if kind == "sound" else f"{len(v)} fotogramas")) if v else "osu! por defecto"
            w = QWidget()
            row = QHBoxLayout(w)
            row.setContentsMargins(0, 0, 0, 0)
            lab = QLabel(state)
            lab.setObjectName("muted")
            pick = QPushButton("Elegir…")
            pick.clicked.connect(lambda _=False, k=key, kd=kind: self._pick(k, kd))
            clr = QPushButton("Usar el de osu!")
            clr.setEnabled(bool(v))
            clr.clicked.connect(lambda _=False, k=key: self._clear(k))
            row.addWidget(lab, 1)
            row.addWidget(pick)
            row.addWidget(clr)
            self.form.addRow(label, w)

    def _pick(self, key, kind):
        pr = self.project
        d = pr.path / "sounds" if kind == "sound" else pr.path / "assets"
        d.mkdir(parents=True, exist_ok=True)
        if kind == "sound":
            f, _ = QFileDialog.getOpenFileName(self, "Elegir sonido", "", "Sonidos (*.wav *.mp3 *.ogg)")
            if not f:
                return
            dest = d / (key + Path(f).suffix.lower())
            shutil.copyfile(f, dest)
            pr.slots[key] = str(dest.relative_to(pr.path))
        else:
            f, _ = QFileDialog.getOpenFileName(self, "Elegir GIF", "", "GIF / imagen (*.gif *.png)")
            if not f:
                return
            reader = QImageReader(f)
            rels = []
            while reader.canRead() and len(rels) < 300:
                img = reader.read()
                if img.isNull():
                    break
                dest = d / f"{key}_{len(rels)}.png"
                img.save(str(dest), "PNG")
                rels.append(str(dest.relative_to(pr.path)))
            if not rels:
                QMessageBox.warning(self, APP_NAME, "No se pudieron leer fotogramas de ese archivo.")
                return
            pr.slots[key] = rels
        pr.dirty = True
        self.show_group(pr, self.gid)
        self.changed.emit()

    def _clear(self, key):
        self.project.slots.pop(key, None)
        self.project.dirty = True
        self.show_group(self.project, self.gid)
        self.changed.emit()


class EffectPanel(QWidget):
    """Efectos: sin código (eliges para qué sirve y un tipo de efecto) o con código (Python, solo en el editor)."""
    changed = Signal()
    removed = Signal()

    IDEAS = [  # (para qué sirve, efecto, color, color 2, cantidad, texto)
        ("hit300", "Pulso de texto", "#ffe27a", "#ffffff", 12, "300"), ("mania_lighting", "Onda", "#ffffff", "#ff66aa", 12, ""),
        ("comboburst", "Lluvia de estrellas", "#ffd166", "#ff7ab6", 18, ""), ("particle300", "Destello", "#ffffff", "#53b9ff", 1, ""),
        ("sliderball", "Brillo giratorio", "#ffffff", "#ff66aa", 1, ""), ("miss", "Pulso de texto", "#ff4d4d", "#ffffff", 1, "✕"),
        ("lighting", "Destello", "#ffffff", "#ff9ecb", 1, ""), ("mania_hit300g", "Estallido de partículas", "#ffe27a", "#7df9ff", 20, ""),
        ("section_pass", "Pulso de texto", "#7dff8f", "#ffffff", 1, "¡Bien!"), ("followpoint", "Onda", "#ffffff", "#53b9ff", 1, "")]

    def __init__(self):
        super().__init__()
        self.project = None
        self.e = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        self.title = QLabel("Efecto")
        self.title.setObjectName("h2")
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setObjectName("muted")
        self.host = QWidget()
        self.form = QFormLayout(self.host)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.code = QPlainTextEdit()
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.code.setFont(f)
        self.code.setMinimumHeight(220)
        self.run_btn = QPushButton("▶ Aplicar y probar el código")
        self.run_btn.clicked.connect(self._run_code)
        self.err = QLabel()
        self.err.setWordWrap(True)
        self.err.setStyleSheet("color:#ff8080;")
        self.idea_btn = QPushButton("💡 Dame una idea")
        self.idea_btn.clicked.connect(self._idea)
        self.del_btn = QPushButton("Eliminar este efecto")
        self.del_btn.clicked.connect(self._delete)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 0, 0)
        for w in (self.host, self.code, self.run_btn, self.err, self.idea_btn):
            il.addWidget(w)
        il.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(inner)
        for w in (self.title, self.note):
            lay.addWidget(w)
        lay.addWidget(scroll, 1)
        lay.addWidget(self.del_btn)

    def show_effect(self, project, e):
        self.project, self.e = project, e
        code = e.get("mode") == "code"
        self.title.setText(("Efecto con código · " if code else "Efecto sin código · ") + e.get("name", ""))
        self.note.setText(
            "osu! no ejecuta código dentro de una skin (ni C# ni Python): solo lee imágenes, sonidos y skin.ini. Por eso tu "
            "función frame(t, p) se ejecuta aquí, en el editor, y al exportar se guardan los fotogramas que dibuja; así sí "
            "funciona en osu!." if code else
            "Elige para qué sirve (el momento del juego) y el tipo de efecto. Se exportan los fotogramas o la imagen que osu! "
            "usa en ese momento. «Dame una idea» prueba una combinación que queda bien.")
        clear_form(self.form)
        specs = [core.P("name", "Nombre", "text", "Efecto"), core.B("enabled", "Exportar este efecto", True),
                 core.CH("event", "Para qué sirve", "hit300", list(core.EFFECT_EVENTS))]
        if not code:
            specs += [core.CH("preset", "Tipo de efecto", "Destello", gens.EFFECT_PRESETS),
                      core.C("color", "Color", "#ffffff"), core.C("color2", "Color 2", "#53b9ff"),
                      core.I("amount", "Cantidad (partículas / estrellas)", 12, 1, 60),
                      core.P("text", "Texto (pulso de texto)", "text", "300"), core.I("seed", "Variación", 7, 0, 999)]
        specs += [core.sec("Animación"), core.I("size", "Tamaño", 256, 32, 1024, "px"),
                  core.I("frames", "Fotogramas", 12, 2, 60), core.I("fps", "Velocidad", 30, 1, 60, "fps")]
        fill_form(self.form, specs, lambda k: e.get(k), self._set)
        name, animated, what = core.EFFECT_EVENTS[e["event"]]
        desc = QLabel(f"{what} → {name.format(i='0…N') if animated else name}"
                      + ("" if animated else " (una sola imagen, no se anima)"))
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        self.form.insertRow(3, desc)
        for w in (self.code, self.run_btn, self.err):
            w.setVisible(code)
        self.idea_btn.setVisible(not code)
        self.code.setPlainText(e.get("code", ""))
        self.err.setText("")

    def _set(self, spec, value):
        self.e[spec["key"]] = Project._coerce(spec, value)
        self.project.dirty = True
        if spec["key"] in ("event", "name"):
            self.show_effect(self.project, self.e)
        self.changed.emit()

    def _run_code(self):
        self.e["code"] = self.code.toPlainText()
        _img, err = gens.render_effect(self.e, 0.5, 64)
        self.err.setText(("Error: " + err) if err else "✔ El código funciona.")
        self.project.dirty = True
        self.changed.emit()

    def _idea(self):
        ev, preset, c1, c2, n, txt = random.choice(self.IDEAS)
        self.e.update(event=ev, preset=preset, color=c1, color2=c2, amount=n, text=txt or self.e.get("text", ""),
                      seed=random.randrange(1000), name=f"{preset} · {ev}")
        self.project.dirty = True
        self.show_effect(self.project, self.e)
        self.changed.emit()

    def _delete(self):
        if self.project and self.e in self.project.effects:
            self.project.effects.remove(self.e)
            self.project.dirty = True
            self.e = None
            self.removed.emit()


class LibList(QListWidget):
    """Lista de recursos globales; al arrastrar un icono lleva «lib:<nombre>» para soltarlo en el visualizador."""

    def mimeData(self, items):
        m = QMimeData()
        if items:
            m.setText("lib:" + items[0].data(Qt.ItemDataRole.UserRole))
        return m


class LibraryDialog(QDialog):
    """Carpeta de recursos global: sirve para cualquier modo y se coloca libremente en la escena abierta."""
    add_image = Signal(str)       # nombre del recurso
    add_text = Signal()
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recursos (carpeta global)")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.resize(420, 640)
        self.project: Project | None = None
        self.list = LibList()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(72, 72))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setDragEnabled(True)
        self.list.setMaximumHeight(210)
        self.list.itemDoubleClicked.connect(lambda it: self.add_image.emit(it.data(Qt.ItemDataRole.UserRole)))
        b_imp = QPushButton("Importar…")
        b_imp.clicked.connect(self.import_files)
        b_add = QPushButton("Añadir a la escena")
        b_add.clicked.connect(self._add_sel)
        b_txt = QPushButton("＋ Texto")
        b_txt.clicked.connect(self.add_text)
        b_del = QPushButton("Eliminar")
        b_del.clicked.connect(self.remove_sel)
        row = QHBoxLayout()
        for b in (b_imp, b_add, b_txt, b_del):
            row.addWidget(b)
        self.info = QLabel("Arrastra un recurso al visualizador, o doble clic para añadirlo. Luego muévelo, "
                           "redimensiónalo y edítalo sin restricciones.")
        self.info.setWordWrap(True)
        self.info.setObjectName("muted")
        self.panel = CanvasPanel()
        self.panel.changed.connect(self.changed)
        self.panel.hint.setVisible(False)
        lay = QVBoxLayout(self)
        lay.addWidget(self.info)
        lay.addWidget(self.list)
        lay.addLayout(row)
        lay.addWidget(self.panel, 1)

    def set_project(self, project):
        self.project = project
        self.refresh()

    def refresh(self):
        self.list.clear()
        if not self.project:
            return
        for r in self.project.library:
            it = QListWidgetItem(r["name"])
            it.setData(Qt.ItemDataRole.UserRole, r["name"])
            pm = QPixmap(str(self.project.path / r["file"]))
            if not pm.isNull():
                it.setIcon(QIcon(pm))
            self.list.addItem(it)

    def import_files(self):
        pr = self.project
        if pr is None:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Importar recursos", "", "Imágenes (*.png *.jpg *.jpeg *.gif *.webp *.bmp)")
        if not files:
            return
        d = pr.path / "resources"
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            name = Path(f).name
            shutil.copyfile(f, d / name)
            rel = str((d / name).relative_to(pr.path))
            for r in pr.library:
                if r["name"] == name:
                    r["file"] = rel
                    break
            else:
                pr.library.append({"name": name, "file": rel})
        pr.dirty = True
        self.refresh()
        self.changed.emit()

    def _add_sel(self):
        it = self.list.currentItem()
        if it:
            self.add_image.emit(it.data(Qt.ItemDataRole.UserRole))

    def remove_sel(self):
        it = self.list.currentItem()
        if self.project and it:
            name = it.data(Qt.ItemDataRole.UserRole)
            self.project.library = [r for r in self.project.library if r["name"] != name]
            self.project.dirty = True
            self.refresh()
            self.changed.emit()


# ======================================================================
# Visualizador
# ======================================================================
class PreviewWidget(QWidget):
    mania_edit = Signal(dict, bool)      # {clave: valor}, ¿es el último movimiento?
    pick = Signal(str)                   # id de elemento pulsado en la escena
    layer_picked = Signal(str)
    layer_changed = Signal(bool)         # ¿final del arrastre?
    layer_delete = Signal()
    lib_dropped = Signal(str, float, float)
    enable_mode = Signal(str)
    pick_obj = Signal(str, str)                  # elemento, archivo
    obj_moved = Signal(str, str, float, float)   # elemento, archivo, dx, dy (unidades de interfaz)
    obj_menu = Signal(str, str, str)             # acción, elemento, archivo

    PREEMPT, D = 800, 73.0
    SLIDER_START, LEG = 3200, 1200
    TAIKO_NOTES = [(800, "don"), (1200, "don"), (1600, "kat"), (2000, "don"), (2400, "bigdon"),
                   (3000, "kat"), (3300, "kat"), (3600, "bigkat"), (4200, "roll", 5400)]

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.scene = "std"
        self.t = 0.0
        self.playing = True
        self.bg_mode = 0
        self.mania_k = 4
        self.edit_mode = True
        self.mouse: QPointF | None = None
        self.trail: deque[QPointF] = deque(maxlen=22)
        self._ox = self._oy = 0.0
        self._k = 1.0
        self._tint_cache: dict = {}
        self._cx = 256.0
        self.canvas: dict | None = None
        self.sel_layer: str | None = None
        self.cv_rev = 0
        self.effect: dict | None = None
        self.fx_t = 0.0
        self._fx_cache: tuple = (None, [])
        self._cvc: dict = {}
        self._hits: list = []
        self._handles: list = []
        self._drag: dict | None = None
        self.hover: QPointF | None = None
        self.multi: dict = {}                # archivo -> elemento (selección múltiple con Ctrl)
        self.rank_shown = "S"
        self._checker = None
        self.path = QPainterPath(QPointF(120, 300))
        self.path.cubicTo(QPointF(200, 220), QPointF(320, 380), QPointF(400, 300))
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(520, 380)
        self._clock = QElapsedTimer()
        self._clock.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    # ---- geometría -------------------------------------------------------
    def aspect(self) -> float:
        return ASPECTS[self.project.get("mania_config", "aspect")] if self.project else 16 / 9

    def logical(self):
        if self.scene in UI_SCENES:
            return 768 * self.aspect(), 768.0
        if self.scene == "canvas":
            return (float(self.canvas["w"]), float(self.canvas["h"])) if self.canvas else (100.0, 100.0)
        return 480 * self.aspect(), 480.0

    def pf_offset(self):
        """Origen del playfield de 512x384 (standard/catch): centrado, 8 px más abajo como en osu!stable."""
        W, _ = self.logical()
        return (W - 512) / 2, (480 - 384) / 2 + 8

    def set_scene(self, scene):
        if scene != self.scene:
            self.scene = scene
            self._drag = None
            self.sel_layer = None
            self.restart()

    def restart(self):
        self.t = 0.0
        self.trail.clear()
        self.update()

    def _tick(self):
        dt = self._clock.restart()
        if not self.project or not self.isVisible():
            return
        if self.playing and self.scene == "effects":
            self.fx_t += dt
        if self.playing and self.scene in ("std", "taiko", "catch", "mania"):
            self.t = (self.t + dt) % LOOPS[self.scene]
            if self.scene == "std":
                self.trail.append(QPointF(self._auto_cursor(self.t) if self.mouse is None else self.mouse))
        self.update()

    def _fp(self, pos) -> QPointF:
        return QPointF((pos.x() - self._ox) / self._k, (pos.y() - self._oy) / self._k)

    # ---- ratón ---------------------------------------------------------------
    def _handle_at(self, fp):
        for h in self._handles:
            if h["rect"].contains(fp):
                return h
        return None

    def _layers(self):
        if self.scene == "canvas":
            return self.canvas["layers"] if self.canvas else []
        return self.project.scene_objs.setdefault(self.scene, []) if self.project else []

    def _layer_at(self, fp):
        for L in reversed(self._layers()):
            if L.get("visible", True) and QRectF(L["x"], L["y"], L["w"], L["h"]).contains(fp):
                return L
        return None

    def _layer(self):
        return next((L for L in self._layers() if L["id"] == self.sel_layer), None)

    def _grip(self, L):
        s = 16 / self._k
        return QRectF(L["x"] + L["w"] - s, L["y"] + L["h"] - s, s * 1.5, s * 1.5)

    def contextMenuEvent(self, e):
        if not self.project or self.scene not in UI_SCENES:
            return
        hit = self._hit_at(self._fp(QPointF(e.pos())), include_locked=True)
        if not hit or not hit[2]:
            return
        _r, sel, fname, _img = hit
        locked = self.project.lay(fname).get("locked")
        m = QMenu(self)
        m.addAction(f"Editar «{fname}»", lambda: self.pick_obj.emit(sel, fname))
        m.addAction("🔓 Desbloquear" if locked else "🔒 Bloquear", lambda: self.obj_menu.emit("lock", sel, fname))
        m.addAction("Restablecer posición y tamaño", lambda: self.obj_menu.emit("reset", sel, fname))
        if not sel.startswith("canvas:"):
            m.addAction("Reemplazar con mi imagen…", lambda: self.obj_menu.emit("image", sel, fname))
        m.exec(e.globalPos())

    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() != Qt.MouseButton.LeftButton or not self.project:
            return
        if self.scene in dict(SCENES) and not self.project.modes.get(self.scene, True):
            self.enable_mode.emit(self.scene)      # clic sobre «modo desactivado» = activarlo
            return
        fp = self._fp(e.position())
        cur = self._layer()
        if cur is not None and self._grip(cur).contains(fp):
            self._drag = {"mode": "resize", "L": cur, "fp": fp, "w": cur["w"], "h": cur["h"]}
            return
        L = self._layer_at(fp)
        if L is not None:
            self.sel_layer = L["id"]
            self.layer_picked.emit(L["id"])
            self._drag = {"mode": "move", "L": L, "fp": fp, "x": L["x"], "y": L["y"]}
            return
        if self.sel_layer:
            self.sel_layer = None
            self.layer_picked.emit("")
        if self.scene == "canvas":
            return
        if self.scene in UI_SCENES:
            hit = self._hit_at(fp, movable=True)
            if hit and e.modifiers() & Qt.KeyboardModifier.ControlModifier:     # Ctrl+clic: varios a la vez
                if hit[2] in self.multi:
                    self.multi.pop(hit[2])
                else:
                    self.multi[hit[2]] = hit[1]
                self.update()
                return
            if hit:
                if hit[2] not in self.multi:
                    self.multi = {}
                self._drag = {"obj": hit, "fp": fp, "moved": False, "delta": QPointF(0, 0)}
                return
            self.multi = {}
        if self.scene == "mania" and self.edit_mode:
            h = self._handle_at(fp)
            if h is not None:
                self._drag = {"h": h, "fp": fp, "moved": False, "orig": dict(h["orig"])}
                return
        self._drag = {"click": fp, "moved": False}

    def mouseMoveEvent(self, e):
        fp = self._fp(e.position())
        W, H = self.logical()
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self._do_drag(fp)
            return
        if self.scene in ("std", "catch"):
            ox, oy = self.pf_offset()
            pf = QPointF(fp.x() - ox, fp.y() - oy)
            if 0 <= pf.x() <= 512 and 0 <= pf.y() <= 384:
                self.mouse = pf
                self.setCursor(Qt.CursorShape.BlankCursor)
                return
            self.mouse = None
            self.unsetCursor()
        elif self.scene == "mania" and self.edit_mode:
            h = self._handle_at(fp)
            self.setCursor(h["cursor"] if h else Qt.CursorShape.ArrowCursor)
        elif self.scene == "canvas":
            cur = self._layer()
            if cur is not None and self._grip(cur).contains(fp):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif self._layer_at(fp) is not None:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.hover = fp
            self.setCursor(Qt.CursorShape.PointingHandCursor if self._hit_at(fp) is not None
                           else Qt.CursorShape.ArrowCursor)

    def _do_drag(self, fp):
        d = self._drag
        if "obj" in d:
            d["delta"] = fp - d["fp"]
            d["moved"] = d["moved"] or d["delta"].manhattanLength() > 3
            self.update()
            return
        if "mode" in d:
            L = d["L"]
            if d["mode"] == "move":
                L["x"], L["y"] = int(d["x"] + fp.x() - d["fp"].x()), int(d["y"] + fp.y() - d["fp"].y())
            else:
                L["w"], L["h"] = max(2, int(d["w"] + fp.x() - d["fp"].x())), max(2, int(d["h"] + fp.y() - d["fp"].y()))
            self.project.dirty = True
            self._cvc.clear()
            self.layer_changed.emit(False)
            return
        if "click" in d:
            if (fp - d["click"]).manhattanLength() > 4:
                d["moved"] = True
            return
        if (fp - d["fp"]).manhattanLength() > 3:
            d["moved"] = True
        if not d["moved"]:
            return
        h, o = d["h"], d["orig"]
        kind, edit = h["kind"], {}
        if kind == "key_lift":          # se guarda en «Teclas (receptores)»
            v = int(max(0, min(400, round(480 - fp.y() - o["hk0"] / 2))))
            self.project.set("mania_keys", "key_lift", v)
            self.mania_edit.emit({}, False)
            return
        if kind in ("hit_position", "light_position", "score_position", "combo_position"):
            lo = 240 if kind in ("hit_position", "light_position") else 0
            hi = 470 if kind == "hit_position" else 480
            edit[kind] = int(max(lo, min(hi, round(fp.y()))))
        elif kind == "move":
            new = o["start"] + fp.x() - d["fp"].x()
            edit = {"auto_center": False, "column_start": int(max(0, min(1200, round(new))))}
        elif kind == "w_right":
            edit["column_width"] = int(max(20, min(100, round((fp.x() - o["start"] - (o["K"] - 1) * o["sp"]) / o["K"]))))
        elif kind == "w_left":
            end = o["start"] + o["total"]
            w = int(max(20, min(100, round((end - fp.x() - (o["K"] - 1) * o["sp"]) / o["K"]))))
            edit = {"column_width": w, "auto_center": False,
                    "column_start": int(max(0, round(end - (o["K"] * w + (o["K"] - 1) * o["sp"]))))}
        if edit:
            self.mania_edit.emit(edit, False)

    def mouseReleaseEvent(self, e):
        d, self._drag = self._drag, None
        if d is None:
            return
        if "mode" in d:
            self.layer_changed.emit(True)
            return
        if "obj" in d:
            _r, sel, fname, _img = d["obj"]
            if d["moved"]:
                pack = d["obj"][3]
                k = pack[2] if pack is not None and len(pack) > 2 and pack[2] else 1.0   # el número va donde sueltes
                group = self.multi if fname in self.multi else {fname: sel}
                for fn, eid in group.items():
                    self.obj_moved.emit(eid, fn, d["delta"].x() / k, d["delta"].y() / k)
            else:
                self.pick_obj.emit(sel, fname)
            return
        if "click" in d or ("h" in d and not d["moved"]):
            if not d.get("moved"):
                fp = d.get("click", d.get("fp"))
                hit = self._hit_at(fp)
                if hit:
                    if hit[2]:
                        self.pick_obj.emit(hit[1], hit[2])
                    elif not hit[1].startswith("fixed:"):
                        self.pick.emit(hit[1])
            return
        self.mania_edit.emit({}, True)

    def leaveEvent(self, e):
        self.mouse = None
        self.hover = None
        self.unsetCursor()

    def keyPressEvent(self, e):
        L = self._layer()
        step = 10 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        key = e.key()
        arrows = (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down)
        if L is None and self.multi and key in arrows:          # mover la selección múltiple con el teclado
            dx = step * ((key == Qt.Key.Key_Right) - (key == Qt.Key.Key_Left))
            dy = step * ((key == Qt.Key.Key_Down) - (key == Qt.Key.Key_Up))
            for fn, eid in self.multi.items():
                self.obj_moved.emit(eid, fn, dx, dy)
            return
        if L is None:
            return super().keyPressEvent(e)
        if key == Qt.Key.Key_R:          # R / Mayús+R: girar la capa
            L["rot"] = ((L.get("rot", 0) + (-15 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 15) + 180) % 360) - 180
            self.project.dirty = True
            self._cvc.clear()
            self.layer_changed.emit(True)
            return
        if key == Qt.Key.Key_Delete:
            self.layer_delete.emit()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            L["x"] += step * ((key == Qt.Key.Key_Right) - (key == Qt.Key.Key_Left))
            L["y"] += step * ((key == Qt.Key.Key_Down) - (key == Qt.Key.Key_Up))
            self.project.dirty = True
            self._cvc.clear()
            self.layer_changed.emit(True)

    # ---- arrastrar recursos desde el panel «Recursos» ---------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasText() and e.mimeData().text().startswith("lib:"):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        fp = self._fp(e.position())
        self.lib_dropped.emit(e.mimeData().text()[4:], fp.x(), fp.y())
        e.acceptProposedAction()

    # ---- utilidades de dibujo ---------------------------------------------------
    def _tint(self, img: QImage, color: QColor) -> QImage:
        key = (img.cacheKey(), color.rgb())
        out = self._tint_cache.get(key)
        if out is None:
            if len(self._tint_cache) > 120:
                self._tint_cache.clear()
            out = img.copy()
            p = QPainter(out)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
            p.fillRect(out.rect(), QColor(color.red(), color.green(), color.blue()))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            p.drawImage(0, 0, img)
            p.end()
            self._tint_cache[key] = out
        return out

    @staticmethod
    def _img(p, img, pos, w, rot=0.0, h=None):
        h = h if h is not None else w * img.height() / img.width()
        p.save()
        p.translate(pos)
        if rot:
            p.rotate(rot)
        p.drawImage(QRectF(-w / 2, -h / 2, w, h), img)
        p.restore()

    def _reg(self, rect: QRectF, sel: str, fname=None, img=None):
        """Zona pulsable. Con fname el objeto se puede mover, escalar y bloquear (se guarda en el archivo exportado).
        La zona se ajusta a la parte visible de la imagen: el borde transparente (que se añade al mover) no cuenta."""
        full = rect
        if img is not None and not img.isNull() and img.width() and img.height():
            b = self._opaque(img)
            if b is not None:
                sx, sy = rect.width() / img.width(), rect.height() / img.height()
                rect = QRectF(rect.left() + b.left() * sx, rect.top() + b.top() * sy, b.width() * sx, b.height() * sy)
        self._hits.append((rect, sel, fname, (img, full) if img is not None else None))

    def _opaque(self, img):
        """Rectángulo de los píxeles visibles de una imagen (con caché)."""
        key = img.cacheKey()
        cache = self.__dict__.setdefault("_opq", {})
        if key not in cache:
            if len(cache) > 400:
                cache.clear()
            reg = QRegion(QBitmap.fromImage(img.createAlphaMask()))
            br = reg.boundingRect()
            cache[key] = br if br.width() > 0 and br.height() > 0 else None
        return cache[key]

    def _hit_at(self, fp, movable=False, include_locked=False):
        for r, sel, fname, img in reversed(self._hits):
            if not r.contains(fp):
                continue
            if fname and self.project.lay(fname).get("locked") and not include_locked:
                continue          # bloqueado: el clic pasa a lo que haya debajo
            if movable and not fname:
                return None
            return r, sel, fname, img
        return None

    def _family(self):
        return self.project.theme()["font"] if self.project else "Arial"

    def _text(self, p, rect, text, px, color="#ffffff", bold=False, flags=None):
        f = QFont(self._family())
        f.setPixelSize(int(px))
        f.setBold(bold)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(rect, int(flags if flags is not None else (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)), text)

    def _combo(self, i) -> QColor:
        return QColor(self.project.get("skin_ini", f"combo{i % 4 + 1}"))

    def _popup(self, p, pos, t0, name="hit300.png", w=64):
        img = self.project.image("hits", name)
        dt = self.t - t0
        if img is not None and 0 <= dt <= 450:
            p.setOpacity(1 - dt / 450)
            self._img(p, img, QPointF(pos.x(), pos.y() - 24 - dt * 0.03), w)
            p.setOpacity(1.0)

    def _canvas_img(self, name):
        """(imagen, escala de interfaz) del lienzo con ese nombre de archivo, con caché."""
        pr = self.project
        cv = next((c for c in pr.canvases if c["name"] == name), None)
        if cv is None:
            return None, 1.0
        key = (cv["id"], self.cv_rev)
        img = self._cvc.get(key)
        if img is None:
            if len(self._cvc) > 6:
                self._cvc.clear()
            img = gens.render_canvas(cv, pr.path)
            self._cvc[key] = img
        return img, (0.5 if cv["hd"] else 1.0)

    def _background(self, p):
        r = self.rect()
        if self.bg_mode == 1:
            p.fillRect(r, QColor("#3a3a3a"))
        elif self.bg_mode == 2:
            p.fillRect(r, QColor("#d9dde6"))
        elif self.bg_mode == 3:
            g = QLinearGradient(0, 0, 0, r.height())
            g.setColorAt(0, QColor("#2a2150"))
            g.setColorAt(1, QColor("#0d1b3a"))
            p.fillRect(r, QBrush(g))
        else:
            p.fillRect(r, QColor("#0e1015"))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
                         | QPainter.RenderHint.TextAntialiasing)
        self._background(p)
        lw, lh = self.logical()
        m = 20
        self._k = max(0.01, min((self.width() - 2 * m) / lw, (self.height() - 2 * m) / lh))
        self._ox, self._oy = (self.width() - lw * self._k) / 2, (self.height() - lh * self._k) / 2
        self._hits, self._handles = [], []
        if self.project is None:
            p.end()
            return
        p.translate(self._ox, self._oy)
        p.scale(self._k, self._k)
        p.save()
        p.setClipRect(QRectF(0, 0, lw, lh))
        getattr(self, "_scene_" + self.scene)(p)
        if self.scene != "canvas":
            p.save()
            if self.scene == "mania":      # en osu! van en los costados del escenario: lo que tape columnas no sale
                keys = self.project.keys()
                ml = mania_layout(self.project, self.mania_k if self.mania_k in keys else keys[0])
                clip = QPainterPath()
                clip.addRect(QRectF(0, 0, lw, lh))
                stage = QPainterPath()
                stage.addRect(QRectF(ml["start"], 0, ml["total"], lh))
                p.setClipPath(clip.subtracted(stage), Qt.ClipOperation.IntersectClip)
            for L in self.project.scene_objs.get(self.scene, []):
                if L.get("visible", True):
                    gens.draw_layer(p, L, self.project.path)
            p.restore()
            cur = self._layer()
            if cur is not None:
                p.setPen(QPen(ACCENT, 2 / self._k))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(cur["x"], cur["y"], cur["w"], cur["h"]))
                g = self._grip(cur)
                p.fillRect(QRectF(g.left(), g.top(), g.width() * 0.66, g.height() * 0.66), ACCENT)
            if self._drag and "obj" in self._drag and self._drag["moved"]:     # vista previa mientras arrastras
                dlt = self._drag["delta"]
                group = [h for h in self._hits if h[2] and (h[2] in self.multi or h[2] == self._drag["obj"][2])]
                for r, _sel, fname, pack in group:
                    dp = self._drag["obj"][3]
                    kd = dp[2] if dp is not None and len(dp) > 2 and dp[2] else 1.0
                    d = dlt * (pack[2] / kd) if pack is not None and len(pack) > 2 else dlt   # cuánto se mueve de verdad
                    if pack is not None:
                        img, full = pack[0], pack[1]
                        p.setOpacity(0.85)
                        p.drawImage(full.translated(d), img)
                        p.setOpacity(1.0)
                    p.setPen(QPen(ACCENT, 2 / self._k, Qt.PenStyle.DashLine))
                    p.setBrush(QColor(255, 79, 157, 25) if pack is None else Qt.BrushStyle.NoBrush)
                    p.drawRect(r.translated(d))
            for r, _sel, fname, _img in self._hits:
                if fname in self.multi:
                    p.setPen(QPen(QColor("#53b9ff"), 2 / self._k))
                    p.setBrush(QColor(83, 185, 255, 40))
                    p.drawRect(r)
                if fname and self.project.lay(fname).get("locked"):
                    self._text(p, QRectF(r.right() - 22, r.top(), 22, 22), "🔒", 14, "#ffffff", False, Qt.AlignmentFlag.AlignCenter)
            if self.scene in UI_SCENES and self.hover is not None and self._drag is None:
                hit = self._hit_at(self.hover)
                if hit:          # resalta lo que se puede editar y dice qué es
                    r, sel, fname = hit[:3]
                    name = fname or (sel[7:] if sel.startswith(("canvas:",)) else sel[6:] if sel.startswith("fixed:")
                                     else ELEMENT_BY_ID.get(sel, {}).get("name", sel))
                    if fname:
                        name += " · arrastra para mover · clic derecho: bloquear"
                    p.setPen(QPen(ACCENT, 2 / self._k, Qt.PenStyle.DashLine))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRect(r)
                    lab = QRectF(r.left(), max(0, r.top() - 24), max(140, len(name) * 8 + 16), 22)
                    p.fillRect(lab, ACCENT)
                    self._text(p, lab, " " + tr(name) + ("" if sel.startswith("fixed:") else tr(" · clic para editar")), 13, "#ffffff", True)
            if not self.project.modes.get(self.scene, True):
                p.fillRect(QRectF(0, 0, lw, lh), QColor(0, 0, 0, 150))
                self._text(p, QRectF(0, lh / 2 - 40, lw, 80), tr("Modo desactivado: osu! usará su skin por defecto"), 26, "#ffffff",
                           True, Qt.AlignmentFlag.AlignCenter)
                self._text(p, QRectF(0, lh / 2 + 30, lw, 40), tr("Haz clic aquí para activarlo"), 20, "#ff9fcb", True,
                           Qt.AlignmentFlag.AlignCenter)
        p.restore()
        p.setPen(QPen(QColor(128, 128, 128, 90), 1 / self._k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(0, 0, lw, lh))
        p.end()

    # ---- canvas -------------------------------------------------------------------
    def _scene_canvas(self, p):
        cv = self.canvas
        if cv is None:
            return
        if self._checker is None:
            pm = QPixmap(16, 16)
            pm.fill(QColor("#2a2d36"))
            q = QPainter(pm)
            q.fillRect(0, 0, 8, 8, QColor("#363a47"))
            q.fillRect(8, 8, 8, 8, QColor("#363a47"))
            q.end()
            self._checker = pm
        p.fillRect(QRectF(0, 0, cv["w"], cv["h"]), QBrush(self._checker))
        key = ("edit", cv["id"], self.cv_rev, len(self._cvc))
        img = self._cvc.get(key)
        if img is None:
            self._cvc.clear()
            img = gens.render_canvas(cv, self.project.path)
            self._cvc[key] = img
        p.drawImage(0, 0, img)
        L = self._layer()
        if L is not None:
            p.setPen(QPen(ACCENT, 2 / self._k))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(L["x"], L["y"], L["w"], L["h"]))
            g = self._grip(L)
            p.fillRect(QRectF(g.left(), g.top(), g.width() * 0.66, g.height() * 0.66), ACCENT)

    # ---- standard ---------------------------------------------------------------------
    def _slider_pct(self, t):
        prog = (t - self.SLIDER_START) / self.LEG
        return max(0.0, min(1.0, prog if prog <= 1 else 2 - prog))

    def _auto_cursor(self, t) -> QPointF:
        if self.SLIDER_START <= t <= self.SLIDER_START + 2 * self.LEG:
            return self.path.pointAtPercent(self._slider_pct(t))
        pts = [(0, QPointF(40, 40)), (1500, QPointF(150, 170)), (2300, QPointF(270, 110)),
               (3200, QPointF(120, 300)), (5600, QPointF(120, 300)), (6600, QPointF(40, 40))]
        for (t0, a), (t1, b) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                f = f * f * (3 - 2 * f)
                return a + (b - a) * f
        return pts[-1][1]

    def _circle_body(self, p, pos, color, number, alpha, scale=1.0):
        pr = self.project
        p.setOpacity(alpha)
        hc, ov = pr.image("hitcircle"), pr.image("hitcircleoverlay")
        if hc:
            self._img(p, self._tint(hc, color), pos, self.D * scale * hc.width() / 128)
        if ov:
            self._img(p, ov, pos, self.D * scale * ov.width() / 128)
        if number is not None and pr.assets["numbers"]["enabled"]:
            self._number(p, pos, number, scale)
        p.setOpacity(1.0)

    def _number(self, p, pos, text, scale):
        pr = self.project
        imgs = [pr.image("numbers", f"default-{d}.png") for d in text]
        overlap = pr.get("skin_ini", "hitcircle_overlap")
        f = self.D * scale / 128
        total = sum(i.width() for i in imgs) * f - (len(imgs) - 1) * overlap * f
        x = pos.x() - total / 2
        for i in imgs:
            w = i.width() * f
            self._img(p, i, QPointF(x + w / 2, pos.y()), w)
            x += (i.width() - overlap) * f

    def _approach(self, p, pos, color, hit):
        ac = self.project.image("approachcircle")
        start = hit - self.PREEMPT
        if ac and start <= self.t <= hit:
            prog = (self.t - start) / self.PREEMPT
            p.setOpacity(min(1.0, (self.t - start) / 300) * 0.9)
            self._img(p, self._tint(ac, color), pos, self.D * (1 + 3 * (1 - prog)) * ac.width() / 128)
            p.setOpacity(1.0)

    def _circle(self, p, hit, pos, idx, number):
        start, end = hit - self.PREEMPT, hit + 150
        if not (start <= self.t <= end):
            return
        if self.t < hit:
            alpha, scale = min(1.0, (self.t - start) / 300), 1.0
        else:
            f = (self.t - hit) / 150
            alpha, scale = max(0.0, 1 - f), 1 + 0.25 * f
        self._circle_body(p, pos, self._combo(idx), number, alpha, scale)

    def _slider(self, p, idx):
        pr, t = self.project, self.t
        start = self.SLIDER_START
        end = start + 2 * self.LEG
        if not (start - self.PREEMPT <= t <= end + 200):
            return
        alpha = min(1.0, (t - (start - self.PREEMPT)) / 300) if t < end else max(0.0, 1 - (t - end) / 200)
        color = self._combo(idx)
        gi = pr.assets["skin_ini"]
        border = QColor(gi["slider_border"])
        track = QColor(gi["slider_track"]) if gi["use_track_override"] else color.darker(250)
        p.setOpacity(alpha)
        for c, width in ((border, self.D), (track, self.D * 0.84)):
            pen = QPen(c, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(self.path)
        sp = pr.image("sliderscorepoint")
        if sp:
            for pct in (0.33, 0.66):
                self._img(p, sp, self.path.pointAtPercent(pct), self.D * sp.width() / 128)
        p.setOpacity(1.0)
        head, tail = self.path.pointAtPercent(0), self.path.pointAtPercent(1)
        self._circle_body(p, tail, color, None, alpha)
        ra = pr.image("reversearrow")
        if ra and t < start + self.LEG:
            before = self.path.pointAtPercent(0.97)
            ang = math.degrees(math.atan2(before.y() - tail.y(), before.x() - tail.x())) + 180
            p.setOpacity(alpha)
            self._img(p, ra, tail, self.D * ra.width() / 128, ang)
            p.setOpacity(1.0)
        if t < start + 150:
            self._circle_body(p, head, color, "3", alpha)
            self._approach(p, head, color, start)
        if start <= t <= end:
            pos = self.path.pointAtPercent(self._slider_pct(t))
            sf = pr.image("sliderfollowcircle")
            if sf:
                self._img(p, sf, pos, self.D * sf.width() / 128)
            sb = pr.image("sliderb")
            if sb:
                if gi["allow_slider_ball_tint"]:
                    sb = self._tint(sb, color)
                self._img(p, sb, pos, self.D * sb.width() / 128)

    def _scene_std(self, p):
        pr = self.project
        ox, oy = self.pf_offset()
        p.fillRect(QRectF(ox, oy, 512, 384), QColor(255, 255, 255, 8))     # área jugable 512x384
        W_ = self.logical()[0] - ox
        p.translate(ox, oy)
        self._slider(p, 2)
        self._circle(p, 2300, QPointF(270, 110), 1, "2")
        self._circle(p, 1500, QPointF(150, 170), 0, "1")
        self._approach(p, QPointF(270, 110), self._combo(1), 2300)
        self._approach(p, QPointF(150, 170), self._combo(0), 1500)
        self._popup(p, QPointF(150, 170), 1500)
        self._popup(p, QPointF(270, 110), 2300, "hit100.png")
        pos = self.mouse if self.mouse is not None else self._auto_cursor(self.t)
        tr = pr.image("cursortrail")
        if tr and self.trail:
            n = len(self.trail)
            for i, tp in enumerate(self.trail):
                p.setOpacity((i + 1) / n)
                self._img(p, tr, tp, tr.width() * 0.6)
            p.setOpacity(1.0)
        bgk, key = pr.image("inputoverlay", "inputoverlay-background.png"), pr.image("inputoverlay", "inputoverlay-key.png")
        if bgk and key:
            ks = 36 / key.width()
            r = QRectF(W_ - bgk.height() * ks, 190, bgk.height() * ks, bgk.width() * ks)     # osu! lo gira 90°
            p.save()
            p.translate(r.center())
            p.rotate(90)
            p.drawImage(QRectF(-r.height() / 2, -r.width() / 2, r.height(), r.width()), bgk)
            p.restore()
            self._reg(r, "inputoverlay")
            for i, lab in enumerate(("K1", "K2", "M1", "M2")):
                kr = QRectF(r.left() + (r.width() - 36) / 2, r.top() + 8 + i * 42, 36, 36 * key.height() / key.width())
                p.drawImage(kr, key)
                self._text(p, kr, lab, 12, "#ffffff", True, Qt.AlignmentFlag.AlignCenter)
        cu = pr.image("cursor")
        if cu:
            self._img(p, cu, pos, cu.width() * 0.55)

    # ---- taiko ---------------------------------------------------------------------------
    def _scene_taiko(self, p):
        pr, t = self.project, self.t
        W, _ = self.logical()
        cy, lp = 200.0, W * 0.19
        tx, speed = lp + 70, 0.32
        bl, br = pr.image("taiko_bar", "taiko-bar-left.png"), pr.image("taiko_bar", "taiko-bar-right.png")
        cl, _s = self._canvas_img("taiko-bar-left.png")
        cr, _s = self._canvas_img("taiko-bar-right.png")
        bl, br = (cl if cl is not None else bl), (cr if cr is not None else br)
        top = cy - 55 - (br.height() * (W - lp) / br.width() - 110 if cr is not None else 0)
        if br:
            p.drawImage(QRectF(lp, top, W - lp, cy + 55 - top), br)
        else:
            p.fillRect(QRectF(lp, cy - 55, W - lp, 110), QColor("#222733"))
        if bl:
            p.drawImage(QRectF(0, cy - 65, lp, 130), bl)
        outer, inner = pr.image("taiko_drum", "taiko-drum-outer.png"), pr.image("taiko_drum", "taiko-drum-inner.png")
        pulse = 1.0 + (0.08 if (t % 400) < 120 else 0)
        if outer:
            self._img(p, outer, QPointF(lp / 2, cy), 96 * pulse)
        if inner:
            self._img(p, inner, QPointF(lp / 2, cy), 58 * pulse)
        ac = pr.image("approachcircle")
        if ac:
            p.setOpacity(0.7)
            self._img(p, ac, QPointF(tx, cy), 70)
            p.setOpacity(1.0)
        else:
            p.setPen(QPen(QColor(255, 255, 255, 160), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(tx, cy), 34, 34)
        don, kat = QColor("#eb452b"), QColor("#438eb9")
        for n in self.TAIKO_NOTES:
            hit = n[0]
            x = tx + (hit - t) * speed
            if n[1] == "roll":
                x1 = tx + (n[2] - t) * speed
                mid, end = pr.image("taiko_roll", "taiko-roll-middle.png"), pr.image("taiko_roll", "taiko-roll-end.png")
                xa = max(x, tx - 20)
                if mid and x1 > xa and xa < W:
                    p.drawImage(QRectF(xa, cy - 30, x1 - xa, 60), mid)
                if end and tx - 20 < x1 < W + 30:
                    self._img(p, end, QPointF(x1, cy), 60)
                continue
            if t - hit > 60 or x > W + 40:
                continue
            big = n[1].startswith("big")
            color = don if n[1].endswith("don") else kat
            eid = "taiko_big" if big else "taiko_circle"
            body = pr.image(eid, "taikobigcircle.png" if big else "taikohitcircle.png")
            ov = pr.image(eid, "taikobigcircleoverlay.png" if big else "taikohitcircleoverlay.png")
            w = 90 if big else 60
            if body:
                self._img(p, self._tint(body, color), QPointF(x, cy), w)
            if ov:
                self._img(p, ov, QPointF(x, cy), w)
            if -10 <= t - hit <= 60:
                self._popup(p, QPointF(tx, cy - 20), hit)

    # ---- catch -----------------------------------------------------------------------------
    def _scene_catch(self, p):
        pr, t = self.project, self.t
        ox, oy = self.pf_offset()
        p.fillRect(QRectF(ox, oy, 512, 384), QColor(255, 255, 255, 8))
        p.translate(ox, oy)
        FALL, ground = 1400.0, 318.0
        fruits = [(1200 + i * 560, 60 + (i * 137) % 392, gens.FRUITS[i % 6], i // 3) for i in range(11)]
        if self.mouse is not None:
            target = self.mouse.x()
        else:
            nxt = [f for f in fruits if f[0] >= t - 50]
            target = nxt[0][1] if nxt else 256
        self._cx += (target - self._cx) * 0.16
        for land, x, kind, ci in fruits:
            start = land - FALL
            if not (start <= t <= land + 120):
                continue
            y = -30 + (t - start) / FALL * (ground + 30) if t <= land else ground
            alpha = 1.0 if t <= land else max(0.0, 1 - (t - land) / 120)
            size = 34 if kind == "drop" else 62
            body, ov = pr.image("catch_fruits", f"fruit-{kind}.png"), pr.image("catch_fruits", f"fruit-{kind}-overlay.png")
            p.setOpacity(alpha)
            if body:
                self._img(p, self._tint(body, self._combo(ci)), QPointF(x, y), size)
            if ov:
                self._img(p, ov, QPointF(x, y), size)
            p.setOpacity(1.0)
        cat = pr.image("catch_catcher", f"fruit-catcher-{'kiai' if int(t // 3500) % 2 else 'idle'}.png")
        if cat:
            self._img(p, cat, QPointF(self._cx, 340), 120)

    # ---- mania ---------------------------------------------------------------------------------
    def _mania_notes(self, K):
        rng = random.Random(K * 97)
        out, time = [], 700
        while time < 7400:
            out.append((time, rng.randrange(K), 600 if rng.random() < 0.2 else 0))
            time += 260
        return out

    def _marker(self, p, rect: QRectF, label: str, kind: str, orig: dict, cursor):
        self._handles.append({"rect": rect, "kind": kind, "orig": orig, "cursor": cursor})
        if not self.edit_mode:
            return
        p.setPen(QPen(ACCENT, 1.5 / self._k))
        p.setBrush(QColor(255, 79, 157, 70))
        p.drawRoundedRect(rect, 3, 3)
        self._text(p, rect, label, 11, "#ffffff", True, Qt.AlignmentFlag.AlignCenter)

    def _scene_mania(self, p):
        pr, t = self.project, self.t
        keys = pr.keys()
        K = self.mania_k if self.mania_k in keys else keys[0]
        cfg = pr.assets["mania_config"]
        lay = mania_layout(pr, K)
        sx, w, sp, total = lay["start"], lay["w"], lay["sp"], lay["total"]
        W, _ = self.logical()
        hp, lp = cfg["hit_position"], cfg["light_position"]
        cols = gens.mania_columns(K)
        nv = pr.values("mania_notes")
        rotate = bool(nv.get("rotate_by_column", True))
        colx = [sx + i * (w + sp) for i in range(K)]
        speed = 0.45
        notes = self._mania_notes(K)
        pressed = [any(tm - 40 <= t <= tm + max(ln, 90) for tm, c, ln in notes if c == i) for i in range(K)]
        orig = {"start": sx, "K": K, "sp": sp, "total": total}
        bgc = QColor(cfg.get("column_bg", "#000000"))
        bgc.setAlphaF(cfg.get("column_bg_opacity", 100) / 100)
        for x in colx:
            p.fillRect(QRectF(x, 0, w, 480), bgc)
        lc = QColor(cfg["column_line_color"])
        for i, x in enumerate(colx + [colx[-1] + w]):
            lw_ = cfg.get("edge_line_width", 2) if i in (0, K) else cfg["column_line_width"]
            if lw_ > 0:
                p.setPen(QPen(lc, lw_))
                p.drawLine(QPointF(x, 0), QPointF(x, 480))
        for side in ("left", "right"):      # un lienzo «mania-stage-left/right» manda sobre la imagen generada
            nm = f"mania-stage-{side}.png"
            im, cs = self._canvas_img(nm)
            sel = "canvas:" + nm if im is not None else "mania_stage"
            hd = im is not None and cs == 0.5
            im = im if im is not None else pr.image("mania_stage", nm)
            if im:
                wi = stage_side_width(im, hd)        # como osu!: ancho natural, solo se estira en alto
                r = QRectF(sx - wi if side == "left" else sx + total, 0, wi, 480)
                p.drawImage(r, im)
                self._reg(r, sel)
        bt, _ = self._canvas_img("mania-stage-bottom.png")
        if bt is not None:
            r = QRectF(sx, 480 - bt.height() * total / bt.width(), total, bt.height() * total / bt.width())
            p.drawImage(r, bt)
            self._reg(r, "canvas:mania-stage-bottom.png")
        light = pr.image("mania_stage", "mania-stage-light.png")
        if light:
            for i in range(K):
                if pressed[i]:
                    h = light.height() * w / light.width()
                    p.drawImage(QRectF(colx[i], lp - h, w, h), light)
        hint = pr.image("mania_stage", "mania-stage-hint.png")
        if hint:
            hh = hint.height() * total / hint.width()
            p.drawImage(QRectF(sx, hp - hh / 2, total, hh), hint)
            self._reg(QRectF(sx, hp - hh, total, hh * 2), "mania_stage")
        elif cfg["judgement_line"]:
            p.fillRect(QRectF(sx, hp - 1, total, 2), QColor(255, 255, 255, 160))
        imgs = pr.images("mania_notes") if pr.assets["mania_notes"]["enabled"] else {}

        def nimg(i, suffix=""):
            tp, d = cols[i]
            return imgs.get(f"{gens.note_name(tp, d, rotate, nv['note_shape'])}{suffix}.png")

        def put(img, x, ybottom):
            if img is None:
                return
            h = w * img.height() / img.width()
            p.drawImage(QRectF(x, ybottom - h, w, h), img)
            self._reg(QRectF(x, ybottom - h, w, h), "mania_notes")

        def draw_keys():
            for i in range(K):
                key = pr.image("mania_keys", f"mania-key{cols[i][0]}{'D' if pressed[i] else ''}.png")
                if key:
                    hk = key.height() * w / key.width()
                    r = QRectF(colx[i], 480 - hk, w, hk)
                    p.drawImage(r, key)
                    self._reg(r, "mania_keys")

        if cfg["keys_under_notes"]:          # notas por delante de los receptores (KeysUnderNotes)
            draw_keys()
        for tm, c, ln in notes:
            x = colx[c]
            yh = hp - (tm - t) * speed
            if ln:
                yt = hp - (tm + ln - t) * speed
                if t > tm:
                    yh = hp
                body, tail, head = nimg(c, "L"), nimg(c, "T"), nimg(c, "H")
                if t < tm + ln + 40:
                    # el cuerpo va de centro a centro: queda escondido bajo la cabeza y bajo el final
                    hh = w * head.height() / head.width() if head else 0
                    top, bottom = yt - hh / 2, yh - hh / 2
                    if body and bottom > top:
                        p.drawImage(QRectF(x, top, w, bottom - top), body)
                    if tail:          # osu! dibuja el final volteado en vertical
                        put(tail.transformed(QTransform().scale(1, -1)), x, top + w * tail.height() / tail.width() / 2)
                    put(head, x, yh)
            elif -60 < yh < 540 and t < tm + 40:
                put(nimg(c), x, yh)
        if not cfg["keys_under_notes"]:
            draw_keys()
        ln_img = pr.image("mania_lighting", "lightingN.png")
        shown = False
        for tm, c, ln in notes:
            if 0 <= t - tm <= 220:
                shown = True
                if ln_img:
                    p.setOpacity(1 - (t - tm) / 220)
                    self._img(p, ln_img, QPointF(colx[c] + w / 2, hp), w * 2.4)
                    p.setOpacity(1.0)
        cx = sx + total / 2
        if shown:
            img = pr.image("mania_hits", "mania-hit300.png")
            if img:
                jw = img.width() * 480 / 768          # tamaño real: imagen 1x en la pantalla de 480 de mania
                self._img(p, img, QPointF(cx, cfg["score_position"]), jw)
                jh = jw * img.height() / img.width()
                self._reg(QRectF(cx - jw / 2, cfg["score_position"] - jh / 2, jw, jh), "mania_hits")
        digits = [pr.image("combo_font", f"combo-{d}.png") for d in "128"]
        if all(digits):          # contador con tus dígitos, superposición incluida (como ComboOverlap)
            f = 480 / 768            # imagen 1x a su tamaño real en la pantalla de 480 de mania
            hgt = digits[0].height() * f
            ov = pr.assets["combo_font"]["overlap"] * f
            tot = sum(d.width() * f for d in digits) - ov * (len(digits) - 1)
            x = cx - tot / 2
            for d in digits:
                p.drawImage(QRectF(x, cfg["combo_position"] - hgt / 2, d.width() * f, hgt), d)
                x += d.width() * f - ov
            self._reg(QRectF(cx - tot / 2, cfg["combo_position"] - hgt / 2, tot, hgt), "combo_font")
        else:
            self._text(p, QRectF(cx - 80, cfg["combo_position"] - 24, 160, 48), "128", 40, "#ffffff", True,
                       Qt.AlignmentFlag.AlignCenter)
        # interfaz que osu! dibuja por su cuenta: barra de vida, puntuación y precisión
        p.fillRect(QRectF(sx + total + 6, 200, 7, 270), QColor(255, 255, 255, 210))
        self._text(p, QRectF(W - 260, 0, 252, 34), "00000000", 32, "#ffffff", True,
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._text(p, QRectF(W - 200, 30, 192, 26), "100.00%", 22, "#ffffff", True,
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # ---- tiradores: todo lo que osu! deja mover desde skin.ini ----------
        top = max(10, hp - 60)
        self._marker(p, QRectF(sx - 8, hp - 10, total + 16, 20), "", "hit_position", orig, Qt.CursorShape.SizeVerCursor)
        if self.edit_mode:
            p.setPen(QPen(ACCENT, 1.2 / self._k, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(sx - 40, hp), QPointF(sx + total + 40, hp))
        self._marker(p, QRectF(sx - 120, hp - 10, 100, 20), "HitPosition", "hit_position", orig, Qt.CursorShape.SizeVerCursor)
        self._marker(p, QRectF(sx - 120, lp - 10 + 24, 100, 20), "LightPosition", "light_position", orig, Qt.CursorShape.SizeVerCursor)
        self._marker(p, QRectF(sx + total + 20, cfg["score_position"] - 10, 100, 20), "ScorePosition", "score_position", orig,
                     Qt.CursorShape.SizeVerCursor)
        self._marker(p, QRectF(sx + total + 20, cfg["combo_position"] - 10, 100, 20), "ComboPosition", "combo_position", orig,
                     Qt.CursorShape.SizeVerCursor)
        kv = pr.assets["mania_keys"]
        lift = kv.get("key_lift", 0)
        hk0 = w * kv["key_height"] / 100
        orig_k = dict(orig, hk0=hk0)
        self._marker(p, QRectF(sx + total + 20, 480 - lift - hk0 / 2 - 10, 100, 20), "Receptores", "key_lift", orig_k,
                     Qt.CursorShape.SizeVerCursor)
        self._marker(p, QRectF(sx - 7, top - 40, 14, 40), "↔", "w_left", orig, Qt.CursorShape.SizeHorCursor)
        self._marker(p, QRectF(sx + total - 7, top - 40, 14, 40), "↔", "w_right", orig, Qt.CursorShape.SizeHorCursor)
        self._handles.append({"rect": QRectF(sx, 0, total, hp - 30), "kind": "move", "orig": orig,
                              "cursor": Qt.CursorShape.SizeAllCursor})
        if self.edit_mode:
            self._text(p, QRectF(sx, 2, total, 18), f"ColumnStart {round(sx)} · ColumnWidth {w} · {K}K", 11, "#ff9fcb", True,
                       Qt.AlignmentFlag.AlignCenter)

    # ---- menú (unidades de interfaz 1366x768 como la wiki) -----------------------------------------
    def _ui_img(self, name, eid):
        img = self.project.image(eid, name)
        return img, self.project.ui_scale(eid)

    def _scene_menu(self, p):
        pr = self.project
        W, H = self.logical()
        T = self._text
        bg = pr.image("menu_bg")
        if bg:
            p.drawImage(QRectF(0, 0, W, H), bg)
        else:
            p.fillRect(QRectF(0, 0, W, H), QColor("#10131c"))
        self._reg(QRectF(0, 0, W, H), "menu_bg")
        big, bgs = self._ui_img("mode-osu.png", "mode_icons")
        if big:
            r = QRectF(W * 0.62 - big.width() * bgs / 2, H / 2 - big.height() * bgs / 2, big.width() * bgs, big.height() * bgs)
            p.setOpacity(0.18)
            p.drawImage(r, big)
            p.setOpacity(1.0)
            self._reg(r, "mode_icons", "mode-osu.png", big)
        # clasificación local
        rank, rs = self._ui_img("ranking-S-small.png", "ranking")
        for i in range(8):
            y = 155 + i * 52
            p.fillRect(QRectF(8, y, 360, 46), QColor(0, 0, 0, 110))
            p.fillRect(QRectF(8, y, 44, 44), QColor(90 + i * 12, 70, 120, 200))
            if rank:
                r = QRectF(58, y + 23 - rank.height() * rs / 2, rank.width() * rs, rank.height() * rs)
                p.drawImage(r, rank)
                self._reg(r, "ranking", "ranking-S-small.png", rank)
            T(p, QRectF(104, y, 250, 23), "Guest", 20, bold=True)
            T(p, QRectF(104, y + 23, 250, 21), "Score: 103 314 (73x)", 14)
        # lista de canciones: conjunto (naranja/rosa), dificultades (azul) y la seleccionada (blanca)
        mp = pr.assets["menu_panel"]
        panel, ps = self._ui_img("menu-button-background.png", "menu_panel")
        star, _ss = self._ui_img("star.png", "stars")
        small, sms = self._ui_img("mode-osu-small.png", "mode_icons")
        specs = [(875, 106, "#ff9a3d", "Telephoc Hype", "Backfire", 0), (863, 200, "#e060b0", "Imperial Circus Dead Decadence", "Collab", 0),
                 (768, 288, "#1da1f2", "Minorsonek's Easy", "ChuuritsuTv", 2), (754, 378, "#ffffff", "Normal", "ChuuritsuTv", 3),
                 (840, 474, "#ff9a3d", "Utakatastrofi", "HelloSCV", 0), (850, 566, "#ff9a3d", "Uta ni Katachi wa nai keredo", "Hatsune Miku", 0)]
        for x, y, color, title, artist, stars in specs:
            if panel:
                r = QRectF(x, y, panel.width() * ps, panel.height() * ps)
                p.drawImage(r, self._tint(panel, QColor(color)))
                self._reg(r, "menu_panel", "menu-button-background.png", panel)
            else:
                p.fillRect(QRectF(x, y, 560, 90), QColor(color))
            tc = mp["active_text"] if color == "#ffffff" else mp["inactive_text"]
            if stars:
                if small:
                    r = QRectF(x + 24, y + 26, small.width() * sms, small.height() * sms)
                    p.drawImage(r, small)
                    self._reg(r, "mode_icons", "mode-osu-small.png", small)
                if rank:
                    p.drawImage(QRectF(x + 70, y + 14, rank.width() * rs, rank.height() * rs), rank)
                if star:
                    for k in range(stars):
                        r = QRectF(x + 176 + k * 22, y + 66, 18, 18)
                        p.drawImage(r, star)
                        self._reg(r, "stars", "star.png", star)
            T(p, QRectF(x + 176, y + 10, 520, 30), title, 21, tc, True)
            T(p, QRectF(x + 176, y + 40, 520, 24), artist, 15, tc)
        # barras superior e inferior (lienzos o, si no hay, las de osu!); pulsar abre su editor
        top, ts = self._canvas_img("songselect-top.png")
        r = QRectF(0, 0, W, 80)
        if top is not None:
            r = QRectF(0, 0, top.width() * ts, top.height() * ts)
            p.drawImage(r, top)
        else:
            p.fillRect(r, QColor(0, 0, 0, 215))
        self._reg(r, "canvas:songselect-top.png")
        T(p, QRectF(36, 4, 760, 26), "Imperial Circus Dead Decadence - Intro ver. [Normal]", 21, bold=True)
        T(p, QRectF(36, 30, 760, 20), "Mapped by Guest", 14)
        T(p, QRectF(8, 50, 760, 20), "Length: 00:31  BPM: 71-140  Objects: 45", 14)
        bot, bs = self._canvas_img("songselect-bottom.png")
        r = QRectF(0, H - 90, W, 90)
        if bot is not None:
            r = QRectF(0, H - bot.height() * bs, bot.width() * bs, bot.height() * bs)
            p.drawImage(r, bot)
        else:
            p.fillRect(r, QColor(0, 0, 0, 200))
        self._reg(r, "canvas:songselect-bottom.png")
        p.fillRect(QRectF(880, H - 82, 52, 52), QColor("#5b6b8c"))
        T(p, QRectF(940, H - 78, 320, 26), "Guest", 20, bold=True)
        T(p, QRectF(940, H - 52, 320, 22), "Performance: 0pp   Lv1", 14)
        # botones inferiores a tamaño natural (la imagen manda, como en el juego)
        for fname, x in (("selection-mode.png", 224), ("selection-mods.png", 317), ("selection-random.png", 394),
                         ("selection-options.png", 472)):
            img, s = self._ui_img(fname, "sel_buttons")
            if img:
                r = QRectF(x, H - img.height() * s - 2, img.width() * s, img.height() * s)
                p.drawImage(r, img)
                self._reg(r, "sel_buttons", fname, img)
        for i, mod in enumerate(("hidden", "hardrock", "doubletime")):      # mods activos de ejemplo
            img, s = self._ui_img(f"selection-mod-{mod}.png", "mod_icons")
            if img:
                r = QRectF(600 + i * 40, H - 74, img.width() * s * 0.7, img.height() * s * 0.7)
                p.drawImage(r, img)
                self._reg(r, "mod_icons", f"selection-mod-{mod}.png", img)
        back, bks = self._ui_img("menu-back.png", "menu_back")
        if back:
            r = QRectF(0, H - back.height() * bks - 6, back.width() * bks, back.height() * bks)
            p.drawImage(r, back)
            self._reg(r, "menu_back", "menu-back.png", back)
        logo = pr.image("menu_logo")
        if logo:
            r = QRectF(W - 150, H - 130, 240, 240)
            p.drawImage(r, logo)
            self._reg(r, "menu_logo")
        tab, tbs = self._ui_img("selection-tab.png", "menu_tab")
        labels = ["Collections", "Recently Played", "By Artist", "By Difficulty", "No Grouping"]
        for i, lab in enumerate(labels):
            x = W - 30 - (5 - i) * 128
            if tab:
                r = QRectF(x, 56, tab.width() * tbs, tab.height() * tbs)
                p.drawImage(r, tab if i == 4 else self._tint(tab, QColor("#e0425a")))
                self._reg(r, "menu_tab", "selection-tab.png", tab)
                T(p, r, lab, 13, "#202020" if i == 4 else "#ffffff", True, Qt.AlignmentFlag.AlignCenter)
        T(p, QRectF(W - 560, 8, 200, 40), "Group", 30, "#8fd3ff")
        T(p, QRectF(W - 280, 8, 200, 40), "Sort", 30, "#8fd3ff")

    # ---- pausa / fallo / resultados: lienzos libres sobre posiciones fijas de osu! -----------------
    # ---- pausa / fallo / resultados: imágenes del elemento (o de un lienzo libre con el mismo nombre) ----
    def _res(self, name, eid):
        img, s = self._canvas_img(name)
        if img is not None:
            return img, s, "canvas:" + name
        return self.project.image(eid, name), self.project.ui_scale(eid), eid

    def _put(self, p, name, eid, x, y, anchor="tl"):
        """Dibuja un archivo a tamaño natural; anchor 'tl' (esquina) o 'c' (centro)."""
        img, s, sel = self._res(name, eid)
        if img is None:
            return None
        w, h = img.width() * s, img.height() * s
        r = QRectF(x - w / 2, y - h / 2, w, h) if anchor == "c" else QRectF(x, y, w, h)
        p.drawImage(r, img)
        self._reg(r, sel, name, img)
        return r

    def _full(self, p, name, eid):
        W, H = self.logical()
        img, _s, sel = self._res(name, eid)
        if img is not None:
            p.drawImage(QRectF(0, 0, W, H), img)
            self._reg(QRectF(0, 0, W, H), sel)

    def _game_bg(self, p):
        W, H = self.logical()
        g = QLinearGradient(0, 0, W, H)
        g.setColorAt(0, QColor("#3d3466"))
        g.setColorAt(1, QColor("#1c2a4a"))
        p.fillRect(QRectF(0, 0, W, H), QBrush(g))

    def _pause_buttons(self, p, items):
        W, H = self.logical()
        for name, y in items:
            self._put(p, name, "pause_screen", W / 2, H * y, "c")

    def _scene_pause(self, p):
        self._game_bg(p)
        self._full(p, "pause-overlay.png", "pause_screen")
        self._pause_buttons(p, (("pause-continue.png", .296), ("pause-retry.png", .528), ("pause-back.png", .757)))

    def _scene_fail(self, p):
        self._game_bg(p)
        self._full(p, "fail-background.png", "fail_screen")
        self._pause_buttons(p, (("pause-retry.png", .528), ("pause-back.png", .757)))

    def _scene_results(self, p):
        W, H = self.logical()
        self._game_bg(p)
        T = self._text
        T(p, QRectF(10, 4, 700, 26), "LiSA - L.Miranic [Standard]", 22, "#fff", True)
        T(p, QRectF(10, 30, 700, 20), "Beatmap by Guest", 15, "#ddd")
        T(p, QRectF(10, 50, 700, 20), "Played by Guest on 19/10/2026 11:24:05.", 15, "#ddd")
        self._put(p, "ranking-panel.png", "results_screen", 12, 112)
        pan = QRectF(12, 112, 620, 490)      # osu! pone los números en sitios fijos: no siguen al panel movido
        fixed = "fixed:Números de osu! (posición fija, el juego no deja moverlos; mueve el panel o las etiquetas)"

        sf = self.project.assets["score_font"]
        sdx, sdy = -sf.get("off_x", 0), sf.get("off_y", 0)      # usan los mismos dígitos que la puntuación

        def num(r, text, px, color="#fff"):
            r = r.translated(sdx, sdy)
            T(p, r, text, px, color, True)
            self._reg(r, "score_font", "num:score_font", None)
        num(QRectF(pan.left() + 180, pan.top() + 6, 420, 60), "1000000", 46)
        rows = (("300", "0", "#ffd24d"), ("300", "696", "#7fe0ff"), ("200", "0", "#7bd34f"), ("100", "0", "#53a8ff"),
                ("50", "0", "#9aa0a6"), ("miss!", "0", "#ff4d4d"))
        for i, (a, b, c) in enumerate(rows):
            x, y = pan.left() + 14 + (i % 2) * 300, pan.top() + 110 + (i // 2) * 72
            num(QRectF(x, y, 130, 50), a, 34, c)
            num(QRectF(x + 130, y, 150, 50), b, 34)
        self._put(p, "ranking-maxcombo.png", "results_screen", pan.left() + 10, pan.top() + 330)
        self._put(p, "ranking-accuracy.png", "results_screen", pan.left() + 300, pan.top() + 330)
        num(QRectF(pan.left() + 20, pan.top() + 395, 250, 50), "813", 38)
        num(QRectF(pan.left() + 310, pan.top() + 395, 300, 50), "100.00%", 38)
        self._put(p, "ranking-title.png", "results_screen", W / 2, 70, "c")
        self._put(p, "ranking-graph.png", "results_screen", pan.left() + 10, pan.bottom() + 8)
        self._put(p, "ranking-perfect.png", "results_screen", pan.left() + 470, pan.bottom() + 8)
        self._put(p, f"ranking-{self.rank_shown}.png", "results_screen", W - 260, 300, "c")
        self._put(p, "ranking-replay.png", "results_screen", W - 260, 580, "c")
        back, bs = self.project.image("menu_back", "menu-back.png"), self.project.ui_scale("menu_back")
        if back:
            p.drawImage(QRectF(0, H - back.height() * bs - 6, back.width() * bs, back.height() * bs), back)

    # ---- mods, selección de modo y diálogos (encima de otra pantalla atenuada) -------------------------
    def _overlay_on(self, p, scene, alpha=185):
        getattr(self, "_scene_" + scene)(p)
        self._hits = []           # lo de atrás no se edita desde aquí
        W, H = self.logical()
        p.fillRect(QRectF(0, 0, W, H), QColor(0, 0, 0, alpha))

    def _dlg_button(self, p, r: QRectF, color: str, text: str):
        pr = self.project
        parts = [pr.image("dialog_buttons", f"button-{n}.png") for n in ("left", "middle", "right")]
        if all(parts):
            c = QColor(color)
            lw = parts[0].width() * r.height() / parts[0].height()
            rw = parts[2].width() * r.height() / parts[2].height()
            p.drawImage(QRectF(r.left(), r.top(), lw, r.height()), self._tint(parts[0], c))
            p.drawImage(QRectF(r.left() + lw, r.top(), max(1, r.width() - lw - rw), r.height()), self._tint(parts[1], c))
            p.drawImage(QRectF(r.right() - rw, r.top(), rw, r.height()), self._tint(parts[2], c))
        else:
            p.fillRect(r, QColor(color))
        self._text(p, r, text, int(r.height() * 0.72), "#ffffff", False, Qt.AlignmentFlag.AlignCenter)
        self._reg(r, "dialog_buttons")

    def _scene_effects(self, p):
        """Reproduce el efecto elegido en bucle, con todos sus fotogramas debajo."""
        W, H = self.logical()
        if self._checker is None:
            pm = QPixmap(16, 16)
            pm.fill(QColor("#2a2d36"))
            q = QPainter(pm)
            q.fillRect(0, 0, 8, 8, QColor("#363a47"))
            q.fillRect(8, 8, 8, 8, QColor("#363a47"))
            q.end()
            self._checker = pm
        p.fillRect(QRectF(0, 0, W, H), QColor("#151821"))
        e = self.effect
        if e is None or e not in self.project.effects:
            self._text(p, QRectF(0, 0, W, H), tr("Crea o elige un efecto en «✨ Efectos»"), 30, "#8a91a3", False,
                       Qt.AlignmentFlag.AlignCenter)
            return
        key = json.dumps(e, sort_keys=True)
        if self._fx_cache[0] != key:
            animated = core.EFFECT_EVENTS[e["event"]][1]
            n = max(1, int(e.get("frames", 12))) if animated else 1
            frames = [gens.render_effect(e, (i / max(1, n - 1)) if animated else 0.35, 256)[0] for i in range(n)]
            self._fx_cache = (key, frames)
        frames = self._fx_cache[1]
        idx = int(self.fx_t / 1000 * max(1, e.get("fps", 30))) % len(frames)
        big = QRectF(W / 2 - 220, 60, 440, 440)
        p.fillRect(big, QBrush(self._checker))
        p.drawImage(big, frames[idx])
        self._text(p, QRectF(0, 10, W, 40), f"{e.get('name', '')} — {core.EFFECT_EVENTS[e['event']][2]}", 22, "#ffffff",
                   True, Qt.AlignmentFlag.AlignCenter)
        step = min(90.0, (W - 40) / max(1, len(frames)))
        for i, im in enumerate(frames):
            r = QRectF(20 + i * step, 560, step - 6, step - 6)
            p.fillRect(r, QBrush(self._checker))
            p.drawImage(r, im)
            if i == idx:
                p.setPen(QPen(ACCENT, 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r)

    def _digits(self, p, eid, prefix, text, x, y, scale, align="l", overlap=0, bottom=False, movable=True):
        """Dibuja un número con las imágenes de dígitos a su tamaño real, como osu! (las imágenes 1x se ven a sus
        píxeles en la pantalla base de 768 de alto; scale = cuánto las escala osu!). Devuelve el rect o None."""
        names = {",": "comma", ".": "dot", "%": "percent", "x": "x"}
        imgs = [self.project.image(eid, f"{prefix}-{names.get(ch, ch)}.png") for ch in text]
        if not all(imgs):
            return None
        f = scale
        h = imgs[0].height() * f
        if bottom:
            y -= h
        tot = sum(i.width() * f for i in imgs) - overlap * f * (len(imgs) - 1)
        x0 = x - tot if align == "r" else x
        cx = x0
        r = QRectF()
        for im in imgs:
            dr = QRectF(cx, y, im.width() * f, im.height() * f)
            p.drawImage(dr, im)
            b = self._opaque(im)
            if b is not None:
                tight = QRectF(dr.left() + b.left() * f, dr.top() + b.top() * f, b.width() * f, b.height() * f)
                r = tight if r.isNull() else r.united(tight)
            cx += im.width() * f - overlap * f
        if r.isNull():
            r = QRectF(x0, y, tot, h)
        if movable:          # copia del número para verlo moverse; scale = cuánto se mueve en osu! por cada px
            snap = QImage(max(1, int(r.width() * 2)), max(1, int(r.height() * 2)), QImage.Format.Format_ARGB32_Premultiplied)
            snap.fill(Qt.GlobalColor.transparent)
            q = QPainter(snap)
            q.scale(2, 2)
            q.translate(-r.left(), -r.top())
            cx = x0
            for im in imgs:
                q.drawImage(QRectF(cx, y, im.width() * f, im.height() * f), im)
                cx += im.width() * f - overlap * f
            q.end()
            self._hits.append((r, eid, "num:" + eid, (snap, r, scale)))
        else:
            self._reg(r, eid)
        return r

    def _scene_ui(self, p):
        """Interfaz de juego: barra de vida, puntuación, precisión, combo, clasificación y botón skip."""
        pr = self.project
        W, H = self.logical()
        g = QLinearGradient(0, 0, W, H)
        g.setColorAt(0, QColor("#3d3466"))
        g.setColorAt(1, QColor("#1c2a4a"))
        p.fillRect(QRectF(0, 0, W, H), QBrush(g))
        for name, (bx, by) in (("scorebar-bg.png", (0, 0)), ("scorebar-colour.png", (5, 16))):   # osu! pone el relleno en (5,16)
            img, s = self._ui_img(name, "hp_bar")
            if img:
                r = QRectF(bx, by, img.width() * s, img.height() * s)
                p.drawImage(r, img)
                if name == "scorebar-bg.png":
                    self._reg(r, "hp_bar", "scorebar-bg.png", img)      # arrastrable (mueve fondo y relleno)
        ov = core.digit_overlap(pr, "score_font")
        if not self._digits(p, "score_font", "score", "00727550", W - 10, 0, 0.96, "r", ov):     # escalas de osu!
            self._text(p, QRectF(W - 300, 0, 290, 52), "00727550", 44, "#fff", True, Qt.AlignmentFlag.AlignRight)
        top = pr.image("score_font", "score-0.png")
        acc = self._digits(p, "score_font", "score", "98.62%", W - 17, 9 + ((top.height() - pr.assets["score_font"].get("off_y", 0)) * 0.96 if top else 60), 0.576,
                           "r", ov)
        if acc is None:
            self._text(p, QRectF(W - 200, 52, 190, 34), "98.62%", 28, "#fff", True, Qt.AlignmentFlag.AlignRight)
        pie_x = (acc.left() if acc else W - 200) - 30
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawEllipse(QPointF(pie_x, 70), 14, 14)
        p.setBrush(QColor("#9acd32"))
        p.drawPie(QRectF(pie_x - 14, 56, 28, 28), 90 * 16, -100 * 16)
        self._reg(QRectF(pie_x - 16, 54, 32, 32), "fixed:Reloj de la canción (lo dibuja osu!, no se puede mover)")
        if not self._digits(p, "combo_font", "combo", "123x", 6, H - 4, 1.0, "l", core.digit_overlap(pr, "combo_font"), True):
            self._text(p, QRectF(10, H - 74, 300, 64), "123x", 56, "#fff", True)
        for i in range(4):          # barras de clasificación
            y = 260 + i * 58
            p.fillRect(QRectF(0, y, 190, 52), QColor(255, 255, 255, 40 if i != 2 else 90))
            self._text(p, QRectF(6, y, 180, 26), "Guest", 20, "#fff", False)
            self._digits(p, "score_font", "scoreentry", f"{980000 - i * 13117:,}", 6, y + 28, 1.0, "l", movable=False)
        img, s = self._ui_img("play-skip.png", "skip")
        if img:
            r = QRectF(W - img.width() * s, H - img.height() * s, img.width() * s, img.height() * s)
            p.drawImage(r, img)
            self._reg(r, "skip", "play-skip.png", img)

    def _scene_mods(self, p):
        W, H = self.logical()
        self._overlay_on(p, "menu")
        T = self._text
        T(p, QRectF(8, 0, W - 16, 70), "Los mods ofrecen maneras diferentes de disfrutar del juego. Algunos de ellos afectarán "
          "a la puntuación que obtengas al jugar, otros simplemente están para divertirse.", 26, "#fff", False,
          Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap)
        T(p, QRectF(0, 100, W, 60), "Score Multiplier: 1.00x", 40, "#fff", False, Qt.AlignmentFlag.AlignCenter)
        rows = (("Menos dificultad", "#5ad65a", ("easy", "nofail", "halftime")),
                ("Más dificultad", "#ff5a2a", ("hardrock", "suddendeath", "doubletime", "hidden", "flashlight")),
                ("Especiales", "#ffffff", ("relax", "relax2", "spunout", "autoplay", "scorev2")))
        for i, (label, color, mods) in enumerate(rows):
            cy = 218 + i * 96
            T(p, QRectF(38, cy - 25, 300, 50), label, 34, color)
            for j, mod in enumerate(mods):
                name = f"selection-mod-{mod}.png"
                img, s = self._ui_img(name, "mod_icons")
                if img:
                    r = QRectF(354 + j * 105, cy - img.height() * s / 2, img.width() * s, img.height() * s)
                    p.drawImage(r, img)
                    self._reg(r, "mod_icons", name, img)
        self._dlg_button(p, QRectF(322, 513, 723, 55), "#e8380d", "1. Desactivar todos")
        self._dlg_button(p, QRectF(322, 593, 723, 55), "#8a8a8a", "2. Cerrar")

    def _scene_modes(self, p):
        self._overlay_on(p, "menu", 120)
        p.fillRect(QRectF(224, 166, 448, 510), QColor(0, 0, 0, 110))
        for i, (mode, label) in enumerate((("mania", "osu!mania"), ("fruits", "osu!catch"), ("taiko", "osu!taiko"), ("osu", "osu!"))):
            cy = 230 + i * 128
            name = f"mode-{mode}-med.png"
            img, s = self._ui_img(name, "mode_icons")
            if img:
                r = QRectF(288 - img.width() * s / 2, cy - img.height() * s / 2, img.width() * s, img.height() * s)
                p.drawImage(r, img)
                self._reg(r, "mode_icons", name, img)
            self._text(p, QRectF(375, cy - 30, 300, 60), label, 36, "#ffffff", True)

    def _scene_dialogs(self, p):
        self._overlay_on(p, "home", 170)
        for i, (color, text) in enumerate((("#2a5a9a", "1. Ver perfil"), ("#e08a10", "2. Cerrar sesión"),
                                           ("#e08a10", "3. Cambiar foto de perfil"), ("#9a9a9a", "4. Cerrar"))):
            self._dlg_button(p, QRectF(402, 100 + i * 80, 724, 55), color, text)

    def _scene_home(self, p):
        """Menú principal de osu!stable (posiciones medidas a 1366x768). Solo se exporta el fondo."""
        pr = self.project
        W, H = self.logical()
        T = self._text
        bg = pr.image("menu_bg")
        if bg:
            p.drawImage(QRectF(0, 0, W, H), bg)
        else:
            p.fillRect(QRectF(0, 0, W, H), QColor("#1a1033"))
        self._reg(QRectF(0, 0, W, H), "menu_bg")
        p.fillRect(QRectF(0, 0, W, 86), QColor(0, 0, 0, 130))
        p.fillRect(QRectF(0, H - 82, W, 82), QColor(0, 0, 0, 90))
        # barra superior: jugador invitado y datos
        p.fillRect(QRectF(7, 7, 72, 72), QColor("#5b6b8c"))
        T(p, QRectF(86, 0, 260, 24), "Guest", 20, "#fff")
        for i, line in enumerate(("Performance: 0pp", "Accuracy: 0.00%", "Lv1")):
            T(p, QRectF(86, 22 + i * 18, 200, 18), line, 13, "#fff")
        p.fillRect(QRectF(128, 70, 196, 7), QColor("#d9b44a"))
        T(p, QRectF(339, 0, 560, 26), "¡Tienes un total de 42 mapas!", 19, "#fff")
        T(p, QRectF(339, 24, 560, 26), "Duración de la sesión actual: 08:54", 19, "#fff")
        T(p, QRectF(339, 48, 560, 26), "Hora actual: 11:24", 19, "#fff")
        for i, ch in enumerate(("⏮", "▶", "⏸", "⏹", "⏭", "i", "☰")):
            T(p, QRectF(1140 + i * 31, 6, 30, 30), ch, 20, "#fff", True, Qt.AlignmentFlag.AlignCenter)
        # botones (detrás del logo, con el borde derecho inclinado)
        for (lab, y0, x1) in (("Play", 186, 1079), ("Edit", 290, 1090), ("Options", 394, 1088), ("Exit", 497, 1077)):
            h = 86
            g = QLinearGradient(640, 0, x1, 0)
            g.setColorAt(0, QColor("#6d4fe6"))
            g.setColorAt(1, QColor("#8a6cf5"))
            path = QPainterPath()
            path.addPolygon(QPolygonF([QPointF(640, y0), QPointF(x1 - 14, y0), QPointF(x1, y0 + h), QPointF(640, y0 + h)]))
            p.fillPath(path, QBrush(g))
            f = QFont(self._family())
            f.setPixelSize(50)
            f.setItalic(True)
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(783, y0, 260, h), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), lab)
        # logo encima
        logo = pr.image("menu_logo")
        cx, cy, R = 483, 383, 267
        if logo:
            p.drawImage(QRectF(cx - R, cy - R, 2 * R, 2 * R), logo)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(cx, cy), R, R)
            p.setBrush(QColor("#ee6ca6"))
            p.drawEllipse(QPointF(cx, cy), R - 30, R - 30)
            T(p, QRectF(cx - R, cy - R, 2 * R, 2 * R), "osu!", 150, "#fff", True, Qt.AlignmentFlag.AlignCenter)
        # pestaña osu!direct y pie
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setBrush(QColor(0, 0, 0, 160))
        p.drawRoundedRect(QRectF(W - 34, 246, 40, 276), 6, 6)
        p.save()
        p.translate(W - 14, 384)
        p.rotate(90)
        T(p, QRectF(-110, -16, 220, 32), "osu!direct", 26, "#fff", False, Qt.AlignmentFlag.AlignCenter)
        p.restore()
        T(p, QRectF(6, H - 50, 70, 44), "ppy", 38, "#fff", True)
        T(p, QRectF(68, H - 44, 220, 18), "ppy powered 2007-2026", 12, "#fff", True)
        T(p, QRectF(68, H - 28, 220, 18), "osu.ppy.sh", 12, "#fff")


# ======================================================================
# Páginas
# ======================================================================
class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo proyecto")
        self.setMinimumWidth(480)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Future Funk Cyan")
        self.author = QLineEdit()
        self.author.setPlaceholderText("Nyroxt")
        self.base = QLineEdit(str(PROJECTS_DIR))
        browse = QPushButton("Examinar…")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.base, 1)
        row.addWidget(browse)
        self.target = QLabel()
        self.target.setObjectName("muted")
        form = QFormLayout()
        form.addRow("Nombre de la skin", self.name)
        form.addRow("Autor", self.author)
        form.addRow("Carpeta base", row)
        form.addRow("Se creará en", self.target)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.buttons)
        for w in (self.name, self.base):
            w.textChanged.connect(self._refresh)
        self._refresh()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta base", self.base.text())
        if d:
            self.base.setText(d)

    def _refresh(self):
        ok = bool(self.name.text().strip()) and bool(self.base.text().strip())
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)
        self.target.setText(str(Path(self.base.text() or ".") / safe_name(self.name.text(), "…")))

    def result_values(self):
        name = self.name.text().strip()
        return name, self.author.text().strip() or "Unknown", Path(self.base.text()) / safe_name(name)


class StartPage(QWidget):
    new_requested = Signal()
    open_requested = Signal()
    open_path = Signal(str)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("NYROXT'S OSU! SKIN CREATOR")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Standard · Taiko · Catch · Mania · Menú — diseña, prueba en vivo y exporta un .osk")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_b = QPushButton("Nuevo proyecto")
        new_b.setObjectName("primary")
        new_b.clicked.connect(self.new_requested)
        open_b = QPushButton("Abrir proyecto…")
        open_b.clicked.connect(self.open_requested)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(new_b)
        row.addWidget(open_b)
        row.addStretch(1)
        self.recent = QListWidget()
        self.recent.setFixedWidth(620)
        self.recent.setMaximumHeight(180)
        self.recent.itemActivated.connect(lambda it: self.open_path.emit(it.data(Qt.ItemDataRole.UserRole)))
        rl = QLabel("Proyectos recientes")
        rl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo = next((f for f in [BASE_DIR / "menu_img" / "logo.png"] + sorted((BASE_DIR / "menu_img").glob("*.png"))
                     if f.is_file()), None) if (BASE_DIR / "menu_img").is_dir() else None
        pm = QPixmap(str(logo)) if logo else QPixmap()
        if not pm.isNull():          # el logo reemplaza al título y al subtítulo
            title.setPixmap(pm.scaledToWidth(min(640, pm.width()), Qt.TransformationMode.SmoothTransformation))
            lay.addWidget(title)
        else:
            lay.addWidget(title)
            lay.addWidget(sub)
        lay.addSpacing(18)
        lay.addLayout(row)
        lay.addSpacing(18)
        lay.addWidget(rl)
        lay.addWidget(self.recent, 0, Qt.AlignmentFlag.AlignCenter)

    def set_recent(self, paths):
        self.recent.clear()
        for path in paths:
            if (Path(path) / "project.json").is_file():
                it = QListWidgetItem(f"{Path(path).name}   —   {path}")
                it.setData(Qt.ItemDataRole.UserRole, path)
                self.recent.addItem(it)


class EditorPage(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(230)
        self.tree.currentItemChanged.connect(self._on_select)
        self.tree.itemChanged.connect(self._on_check)
        b_gif = QPushButton("＋ Animación desde GIF")
        b_gif.setToolTip("Separa el GIF en fotogramas nombre-0.png, nombre-1.png…")
        b_gif.clicked.connect(self.add_gif)
        brow = QHBoxLayout()
        brow.addWidget(b_gif)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.tree, 1)
        ll.addLayout(brow)
        self.preview = PreviewWidget()
        self.props = PropertiesPanel()
        self.cpanel = CanvasPanel()
        self.right = QStackedWidget()
        self.right.addWidget(self.props)
        self.right.addWidget(self.cpanel)
        self.fxpanel = EffectPanel()
        self.right.addWidget(self.fxpanel)
        self.slpanel = SlotPanel()
        self.right.addWidget(self.slpanel)
        self.slpanel.changed.connect(self.changed)
        self.opanel = CanvasPanel()          # capas de la escena (imágenes y textos libres)
        self.right.addWidget(self.opanel)
        self.opanel.changed.connect(self._canvas_changed)
        self.opanel.layer_selected.connect(self._panel_layer)
        self.preview.enable_mode.connect(self._enable_mode)
        self.fxpanel.changed.connect(self._fx_changed)
        self.fxpanel.removed.connect(lambda: (self._build_tree(), self.changed.emit()))
        self.props.edited.connect(self._on_edited)
        self.props.structure_changed.connect(self._rebuild_keep)
        self.cpanel.changed.connect(self._canvas_changed)
        self.cpanel.structure_changed.connect(self._rebuild_keep)
        self.cpanel.layer_selected.connect(self._panel_layer)
        self.preview.pick.connect(self.select_id)
        self.preview.pick_obj.connect(self._pick_obj)
        self.preview.obj_moved.connect(self._obj_moved)
        self.preview.obj_menu.connect(self._obj_menu)
        self.preview.mania_edit.connect(self._mania_edit)
        self.preview.layer_picked.connect(self._preview_layer)
        self.preview.layer_changed.connect(self._layer_dragged)
        self.preview.layer_delete.connect(lambda: self._active_panel().del_layer())

        self.scene_box = QComboBox()
        for sid, label in SCENES:
            self.scene_box.addItem(label, sid)
        self.scene_box.currentIndexChanged.connect(lambda i: self._set_scene(self.scene_box.itemData(i)))
        self.keys_box = QComboBox()
        self.keys_box.currentIndexChanged.connect(self._set_keys)
        self.aspect_box = QComboBox()
        self.aspect_box.addItems(list(ASPECTS))
        self.aspect_box.setToolTip("Relación de aspecto de la pantalla de referencia (osu! mide las X con alto 480)")
        self.aspect_box.currentTextChanged.connect(self._set_aspect)
        self.lib = LibraryDialog(self)
        self.lib.add_image.connect(lambda n: self._lib_add_image(n))
        self.lib.add_text.connect(self._lib_add_text)
        self.lib.changed.connect(self._canvas_changed)
        self.lib.panel.layer_selected.connect(self._panel_layer)
        self.preview.lib_dropped.connect(self._lib_add_image)
        b_lib = QPushButton("Recursos")
        b_lib.setToolTip("Carpeta global de recursos: arrastra imágenes o añade texto en la escena abierta")
        b_lib.clicked.connect(lambda: (self.lib.show(), self.lib.raise_()))
        self.hist, self.hpos, self.saved_snap, self._restoring = [], 0, None, False
        self._hist_timer = QTimer(self)
        self._hist_timer.setSingleShot(True)
        self._hist_timer.setInterval(350)
        self._hist_timer.timeout.connect(self._push)
        self.changed.connect(self._schedule_push)
        self.undo_btn = QPushButton("↶ Deshacer")
        self.undo_btn.setToolTip("Deshacer el último cambio (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.undo)
        self.redo_btn = QPushButton("↷ Rehacer")
        self.redo_btn.setToolTip("Rehacer (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.redo)
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        self.rank_box = QComboBox()
        for code, label in (("XH", "Rango SS plateado (XH)"), ("X", "Rango SS (X)"), ("SH", "Rango S plateado (SH)"),
                            ("S", "Rango S"), ("A", "Rango A"), ("B", "Rango B"), ("C", "Rango C"), ("D", "Rango D")):
            self.rank_box.addItem(label, code)
        self.rank_box.setCurrentIndex(3)
        self.rank_box.setToolTip("Qué letra grande se ve en los resultados (haz clic en ella para cambiar su texto y colores)")
        self.rank_box.currentIndexChanged.connect(lambda i: (setattr(self.preview, "rank_shown", self.rank_box.itemData(i)),
                                                             self.preview.update()))
        self.edit_chk = QCheckBox("Editar con el ratón")
        self.edit_chk.setChecked(True)
        self.edit_chk.toggled.connect(self._set_edit)
        bg = QComboBox()
        for i, t in enumerate(["Fondo oscuro", "Fondo gris", "Fondo claro", "Fondo degradado"]):
            bg.addItem(t, i)
        bg.currentIndexChanged.connect(self._set_bg)
        play = QPushButton("Pausar")
        play.clicked.connect(lambda: self._toggle_play(play))
        restart = QPushButton("Reiniciar")
        restart.clicked.connect(self.preview.restart)
        bar = QHBoxLayout()
        for w in (self.scene_box, self.keys_box, self.rank_box, self.aspect_box, self.edit_chk, b_lib):
            bar.addWidget(w)
        bar.addStretch(1)
        for w in (self.undo_btn, self.redo_btn, bg, play, restart):
            bar.addWidget(w)
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(8, 8, 8, 8)
        ml.addLayout(bar)
        ml.addWidget(self.preview, 1)
        self.hint = QLabel()
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        ml.addWidget(self.hint)
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(mid)
        split.addWidget(self.right)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 720, 380])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(split)
        self._update_hint()

    HINTS = {
        "mania": "Mania: arrastra la línea HitPosition, los marcadores Light/Score/Combo, el escenario (mover) o sus bordes (ancho). "
                 "Todo se guarda como valores de skin.ini; las X se miden con alto 480 y origen en el borde izquierdo, como en osu!.",
        "menu": "Menú: pasa el ratón por encima para ver qué es cada cosa y haz clic para editarla (barras, botones, paneles, estrellas, "
                "iconos de modo y mods…). «★ Estilo rápido del menú» lo cambia todo de una vez. osu! no deja mover estas piezas: se edita su imagen.",
        "canvas": "Lienzo: arrastra capas, usa el cuadro rosa de la esquina para redimensionar, flechas para ajustar 1 px "
                  "(Mayús = 10 px) y Supr para borrar.",
        "effects": "Efectos: se ven en bucle con todos sus fotogramas. Al exportar se guardan como las imágenes que osu! usa en ese "
                   "momento (p. ej. hit300-0.png…); osu! no ejecuta código, solo imágenes.",
        "ui": "Interfaz de juego: haz clic en la barra de vida, la puntuación, la precisión, el combo, las barras de clasificación o el "
              "botón skip para editarlos. El reloj de la canción lo dibuja osu! y no se puede mover.",
        "mods": "Selección de mods: haz clic en un icono para editarlo (o arrástralo); los botones grandes son «Botones de diálogo».",
        "modes": "Selección de modo: los iconos son mode-*-med.png; clic para editar.",
        "dialogs": "Diálogos: osu! tiñe y estira button-left/middle/right en cada botón; aquí ves cómo quedan con sus colores.",
        "home": "Menú principal: solo el fondo se exporta (menu-background.jpg, lo ven los supporters). Reemplázalo con tu imagen o añade objetos con «Recursos».",
        "pause": "Pausa: todo se cambia en el panel de la derecha (fondo, título, estilo de botón y textos). Con «Recursos» pones imágenes o texto libre encima.",
        "fail": "Fallo: cambia el fondo y el texto grande en el panel; los botones son los de la pausa. «Recursos» añade imágenes o texto libre.",
        "results": "Resultados: un solo panel cambia paneles, títulos, textos y letras grandes; osu! dibuja los números encima.",
        "std": "Standard: el área jugable de 512x384 está centrada y 8 px más abajo, como en osu!stable. El cursor sigue tu ratón.",
        "taiko": "Taiko: simulación aproximada; las notas se tiñen de rojo/azul dentro del juego.",
        "catch": "Catch: el catcher sigue tu ratón.",
    }

    def _update_hint(self):
        self.hint.setText(tr(self.HINTS.get(self.preview.scene, "")) + "  " + tr("La prueba definitiva es abrir el .osk en osu!stable."))

    # ---- barra ---------------------------------------------------------------------
    def _toggle_play(self, btn):
        self.preview.playing = not self.preview.playing
        btn.setText("Pausar" if self.preview.playing else "Reproducir")

    def _set_bg(self, i):
        self.preview.bg_mode = i
        self.preview.update()

    def _set_edit(self, on):
        self.preview.edit_mode = on
        self.preview.update()

    def _set_scene(self, sid):
        self.preview.set_scene(sid)
        self.keys_box.setVisible(sid == "mania")
        self.edit_chk.setVisible(sid == "mania")
        self.rank_box.setVisible(sid == "results")
        idx = self.scene_box.findData(sid)
        self.scene_box.blockSignals(True)
        self.scene_box.setCurrentIndex(idx if idx >= 0 else self.scene_box.currentIndex())
        self.scene_box.blockSignals(False)
        self._sync_lib()
        self._update_hint()

    def _set_keys(self, i):
        k = self.keys_box.itemData(i)
        if k:
            self.preview.mania_k = k
            self.preview.update()

    def _set_aspect(self, text):
        if self.project and text in ASPECTS:
            self.project.set("mania_config", "aspect", text)
            self.preview.update()
            self.changed.emit()
            if self.props.eid == "mania_config":
                self.props.show_element(self.project, "mania_config")

    def _refresh_keys(self):
        if not self.project:
            return
        self.keys_box.blockSignals(True)
        self.keys_box.clear()
        for k in self.project.keys():
            self.keys_box.addItem(f"{k}K", k)
        i = self.keys_box.findData(self.preview.mania_k)
        self.keys_box.setCurrentIndex(max(0, i))
        self.keys_box.blockSignals(False)
        self.preview.mania_k = self.keys_box.currentData() or 4
        self.aspect_box.blockSignals(True)
        self.aspect_box.setCurrentText(self.project.get("mania_config", "aspect"))
        self.aspect_box.blockSignals(False)

    # ---- proyecto y árbol ------------------------------------------------------------
    def set_project(self, project: Project):
        self.project = project
        self.preview.project = project
        self.props.project = project
        self.cpanel.project = project
        self.preview.restart()
        self.lib.set_project(project)
        self._refresh_keys()
        self._build_tree(select="hitcircle")
        self.hist, self.hpos = [project.snapshot()], 0
        self.saved_snap = self.hist[0]
        self._update_undo()

    # ---- deshacer / rehacer / descartar -----------------------------------------
    def _schedule_push(self):
        if not self._restoring and self.project is not None:
            self._hist_timer.start()        # agrupa cambios seguidos (p. ej. arrastrar un deslizador)

    def _push(self):
        snap = self.project.snapshot()
        if self.hist and self.hist[self.hpos] == snap:
            return
        del self.hist[self.hpos + 1:]
        self.hist.append(snap)
        if len(self.hist) > 200:
            self.hist.pop(0)
        self.hpos = len(self.hist) - 1
        self._update_undo()

    def _flush(self):
        if self._hist_timer.isActive():
            self._hist_timer.stop()
            self._push()

    def undo(self):
        if self.project is None:
            return
        self._flush()
        if self.hpos > 0:
            self.hpos -= 1
            self._restore(self.hist[self.hpos])

    def redo(self):
        if self.project is None:
            return
        self._flush()
        if self.hpos < len(self.hist) - 1:
            self.hpos += 1
            self._restore(self.hist[self.hpos])

    def discard(self):
        """Vuelve a lo último guardado (y se puede deshacer)."""
        if self.project is None:
            return
        self._flush()
        if self.hist[self.hpos] != self.saved_snap:
            self._restore(self.saved_snap)
            self._push()
            self.project.dirty = False
            self.changed.emit()

    def mark_saved(self):
        if self.project is not None:
            self._flush()
            self.saved_snap = self.project.snapshot()

    def _restore(self, snap):
        self._restoring = True
        try:
            pr = self.project
            pr.restore(snap)
            self.preview._cvc.clear()
            self.preview._tint_cache.clear()
            self.lib.refresh()
            self._refresh_keys()
            self._rebuild_keep()
            if self.right.currentWidget() is self.props and self.props.eid:
                self.props.show_element(pr, self.props.eid, self.props.file)
            self._sync_lib()
        finally:
            self._restoring = False
        self._update_undo()

    def _update_undo(self):
        self.undo_btn.setEnabled(self.hpos > 0)
        self.redo_btn.setEnabled(self.hpos < len(self.hist) - 1)

    def _top(self, label):
        top = QTreeWidgetItem(self.tree, [label])
        top.setFlags(Qt.ItemFlag.ItemIsEnabled)
        return top

    def _build_tree(self, select=None):
        pr = self.project
        self.tree.blockSignals(True)
        self.tree.clear()
        tops = {}
        for mode, label in MODES:
            top = self._top(label)
            if mode not in ("global", "config"):      # casilla: desactivar un modo = usar la skin por defecto de osu!
                top.setFlags(top.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                top.setCheckState(0, Qt.CheckState.Checked if pr.modes.get(mode, True) else Qt.CheckState.Unchecked)
                top.setData(0, Qt.ItemDataRole.UserRole, "mode:" + mode)
            tops[mode] = top
        target = None
        for e in ELEMENTS:
            it = QTreeWidgetItem(tops[e["mode"]], [e["name"]])
            it.setData(0, Qt.ItemDataRole.UserRole, e["id"])
            if e["toggle"]:
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(0, Qt.CheckState.Checked if pr.get(e["id"], "enabled") else Qt.CheckState.Unchecked)
            if e["id"] == select:
                target = it
        for gid, (label, mode, _d, _s) in core.SLOT_GROUPS.items():
            it = QTreeWidgetItem(tops[mode], [label])
            it.setData(0, Qt.ItemDataRole.UserRole, "slots:" + gid)
            if select == "slots:" + gid:
                target = it
        for mode in ("std", "mania", "menu", "ui"):
            it = QTreeWidgetItem(tops[mode], ["Capas (imágenes y textos libres)"])
            it.setData(0, Qt.ItemDataRole.UserRole, "layers:" + mode)
        for mode, items in FIXED_SECTIONS.items():
            for label, name in items:
                it = QTreeWidgetItem(tops[mode], [label])
                it.setData(0, Qt.ItemDataRole.UserRole, "section:" + name)
                if select == "section:" + name:
                    target = it
        top = self._top("Lienzos libres (decoración, perfil…)")
        for c in pr.canvases:
            if c["name"] not in FIXED_NAMES:
                it = QTreeWidgetItem(top, [c["name"]])
                it.setData(0, Qt.ItemDataRole.UserRole, "canvas:" + c["id"])
                if select == "canvas:" + c["id"]:
                    target = it
        add = QTreeWidgetItem(top, ["＋ Añadir…"])
        add.setData(0, Qt.ItemDataRole.UserRole, "add:0")
        top = self._top("✨ Efectos")
        for e in pr.effects:
            it = QTreeWidgetItem(top, [("⌨ " if e.get("mode") == "code" else "✦ ") + e.get("name", "Efecto")])
            it.setData(0, Qt.ItemDataRole.UserRole, "effect:" + e["id"])
            if select == "effect:" + e["id"]:
                target = it
        for label, key in (("＋ Efecto sin código (eventos)", "addfx:nocode"), ("＋ Efecto con código", "addfx:code")):
            it = QTreeWidgetItem(top, [label])
            it.setData(0, Qt.ItemDataRole.UserRole, key)
        for label, items, prefix in (("Animaciones (GIF)", [(a["name"], a["name"]) for a in pr.anims], "anim:"),
                                     ("Recursos propios", [(c["name"], c["name"]) for c in pr.customs], "custom:")):
            top = self._top(label)
            for text, key in items:
                it = QTreeWidgetItem(top, [text])
                it.setData(0, Qt.ItemDataRole.UserRole, prefix + key)
                if select == prefix + key:
                    target = it
        self.tree.expandAll()
        self.tree.blockSignals(False)
        if target:
            self.tree.setCurrentItem(target)
            self._on_select(target, None)
        else:
            self.right.setCurrentWidget(self.props)
            self.props.show_element(pr, None)

    def _current_sel(self):
        cur = self.tree.currentItem()
        return cur.data(0, Qt.ItemDataRole.UserRole) if cur else None

    def _rebuild_keep(self):
        sel = self._current_sel()
        if sel and sel.startswith("custom:") and self.props.custom:
            sel = "custom:" + self.props.custom
        if sel and sel.startswith("anim:") and self.props.anim:
            sel = "anim:" + self.props.anim
        if sel and sel.startswith("canvas:") and not (self.cpanel.cv and self.project.canvas(sel[7:])):
            sel = None
        if sel and sel.startswith("section:") and not any(c["name"] == sel[8:] for c in self.project.canvases):
            sel = None
        self.preview.cv_rev += 1
        self._build_tree(select=sel)
        self.preview.update()
        self.changed.emit()

    def select_id(self, sel):
        if sel.startswith("canvas:"):
            name = sel[7:]
            if name in FIXED_NAMES:
                return self._select_key("section:" + name)
            cv = next((c for c in self.project.canvases if c["name"] == name), None)
            if cv:
                return self._select_key("canvas:" + cv["id"])
            preset = CANVAS_BY_NAME.get(name)
            if preset:
                cv = new_canvas(preset)
                self.project.canvases.append(cv)
                self.project.dirty = True
                self._build_tree(select="canvas:" + cv["id"])
                self.changed.emit()
            return
        self._select_key(sel)

    def _select_key(self, key):
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                it = top.child(j)
                if it.data(0, Qt.ItemDataRole.UserRole) == key:
                    self.tree.setCurrentItem(it)
                    return

    def _canvas_name(self, cid):
        cv = self.project.canvas(cid)
        return cv["name"] if cv else None

    # ---- altas -----------------------------------------------------------------------------------
    def add_canvas(self):
        pr = self.project
        if pr is None:
            return
        names = {tr(k): k for k in CANVAS_PRESETS}
        item, ok = QInputDialog.getItem(self, tr("Nuevo lienzo"), tr("Plantilla:"), list(names), 0, False)
        if not ok:
            return
        cv = new_canvas(names[item])
        pr.canvases.append(cv)
        pr.dirty = True
        self._build_tree(select="canvas:" + cv["id"])
        self.changed.emit()

    def add_custom(self):
        pr = self.project
        if pr is None:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "Añadir recursos propios", "", "Imágenes (*.png *.jpg *.jpeg);;Todos (*)")
        if not files:
            return
        (pr.path / "assets").mkdir(parents=True, exist_ok=True)
        last = None
        for f in files:
            name = safe_name(Path(f).name, "recurso.png")
            dest = pr.path / "assets" / f"custom_{name}"
            shutil.copyfile(f, dest)
            pr._img_cache.pop(str(dest), None)
            rel = str(dest.relative_to(pr.path))
            for c in pr.customs:
                if c["name"] == name:
                    c["file"] = rel
                    break
            else:
                pr.customs.append({"name": name, "file": rel})
            last = name
        pr.dirty = True
        self._build_tree(select="custom:" + last)
        self.changed.emit()

    def add_gif(self):
        pr = self.project
        if pr is None:
            return
        f, _ = QFileDialog.getOpenFileName(self, "Elegir GIF", "", "GIF (*.gif)")
        if not f:
            return
        name, ok = QInputDialog.getText(self, "Animación", "Nombre base de los fotogramas (ej. menu-snow, cursor…):",
                                        text=safe_name(Path(f).stem, "anim"))
        name = safe_name(name, "")
        if not ok or not name:
            return
        if any(a["name"] == name for a in pr.anims):
            QMessageBox.warning(self, APP_NAME, "Ya hay una animación con ese nombre.")
            return
        reader = QImageReader(f)
        frames, delays = [], []
        while reader.canRead() and len(frames) < 600:
            delay = reader.nextImageDelay()
            img = reader.read()
            if img.isNull():
                break
            frames.append(img)
            delays.append(delay)
        if not frames:
            QMessageBox.warning(self, APP_NAME, "No se pudieron leer fotogramas de ese GIF.")
            return
        (pr.path / "assets").mkdir(parents=True, exist_ok=True)
        rels = []
        for i, img in enumerate(frames):
            dest = pr.path / "assets" / f"anim_{name}_{i}.png"
            img.save(str(dest), "PNG")
            rels.append(str(dest.relative_to(pr.path)))
        avg = sum(d for d in delays if d > 0) / max(1, len([d for d in delays if d > 0])) or 100
        fps = int(max(1, min(60, round(1000 / avg))))
        pr.anims.append({"name": name, "fps": fps, "frames": rels})
        pr.dirty = True
        self._build_tree(select="anim:" + name)
        self.changed.emit()
        QMessageBox.information(self, APP_NAME, f"GIF separado en {len(frames)} fotogramas ({fps} fps).\n"
                                f"Se exportarán como {name}-0.png … {name}-{len(frames) - 1}.png "
                                "y skin.ini incluirá AnimationFramerate.")

    # ---- selección ---------------------------------------------------------------------------------
    def _on_select(self, cur, _prev):
        sel = cur.data(0, Qt.ItemDataRole.UserRole) if cur else None
        if not sel:
            return
        pr = self.project
        if sel.startswith("mode:"):
            if sel[5:] in dict(SCENES):
                self._set_scene(sel[5:])
            return
        if sel.startswith("add:"):
            self.add_canvas()
            return
        if sel.startswith("slots:"):
            self.right.setCurrentWidget(self.slpanel)
            self.slpanel.show_group(pr, sel[6:])
            return
        if sel.startswith("layers:"):
            self._set_scene(sel[7:])
            W, H = self.preview.logical()
            self.opanel.show_objects(pr, sel[7:], W, H)
            self.opanel.hint.setText("Capas de esta escena: «＋ Imagen…» o «＋ Texto», arrástralas en el visualizador, "
                                     "▲▼ cambia cuál va delante, R gira 15° (Mayús+R al revés), Supr borra.")
            self.right.setCurrentWidget(self.opanel)
            return
        if sel.startswith("addfx:"):
            e = core.new_effect(sel[6:])
            pr.effects.append(e)
            pr.dirty = True
            self._build_tree(select="effect:" + e["id"])
            self.changed.emit()
            return
        if sel.startswith("effect:"):
            e = next((x for x in pr.effects if x["id"] == sel[7:]), None)
            if e is not None:
                self.right.setCurrentWidget(self.fxpanel)
                self.fxpanel.show_effect(pr, e)
                self.preview.effect = e
                self._set_scene("effects")
            return
        if sel.startswith("section:"):
            name = sel[8:]
            cv = next((c for c in pr.canvases if c["name"] == name), None)
            if cv is None:      # la primera vez se crea desde su plantilla
                cv = new_canvas(CANVAS_BY_NAME[name])
                pr.canvases.append(cv)
                pr.dirty = True
                self.changed.emit()
            return self._open_canvas(cv)
        if sel.startswith("canvas:"):
            cv = pr.canvas(sel[7:])
            if cv is None:
                return
            return self._open_canvas(cv)
        self.right.setCurrentWidget(self.props)
        if sel.startswith("custom:"):
            self.props.show_custom(pr, sel[7:])
            return
        if sel.startswith("anim:"):
            self.props.show_anim(pr, sel[5:])
            return
        self.props.show_element(pr, sel)
        mode = ELEMENT_BY_ID[sel].get("scene", ELEMENT_BY_ID[sel]["mode"])
        if mode in dict(SCENES):
            self._set_scene(mode)
        elif self.preview.scene == "canvas":
            self._set_scene(self.scene_box.currentData() or "std")

    def _open_canvas(self, cv):
        pr = self.project
        self.preview.canvas = cv
        self.preview.cv_rev += 1
        self.right.setCurrentWidget(self.cpanel)
        self.cpanel.show_canvas(pr, cv)
        self.preview.set_scene("canvas")
        self.preview.sel_layer = self.cpanel.sel
        self._sync_lib()
        self._update_hint()

    def _sync_lib(self):
        pr = self.project
        if pr is None:
            return
        sc = self.preview.scene
        self.lib.panel.setEnabled(sc != "canvas")
        if sc != "canvas":
            W, H = self.preview.logical()
            self.lib.panel.show_objects(pr, sc, W, H)
            self.lib.panel.list.setCurrentRow(-1)
        where = {"mania": "Se exportan dentro de las imágenes de los costados del escenario (StageLeft/StageRight); "
                          "lo que tape las columnas se recorta.",
                 "pause": "Se exportan dentro del fondo de la pausa.", "fail": "Se exportan dentro del fondo de fallo.",
                 "home": "Se exportan dentro del fondo del menú principal."}
        self.lib.info.setText("Arrastra un recurso al visualizador o haz doble clic; luego muévelo y redimensiónalo libre.\n"
                              + where.get(sc, "⚠ En esta pantalla osu! no tiene dónde mostrarlos: solo se ven en el editor."))

    def _lib_add_image(self, name, x=None, y=None):
        pr = self.project
        rec = next((r for r in pr.library if r["name"] == name), None) if pr else None
        if rec is None:
            return
        self._active_panel().place_image(rec["file"], x, y)

    def _lib_add_text(self):
        self._active_panel().add_layer("text")

    def _on_check(self, item, _col):
        eid = item.data(0, Qt.ItemDataRole.UserRole)
        if eid and eid.startswith("mode:") and self.project is not None:
            self.project.modes[eid[5:]] = item.checkState(0) == Qt.CheckState.Checked
            self.project.dirty = True
            self.preview.update()
            self.changed.emit()
            return
        if not eid or eid not in ELEMENT_BY_ID or self.project is None:
            return
        self.project.set(eid, "enabled", item.checkState(0) == Qt.CheckState.Checked)
        if self.props.eid == eid:
            self.props.sync_enabled()
        self.preview.update()
        self.changed.emit()

    def _on_edited(self, eid):
        pr = self.project
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                it = top.child(j)
                sel = it.data(0, Qt.ItemDataRole.UserRole)
                if sel in ELEMENT_BY_ID and ELEMENT_BY_ID[sel]["toggle"]:
                    it.setCheckState(0, Qt.CheckState.Checked if pr.get(sel, "enabled") else Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        if eid in ("mania_config", "theme"):
            self._refresh_keys()
        self.preview.update()
        self.changed.emit()

    # ---- mania / lienzos ---------------------------------------------------------------------------
    def _mania_edit(self, edit: dict, final: bool):
        pr = self.project
        if edit:
            pr.set_many("mania_config", edit)
            self.preview.update()
            self.changed.emit()
        if final:
            self.changed.emit()          # entra en el historial de deshacer
        if final and self.props.eid in ("mania_config", "mania_keys"):
            self.props.show_element(pr, self.props.eid)

    def _canvas_changed(self):
        self.preview.cv_rev += 1
        self.preview._cvc.clear()
        self.preview.update()
        self.changed.emit()

    def _panel_layer(self, lid):
        self.preview.sel_layer = lid or None
        self.preview.update()

    def _pick_obj(self, eid, fname):
        """Clic en un objeto: panel solo con lo suyo (sin cambiar de escena)."""
        if fname.startswith("num:"):
            fname = None
        if eid.startswith("canvas:"):
            return self.select_id(eid)
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).data(0, Qt.ItemDataRole.UserRole) == eid:
                    self.tree.setCurrentItem(top.child(j))
        self.tree.blockSignals(False)
        self.right.setCurrentWidget(self.props)
        self.props.show_element(self.project, eid, fname)

    def _obj_moved(self, eid, fname, dx, dy):
        if fname.startswith("num:"):          # números: se mueven con borde transparente (ver core.pad_digits)
            a = self.project.assets[eid]
            sx, sy = (-1, 1) if eid == "score_font" else (1, -1)
            self.project.set_many(eid, {"off_x": a.get("off_x", 0) + round(dx) * sx, "off_y": a.get("off_y", 0) + round(dy) * sy})
            self.preview.update()
            self.changed.emit()
            if self.props.eid == eid:
                self.props.show_element(self.project, eid)
            return
        lay = self.project.lay(fname)
        if lay.get("locked"):
            return
        self.project.set_lay(eid, fname, dx=round(lay.get("dx", 0) + dx), dy=round(lay.get("dy", 0) + dy))
        self._pick_obj(eid, fname)
        self.preview.update()
        self.changed.emit()

    def _obj_menu(self, action, eid, fname):
        pr = self.project
        if action == "lock":
            pr.set_lay(eid, fname, locked=not pr.lay(fname).get("locked"))
        elif action == "reset":
            pr.set_lay(eid, fname, dx=0, dy=0, scale=100)
        elif action == "image":
            self._pick_obj(eid, fname)
            self.props._ov_set()
        if action != "image" and self.props.eid == eid and self.props.file == fname:
            self.props.show_element(pr, eid, fname)
        self.preview.update()
        self.changed.emit()

    def _fx_changed(self):
        e = self.fxpanel.e
        it = self.tree.currentItem()
        if e is not None and it is not None and it.data(0, Qt.ItemDataRole.UserRole) == "effect:" + e["id"]:
            self.tree.blockSignals(True)
            it.setText(0, ("⌨ " if e.get("mode") == "code" else "✦ ") + e.get("name", "Efecto"))
            self.tree.blockSignals(False)
        self.preview.update()
        self.changed.emit()

    def _active_panel(self):
        if self.preview.scene == "canvas":
            return self.cpanel
        if self.right.currentWidget() is self.opanel and self.opanel.cv and self.opanel.cv["id"] == "scene:" + self.preview.scene:
            return self.opanel
        return self.lib.panel

    def _enable_mode(self, mode):
        self.project.modes[mode] = True
        self.project.dirty = True
        sel = self._current_sel()
        self._build_tree(select=sel)
        self.preview.update()
        self.changed.emit()

    def _preview_layer(self, lid):
        panel = self._active_panel()
        if panel.cv is not None:
            if lid:
                panel.select(lid)
            panel.sel = lid or None
            if not lid:
                panel.list.blockSignals(True)
                panel.list.setCurrentRow(-1)
                panel.list.blockSignals(False)
                clear_form(panel.lform)
            else:
                if panel is self.lib.panel:
                    self.lib.show()
        self.preview.update()

    def _layer_dragged(self, final):
        self.preview.cv_rev += 1
        self.changed.emit()
        if final:
            self._active_panel().refresh_layer()


STYLE = """
QWidget { background:#14161c; color:#e6e9f0; font-size:10pt; }
QLabel#title { font-size:26pt; font-weight:bold; color:#53b9ff; }
QLabel#h2 { font-size:13pt; font-weight:bold; color:#53b9ff; }
QLabel#muted { color:#8a91a3; }
QLabel#sect { color:#ff7ab6; font-weight:bold; padding-top:8px; }
QPushButton { background:#232733; border:1px solid #343a4a; border-radius:5px; padding:6px 14px; }
QPushButton:hover { border-color:#53b9ff; }
QPushButton#primary { background:#53b9ff; color:#0b1220; font-weight:bold; }
QLineEdit, QSpinBox, QComboBox, QListWidget, QTreeWidget, QFontComboBox
  { background:#1b1e27; border:1px solid #343a4a; border-radius:4px; padding:3px; }
QSlider::groove:horizontal { height:4px; background:#2a2f3d; border-radius:2px; }
QSlider::handle:horizontal { background:#53b9ff; width:12px; margin:-5px 0; border-radius:6px; }
QTreeWidget::item:selected, QListWidget::item:selected { background:#2b4a63; }
QSplitter::handle { background:#232733; }
QMenuBar, QMenu { background:#1b1e27; }
QMenu::item:selected { background:#2b4a63; }
QStatusBar { color:#8a91a3; }
"""


LIGHT = """
QWidget { background:#f3f4f8; color:#1d2230; }
QLabel#h2 { color:#1f6fb2; } QLabel#muted { color:#5b6275; } QLabel#sect { color:#c2185b; }
QPushButton { background:#ffffff; border:1px solid #c9cedb; }
QPushButton:hover { border-color:#1f6fb2; }
QLineEdit, QSpinBox, QComboBox, QListWidget, QTreeWidget, QFontComboBox, QPlainTextEdit
  { background:#ffffff; border:1px solid #c9cedb; color:#1d2230; }
QTreeWidget::item:selected, QListWidget::item:selected { background:#cfe3f7; color:#1d2230; }
QSlider::groove:horizontal { background:#d5d9e3; }
QSplitter::handle { background:#dde1ea; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.settings = QSettings("nyroxt", "osu-skin-creator")
        self.stack = QStackedWidget()
        self.start = StartPage()
        self.editor = EditorPage()
        self.stack.addWidget(self.start)
        self.stack.addWidget(self.editor)
        self.setCentralWidget(self.stack)
        self.start.new_requested.connect(self.new_project)
        self.start.open_requested.connect(self.open_dialog)
        self.start.open_path.connect(self.open_path)
        self.editor.changed.connect(self._update_title)
        menu = self.menuBar().addMenu("&Archivo")
        self.act_new = self._action(menu, "Nuevo proyecto…", self.new_project, QKeySequence.StandardKey.New)
        self.act_open = self._action(menu, "Abrir proyecto…", self.open_dialog, QKeySequence.StandardKey.Open)
        menu.addSeparator()
        self.act_save = self._action(menu, "Guardar proyecto", self.save, QKeySequence.StandardKey.Save)
        self.act_export = self._action(menu, "Exportar .osk…", self.export, QKeySequence("Ctrl+E"))
        self.act_close = self._action(menu, "Cerrar proyecto", self.close_project, None)
        menu.addSeparator()
        self._action(menu, "Salir", self.close, QKeySequence.StandardKey.Quit)
        edit = self.menuBar().addMenu("&Edición")
        self.act_undo = self._action(edit, "Deshacer", self.editor.undo, QKeySequence.StandardKey.Undo)
        self.act_redo = self._action(edit, "Rehacer", self.editor.redo, QKeySequence("Ctrl+Y"))
        edit.addSeparator()
        self.act_discard = self._action(edit, "Descartar cambios sin guardar…", self.discard, None)
        other = self.menuBar().addMenu("&Otros")
        self._action(other, "Buscar actualizaciones…", self.check_updates, None)
        self._action(other, "Tema del editor: claro / oscuro", self.toggle_theme, None)
        self._action(other, "Idioma…", self.language_dialog, None)
        self._action(other, "Rich Presence (Discord)…", self.presence_dialog, None)
        self._action(other, "Donar a Nyroxt ♥", lambda: QDesktopServices.openUrl(QUrl("https://nyroxt.online/donate.html")), None)
        self._action(other, f"Versión {APP_VERSION}", lambda: None, None)
        tools = self.menuBar().addMenu("&Herramientas")
        self.act_font = self._action(tools, "Importar fuente…", lambda: self.editor.props.import_font() if self.project else None, None)
        self.act_res = self._action(tools, "Añadir recurso propio…", self.editor.add_custom, None)
        self.act_cv = self._action(tools, "Nuevo lienzo…", self.editor.add_canvas, None)
        self.act_gif = self._action(tools, "Añadir GIF…", self.editor.add_gif, None)
        self._refresh_recent()
        self._update_title()
        self._apply_theme()
        self._tr_timer = QTimer(self)                 # traduce lo que aparece en pantalla
        self._tr_timer.timeout.connect(self._retranslate)
        self._tr_timer.start(300)
        self.rpc = presence.RichPresence()
        self._rpc_last = None
        self._rpc_timer = QTimer(self)
        self._rpc_timer.timeout.connect(self._rpc_tick)
        self._rpc_timer.start(3000)
        self._rpc_tick()

    def _action(self, menu, text, slot, shortcut):
        a = QAction(text, self)
        if shortcut is not None:
            a.setShortcut(shortcut)
        a.triggered.connect(lambda _=False: slot())
        menu.addAction(a)
        return a

    def _update_title(self):
        has = self.project is not None
        for a in (self.act_undo, self.act_redo, self.act_discard, self.act_save, self.act_export, self.act_close, self.act_font, self.act_res, self.act_cv, self.act_gif):
            a.setEnabled(has)
        if has:
            self.setWindowTitle(f"{self.project.name}{'*' if self.project.dirty else ''} — {APP_NAME}")
        else:
            self.setWindowTitle(APP_NAME)

    def _recent(self):
        v = self.settings.value("recent", [])
        return [v] if isinstance(v, str) else list(v or [])

    def _refresh_recent(self):
        self.start.set_recent(self._recent())

    def _remember(self, path: Path):
        lst = [p for p in self._recent() if p != str(path)]
        lst.insert(0, str(path))
        self.settings.setValue("recent", lst[:8])

    def _confirm_discard(self) -> bool:
        if self.project is None or not self.project.dirty:
            return True
        r = QMessageBox.question(self, APP_NAME, "Hay cambios sin guardar. ¿Guardar el proyecto?",
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                 | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Cancel:
            return False
        if r == QMessageBox.StandardButton.Save:
            return self.save()
        return True

    def new_project(self):
        if not self._confirm_discard():
            return
        dlg = NewProjectDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, author, folder = dlg.result_values()
        if folder.exists() and any(folder.iterdir()):
            QMessageBox.warning(self, APP_NAME, f"La carpeta ya contiene archivos:\n{folder}\n\n"
                                "Elige otro nombre o carpeta para no sobrescribir nada.")
            return
        project = Project(name, author, folder)
        try:
            project.save()
        except OSError as ex:
            QMessageBox.critical(self, APP_NAME, f"No se pudo crear el proyecto:\n{ex}")
            return
        self._enter(project)

    def open_dialog(self):
        if not self._confirm_discard():
            return
        d = QFileDialog.getExistingDirectory(self, "Abrir proyecto (carpeta con project.json)", str(PROJECTS_DIR))
        if d:
            self.open_path(d, checked=True)

    def open_path(self, path: str, checked: bool = False):
        if not checked and not self._confirm_discard():
            return
        try:
            project = Project.load(path)
        except (OSError, ValueError, json.JSONDecodeError) as ex:
            QMessageBox.critical(self, APP_NAME, f"No se pudo abrir el proyecto:\n{ex}")
            return
        self._enter(project)

    def _enter(self, project: Project):
        self.project = project
        self.editor.set_project(project)
        self.stack.setCurrentIndex(1)
        self._project_mode()
        self._remember(project.path)
        self._update_title()
        self.statusBar().showMessage(f"Proyecto: {project.path}  ·  la carpeta «skin» se actualiza al guardar", 8000)

    START_SIZE = (1024, 768)      # inicio en 4:3, tamaño fijo

    def _start_mode(self):
        self.showNormal()
        self.setFixedSize(*self.START_SIZE)
        geo = self.screen().availableGeometry()
        self.move(geo.center().x() - self.START_SIZE[0] // 2, geo.center().y() - self.START_SIZE[1] // 2)

    def _project_mode(self):
        self.setMinimumSize(900, 600)          # quita el tamaño fijo: ya se puede ajustar a gusto
        self.setMaximumSize(16777215, 16777215)
        self.showMaximized()

    def close_project(self):
        if not self._confirm_discard():
            return
        self.project = None
        self.editor.preview.project = None
        self.stack.setCurrentIndex(0)
        self._start_mode()
        self._refresh_recent()
        self._update_title()

    def save(self) -> bool:
        if self.project is None:
            return False
        try:
            self.project.save()
        except OSError as ex:
            QMessageBox.critical(self, APP_NAME, f"No se pudo guardar:\n{ex}")
            return False
        self.editor.mark_saved()
        self._update_title()
        self.statusBar().showMessage("Proyecto guardado.", 4000)
        return True

    # ---- Discord Rich Presence -------------------------------------------------------------
    def _rpc_tick(self):
        on = self.settings.value("rpc_on", "1") == "1"
        cid = presence.DEFAULT_ID
        if not on:
            state = (None, "", None)
        elif self.project is None or self.stack.currentIndex() == 0:
            state = (cid, "Main Menu", None)          # menú de crear proyecto: sin icono de modo
        else:
            sc = self.editor.preview.scene
            state = (cid, f'Creating "{self.project.name}"', sc if sc in presence.MODE_ICONS else None)
        if state != self._rpc_last:
            self._rpc_last = state
            self.rpc.set(*state)

    # ---- idioma -------------------------------------------------------------------------------
    @staticmethod
    def _tr_prop(obj, get, put):
        """Traduce un texto una sola vez y recuerda el original para poder cambiar de idioma."""
        txt = get()
        if not txt or obj.property("_i18n_out") == txt:
            return
        out = tr(txt)
        obj.setProperty("_i18n_src", txt)
        obj.setProperty("_i18n_out", out)
        if out != txt:
            put(out)

    def _retranslate(self):
        if i18n.current == "español" or not i18n._table:
            return
        for w in QApplication.allWidgets():
            if not w.isVisible():
                continue
            if isinstance(w, (QLabel, QPushButton, QCheckBox)) and not isinstance(w, ColorEdit):
                if not (isinstance(w, QLabel) and w.pixmap() is not None and not w.pixmap().isNull()):
                    self._tr_prop(w, w.text, w.setText)
            if w.isWindow():
                self._tr_prop(w, w.windowTitle, w.setWindowTitle)
            if isinstance(w, QTreeWidget):
                it = QTreeWidgetItemIterator(w)
                while it.value():
                    item = it.value()
                    t = item.text(0)
                    if item.data(0, Qt.ItemDataRole.UserRole + 50) != t:
                        out = tr(t)
                        item.setText(0, out)
                        item.setData(0, Qt.ItemDataRole.UserRole + 50, out)
                    it += 1
            if isinstance(w, QComboBox) and not isinstance(w, QFontComboBox):
                for i in range(w.count()):
                    t = w.itemText(i)
                    if w.itemData(i, Qt.ItemDataRole.UserRole + 50) != t and w.itemData(i) is not None:
                        out = tr(t)
                        w.setItemText(i, out)
                        w.setItemData(i, out, Qt.ItemDataRole.UserRole + 50)
            if w.toolTip():
                self._tr_prop(w, w.toolTip, w.setToolTip)
        for a in self.menuBar().actions():
            self._tr_act(a)

    def _tr_act(self, a):
        t = a.text()
        if t and a.property("_i18n_out") != t:
            out = tr(t)
            a.setProperty("_i18n_out", out)
            a.setText(out)
        if a.menu():
            for b in a.menu().actions():
                self._tr_act(b)

    def language_dialog(self):
        langs = i18n.available()
        if not langs:
            QMessageBox.warning(self, APP_NAME, tr("No hay idiomas en la carpeta «languajes»."))
            return
        cur = langs.index(i18n.current) if i18n.current in langs else 0
        item, ok = QInputDialog.getItem(self, tr("Idioma"), tr("Elige el idioma:"), langs, cur, False)
        if not ok or item == i18n.current:
            return
        self.settings.setValue("lang", item)
        r = QMessageBox.question(self, APP_NAME, tr("El idioma se aplica por completo al reiniciar la app. ¿Reiniciar ahora?"))
        if r == QMessageBox.StandardButton.Yes and self._confirm_discard():
            import subprocess
            subprocess.Popen([sys.executable] + sys.argv)
            QApplication.quit()

    def presence_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Rich Presence (Discord)")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        chk = QCheckBox("Mostrar en Discord lo que estoy haciendo")
        chk.setChecked(self.settings.value("rpc_on", "1") == "1")
        lay.addWidget(chk)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings.setValue("rpc_on", "1" if chk.isChecked() else "0")
            self._rpc_tick()

    def toggle_theme(self):
        light = self.settings.value("light", "0") != "1"
        self.settings.setValue("light", "1" if light else "0")
        self._apply_theme()

    def _apply_theme(self):
        """Solo cambia la interfaz de creación; la pantalla de inicio se queda oscura."""
        self.editor.setStyleSheet(LIGHT if self.settings.value("light", "0") == "1" else "")

    def check_updates(self):
        import urllib.request
        import urllib.error
        url = f"https://api.github.com/repos/{REPO}/releases/latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nyroxt-skin-creator"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                QMessageBox.information(self, APP_NAME, tr("Estás en la última versión") + f" ({APP_VERSION}).\n"
                                        + tr("(El repositorio todavía no tiene versiones publicadas.)"))
            else:
                QMessageBox.warning(self, APP_NAME, tr("No se pudo comprobar: error") + f" {ex.code}.")
            return
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, APP_NAME, tr("No se pudo conectar con GitHub:") + f"\n{ex}")
            return
        latest = str(data.get("tag_name", "")).lstrip("vV")

        def ver(t):
            return tuple(int(x) for x in re.findall(r"\d+", t)[:3]) or (0,)
        if latest and ver(latest) > ver(APP_VERSION):
            r = QMessageBox.question(self, tr("Actualización disponible"),
                                     f"{tr('Versión actual:')} {APP_VERSION}\n{tr('Nueva versión disponible:')} {latest}\n\n"
                                     + tr("¿Actualizar ahora?"),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(data.get("html_url") or f"https://github.com/{REPO}/releases/latest"))
        else:
            QMessageBox.information(self, APP_NAME, tr("Estás en la última versión") + f" ({APP_VERSION}).")

    def discard(self):
        if self.project is None or not self.project.dirty:
            return
        if QMessageBox.question(self, APP_NAME, "¿Descartar todos los cambios desde el último guardado?\n"
                                "(Puedes recuperarlos con Deshacer.)") == QMessageBox.StandardButton.Yes:
            self.editor.discard()
            self._update_title()

    def export(self):
        pr = self.project
        if pr is None:
            return
        issues = validate(pr)
        errors = [m for lvl, m in issues if lvl == "error"]
        warns = [m for lvl, m in issues if lvl == "warning"]
        if errors:
            QMessageBox.critical(self, "No se puede exportar", "\n\n".join(errors))
            return
        if warns:
            r = QMessageBox.question(self, "Advertencias", "\n\n".join(warns[:12]) + "\n\n¿Exportar de todos modos?")
            if r != QMessageBox.StandardButton.Yes:
                return
        default = PROJECTS_DIR / f"{safe_name(pr.assets['skin_ini']['name'])}.osk"
        dest, _ = QFileDialog.getSaveFileName(self, "Exportar skin", str(default), "Skin de osu! (*.osk)")
        if not dest:
            return
        if not self.save():
            return
        try:
            names = export_osk(pr, dest)
        except (OSError, RuntimeError, zipfile.BadZipFile) as ex:
            QMessageBox.critical(self, "Error al exportar", str(ex))
            return
        QMessageBox.information(self, tr("Exportación completada"),
                                tr("Archivos:") + f" {len(names)}\n{Path(dest).with_suffix('.osk')}")

    def closeEvent(self, e):
        if self._confirm_discard():
            e.accept()
        else:
            e.ignore()


def main():
    PROJECTS_DIR.mkdir(exist_ok=True)
    if sys.platform == "win32":      # que la barra de tareas muestre nuestro icono y no el de Python
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nyroxt.osuskincreator")
        except (AttributeError, OSError):
            pass
    i18n.load(QSettings("nyroxt", "osu-skin-creator").value("lang", i18n.DEFAULT) or i18n.DEFAULT)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = next((BASE_DIR / n for n in ("icon.ico", "app.ico", "icon.png") if (BASE_DIR / n).is_file()), None)
    if icon:
        app.setWindowIcon(QIcon(str(icon)))
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win._start_mode()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()