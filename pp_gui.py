import tkinter as tk
import tkinter.font as tkfont
import sqlite3
import os
from datetime import datetime

# ── DB setup ──────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "PizzaParty.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Create app-managed tables not in the SQL schema files."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Active_sessions (
                u_id      INTEGER PRIMARY KEY REFERENCES Users(u_id),
                last_used DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

def save_session(u_id: int):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO Active_sessions (u_id, last_used)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(u_id) DO UPDATE SET last_used = CURRENT_TIMESTAMP
        """, (u_id,))
        # Enforce max 20 sessions: delete oldest beyond the limit
        conn.execute("""
            DELETE FROM Active_sessions
            WHERE u_id NOT IN (
                SELECT u_id FROM Active_sessions
                ORDER BY last_used DESC LIMIT 20
            )
        """)

def get_sessions():
    """Return saved sessions newest-first. Includes deleted accounts (is_deleted flag)."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT s.u_id, u.username, u.is_deleted, s.last_used
            FROM   Active_sessions s
            JOIN   Users u ON u.u_id = s.u_id
            ORDER  BY s.last_used DESC
        """).fetchall()

def remove_session(u_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM Active_sessions WHERE u_id = ?", (u_id,)
        )

# ── Auth queries ──────────────────────────────────────────────────────────────

def attempt_login(email: str, password: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u_id, username FROM Users "
            "WHERE email_address = ? AND password = ? AND is_deleted = 0",
            (email, password)
        ).fetchone()
    return row

def attempt_signup(email: str, password: str, username: str):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO Users (email_address, password, username) VALUES (?, ?, ?)",
                (email, password, username)
            )
        return True
    except sqlite3.IntegrityError:
        return False

# ── Feed queries ──────────────────────────────────────────────────────────────

def get_feed_posts(u_id: int):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.post_id, p.u_id, u.username, p.content, p.created_at,
                   p.like_count, p.dlike_count, p.comment_count, p.been_edited,
                   COALESCE(pl.is_like,  0) AS my_like,
                   COALESCE(pl.is_dlike, 0) AS my_dlike
            FROM   Posts p
            JOIN   Users u  ON p.u_id     = u.u_id
            LEFT JOIN Posts_ledger pl
                           ON p.post_id   = pl.post_id AND pl.u_id = ?
            WHERE  p.u_id IN (
                       SELECT follows_u_id FROM Follows_ledger WHERE follower_u_id = ?
                   )
              AND  p.is_deleted  = 0
              AND  p.is_archived = 0
              AND  p.is_private  = 0
              AND  u.is_deleted  = 0
        """, (u_id, u_id)).fetchall()

    def score(row):
        try:
            dt = datetime.strptime(row[4], "%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = datetime.now()
        age_hours = max((datetime.now() - dt).total_seconds() / 3600, 0)
        return (max(row[5], 0) + 1) / (age_hours + 2) ** 1.8

    return sorted(rows, key=score, reverse=True)

def toggle_post_reaction(post_id: int, u_id: int, reaction: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT is_like, is_dlike FROM Posts_ledger WHERE post_id=? AND u_id=?",
            (post_id, u_id)
        ).fetchone()
        if reaction == "like":
            if row and row[0]:
                conn.execute("DELETE FROM Posts_ledger WHERE post_id=? AND u_id=?", (post_id, u_id))
            else:
                conn.execute("""
                    INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike) VALUES (?,?,1,0)
                    ON CONFLICT(post_id, u_id) DO UPDATE SET is_like=1, is_dlike=0
                """, (post_id, u_id))
        else:
            if row and row[1]:
                conn.execute("DELETE FROM Posts_ledger WHERE post_id=? AND u_id=?", (post_id, u_id))
            else:
                conn.execute("""
                    INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike) VALUES (?,?,0,1)
                    ON CONFLICT(post_id, u_id) DO UPDATE SET is_like=0, is_dlike=1
                """, (post_id, u_id))

def get_profile(u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT u.username, u.total_followers, u.total_follows, COUNT(p.post_id)
            FROM   Users u
            LEFT JOIN Posts p ON p.u_id = u.u_id AND p.is_deleted = 0 AND p.is_archived = 0
            WHERE  u.u_id = ?
            GROUP  BY u.u_id
        """, (u_id,)).fetchone()

def get_user_posts(profile_u_id: int, viewer_u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.post_id, p.u_id, u.username, p.content, p.created_at,
                   p.like_count, p.dlike_count, p.comment_count, p.been_edited,
                   COALESCE(pl.is_like,  0),
                   COALESCE(pl.is_dlike, 0),
                   p.is_private
            FROM   Posts p
            JOIN   Users u  ON p.u_id   = u.u_id
            LEFT JOIN Posts_ledger pl ON p.post_id = pl.post_id AND pl.u_id = ?
            WHERE  p.u_id      = ?
              AND  p.is_deleted  = 0
              AND  p.is_archived = 0
              AND  (p.is_private = 0 OR p.u_id = ?)
            ORDER  BY p.created_at DESC
        """, (viewer_u_id, profile_u_id, viewer_u_id)).fetchall()

def create_post(u_id: int, content: str, is_private: int = 0):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Posts (u_id, content, is_private) VALUES (?, ?, ?)",
            (u_id, content, is_private)
        )

def edit_post(post_id: int, new_content: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE Posts SET content = ?, been_edited = 1 WHERE post_id = ?",
            (new_content, post_id)
        )

def delete_post(post_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE Posts SET is_deleted = 1 WHERE post_id = ?", (post_id,))

def toggle_post_privacy(post_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE Posts SET is_private = 1 - is_private WHERE post_id = ?", (post_id,)
        )

def edit_comment(comment_id: int, new_content: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE Comments SET content = ?, been_edited = 1 WHERE comment_id = ?",
            (new_content, comment_id)
        )

def delete_comment(comment_id: int, post_id: int, parent_c_id):
    with get_conn() as conn:
        conn.execute("UPDATE Comments SET is_deleted = 1 WHERE comment_id = ?", (comment_id,))
        conn.execute(
            "UPDATE Posts SET comment_count = MAX(0, comment_count - 1) WHERE post_id = ?",
            (post_id,)
        )
        if parent_c_id:
            conn.execute(
                "UPDATE Comments SET comment_count = MAX(0, comment_count - 1) WHERE comment_id = ?",
                (parent_c_id,)
            )

def create_comment(post_id: int, u_id: int, content: str, parent_c_id=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Comments (parent_c_id, post_id, u_id, content) VALUES (?, ?, ?, ?)",
            (parent_c_id, post_id, u_id, content)
        )
        comment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        if parent_c_id:
            conn.execute(
                "UPDATE Comments SET comment_count = comment_count + 1 WHERE comment_id = ?",
                (parent_c_id,)
            )
        conn.execute(
            "UPDATE Posts SET comment_count = comment_count + 1 WHERE post_id = ?", (post_id,)
        )
    return comment_id

def get_post_header(post_id: int, viewer_u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.post_id, u.username, p.content, p.created_at, p.been_edited
            FROM   Posts p JOIN Users u ON p.u_id = u.u_id
            WHERE  p.post_id = ?
        """, (post_id,)).fetchone()

def get_post_comments(post_id: int, viewer_u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT c.comment_id, c.parent_c_id, c.u_id, u.username,
                   c.content, c.created_at, c.like_count, c.dlike_count,
                   c.been_edited,
                   COALESCE(cl.is_like,  0),
                   COALESCE(cl.is_dlike, 0)
            FROM   Comments c
            JOIN   Users u  ON c.u_id = u.u_id
            LEFT JOIN Comments_ledger cl ON c.comment_id = cl.comment_id AND cl.u_id = ?
            WHERE  c.post_id = ? AND c.is_deleted = 0
            ORDER  BY c.created_at ASC
        """, (viewer_u_id, post_id)).fetchall()

# ── Theme ─────────────────────────────────────────────────────────────────────

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

# (family, base_size, weight)
_FONT_SPECS = {
    "FONT_TITLE":        ("Georgia",    22, "bold"),
    "FONT_LABEL":        ("Helvetica",  10, "normal"),
    "FONT_ENTRY":        ("Helvetica",  11, "normal"),
    "FONT_BTN":          ("Helvetica",  11, "bold"),
    "FONT_SMALL":        ("Helvetica",   9, "normal"),
    "FONT_NAV":          ("Georgia",    15, "bold"),
    "FONT_HANDLE":       ("Helvetica",  10, "bold"),
    "FONT_POST":         ("Helvetica",  11, "normal"),
    "FONT_META":         ("Helvetica",   9, "normal"),
    # extras used inline throughout the file
    "FONT_SECTION":      ("Georgia",    13, "bold"),
    "FONT_PROFILE_NAME": ("Georgia",    16, "bold"),
    "FONT_STATS_VAL":    ("Helvetica",  12, "bold"),
    "FONT_PIZZA":        ("Helvetica",  18, "normal"),
    "FONT_AV_SM":        ("Helvetica",   7, "bold"),   # tiny avatar initials
    "FONT_AV_MD":        ("Helvetica",  10, "bold"),   # medium avatar
    "FONT_AV_LG":        ("Helvetica",  12, "bold"),   # large feed avatar
    "FONT_AV_XL":        ("Helvetica",  26, "bold"),   # profile hero avatar
    "FONT_CMT_BODY":     ("Helvetica",   9, "normal"), # comment body text
    "FONT_CMT_HANDLE":   ("Helvetica",   8, "bold"),
    "FONT_CMT_META":     ("Helvetica",   7, "normal"),
    "FONT_CMT_REACT":    ("Helvetica",   7, "bold"),
}

# Populated by _init_fonts() called in App.__init__
F: dict = {}

def _init_fonts():
    for name, (family, size, weight) in _FONT_SPECS.items():
        F[name] = tkfont.Font(family=family, size=size, weight=weight)

def _scale_fonts(scale: float):
    """Rescale all named fonts proportionally to `scale`."""
    for name, (_, base_size, _) in _FONT_SPECS.items():
        new_size = max(6, round(base_size * scale))
        F[name].configure(size=new_size)

# ── Helpers ───────────────────────────────────────────────────────────────────

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

AVATAR_PALETTE = [
    "#5865f2", "#eb459e", "#faa61a", "#57f287",
    "#ed4245", "#00b0f4", "#9c59b6", "#e67e22",
]

def avatar_color(name: str) -> str:
    return AVATAR_PALETTE[sum(ord(c) for c in name) % len(AVATAR_PALETTE)]

def auto_wrap(label: tk.Label, padding: int = 28):
    """Bind a label's wraplength to its parent container width minus padding."""
    def _update(event):
        label.configure(wraplength=max(100, event.width - padding))
    label.master.bind("<Configure>", _update, add="+")

# ── Reusable widgets ──────────────────────────────────────────────────────────

def styled_entry(parent, show=None):
    return tk.Entry(
        parent, show=show,
        bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
        relief="flat", font=F["FONT_ENTRY"],
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT
    )

def styled_button(parent, text, command, color=ACCENT, hover=ACCENT_HOV):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg="white", activebackground=hover, activeforeground="white",
        relief="flat", font=F["FONT_BTN"], cursor="hand2",
        padx=0, pady=10, borderwidth=0
    )
    return btn

def flat_label(parent, text, font_key="FONT_LABEL", fg=SUBTEXT, bg=PANEL, **kw):
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=F[font_key], **kw)

# ── App shell ─────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        _init_fonts()                   # must be after Tk() starts
        init_db()                       # ensure Active_sessions table exists

        self.title("Pizza Party")
        self.configure(bg=BG)
        self.update_idletasks()
        min_w = max(480, int(self.winfo_screenwidth()  * 0.35))
        min_h = max(400, int(self.winfo_screenheight() * 0.35))
        self.minsize(min_w, min_h)
        self._comments_panel = None
        self._switcher_panel = None
        self._resize_job     = None     # debounce handle

        self._center(420, 520)
        self.bind("<Configure>", self._on_configure)
        self.show_auth()

    def _center(self, w, h, use_screen_fraction=False):
        if use_screen_fraction:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w  = int(sw * 0.75)
            h  = int(sh * 0.75)
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── Resize handler ────────────────────────────────────────────────────────

    def _on_configure(self, event):
        if event.widget is not self:
            return
        # Debounce: only act 80 ms after the last resize event
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._apply_scale)

    def _apply_scale(self):
        self._resize_job = None
        w = self.winfo_width()
        # Use the main screen width (700) as the reference; auth screen uses 420
        ref = BASE_W if w > 500 else 420
        scale = max(0.6, min(2.0, w / ref))
        _scale_fonts(scale)
        # Reposition floating panels if open
        if self._comments_panel and self._comments_panel.winfo_exists():
            self._comments_panel.reposition()
        if self._switcher_panel and self._switcher_panel.winfo_exists():
            self._switcher_panel.reposition()

    # ── Screen management ─────────────────────────────────────────────────────

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._comments_panel = None
        self._switcher_panel = None

    def show_auth(self, on_cancel=None):
        self._center(420, 520)
        self.resizable(False, False)
        self.clear()
        AuthScreen(self, on_cancel=on_cancel)

    def show_main(self, u_id, username):
        save_session(u_id)
        self._center(700, 780, use_screen_fraction=True)
        self.resizable(True, True)
        self.clear()
        MainScreen(self, u_id, username)

    # ── Account switcher management ──────────────────────────────────────────

    def open_switcher(self, anchor_widget, current_u_id: int):
        if self._switcher_panel and self._switcher_panel.winfo_exists():
            self._switcher_panel.destroy()
            self._switcher_panel = None
            return
        self._switcher_panel = AccountSwitcherPanel(
            self, anchor_widget, current_u_id
        )

    def close_switcher(self):
        if self._switcher_panel and self._switcher_panel.winfo_exists():
            self._switcher_panel.destroy()
        self._switcher_panel = None

    # ── Comments panel management ─────────────────────────────────────────────

    def open_comments(self, post_id: int, viewer_u_id: int, on_close=None):
        if self._comments_panel is not None:
            self._comments_panel.destroy()
        self._comments_panel = CommentsPanel(self, post_id, viewer_u_id, on_close=on_close)

    def close_comments(self):
        if self._comments_panel is not None:
            self._comments_panel.destroy()
            self._comments_panel = None

# ── Auth screen ───────────────────────────────────────────────────────────────

class AuthScreen(tk.Frame):
    def __init__(self, app: App, on_cancel=None):
        super().__init__(app, bg=BG)
        self.app       = app
        self.on_cancel = on_cancel
        self.mode      = tk.StringVar(value="login")
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        wrapper = tk.Frame(self, bg=BG)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(wrapper, text="welcome back", font=F["FONT_TITLE"],
                 bg=BG, fg=TEXT).pack(pady=(0, 4))
        self.subtitle = tk.Label(wrapper, text="log in to continue",
                                  font=F["FONT_SMALL"], bg=BG, fg=SUBTEXT)
        self.subtitle.pack(pady=(0, 24))

        if self.on_cancel:
            cancel_btn = tk.Button(
                wrapper, text="← Back", command=self.on_cancel,
                bg=BG, fg=SUBTEXT, activebackground=BG, activeforeground=TEXT,
                relief="flat", font=F["FONT_SMALL"], cursor="hand2", borderwidth=0
            )
            cancel_btn.pack(anchor="w", pady=(0, 8))
            cancel_btn.bind("<Enter>", lambda e: cancel_btn.configure(fg=TEXT))
            cancel_btn.bind("<Leave>", lambda e: cancel_btn.configure(fg=SUBTEXT))

        panel = tk.Frame(wrapper, bg=PANEL, padx=32, pady=28,
                         highlightthickness=1, highlightbackground=BORDER)
        panel.pack(ipadx=10)

        tab_row = tk.Frame(panel, bg=PANEL)
        tab_row.pack(fill="x", pady=(0, 20))

        self.tab_login  = self._tab(tab_row, "Login",   "login")
        self.tab_signup = self._tab(tab_row, "Sign up", "signup")
        self.tab_login.pack(side="left",  expand=True, fill="x")
        self.tab_signup.pack(side="left", expand=True, fill="x")

        self.fields_frame = tk.Frame(panel, bg=PANEL)
        self.fields_frame.pack(fill="x")
        self._render_fields()

        self.status_var = tk.StringVar()
        tk.Label(panel, textvariable=self.status_var, bg=PANEL, fg=ERROR,
                 font=F["FONT_SMALL"], wraplength=280).pack(pady=(8, 0))

        self.submit_btn = styled_button(panel, "Log in", self._submit)
        self.submit_btn.pack(fill="x", pady=(12, 0))

    def _tab(self, parent, text, mode):
        def select():
            self.mode.set(mode)
            self._render_fields()
            self._update_tabs()
        btn = tk.Button(parent, text=text, command=select,
                        relief="flat", font=F["FONT_LABEL"], cursor="hand2",
                        padx=0, pady=8, borderwidth=0)
        self._style_tab(btn, mode == self.mode.get())
        return btn

    def _style_tab(self, btn, active):
        btn.configure(
            bg=ACCENT if active else PANEL,
            fg="white" if active else SUBTEXT,
            activebackground=ACCENT_HOV, activeforeground="white"
        )

    def _update_tabs(self):
        self._style_tab(self.tab_login,  self.mode.get() == "login")
        self._style_tab(self.tab_signup, self.mode.get() == "signup")
        is_signup = self.mode.get() == "signup"
        self.submit_btn.configure(text="Create account" if is_signup else "Log in")
        self.subtitle.configure(
            text="create a new account" if is_signup else "log in to continue")
        self.status_var.set("")

    def _render_fields(self):
        for w in self.fields_frame.winfo_children():
            w.destroy()

        is_signup = self.mode.get() == "signup"

        if is_signup:
            flat_label(self.fields_frame, "Username").pack(anchor="w", pady=(0, 4))
            self.entry_username = styled_entry(self.fields_frame)
            self.entry_username.pack(fill="x", ipady=6, pady=(0, 12))

        flat_label(self.fields_frame, "Email").pack(anchor="w", pady=(0, 4))
        self.entry_email = styled_entry(self.fields_frame)
        self.entry_email.pack(fill="x", ipady=6, pady=(0, 12))

        flat_label(self.fields_frame, "Password").pack(anchor="w", pady=(0, 4))
        pw_row = tk.Frame(self.fields_frame, bg=PANEL)
        pw_row.pack(fill="x")
        self.entry_password = styled_entry(pw_row, show="•")
        self.entry_password.pack(side="left", fill="x", expand=True, ipady=6)
        self.show_pw = tk.BooleanVar(value=False)

        def toggle_pw():
            self.show_pw.set(not self.show_pw.get())
            self.entry_password.configure(show="" if self.show_pw.get() else "•")
            toggle_btn.configure(text="hide" if self.show_pw.get() else "show")

        toggle_btn = tk.Button(
            pw_row, text="show", command=toggle_pw,
            bg=PANEL, fg=SUBTEXT, activebackground=PANEL, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2", borderwidth=0, width=4
        )
        toggle_btn.pack(side="left", padx=(6, 0))
        self.entry_password.bind("<Return>", lambda e: self._submit())

    def _submit(self):
        self.status_var.set("")
        email    = self.entry_email.get().strip()
        password = self.entry_password.get()

        if not email or not password:
            self.status_var.set("Please fill in all fields.")
            return

        if self.mode.get() == "login":
            result = attempt_login(email, password)
            if result:
                self.app.show_main(*result)
            else:
                self.status_var.set("Incorrect email or password.")
        else:
            username = self.entry_username.get().strip()
            if not username:
                self.status_var.set("Please fill in all fields.")
                return
            if not attempt_signup(email, password, username):
                self.status_var.set("That email is already registered.")
            else:
                result = attempt_login(email, password)
                if result:
                    self.app.show_main(*result)

# ── Main screen ───────────────────────────────────────────────────────────────

class MainScreen(tk.Frame):
    def __init__(self, app: App, u_id: int, username: str):
        super().__init__(app, bg=BG)
        self.app      = app
        self.u_id     = u_id
        self.username = username
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        self._build_nav()
        self._content_frame = tk.Frame(self, bg=BG)
        self._content_frame.pack(fill="both", expand=True)
        self._show_feed()

    def _clear_content(self):
        for w in self._content_frame.winfo_children():
            w.destroy()

    def _show_feed(self):
        self.app.close_comments()
        self.app.close_switcher()
        self._clear_content()
        self._build_composer()
        self._build_feed_area()
        self.refresh()

    def _show_profile(self):
        self.app.close_comments()
        self.app.close_switcher()
        self._clear_content()
        ProfilePanel(self._content_frame, self.u_id, self.u_id,
                     viewer_u_id=self.u_id,
                     on_back=self._show_feed)

    # ── Top navigation bar ────────────────────────────────────────────────────

    def _build_nav(self):
        nav = tk.Frame(self, bg=PANEL, height=54,
                       highlightthickness=1, highlightbackground=BORDER)
        nav.pack(fill="x", side="top")
        nav.pack_propagate(False)

        brand = tk.Frame(nav, bg=PANEL, cursor="hand2")
        brand.pack(side="left", padx=20, fill="y")
        pizza_lbl = tk.Label(brand, text="🍕", font=F["FONT_PIZZA"],
                             bg=PANEL, fg=TEXT, cursor="hand2")
        pizza_lbl.pack(side="left")
        name_lbl = tk.Label(brand, text="Pizza Party", font=F["FONT_NAV"],
                            bg=PANEL, fg=TEXT, cursor="hand2")
        name_lbl.pack(side="left", padx=(6, 0))

        for w in (brand, pizza_lbl, name_lbl):
            w.bind("<Button-1>", lambda e: self._show_feed())
            w.bind("<Enter>",    lambda e: name_lbl.configure(fg=ACCENT))
            w.bind("<Leave>",    lambda e: name_lbl.configure(fg=TEXT))

        right = tk.Frame(nav, bg=PANEL)
        right.pack(side="right", padx=16, fill="y")

        logout_btn = tk.Button(
            right, text="Log out", command=self.app.show_auth,
            bg=PANEL, fg=SUBTEXT,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2", borderwidth=0,
            padx=10, pady=4
        )
        logout_btn.pack(side="right", padx=(8, 0))
        logout_btn.bind("<Enter>", lambda e: logout_btn.configure(fg=TEXT))
        logout_btn.bind("<Leave>", lambda e: logout_btn.configure(fg=SUBTEXT))

        # ── Username chip: click left side → profile, click ▾ → switcher ──
        chip = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        chip.pack(side="right")
        inner_chip = tk.Frame(chip, bg=PANEL, padx=4, pady=4)
        inner_chip.pack()

        # Left part — profile link
        profile_part = tk.Frame(inner_chip, bg=PANEL, cursor="hand2", padx=4)
        profile_part.pack(side="left")

        av = tk.Canvas(profile_part, width=20, height=20, bg=PANEL,
                       highlightthickness=0, cursor="hand2")
        av.pack(side="left")
        clr = avatar_color(self.username)
        av.create_oval(1, 1, 19, 19, fill=clr, outline="")
        av.create_text(10, 10, text=self.username[0].upper(),
                       fill="white", font=F["FONT_AV_SM"])

        uname_lbl = tk.Label(profile_part, text=f"@{self.username}",
                             font=F["FONT_LABEL"], bg=PANEL, fg=TEXT, cursor="hand2")
        uname_lbl.pack(side="left", padx=(6, 0))

        for w in (profile_part, av, uname_lbl):
            w.bind("<Button-1>", lambda e: self._show_profile())
            w.bind("<Enter>",    lambda e: uname_lbl.configure(fg=ACCENT))
            w.bind("<Leave>",    lambda e: uname_lbl.configure(fg=TEXT))

        # Divider
        tk.Frame(inner_chip, bg=BORDER, width=1).pack(side="left", fill="y", pady=2)

        # Right part — switcher chevron
        chevron_btn = tk.Button(
            inner_chip, text="▾",
            command=lambda: self.app.open_switcher(chip, self.u_id),
            bg=PANEL, fg=SUBTEXT,
            activebackground=CARD_HOV, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2",
            borderwidth=0, padx=6
        )
        chevron_btn.pack(side="left")
        chevron_btn.bind("<Enter>", lambda e: chevron_btn.configure(fg=TEXT))
        chevron_btn.bind("<Leave>", lambda e: chevron_btn.configure(fg=SUBTEXT))

        refresh_btn = tk.Button(
            nav, text="⟳  Refresh", command=self.refresh,
            bg=PANEL, fg=SUBTEXT,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2", borderwidth=0,
            padx=10
        )
        refresh_btn.pack(side="left", padx=(16, 0))
        refresh_btn.bind("<Enter>", lambda e: refresh_btn.configure(fg=TEXT))
        refresh_btn.bind("<Leave>", lambda e: refresh_btn.configure(fg=SUBTEXT))

    # ── Post composer ─────────────────────────────────────────────────────────

    def _build_composer(self):
        outer = tk.Frame(self._content_frame, bg=BG)
        outer.pack(fill="x", padx=30, pady=(16, 4))

        card = tk.Frame(outer, bg=CARD,
                        highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x")

        hdr = tk.Frame(card, bg=CARD)
        hdr.pack(fill="x", padx=12, pady=(12, 6))

        clr = avatar_color(self.username)
        av  = tk.Canvas(hdr, width=30, height=30, bg=CARD, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 29, 29, fill=clr, outline="")
        av.create_text(15, 15, text=self.username[0].upper(),
                       fill="white", font=F["FONT_AV_MD"])

        tk.Label(hdr, text=f"What's on your mind, @{self.username}?",
                 font=F["FONT_SMALL"], bg=CARD, fg=SUBTEXT).pack(side="left", padx=(10, 0))

        self._composer_text = tk.Text(
            card, height=3, font=F["FONT_POST"],
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, padx=8, pady=6
        )
        self._composer_text.pack(fill="x", padx=12, pady=(0, 8))

        footer = tk.Frame(card, bg=CARD)
        footer.pack(fill="x", padx=12, pady=(0, 10))

        self._char_var = tk.StringVar(value="0 / 280")
        tk.Label(footer, textvariable=self._char_var,
                 font=F["FONT_META"], bg=CARD, fg=SUBTEXT).pack(side="left")

        self._composer_text.bind("<KeyRelease>", self._on_composer_key)

        self._is_private = tk.BooleanVar(value=False)
        tk.Checkbutton(
            footer, text="🔒 Private",
            variable=self._is_private,
            bg=CARD, fg=SUBTEXT, activebackground=CARD,
            activeforeground=TEXT, selectcolor=CARD,
            font=F["FONT_META"], cursor="hand2", borderwidth=0, relief="flat"
        ).pack(side="left", padx=(16, 0))

        tk.Button(
            footer, text="Post", command=self._submit_post,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", font=F["FONT_BTN"], cursor="hand2",
            padx=20, pady=4, borderwidth=0
        ).pack(side="right")

        self._composer_status = tk.StringVar()
        tk.Label(card, textvariable=self._composer_status,
                 font=F["FONT_SMALL"], bg=CARD, fg=ERROR).pack(pady=(0, 6))

    def _on_composer_key(self, _event=None):
        n = len(self._composer_text.get("1.0", "end-1c"))
        self._char_var.set(f"{n} / 280")
        self._composer_status.set("" if n <= 280 else "Post is too long.")

    def _submit_post(self):
        content = self._composer_text.get("1.0", "end-1c").strip()
        if not content:
            self._composer_status.set("Write something first.")
            return
        if len(content) > 280:
            self._composer_status.set("Post is too long (max 280 characters).")
            return
        create_post(self.u_id, content, int(self._is_private.get()))
        self._composer_text.delete("1.0", "end")
        self._char_var.set("0 / 280")
        self._composer_status.set("")
        self.refresh()

    # ── Feed area ─────────────────────────────────────────────────────────────

    def _build_feed_area(self):
        container = tk.Frame(self._content_frame, bg=BG)
        container.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        self._sb     = tk.Scrollbar(container, orient="vertical",
                                    command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._sb.set)

        self._sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._feed_frame = tk.Frame(self._canvas, bg=BG)
        self._win_id     = self._canvas.create_window(
            (0, 0), window=self._feed_frame, anchor="nw"
        )

        self._feed_frame.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def refresh(self):
        for w in self._feed_frame.winfo_children():
            w.destroy()

        posts = get_feed_posts(self.u_id)

        if not posts:
            tk.Label(
                self._feed_frame,
                text="Nothing here yet — follow some people to see their posts.",
                font=F["FONT_SMALL"], bg=BG, fg=SUBTEXT, pady=60
            ).pack()
            return

        hdr = tk.Frame(self._feed_frame, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(18, 6))
        tk.Label(hdr, text="Your Feed", font=F["FONT_SECTION"],
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(hdr, text=f"{len(posts)} posts", font=F["FONT_SMALL"],
                 bg=BG, fg=SUBTEXT).pack(side="left", padx=(8, 0))

        for row in posts:
            PostCard(self._feed_frame, row, self.u_id,
                     on_reaction=self.refresh, app=self.app)

        tk.Frame(self._feed_frame, bg=BG, height=24).pack()

# ── Profile panel ─────────────────────────────────────────────────────────────

class ProfilePanel(tk.Frame):
    def __init__(self, parent, profile_u_id: int, owner_u_id: int,
                 viewer_u_id: int, on_back):
        super().__init__(parent, bg=BG)
        self.pack(fill="both", expand=True)
        self.profile_u_id = profile_u_id
        self.owner_u_id   = owner_u_id
        self.viewer_u_id  = viewer_u_id
        self.on_back      = on_back
        self._build()

    def _build(self):
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        sb     = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner  = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        back_row = tk.Frame(inner, bg=BG)
        back_row.pack(fill="x", padx=30, pady=(14, 0))
        back_btn = tk.Button(
            back_row, text="← Back to Feed", command=self.on_back,
            bg=BG, fg=SUBTEXT, activebackground=BG, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2", borderwidth=0
        )
        back_btn.pack(side="left")
        back_btn.bind("<Enter>", lambda e: back_btn.configure(fg=TEXT))
        back_btn.bind("<Leave>", lambda e: back_btn.configure(fg=SUBTEXT))

        info = get_profile(self.profile_u_id)
        if not info:
            tk.Label(inner, text="User not found.", font=F["FONT_SMALL"],
                     bg=BG, fg=SUBTEXT).pack(pady=40)
            return

        username, followers, follows, post_count = info

        hero = tk.Frame(inner, bg=PANEL,
                        highlightthickness=1, highlightbackground=BORDER)
        hero.pack(fill="x", padx=30, pady=(10, 0))

        hero_body = tk.Frame(hero, bg=PANEL)
        hero_body.pack(fill="x", padx=20, pady=18)

        clr = avatar_color(username)
        av  = tk.Canvas(hero_body, width=64, height=64, bg=PANEL, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(2, 2, 62, 62, fill=clr, outline="")
        av.create_text(32, 32, text=username[0].upper(),
                       fill="white", font=F["FONT_AV_XL"])

        info_box = tk.Frame(hero_body, bg=PANEL)
        info_box.pack(side="left", padx=(18, 0))

        tk.Label(info_box, text=f"@{username}",
                 font=F["FONT_PROFILE_NAME"], bg=PANEL, fg=TEXT).pack(anchor="w")

        stats_row = tk.Frame(info_box, bg=PANEL)
        stats_row.pack(anchor="w", pady=(6, 0))

        for val, lbl in [(followers, "followers"), (follows, "following"), (post_count, "posts")]:
            block = tk.Frame(stats_row, bg=PANEL)
            block.pack(side="left", padx=(0, 20))
            tk.Label(block, text=str(val),
                     font=F["FONT_STATS_VAL"], bg=PANEL, fg=TEXT).pack(anchor="w")
            tk.Label(block, text=lbl,
                     font=F["FONT_META"], bg=PANEL, fg=SUBTEXT).pack(anchor="w")

        ph = tk.Frame(inner, bg=BG)
        ph.pack(fill="x", padx=30, pady=(18, 6))
        tk.Label(ph, text="Posts", font=F["FONT_SECTION"],
                 bg=BG, fg=TEXT).pack(side="left")

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=30)

        self._post_list_container = inner
        self._render_post_list(inner)
        tk.Frame(inner, bg=BG, height=24).pack()

    def _render_post_list(self, container):
        for w in getattr(self, "_post_card_widgets", []):
            w.destroy()
        self._post_card_widgets = []

        posts    = get_user_posts(self.profile_u_id, self.viewer_u_id)
        is_owner = (self.profile_u_id == self.owner_u_id)

        if not posts:
            lbl = tk.Label(container, text="No posts yet.", font=F["FONT_SMALL"],
                           bg=BG, fg=SUBTEXT)
            lbl.pack(pady=30)
            self._post_card_widgets.append(lbl)
        else:
            spacer = tk.Frame(container, bg=BG, height=8)
            spacer.pack()
            self._post_card_widgets.append(spacer)
            for row in posts:
                card = ProfilePostCard(
                    container, row, self.viewer_u_id,
                    is_owner=is_owner,
                    on_change=self._render_post_list_refresh
                )
                self._post_card_widgets.append(card)

    def _render_post_list_refresh(self):
        self._render_post_list(self._post_list_container)


class ProfilePostCard(tk.Frame):
    def __init__(self, parent, row, viewer_u_id: int,
                 is_owner: bool = False, on_change=None):
        super().__init__(parent, bg=CARD,
                         highlightthickness=1, highlightbackground=BORDER)
        self.pack(fill="x", padx=30, pady=(0, 10))

        (self.post_id, _, self.author, self.content, self.created_at,
         self.likes, self.dlikes, self.n_comments, self.edited,
         self.my_like, self.my_dlike, self.is_private) = row

        self.viewer_u_id = viewer_u_id
        self.is_owner    = is_owner
        self.on_change   = on_change
        self._editing    = False
        self._build()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()

        hdr = tk.Frame(self, bg=CARD)
        hdr.pack(fill="x", padx=14, pady=(10, 0))

        clr = avatar_color(self.author)
        av  = tk.Canvas(hdr, width=30, height=30, bg=CARD, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 29, 29, fill=clr, outline="")
        av.create_text(15, 15, text=self.author[0].upper(),
                       fill="white", font=F["FONT_AV_MD"])

        meta = tk.Frame(hdr, bg=CARD)
        meta.pack(side="left", padx=(10, 0))
        tk.Label(meta, text=f"@{self.author}",
                 font=F["FONT_HANDLE"], bg=CARD, fg=TEXT).pack(anchor="w")
        age = format_age(self.created_at) + (" · edited" if self.edited else "")
        if self.is_private:
            age += "  🔒"
        tk.Label(meta, text=age, font=F["FONT_META"], bg=CARD, fg=SUBTEXT).pack(anchor="w")

        if self.is_owner:
            action_bar = tk.Frame(hdr, bg=CARD)
            action_bar.pack(side="right")

            priv_lbl = "Make Public" if self.is_private else "Make Private"
            priv_clr = SUCCESS if self.is_private else SUBTEXT

            def _icon_btn(parent, text, fg, cmd):
                b = tk.Button(parent, text=text, command=cmd,
                              bg=CARD, fg=fg,
                              activebackground=CARD_HOV, activeforeground=TEXT,
                              relief="flat", font=F["FONT_META"], cursor="hand2",
                              borderwidth=0, padx=6)
                b.pack(side="left")
                b.bind("<Enter>", lambda e: b.configure(fg=TEXT))
                b.bind("<Leave>", lambda e: b.configure(fg=fg))
                return b

            _icon_btn(action_bar, "✏ Edit",        SUBTEXT,  self._start_edit)
            _icon_btn(action_bar, f"🔒 {priv_lbl}", priv_clr, self._toggle_private)
            _icon_btn(action_bar, "🗑 Delete",      DLIK_CLR, self._confirm_delete)

        if self._editing:
            edit_frame = tk.Frame(self, bg=CARD)
            edit_frame.pack(fill="x", padx=14, pady=(8, 0))

            self._edit_box = tk.Text(
                edit_frame, height=4, font=F["FONT_POST"],
                bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                relief="flat", wrap="word",
                highlightthickness=1, highlightbackground=BORDER,
                highlightcolor=ACCENT, padx=8, pady=6
            )
            self._edit_box.insert("1.0", self.content)
            self._edit_box.pack(fill="x")

            btn_row = tk.Frame(self, bg=CARD)
            btn_row.pack(fill="x", padx=14, pady=(6, 10))

            self._edit_status = tk.StringVar()
            tk.Label(btn_row, textvariable=self._edit_status,
                     font=F["FONT_SMALL"], bg=CARD, fg=ERROR).pack(side="left")

            tk.Button(btn_row, text="Cancel", command=self._cancel_edit,
                      bg="#2e2e2e", fg=SUBTEXT,
                      activebackground=BORDER, activeforeground=TEXT,
                      relief="flat", font=F["FONT_SMALL"], cursor="hand2",
                      borderwidth=0, padx=12, pady=4
                      ).pack(side="right", padx=(6, 0))
            tk.Button(btn_row, text="Save", command=self._save_edit,
                      bg=ACCENT, fg="white",
                      activebackground=ACCENT_HOV, activeforeground="white",
                      relief="flat", font=F["FONT_BTN"], cursor="hand2",
                      borderwidth=0, padx=12, pady=4
                      ).pack(side="right")
        else:
            content_lbl = tk.Label(
                self, text=self.content, font=F["FONT_POST"],
                bg=CARD, fg=TEXT, wraplength=580,
                justify="left", anchor="w"
            )
            content_lbl.pack(fill="x", padx=14, pady=(8, 10))
            auto_wrap(content_lbl, padding=60)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        strip = tk.Frame(self, bg=CARD)
        strip.pack(fill="x", padx=12, pady=5)

        lc = LIKE_CLR if self.my_like  else SUBTEXT
        dc = DLIK_CLR if self.my_dlike else SUBTEXT
        tk.Label(strip, text=f"▲  {self.likes}",
                 font=F["FONT_HANDLE"], bg=CARD, fg=lc
                 ).pack(side="left", padx=(4, 0))
        tk.Label(strip, text=f"▼  {self.dlikes}",
                 font=F["FONT_HANDLE"], bg=CARD, fg=dc
                 ).pack(side="left", padx=(8, 0))
        tk.Label(strip,
                 text=f"💬  {self.n_comments}  comment{'s' if self.n_comments != 1 else ''}",
                 font=F["FONT_META"], bg=CARD, fg=SUBTEXT
                 ).pack(side="left", padx=(12, 0))

    def _start_edit(self):
        self._editing = True
        self._build()
        self._edit_box.focus_set()

    def _cancel_edit(self):
        self._editing = False
        self._build()

    def _save_edit(self):
        new_content = self._edit_box.get("1.0", "end-1c").strip()
        if not new_content:
            self._edit_status.set("Content can't be empty.")
            return
        if len(new_content) > 280:
            self._edit_status.set("Too long (max 280 chars).")
            return
        edit_post(self.post_id, new_content)
        self.content = new_content
        self.edited  = 1
        self._editing = False
        self._build()

    def _toggle_private(self):
        toggle_post_privacy(self.post_id)
        self.is_private = 0 if self.is_private else 1
        self._build()

    def _confirm_delete(self):
        dialog = tk.Toplevel(self)
        dialog.title("Delete Post")
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()

        w, h = 320, 140
        dialog.geometry(f"{w}x{h}")
        dialog.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        py = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{px}+{py}")

        tk.Label(dialog, text="Delete this post?",
                 font=F["FONT_HANDLE"], bg=PANEL, fg=TEXT).pack(pady=(20, 4))
        tk.Label(dialog, text="This can't be undone.",
                 font=F["FONT_SMALL"], bg=PANEL, fg=SUBTEXT).pack()

        btn_row = tk.Frame(dialog, bg=PANEL)
        btn_row.pack(pady=16)

        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  bg="#2e2e2e", fg=SUBTEXT,
                  activebackground=BORDER, activeforeground=TEXT,
                  relief="flat", font=F["FONT_SMALL"], cursor="hand2",
                  borderwidth=0, padx=16, pady=6
                  ).pack(side="left", padx=(0, 8))

        def do_delete():
            dialog.destroy()
            delete_post(self.post_id)
            self.destroy()
            if self.on_change:
                self.on_change()

        tk.Button(btn_row, text="Delete", command=do_delete,
                  bg=DLIK_CLR, fg="white",
                  activebackground="#c0392b", activeforeground="white",
                  relief="flat", font=F["FONT_BTN"], cursor="hand2",
                  borderwidth=0, padx=16, pady=6
                  ).pack(side="left")

# ── Post card ─────────────────────────────────────────────────────────────────

class PostCard(tk.Frame):
    def __init__(self, parent, row, viewer_u_id: int, on_reaction, app: App):
        super().__init__(parent, bg=CARD,
                         highlightthickness=1, highlightbackground=BORDER)
        self.pack(fill="x", padx=30, pady=(0, 10))

        (self.post_id, _, self.author, self.content,
         self.created_at, self.likes, self.dlikes, self.n_comments,
         self.edited, self.my_like, self.my_dlike) = row

        self.viewer_u_id = viewer_u_id
        self.on_reaction = on_reaction
        self.app         = app
        self._build()

    def _build(self):
        header = tk.Frame(self, bg=CARD)
        header.pack(fill="x", padx=14, pady=(12, 0))

        clr = avatar_color(self.author)
        av  = tk.Canvas(header, width=34, height=34, bg=CARD, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 33, 33, fill=clr, outline="")
        av.create_text(17, 17, text=self.author[0].upper(),
                       fill="white", font=F["FONT_AV_LG"])

        meta_box = tk.Frame(header, bg=CARD)
        meta_box.pack(side="left", padx=(10, 0))
        tk.Label(meta_box, text=f"@{self.author}",
                 font=F["FONT_HANDLE"], bg=CARD, fg=TEXT).pack(anchor="w")
        age_txt = format_age(self.created_at) + (" · edited" if self.edited else "")
        tk.Label(meta_box, text=age_txt,
                 font=F["FONT_META"], bg=CARD, fg=SUBTEXT).pack(anchor="w")

        content_lbl = tk.Label(
            self, text=self.content, font=F["FONT_POST"],
            bg=CARD, fg=TEXT, wraplength=580,
            justify="left", anchor="w"
        )
        content_lbl.pack(fill="x", padx=14, pady=(10, 12))
        auto_wrap(content_lbl, padding=60)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        actions = tk.Frame(self, bg=CARD)
        actions.pack(fill="x", padx=8, pady=5)

        self._reaction_btn(actions, "▲", self.likes, bool(self.my_like),
                           LIKE_CLR, lambda: self._react("like"))
        self._reaction_btn(actions, "▼", self.dlikes, bool(self.my_dlike),
                           DLIK_CLR, lambda: self._react("dislike"))

        tk.Frame(actions, bg=BORDER, width=1).pack(side="left", fill="y", padx=10, pady=4)

        comment_btn = tk.Button(
            actions,
            text=f"💬  {self.n_comments}  comment{'s' if self.n_comments != 1 else ''}",
            command=self._open_comments,
            bg=CARD, fg=SUBTEXT,
            activebackground=CARD_HOV, activeforeground=TEXT,
            relief="flat", font=F["FONT_META"], cursor="hand2",
            borderwidth=0, padx=10, pady=6
        )
        comment_btn.pack(side="left")
        comment_btn.bind("<Enter>", lambda e: comment_btn.configure(fg=TEXT))
        comment_btn.bind("<Leave>", lambda e: comment_btn.configure(fg=SUBTEXT))

    def _reaction_btn(self, parent, symbol, count, active, active_clr, cmd):
        fg  = active_clr if active else SUBTEXT
        btn = tk.Button(
            parent, text=f"{symbol}  {count}", command=cmd,
            bg=CARD, fg=fg,
            activebackground=CARD_HOV, activeforeground=active_clr,
            relief="flat", font=F["FONT_BTN"], cursor="hand2",
            borderwidth=0, padx=10, pady=6
        )
        btn.pack(side="left")
        if not active:
            btn.bind("<Enter>", lambda e: btn.configure(fg=active_clr))
            btn.bind("<Leave>", lambda e: btn.configure(fg=SUBTEXT))
        return btn

    def _react(self, kind: str):
        toggle_post_reaction(self.post_id, self.viewer_u_id, kind)
        self.on_reaction()

    def _open_comments(self):
        self.app.open_comments(self.post_id, self.viewer_u_id,
                               on_close=self.on_reaction)

# ── Comments panel (floating in-window overlay) ───────────────────────────────

# ── Account switcher panel ───────────────────────────────────────────────────

class AccountSwitcherPanel(tk.Frame):
    """
    Floating dropdown that appears just below the nav-bar chip.
    Lists all saved sessions sorted by most recently used.
    Deleted accounts show a warning + remove button instead of Switch.
    """

    def __init__(self, app: App, anchor_widget: tk.Widget, current_u_id: int):
        super().__init__(app, bg=PANEL,
                         highlightthickness=1, highlightbackground=ACCENT)
        self.app           = app
        self.anchor        = anchor_widget
        self.current_u_id  = current_u_id
        self._place()
        self.lift()
        self._build()
        # Clicking anywhere outside closes the panel
        app.bind("<Button-1>", self._on_global_click, add="+")

    # ── Positioning ───────────────────────────────────────────────────────────

    def _place(self):
        self.update_idletasks()
        # Position below-right of the anchor chip
        ax = self.anchor.winfo_rootx() - self.app.winfo_rootx()
        ay = self.anchor.winfo_rooty() - self.app.winfo_rooty()
        ah = self.anchor.winfo_height()
        pw = max(260, int(self.app.winfo_width() * 0.34))
        # Clamp so it doesn't go off the right edge
        x  = min(ax, self.app.winfo_width() - pw - 4)
        self.place(x=x, y=ay + ah + 4, width=pw)

    def reposition(self):
        if self.winfo_exists():
            self._place()

    def _on_global_click(self, event):
        # Ignore clicks that land inside this panel
        try:
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            if wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh:
                return
        except Exception:
            pass
        self.app.close_switcher()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        for w in self.winfo_children():
            w.destroy()

        sessions = get_sessions()

        # Header
        hdr = tk.Frame(self, bg=ACCENT)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Switch Account", font=F["FONT_HANDLE"],
                 bg=ACCENT, fg="white").pack(side="left", padx=12, pady=8)

        if not sessions:
            tk.Label(self, text="No saved accounts yet.",
                     font=F["FONT_SMALL"], bg=PANEL, fg=SUBTEXT
                     ).pack(pady=16, padx=12)
        else:
            for u_id, username, is_deleted, last_used in sessions:
                self._render_row(u_id, username, bool(is_deleted),
                                 is_current=(u_id == self.current_u_id))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(4, 0))

        # Add account button
        add_btn = tk.Button(
            self, text="＋  Add account",
            command=self._add_account,
            bg=PANEL, fg=SUBTEXT,
            activebackground=CARD_HOV, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2",
            borderwidth=0, padx=12, pady=8, anchor="w"
        )
        add_btn.pack(fill="x")
        add_btn.bind("<Enter>", lambda e: add_btn.configure(fg=TEXT))
        add_btn.bind("<Leave>", lambda e: add_btn.configure(fg=SUBTEXT))

    def _render_row(self, u_id: int, username: str,
                    is_deleted: bool, is_current: bool):
        row = tk.Frame(self, bg=PANEL)
        row.pack(fill="x", padx=8, pady=4)

        # Avatar
        clr = avatar_color(username)
        av  = tk.Canvas(row, width=28, height=28, bg=PANEL, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 27, 27, fill=clr if not is_deleted else BORDER, outline="")
        av.create_text(14, 14, text=username[0].upper(),
                       fill="white" if not is_deleted else SUBTEXT,
                       font=F["FONT_AV_SM"])

        # Text block
        text_block = tk.Frame(row, bg=PANEL)
        text_block.pack(side="left", padx=(8, 0), expand=True, fill="x")

        name_color = SUBTEXT if is_deleted else (ACCENT if is_current else TEXT)
        name_text  = f"@{username}" + (" (you)" if is_current else "")
        tk.Label(text_block, text=name_text,
                 font=F["FONT_HANDLE"], bg=PANEL, fg=name_color).pack(anchor="w")

        if is_deleted:
            tk.Label(text_block, text="Account deleted",
                     font=F["FONT_META"], bg=PANEL, fg=DLIK_CLR).pack(anchor="w")

        # Action button(s)
        if is_deleted:
            def make_remove(uid=u_id):
                return lambda: self._remove(uid)
            remove_btn = tk.Button(
                row, text="✕ Remove",
                command=make_remove(),
                bg=PANEL, fg=DLIK_CLR,
                activebackground=CARD_HOV, activeforeground=DLIK_CLR,
                relief="flat", font=F["FONT_META"], cursor="hand2",
                borderwidth=0, padx=6
            )
            remove_btn.pack(side="right")
        elif not is_current:
            def make_switch(uid=u_id, uname=username):
                return lambda: self._switch(uid, uname)
            switch_btn = tk.Button(
                row, text="Switch",
                command=make_switch(),
                bg=ACCENT, fg="white",
                activebackground=ACCENT_HOV, activeforeground="white",
                relief="flat", font=F["FONT_META"], cursor="hand2",
                borderwidth=0, padx=10, pady=3
            )
            switch_btn.pack(side="right")

        # Separator
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=8)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _switch(self, u_id: int, username: str):
        self.app.close_switcher()
        self.app.show_main(u_id, username)

    def _remove(self, u_id: int):
        remove_session(u_id)
        self._build()          # rebuild in place

    def _add_account(self):
        # Store current session info so we can return if user cancels
        current_u_id      = self.current_u_id
        current_sessions  = get_sessions()

        def on_cancel():
            # Restore the previous main screen
            for uid, uname, _, _ in current_sessions:
                if uid == current_u_id:
                    self.app.show_main(uid, uname)
                    return
            # Fallback: just go back to auth
            self.app.show_auth()

        self.app.close_switcher()
        self.app.show_auth(on_cancel=on_cancel)


class CommentsPanel(tk.Frame):
    """
    Floating panel in the bottom-right of the App window.
    Scales its size and position relative to the current window dimensions.
    """

    # Panel occupies 53% of window width and 67% of window height
    W_FRAC = 0.53
    H_FRAC = 0.67
    PAD    = 10

    def __init__(self, app: App, post_id: int, viewer_u_id: int, on_close=None):
        super().__init__(app, bg=PANEL,
                         highlightthickness=1, highlightbackground=ACCENT)
        self.app          = app
        self.post_id      = post_id
        self.viewer_u_id  = viewer_u_id
        self.on_close_cb  = on_close
        self._reply_to_id = None

        self._place()
        self.lift()
        self._build()

    def _panel_dims(self):
        w = max(300, int(self.app.winfo_width()  * self.W_FRAC))
        h = max(340, int(self.app.winfo_height() * self.H_FRAC))
        return w, h

    def _place(self):
        w, h = self._panel_dims()
        self.place(
            relx=1.0, rely=1.0, anchor="se",
            x=-self.PAD, y=-self.PAD,
            width=w, height=h
        )

    def reposition(self):
        """Called by App._apply_scale after a window resize."""
        if self.winfo_exists():
            self._place()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Title bar
        title_bar = tk.Frame(self, bg=ACCENT, height=36)
        title_bar.pack(fill="x", side="top")
        title_bar.pack_propagate(False)

        tk.Label(title_bar, text="💬  Comments", font=F["FONT_HANDLE"],
                 bg=ACCENT, fg="white").pack(side="left", padx=12)

        tk.Button(
            title_bar, text="✕", command=self._close,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", font=F["FONT_LABEL"], cursor="hand2",
            borderwidth=0, padx=10
        ).pack(side="right")

        # Post context strip
        post = get_post_header(self.post_id, self.viewer_u_id)
        if post:
            _, author, content, created_at, edited = post
            ctx = tk.Frame(self, bg=CARD)
            ctx.pack(fill="x")

            ctx_hdr = tk.Frame(ctx, bg=CARD)
            ctx_hdr.pack(fill="x", padx=10, pady=(8, 2))

            clr = avatar_color(author)
            av  = tk.Canvas(ctx_hdr, width=20, height=20, bg=CARD, highlightthickness=0)
            av.pack(side="left")
            av.create_oval(1, 1, 19, 19, fill=clr, outline="")
            av.create_text(10, 10, text=author[0].upper(),
                           fill="white", font=F["FONT_AV_SM"])

            tk.Label(ctx_hdr, text=f"@{author}", font=F["FONT_CMT_HANDLE"],
                     bg=CARD, fg=TEXT).pack(side="left", padx=(6, 0))
            age = format_age(created_at) + (" · edited" if edited else "")
            tk.Label(ctx_hdr, text=age, font=F["FONT_CMT_META"],
                     bg=CARD, fg=SUBTEXT).pack(side="left", padx=(5, 0))

            preview = content if len(content) <= 120 else content[:117] + "…"
            preview_lbl = tk.Label(ctx, text=preview, font=F["FONT_CMT_BODY"],
                                   bg=CARD, fg=SUBTEXT, wraplength=320,
                                   justify="left", anchor="w")
            preview_lbl.pack(fill="x", padx=10, pady=(0, 8))
            auto_wrap(preview_lbl, padding=20)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        self._scroll_outer = tk.Frame(self, bg=BG)
        self._scroll_outer.pack(fill="both", expand=True)
        self._build_scroll_area()

        # Composer
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        composer = tk.Frame(self, bg=PANEL)
        composer.pack(fill="x", padx=10, pady=8)

        self._reply_indicator_var = tk.StringVar(value="")
        tk.Label(composer, textvariable=self._reply_indicator_var,
                 font=F["FONT_META"], bg=PANEL, fg=ACCENT
                 ).pack(anchor="w", pady=(0, 3))

        self._comment_entry = tk.Text(
            composer, height=2, font=F["FONT_CMT_BODY"],
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, padx=6, pady=4
        )
        self._comment_entry.pack(fill="x")

        btn_row = tk.Frame(composer, bg=PANEL)
        btn_row.pack(fill="x", pady=(5, 0))

        self._comment_status = tk.StringVar()
        tk.Label(btn_row, textvariable=self._comment_status,
                 font=F["FONT_META"], bg=PANEL, fg=ERROR).pack(side="left")

        tk.Button(
            btn_row, text="Post", command=self._submit_comment,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", font=F["FONT_BTN"], cursor="hand2",
            padx=14, pady=3, borderwidth=0
        ).pack(side="right")

        self._cancel_reply_btn = tk.Button(
            btn_row, text="✕ Cancel",
            command=self._cancel_reply,
            bg=PANEL, fg=SUBTEXT,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2",
            padx=8, pady=3, borderwidth=0
        )

        self._comment_entry.bind("<Control-Return>", lambda e: self._submit_comment())

    # ── Comment list ──────────────────────────────────────────────────────────

    def _build_scroll_area(self):
        for w in self._scroll_outer.winfo_children():
            w.destroy()

        comments = get_post_comments(self.post_id, self.viewer_u_id)

        canvas = tk.Canvas(self._scroll_outer, bg=BG, highlightthickness=0)
        sb     = tk.Scrollbar(self._scroll_outer, orient="vertical",
                              command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner  = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        if not comments:
            tk.Label(inner, text="No comments yet — be the first!",
                     font=F["FONT_SMALL"], bg=BG, fg=SUBTEXT).pack(pady=30)
        else:
            self._render_tree(inner, comments)

        tk.Frame(inner, bg=BG, height=8).pack()

    def _render_tree(self, parent, rows):
        children: dict = {}
        roots = []
        for r in rows:
            pid = r[1]
            if pid is None:
                roots.append(r)
            else:
                children.setdefault(pid, []).append(r)

        def render(node, depth=0):
            (cid, parent_cid, uid, uname, content, created_at,
             likes, dlikes, edited, my_like, my_dlike) = node

            is_mine   = (uid == self.viewer_u_id)
            indent_px = depth * 12
            wrapper   = tk.Frame(parent, bg=BG)
            wrapper.pack(fill="x", padx=(8 + indent_px, 8), pady=(5, 0))

            if depth > 0:
                line = tk.Frame(wrapper, bg=BORDER, width=2)
                line.pack(side="left", fill="y", padx=(0, 4))

            card = tk.Frame(wrapper, bg=CARD,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", fill="x", expand=True)

            # Header
            chdr = tk.Frame(card, bg=CARD)
            chdr.pack(fill="x", padx=8, pady=(5, 2))

            clr = avatar_color(uname)
            av  = tk.Canvas(chdr, width=16, height=16, bg=CARD, highlightthickness=0)
            av.pack(side="left")
            av.create_oval(1, 1, 15, 15, fill=clr, outline="")
            av.create_text(8, 8, text=uname[0].upper(),
                           fill="white", font=F["FONT_AV_SM"])

            tk.Label(chdr, text=f"@{uname}", font=F["FONT_CMT_HANDLE"],
                     bg=CARD, fg=TEXT).pack(side="left", padx=(4, 0))
            age = format_age(created_at) + (" · edited" if edited else "")
            tk.Label(chdr, text=age, font=F["FONT_CMT_META"],
                     bg=CARD, fg=SUBTEXT).pack(side="left", padx=(4, 0))

            if is_mine:
                own_bar = tk.Frame(chdr, bg=CARD)
                own_bar.pack(side="right")

                def _sb(parent, text, fg, cmd):
                    b = tk.Button(parent, text=text, command=cmd,
                                  bg=CARD, fg=fg,
                                  activebackground=CARD_HOV, activeforeground=TEXT,
                                  relief="flat", font=F["FONT_CMT_META"], cursor="hand2",
                                  borderwidth=0, padx=3)
                    b.pack(side="left")
                    b.bind("<Enter>", lambda e: b.configure(fg=TEXT))
                    b.bind("<Leave>", lambda e: b.configure(fg=fg))

                def make_edit(c_id=cid, c_content=content):
                    return lambda: self._open_edit_comment(c_id, c_content)

                def make_del(c_id=cid, p_cid=parent_cid):
                    return lambda: self._confirm_delete_comment(c_id, p_cid)

                _sb(own_bar, "✏", SUBTEXT,  make_edit())
                _sb(own_bar, "🗑", DLIK_CLR, make_del())

            # Content with auto wraplength
            body_lbl = tk.Label(card, text=content, font=F["FONT_CMT_BODY"],
                                bg=CARD, fg=TEXT, wraplength=260,
                                justify="left", anchor="w")
            body_lbl.pack(fill="x", padx=8, pady=(0, 3))
            auto_wrap(body_lbl, padding=20)

            # Action strip
            arow = tk.Frame(card, bg=CARD)
            arow.pack(fill="x", padx=6, pady=(0, 4))

            lc = LIKE_CLR if my_like  else SUBTEXT
            dc = DLIK_CLR if my_dlike else SUBTEXT
            tk.Label(arow, text=f"▲ {likes}",
                     font=F["FONT_CMT_REACT"], bg=CARD, fg=lc
                     ).pack(side="left", padx=(2, 0))
            tk.Label(arow, text=f"▼ {dlikes}",
                     font=F["FONT_CMT_REACT"], bg=CARD, fg=dc
                     ).pack(side="left", padx=(5, 0))

            def make_reply(c_id=cid, c_uname=uname):
                return lambda: self._set_reply_target(c_id, c_uname)

            rb = tk.Button(arow, text="↩ Reply", command=make_reply(),
                           bg=CARD, fg=SUBTEXT,
                           activebackground=CARD_HOV, activeforeground=ACCENT,
                           relief="flat", font=F["FONT_CMT_META"], cursor="hand2",
                           borderwidth=0, padx=4)
            rb.pack(side="left", padx=(6, 0))
            rb.bind("<Enter>", lambda e: rb.configure(fg=ACCENT))
            rb.bind("<Leave>", lambda e: rb.configure(fg=SUBTEXT))

            for child in children.get(cid, []):
                render(child, depth + 1)

        for root in roots:
            render(root)

    # ── Edit / delete comment ─────────────────────────────────────────────────

    def _open_edit_comment(self, comment_id: int, current_content: str):
        dialog = tk.Toplevel(self)
        dialog.title("Edit Comment")
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()

        w, h = 400, 195
        dialog.geometry(f"{w}x{h}")
        dialog.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        py = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{px}+{py}")

        tk.Label(dialog, text="Edit your comment",
                 font=F["FONT_HANDLE"], bg=PANEL, fg=TEXT).pack(padx=16, pady=(14, 6), anchor="w")

        text_box = tk.Text(
            dialog, height=4, font=F["FONT_POST"],
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, padx=8, pady=6
        )
        text_box.insert("1.0", current_content)
        text_box.pack(fill="x", padx=16)

        status_var = tk.StringVar()
        tk.Label(dialog, textvariable=status_var,
                 font=F["FONT_SMALL"], bg=PANEL, fg=ERROR).pack(padx=16, anchor="w")

        btn_row = tk.Frame(dialog, bg=PANEL)
        btn_row.pack(fill="x", padx=16, pady=(4, 14))

        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  bg="#2e2e2e", fg=SUBTEXT,
                  activebackground=BORDER, activeforeground=TEXT,
                  relief="flat", font=F["FONT_SMALL"], cursor="hand2",
                  borderwidth=0, padx=14, pady=5
                  ).pack(side="right", padx=(6, 0))

        def save():
            new_text = text_box.get("1.0", "end-1c").strip()
            if not new_text:
                status_var.set("Comment can't be empty.")
                return
            if len(new_text) > 500:
                status_var.set("Too long (max 500 chars).")
                return
            edit_comment(comment_id, new_text)
            dialog.destroy()
            self._build_scroll_area()

        tk.Button(btn_row, text="Save", command=save,
                  bg=ACCENT, fg="white",
                  activebackground=ACCENT_HOV, activeforeground="white",
                  relief="flat", font=F["FONT_BTN"], cursor="hand2",
                  borderwidth=0, padx=14, pady=5
                  ).pack(side="right")

        text_box.bind("<Control-Return>", lambda e: save())

    def _confirm_delete_comment(self, comment_id: int, parent_cid):
        dialog = tk.Toplevel(self)
        dialog.title("Delete Comment")
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.grab_set()

        w, h = 300, 130
        dialog.geometry(f"{w}x{h}")
        dialog.update_idletasks()
        px = self.winfo_rootx() + (self.winfo_width()  - w) // 2
        py = self.winfo_rooty() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{px}+{py}")

        tk.Label(dialog, text="Delete this comment?",
                 font=F["FONT_HANDLE"], bg=PANEL, fg=TEXT).pack(pady=(18, 4))
        tk.Label(dialog, text="This can't be undone.",
                 font=F["FONT_SMALL"], bg=PANEL, fg=SUBTEXT).pack()

        btn_row = tk.Frame(dialog, bg=PANEL)
        btn_row.pack(pady=14)

        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  bg="#2e2e2e", fg=SUBTEXT,
                  activebackground=BORDER, activeforeground=TEXT,
                  relief="flat", font=F["FONT_SMALL"], cursor="hand2",
                  borderwidth=0, padx=14, pady=5
                  ).pack(side="left", padx=(0, 8))

        def do_delete():
            dialog.destroy()
            delete_comment(comment_id, self.post_id, parent_cid)
            self._build_scroll_area()

        tk.Button(btn_row, text="Delete", command=do_delete,
                  bg=DLIK_CLR, fg="white",
                  activebackground="#c0392b", activeforeground="white",
                  relief="flat", font=F["FONT_BTN"], cursor="hand2",
                  borderwidth=0, padx=14, pady=5
                  ).pack(side="left")

    # ── Reply targeting ───────────────────────────────────────────────────────

    def _set_reply_target(self, comment_id: int, username: str):
        self._reply_to_id = comment_id
        self._reply_indicator_var.set(f"↩  Replying to @{username}")
        self._cancel_reply_btn.pack(side="right", padx=(6, 0))
        self._comment_entry.focus_set()

    def _cancel_reply(self):
        self._reply_to_id = None
        self._reply_indicator_var.set("")
        self._cancel_reply_btn.pack_forget()

    # ── Submit ────────────────────────────────────────────────────────────────

    def _submit_comment(self):
        content = self._comment_entry.get("1.0", "end-1c").strip()
        if not content:
            self._comment_status.set("Write something first.")
            return
        if len(content) > 500:
            self._comment_status.set("Too long (max 500 chars).")
            return
        create_comment(self.post_id, self.viewer_u_id, content,
                       parent_c_id=self._reply_to_id)
        self._comment_entry.delete("1.0", "end")
        self._comment_status.set("")
        self._cancel_reply()
        self._build_scroll_area()

    # ── Close ─────────────────────────────────────────────────────────────────

    def _close(self):
        self.app._comments_panel = None
        self.destroy()
        if self.on_close_cb:
            self.on_close_cb()

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().mainloop()