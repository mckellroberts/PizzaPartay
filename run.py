import sys
from pizzaparty.app import App
from pizzaparty.db import get_conn


def resolve_users():
    """Return list of (u_id, username) for all --Name args, in order."""
    users = []
    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            username = arg[2:]
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT u_id, username FROM Users "
                    "WHERE username = ? AND is_deleted = 0",
                    (username,)
                ).fetchone()
            if row:
                users.append(row)
            else:
                print(f"No active user '{username}' found in DB.")
                sys.exit(1)
    return users


if __name__ == "__main__":
    App(auto_login=resolve_users()).mainloop()
