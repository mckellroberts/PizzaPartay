import tkinter as tk
import sqlite3
import os
from datetime import datetime

# ── DB setup ──────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "PizzaParty.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ── Auth queries ──────────────────────────────────────────────────────────────

def attempt_login(email: str, password: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u_id, username FROM Users "
            "WHERE email_address = ? AND password = ? AND is_deleted = 0",
            (email, password)
        ).fetchone()
    return row  # (u_id, username) or None

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
    """Posts from followed users, returned sorted by a recency+likes decay score."""
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
                       SELECT follows_u_id
                       FROM   Follows_ledger
                       WHERE  follower_u_id = ?
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
        # Exponential decay: newer posts and liked posts float to the top.
        # Gravity = 1.8  →  a post's "freshness" halves roughly every ~3 extra hours.
        return (max(row[5], 0) + 1) / (age_hours + 2) ** 1.8

    return sorted(rows, key=score, reverse=True)


def toggle_post_reaction(post_id: int, u_id: int, reaction: str):
    """'like' or 'dislike'. Calling again with the same reaction removes it."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT is_like, is_dlike FROM Posts_ledger WHERE post_id=? AND u_id=?",
            (post_id, u_id)
        ).fetchone()
        if reaction == "like":
            if row and row[0]:
                conn.execute(
                    "DELETE FROM Posts_ledger WHERE post_id=? AND u_id=?",
                    (post_id, u_id)
                )
            else:
                conn.execute("""
                    INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike)
                    VALUES (?,?,1,0)
                    ON CONFLICT(post_id, u_id) DO UPDATE SET is_like=1, is_dlike=0
                """, (post_id, u_id))
        else:
            if row and row[1]:
                conn.execute(
                    "DELETE FROM Posts_ledger WHERE post_id=? AND u_id=?",
                    (post_id, u_id)
                )
            else:
                conn.execute("""
                    INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike)
                    VALUES (?,?,0,1)
                    ON CONFLICT(post_id, u_id) DO UPDATE SET is_like=0, is_dlike=1
                """, (post_id, u_id))


def get_profile(u_id: int):
    """Returns (username, total_followers, total_follows, post_count)."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT u.username, u.total_followers, u.total_follows,
                   COUNT(p.post_id)
            FROM   Users u
            LEFT JOIN Posts p
                   ON p.u_id = u.u_id AND p.is_deleted = 0 AND p.is_archived = 0
            WHERE  u.u_id = ?
            GROUP  BY u.u_id
        """, (u_id,)).fetchone()

def get_user_posts(profile_u_id: int, viewer_u_id: int):
    """All non-deleted, non-archived posts by a user.
    Private posts shown only if the viewer IS the owner."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.post_id, p.u_id, u.username, p.content, p.created_at,
                   p.like_count, p.dlike_count, p.comment_count, p.been_edited,
                   COALESCE(pl.is_like,  0),
                   COALESCE(pl.is_dlike, 0),
                   p.is_private
            FROM   Posts p
            JOIN   Users u  ON p.u_id   = u.u_id
            LEFT JOIN Posts_ledger pl
                           ON p.post_id = pl.post_id AND pl.u_id = ?
            WHERE  p.u_id      = ?
              AND  p.is_deleted  = 0
              AND  p.is_archived = 0
              AND  (p.is_private = 0 OR p.u_id = ?)
            ORDER  BY p.created_at DESC
        """, (viewer_u_id, profile_u_id, viewer_u_id)).fetchall()
    return rows

def create_post(u_id: int, content: str, is_private: int = 0):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Posts (u_id, content, is_private) VALUES (?, ?, ?)",
            (u_id, content, is_private)
        )

def create_comment(post_id: int, u_id: int, content: str, parent_c_id=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Comments (parent_c_id, post_id, u_id, content) "
            "VALUES (?, ?, ?, ?)",
            (parent_c_id, post_id, u_id, content)
        )
        comment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        if parent_c_id:
            conn.execute(
                "UPDATE Comments SET comment_count = comment_count + 1 "
                "WHERE comment_id = ?", (parent_c_id,)
            )
        conn.execute(
            "UPDATE Posts SET comment_count = comment_count + 1 "
            "WHERE post_id = ?", (post_id,)
        )
    return comment_id

def get_post_header(post_id: int, viewer_u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.post_id, u.username, p.content, p.created_at, p.been_edited
            FROM   Posts p
            JOIN   Users u ON p.u_id = u.u_id
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
            JOIN   Users u  ON c.u_id      = u.u_id
            LEFT JOIN Comments_ledger cl
                            ON c.comment_id = cl.comment_id AND cl.u_id = ?
            WHERE  c.post_id   = ?
              AND  c.is_deleted = 0
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
TEXT       = "#e8e8e8"
SUBTEXT    = "#777777"
ERROR      = "#ed4245"
ENTRY_BG   = "#111111"

FONT_TITLE  = ("Georgia",    22, "bold")
FONT_LABEL  = ("Helvetica",  10)
FONT_ENTRY  = ("Helvetica",  11)
FONT_BTN    = ("Helvetica",  11, "bold")
FONT_SMALL  = ("Helvetica",   9)
FONT_NAV    = ("Georgia",    15, "bold")
FONT_HANDLE = ("Helvetica",  10, "bold")
FONT_POST   = ("Helvetica",  11)
FONT_META   = ("Helvetica",   9)

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

# ── Reusable widgets ──────────────────────────────────────────────────────────

def styled_entry(parent, show=None):
    return tk.Entry(
        parent, show=show,
        bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
        relief="flat", font=FONT_ENTRY,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT
    )

def styled_button(parent, text, command, color=ACCENT, hover=ACCENT_HOV):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg="white", activebackground=hover, activeforeground="white",
        relief="flat", font=FONT_BTN, cursor="hand2",
        padx=0, pady=10, borderwidth=0
    )
    return btn

def flat_label(parent, text, font=FONT_LABEL, fg=SUBTEXT, bg=PANEL, **kw):
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=font, **kw)

# ── App shell ─────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pizza Party")
        self.configure(bg=BG)
        self.resizable(False, False)
        self._center(420, 520)
        self.show_auth()

    def _center(self, w, h):
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def show_auth(self):
        self._center(420, 520)
        self.clear()
        AuthScreen(self)

    def show_main(self, u_id, username):
        self._center(700, 780)
        self.clear()
        MainScreen(self, u_id, username)

# ── Auth screen ───────────────────────────────────────────────────────────────

class AuthScreen(tk.Frame):
    def __init__(self, app: App):
        super().__init__(app, bg=BG)
        self.app  = app
        self.mode = tk.StringVar(value="login")
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        wrapper = tk.Frame(self, bg=BG)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(wrapper, text="welcome back", font=FONT_TITLE,
                 bg=BG, fg=TEXT).pack(pady=(0, 4))
        self.subtitle = tk.Label(wrapper, text="log in to continue",
                                  font=FONT_SMALL, bg=BG, fg=SUBTEXT)
        self.subtitle.pack(pady=(0, 24))

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
                 font=FONT_SMALL, wraplength=280).pack(pady=(8, 0))

        self.submit_btn = styled_button(panel, "Log in", self._submit)
        self.submit_btn.pack(fill="x", pady=(12, 0))

    def _tab(self, parent, text, mode):
        def select():
            self.mode.set(mode)
            self._render_fields()
            self._update_tabs()
        btn = tk.Button(parent, text=text, command=select,
                        relief="flat", font=FONT_LABEL, cursor="hand2",
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
            relief="flat", font=FONT_SMALL, cursor="hand2", borderwidth=0, width=4
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
        self._clear_content()
        self._build_composer()
        self._build_feed_area()
        self.refresh()

    def _show_profile(self):
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

        # Brand (clickable → home feed)
        brand = tk.Frame(nav, bg=PANEL, cursor="hand2")
        brand.pack(side="left", padx=20, fill="y")
        pizza_lbl = tk.Label(brand, text="🍕", font=("Helvetica", 18), bg=PANEL, fg=TEXT, cursor="hand2")
        pizza_lbl.pack(side="left")
        name_lbl = tk.Label(brand, text="Pizza Party", font=FONT_NAV, bg=PANEL, fg=TEXT, cursor="hand2")
        name_lbl.pack(side="left", padx=(6, 0))

        for w in (brand, pizza_lbl, name_lbl):
            w.bind("<Button-1>", lambda e: self._show_feed())
            w.bind("<Enter>",    lambda e: name_lbl.configure(fg=ACCENT))
            w.bind("<Leave>",    lambda e: name_lbl.configure(fg=TEXT))

        # Right side
        right = tk.Frame(nav, bg=PANEL)
        right.pack(side="right", padx=16, fill="y")

        logout_btn = tk.Button(
            right, text="Log out", command=self.app.show_auth,
            bg=PANEL, fg=SUBTEXT,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", font=FONT_SMALL, cursor="hand2", borderwidth=0,
            padx=10, pady=4
        )
        logout_btn.pack(side="right", padx=(8, 0))
        logout_btn.bind("<Enter>", lambda e: logout_btn.configure(fg=TEXT))
        logout_btn.bind("<Leave>", lambda e: logout_btn.configure(fg=SUBTEXT))

        # Avatar + username chip  (clickable → profile)
        chip = tk.Frame(right, bg=BORDER, padx=1, pady=1)
        chip.pack(side="right")
        inner_chip = tk.Frame(chip, bg=PANEL, padx=8, pady=4, cursor="hand2")
        inner_chip.pack()

        av = tk.Canvas(inner_chip, width=20, height=20, bg=PANEL,
                       highlightthickness=0, cursor="hand2")
        av.pack(side="left")
        clr = avatar_color(self.username)
        av.create_oval(1, 1, 19, 19, fill=clr, outline="")
        av.create_text(10, 10, text=self.username[0].upper(),
                       fill="white", font=("Helvetica", 9, "bold"))

        name_lbl = tk.Label(inner_chip, text=f"@{self.username}", font=FONT_LABEL,
                            bg=PANEL, fg=TEXT, cursor="hand2")
        name_lbl.pack(side="left", padx=(6, 0))

        # Bind click + hover to entire chip
        for w in (inner_chip, av, name_lbl):
            w.bind("<Button-1>", lambda e: self._show_profile())
            w.bind("<Enter>",    lambda e: name_lbl.configure(fg=ACCENT))
            w.bind("<Leave>",    lambda e: name_lbl.configure(fg=TEXT))

        # Refresh button
        refresh_btn = tk.Button(
            nav, text="⟳  Refresh", command=self.refresh,
            bg=PANEL, fg=SUBTEXT,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", font=FONT_SMALL, cursor="hand2", borderwidth=0,
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

        # Header row: avatar + placeholder label
        hdr = tk.Frame(card, bg=CARD)
        hdr.pack(fill="x", padx=12, pady=(12, 6))

        clr = avatar_color(self.username)
        av  = tk.Canvas(hdr, width=30, height=30, bg=CARD, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 29, 29, fill=clr, outline="")
        av.create_text(15, 15, text=self.username[0].upper(),
                       fill="white", font=("Helvetica", 11, "bold"))

        tk.Label(hdr, text=f"What's on your mind, @{self.username}?",
                 font=FONT_SMALL, bg=CARD, fg=SUBTEXT).pack(
            side="left", padx=(10, 0))

        # Text box
        self._composer_text = tk.Text(
            card, height=3, font=FONT_POST,
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, padx=8, pady=6
        )
        self._composer_text.pack(fill="x", padx=12, pady=(0, 8))

        # Bottom row: char counter + privacy toggle + post button
        footer = tk.Frame(card, bg=CARD)
        footer.pack(fill="x", padx=12, pady=(0, 10))

        self._char_var = tk.StringVar(value="0 / 280")
        tk.Label(footer, textvariable=self._char_var,
                 font=FONT_META, bg=CARD, fg=SUBTEXT).pack(side="left")

        self._composer_text.bind("<KeyRelease>", self._on_composer_key)

        self._is_private = tk.BooleanVar(value=False)
        priv_btn = tk.Checkbutton(
            footer, text="🔒 Private",
            variable=self._is_private,
            bg=CARD, fg=SUBTEXT, activebackground=CARD,
            activeforeground=TEXT, selectcolor=CARD,
            font=FONT_META, cursor="hand2", borderwidth=0, relief="flat"
        )
        priv_btn.pack(side="left", padx=(16, 0))

        self._post_btn = tk.Button(
            footer, text="Post",
            command=self._submit_post,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", font=FONT_BTN, cursor="hand2",
            padx=20, pady=4, borderwidth=0
        )
        self._post_btn.pack(side="right")

        self._composer_status = tk.StringVar()
        tk.Label(card, textvariable=self._composer_status,
                 font=FONT_SMALL, bg=CARD, fg=ERROR).pack(pady=(0, 6))

    def _on_composer_key(self, _event=None):
        content = self._composer_text.get("1.0", "end-1c")
        n = len(content)
        self._char_var.set(f"{n} / 280")
        color = DLIK_CLR if n > 280 else SUBTEXT
        # update counter color if over limit
        for w in self._composer_text.master.winfo_children():
            pass  # handled via label fg below
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

    # ── Feed area (scrollable canvas) ─────────────────────────────────────────

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
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._win_id, width=e.width))
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(
                int(-1 * (e.delta / 120)), "units"))

    def refresh(self):
        for w in self._feed_frame.winfo_children():
            w.destroy()

        posts = get_feed_posts(self.u_id)

        if not posts:
            tk.Label(
                self._feed_frame,
                text="Nothing here yet — follow some people to see their posts.",
                font=FONT_SMALL, bg=BG, fg=SUBTEXT, pady=60
            ).pack()
            return

        # Feed header
        hdr = tk.Frame(self._feed_frame, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(18, 6))
        tk.Label(hdr, text="Your Feed", font=("Georgia", 13, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(hdr, text=f"{len(posts)} posts", font=FONT_SMALL,
                 bg=BG, fg=SUBTEXT).pack(side="left", padx=(8, 0))

        for row in posts:
            PostCard(self._feed_frame, row, self.u_id,
                     on_reaction=self.refresh, app=self.app)

        # Bottom padding
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
        # ── Scrollable outer canvas ───────────────────────────────────────────
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

        # ── Back button ───────────────────────────────────────────────────────
        back_row = tk.Frame(inner, bg=BG)
        back_row.pack(fill="x", padx=30, pady=(14, 0))
        back_btn = tk.Button(
            back_row, text="← Back to Feed", command=self.on_back,
            bg=BG, fg=SUBTEXT, activebackground=BG, activeforeground=TEXT,
            relief="flat", font=FONT_SMALL, cursor="hand2", borderwidth=0
        )
        back_btn.pack(side="left")
        back_btn.bind("<Enter>", lambda e: back_btn.configure(fg=TEXT))
        back_btn.bind("<Leave>", lambda e: back_btn.configure(fg=SUBTEXT))

        # ── Profile hero card ─────────────────────────────────────────────────
        info = get_profile(self.profile_u_id)
        if not info:
            tk.Label(inner, text="User not found.", font=FONT_SMALL,
                     bg=BG, fg=SUBTEXT).pack(pady=40)
            return

        username, followers, follows, post_count = info

        hero = tk.Frame(inner, bg=PANEL,
                        highlightthickness=1, highlightbackground=BORDER)
        hero.pack(fill="x", padx=30, pady=(10, 0))

        hero_body = tk.Frame(hero, bg=PANEL)
        hero_body.pack(fill="x", padx=20, pady=18)

        # Large avatar
        clr = avatar_color(username)
        av  = tk.Canvas(hero_body, width=64, height=64, bg=PANEL,
                        highlightthickness=0)
        av.pack(side="left")
        av.create_oval(2, 2, 62, 62, fill=clr, outline="")
        av.create_text(32, 32, text=username[0].upper(),
                       fill="white", font=("Helvetica", 26, "bold"))

        info_box = tk.Frame(hero_body, bg=PANEL)
        info_box.pack(side="left", padx=(18, 0))

        tk.Label(info_box, text=f"@{username}",
                 font=("Georgia", 16, "bold"), bg=PANEL, fg=TEXT).pack(anchor="w")

        stats_row = tk.Frame(info_box, bg=PANEL)
        stats_row.pack(anchor="w", pady=(6, 0))

        for val, lbl in [
            (followers,   "followers"),
            (follows,     "following"),
            (post_count,  "posts"),
        ]:
            block = tk.Frame(stats_row, bg=PANEL)
            block.pack(side="left", padx=(0, 20))
            tk.Label(block, text=str(val),
                     font=("Helvetica", 12, "bold"), bg=PANEL, fg=TEXT
                     ).pack(anchor="w")
            tk.Label(block, text=lbl,
                     font=FONT_META, bg=PANEL, fg=SUBTEXT).pack(anchor="w")

        # ── Posts section header ──────────────────────────────────────────────
        ph = tk.Frame(inner, bg=BG)
        ph.pack(fill="x", padx=30, pady=(18, 6))
        tk.Label(ph, text="Posts", font=("Georgia", 13, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=30)

        # ── Post list ─────────────────────────────────────────────────────────
        posts = get_user_posts(self.profile_u_id, self.viewer_u_id)

        if not posts:
            tk.Label(inner, text="No posts yet.", font=FONT_SMALL,
                     bg=BG, fg=SUBTEXT).pack(pady=30)
        else:
            tk.Frame(inner, bg=BG, height=8).pack()
            for row in posts:
                # row has 12 cols: standard 11 + is_private at index 11
                ProfilePostCard(inner, row, self.viewer_u_id)

        tk.Frame(inner, bg=BG, height=24).pack()


class ProfilePostCard(tk.Frame):
    """Slimmed-down read-only post card for the profile page."""

    def __init__(self, parent, row, viewer_u_id: int):
        super().__init__(parent, bg=CARD,
                         highlightthickness=1, highlightbackground=BORDER)
        self.pack(fill="x", padx=30, pady=(0, 10))

        (post_id, _, author, content, created_at,
         likes, dlikes, n_comments, edited,
         my_like, my_dlike, is_private) = row

        self.viewer_u_id = viewer_u_id
        self.post_id     = post_id

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=CARD)
        hdr.pack(fill="x", padx=14, pady=(10, 0))

        clr = avatar_color(author)
        av  = tk.Canvas(hdr, width=30, height=30, bg=CARD, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 29, 29, fill=clr, outline="")
        av.create_text(15, 15, text=author[0].upper(),
                       fill="white", font=("Helvetica", 10, "bold"))

        meta = tk.Frame(hdr, bg=CARD)
        meta.pack(side="left", padx=(10, 0))
        tk.Label(meta, text=f"@{author}",
                 font=FONT_HANDLE, bg=CARD, fg=TEXT).pack(anchor="w")
        age = format_age(created_at) + (" · edited" if edited else "")
        if is_private:
            age += "  🔒"
        tk.Label(meta, text=age, font=FONT_META, bg=CARD, fg=SUBTEXT
                 ).pack(anchor="w")

        # ── Content ───────────────────────────────────────────────────────────
        tk.Label(self, text=content, font=FONT_POST, bg=CARD, fg=TEXT,
                 wraplength=608, justify="left", anchor="w"
                 ).pack(fill="x", padx=14, pady=(8, 10))

        # ── Stats strip ───────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")
        strip = tk.Frame(self, bg=CARD)
        strip.pack(fill="x", padx=12, pady=5)

        lc = LIKE_CLR if my_like  else SUBTEXT
        dc = DLIK_CLR if my_dlike else SUBTEXT
        tk.Label(strip, text=f"▲  {likes}",
                 font=("Helvetica", 9, "bold"), bg=CARD, fg=lc
                 ).pack(side="left", padx=(4, 0))
        tk.Label(strip, text=f"▼  {dlikes}",
                 font=("Helvetica", 9, "bold"), bg=CARD, fg=dc
                 ).pack(side="left", padx=(8, 0))
        tk.Label(strip,
                 text=f"💬  {n_comments}  comment{'s' if n_comments != 1 else ''}",
                 font=FONT_META, bg=CARD, fg=SUBTEXT
                 ).pack(side="left", padx=(12, 0))


# ── Post card ─────────────────────────────────────────────────────────────────

class PostCard(tk.Frame):
    """
    row columns:
      0  post_id       1  u_id         2  username    3  content
      4  created_at    5  like_count   6  dlike_count 7  comment_count
      8  been_edited   9  my_like      10 my_dlike
    """

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
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=CARD)
        header.pack(fill="x", padx=14, pady=(12, 0))

        # Coloured avatar circle
        clr = avatar_color(self.author)
        av  = tk.Canvas(header, width=34, height=34, bg=CARD,
                        highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 33, 33, fill=clr, outline="")
        av.create_text(17, 17, text=self.author[0].upper(),
                       fill="white", font=("Helvetica", 12, "bold"))

        meta_box = tk.Frame(header, bg=CARD)
        meta_box.pack(side="left", padx=(10, 0))
        tk.Label(meta_box, text=f"@{self.author}",
                 font=FONT_HANDLE, bg=CARD, fg=TEXT).pack(anchor="w")
        age_txt = format_age(self.created_at) + (" · edited" if self.edited else "")
        tk.Label(meta_box, text=age_txt,
                 font=FONT_META, bg=CARD, fg=SUBTEXT).pack(anchor="w")

        # ── Content ───────────────────────────────────────────────────────────
        tk.Label(self, text=self.content, font=FONT_POST,
                 bg=CARD, fg=TEXT, wraplength=608,
                 justify="left", anchor="w").pack(
            fill="x", padx=14, pady=(10, 12))

        # ── Divider ───────────────────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── Action row ────────────────────────────────────────────────────────
        actions = tk.Frame(self, bg=CARD)
        actions.pack(fill="x", padx=8, pady=5)

        self._like_btn  = self._reaction_btn(
            actions, "▲", self.likes, bool(self.my_like),
            LIKE_CLR, lambda: self._react("like")
        )
        self._dlike_btn = self._reaction_btn(
            actions, "▼", self.dlikes, bool(self.my_dlike),
            DLIK_CLR, lambda: self._react("dislike")
        )

        # Thin separator
        sep = tk.Frame(actions, bg=BORDER, width=1)
        sep.pack(side="left", fill="y", padx=10, pady=4)

        # Comments button
        comment_btn = tk.Button(
            actions,
            text=f"💬  {self.n_comments}  comment{'s' if self.n_comments != 1 else ''}",
            command=self._open_comments,
            bg=CARD, fg=SUBTEXT,
            activebackground=CARD_HOV, activeforeground=TEXT,
            relief="flat", font=FONT_META, cursor="hand2",
            borderwidth=0, padx=10, pady=6
        )
        comment_btn.pack(side="left")
        comment_btn.bind("<Enter>", lambda e: comment_btn.configure(fg=TEXT))
        comment_btn.bind("<Leave>", lambda e: comment_btn.configure(fg=SUBTEXT))

    def _reaction_btn(self, parent, symbol, count, active, active_clr, cmd):
        fg = active_clr if active else SUBTEXT
        btn = tk.Button(
            parent, text=f"{symbol}  {count}",
            command=cmd,
            bg=CARD, fg=fg,
            activebackground=CARD_HOV, activeforeground=active_clr,
            relief="flat", font=("Helvetica", 10, "bold"), cursor="hand2",
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
        CommentsDialog(self.app, self.post_id, self.viewer_u_id,
                       on_close=self.on_reaction)

# ── Comments dialog ───────────────────────────────────────────────────────────

class CommentsDialog(tk.Toplevel):
    def __init__(self, parent: App, post_id: int,
                 viewer_u_id: int, on_close=None):
        super().__init__(parent)
        self.post_id      = post_id
        self.viewer_u_id  = viewer_u_id
        self.on_close_cb  = on_close
        self._reply_to_id = None   # comment_id being replied to, or None
        self._reply_frame = None   # the currently open inline reply widget

        self.title("Comments")
        self.configure(bg=BG)
        self.resizable(False, False)

        w, h = 600, 680
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()

    # ── Initial layout ────────────────────────────────────────────────────────

    def _build(self):
        # Post context card (static, never rebuilt)
        post = get_post_header(self.post_id, self.viewer_u_id)
        if post:
            _, author, content, created_at, edited = post
            ctx = tk.Frame(self, bg=PANEL,
                           highlightthickness=1, highlightbackground=BORDER)
            ctx.pack(fill="x", padx=16, pady=(14, 0))

            ctx_hdr = tk.Frame(ctx, bg=PANEL)
            ctx_hdr.pack(fill="x", padx=12, pady=(10, 4))

            clr = avatar_color(author)
            av  = tk.Canvas(ctx_hdr, width=26, height=26, bg=PANEL,
                            highlightthickness=0)
            av.pack(side="left")
            av.create_oval(1, 1, 25, 25, fill=clr, outline="")
            av.create_text(13, 13, text=author[0].upper(),
                           fill="white", font=("Helvetica", 9, "bold"))

            tk.Label(ctx_hdr, text=f"@{author}", font=FONT_HANDLE,
                     bg=PANEL, fg=TEXT).pack(side="left", padx=(8, 0))
            age = format_age(created_at) + (" · edited" if edited else "")
            tk.Label(ctx_hdr, text=age, font=FONT_META,
                     bg=PANEL, fg=SUBTEXT).pack(side="left", padx=(8, 0))

            tk.Label(ctx, text=content, font=FONT_POST, bg=PANEL, fg=TEXT,
                     wraplength=550, justify="left", anchor="w").pack(
                fill="x", padx=12, pady=(0, 10))

        # Scrollable comment area (rebuilt on refresh)
        self._scroll_outer = tk.Frame(self, bg=BG)
        self._scroll_outer.pack(fill="both", expand=True)
        self._build_scroll_area()

        # ── Fixed bottom composer ─────────────────────────────────────────────
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        composer_frame = tk.Frame(self, bg=PANEL)
        composer_frame.pack(fill="x", padx=16, pady=10)

        # "Replying to @x" indicator
        self._reply_indicator_var = tk.StringVar(value="")
        self._reply_indicator_lbl = tk.Label(
            composer_frame, textvariable=self._reply_indicator_var,
            font=FONT_META, bg=PANEL, fg=ACCENT
        )
        self._reply_indicator_lbl.pack(anchor="w", pady=(0, 4))

        text_row = tk.Frame(composer_frame, bg=PANEL)
        text_row.pack(fill="x")

        self._comment_entry = tk.Text(
            text_row, height=2, font=FONT_POST,
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, padx=8, pady=6
        )
        self._comment_entry.pack(side="left", fill="x", expand=True)

        btn_col = tk.Frame(text_row, bg=PANEL)
        btn_col.pack(side="left", padx=(8, 0))

        post_btn = tk.Button(
            btn_col, text="Post",
            command=self._submit_comment,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", font=FONT_BTN, cursor="hand2",
            padx=14, pady=6, borderwidth=0
        )
        post_btn.pack(fill="x")

        self._cancel_reply_btn = tk.Button(
            btn_col, text="Cancel",
            command=self._cancel_reply,
            bg="#2e2e2e", fg=SUBTEXT,
            activebackground=BORDER, activeforeground=TEXT,
            relief="flat", font=FONT_SMALL, cursor="hand2",
            padx=14, pady=4, borderwidth=0
        )
        # Only shown when replying

        self._comment_status = tk.StringVar()
        tk.Label(composer_frame, textvariable=self._comment_status,
                 font=FONT_SMALL, bg=PANEL, fg=ERROR).pack(anchor="w", pady=(4, 0))

        # Bind Ctrl+Enter to post
        self._comment_entry.bind("<Control-Return>", lambda e: self._submit_comment())

    def _build_scroll_area(self):
        """Clears and rebuilds the scrollable comment tree."""
        for w in self._scroll_outer.winfo_children():
            w.destroy()

        comments = get_post_comments(self.post_id, self.viewer_u_id)

        # Section header
        hdr_row = tk.Frame(self._scroll_outer, bg=BG)
        hdr_row.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(hdr_row, text="Comments", font=("Georgia", 11, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        n = len(comments)
        tk.Label(hdr_row, text=str(n) if n else "",
                 font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(side="left", padx=(6, 0))

        tk.Frame(self._scroll_outer, bg=BORDER, height=1).pack(fill="x", padx=16)

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
                     font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(pady=40)
        else:
            self._render_tree(inner, comments)

        tk.Frame(inner, bg=BG, height=10).pack()

    # ── Comment tree renderer ─────────────────────────────────────────────────

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
            (cid, _, uid, uname, content, created_at,
             likes, dlikes, edited, my_like, my_dlike) = node

            indent_px = depth * 22
            wrapper = tk.Frame(parent, bg=BG)
            wrapper.pack(fill="x", padx=(16 + indent_px, 16), pady=(8, 0))

            if depth > 0:
                line = tk.Frame(wrapper, bg=BORDER, width=2)
                line.pack(side="left", fill="y", padx=(0, 8))

            card = tk.Frame(wrapper, bg=CARD,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", fill="x", expand=True)

            # Header
            chdr = tk.Frame(card, bg=CARD)
            chdr.pack(fill="x", padx=10, pady=(8, 4))

            clr = avatar_color(uname)
            av  = tk.Canvas(chdr, width=22, height=22, bg=CARD,
                            highlightthickness=0)
            av.pack(side="left")
            av.create_oval(1, 1, 21, 21, fill=clr, outline="")
            av.create_text(11, 11, text=uname[0].upper(),
                           fill="white", font=("Helvetica", 8, "bold"))

            tk.Label(chdr, text=f"@{uname}", font=FONT_HANDLE,
                     bg=CARD, fg=TEXT).pack(side="left", padx=(7, 0))
            age = format_age(created_at) + (" · edited" if edited else "")
            tk.Label(chdr, text=age, font=FONT_META,
                     bg=CARD, fg=SUBTEXT).pack(side="left", padx=(6, 0))

            # Content
            wrap = max(460 - indent_px * 2, 240)
            tk.Label(card, text=content, font=FONT_POST,
                     bg=CARD, fg=TEXT, wraplength=wrap,
                     justify="left", anchor="w").pack(
                fill="x", padx=10, pady=(0, 6))

            # Action strip: reactions + Reply
            arow = tk.Frame(card, bg=CARD)
            arow.pack(fill="x", padx=8, pady=(0, 6))

            lc = LIKE_CLR if my_like  else SUBTEXT
            dc = DLIK_CLR if my_dlike else SUBTEXT
            tk.Label(arow, text=f"▲  {likes}",
                     font=("Helvetica", 8, "bold"), bg=CARD, fg=lc
                     ).pack(side="left", padx=(4, 0))
            tk.Label(arow, text=f"▼  {dlikes}",
                     font=("Helvetica", 8, "bold"), bg=CARD, fg=dc
                     ).pack(side="left", padx=(8, 0))

            # Reply button — captures cid and uname by default arg
            def make_reply(c_id=cid, c_uname=uname):
                return lambda: self._set_reply_target(c_id, c_uname)

            reply_btn = tk.Button(
                arow, text="↩ Reply",
                command=make_reply(),
                bg=CARD, fg=SUBTEXT,
                activebackground=CARD_HOV, activeforeground=ACCENT,
                relief="flat", font=FONT_META, cursor="hand2",
                borderwidth=0, padx=8
            )
            reply_btn.pack(side="left", padx=(10, 0))
            reply_btn.bind("<Enter>", lambda e: reply_btn.configure(fg=ACCENT))
            reply_btn.bind("<Leave>", lambda e: reply_btn.configure(fg=SUBTEXT))

            # Recurse into children
            for child in children.get(cid, []):
                render(child, depth + 1)

        for root in roots:
            render(root)

    # ── Reply targeting ───────────────────────────────────────────────────────

    def _set_reply_target(self, comment_id: int, username: str):
        self._reply_to_id = comment_id
        self._reply_indicator_var.set(f"↩  Replying to @{username}")
        self._cancel_reply_btn.pack(fill="x", pady=(4, 0))
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
            self._comment_status.set("Comment too long (max 500 chars).")
            return

        create_comment(self.post_id, self.viewer_u_id, content,
                       parent_c_id=self._reply_to_id)

        self._comment_entry.delete("1.0", "end")
        self._comment_status.set("")
        self._cancel_reply()
        self._build_scroll_area()   # refresh tree

    # ── Close ─────────────────────────────────────────────────────────────────

    def _close(self):
        self.destroy()
        if self.on_close_cb:
            self.on_close_cb()

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().mainloop()