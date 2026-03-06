import tkinter as tk
import sqlite3
import os

# ── DB setup ────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "PizzaParty.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

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
        return False  # email already taken

# ── Theme ────────────────────────────────────────────────────────────────────

BG         = "#0e0e0e"
PANEL      = "#1a1a1a"
BORDER     = "#2e2e2e"
ACCENT     = "#5865f2"
ACCENT_HOV = "#4752c4"
TEXT       = "#e8e8e8"
SUBTEXT    = "#888888"
ERROR      = "#ed4245"
SUCCESS    = "#57f287"
ENTRY_BG   = "#111111"

FONT_TITLE  = ("Georgia", 22, "bold")
FONT_LABEL  = ("Helvetica", 10)
FONT_ENTRY  = ("Helvetica", 11)
FONT_BTN    = ("Helvetica", 11, "bold")
FONT_SMALL  = ("Helvetica", 9)

# ── Reusable widgets ──────────────────────────────────────────────────────────

def styled_entry(parent, show=None):
    e = tk.Entry(
        parent, show=show,
        bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
        relief="flat", font=FONT_ENTRY,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT
    )
    return e

def styled_button(parent, text, command, color=ACCENT, hover=ACCENT_HOV):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg="white", activebackground=hover, activeforeground="white",
        relief="flat", font=FONT_BTN, cursor="hand2",
        padx=0, pady=10, borderwidth=0
    )
    return btn

def label(parent, text, font=FONT_LABEL, fg=SUBTEXT, **kwargs):
    return tk.Label(parent, text=text, bg=PANEL, fg=fg, font=font, **kwargs)

# ── Main App ──────────────────────────────────────────────────────────────────

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
        self.clear()
        AuthScreen(self)

    def show_main(self, u_id, username):
        self.clear()
        MainScreen(self, u_id, username)


# ── Auth screen ───────────────────────────────────────────────────────────────

class AuthScreen(tk.Frame):
    def __init__(self, app: App):
        super().__init__(app, bg=BG)
        self.app = app
        self.mode = tk.StringVar(value="login")  # "login" | "signup"
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        # Outer padding
        wrapper = tk.Frame(self, bg=BG)
        wrapper.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        tk.Label(wrapper, text="welcome back", font=FONT_TITLE,
                 bg=BG, fg=TEXT).pack(pady=(0, 4))
        self.subtitle = tk.Label(wrapper, text="log in to continue",
                                  font=FONT_SMALL, bg=BG, fg=SUBTEXT)
        self.subtitle.pack(pady=(0, 24))

        # Panel
        panel = tk.Frame(wrapper, bg=PANEL, padx=32, pady=28,
                         highlightthickness=1, highlightbackground=BORDER)
        panel.pack(ipadx=10)

        # Tab toggle
        tab_row = tk.Frame(panel, bg=PANEL)
        tab_row.pack(fill="x", pady=(0, 20))

        self.tab_login  = self._tab(tab_row, "Login",   "login")
        self.tab_signup = self._tab(tab_row, "Sign up", "signup")
        self.tab_login.pack(side="left", expand=True, fill="x")
        self.tab_signup.pack(side="left", expand=True, fill="x")

        # Fields
        self.fields_frame = tk.Frame(panel, bg=PANEL)
        self.fields_frame.pack(fill="x")

        self._render_fields()

        # Status label
        self.status_var = tk.StringVar()
        self.status_lbl = tk.Label(panel, textvariable=self.status_var,
                                    bg=PANEL, fg=ERROR, font=FONT_SMALL,
                                    wraplength=280)
        self.status_lbl.pack(pady=(8, 0))

        # Submit button
        self.submit_btn = styled_button(panel, "Log in", self._submit)
        self.submit_btn.pack(fill="x", pady=(12, 0), ipady=0)

    def _tab(self, parent, text, mode):
        def select():
            self.mode.set(mode)
            self._render_fields()
            self._update_tabs()
        btn = tk.Button(
            parent, text=text, command=select,
            relief="flat", font=FONT_LABEL, cursor="hand2",
            padx=0, pady=8, borderwidth=0
        )
        self._style_tab(btn, mode == self.mode.get())
        return btn

    def _style_tab(self, btn, active):
        btn.configure(
            bg=ACCENT if active else PANEL,
            fg="white" if active else SUBTEXT,
            activebackground=ACCENT_HOV,
            activeforeground="white"
        )

    def _update_tabs(self):
        self._style_tab(self.tab_login,  self.mode.get() == "login")
        self._style_tab(self.tab_signup, self.mode.get() == "signup")
        is_signup = self.mode.get() == "signup"
        self.submit_btn.configure(text="Create account" if is_signup else "Log in")
        self.subtitle.configure(
            text="create a new account" if is_signup else "log in to continue"
        )
        self.status_var.set("")

    def _render_fields(self):
        for w in self.fields_frame.winfo_children():
            w.destroy()

        is_signup = self.mode.get() == "signup"

        if is_signup:
            label(self.fields_frame, "Username").pack(anchor="w", pady=(0, 4))
            self.entry_username = styled_entry(self.fields_frame)
            self.entry_username.pack(fill="x", ipady=6, pady=(0, 12))

        label(self.fields_frame, "Email").pack(anchor="w", pady=(0, 4))
        self.entry_email = styled_entry(self.fields_frame)
        self.entry_email.pack(fill="x", ipady=6, pady=(0, 12))

        label(self.fields_frame, "Password").pack(anchor="w", pady=(0, 4))
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
            relief="flat", font=FONT_SMALL, cursor="hand2", borderwidth=0,
            width=4
        )
        toggle_btn.pack(side="left", padx=(6, 0))

        # Bind enter key
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
                u_id, username = result
                self.app.show_main(u_id, username)
            else:
                self.status_var.set("Incorrect email or password.")

        else:  # signup
            username = self.entry_username.get().strip()
            if not username:
                self.status_var.set("Please fill in all fields.")
                return

            ok = attempt_signup(email, password, username)
            if not ok:
                self.status_var.set("That email is already registered.")
            else:
                result = attempt_login(email, password)
                if result:
                    u_id, username = result
                    self.app.show_main(u_id, username)


# ── Placeholder main screen ───────────────────────────────────────────────────

class MainScreen(tk.Frame):
    def __init__(self, app: App, u_id, username):
        super().__init__(app, bg=BG)
        self.app = app
        self.pack(fill="both", expand=True)

        tk.Label(self, text=f"@{username}",
                 font=FONT_TITLE, bg=BG, fg=TEXT).pack(pady=(80, 8))
        tk.Label(self, text="main screen coming soon",
                 font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack()

        styled_button(self, "Log out", app.show_auth,
                      color="#2e2e2e", hover="#3e3e3e").pack(pady=32, ipadx=20)


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().mainloop()