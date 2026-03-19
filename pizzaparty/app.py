import sys
import tkinter as tk
from pizzaparty.theme import init_fonts, scale_fonts, BASE_W, BG
from pizzaparty.db import save_session, clear_sessions


class App(tk.Tk):
    def __init__(self, auto_login=None):
        super().__init__()
        init_fonts()

        self.title("Pizza Party")
        self.configure(bg=BG)
        self.update_idletasks()
        min_w = max(480, int(self.winfo_screenwidth()  * 0.35))
        min_h = max(400, int(self.winfo_screenheight() * 0.35))
        self.minsize(min_w, min_h)
        self._comments_panel = None
        self._switcher_panel = None
        self._resize_job     = None

        self._center(420, 520)
        self.bind("<Configure>", self._on_configure)
        if sys.platform.startswith("linux"):
            self.bind_all("<Button-4>", lambda e: self._on_scroll(e, -1))
            self.bind_all("<Button-5>", lambda e: self._on_scroll(e,  1))
        else:
            self.bind_all("<MouseWheel>",
                lambda e: self._on_scroll(e, int(-1 * e.delta / 120)))
        if auto_login:
            for u_id, username in auto_login:
                save_session(u_id)
            self.show_main(*auto_login[0])
        else:
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

    def _on_scroll(self, event, delta):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget:
            if isinstance(widget, tk.Canvas):
                try:
                    widget.yview_scroll(delta, "units")
                except tk.TclError:
                    pass
                return
            widget = getattr(widget, "master", None)

    # ── Resize handler ────────────────────────────────────────────────────────

    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._apply_scale)

    def _apply_scale(self):
        self._resize_job = None
        w = self.winfo_width()
        ref = BASE_W if w > 500 else 420
        scale = max(0.6, min(2.0, w / ref))
        scale_fonts(scale)
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

    def logout(self):
        clear_sessions()
        self.show_auth()

    def show_auth(self, on_cancel=None):
        self._center(420, 520)
        self.resizable(False, False)
        self.clear()
        from pizzaparty.screens import AuthScreen
        AuthScreen(self, on_cancel=on_cancel)

    def show_main(self, u_id, username):
        save_session(u_id)
        self._center(700, 780, use_screen_fraction=True)
        self.resizable(True, True)
        self.clear()
        from pizzaparty.screens import MainScreen
        MainScreen(self, u_id, username)

    # ── Account switcher management ───────────────────────────────────────────

    def open_switcher(self, anchor_widget, current_u_id: int):
        if self._switcher_panel and self._switcher_panel.winfo_exists():
            self._switcher_panel.destroy()
            self._switcher_panel = None
            return
        from pizzaparty.panels import AccountSwitcherPanel
        self._switcher_panel = AccountSwitcherPanel(self, anchor_widget, current_u_id)

    def close_switcher(self):
        if self._switcher_panel and self._switcher_panel.winfo_exists():
            self._switcher_panel.destroy()
        self._switcher_panel = None

    # ── Comments panel management ─────────────────────────────────────────────

    def open_comments(self, post_id: int, viewer_u_id: int, on_close=None):
        if self._comments_panel is not None:
            self._comments_panel.destroy()
        from pizzaparty.panels import CommentsPanel
        self._comments_panel = CommentsPanel(self, post_id, viewer_u_id, on_close=on_close)

    def close_comments(self):
        if self._comments_panel is not None:
            self._comments_panel.destroy()
            self._comments_panel = None
