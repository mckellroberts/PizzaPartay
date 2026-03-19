from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from pizzaparty.theme import (
    F, BG, PANEL, CARD, CARD_HOV, BORDER, ACCENT, ACCENT_HOV,
    LIKE_CLR, DLIK_CLR, TEXT, SUBTEXT, ERROR, ENTRY_BG,
    format_age, avatar_color, auto_wrap,
)
from pizzaparty import db

if TYPE_CHECKING:
    from pizzaparty.app import App

# ── Post card (feed) ──────────────────────────────────────────────────────────

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
        db.toggle_post_reaction(self.post_id, self.viewer_u_id, kind)
        self.on_reaction()

    def _open_comments(self):
        self.app.open_comments(self.post_id, self.viewer_u_id,
                               on_close=self.on_reaction)

# ── Account switcher panel ────────────────────────────────────────────────────

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
        app.bind("<Button-1>", self._on_global_click, add="+")

    def _place(self):
        self.update_idletasks()
        ax = self.anchor.winfo_rootx() - self.app.winfo_rootx()
        ay = self.anchor.winfo_rooty() - self.app.winfo_rooty()
        ah = self.anchor.winfo_height()
        pw = max(260, int(self.app.winfo_width() * 0.34))
        x  = min(ax, self.app.winfo_width() - pw - 4)
        self.place(x=x, y=ay + ah + 4, width=pw)

    def reposition(self):
        if self.winfo_exists():
            self._place()

    def _on_global_click(self, event):
        try:
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            if wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh:
                return
        except Exception:
            return
        self.app.close_switcher()

    def _build(self):
        for w in self.winfo_children():
            w.destroy()

        sessions = db.get_sessions()

        hdr = tk.Frame(self, bg=ACCENT)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Switch Account", font=F["FONT_HANDLE"],
                 bg=ACCENT, fg="white").pack(side="left", padx=12, pady=8)

        if not sessions:
            tk.Label(self, text="No saved accounts yet.",
                     font=F["FONT_SMALL"], bg=PANEL, fg=SUBTEXT
                     ).pack(pady=16, padx=12)
        else:
            for u_id, username, is_deleted in sessions:
                self._render_row(u_id, username, bool(is_deleted),
                                 is_current=(u_id == self.current_u_id))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(4, 0))

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

        clr = avatar_color(username)
        av  = tk.Canvas(row, width=28, height=28, bg=PANEL, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(1, 1, 27, 27, fill=clr if not is_deleted else BORDER, outline="")
        av.create_text(14, 14, text=username[0].upper(),
                       fill="white" if not is_deleted else SUBTEXT,
                       font=F["FONT_AV_SM"])

        text_block = tk.Frame(row, bg=PANEL)
        text_block.pack(side="left", padx=(8, 0), expand=True, fill="x")

        name_color = SUBTEXT if is_deleted else (ACCENT if is_current else TEXT)
        name_text  = f"@{username}" + (" (you)" if is_current else "")
        tk.Label(text_block, text=name_text,
                 font=F["FONT_HANDLE"], bg=PANEL, fg=name_color).pack(anchor="w")

        if is_deleted:
            tk.Label(text_block, text="Account deleted",
                     font=F["FONT_META"], bg=PANEL, fg=DLIK_CLR).pack(anchor="w")

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

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=8)

    def _switch(self, u_id: int, username: str):
        self.app.close_switcher()
        self.app.show_main(u_id, username)

    def _remove(self, u_id: int):
        db.remove_session(u_id)
        self._build()

    def _add_account(self):
        current_u_id     = self.current_u_id
        current_sessions = db.get_sessions()

        def on_cancel():
            for uid, uname, _ in current_sessions:
                if uid == current_u_id:
                    self.app.show_main(uid, uname)
                    return
            self.app.show_auth()

        self.app.close_switcher()
        self.app.show_auth(on_cancel=on_cancel)

# ── Comments panel ────────────────────────────────────────────────────────────

class CommentsPanel(tk.Frame):
    """
    Floating panel in the bottom-right of the App window.
    Scales its size and position relative to the current window dimensions.
    """

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
        if self.winfo_exists():
            self._place()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
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

        post = db.get_post_header(self.post_id, self.viewer_u_id)
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

        comments = db.get_post_comments(self.post_id, self.viewer_u_id)

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

            body_lbl = tk.Label(card, text=content, font=F["FONT_CMT_BODY"],
                                bg=CARD, fg=TEXT, wraplength=260,
                                justify="left", anchor="w")
            body_lbl.pack(fill="x", padx=8, pady=(0, 3))
            auto_wrap(body_lbl, padding=20)

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
            db.edit_comment(comment_id, new_text)
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
            db.delete_comment(comment_id, self.post_id, parent_cid)
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
        db.create_comment(self.post_id, self.viewer_u_id, content,
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
