# Pizza Party

A social media desktop app built with Python/tkinter and SQLite.

## Requirements

Python 3.7+ with tkinter (standard library).

## Setup

```bash
python seed.py          # create DB and load test data
python run.py           # open the app
```

To wipe and reseed:

```bash
python seed.py --force
```

## Test accounts

| Username | Email | Password |
|---|---|---|
| Alice | alice@example.com | password123 |
| Bob | bob@example.com | hunter2 |
| Carol | carol@example.com | letmein |
| Dave | dave@example.com | qwerty |
| Eve | eve@example.com | abc123 |

## Project layout

```
run.py          entry point — opens the GUI
seed.py         entry point — creates and seeds the DB
pizzaparty/
    db.py       database layer
    theme.py    colors, fonts, widget factories
    app.py      app shell and screen management
    screens.py  auth, feed, and profile screens
    panels.py   comments panel, account switcher, post cards
    sql/        schema, indices, and trigger definitions
```
