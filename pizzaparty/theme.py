import sys
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime

# ── Colors ────────────────────────────────────────────────────────────────────

BG         = "#0e0e0e"
PANEL      = "#1a1a1a"
CARD       = "#131313"
CARD_HOV   = "#1c1c1c"
BORDER     = "#2a2a2a"
ACCENT     = "#5865f2"
ACCENT_HOV = "#4752c4"
LIKE_CLR   = "#57f287"
DLIK_CLR   = "#ed4245"
SUCCESS    = "#57f287"
TEXT       = "#e8e8e8"
SUBTEXT    = "#777777"
ERROR      = "#ed4245"
ENTRY_BG   = "#111111"

# ── Font system ───────────────────────────────────────────────────────────────
# All fonts are tkfont.Font objects so their sizes can be updated live on resize.
# BASE_W is the design width; the scale factor is current_width / BASE_W.

BASE_W = 700
BASE_H = 780

# Populated by init_fonts() called in App.__init__
F:           dict = {}
_FONT_SPECS: dict = {}  # set by init_fonts(); used by scale_fonts()


def _resolve_families():
    """Return (sans, serif, emoji) font families for this platform."""
    def pick(candidates):
        available = set(tkfont.families())
        return next((f for f in candidates if f in available), candidates[-1])

    if sys.platform.startswith("linux"):
        sans  = pick(["Noto Sans", "DejaVu Sans", "Liberation Sans", "Helvetica"])
        serif = pick(["Noto Serif", "DejaVu Serif", "Liberation Serif", "Georgia"])
        emoji = pick(["Symbola", "Noto Emoji", "Segoe UI Emoji", sans])
    elif sys.platform == "darwin":
        sans, serif, emoji = "Helvetica", "Georgia", "Apple Color Emoji"
    else:
        sans, serif, emoji = "Helvetica", "Georgia", "Segoe UI Emoji"

    return sans, serif, emoji


def init_fonts():
    global _FONT_SPECS
    sans, serif, emoji = _resolve_families()

    _FONT_SPECS = {
        "FONT_TITLE":        (serif,  22, "bold"),
        "FONT_LABEL":        (sans,   10, "normal"),
        "FONT_ENTRY":        (sans,   11, "normal"),
        "FONT_BTN":          (sans,   11, "bold"),
        "FONT_SMALL":        (sans,    9, "normal"),
        "FONT_NAV":          (serif,  15, "bold"),
        "FONT_HANDLE":       (sans,   10, "bold"),
        "FONT_POST":         (sans,   11, "normal"),
        "FONT_META":         (sans,    9, "normal"),
        "FONT_SECTION":      (serif,  13, "bold"),
        "FONT_PROFILE_NAME": (serif,  16, "bold"),
        "FONT_STATS_VAL":    (sans,   12, "bold"),
        "FONT_PIZZA":        (emoji,  18, "normal"),
        "FONT_AV_SM":        (sans,    7, "bold"),
        "FONT_AV_MD":        (sans,   10, "bold"),
        "FONT_AV_LG":        (sans,   12, "bold"),
        "FONT_AV_XL":        (sans,   26, "bold"),
        "FONT_CMT_BODY":     (sans,    9, "normal"),
        "FONT_CMT_HANDLE":   (sans,    8, "bold"),
        "FONT_CMT_META":     (sans,    7, "normal"),
        "FONT_CMT_REACT":    (sans,    7, "bold"),
    }

    for name, (family, size, weight) in _FONT_SPECS.items():
        F[name] = tkfont.Font(family=family, size=size, weight=weight)


def scale_fonts(scale: float):
    """Rescale all named fonts proportionally to `scale`."""
    for name, (_, base_size, _) in _FONT_SPECS.items():
        new_size = max(6, round(base_size * scale))
        F[name].configure(size=new_size)

# ── Helpers ───────────────────────────────────────────────────────────────────

AVATAR_PALETTE = [
    "#5865f2", "#eb459e", "#faa61a", "#57f287",
    "#ed4245", "#00b0f4", "#9c59b6", "#e67e22",
]

def format_age(ts: str) -> str:
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""
    s = (datetime.now() - dt).total_seconds()
    if s < 60:      return "just now"
    if s < 3600:    return f"{int(s // 60)}m ago"
    if s < 86400:   return f"{int(s // 3600)}h ago"
    if s < 2592000: return f"{int(s // 86400)}d ago"
    return dt.strftime("%b %d")

def avatar_color(name: str) -> str:
    return AVATAR_PALETTE[sum(ord(c) for c in name) % len(AVATAR_PALETTE)]

def auto_wrap(label: tk.Label, padding: int = 28):
    """Bind a label's wraplength to its parent container width minus padding."""
    def _update(event):
        label.configure(wraplength=max(100, event.width - padding))
    label.master.bind("<Configure>", _update, add="+")

# ── Widget factories ──────────────────────────────────────────────────────────

def styled_entry(parent, show=None):
    return tk.Entry(
        parent, show=show,
        bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
        relief="flat", font=F["FONT_ENTRY"],
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT
    )

def styled_button(parent, text, command, color=ACCENT, hover=ACCENT_HOV):
    return tk.Button(
        parent, text=text, command=command,
        bg=color, fg="white", activebackground=hover, activeforeground="white",
        relief="flat", font=F["FONT_BTN"], cursor="hand2",
        padx=0, pady=10, borderwidth=0
    )

def flat_label(parent, text, font_key="FONT_LABEL", fg=SUBTEXT, bg=PANEL, **kw):
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=F[font_key], **kw)
