"""
PyRokuMe.pyw  —  PyDisplay-styled Roku TV remote
────────────────────────────────────────────────────
• Auto-discovers Roku devices via SSDP, with fallback IP range scan
  (192.168.2.1 – 192.168.2.99 + SSDP simultaneously)
• Resizable / draggable window — drag body to move, drag corners to resize
• PyDisplay-styled dep checker (only shown when `requests` is missing)

Keyboard shortcuts  (controku-compatible):
  WASD / Arrows  →  Up / Down / Left / Right
  Enter/Space/O  →  Select
  Backspace / B  →  Back
  Escape / H     →  Home
  I              →  Info
  , / R          →  Rewind    . / F  →  Fast Forward
  / / P          →  Play/Pause
  [ / -          →  Vol−     ] / +  →  Vol+     \\ / M  →  Mute
"""

import tkinter as tk
import threading
import importlib
import importlib.metadata as _importlib_metadata
import socket
import time
import json
import os
import sys
import subprocess
import ctypes

# ── Constants ─────────────────────────────────────────────────────────────────
_APP_VERSION = "1.0.0"
_FONT        = "Courier New"
_FS          = 9
_ECP_PORT    = 8060
_SSDP_ADDR   = "239.255.255.250"
_SSDP_PORT   = 1900
_SCAN_SUBNET = "192.168.2"          # scan .1 – .99 in addition to SSDP
_NO_WIN      = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000

# ── Portable mode ─────────────────────────────────────────────────────────────
# The script's own directory — config.json lives here in portable mode.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def _is_portable_dir():
    """True when the script already lives inside a folder named 'PyRokuMe'."""
    return os.path.basename(_SCRIPT_DIR).lower() == "pyrokuMe".lower()

def _load_mode():
    """
    Return 'portable', 'standard', or None (first launch / undecided).
    No extra files — mode is stored inside config.json under the 'mode' key,
    or auto-detected from the folder name.
    """
    if _is_portable_dir():
        return "portable"
    # Check portable config first, then standard APPDATA location
    for path in (
        os.path.join(_SCRIPT_DIR, "config.json"),
        os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                     "PyRokuMe", "config.json"),
    ):
        try:
            with open(path) as f:
                v = json.load(f).get("mode")
                if v in ("portable", "standard"):
                    return v
        except Exception:
            pass
    return None

def _save_mode(mode):
    """Write the mode key into the correct config.json (no extra files)."""
    if mode == "portable":
        cfg_path = os.path.join(_SCRIPT_DIR, "config.json")
    else:
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PyRokuMe")
        os.makedirs(d, exist_ok=True)
        cfg_path = os.path.join(d, "config.json")
    try:
        try:
            with open(cfg_path) as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["mode"] = mode
        with open(cfg_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _show_portable_saved(portable_dir, new_script):
    """
    PyDisplay-styled popup shown after portable setup completes.
    Tells the user where the folder is, with a button to open it in Explorer.
    Relaunches the script when dismissed.
    """
    root = tk.Tk()
    root.title("PyRokuMe — Portable Setup")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.wm_attributes("-topmost", True)
    root.overrideredirect(True)

    def _relaunch_and_close():
        root.destroy()
        subprocess.Popen(
            [sys.executable, new_script],
            creationflags=_NO_WIN,
            close_fds=True,
        )

    _make_titlebar(root, PANEL, BORDER, SUBTEXT, RED,
                   on_close=_relaunch_and_close,
                   title_text="PyRokuMe  ·  portable setup complete",
                   title_fg=TEXT, title_bg=PANEL)

    body = tk.Frame(root, bg=BG, padx=16, pady=12)
    body.pack(fill="x")

    tk.Label(body, text="✔  Portable folder created",
             bg=BG, fg=GREEN, font=(_FONT, _FS, "bold"), anchor="w").pack(fill="x")
    tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(6, 8))
    tk.Label(body, text="PyRokuMe will now run from:", bg=BG, fg=SUBTEXT,
             font=(_FONT, _FS - 1), anchor="w").pack(fill="x")
    tk.Label(body, text=portable_dir, bg=PANEL, fg=ACCENT,
             font=(_FONT, _FS - 1), anchor="w", padx=8, pady=6,
             wraplength=320, justify="left").pack(fill="x", pady=(2, 0))

    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(10, 0))

    bot = tk.Frame(root, bg=BG, pady=8, padx=16)
    bot.pack(fill="x")

    def _open_folder():
        subprocess.Popen(["explorer.exe", portable_dir], creationflags=_NO_WIN)

    open_btn = tk.Label(bot, text="📂  Open Folder", bg=BORDER, fg=SUBTEXT,
                        font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=5)
    open_btn.pack(side="left")
    open_btn.bind("<Button-1>", lambda e: _open_folder())
    open_btn.bind("<Enter>",    lambda e: open_btn.config(fg=TEXT))
    open_btn.bind("<Leave>",    lambda e: open_btn.config(fg=SUBTEXT))

    ok_btn = tk.Label(bot, text="▶  Launch", bg=ROKU_PURPLE, fg=TEXT,
                      font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=5)
    ok_btn.pack(side="right")
    ok_btn.bind("<Button-1>", lambda e: _relaunch_and_close())
    ok_btn.bind("<Enter>",    lambda e: ok_btn.config(bg=GREEN, fg=BG))
    ok_btn.bind("<Leave>",    lambda e: ok_btn.config(bg=ROKU_PURPLE, fg=TEXT))

    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - root.winfo_reqwidth()) // 2}+{(sh - root.winfo_reqheight()) // 2}")
    root.mainloop()


def _setup_portable():
    """
    Create a PyRokuMe folder next to the script, move PyRokuMe.pyw into it,
    write config.json with mode=portable, then show a confirmation popup.
    Returns True on success, False on failure.
    """
    import shutil
    script_path  = os.path.abspath(__file__)
    script_name  = os.path.basename(script_path)
    parent_dir   = os.path.dirname(script_path)
    portable_dir = os.path.join(parent_dir, "PyRokuMe")
    new_script   = os.path.join(portable_dir, script_name)
    new_cfg      = os.path.join(portable_dir, "config.json")

    try:
        os.makedirs(portable_dir, exist_ok=True)

        # Write config.json into the new folder
        try:
            with open(new_cfg) as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["mode"] = "portable"
        with open(new_cfg, "w") as f:
            json.dump(data, f, indent=2)

        # Move the script (copy+delete avoids cross-drive issues)
        shutil.copy2(script_path, new_script)
        try:
            os.remove(script_path)
        except Exception:
            pass    # non-fatal — duplicate is harmless

        # Show confirmation popup — relaunch happens from inside it
        _show_portable_saved(portable_dir, new_script)
        return True
    except Exception:
        return False

def _resolve_app_dir():
    """Return the data directory based on the chosen/detected mode."""
    if _load_mode() == "portable":
        return _SCRIPT_DIR
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PyRokuMe")

_APP_DIR  = _resolve_app_dir()
_CFG_PATH = os.path.join(_APP_DIR, "config.json")

# ── Default keyboard → ECP mapping (user can override via theme popup) ────────
_DEFAULT_KEYMAP = {
    "up":           "Up",
    "w":            "Up",
    "down":         "Down",
    "s":            "Down",
    "left":         "Left",
    "a":            "Left",
    "right":        "Right",
    "d":            "Right",
    "return":       "Select",
    "space":        "Select",
    "o":            "Select",
    "backspace":    "Back",
    "b":            "Back",
    "escape":       "Home",
    "h":            "Home",
    "i":            "Info",
    "comma":        "Rev",
    "r":            "Rev",
    "period":       "Fwd",
    "f":            "Fwd",
    "slash":        "Play",
    "p":            "Play",
    "bracketleft":  "VolumeDown",
    "minus":        "VolumeDown",
    "bracketright": "VolumeUp",
    "plus":         "VolumeUp",
    "backslash":    "VolumeMute",
    "m":            "VolumeMute",
}

# Human-readable labels for the keybind editor
_ECP_ACTIONS = [
    "Up", "Down", "Left", "Right", "Select", "Back", "Home", "Info",
    "Rev", "Fwd", "Play", "VolumeDown", "VolumeUp", "VolumeMute",
    "Power", "ChannelUp", "ChannelDown",
]

# ── Palette — exact PyDisplay colours ────────────────────────────────────────
BG          = "#0a0a0f"
PANEL       = "#111118"
BORDER      = "#1e1e2e"
DIM         = "#3a3a5c"
TEXT        = "#e0e0f0"
SUBTEXT     = "#6868a0"
GREEN       = "#39ff7f"
RED         = "#ff3860"
ACCENT      = "#00ffe5"
ACCENT2     = "#c792ea"
YELLOW      = "#ffcc00"
ROKU_PURPLE = "#6c2bd9"

# ── Win32 — exact PyDisplay constants ────────────────────────────────────────
_GWL_EXSTYLE        = -20
_WS_EX_TOOLWINDOW   = 0x80
_WS_EX_APPWINDOW    = 0x40000
_SWP_NOSIZE         = 0x0001
_SWP_NOMOVE         = 0x0002
_SWP_NOZORDER       = 0x0004
_SWP_NOACTIVATE     = 0x0010
_SWP_FRAMECHANGED   = 0x0020
_HWND_TOP           = 0
try:
    _user32  = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    _WIN32   = True
except Exception:
    _WIN32   = False
    _kernel32 = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _can_import(name):
    import importlib.util
    try:
        importlib.invalidate_caches()
        for m in list(sys.modules):
            if m == name or m.startswith(name + "."):
                sys.modules.pop(m, None)
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _make_titlebar(window, bg, border, subtext, red, on_close=None,
                   title_text=None, title_fg=None, title_bg=None,
                   separator_color=None, draggable=True):
    """Exact PyDisplay _make_titlebar — optionally draggable, ✕ on left, optional title."""
    drag = {"x": 0, "y": 0}
    def _ds(e): drag["x"] = e.x_root; drag["y"] = e.y_root
    def _dm(e):
        dx = e.x_root - drag["x"]; dy = e.y_root - drag["y"]
        window.geometry(f"+{window.winfo_x()+dx}+{window.winfo_y()+dy}")
        drag["x"] = e.x_root; drag["y"] = e.y_root

    tb = tk.Frame(window, bg=bg, height=28)
    tb.pack(fill="x")
    tb.pack_propagate(False)

    x_btn = tk.Label(tb, text=" ✕ ", bg=border, fg=subtext,
                     font=(_FONT, _FS, "bold"), cursor="hand2", padx=2, pady=2)
    x_btn.pack(side="left", padx=(4, 0))
    _close = on_close or window.destroy
    x_btn.bind("<Button-1>", lambda e: _close())
    x_btn.bind("<Enter>",    lambda e: x_btn.config(fg=red))
    x_btn.bind("<Leave>",    lambda e: x_btn.config(fg=subtext))

    lbl_bg = title_bg or bg
    lbl_fg = title_fg or subtext
    cursor = "fleur" if draggable else "arrow"
    handle = tk.Label(tb, text=title_text or "", bg=lbl_bg, fg=lbl_fg,
                      font=(_FONT, _FS, "bold"), cursor=cursor)
    handle.pack(side="left", fill="both", expand=True)

    if draggable:
        for w in (tb, handle):
            w.bind("<ButtonPress-1>", _ds)
            w.bind("<B1-Motion>",     _dm)

    tk.Frame(window, bg=separator_color or border, height=1).pack(fill="x")
    return tb


# ── Global popup registry — so theme changes can re-theme open popups ──────────
_open_popups = []   # list of (Toplevel, rebuild_callback)

def _register_popup(win, rebuild_cb=None):
    """Register a Toplevel so _retheme_all_popups can refresh it."""
    _open_popups.append((win, rebuild_cb))
    def _cleanup():
        _open_popups[:] = [(w, cb) for w, cb in _open_popups if w is not win]
    win.bind("<Destroy>", lambda e: _cleanup() if e.widget is win else None, add="+")

def _retheme_all_popups():
    """Called after a theme change — destroy & reopen every registered popup."""
    for win, cb in list(_open_popups):
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:
            pass
    _open_popups.clear()


# ═══════════════════════════════════════════════════════════════════════════════
#  Dependency checker  — compact PyDisplay style (single dep)
# ═══════════════════════════════════════════════════════════════════════════════

def _run_dependency_check():
    """Compact single-dep PyDisplay-styled installer. Returns True on Launch."""
    result = {"launch": False}

    root = tk.Tk()
    root.title("PyRokuMe — Setup")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.wm_attributes("-topmost", True)
    root.overrideredirect(True)

    _make_titlebar(root, PANEL, BORDER, SUBTEXT, RED,
                   on_close=root.destroy,
                   title_text="PyRokuMe  ·  setup",
                   title_fg=TEXT, title_bg=PANEL)

    # ── Single-line header ────────────────────────────────────────────────────
    hdr = tk.Frame(root, bg=BG, padx=16, pady=10)
    hdr.pack(fill="x")
    tk.Label(hdr, text="PyRokuMe", bg=BG, fg=ACCENT,
             font=(_FONT, _FS, "bold")).pack(side="left")
    tk.Label(hdr, text=f"  v{_APP_VERSION}  ·  one dependency required",
             bg=BG, fg=SUBTEXT, font=(_FONT, _FS - 1)).pack(side="left")
    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=12)

    # ── Single package row ────────────────────────────────────────────────────
    PIP_NAME = "requests"
    IMP_NAME = "requests"

    installed = _can_import(IMP_NAME)
    try:
        ver = _importlib_metadata.version(PIP_NAME) if installed else ""
    except Exception:
        ver = ""

    _inst  = [installed]
    _busy  = [False]
    _errs  = {}

    row = tk.Frame(root, bg=PANEL, padx=16, pady=10)
    row.pack(fill="x", padx=12, pady=(6, 0))

    # Name
    tk.Label(row, text="requests *", bg=PANEL, fg=TEXT,
             font=(_FONT, _FS, "bold"), width=12, anchor="w").pack(side="left")

    # Status
    st_text  = (f"✔  v{ver}" if ver else "✔  installed") if installed else "✘  missing"
    st_color = GREEN if installed else RED
    st_lbl = tk.Label(row, text=st_text, bg=PANEL, fg=st_color,
                      font=(_FONT, _FS), width=14, anchor="w")
    st_lbl.pack(side="left")

    # Description
    tk.Label(row, text="HTTP lib — sends ECP commands to Roku",
             bg=PANEL, fg=SUBTEXT, font=(_FONT, _FS - 2), anchor="w").pack(side="left", fill="x", expand=True)

    # Action button
    act_btn = tk.Label(row, bg=PANEL, font=(_FONT, _FS, "bold"),
                       cursor="hand2", padx=8, pady=3, anchor="center")
    act_btn.pack(side="right", padx=(8, 0))

    log_var = tk.StringVar(value="* required")
    prog    = tk.Canvas(root, bg=BG, highlightthickness=0, height=3)
    prog.pack(fill="x", padx=16, pady=(4, 0))

    def _set_prog(frac):
        prog.delete("all")
        if frac is None: return
        w = prog.winfo_width() or 360
        prog.create_rectangle(0, 0, int(w * frac), 3, fill=ACCENT, outline="")

    def _set_failed(err):
        _errs[PIP_NAME] = err
        st_lbl.config(text="?  Failed", fg=YELLOW, cursor="hand2")
        def _show(e):
            d = tk.Toplevel(root)
            d.configure(bg=PANEL); d.overrideredirect(True)
            d.attributes("-topmost", True); d.lift(); d.focus_force(); d.grab_set()
            _make_titlebar(d, PANEL, BORDER, SUBTEXT, RED, on_close=d.destroy,
                           title_text="PyRokuMe  ·  install error",
                           title_fg=TEXT, title_bg=PANEL)
            f = tk.Frame(d, bg=PANEL, padx=16, pady=12); f.pack(fill="both")
            tk.Label(f, text=f"Install error — {PIP_NAME}", bg=PANEL, fg=RED,
                     font=(_FONT, _FS, "bold")).pack(anchor="w")
            tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=(4, 8))
            tk.Label(f, text=err, bg=BORDER, fg=TEXT,
                     font=(_FONT, _FS - 2), anchor="w", justify="left",
                     padx=8, pady=8, wraplength=340).pack(fill="x")
            cb = tk.Label(f, text="Close", bg=BORDER, fg=SUBTEXT,
                          font=(_FONT, _FS, "bold"), cursor="hand2", padx=10, pady=3)
            cb.pack(anchor="e", pady=(8, 0))
            cb.bind("<Button-1>", lambda e: d.destroy())
            cb.bind("<Enter>", lambda e: cb.config(fg=TEXT))
            cb.bind("<Leave>", lambda e: cb.config(fg=SUBTEXT))
            d.update_idletasks()
            d.geometry(f"+{root.winfo_x()+(root.winfo_width()-d.winfo_reqwidth())//2}"
                       f"+{root.winfo_y()+(root.winfo_height()-d.winfo_reqheight())//2}")
        st_lbl.bind("<Button-1>", _show)
        st_lbl.bind("<Enter>", lambda e: st_lbl.config(fg=GREEN))
        st_lbl.bind("<Leave>", lambda e: st_lbl.config(fg=YELLOW))

    def _refresh_act():
        if _busy[0]:
            act_btn.config(text="  …  ", fg=SUBTEXT, bg=PANEL, cursor="arrow")
            return
        if _inst[0]:
            act_btn.config(text="✕  Delete ", fg=RED,   bg=BORDER, cursor="hand2")
        else:
            act_btn.config(text="＋ Install", fg=GREEN, bg=BORDER, cursor="hand2")

    def _click_act(e):
        if _busy[0]: return
        _busy[0] = True; _refresh_act()

        def _worker():
            if _inst[0]:
                root.after(0, lambda: log_var.set("Removing requests…"))
                root.after(0, lambda: st_lbl.config(text="⏳  Removing…", fg=YELLOW))
                root.after(0, lambda: _set_prog(0.1))
                try:
                    subprocess.run([sys.executable, "-m", "pip", "uninstall",
                                    PIP_NAME, "-y", "--disable-pip-version-check"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, creationflags=_NO_WIN)
                    importlib.invalidate_caches()
                    for m in list(sys.modules):
                        if m == IMP_NAME or m.startswith(IMP_NAME + "."): sys.modules.pop(m, None)
                    if _can_import(IMP_NAME):
                        raise RuntimeError("Still importable — manual removal may be needed.")
                    _inst[0] = False
                    root.after(0, lambda: st_lbl.config(text="✘  removed", fg=SUBTEXT))
                    root.after(0, lambda: log_var.set("✔  requests removed."))
                    root.after(0, lambda: _set_prog(1.0))
                    root.after(200, lambda: _set_prog(None))
                except Exception as exc:
                    s = str(exc)
                    root.after(0, lambda s=s: _set_failed(s))
                    root.after(0, lambda s=s: log_var.set(f"✘  {s}"))
                    root.after(0, lambda: _set_prog(None))
            else:
                root.after(0, lambda: log_var.set("Installing requests…"))
                root.after(0, lambda: st_lbl.config(text="⏳  Installing…", fg=YELLOW))
                root.after(0, lambda: _set_prog(0.2))
                try:
                    proc = subprocess.run(
                        [sys.executable, "-m", "pip", "install", PIP_NAME,
                         "--disable-pip-version-check", "--no-cache-dir"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        text=True, creationflags=_NO_WIN)
                    if proc.returncode != 0:
                        lines = (proc.stderr or "").strip().splitlines()
                        raise RuntimeError(lines[-1] if lines else f"exit {proc.returncode}")
                    importlib.invalidate_caches()
                    for m in list(sys.modules):
                        if m == IMP_NAME or m.startswith(IMP_NAME + "."): sys.modules.pop(m, None)
                    importlib.import_module(IMP_NAME)
                    try:    vs = f"✔  v{_importlib_metadata.version(PIP_NAME)}"
                    except: vs = "✔  installed"
                    _inst[0] = True
                    root.after(0, lambda vs=vs: st_lbl.config(text=vs, fg=GREEN))
                    root.after(0, lambda: log_var.set("✔  requests installed — ready to launch."))
                    root.after(0, lambda: _set_prog(1.0))
                    root.after(200, lambda: _set_prog(None))
                except Exception as exc:
                    s = str(exc)
                    root.after(0, lambda s=s: _set_failed(s))
                    root.after(0, lambda s=s: log_var.set(f"✘  {s}"))
                    root.after(0, lambda: _set_prog(None))
            _busy[0] = False
            root.after(0, _refresh_act)

        threading.Thread(target=_worker, daemon=True).start()

    act_btn.bind("<Button-1>", _click_act)
    act_btn.bind("<Enter>",
                 lambda e: act_btn.config(fg=RED if _inst[0] else GREEN) if not _busy[0] else None)
    act_btn.bind("<Leave>", lambda e: _refresh_act())
    _refresh_act()

    # ── Bottom bar ────────────────────────────────────────────────────────────
    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(6, 0))
    tk.Label(root, textvariable=log_var, bg=BG, fg=SUBTEXT,
             font=(_FONT, _FS - 2), anchor="w", padx=16, pady=4).pack(fill="x")

    bot = tk.Frame(root, bg=BG, pady=8)
    bot.pack(fill="x", padx=16)

    def _do_launch():
        if not _inst[0]:
            warn = tk.Toplevel(root)
            warn.configure(bg=BG); warn.resizable(False, False)
            warn.wm_attributes("-topmost", True); warn.overrideredirect(True); warn.withdraw()
            _make_titlebar(warn, PANEL, BORDER, SUBTEXT, RED, on_close=warn.destroy,
                           title_text="PyRokuMe  ·  Warning", title_fg=TEXT, title_bg=PANEL)
            tk.Label(warn, text="⚠  requests is not installed",
                     bg=BG, fg=YELLOW, font=(_FONT, _FS, "bold"), padx=16, pady=12).pack(fill="x")
            tk.Label(warn, text="PyRokuMe needs requests to send commands to your Roku.\n"
                               "Install it first, or continue at your own risk.",
                     bg=BG, fg=TEXT, font=(_FONT, _FS), justify="left",
                     padx=16, pady=6, wraplength=300).pack(fill="x")
            tk.Frame(warn, bg=BORDER, height=1).pack(fill="x", padx=10, pady=4)
            wr = tk.Frame(warn, bg=BG); wr.pack(fill="x", padx=16, pady=8)
            def _cont():
                result["launch"] = True; warn.destroy(); root.destroy()
            wb1 = tk.Label(wr, text="Continue Anyway", bg=BORDER, fg=YELLOW,
                           font=(_FONT, _FS, "bold"), cursor="hand2", padx=10, pady=4)
            wb1.pack(side="right", padx=(6, 0))
            wb1.bind("<Button-1>", lambda e: _cont())
            wb1.bind("<Enter>",    lambda e: wb1.config(fg=GREEN))
            wb1.bind("<Leave>",    lambda e: wb1.config(fg=YELLOW))
            wb2 = tk.Label(wr, text="Go Back", bg=BORDER, fg=SUBTEXT,
                           font=(_FONT, _FS, "bold"), cursor="hand2", padx=10, pady=4)
            wb2.pack(side="right")
            wb2.bind("<Button-1>", lambda e: warn.destroy())
            wb2.bind("<Enter>",    lambda e: wb2.config(fg=TEXT))
            wb2.bind("<Leave>",    lambda e: wb2.config(fg=SUBTEXT))
            warn.update_idletasks()
            warn.geometry(f"+{root.winfo_x()+(root.winfo_width()-warn.winfo_reqwidth())//2}"
                          f"+{root.winfo_y()+(root.winfo_height()-warn.winfo_reqheight())//2}")
            warn.deiconify(); warn.grab_set()
            return
        result["launch"] = True; root.destroy()

    def _mk(text, color, cmd):
        b = tk.Label(bot, text=text, bg=BORDER, fg=color,
                     font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=5)
        b.pack(side="right", padx=(8, 0))
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e, w=b: w.config(fg=GREEN))
        b.bind("<Leave>",    lambda e, w=b, c=color: w.config(fg=c))
        return b

    _mk("▶  Launch", ACCENT, _do_launch)

    # Install shortcut button — shown only when missing
    install_btn = tk.Label(bot, bg=BORDER, font=(_FONT, _FS, "bold"),
                           cursor="hand2", padx=12, pady=5)

    def _poll_install_btn():
        if not root.winfo_exists(): return
        if not _inst[0]:
            install_btn.config(text="⬇  Install requests", fg=ACCENT, cursor="hand2")
            install_btn.bind("<Button-1>", lambda e: _click_act(e))
            install_btn.bind("<Enter>",    lambda e: install_btn.config(fg=GREEN))
            install_btn.bind("<Leave>",    lambda e: install_btn.config(fg=ACCENT))
            install_btn.pack(side="right", padx=(8, 0))
        else:
            install_btn.config(text="✔  Installed", fg=GREEN, cursor="arrow")
            install_btn.unbind("<Button-1>")
            install_btn.pack(side="right", padx=(8, 0))
        root.after(300, _poll_install_btn)

    _poll_install_btn()

    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw-root.winfo_reqwidth())//2}+{(sh-root.winfo_reqheight())//2}")
    root.mainloop()
    return result["launch"]


# ═══════════════════════════════════════════════════════════════════════════════
#  ECP helpers
# ═══════════════════════════════════════════════════════════════════════════════

def ecp_post(ip, path, timeout=2.0):
    try:
        import requests
        requests.post(f"http://{ip}:{_ECP_PORT}{path}", timeout=timeout)
        return True
    except Exception:
        return False

def ecp_get(ip, path, timeout=3.0):
    try:
        import requests
        r = requests.get(f"http://{ip}:{_ECP_PORT}{path}", timeout=timeout)
        return r.text
    except Exception:
        return None

def ecp_keypress(ip, key):
    return ecp_post(ip, f"/keypress/{key}")

def ecp_device_info(ip):
    xml = ecp_get(ip, "/query/device-info", timeout=1.5)
    if not xml: return {}
    import re
    info = {}
    for tag in ("friendly-device-name", "model-name", "user-device-name"):
        m = re.search(rf"<{tag}>(.*?)</{tag}>", xml)
        if m: info[tag] = m.group(1).strip()
    return info

def ecp_apps(ip):
    xml = ecp_get(ip, "/query/apps")
    if not xml: return []
    import re
    return re.findall(r'<app id="(\d+)"[^>]*>(.*?)</app>', xml)


def send_wol(mac: str):
    """Send a Wake-on-LAN magic packet to the given MAC address."""
    mac = mac.replace(":", "").replace("-", "").replace(".", "").upper()
    if len(mac) != 12:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    payload = bytes.fromhex("FF" * 6 + mac * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(payload, ("<broadcast>", 9))


# ═══════════════════════════════════════════════════════════════════════════════
#  Discovery  — SSDP + IP range scan in parallel
# ═══════════════════════════════════════════════════════════════════════════════

_SSDP_MSG = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {_SSDP_ADDR}:{_SSDP_PORT}\r\n"
    "MAN: \"ssdp:discover\"\r\n"
    "ST: roku:ecp\r\n"
    "MX: 3\r\n\r\n"
)

def ssdp_discover(timeout=4.0):
    found = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)
        sock.sendto(_SSDP_MSG.encode(), (_SSDP_ADDR, _SSDP_PORT))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                if "roku" in data.decode(errors="ignore").lower():
                    ip = addr[0]
                    if ip not in found:
                        found[ip] = {"ip": ip}
            except socket.timeout:
                break
            except Exception:
                break
    except Exception:
        pass
    finally:
        try: sock.close()
        except Exception: pass
    return list(found.values())


def _probe_ecp(ip, found, lock):
    """Try to hit ECP port 8060. Adds ip to found if it responds."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.6)
        err = s.connect_ex((ip, _ECP_PORT))
        s.close()
        if err == 0:
            with lock:
                if ip not in found:
                    found[ip] = {"ip": ip}
    except Exception:
        pass


def discover_all(timeout=5.0):
    """
    Run SSDP + IP range scan (192.168.2.1–99) concurrently.
    Returns list of dicts: [{'ip': '...'}]
    """
    found = {}          # ip → {'ip': ...}
    lock  = threading.Lock()

    # SSDP thread
    def _ssdp():
        for d in ssdp_discover(timeout=timeout - 1):
            with lock:
                found[d["ip"]] = d

    ssdp_t = threading.Thread(target=_ssdp, daemon=True)
    ssdp_t.start()

    # IP range probe — 1 to 99 on subnet
    threads = []
    for last in range(1, 100):
        ip = f"{_SCAN_SUBNET}.{last}"
        t = threading.Thread(target=_probe_ecp, args=(ip, found, lock), daemon=True)
        t.start()
        threads.append(t)

    # Wait for all probes (they each have 0.6 s timeout)
    for t in threads:
        t.join(timeout=1.5)
    ssdp_t.join(timeout=timeout)

    return list(found.values())


# ═══════════════════════════════════════════════════════════════════════════════
#  Config
# ═══════════════════════════════════════════════════════════════════════════════

def _read_cfg():
    try:
        with open(_CFG_PATH) as f: return json.load(f)
    except Exception:
        return {}

def _write_cfg(data):
    try:
        os.makedirs(_APP_DIR, exist_ok=True)
        ex = _read_cfg(); ex.update(data)
        with open(_CFG_PATH, "w") as f: json.dump(ex, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  Main App  — resizable / draggable like PyDisplay
# ═══════════════════════════════════════════════════════════════════════════════

_EDGE_MARGIN = 16   # px from corner to trigger resize cursor
_MIN_W       = 220
_MIN_H       = 340

class RokuRemote(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("PyRokuMe")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(_MIN_W, _MIN_H)

        # ── Exact PyDisplay startup sequence ──────────────────────────────────
        self.overrideredirect(True)

        # Drag / resize state (mirrors PyDisplay)
        self._drag_x  = self._drag_y  = 0
        self._drag_wx = self._drag_wy = 0
        self._drag_ww = self._drag_wh = 0
        self._resize_edge = None

        self._ip          = None
        self._devices     = []
        self._closing     = False
        self._device_name = ""
        self._hwnd        = None
        self._status_job  = None
        # Single-instance popup guards
        self._popup_theme    = None
        self._popup_keybinds = None
        self._popup_apps     = None
        self._popup_manual   = None
        self._mac            = ""
        self._opacity    = 1.0

        cfg = _read_cfg()
        saved_ip   = cfg.get("last_ip", "")
        self._mac  = cfg.get("mac", "")
        # Saved device list  [{"name": ..., "ip": ...}, ...]
        self._saved_devices   = cfg.get("saved_devices", [])
        self._reconnect_job   = None   # after() handle for auto-reconnect
        self._was_online      = False  # tracks last known connectivity state

        # Restore saved opacity
        saved_opacity = cfg.get("opacity", 1.0)
        try:    self._opacity = max(0.2, min(1.0, float(saved_opacity)))
        except: self._opacity = 1.0

        # Restore always-on-top preference
        self._always_on_top = bool(cfg.get("always_on_top", False))

        # Load saved keymap
        saved_km = cfg.get("keymap", {})
        self._keymap = dict(_DEFAULT_KEYMAP)
        self._keymap.update(saved_km)

        # Restore saved theme before building UI
        saved_theme = cfg.get("theme", {})
        if saved_theme:
            import builtins
            g = globals()
            for k, gk in (("bg","BG"),("panel","PANEL"),("border","BORDER"),
                          ("dim","DIM"),("text","TEXT"),("subtext","SUBTEXT"),
                          ("accent","ACCENT"),("accent2","ACCENT2"),("purple","ROKU_PURPLE"),
                          ("green","GREEN"),("red","RED"),("yellow","YELLOW")):
                if k in saved_theme:
                    g[gk] = saved_theme[k]
            self.configure(bg=BG)

        self._build_ui()

        # Restore saved geometry — applied after window is ready
        self._saved_geo = {
            "w": int(cfg.get("w", 260)), "h": int(cfg.get("h", 500)),
            "x": int(cfg.get("x", 100)), "y": int(cfg.get("y", 100)),
            "rel_x": cfg.get("rel_x"),   "rel_y": cfg.get("rel_y"),
            "monitor": cfg.get("monitor", 0),
        }
        self.after(10, self._restore_geometry)

        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.bind("<Destroy>",       self._on_destroy)
        self.bind_all("<KeyPress>",  self._on_key)
        self.bind("<FocusIn>",       lambda e: self._on_main_focus() if e.widget is self else None)
        self.bind("<ButtonPress-1>",  lambda e: self._lift_popups(), add="+")
        self.bind("<Configure>",      lambda e: self._lift_popups() if e.widget is self else None)
        self.bind("<FocusOut>", lambda e: self.wm_attributes("-topmost", False) if (e.widget is self and not self._always_on_top) else None)
        self.bind("<Motion>",          self._update_cursor)
        # Resize from edges only (not drag-to-move — that is titlebar only)
        self.bind("<ButtonPress-1>",   self._resize_start)
        self.bind("<B1-Motion>",       self._resize_move)
        self.bind("<ButtonRelease-1>", self._drag_end)

        # Apply opacity/topmost first, THEN hide from Alt+Tab last
        # (-topmost can cause Windows to re-add the window to Alt+Tab)
        self.after(100, self._apply_opacity)
        self.after(110, self._apply_always_on_top)
        self.after(200, self._init_window_style)
        # If we have a saved IP try to reconnect silently, else scan
        if saved_ip:
            self.after(150, lambda: self._try_reconnect_startup(saved_ip))
        else:
            self.after(150, self._start_discovery)

    def _on_main_focus(self):
        """When main window gains focus, push all open popups back on top."""
        self._apply_always_on_top()
        self._lift_popups()

    def _lift_popups(self):
        """Lift all open popups above the main window."""
        for win, _ in list(_open_popups):
            try:
                if win.winfo_exists():
                    win.lift()
            except Exception:
                pass

    def _try_reconnect_startup(self, ip):
        """On launch try the last-used IP silently before falling back to scan."""
        self._set_status("Reconnecting…", ACCENT, 0)
        def _check():
            info = ecp_device_info(ip)
            if info:
                name = (info.get("user-device-name") or info.get("friendly-device-name")
                        or info.get("model-name") or ip)
                self.after(0, lambda: self._connect({"ip": ip, "name": name}))
            else:
                self.after(0, self._start_discovery)
        threading.Thread(target=_check, daemon=True).start()

    def _restore_geometry(self):
        try:
            g = self._saved_geo
            w, h = g["w"], g["h"]
            x, y = g["x"], g["y"]
            rel_x, rel_y = g["rel_x"], g["rel_y"]
            mon_i = g["monitor"]
            if rel_x is not None and rel_y is not None:
                monitors = self._get_monitors()
                if 0 <= mon_i < len(monitors):
                    mx, my, mw, mh = monitors[mon_i]
                    cx = mx + int(rel_x) + w // 2
                    cy = my + int(rel_y) + h // 2
                    # Only use monitor-relative pos if it lands on a valid monitor
                    on_screen = any(
                        mx2 <= cx < mx2 + mw2 and my2 <= cy < my2 + mh2
                        for mx2, my2, mw2, mh2 in monitors
                    )
                    if on_screen:
                        x = mx + int(rel_x)
                        y = my + int(rel_y)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry("260x500+100+100")

    # ── Taskbar hiding — exact PyDisplay _init_click_through ──────────────────

    def _init_window_style(self):
        if not _WIN32: return
        try:
            hwnd = _user32.GetAncestor(self.winfo_id(), 2)
            if not hwnd:
                hwnd = _user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            self._hwnd = hwnd
            style = _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            style = (style | _WS_EX_TOOLWINDOW) & ~_WS_EX_APPWINDOW
            _user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style)
            _user32.SetWindowPos(hwnd, _HWND_TOP, 0, 0, 0, 0,
                _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER |
                _SWP_NOACTIVATE | _SWP_FRAMECHANGED)
            self.withdraw()
            self.after(50, self.deiconify)
        except Exception:
            self._hwnd = None

    # ── Drag / resize — mirrors PyDisplay _drag_start / _drag_move ────────────

    def _get_edge(self, x, y):
        """Only allow resize from the bottom-right corner."""
        w = self.winfo_width(); h = self.winfo_height(); m = _EDGE_MARGIN
        if x > w - m and y > h - m:
            return "se"
        return None

    _EDGE_CURSORS = {
        "se": "size_nw_se",
        None: "arrow",
    }

    def _update_cursor(self, e):
        edge = self._get_edge(e.x, e.y)
        cur  = self._EDGE_CURSORS.get(edge, "arrow")
        try: self.config(cursor=cur)
        except Exception: pass

    def _drag_start(self, e):
        self.wm_attributes("-topmost", True)
        self._resize_edge = self._get_edge(e.x, e.y)
        self._drag_x  = self.winfo_pointerx()
        self._drag_y  = self.winfo_pointery()
        self._drag_wx = self.winfo_x()
        self._drag_wy = self.winfo_y()
        self._drag_ww = self.winfo_width()
        self._drag_wh = self.winfo_height()

    def _drag_move(self, e):
        px = self.winfo_pointerx(); py = self.winfo_pointery()
        dx = px - self._drag_x;    dy = py - self._drag_y
        edge = self._resize_edge
        if edge is None:
            self.geometry(f"+{self._drag_wx+dx}+{self._drag_wy+dy}")
        else:
            x, y = self._drag_wx, self._drag_wy
            w, h = self._drag_ww, self._drag_wh
            if "e" in edge: w = max(_MIN_W, w + dx)
            if "s" in edge: h = max(_MIN_H, h + dy)
            if "w" in edge:
                w = max(_MIN_W, w - dx)
                x = self._drag_wx + self._drag_ww - w
            if "n" in edge:
                h = max(_MIN_H, h - dy)
                y = self._drag_wy + self._drag_wh - h
            self.geometry(f"{w}x{h}+{x}+{y}")

    def _resize_start(self, e):
        """Like _drag_start but only activates on edge zones — ignores body clicks."""
        edge = self._get_edge(e.x, e.y)
        if edge is None: return          # not an edge — ignore
        self._resize_edge = edge
        self._drag_x  = self.winfo_pointerx()
        self._drag_y  = self.winfo_pointery()
        self._drag_wx = self.winfo_x()
        self._drag_wy = self.winfo_y()
        self._drag_ww = self.winfo_width()
        self._drag_wh = self.winfo_height()

    def _grip_resize_start(self, e):
        """Called from the grip widget — always resize from SE corner."""
        self._resize_edge = "se"
        self._drag_x  = self.winfo_pointerx()
        self._drag_y  = self.winfo_pointery()
        self._drag_wx = self.winfo_x()
        self._drag_wy = self.winfo_y()
        self._drag_ww = self.winfo_width()
        self._drag_wh = self.winfo_height()

    def _resize_move(self, e):
        """Resize only — no move."""
        if self._resize_edge is None: return
        px = self.winfo_pointerx(); py = self.winfo_pointery()
        dx = px - self._drag_x;    dy = py - self._drag_y
        edge = self._resize_edge
        x, y = self._drag_wx, self._drag_wy
        w, h = self._drag_ww, self._drag_wh
        if "e" in edge: w = max(_MIN_W, w + dx)
        if "s" in edge: h = max(_MIN_H, h + dy)
        if "w" in edge:
            w = max(_MIN_W, w - dx)
            x = self._drag_wx + self._drag_ww - w
        if "n" in edge:
            h = max(_MIN_H, h - dy)
            y = self._drag_wy + self._drag_wh - h
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _drag_end(self, e):
        self._write_pos()

    def _get_monitors(self):
        """Return list of (x, y, w, h) for each monitor. Falls back to primary only."""
        monitors = []
        if _WIN32:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                MONITOR_DEFAULTTONULL = 0
                EnumDisplayMonitors = user32.EnumDisplayMonitors
                from ctypes import WINFUNCTYPE, POINTER, byref
                from ctypes.wintypes import BOOL, HMONITOR, HDC, RECT
                MonitorProc = WINFUNCTYPE(BOOL, HMONITOR, HDC, POINTER(RECT), ctypes.c_long)
                rects = []
                def _cb(hm, hdc, lprect, lparam):
                    r = lprect.contents
                    rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                    return True
                EnumDisplayMonitors(None, None, MonitorProc(_cb), 0)
                monitors = rects
            except Exception:
                pass
        if not monitors:
            sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
            monitors = [(0, 0, sw, sh)]
        return monitors

    def _write_pos(self):
        try:
            wx, wy = self.winfo_x(), self.winfo_y()
            ww, wh = self.winfo_width(), self.winfo_height()
            # Find which monitor the window centre is on
            cx = wx + ww // 2; cy = wy + wh // 2
            monitors = self._get_monitors()
            mon_idx = 0
            for i, (mx, my, mw, mh) in enumerate(monitors):
                if mx <= cx < mx + mw and my <= cy < my + mh:
                    mon_idx = i; break
            mx, my, mw, mh = monitors[mon_idx]
            # Store position relative to that monitor
            _write_cfg({"x": wx, "y": wy, "w": ww, "h": wh,
                        "monitor": mon_idx,
                        "rel_x": wx - mx, "rel_y": wy - my})
        except Exception:
            pass

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _quit(self):
        self._closing = True
        self._write_pos()
        _write_cfg({"last_ip": self._ip or ""})
        _clear_lock_pid()
        self.destroy()

    def _on_destroy(self, e):
        if e.widget is self and not self._closing:
            self._quit()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _apply_opacity(self, value=None):
        if value is not None:
            self._opacity = value
        try:
            self.wm_attributes("-alpha", self._opacity)
        except Exception:
            pass

    def _apply_always_on_top(self, value=None):
        if value is not None:
            self._always_on_top = value
            _write_cfg({"always_on_top": value})
        try:
            self.wm_attributes("-topmost", self._always_on_top)
        except Exception:
            pass
        # Changing -topmost can cause Windows to re-add the window to Alt+Tab;
        # re-stamp TOOLWINDOW to keep it hidden
        if _WIN32 and hasattr(self, "_hwnd") and self._hwnd:
            try:
                style = _user32.GetWindowLongW(self._hwnd, _GWL_EXSTYLE)
                style = (style | _WS_EX_TOOLWINDOW) & ~_WS_EX_APPWINDOW
                _user32.SetWindowLongW(self._hwnd, _GWL_EXSTYLE, style)
                _user32.SetWindowPos(self._hwnd, _HWND_TOP, 0, 0, 0, 0,
                    _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER |
                    _SWP_NOACTIVATE | _SWP_FRAMECHANGED)
            except Exception:
                pass
        try:
            if hasattr(self, "_pin_btn"):
                self._pin_btn.config(
                    fg=ACCENT if self._always_on_top else SUBTEXT,
                    bg=DIM    if self._always_on_top else BORDER)
        except Exception:
            pass


    def _build_ui(self):
        tb = _make_titlebar(self, PANEL, BORDER, SUBTEXT, RED,
                            on_close=self._quit,
                            title_text="  📺  PyRokuMe",
                            title_fg=SUBTEXT, title_bg=PANEL)
        # Theme button on right side of titlebar
        theme_btn = tk.Label(tb, text=" 🎨 ", bg=BORDER, fg=SUBTEXT,
                             font=(_FONT, _FS, "bold"), cursor="hand2", padx=2, pady=2)
        theme_btn.pack(side="right", padx=(0, 4))
        theme_btn.bind("<Button-1>", lambda e: self._open_theme())
        theme_btn.bind("<Enter>",    lambda e: theme_btn.config(fg=ACCENT))
        theme_btn.bind("<Leave>",    lambda e: theme_btn.config(fg=SUBTEXT))

        # Always-on-top pin button
        self._pin_btn = tk.Label(tb, text=" 📌 ",
                                 bg=DIM if self._always_on_top else BORDER,
                                 fg=ACCENT if self._always_on_top else SUBTEXT,
                                 font=(_FONT, _FS, "bold"), cursor="hand2", padx=2, pady=2)
        self._pin_btn.pack(side="right", padx=(0, 2))
        self._pin_btn.bind("<Button-1>", lambda e: self._apply_always_on_top(not self._always_on_top))
        self._pin_btn.bind("<Enter>",    lambda e: self._pin_btn.config(fg=GREEN))
        self._pin_btn.bind("<Leave>",    lambda e: self._pin_btn.config(
            fg=ACCENT if self._always_on_top else SUBTEXT))


        # Bind drag (move only) to titlebar — body is resize-edge only
        x_btn = tb.winfo_children()[0]   # first child is always the ✕ button
        for w in [tb] + list(tb.winfo_children()):
            if w in {theme_btn, self._pin_btn, x_btn}: continue
            w.bind("<ButtonPress-1>",   self._drag_start)
            w.bind("<B1-Motion>",       self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)

        # Device bar
        info_row = tk.Frame(self, bg=PANEL, padx=10, pady=5)
        info_row.pack(fill="x")
        self._device_lbl = tk.Label(info_row, text="No device connected",
                                     bg=PANEL, fg=SUBTEXT,
                                     font=(_FONT, _FS - 1, "bold"), anchor="w")
        self._device_lbl.pack(side="left", fill="x", expand=True)
        self._disc_btn = tk.Label(info_row, text="⌕ SCAN", bg=BORDER,
                                   fg=ACCENT, font=(_FONT, _FS - 2, "bold"),
                                   cursor="hand2", padx=8, pady=2)
        self._disc_btn.pack(side="right")
        self._disc_btn.bind("<Button-1>", lambda e: self._start_discovery())
        self._disc_btn.bind("<Enter>",    lambda e: self._disc_btn.config(fg=GREEN))
        self._disc_btn.bind("<Leave>",    lambda e: self._disc_btn.config(fg=ACCENT))
        # Saved devices quick-switch button
        self._sw_btn = tk.Label(info_row, text="▾", bg=BORDER,
                                fg=SUBTEXT, font=(_FONT, _FS, "bold"),
                                cursor="hand2", padx=6, pady=2)
        self._sw_btn.pack(side="right", padx=(0, 2))
        self._sw_btn.bind("<Button-1>", lambda e: self._open_device_switcher())
        self._sw_btn.bind("<Enter>",    lambda e: self._sw_btn.config(fg=ACCENT))
        self._sw_btn.bind("<Leave>",    lambda e: self._sw_btn.config(fg=SUBTEXT))
        wol_btn = tk.Label(info_row, text="⚡WOL", bg=BORDER,
                           fg=YELLOW, font=(_FONT, _FS - 2, "bold"),
                           cursor="hand2", padx=8, pady=2)
        wol_btn.pack(side="right", padx=(0, 4))
        wol_btn.bind("<Button-1>", lambda e: self._open_wol())
        wol_btn.bind("<Enter>",    lambda e: wol_btn.config(fg=GREEN))
        wol_btn.bind("<Leave>",    lambda e: wol_btn.config(fg=YELLOW))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Stretching body — grid rows all weighted so buttons fill the window ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=6)

        # 7 content rows: r1, dpad-up, dpad-mid, dpad-dn, r3, r4, r5
        # Separator rows (thin) are weight=0.
        # All button rows share equal weight so they grow together.
        _ROW_WEIGHTS = {
            0: 1,   # power/home/back/mute
            1: 0,   # sep
            2: 1,   # dpad up
            3: 1,   # dpad mid (OK row — same height as up/down)
            4: 1,   # dpad down
            5: 0,   # sep
            6: 1,   # vol/ch
            7: 1,   # playback
            8: 0,   # sep
            9: 1,   # apps/text/info
        }
        for row, w in _ROW_WEIGHTS.items():
            body.rowconfigure(row, weight=w, uniform="rows" if w else "")
        body.columnconfigure(0, weight=1)

        def _row_frame(row, pad_top=4, pad_bot=4):
            f = tk.Frame(body, bg=BG)
            f.grid(row=row, column=0, sticky="nsew",
                   pady=(pad_top, pad_bot), padx=0)
            f.columnconfigure(0, weight=1)
            f.rowconfigure(0, weight=1)
            return f

        # ── Row 0 — Power / Home / Back / Mute ───────────────────────────────
        r1 = _row_frame(0)
        r1.columnconfigure((0, 1, 2, 3), weight=1, uniform="r1")
        r1.rowconfigure(0, weight=1)
        self._gbtn(r1, "←", lambda: ecp_keypress(self._ip, "Back"),
                   SUBTEXT, "Back  [Backspace / B]").grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        self._gbtn(r1, "⌂", lambda: ecp_keypress(self._ip, "Home"),
                   SUBTEXT, "Home  [Esc / H]").grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        self._gbtn(r1, "🔇", lambda: ecp_keypress(self._ip, "VolumeMute"),
                   YELLOW,  "Mute  [\\ / M]").grid(row=0, column=2, sticky="nsew", padx=3, pady=3)
        self._gbtn(r1, "⏻", lambda: ecp_keypress(self._ip, "Power"),
                   RED,     "Power toggle").grid(row=0, column=3, sticky="nsew", padx=3, pady=3)

        # sep
        tk.Frame(body, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew",
                                                   padx=6, pady=2)

        # ── D-pad — rows 2/3/4 ────────────────────────────────────────────────
        # 3-col grid: col0=left, col1=center, col2=right — all uniform weight.
        # Up/Down buttons live in col1 only.
        # Left/Right buttons live in col0 and col2 respectively.
        # A single invisible placeholder Label in every unused cell locks each
        # column to a real size so uniform="dpad" always works, even after
        # a theme rebuild that destroys and recreates all widgets.
        def _spacer(parent, col):
            """Invisible placeholder that holds its column open."""
            tk.Label(parent, text="", bg=BG, width=4,
                     relief="flat", padx=0, pady=0).grid(
                row=0, column=col, sticky="nsew")

        for drow in (2, 3, 4):
            f = tk.Frame(body, bg=BG)
            f.grid(row=drow, column=0, sticky="nsew", pady=2)
            f.columnconfigure((0, 1, 2), weight=1, uniform="dpad")
            f.rowconfigure(0, weight=1)

            if drow == 2:   # Up
                _spacer(f, 0)
                self._gbtn(f, "▲", lambda: ecp_keypress(self._ip, "Up"),
                           ROKU_PURPLE, "Up  [W / ↑]").grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
                _spacer(f, 2)
            elif drow == 3: # Left / OK / Right
                self._gbtn(f, "◀", lambda: ecp_keypress(self._ip, "Left"),
                           ROKU_PURPLE, "Left  [A / ←]").grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
                self._gbtn(f, "OK", lambda: ecp_keypress(self._ip, "Select"),
                           GREEN, "OK  [Enter / Space / O]",
                           bold=True).grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
                self._gbtn(f, "▶", lambda: ecp_keypress(self._ip, "Right"),
                           ROKU_PURPLE, "Right  [D / →]").grid(row=0, column=2, sticky="nsew", padx=3, pady=3)
            else:           # Down
                _spacer(f, 0)
                self._gbtn(f, "▼", lambda: ecp_keypress(self._ip, "Down"),
                           ROKU_PURPLE, "Down  [S / ↓]").grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
                _spacer(f, 2)

        # sep
        tk.Frame(body, bg=BORDER, height=1).grid(row=5, column=0, sticky="ew",
                                                   padx=6, pady=2)

        # ── Row 6 — Vol− / Vol+ / Ch− / Ch+ ──────────────────────────────────
        r3 = _row_frame(6)
        r3.columnconfigure((0, 1, 2, 3), weight=1, uniform="r3")
        r3.rowconfigure(0, weight=1)
        self._gbtn(r3, "Ch−",  lambda: ecp_keypress(self._ip, "ChannelDown"),
                   SUBTEXT, "Ch−").grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        self._gbtn(r3, "Ch+",  lambda: ecp_keypress(self._ip, "ChannelUp"),
                   SUBTEXT, "Ch+").grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        self._gbtn(r3, "Vol−", lambda: ecp_keypress(self._ip, "VolumeDown"),
                   ACCENT2, "Vol−  [[ / -]").grid(row=0, column=2, sticky="nsew", padx=3, pady=3)
        self._gbtn(r3, "Vol+", lambda: ecp_keypress(self._ip, "VolumeUp"),
                   ACCENT2, "Vol+  [] / +]").grid(row=0, column=3, sticky="nsew", padx=3, pady=3)

        # ── Row 7 — ⏮ ⏯ ⏭ ↺ ────────────────────────────────────────────────
        r4 = _row_frame(7)
        r4.columnconfigure((0, 1, 2), weight=1, uniform="r4")
        r4.rowconfigure(0, weight=1)
        self._gbtn(r4, "⏮", lambda: ecp_keypress(self._ip, "Rev"),
                   SUBTEXT, "Rewind  [, / R]").grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        self._gbtn(r4, "⏯", lambda: ecp_keypress(self._ip, "Play"),
                   GREEN,   "Play/Pause  [/ / P]").grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
        self._gbtn(r4, "⏭", lambda: ecp_keypress(self._ip, "Fwd"),
                   SUBTEXT, "FF  [. / F]").grid(row=0, column=2, sticky="nsew", padx=3, pady=3)

        # sep
        tk.Frame(body, bg=BORDER, height=1).grid(row=8, column=0, sticky="ew",
                                                   padx=6, pady=2)

        # ── Row 9 — ✦ Apps / ⌖ Info ──────────────────────────────────────────
        r5 = _row_frame(9, pad_bot=2)
        r5.columnconfigure((0, 1), weight=1, uniform="r5")
        r5.rowconfigure(0, weight=1)
        self._gbtn(r5, "✦ Apps", self._open_apps,
                   ACCENT,  "Browse & launch apps").grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        self._gbtn(r5, "⌖ Info", lambda: ecp_keypress(self._ip, "Info"),
                   SUBTEXT, "Info  [I]").grid(row=0, column=1, sticky="nsew", padx=3, pady=3)

        # Status bar with resize grip
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="bottom")
        _bot = tk.Frame(self, bg=PANEL)
        _bot.pack(fill="x", side="bottom")

        self._status_lbl = tk.Label(_bot, text="Ready", bg=PANEL, fg=DIM,
                                     font=(_FONT, _FS - 2), anchor="w",
                                     padx=10, pady=3)
        self._status_lbl.pack(side="left", fill="x", expand=True)

        # Resize grip — drawn as a 3×3 dot grid in the bottom-right corner
        _grip = tk.Canvas(_bot, bg=PANEL, width=16, height=16,
                          highlightthickness=0, cursor="size_nw_se")
        _grip.pack(side="right", padx=(0, 2), pady=1)

        def _draw_grip(c=_grip):
            c.delete("all")
            dot = DIM
            r = 1
            for row in range(3):
                for col in range(3):
                    if row + col >= 2:   # lower-right triangle only
                        cx2 = 4 + col * 5
                        cy2 = 4 + row * 5
                        c.create_oval(cx2-r, cy2-r, cx2+r, cy2+r, fill=dot, outline="")
        _draw_grip()
        _grip.bind("<Configure>", lambda e: _draw_grip())

        # Wire grip to resize
        _grip.bind("<ButtonPress-1>",   self._grip_resize_start)
        _grip.bind("<B1-Motion>",       self._resize_move)
        _grip.bind("<ButtonRelease-1>", self._drag_end)
        _grip.bind("<Enter>", lambda e: _grip.config(cursor="size_nw_se"))

        self._resize_grip = _grip

    # ── Grid button factory — fills its cell completely ────────────────────────

    def _gbtn(self, parent, label, cmd, fg=SUBTEXT, tip="", bold=False):
        """Button that fills its grid cell — height driven entirely by row weight."""
        b = tk.Label(parent, text=label, bg=BORDER, fg=fg,
                     font=(_FONT, _FS + 2, "bold" if bold else "normal"),
                     cursor="hand2", padx=4, pady=0,
                     anchor="center", relief="flat")

        def _click(e):
            if not self._ip:
                self._set_status("No Roku connected — click ⌕ SCAN", RED); return
            threading.Thread(target=cmd, daemon=True).start()
            orig = b.cget("bg"); b.config(bg=DIM)
            self.after(120, lambda: b.config(bg=orig) if b.winfo_exists() else None)

        b.bind("<Button-1>", _click)
        b.bind("<Enter>",    lambda e: b.config(bg=DIM))
        b.bind("<Leave>",    lambda e: b.config(bg=BORDER))
        if tip:
            b.bind("<Enter>", lambda e, t=tip: (b.config(bg=DIM), self._set_status(t, DIM, 0)), add="+")
            b.bind("<Leave>", lambda e: self._set_status("", DIM, 0), add="+")
        # Block drag propagation (but NOT ButtonPress-1 — that kills the click)
        b.bind("<B1-Motion>",       lambda e: "break")
        b.bind("<ButtonRelease-1>", lambda e: "break")
        return b

    # grid() helper so callers can do .grid(row=0, column=1, sticky="nsew", padx=3, pady=3)
    def _gbtn_grid(self, b, row, col, padx=3, pady=3):
        b.grid(row=row, column=col, sticky="nsew", padx=padx, pady=pady)
        return b

    # Keep old _btn for any non-grid use (popups etc.)
    def _btn(self, parent, label, cmd, fg=SUBTEXT, tip="", wide=False, bold=False):
        b = tk.Label(parent, text=label, bg=BORDER, fg=fg,
                     font=(_FONT, _FS, "bold" if bold else "normal"),
                     cursor="hand2", padx=8, pady=5,
                     width=(6 if wide else None),
                     anchor="center", relief="flat")

        def _click(e):
            if not self._ip:
                self._set_status("No Roku connected — click ⌕ SCAN", RED); return
            threading.Thread(target=cmd, daemon=True).start()
            orig = b.cget("bg"); b.config(bg=DIM)
            self.after(120, lambda: b.config(bg=orig) if b.winfo_exists() else None)

        b.bind("<Button-1>", _click)
        b.bind("<Enter>",    lambda e: b.config(bg=DIM))
        b.bind("<Leave>",    lambda e: b.config(bg=BORDER))
        if tip:
            b.bind("<Enter>", lambda e, t=tip: (b.config(bg=DIM), self._set_status(t, DIM, 0)), add="+")
            b.bind("<Leave>", lambda e: self._set_status("", DIM, 0), add="+")
        return b

    # ── Status ────────────────────────────────────────────────────────────────

    def _set_status(self, msg, color=DIM, duration=2500):
        if self._status_job:
            try: self.after_cancel(self._status_job)
            except Exception: pass
            self._status_job = None
        self._status_lbl.config(text=msg or "Ready", fg=color)
        if msg and duration:
            self._status_job = self.after(duration, lambda: self._set_status("", DIM, 0))

    # ── Keyboard shortcuts ─────────────────────────────────────────────────────

    def _on_key(self, e):
        if not self._ip: return
        k = e.keysym.lower()
        key = self._keymap.get(k)
        if key:
            threading.Thread(target=ecp_keypress, args=(self._ip, key), daemon=True).start()

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _start_discovery(self, preferred_ip=None):
        self._disc_btn.config(text="⌕ ...", fg=YELLOW, cursor="arrow")
        self._disc_btn.unbind("<Button-1>")
        self._set_status(f"Scanning SSDP + {_SCAN_SUBNET}.1–99…", ACCENT, 0)
        threading.Thread(target=self._discovery_worker,
                         args=(preferred_ip,), daemon=True).start()

    def _discovery_worker(self, preferred_ip=None):
        raw = discover_all(timeout=5.0)
        enriched = []
        for d in raw:
            info = ecp_device_info(d["ip"])
            if not info: continue   # port open but not a Roku ECP endpoint
            name = (info.get("user-device-name")
                    or info.get("friendly-device-name")
                    or info.get("model-name") or d["ip"])
            enriched.append({"ip": d["ip"], "name": name, "info": info})
        self.after(0, lambda: self._discovery_done(enriched, preferred_ip))

    def _discovery_done(self, devices, preferred_ip=None):
        self._disc_btn.config(text="⌕ SCAN", fg=ACCENT, cursor="hand2")
        self._disc_btn.bind("<Button-1>", lambda e: self._start_discovery())
        self._devices = devices
        if not devices:
            self._set_status("No Roku found. Enter IP manually.", RED, 0)
            self._open_manual_ip(); return
        # Always show picker — never auto-connect
        self._open_device_picker(devices)

    def _connect(self, device):
        self._ip = device["ip"]
        self._device_name = device["name"]
        self._device_lbl.config(
            text=f"📺  {device['name']}  [{device['ip']}]", fg=GREEN)
        self._was_online = True
        # Add/update in saved devices list (max 10, most-recent first)
        entry = {"name": device["name"], "ip": device["ip"]}
        self._saved_devices = [d for d in self._saved_devices
                                if d["ip"] != entry["ip"]]
        self._saved_devices.insert(0, entry)
        self._saved_devices = self._saved_devices[:10]
        _write_cfg({"last_ip": self._ip, "saved_devices": self._saved_devices})
        self._set_status(f"Connected to {device['name']}", GREEN)
        self._start_reconnect_watcher()

    # ── Auto-reconnect watcher ───────────────────────────────────────────────────

    def _start_reconnect_watcher(self):
        if self._reconnect_job:
            try: self.after_cancel(self._reconnect_job)
            except Exception: pass
        self._reconnect_job = self.after(10000, self._reconnect_tick)

    def _reconnect_tick(self):
        if self._closing or not self._ip:
            return
        def _check():
            info = ecp_device_info(self._ip)
            self.after(0, lambda: self._reconnect_result(info))
        threading.Thread(target=_check, daemon=True).start()

    def _reconnect_result(self, info):
        if self._closing: return
        if info:
            if not self._was_online:
                # Came back online
                self._was_online = True
                self._device_lbl.config(
                    text=f"📺  {self._device_name}  [{self._ip}]", fg=GREEN)
                self._set_status(f"Reconnected to {self._device_name}", GREEN)
        else:
            if self._was_online:
                # Just went offline
                self._was_online = False
                self._device_lbl.config(
                    text=f"📺  {self._device_name}  [{self._ip}]  ⚠ offline", fg=YELLOW)
                self._set_status(f"Lost connection to {self._device_name}", YELLOW)
        # Schedule next check (5s if offline, 12s if online)
        interval = 5000 if not self._was_online else 12000
        self._reconnect_job = self.after(interval, self._reconnect_tick)

    # ── Device picker ──────────────────────────────────────────────────────────

    def _open_device_picker(self, devices):
        dlg = tk.Toplevel(self); dlg.configure(bg=BG)
        dlg.resizable(False, False); dlg.overrideredirect(True)
        dlg.withdraw()
        dlg.wm_attributes("-topmost", True)
        dlg.transient(self)
        _register_popup(dlg)
        _make_titlebar(dlg, PANEL, BORDER, SUBTEXT, RED, on_close=dlg.destroy,
                       title_text="  Select Roku Device", title_fg=TEXT, title_bg=PANEL, draggable=False)
        inner = tk.Frame(dlg, bg=BG, padx=14, pady=10); inner.pack(fill="both")
        count = len(devices)
        lbl = "1 Roku device found:" if count == 1 else f"{count} Roku devices found:"
        tk.Label(inner, text=lbl, bg=BG, fg=TEXT,
                 font=(_FONT, _FS, "bold")).pack(anchor="w", pady=(0, 8))
        for d in devices:
            row = tk.Frame(inner, bg=BORDER, cursor="hand2"); row.pack(fill="x", pady=3)
            tk.Label(row, text=f"  {d['name']}", bg=BORDER, fg=TEXT,
                     font=(_FONT, _FS, "bold"), anchor="w",
                     padx=8, pady=6).pack(side="left", fill="x", expand=True)
            tk.Label(row, text=d["ip"], bg=BORDER, fg=SUBTEXT,
                     font=(_FONT, _FS - 2), padx=8).pack(side="right")
            def _pick(dev=d): self._connect(dev); dlg.destroy()
            for w in [row] + list(row.winfo_children()):
                w.bind("<Button-1>", lambda e, fn=_pick: fn())
                w.bind("<Enter>",    lambda e, r=row: r.config(bg=DIM))
                w.bind("<Leave>",    lambda e, r=row: r.config(bg=BORDER))
        tk.Frame(dlg, bg=BORDER, height=1).pack(fill="x", padx=10)
        man = tk.Label(dlg, text="Enter IP manually…", bg=BG, fg=SUBTEXT,
                       font=(_FONT, _FS - 2), cursor="hand2", pady=6)
        man.pack()
        man.bind("<Button-1>", lambda e: (dlg.destroy(), self._open_manual_ip()))
        man.bind("<Enter>",    lambda e: man.config(fg=ACCENT))
        man.bind("<Leave>",    lambda e: man.config(fg=SUBTEXT))
        dlg.update_idletasks()
        cx = self.winfo_rootx() + self.winfo_width()  // 2 - dlg.winfo_reqwidth()  // 2
        cy = self.winfo_rooty() + self.winfo_height() // 2 - dlg.winfo_reqheight() // 2
        dlg.geometry(f"+{cx}+{cy}"); dlg.deiconify()

    # ── Manual IP ─────────────────────────────────────────────────────────────

    def _open_manual_ip(self):
        if self._popup_manual and self._popup_manual.winfo_exists():
            self._popup_manual.lift(); self._popup_manual.focus_force(); return
        dlg = tk.Toplevel(self); dlg.configure(bg=BG)
        dlg.resizable(False, False); dlg.overrideredirect(True)
        dlg.withdraw()
        dlg.wm_attributes("-topmost", True)
        dlg.transient(self)
        self._popup_manual = dlg
        _register_popup(dlg)
        _make_titlebar(dlg, PANEL, BORDER, SUBTEXT, RED, on_close=dlg.destroy,
                       title_text="  Enter Roku IP", title_fg=TEXT, title_bg=PANEL, draggable=False)
        inner = tk.Frame(dlg, bg=BG, padx=16, pady=12); inner.pack(fill="both")
        tk.Label(inner, text="Roku IP address:", bg=BG, fg=TEXT,
                 font=(_FONT, _FS)).pack(anchor="w", pady=(0, 4))
        entry = tk.Entry(inner, bg=BORDER, fg=TEXT, insertbackground=TEXT,
                         font=(_FONT, _FS), relief="flat", width=22)
        entry.pack(fill="x", ipady=4)
        entry.insert(0, self._ip or ""); entry.select_range(0, "end"); entry.focus_set()
        status = tk.Label(inner, text="", bg=BG, fg=RED, font=(_FONT, _FS - 3))
        status.pack(pady=(2, 0))
        btn_row = tk.Frame(inner, bg=BG); btn_row.pack(fill="x", pady=(8, 0))
        def _try():
            ip = entry.get().strip()
            if not ip: status.config(text="Enter an IP address."); return
            status.config(text="Connecting…", fg=YELLOW); dlg.update_idletasks()
            def _w():
                info = ecp_device_info(ip)
                if info:
                    name = (info.get("user-device-name")
                            or info.get("friendly-device-name")
                            or info.get("model-name") or ip)
                    self.after(0, lambda: (
                        self._connect({"ip": ip, "name": name, "info": info}),
                        dlg.destroy()))
                else:
                    self.after(0, lambda: status.config(
                        text="Could not reach Roku at that IP.", fg=RED))
            threading.Thread(target=_w, daemon=True).start()
        conn = tk.Label(btn_row, text="Connect", bg=ROKU_PURPLE, fg=TEXT,
                        font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=3)
        conn.pack(side="left")
        conn.bind("<Button-1>", lambda e: _try())
        conn.bind("<Enter>",    lambda e: conn.config(bg=GREEN, fg=BG))
        conn.bind("<Leave>",    lambda e: conn.config(bg=ROKU_PURPLE, fg=TEXT))
        entry.bind("<Return>",  lambda e: _try())
        cancel = tk.Label(btn_row, text="Cancel", bg=BORDER, fg=SUBTEXT,
                          font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=3)
        cancel.pack(side="right")
        cancel.bind("<Button-1>", lambda e: dlg.destroy())
        cancel.bind("<Enter>",    lambda e: cancel.config(fg=RED))
        cancel.bind("<Leave>",    lambda e: cancel.config(fg=SUBTEXT))
        dlg.update_idletasks()
        cx = self.winfo_rootx() + self.winfo_width()  // 2 - dlg.winfo_reqwidth()  // 2
        cy = self.winfo_rooty() + self.winfo_height() // 2 - dlg.winfo_reqheight() // 2
        dlg.geometry(f"+{cx}+{cy}"); dlg.deiconify()

    # ── Saved device switcher ────────────────────────────────────────────────────

    def _open_device_switcher(self):
        if not self._saved_devices:
            self._set_status("No saved devices — click ⌕ SCAN first", SUBTEXT); return

        dlg = tk.Toplevel(self); dlg.configure(bg=BG)
        dlg.resizable(False, False); dlg.overrideredirect(True)
        dlg.withdraw(); dlg.wm_attributes("-topmost", True); dlg.transient(self)
        _register_popup(dlg)

        _make_titlebar(dlg, PANEL, BORDER, SUBTEXT, RED, on_close=dlg.destroy,
                       title_text="  📺  Saved Devices", title_fg=TEXT, title_bg=PANEL, draggable=False)
        inner = tk.Frame(dlg, bg=BG, padx=12, pady=8); inner.pack(fill="both")

        for d in self._saved_devices:
            is_current = d["ip"] == self._ip
            row = tk.Frame(inner, bg=BORDER if not is_current else DIM, cursor="hand2")
            row.pack(fill="x", pady=2)
            name_lbl = tk.Label(row, text=f"  {d['name']}", bg=row.cget("bg"),
                                fg=GREEN if is_current else TEXT,
                                font=(_FONT, _FS, "bold" if is_current else "normal"),
                                anchor="w", padx=6, pady=6)
            name_lbl.pack(side="left", fill="x", expand=True)
            ip_lbl = tk.Label(row, text=d["ip"], bg=row.cget("bg"),
                              fg=ACCENT if is_current else SUBTEXT,
                              font=(_FONT, _FS - 2), padx=8)
            ip_lbl.pack(side="left")
            # Delete button
            del_lbl = tk.Label(row, text=" ✕ ", bg=row.cget("bg"), fg=SUBTEXT,
                               font=(_FONT, _FS - 2), cursor="hand2", padx=4)
            del_lbl.pack(side="right")

            def _switch(dev=d):
                def _do():
                    info = ecp_device_info(dev["ip"])
                    name = (info.get("user-device-name") or info.get("friendly-device-name")
                            or dev["name"]) if info else dev["name"]
                    self.after(0, lambda: self._connect({"ip": dev["ip"], "name": name}))
                dlg.destroy()
                if dev["ip"] == self._ip:
                    self._set_status(f"Already connected to {dev['name']}", SUBTEXT); return
                self._set_status(f"Connecting to {dev['name']}…", ACCENT, 0)
                threading.Thread(target=_do, daemon=True).start()

            def _delete(dev=d):
                self._saved_devices = [x for x in self._saved_devices if x["ip"] != dev["ip"]]
                _write_cfg({"saved_devices": self._saved_devices})
                dlg.destroy()
                self._open_device_switcher()

            for w in [row, name_lbl, ip_lbl]:
                w.bind("<Button-1>", lambda e, fn=_switch: fn())
                w.bind("<Enter>",    lambda e, r=row, nl=name_lbl, il=ip_lbl, dl=del_lbl:
                       (r.config(bg=DIM), nl.config(bg=DIM), il.config(bg=DIM), dl.config(bg=DIM)))
                w.bind("<Leave>",    lambda e, r=row, nl=name_lbl, il=ip_lbl, dl=del_lbl, ic=is_current:
                       (r.config(bg=DIM if ic else BORDER), nl.config(bg=DIM if ic else BORDER),
                        il.config(bg=DIM if ic else BORDER), dl.config(bg=DIM if ic else BORDER)))
            del_lbl.bind("<Button-1>", lambda e, fn=_delete: fn())
            del_lbl.bind("<Enter>",    lambda e, b=del_lbl: b.config(fg=RED))
            del_lbl.bind("<Leave>",    lambda e, b=del_lbl: b.config(fg=SUBTEXT))

        # Scan for new
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(6, 2))
        scan_lbl = tk.Label(inner, text="⌕  Scan for new devices…", bg=BG,
                            fg=SUBTEXT, font=(_FONT, _FS - 1), cursor="hand2",
                            anchor="w", pady=4)
        scan_lbl.pack(fill="x")
        scan_lbl.bind("<Button-1>", lambda e: (dlg.destroy(), self._start_discovery()))
        scan_lbl.bind("<Enter>",    lambda e: scan_lbl.config(fg=ACCENT))
        scan_lbl.bind("<Leave>",    lambda e: scan_lbl.config(fg=SUBTEXT))

        dlg.update_idletasks()
        # Position below the ▾ button
        bx = self._sw_btn.winfo_rootx()
        by = self._sw_btn.winfo_rooty() + self._sw_btn.winfo_height() + 2
        dlg.geometry(f"+{bx}+{by}"); dlg.deiconify()

    # ── Wake on LAN ───────────────────────────────────────────────────────────

    def _open_wol(self):
        dlg = tk.Toplevel(self); dlg.configure(bg=BG)
        dlg.resizable(False, False); dlg.overrideredirect(True)
        dlg.withdraw()
        dlg.wm_attributes("-topmost", True)
        dlg.transient(self)
        _register_popup(dlg)
        _make_titlebar(dlg, PANEL, BORDER, SUBTEXT, RED, on_close=dlg.destroy,
                       title_text="  ⚡  Wake on LAN", title_fg=TEXT, title_bg=PANEL, draggable=False)
        inner = tk.Frame(dlg, bg=BG, padx=16, pady=12); inner.pack(fill="both")

        tk.Label(inner, text="Roku MAC address:", bg=BG, fg=TEXT,
                 font=(_FONT, _FS)).pack(anchor="w", pady=(0, 4))
        tk.Label(inner, text="Format: AA:BB:CC:DD:EE:FF", bg=BG, fg=DIM,
                 font=(_FONT, _FS - 2)).pack(anchor="w", pady=(0, 6))

        entry = tk.Entry(inner, bg=BORDER, fg=TEXT, insertbackground=TEXT,
                         font=(_FONT, _FS), relief="flat", width=22)
        entry.pack(fill="x", ipady=4)
        if self._mac:
            entry.insert(0, self._mac)
        entry.select_range(0, "end"); entry.focus_set()

        status = tk.Label(inner, text="", bg=BG, fg=RED, font=(_FONT, _FS - 2))
        status.pack(pady=(4, 0))

        btn_row = tk.Frame(inner, bg=BG); btn_row.pack(fill="x", pady=(10, 0))

        def _send():
            mac = entry.get().strip()
            if not mac:
                status.config(text="Enter a MAC address.", fg=RED); return
            try:
                send_wol(mac)
                self._mac = mac
                _write_cfg({"mac": mac})
                status.config(text="✔ Magic packet sent!", fg=GREEN)
                dlg.after(1500, dlg.destroy)
            except ValueError as ex:
                status.config(text=str(ex), fg=RED)
            except Exception as ex:
                status.config(text=f"Error: {ex}", fg=RED)

        send_btn = tk.Label(btn_row, text="⚡ Wake", bg=ROKU_PURPLE, fg=TEXT,
                            font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=3)
        send_btn.pack(side="left")
        send_btn.bind("<Button-1>", lambda e: _send())
        send_btn.bind("<Enter>",    lambda e: send_btn.config(bg=GREEN, fg=BG))
        send_btn.bind("<Leave>",    lambda e: send_btn.config(bg=ROKU_PURPLE, fg=TEXT))
        entry.bind("<Return>", lambda e: _send())

        cancel = tk.Label(btn_row, text="Cancel", bg=BORDER, fg=SUBTEXT,
                          font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=3)
        cancel.pack(side="right")
        cancel.bind("<Button-1>", lambda e: dlg.destroy())
        cancel.bind("<Enter>",    lambda e: cancel.config(fg=RED))
        cancel.bind("<Leave>",    lambda e: cancel.config(fg=SUBTEXT))

        dlg.update_idletasks()
        cx = self.winfo_rootx() + self.winfo_width()  // 2 - dlg.winfo_reqwidth()  // 2
        cy = self.winfo_rooty() + self.winfo_height() // 2 - dlg.winfo_reqheight() // 2
        dlg.geometry(f"+{cx}+{cy}"); dlg.deiconify()

    # ── Theme popup — PyDisplay style ────────────────────────────────────────

    # Colours that can change at runtime
    _theme_bg      = BG
    _theme_panel   = PANEL
    _theme_border  = BORDER
    _theme_dim     = DIM
    _theme_text    = TEXT
    _theme_subtext = SUBTEXT
    _theme_accent  = ACCENT
    _theme_accent2 = ACCENT2
    _theme_purple  = ROKU_PURPLE
    _theme_green   = GREEN
    _theme_red     = RED
    _theme_yellow  = YELLOW

    # Built-in presets  ─────────────────────────────────────────────────────
    _PRESETS = {
        "Dark (Default)": {
            "bg": "#0a0a0f", "panel": "#111118", "border": "#1e1e2e",
            "dim": "#3a3a5c", "text": "#e0e0f0", "subtext": "#6868a0",
            "accent": "#00ffe5", "accent2": "#c792ea", "purple": "#6c2bd9",
            "green": "#39ff7f", "red": "#ff3860", "yellow": "#ffcc00",
        },
        "Terminal": {
            "bg": "#0d1117", "panel": "#161b22", "border": "#30363d",
            "dim": "#484f58", "text": "#c9d1d9", "subtext": "#8b949e",
            "accent": "#58a6ff", "accent2": "#f0883e", "purple": "#6e40c9",
            "green": "#3fb950", "red": "#f85149", "yellow": "#d29922",
        },
        "Ice": {
            "bg": "#050d1a", "panel": "#0d1f33", "border": "#1a3a5c",
            "dim": "#1e4976", "text": "#cce7ff", "subtext": "#5b8db8",
            "accent": "#4fc3f7", "accent2": "#81d4fa", "purple": "#0288d1",
            "green": "#00e5ff", "red": "#ef5350", "yellow": "#ffd740",
        },
        "Sunset": {
            "bg": "#120a0a", "panel": "#1f1010", "border": "#3d1f1f",
            "dim": "#5c2e2e", "text": "#f0d0c0", "subtext": "#a06060",
            "accent": "#ff7043", "accent2": "#ffab40", "purple": "#c62828",
            "green": "#69f0ae", "red": "#ff1744", "yellow": "#ffea00",
        },
        "Midnight": {
            "bg": "#07071a", "panel": "#0d0d2b", "border": "#1a1a4d",
            "dim": "#2e2e66", "text": "#d0d0ff", "subtext": "#6060b0",
            "accent": "#7c4dff", "accent2": "#e040fb", "purple": "#4527a0",
            "green": "#76ff03", "red": "#ff1744", "yellow": "#ffd600",
        },
        "Light": {
            "bg": "#f5f5f5", "panel": "#eeeeee", "border": "#cccccc",
            "dim": "#aaaaaa", "text": "#111111", "subtext": "#555555",
            "accent": "#0066cc", "accent2": "#9c27b0", "purple": "#5c35cc",
            "green": "#1b8000", "red": "#cc0000", "yellow": "#b37400",
        },
    }

    def _apply_theme_dict(self, d):
        """Apply a colour dict to the whole UI by rebuilding it."""
        global BG, PANEL, BORDER, DIM, TEXT, SUBTEXT, ACCENT, ACCENT2, ROKU_PURPLE, GREEN, RED, YELLOW
        BG          = d["bg"];      PANEL  = d["panel"];  BORDER = d["border"]
        DIM         = d["dim"];     TEXT   = d["text"];   SUBTEXT= d["subtext"]
        ACCENT      = d["accent"];  ACCENT2= d["accent2"];ROKU_PURPLE = d["purple"]
        GREEN       = d["green"];   RED    = d["red"];    YELLOW = d["yellow"]
        _write_cfg({"theme": d})
        _retheme_all_popups()   # close any open popups so they reopen with new colours
        # Rebuild UI
        for w in self.winfo_children():
            w.destroy()
        self.configure(bg=BG)
        self._build_ui()
        # Restore device label
        if self._ip:
            self._device_lbl.config(
                text=f"{self._device_name}  [{self._ip}]", fg=GREEN)

    def _open_theme(self):
        # Single-instance guard
        if self._popup_theme and self._popup_theme.winfo_exists():
            self._popup_theme.lift(); self._popup_theme.focus_force(); return
        # Position popup centred over main window (live coords)
        pw, ph = 300, 340
        cx = self.winfo_rootx() + self.winfo_width()  // 2 - pw // 2
        cy = self.winfo_rooty() + self.winfo_height() // 2 - ph // 2

        pop = tk.Toplevel(self)
        self._popup_theme = pop
        pop.configure(bg=BG); pop.resizable(False, False)
        pop.overrideredirect(True)
        pop.wm_attributes("-topmost", True)
        pop.transient(self)
        pop.withdraw()
        pop.geometry(f"{pw}x{ph}+{cx}+{cy}")

        _make_titlebar(pop, PANEL, BORDER, SUBTEXT, RED, on_close=pop.destroy,
                       title_text="  🎨  Theme", title_fg=TEXT, title_bg=PANEL, draggable=False)

        body = tk.Frame(pop, bg=BG, padx=12, pady=8)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Presets", bg=BG, fg=SUBTEXT,
                 font=(_FONT, _FS - 1, "bold"), anchor="w").pack(fill="x", pady=(0, 4))

        current_cfg = _read_cfg().get("theme", {})

        for name, d in self._PRESETS.items():
            row = tk.Frame(body, bg=BORDER, cursor="hand2")
            row.pack(fill="x", pady=2)

            # Colour swatches
            swatch_row = tk.Frame(row, bg=BORDER)
            swatch_row.pack(side="right", padx=6, pady=4)
            for col_key in ("bg", "accent", "green", "purple"):
                tk.Frame(swatch_row, bg=d[col_key], width=10, height=10).pack(
                    side="left", padx=1)

            tk.Label(row, text=name, bg=BORDER, fg=TEXT,
                     font=(_FONT, _FS - 1), anchor="w", padx=8, pady=6).pack(
                     side="left", fill="x", expand=True)

            def _apply(preset=d, p=pop):
                self._apply_theme_dict(preset)
                p.destroy()

            for w in [row] + list(row.winfo_children()) + list(swatch_row.winfo_children()):
                w.bind("<Button-1>", lambda e, fn=_apply: fn())
                w.bind("<Enter>",    lambda e, r=row: r.config(bg=DIM))
                w.bind("<Leave>",    lambda e, r=row: r.config(bg=BORDER))

        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(8, 4))
        tk.Label(body, text="Click a preset to apply instantly",
                 bg=BG, fg=DIM, font=(_FONT, _FS - 2), anchor="w").pack(fill="x")

        # ── Opacity row — matches PyDisplay style ────────────────────────────
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(8, 4))
        op_row = tk.Frame(body, bg=BG)
        op_row.pack(fill="x")

        tk.Label(op_row, text="Opacity", bg=BG, fg=SUBTEXT,
                 font=(_FONT, _FS - 1, "bold"), anchor="w").pack(side="left")

        # Entry field — shows integer percent
        op_var = tk.StringVar(value=str(int(round(self._opacity * 100))))
        op_entry = tk.Entry(op_row, textvariable=op_var, bg=BORDER, fg=TEXT,
                            insertbackground=TEXT, font=(_FONT, _FS, "bold"),
                            relief="flat", width=4, justify="center")
        op_entry.pack(side="left", padx=(8, 2), ipady=3)

        pct_lbl = tk.Label(op_row, text="%", bg=BG, fg=SUBTEXT,
                           font=(_FONT, _FS - 1))
        pct_lbl.pack(side="left")

        def _set_opacity(val):
            try:
                v = max(20, min(100, int(val)))
            except (ValueError, TypeError):
                return
            op_var.set(str(v))
            alpha = v / 100.0
            self._opacity = alpha
            self._apply_opacity()
            _write_cfg({"opacity": alpha})

        def _step(delta):
            try:   cur = int(op_var.get())
            except ValueError: cur = 100
            _set_opacity(cur + delta)

        def _on_entry_change(*_):
            try:   _set_opacity(int(op_var.get()))
            except ValueError: pass

        op_entry.bind("<Return>",   lambda e: _on_entry_change())
        op_entry.bind("<FocusOut>", lambda e: _on_entry_change())
        op_var.trace_add("write", _on_entry_change)

        # − / + buttons
        for symbol, delta in (("−", -5), ("+", +5)):
            btn = tk.Label(op_row, text=f" {symbol} ", bg=BORDER, fg=ACCENT,
                           font=(_FONT, _FS, "bold"), cursor="hand2",
                           padx=4, pady=2, relief="flat")
            if delta < 0:
                btn.pack(side="left", padx=(6, 2))
            else:
                btn.pack(side="left", padx=(2, 0))
            btn.bind("<Button-1>",  lambda e, d=delta: _step(d))
            btn.bind("<Enter>",     lambda e, b=btn: b.config(fg=GREEN))
            btn.bind("<Leave>",     lambda e, b=btn: b.config(fg=ACCENT))

        # ── Keybinds button ──────────────────────────────────────────────────
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(8, 4))
        # Always-on-top toggle
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(8, 4))
        aot_row = tk.Frame(body, bg=BG)
        aot_row.pack(fill="x", pady=(0, 4))
        tk.Label(aot_row, text="📌  Always on Top", bg=BG, fg=SUBTEXT,
                 font=(_FONT, _FS - 1, "bold"), anchor="w").pack(side="left")
        aot_var = tk.BooleanVar(value=self._always_on_top)
        def _toggle_aot():
            self._apply_always_on_top(aot_var.get())
        aot_chk = tk.Checkbutton(aot_row, variable=aot_var, command=_toggle_aot,
                                  bg=BG, fg=ACCENT, selectcolor=BORDER,
                                  activebackground=BG, activeforeground=GREEN,
                                  relief="flat", cursor="hand2")
        aot_chk.pack(side="right")

        kb_btn = tk.Label(body, text="⌨  Edit Key Bindings…",
                          bg=BORDER, fg=ACCENT, font=(_FONT, _FS - 1, "bold"),
                          cursor="hand2", anchor="w", padx=8, pady=6)
        kb_btn.pack(fill="x")
        kb_btn.bind("<Button-1>", lambda e: (pop.destroy(), self._open_keybinds()))
        kb_btn.bind("<Enter>",    lambda e: kb_btn.config(fg=GREEN))
        kb_btn.bind("<Leave>",    lambda e: kb_btn.config(fg=ACCENT))

        _register_popup(pop)
        pop.update_idletasks()
        pop.geometry(f"300x{pop.winfo_reqheight()}+{cx}+{cy}")
        pop.deiconify()

    # ── Keybind editor ────────────────────────────────────────────────────────

    def _open_keybinds(self):
        """PyDisplay-styled keybind editor — edits a local copy, saves only on Save."""
        if self._popup_keybinds and self._popup_keybinds.winfo_exists():
            self._popup_keybinds.lift(); self._popup_keybinds.focus_force(); return
        pw, ph = 340, 440
        cx = self.winfo_rootx() + self.winfo_width()  // 2 - pw // 2
        cy = self.winfo_rooty() + self.winfo_height() // 2 - ph // 2

        pop = tk.Toplevel(self)
        self._popup_keybinds = pop
        pop.configure(bg=BG); pop.resizable(False, False)
        pop.overrideredirect(True)
        pop.wm_attributes("-topmost", True)
        pop.transient(self)
        pop.withdraw()
        pop.geometry(f"{pw}x{ph}+{cx}+{cy}")
        _register_popup(pop)

        # Work on a LOCAL copy — only written to self._keymap on Save
        local_km = dict(self._keymap)

        def _cancel():
            pop.destroy()   # discard local_km, self._keymap unchanged

        def _save_all():
            self._keymap = dict(local_km)
            _write_cfg({"keymap": self._keymap})
            pop.destroy()

        _make_titlebar(pop, PANEL, BORDER, SUBTEXT, RED, on_close=_cancel,
                       title_text="  ⌨  Key Bindings", title_fg=TEXT, title_bg=PANEL, draggable=False)

        # ── Scrollable body ───────────────────────────────────────────────────
        outer = tk.Frame(pop, bg=BG); outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        body = tk.Frame(canvas, bg=BG, padx=12, pady=8)
        body_win = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(body_win, width=e.width)
        canvas.bind("<Configure>", _on_resize)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # Column headers
        hdr = tk.Frame(body, bg=BG); hdr.pack(fill="x", pady=(0, 4))
        hdr.columnconfigure(0, weight=1); hdr.columnconfigure(1, weight=1)
        hdr.columnconfigure(2, weight=0)
        tk.Label(hdr, text="KEY", bg=BG, fg=SUBTEXT,
                 font=(_FONT, _FS - 2, "bold"), anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(hdr, text="ACTION", bg=BG, fg=SUBTEXT,
                 font=(_FONT, _FS - 2, "bold"), anchor="w").grid(row=0, column=1, sticky="w")
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(0, 6))

        row_widgets = {}

        def _rebuild_rows():
            for w in list(row_widgets.values()):
                try: w[0].destroy()
                except Exception: pass
            row_widgets.clear()
            for ks in sorted(local_km.keys()):
                action = local_km[ks]
                rf = tk.Frame(body, bg=PANEL); rf.pack(fill="x", pady=1)
                rf.columnconfigure(0, weight=1); rf.columnconfigure(1, weight=1)
                rf.columnconfigure(2, weight=0)
                tk.Label(rf, text=ks, bg=PANEL, fg=TEXT,
                         font=(_FONT, _FS - 1), anchor="w",
                         padx=6, pady=4).grid(row=0, column=0, sticky="ew")
                act_lbl = tk.Label(rf, text=action, bg=PANEL, fg=ACCENT,
                                   font=(_FONT, _FS - 1), anchor="w", padx=6)
                act_lbl.grid(row=0, column=1, sticky="ew")
                del_btn = tk.Label(rf, text=" ✕ ", bg=PANEL, fg=SUBTEXT,
                                   font=(_FONT, _FS - 2), cursor="hand2", padx=4)
                del_btn.grid(row=0, column=2, padx=(0, 4))

                def _delete(k=ks):
                    local_km.pop(k, None)
                    _rebuild_rows()

                def _click_row(e, k=ks, a=action):
                    _start_rebind(k, a)

                for w in [rf, act_lbl]:
                    w.bind("<Button-1>", _click_row)
                    w.bind("<Enter>",    lambda e, r=rf: r.config(bg=DIM))
                    w.bind("<Leave>",    lambda e, r=rf: r.config(bg=PANEL))
                del_btn.bind("<Button-1>", lambda e, fn=_delete: fn())
                del_btn.bind("<Enter>",    lambda e, b=del_btn: b.config(fg=RED))
                del_btn.bind("<Leave>",    lambda e, b=del_btn: b.config(fg=SUBTEXT))
                row_widgets[ks] = (rf, act_lbl)

        _rebuild_rows()

        # ── Bottom bar — Reset / Add / Cancel / Save ──────────────────────────
        tk.Frame(pop, bg=BORDER, height=1).pack(fill="x")
        bot = tk.Frame(pop, bg=BG, padx=12, pady=6); bot.pack(fill="x")

        def _reset_all():
            local_km.clear()
            local_km.update(_DEFAULT_KEYMAP)
            _rebuild_rows()

        rst = tk.Label(bot, text="↺ Reset", bg=BORDER, fg=SUBTEXT,
                       font=(_FONT, _FS - 1, "bold"), cursor="hand2", padx=8, pady=4)
        rst.pack(side="left")
        rst.bind("<Button-1>", lambda e: _reset_all())
        rst.bind("<Enter>",    lambda e: rst.config(fg=YELLOW))
        rst.bind("<Leave>",    lambda e: rst.config(fg=SUBTEXT))

        add = tk.Label(bot, text="＋ Add", bg=BORDER, fg=ACCENT,
                       font=(_FONT, _FS - 1, "bold"), cursor="hand2", padx=8, pady=4)
        add.pack(side="left", padx=(6, 0))
        add.bind("<Button-1>", lambda e: _start_rebind(None, None))
        add.bind("<Enter>",    lambda e: add.config(fg=GREEN))
        add.bind("<Leave>",    lambda e: add.config(fg=ACCENT))

        cn_btn = tk.Label(bot, text="Cancel", bg=BORDER, fg=SUBTEXT,
                          font=(_FONT, _FS - 1, "bold"), cursor="hand2", padx=8, pady=4)
        cn_btn.pack(side="right", padx=(6, 0))
        cn_btn.bind("<Button-1>", lambda e: _cancel())
        cn_btn.bind("<Enter>",    lambda e: cn_btn.config(fg=RED))
        cn_btn.bind("<Leave>",    lambda e: cn_btn.config(fg=SUBTEXT))

        sv_btn = tk.Label(bot, text="✔ Save", bg=ROKU_PURPLE, fg=TEXT,
                          font=(_FONT, _FS - 1, "bold"), cursor="hand2", padx=8, pady=4)
        sv_btn.pack(side="right")
        sv_btn.bind("<Button-1>", lambda e: _save_all())
        sv_btn.bind("<Enter>",    lambda e: sv_btn.config(bg=GREEN, fg=BG))
        sv_btn.bind("<Leave>",    lambda e: sv_btn.config(bg=ROKU_PURPLE, fg=TEXT))

        # ── Rebind dialog ─────────────────────────────────────────────────────
        def _start_rebind(old_key, old_action):
            rdlg = tk.Toplevel(pop)
            rdlg.configure(bg=BG); rdlg.resizable(False, False)
            rdlg.overrideredirect(True)
            rdlg.wm_attributes("-topmost", True)
            rdlg.transient(pop)
            rdlg.withdraw()
            _register_popup(rdlg)
            _make_titlebar(rdlg, PANEL, BORDER, SUBTEXT, RED, on_close=rdlg.destroy,
                           title_text="  ⌨  Rebind Key", title_fg=TEXT, title_bg=PANEL, draggable=False)
            inner = tk.Frame(rdlg, bg=BG, padx=16, pady=12); inner.pack(fill="both")

            state = {"key": old_key, "action": old_action or "Select"}

            tk.Label(inner, text="Press a key:", bg=BG, fg=SUBTEXT,
                     font=(_FONT, _FS - 1, "bold"), anchor="w").pack(fill="x")
            key_lbl = tk.Label(inner, text=old_key or "— click to capture —",
                               bg=BORDER, fg=TEXT if old_key else DIM,
                               font=(_FONT, _FS, "bold"), pady=6, cursor="hand2")
            key_lbl.pack(fill="x", pady=(4, 10))

            capturing = [False]
            def _start_capture(e=None):
                capturing[0] = True
                key_lbl.config(text="… listening …", fg=YELLOW, bg=DIM)
                rdlg.bind("<KeyPress>", _capture_key)
                key_lbl.focus_set()
            def _capture_key(e):
                if not capturing[0]: return
                capturing[0] = False
                ks = e.keysym.lower()
                state["key"] = ks
                key_lbl.config(text=ks, fg=GREEN, bg=BORDER)
                rdlg.unbind("<KeyPress>")
            key_lbl.bind("<Button-1>", _start_capture)
            key_lbl.bind("<Enter>",    lambda e: key_lbl.config(bg=DIM) if not capturing[0] else None)
            key_lbl.bind("<Leave>",    lambda e: key_lbl.config(bg=BORDER) if not capturing[0] else None)

            tk.Label(inner, text="ECP Action:", bg=BG, fg=SUBTEXT,
                     font=(_FONT, _FS - 1, "bold"), anchor="w").pack(fill="x")
            act_var = tk.StringVar(value=state["action"])
            act_var.trace_add("write", lambda *_: state.update({"action": act_var.get()}))
            om = tk.OptionMenu(inner, act_var, *_ECP_ACTIONS)
            om.config(bg=BORDER, fg=TEXT, activebackground=DIM, activeforeground=TEXT,
                      font=(_FONT, _FS), relief="flat", highlightthickness=0,
                      indicatoron=True, anchor="w")
            om["menu"].config(bg=PANEL, fg=TEXT, activebackground=ROKU_PURPLE,
                              activeforeground=TEXT, font=(_FONT, _FS))
            om.pack(fill="x", pady=(4, 12))

            btn_row = tk.Frame(inner, bg=BG); btn_row.pack(fill="x")
            def _save_bind():
                k = state["key"]; a = state["action"]
                if not k: return
                if old_key and old_key != k:
                    local_km.pop(old_key, None)
                local_km[k] = a
                rdlg.destroy()
                _rebuild_rows()
            sv = tk.Label(btn_row, text="Add", bg=ROKU_PURPLE, fg=TEXT,
                          font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=4)
            sv.pack(side="left")
            sv.bind("<Button-1>", lambda e: _save_bind())
            sv.bind("<Enter>",    lambda e: sv.config(bg=GREEN, fg=BG))
            sv.bind("<Leave>",    lambda e: sv.config(bg=ROKU_PURPLE, fg=TEXT))
            cn = tk.Label(btn_row, text="Cancel", bg=BORDER, fg=SUBTEXT,
                          font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=4)
            cn.pack(side="right")
            cn.bind("<Button-1>", lambda e: rdlg.destroy())
            cn.bind("<Enter>",    lambda e: cn.config(fg=RED))
            cn.bind("<Leave>",    lambda e: cn.config(fg=SUBTEXT))

            rdlg.update_idletasks()
            rx = pop.winfo_rootx() + pop.winfo_width()  // 2 - rdlg.winfo_reqwidth()  // 2
            ry = pop.winfo_rooty() + pop.winfo_height() // 2 - rdlg.winfo_reqheight() // 2
            rdlg.geometry(f"+{rx}+{ry}"); rdlg.deiconify(); rdlg.grab_set()

        pop.update_idletasks()
        pop.geometry(f"{pw}x{pop.winfo_reqheight()}+{cx}+{cy}")
        pop.deiconify()

    # ── Apps popup ────────────────────────────────────────────────────────────

    def _open_apps(self):
        if not self._ip:
            self._set_status("No Roku connected — click ⌕ SCAN", RED); return
        # Single-instance guard
        if self._popup_apps and self._popup_apps.winfo_exists():
            self._popup_apps.lift(); self._popup_apps.focus_force(); return
        dlg = tk.Toplevel(self)
        dlg.wm_attributes("-alpha", 0)   # invisible until fully built
        dlg.configure(bg=BG)
        dlg.resizable(False, False); dlg.overrideredirect(True)
        dlg.withdraw()
        dlg.wm_attributes("-topmost", True)
        dlg.transient(self)
        self._popup_apps = dlg
        _register_popup(dlg)
        _make_titlebar(dlg, PANEL, BORDER, SUBTEXT, RED, on_close=dlg.destroy,
                       title_text="  ✦ Apps", title_fg=TEXT, title_bg=PANEL, draggable=False)
        inner = tk.Frame(dlg, bg=BG, padx=12, pady=8); inner.pack(fill="both")
        # Show a status in the main bar while loading — don't show the popup yet
        self._set_status("Loading apps…", ACCENT, 0)
        _canvas_ref = [None]   # mutable ref so _scroll can always reach the canvas

        def _scroll(e):
            c = _canvas_ref[0]
            if c:
                c.yview_scroll(-1 * (e.delta // 120), "units")

        def _fetch():
            apps = ecp_apps(self._ip)
            self.after(0, lambda: _show(apps))

        def _show(apps):
            if not dlg.winfo_exists(): return
            self._set_status("", DIM, 0)
            if not apps:
                tk.Label(inner, text="No apps found.", bg=BG, fg=RED, font=(_FONT, _FS)).pack(pady=10)
            else:
                c = tk.Canvas(inner, bg=BG, width=240, height=min(len(apps)*32, 320), highlightthickness=0)
                _canvas_ref[0] = c
                sb2 = tk.Scrollbar(inner, orient="vertical", command=c.yview)
                c.configure(yscrollcommand=sb2.set)
                c.pack(side="left", fill="both", expand=True)
                sb2.pack(side="right", fill="y")
                fr = tk.Frame(c, bg=BG); c.create_window((0, 0), window=fr, anchor="nw")
                for app_id, name in apps:
                    row = tk.Frame(fr, bg=BORDER, cursor="hand2"); row.pack(fill="x", pady=2, padx=2)
                    nl = tk.Label(row, text=name, bg=BORDER, fg=TEXT, font=(_FONT, _FS-1), anchor="w", padx=8, pady=5)
                    nl.pack(side="left", fill="x", expand=True)
                    al = tk.Label(row, text=app_id, bg=BORDER, fg=DIM, font=(_FONT, _FS-3), padx=6)
                    al.pack(side="right")
                    def _launch(aid=app_id, n=name):
                        threading.Thread(target=lambda: ecp_post(self._ip, f"/launch/{aid}"), daemon=True).start()
                        self._set_status(f"Launching {n}…", GREEN); dlg.destroy()
                    for w in [row, nl, al]:
                        w.bind("<Button-1>", lambda e, fn=_launch: fn())
                        w.bind("<Enter>",    lambda e, r=row: r.config(bg=DIM))
                        w.bind("<Leave>",    lambda e, r=row: r.config(bg=BORDER))
                fr.update_idletasks(); c.configure(scrollregion=c.bbox("all"))

            # Use bind_all on the dialog so scroll works over ANY child widget
            dlg.bind_all("<MouseWheel>", _scroll)
            dlg.bind("<Destroy>", lambda e: dlg.unbind_all("<MouseWheel>") if e.widget is dlg else None, add="+")

            # Now show the popup — fully populated, no flicker
            dlg.update_idletasks()
            cx = self.winfo_rootx() + self.winfo_width()  // 2 - dlg.winfo_reqwidth()  // 2
            cy = self.winfo_rooty() + self.winfo_height() // 2 - 60
            dlg.geometry(f"+{cx}+{cy}")
            dlg.wm_attributes("-alpha", self._opacity)
            dlg.deiconify()

        threading.Thread(target=_fetch, daemon=True).start()

    # ── Text input popup ──────────────────────────────────────────────────────

    def _open_keyboard(self):
        if not self._ip:
            self._set_status("No Roku connected — click ⌕ SCAN", RED); return
        dlg = tk.Toplevel(self); dlg.configure(bg=BG)
        dlg.resizable(False, False); dlg.overrideredirect(True)
        dlg.withdraw()
        dlg.wm_attributes("-topmost", True)
        dlg.transient(self)
        _make_titlebar(dlg, PANEL, BORDER, SUBTEXT, RED, on_close=dlg.destroy,
                       title_text="  ⌨ Type Text", title_fg=TEXT, title_bg=PANEL, draggable=False)
        inner = tk.Frame(dlg, bg=BG, padx=16, pady=12); inner.pack(fill="both")
        tk.Label(inner, text="Text to send to Roku:", bg=BG, fg=TEXT, font=(_FONT, _FS)).pack(anchor="w", pady=(0, 4))
        entry = tk.Entry(inner, bg=BORDER, fg=TEXT, insertbackground=TEXT, font=(_FONT, _FS), relief="flat", width=28)
        entry.pack(fill="x", ipady=4); entry.focus_set()
        status = tk.Label(inner, text="Sends each character via ECP Lit_", bg=BG, fg=DIM, font=(_FONT, _FS-3), wraplength=240)
        status.pack(pady=(4, 0))
        btn_row = tk.Frame(inner, bg=BG); btn_row.pack(fill="x", pady=(10, 0))
        def _send():
            text = entry.get()
            if not text: return
            status.config(text=f"Sending {len(text)} chars…", fg=YELLOW); dlg.update_idletasks()
            def _w():
                import urllib.parse
                for ch in text:
                    ecp_keypress(self._ip, f"Lit_{urllib.parse.quote(ch, safe='')}")
                    time.sleep(0.08)
                if dlg.winfo_exists():
                    self.after(0, lambda: (status.config(text="✔ Sent!", fg=GREEN), self.after(1200, dlg.destroy)))
            threading.Thread(target=_w, daemon=True).start()
        send = tk.Label(btn_row, text="Send", bg=ROKU_PURPLE, fg=TEXT, font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=3)
        send.pack(side="left"); send.bind("<Button-1>", lambda e: _send())
        send.bind("<Enter>", lambda e: send.config(bg=GREEN, fg=BG))
        send.bind("<Leave>", lambda e: send.config(bg=ROKU_PURPLE, fg=TEXT))
        entry.bind("<Return>", lambda e: _send())
        cancel = tk.Label(btn_row, text="Cancel", bg=BORDER, fg=SUBTEXT, font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=3)
        cancel.pack(side="right"); cancel.bind("<Button-1>", lambda e: dlg.destroy())
        cancel.bind("<Enter>", lambda e: cancel.config(fg=RED))
        cancel.bind("<Leave>", lambda e: cancel.config(fg=SUBTEXT))
        dlg.update_idletasks()
        cx = self.winfo_rootx() + self.winfo_width()  // 2 - dlg.winfo_reqwidth()  // 2
        cy = self.winfo_rooty() + self.winfo_height() // 2 - dlg.winfo_reqheight() // 2
        dlg.geometry(f"+{cx}+{cy}"); dlg.deiconify()


# ═══════════════════════════════════════════════════════════════════════════════
#  Portable mode prompt  — shown only on first launch (no mode chosen yet)
# ═══════════════════════════════════════════════════════════════════════════════

def _ask_portable_mode():
    """
    Show a PyDisplay-styled popup asking whether to run in portable or standard
    mode.  Saves the answer into config.json so it is never asked again.
    Returns the chosen mode string ('portable' or 'standard'), or None if the
    user closed the window without choosing.
    """
    result = {"mode": None}

    root = tk.Tk()
    root.title("PyRokuMe — First Launch")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.wm_attributes("-topmost", True)
    root.overrideredirect(True)

    _make_titlebar(root, PANEL, BORDER, SUBTEXT, RED,
                   on_close=root.destroy,
                   title_text="PyRokuMe  ·  first launch",
                   title_fg=TEXT, title_bg=PANEL)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = tk.Frame(root, bg=BG, padx=16, pady=10)
    hdr.pack(fill="x")
    tk.Label(hdr, text="PyRokuMe", bg=BG, fg=ACCENT,
             font=(_FONT, _FS, "bold")).pack(side="left")
    tk.Label(hdr, text=f"  v{_APP_VERSION}  ·  choose storage mode",
             bg=BG, fg=SUBTEXT, font=(_FONT, _FS - 1)).pack(side="left")
    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=12)

    # ── Body ──────────────────────────────────────────────────────────────────
    body = tk.Frame(root, bg=BG, padx=16, pady=12)
    body.pack(fill="x")

    tk.Label(body,
             text="Choose a storage mode:",
             bg=BG, fg=TEXT, font=(_FONT, _FS, "bold"),
             anchor="w", justify="left").pack(fill="x", pady=(0, 8))

    # ── Option cards ──────────────────────────────────────────────────────────
    def _card(parent, icon, title, bullets, accent_col):
        f = tk.Frame(parent, bg=PANEL, padx=12, pady=8, cursor="hand2")
        f.pack(fill="x", pady=(0, 5))
        tk.Label(f, text=icon + "  " + title, bg=PANEL, fg=accent_col,
                 font=(_FONT, _FS, "bold"), anchor="w").pack(fill="x")
        for line in bullets:
            tk.Label(f, text="  · " + line, bg=PANEL, fg=SUBTEXT,
                     font=(_FONT, _FS - 1), anchor="w").pack(fill="x")
        return f

    portable_card = _card(body, "💾", "Portable", [
        "Creates a PyRokuMe folder — moves the script inside automatically",
        "Config & logs live alongside the script — ideal for USB drives",
    ], ACCENT)

    standard_card = _card(body, "🖥", "Standard", [
        "Config stored in %APPDATA%\\PyRokuMe",
        "Works from anywhere — no folder setup needed",
    ], ACCENT2)

    # Hover highlight
    def _hover(card, on):
        col = DIM if on else PANEL
        card.config(bg=col)
        for w in card.winfo_children():
            try: w.config(bg=col)
            except Exception: pass

    def _bind_card(card):
        card.bind("<Enter>", lambda e, c=card: _hover(c, True))
        card.bind("<Leave>", lambda e, c=card: _hover(c, False))
        for child in card.winfo_children():
            child.bind("<Enter>", lambda e, c=card: _hover(c, True))
            child.bind("<Leave>", lambda e, c=card: _hover(c, False))

    _bind_card(portable_card)
    _bind_card(standard_card)

    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=12)

    # ── Info note ─────────────────────────────────────────────────────────────
    note = tk.Label(root,
        text="↩  Portable mode will relaunch automatically from its new location",
        bg=BG, fg=DIM, font=(_FONT, _FS - 1),
        anchor="w", padx=16, pady=5)
    note.pack(fill="x")

    tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=12)

    # ── Buttons ───────────────────────────────────────────────────────────────
    bot = tk.Frame(root, bg=BG, pady=8, padx=16)
    bot.pack(fill="x")

    def _choose(mode):
        root.destroy()
        if mode == "portable":
            _setup_portable()
        else:
            _save_mode(mode)
        result["mode"] = mode

    def _mk_btn(text, fg, cmd):
        b = tk.Label(bot, text=text, bg=BORDER, fg=fg,
                     font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=5)
        b.pack(side="right", padx=(8, 0))
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>",    lambda e, w=b: w.config(fg=GREEN))
        b.bind("<Leave>",    lambda e, w=b, c=fg: w.config(fg=c))
        return b

    _mk_btn("💾  Portable",  ACCENT,  lambda: _choose("portable"))
    _mk_btn("🖥  Standard",  ACCENT2, lambda: _choose("standard"))

    # Card clicks also choose — rebind after _bind_card so clicks work on labels too
    def _bind_click(card, mode):
        card.bind("<Button-1>", lambda e: _choose(mode))
        for child in card.winfo_children():
            child.bind("<Button-1>", lambda e, m=mode: _choose(m))

    _bind_click(portable_card, "portable")
    _bind_click(standard_card, "standard")

    root.update_idletasks()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{(sw - root.winfo_reqwidth()) // 2}+{(sh - root.winfo_reqheight()) // 2}")
    root.mainloop()

    return result["mode"]




_LOCK_PATH = os.path.join(_APP_DIR, "PyRokuMe.pid")


def _pid_is_running(pid):
    if not pid: return False
    if _WIN32 and _kernel32:
        SYNCHRONIZE = 0x00100000
        h = _kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if h:
            _kernel32.CloseHandle(h)
            return True
        return False
    else:
        try: os.kill(pid, 0); return True
        except OSError: return False


def _read_lock_pid():
    try:
        with open(_LOCK_PATH) as f: return int(f.read().strip())
    except Exception: return 0


def _write_lock_pid(pid):
    try:
        os.makedirs(_APP_DIR, exist_ok=True)
        with open(_LOCK_PATH, "w") as f: f.write(str(pid))
    except Exception: pass


def _clear_lock_pid():
    try: os.remove(_LOCK_PATH)
    except Exception: pass


def _force_kill_pid(pid):
    if not pid: return
    if _WIN32 and _kernel32:
        try:
            h = _kernel32.OpenProcess(0x0001 | 0x00100000, False, pid)
            if h:
                _kernel32.TerminateProcess(h, 0)
                _kernel32.WaitForSingleObject(h, 3000)
                _kernel32.CloseHandle(h)
        except Exception: pass
    else:
        try:
            import signal; os.kill(pid, signal.SIGKILL)
        except Exception: pass
    time.sleep(0.4)


def _single_instance_check():
    existing_pid = _read_lock_pid()
    if not _pid_is_running(existing_pid):
        _write_lock_pid(os.getpid())
        return True

    # Another instance is running — ask user
    action = {"v": None}

    root = tk.Tk()
    root.withdraw()
    root.configure(bg=BG)
    root.overrideredirect(True)

    dlg = tk.Toplevel(root)
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.overrideredirect(True)
    dlg.wm_attributes("-topmost", True)
    dlg.withdraw()

    _make_titlebar(dlg, PANEL, BORDER, SUBTEXT, RED,
                   on_close=lambda: (action.update({"v": "cancel"}), root.quit()),
                   title_text="  PyRokuMe  ·  already running",
                   title_fg=TEXT, title_bg=PANEL, draggable=False)

    body = tk.Frame(dlg, bg=BG, padx=20, pady=14)
    body.pack(fill="both")

    tk.Label(body, text="⚠  PyRokuMe is already open",
             bg=BG, fg=YELLOW, font=(_FONT, _FS, "bold"), anchor="w").pack(fill="x")
    tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(8, 6))
    tk.Label(body, text="Would you like to close the existing\ninstance and launch a new one?",
             bg=BG, fg=TEXT, font=(_FONT, _FS), justify="left").pack(fill="x", pady=(0, 12))

    btn_row = tk.Frame(body, bg=BG)
    btn_row.pack(fill="x")

    def _do_replace():
        action["v"] = "replace"
        root.quit()

    def _do_cancel():
        action["v"] = "cancel"
        root.quit()

    close_btn = tk.Label(btn_row, text="Close old & launch",
                         bg=ROKU_PURPLE, fg=TEXT,
                         font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=5)
    close_btn.pack(side="left")
    close_btn.bind("<Button-1>", lambda e: _do_replace())
    close_btn.bind("<Enter>",    lambda e: close_btn.config(bg=GREEN, fg=BG))
    close_btn.bind("<Leave>",    lambda e: close_btn.config(bg=ROKU_PURPLE, fg=TEXT))

    cancel_btn = tk.Label(btn_row, text="Cancel",
                          bg=BORDER, fg=SUBTEXT,
                          font=(_FONT, _FS, "bold"), cursor="hand2", padx=12, pady=5)
    cancel_btn.pack(side="right")
    cancel_btn.bind("<Button-1>", lambda e: _do_cancel())
    cancel_btn.bind("<Enter>",    lambda e: cancel_btn.config(fg=RED))
    cancel_btn.bind("<Leave>",    lambda e: cancel_btn.config(fg=SUBTEXT))

    dlg.update_idletasks()
    sw = root.winfo_screenwidth(); sh = root.winfo_screenheight()
    dlg.geometry(f"+{(sw - dlg.winfo_reqwidth()) // 2}+{(sh - dlg.winfo_reqheight()) // 2}")
    dlg.deiconify()
    dlg.grab_set()
    root.mainloop()
    root.destroy()

    if action["v"] == "replace":
        _force_kill_pid(existing_pid)
        _write_lock_pid(os.getpid())
        return True

    return False

if __name__ == "__main__":
    # ── First-launch portable mode prompt ─────────────────────────────────────
    # Shown once when no mode has been saved yet. Choice is stored inside
    # config.json — no extra files created.
    if _load_mode() is None:
        chosen = _ask_portable_mode()
        # Portable: folder created, script moved, Explorer highlighted — exit.
        # None: user closed without choosing — abort.
        if chosen in (None, "portable"):
            sys.exit(0)
        # Standard chosen — re-resolve data dir now that config.json is written
        _APP_DIR  = _resolve_app_dir()
        _CFG_PATH = os.path.join(_APP_DIR, "config.json")
        _LOCK_PATH = os.path.join(_APP_DIR, "PyRokuMe.pid")

    if not _single_instance_check():
        sys.exit(0)
    if not _can_import("requests"):
        if not _run_dependency_check():
            sys.exit(0)
    if not _can_import("requests"):
        sys.exit(0)
    app = RokuRemote()
    app.mainloop()
