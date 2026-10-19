<p align="center">
  <img src="menu_img/logo.png" alt="Nyroxt's osu!skin creator" width="560">
</p>

<p align="center">
  <b>The easiest way to create an osu! skin.</b><br>
  Design every element from scratch, preview it live exactly as osu! draws it, and export a ready-to-play <code>.osk</code>.
</p>

---

## ✨ Features

- **All game modes** – osu!standard, osu!taiko, osu!catch and osu!mania (1K–20K).
- **Live preview** that uses the same positioning and scaling rules as osu!stable, so what you see in the editor is what you get in game.
- **Shape designer** – circles, notes, keys, fruits and more from built-in shapes (circle, arrow, diamond, star, hexagon…) or **your own image as a shape**, with fill, gradient, border, glow and shadow.
- **Replace any file with your own image** – it's resized automatically to the size osu! expects.
- **Menus and screens** – song selection, main menu background, pause, fail, results, mod selection, mode icons, dialog buttons and the in-game HUD (score, accuracy, combo, health bar, skip button, key counters).
- **Free mouse editing** – drag, resize, lock/unlock and multi-select (Ctrl+click) objects; drag mania positions (HitPosition, receptors, ScorePosition, ComboPosition, stage width and position).
- **Layers and free canvases** – add your own images and text anywhere (stage sides, song select bars, pause/fail backgrounds…), reorder and rotate them.
- **Sounds** – custom hitsounds for every mode, fail/pause music, “see you next time” and menu sounds, or keep osu!'s defaults.
- **Animations** – import GIFs (split into frames automatically), animated taiko mascot, and an **Effects** section to create animated judgements, bursts and particles with or without code.
- **Global theme** – ready-made themes, palette generator, one font for everything, quick menu style.
- **Compatibility modes** – stable/lazer, stable, lazer, legacy osu! (2008–2015 builds) and “totally” (SD + @2x).
- **Undo / redo**, discard unsaved changes, light/dark editor theme.
- **Discord Rich Presence**, update checker, and multi-language interface.

## 📦 Installation

Requires **Python 3.10+**.

```bash
git clone https://github.com/soyelnyroxt/nyroxt_osu-skincreator.git
cd nyroxt_osu-skincreator

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
python main.py
```

## 🚀 Quick start

1. Click **New project**, give your skin a name and an author.
2. Pick an element in the tree on the left and change it in the properties panel on the right.
3. Use the scene selector at the top to preview each mode or screen. In osu!mania, set the aspect ratio (16:9, 4:3…) to the one you play with.
4. **File → Export .osk…** and double-click the `.osk` to install it in osu!.

> **Tip:** the real test is always opening the `.osk` in osu!stable. If something looks different, compare a screenshot of the game with the editor at the same aspect ratio.

## 📁 Project structure

| File / folder | Description |
|---|---|
| `main.py` | Application entry point and the whole user interface: start screen, editor window, element tree, properties panels, live preview of every mode and screen, mouse editing, undo/redo, menus, update checker and language switching. |
| `core.py` | The skin model: catalog of every editable element and its properties, project save/load (`project.json`), `skin.ini` generation, mania layout maths, @2x/SD export rules, compatibility modes, sounds, effects and `.osk` export. |
| `gens.py` | Image generators: one function per element that draws the PNG files osu! needs (hit circles, notes, keys, fruits, menu buttons, mod icons, results screen, health bar, digits, effects…). |
| `gfx.py` | Drawing primitives shared by all generators: shapes, fills, gradients, borders, glow, shadows, text rendering and “custom image as shape”. |
| `i18n.py` | Translation system: loads the language files from `languajes/` and translates the interface. English is the default. |
| `presence.py` | Discord Rich Presence running in a background thread (shows “Main Menu” or “Creating "project"” with the current mode icon and a download button). |
| `requirements.txt` | Python dependencies (`PySide6`, `pypresence`). |
| `app.ico` | Application icon used for the window and taskbar. |
| `languajes/` | Interface translations, one `.txt` file per language (`english.txt`, `español.txt`…). See *Adding a language* below. |
| `menu_img/` | Images used by the app itself, such as the logo shown on the start screen. |
| `LICENSE` | MIT license. |
| `.gitignore` | Keeps local files out of the repository (`.venv/`, `__pycache__/`, `projects/`, exported `.osk`). |

Created at runtime (not in the repository):

| Folder | Description |
|---|---|
| `projects/` | Your skin projects. Each one contains `project.json`, imported images/fonts/sounds and a `skin/` folder with the generated skin. |
| `.venv/` | Your local Python environment. |

## 🌍 Adding a language

1. Copy `languajes/english.txt` and rename it, e.g. `languajes/português.txt`.
2. Translate the right side of every line:

   ```
   Original text (Spanish) => Your translation
   ```

   `\n` is a line break and lines starting with `#` are comments. Untranslated lines fall back to the original text.
3. Restart the app and choose it in **Others → Language…**.

## 🔄 Releases and updates

The app compares its version (`APP_VERSION` in `main.py`) with the latest **GitHub Release** of this repository. To publish an update:

1. Increase `APP_VERSION` (e.g. `1.0` → `1.1`).
2. Create a new Release with the same tag (`1.1`).

Users will see “New version available” in **Others → Check for updates…**.

## ⚠️ Known limits (osu! rules, not bugs)

- osu! skins can't run code; effects are exported as image frames.
- Some HUD elements have fixed positions in osu! (song clock, leaderboard). Score, accuracy and combo can only be shifted in certain directions, and score and accuracy share the same digits.
- osu!mania stage position depends on the screen aspect ratio; export with the same aspect ratio you play with.
- The main menu background is only visible to osu!supporters.

## ❤️ Support

If you like the project, you can support it at **[nyroxt.online/donate](https://nyroxt.online/donate.html)**.

## 📄 License

Released under the [MIT License](LICENSE).

---

*osu! is a trademark of ppy Pty Ltd. This project is fan-made and not affiliated with ppy.*
