from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from pizzaparty.theme import (
    F, BG, PANEL, CARD, CARD_HOV, BORDER, ACCENT, ACCENT_HOV,
    LIKE_CLR, DLIK_CLR, SUCCESS, TEXT, SUBTEXT, ERROR, ENTRY_BG,
    format_age, avatar_color, auto_wrap,
    styled_entry, styled_button, flat_label,
)
from pizzaparty import db

if TYPE_CHECKING:
    from pizzaparty.app import App

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
            result = db.attempt_login(email, password)
            if result:
                self.app.show_main(*result)
            else:
                self.status_var.set("Incorrect email or password.")
        else:
            username = self.entry_username.get().strip()
            if not username:
                self.status_var.set("Please fill in all fields.")
                return
            if not db.attempt_signup(email, password, username):
                self.status_var.set("That email is already registered.")
            else:
                result = db.attempt_login(email, password)
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
        self._current_feed = "for_you"
        self._tab_btns     = {}
        self._build_nav()
        self._build_tab_bar()
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
        if self._current_feed == "for_you":
            self._build_feed_area()
            self.refresh()
        else:
            tk.Label(
                self._content_frame,
                text="Coming soon.",
                font=F["FONT_SMALL"], bg=BG, fg=SUBTEXT, pady=60
            ).pack()

    def _show_compose(self):
        self.app.close_comments()
        self.app.close_switcher()
        self._clear_content()

        outer = tk.Frame(self._content_frame, bg=BG)
        outer.pack(fill="both", expand=True, padx=30, pady=20)

        back_btn = tk.Button(
            outer, text="← Back", command=self._show_feed,
            bg=BG, fg=SUBTEXT, activebackground=BG, activeforeground=TEXT,
            relief="flat", font=F["FONT_SMALL"], cursor="hand2", borderwidth=0
        )
        back_btn.pack(anchor="w", pady=(0, 12))
        back_btn.bind("<Enter>", lambda e: back_btn.configure(fg=TEXT))
        back_btn.bind("<Leave>", lambda e: back_btn.configure(fg=SUBTEXT))

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
        tk.Label(hdr, text="New Post", font=F["FONT_HANDLE"],
                 bg=CARD, fg=TEXT).pack(side="left", padx=(10, 0))

        text_box = tk.Text(
            card, height=5, font=F["FONT_POST"],
            bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
            relief="flat", wrap="word",
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, padx=8, pady=6
        )
        text_box.pack(fill="x", padx=12, pady=(0, 8))
        text_box.focus_set()

        footer = tk.Frame(card, bg=CARD)
        footer.pack(fill="x", padx=12, pady=(0, 10))

        char_var   = tk.StringVar(value="0 / 280")
        is_private = tk.BooleanVar(value=False)
        status_var = tk.StringVar()

        tk.Label(footer, textvariable=char_var,
                 font=F["FONT_META"], bg=CARD, fg=SUBTEXT).pack(side="left")
        tk.Checkbutton(
            footer, text="🔒 Private", variable=is_private,
            bg=CARD, fg=SUBTEXT, activebackground=CARD,
            activeforeground=TEXT, selectcolor=CARD,
            font=F["FONT_META"], cursor="hand2", borderwidth=0, relief="flat"
        ).pack(side="left", padx=(16, 0))

        tk.Label(card, textvariable=status_var,
                 font=F["FONT_SMALL"], bg=CARD, fg=ERROR).pack(pady=(0, 6))

        def on_key(_event=None):
            n = len(text_box.get("1.0", "end-1c"))
            char_var.set(f"{n} / 280")
            status_var.set("" if n <= 280 else "Post is too long.")

        def submit():
            content = text_box.get("1.0", "end-1c").strip()
            if not content:
                status_var.set("Write something first.")
                return
            if len(content) > 280:
                status_var.set("Post is too long (max 280 characters).")
                return
            db.create_post(self.u_id, content, int(is_private.get()))
            self._show_feed()

        text_box.bind("<KeyRelease>", on_key)
        text_box.bind("<Control-Return>", lambda e: submit())

        tk.Button(
            footer, text="Post", command=submit,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", font=F["FONT_BTN"], cursor="hand2",
            padx=20, pady=4, borderwidth=0
        ).pack(side="right")

    def _show_profile(self):
        self.app.close_comments()
        self.app.close_switcher()
        self._clear_content()
        ProfilePanel(self._content_frame, self.u_id, self.u_id,
                     viewer_u_id=self.u_id,
                     on_back=self._show_feed,
                     app=self.app)

    # ── Tab bar ───────────────────────────────────────────────────────────────

    _TABS = [
        ("for_you",  "For You"),
        ("discover", "Discover"),
        ("top",      "Top"),
    ]

    def _build_tab_bar(self):
        bar = tk.Frame(self, bg=PANEL, height=34,
                       highlightthickness=1, highlightbackground=BORDER)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        for feed_id, label in self._TABS:
            btn = tk.Button(
                bar, text=label,
                command=lambda fid=feed_id: self._switch_feed(fid),
                relief="flat", font=F["FONT_LABEL"], cursor="hand2",
                padx=16, pady=0, borderwidth=0
            )
            btn.pack(side="left", fill="y")
            self._tab_btns[feed_id] = btn

        self._update_tab_styles()

    def _update_tab_styles(self):
        for fid, btn in self._tab_btns.items():
            active = (fid == self._current_feed)
            btn.configure(
                bg=ACCENT if active else PANEL,
                fg="white" if active else SUBTEXT,
                activebackground=ACCENT_HOV, activeforeground="white"
            )

    def _switch_feed(self, name: str):
        self._current_feed = name
        self._update_tab_styles()
        self._show_feed()

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
            right, text="Log out", command=self.app.logout,
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

        tk.Frame(inner_chip, bg=BORDER, width=1).pack(side="left", fill="y", pady=2)

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

        new_post_btn = tk.Button(
            nav, text="＋  New Post", command=self._show_compose,
            bg=ACCENT, fg="white",
            activebackground=ACCENT_HOV, activeforeground="white",
            relief="flat", font=F["FONT_SMALL"], cursor="hand2", borderwidth=0,
            padx=14, pady=4
        )
        new_post_btn.pack(side="left", padx=(10, 0))

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

    def refresh(self):
        for w in self._feed_frame.winfo_children():
            w.destroy()

        posts = db.get_feed_posts(self.u_id)

        if not posts:
            tk.Label(
                self._feed_frame,
                text="Nothing here yet — follow some people to see their posts.",
                font=F["FONT_SMALL"], bg=BG, fg=SUBTEXT, pady=60
            ).pack()
            return

        hdr = tk.Frame(self._feed_frame, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(18, 6))
        tk.Label(hdr, text="For You", font=F["FONT_SECTION"],
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(hdr, text=f"{len(posts)} posts", font=F["FONT_SMALL"],
                 bg=BG, fg=SUBTEXT).pack(side="left", padx=(8, 0))

        from pizzaparty.panels import PostCard
        for row in posts:
            PostCard(self._feed_frame, row, self.u_id,
                     on_reaction=self.refresh, app=self.app)

        tk.Frame(self._feed_frame, bg=BG, height=24).pack()

# ── Profile panel ─────────────────────────────────────────────────────────────

class ProfilePanel(tk.Frame):
    def __init__(self, parent, profile_u_id: int, owner_u_id: int,
                 viewer_u_id: int, on_back, app):
        super().__init__(parent, bg=BG)
        self.pack(fill="both", expand=True)
        self.profile_u_id = profile_u_id
        self.owner_u_id   = owner_u_id
        self.viewer_u_id  = viewer_u_id
        self.on_back      = on_back
        self.app          = app
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

        info = db.get_profile(self.profile_u_id)
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

        self._profile_tab      = "posts"
        self._profile_tab_btns = {}
        is_owner = (self.profile_u_id == self.owner_u_id)

        tab_bar = tk.Frame(inner, bg=BG)
        tab_bar.pack(fill="x", padx=30, pady=(18, 0))

        profile_tabs = [("posts", "Posts")]
        if is_owner:
            profile_tabs.append(("private", "Private"))

        for tab_id, label in profile_tabs:
            btn = tk.Button(
                tab_bar, text=label,
                command=lambda tid=tab_id: self._switch_profile_tab(tid),
                relief="flat", font=F["FONT_LABEL"], cursor="hand2",
                padx=14, pady=4, borderwidth=0
            )
            btn.pack(side="left")
            self._profile_tab_btns[tab_id] = btn

        self._update_profile_tab_styles()
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=30)

        self._post_list_container = inner
        self._render_post_list(inner)
        tk.Frame(inner, bg=BG, height=24).pack()

    def _switch_profile_tab(self, tab_id: str):
        self._profile_tab = tab_id
        self._update_profile_tab_styles()
        self._render_post_list(self._post_list_container)

    def _update_profile_tab_styles(self):
        for tid, btn in self._profile_tab_btns.items():
            active = (tid == self._profile_tab)
            btn.configure(
                bg=ACCENT if active else BG,
                fg="white" if active else SUBTEXT,
                activebackground=ACCENT_HOV, activeforeground="white"
            )

    def _render_post_list(self, container):
        for w in getattr(self, "_post_card_widgets", []):
            w.destroy()
        self._post_card_widgets = []

        is_owner = (self.profile_u_id == self.owner_u_id)

        if getattr(self, "_profile_tab", "posts") == "private":
            posts     = db.get_private_posts(self.profile_u_id)
            empty_msg = "No private posts."
        else:
            posts     = db.get_user_posts(self.profile_u_id, self.viewer_u_id)
            empty_msg = "No posts yet."

        if not posts:
            lbl = tk.Label(container, text=empty_msg, font=F["FONT_SMALL"],
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
                    on_change=self._render_post_list_refresh,
                    app=self.app
                )
                self._post_card_widgets.append(card)

    def _render_post_list_refresh(self):
        self._render_post_list(self._post_list_container)

# ── Profile post card ─────────────────────────────────────────────────────────

class ProfilePostCard(tk.Frame):
    def __init__(self, parent, row, viewer_u_id: int,
                 is_owner: bool = False, on_change=None, app=None):
        super().__init__(parent, bg=CARD,
                         highlightthickness=1, highlightbackground=BORDER)
        self.pack(fill="x", padx=30, pady=(0, 10))

        (self.post_id, _, self.author, self.content, self.created_at,
         self.likes, self.dlikes, self.n_comments, self.edited,
         self.my_like, self.my_dlike, self.is_private) = row

        self.viewer_u_id = viewer_u_id
        self.is_owner    = is_owner
        self.on_change   = on_change
        self.app         = app
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

        comment_btn = tk.Button(
            strip,
            text=f"💬  {self.n_comments}  comment{'s' if self.n_comments != 1 else ''}",
            command=self._open_comments,
            bg=CARD, fg=SUBTEXT,
            activebackground=CARD_HOV, activeforeground=TEXT,
            relief="flat", font=F["FONT_META"], cursor="hand2",
            borderwidth=0, padx=10, pady=6
        )
        comment_btn.pack(side="left", padx=(2, 0))
        comment_btn.bind("<Enter>", lambda e: comment_btn.configure(fg=TEXT))
        comment_btn.bind("<Leave>", lambda e: comment_btn.configure(fg=SUBTEXT))

    def _open_comments(self):
        if self.app:
            self.app.open_comments(self.post_id, self.viewer_u_id)

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
        db.edit_post(self.post_id, new_content)
        self.content = new_content
        self.edited  = 1
        self._editing = False
        self._build()

    def _toggle_private(self):
        db.toggle_post_privacy(self.post_id)
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
            db.delete_post(self.post_id)
            self.destroy()
            if self.on_change:
                self.on_change()

        tk.Button(btn_row, text="Delete", command=do_delete,
                  bg=DLIK_CLR, fg="white",
                  activebackground="#c0392b", activeforeground="white",
                  relief="flat", font=F["FONT_BTN"], cursor="hand2",
                  borderwidth=0, padx=16, pady=6
                  ).pack(side="left")
