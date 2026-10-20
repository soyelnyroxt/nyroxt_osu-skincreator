# -*- coding: utf-8 -*-
"""Discord Rich Presence en un hilo aparte (si Discord no está abierto o falta pypresence, no pasa nada)."""
from __future__ import annotations

import asyncio
import queue
import threading
import time

DEFAULT_ID = "YOUR_ID_CLIENT"
BUTTONS = [{"label": "Download for desktop", "url": "https://github.com/soyelnyroxt/nyroxt_osu-skincreator"}]
MODE_ICONS = {"std": "std_icon", "taiko": "taiko_icon", "catch": "ctb_icon", "mania": "mania_icon"}
SMALL_TEXT = {"std": "osu!standard", "taiko": "osu!taiko", "catch": "osu!catch", "mania": "osu!mania"}


class RichPresence:
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.status = "apagado"
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def set(self, client_id: str | None, details: str = "", mode: str | None = None):
        """client_id None = apagar."""
        self.q.put((client_id, details, mode))

    def _run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        rpc, cur_id, start, want = None, None, int(time.time()), None
        while True:
            try:
                want = self.q.get(timeout=15)
                while not self.q.empty():          # solo importa el último estado
                    want = self.q.get_nowait()
            except queue.Empty:
                if want is None or rpc is not None:
                    continue                       # nada nuevo; si no conectó, reintenta cada 15 s
            cid, details, mode = want
            try:
                if cid != cur_id and rpc is not None:
                    rpc.close()
                    rpc, cur_id = None, None
                if not cid:
                    self.status = "apagado"
                    continue
                if rpc is None:
                    from pypresence import Presence
                    rpc = Presence(cid)
                    rpc.connect()
                    cur_id = cid
                kw = dict(details=details, start=start, buttons=BUTTONS)
                if mode in MODE_ICONS:
                    kw.update(small_image=MODE_ICONS[mode], small_text=SMALL_TEXT[mode])
                rpc.update(**kw)
                self.status = "conectado"
            except ImportError:
                self.status = "falta instalar pypresence (pip install pypresence)"
            except Exception as ex:                # Discord cerrado, ID inválido…
                self.status = f"sin conexión con Discord ({type(ex).__name__})"
                rpc, cur_id = None, None
