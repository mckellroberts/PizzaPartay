# Dependencies

Pizza Party has **no third-party dependencies**. Everything it uses ships with Python.

## Runtime

| Package | Source | Purpose |
|---|---|---|
| `tkinter` | Python standard library | GUI framework |
| `sqlite3` | Python standard library | Database driver |
| `os` | Python standard library | File path handling |
| `sys` | Python standard library | CLI arguments (`--force`) |
| `datetime` | Python standard library | Feed scoring, age formatting |

## Python version

Python **3.7 or later** is required.
`tkinter` is included in most Python distributions. On some Linux systems it must be installed separately:

```bash
# Debian / Ubuntu
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

On macOS and Windows, `tkinter` is bundled with the official Python installer from python.org.

## Database

SQLite **3.35 or later** is recommended (ships inside Python's `sqlite3` module).
No external database server is required — the database is a single file (`PizzaParty.db`) created automatically by `seed.py`.
