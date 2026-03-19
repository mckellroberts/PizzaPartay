# Pizza Party

A social media desktop application built with Python, tkinter, and SQLite.
No third-party libraries required — see [DEPENDENCIES.md](DEPENDENCIES.md).

---

## Setup

```bash
python seed.py      # create the database and load test data
python run.py       # launch the app
```

To wipe and reseed from scratch:

```bash
python seed.py --force
```

---

## Test accounts

| Username | Email | Password |
|---|---|---|
| Alice | alice@example.com | password123 |
| Bob | bob@example.com | hunter2 |
| Carol | carol@example.com | letmein |
| Dave | dave@example.com | qwerty |
| Eve | eve@example.com | abc123 |

---

## Database schema

### Tables

| Table | Kind | Description |
|---|---|---|
| `Users` | entity | Accounts with email, password, username, soft-delete flag, and cached follower/following counts |
| `Posts` | entity | User posts with content, timestamps, privacy/archive/delete flags, and cached reaction counts |
| `Comments` | entity | Threaded comments on posts; supports replies via `parent_c_id` |
| `Notifications` | entity | Records follow, like, and reply events directed at a user |
| `Posts_ledger` | join | One row per (user, post) reaction; enforces mutual exclusion of like and dislike |
| `Comments_ledger` | join | One row per (user, comment) reaction; same mutual-exclusion constraint |
| `Follows_ledger` | join | One row per follow relationship; self-follow prevented by CHECK constraint |
| `Blocked_ledger` | join | One row per block relationship |

### Triggers

Six triggers keep the cached counts on `Posts`, `Comments`, and `Users` consistent without requiring application-level bookkeeping:

- `ledger_p_insert / ledger_p_update / ledger_p_delete` — maintain `Posts.like_count` and `Posts.dlike_count`
- `ledger_c_insert / ledger_c_update / ledger_c_delete` — maintain `Comments.like_count` and `Comments.dlike_count`
- `ledger_f_insert / ledger_f_delete` — maintain `Users.total_followers` and `Users.total_follows`

### Indexes

Eight indexes cover the most common lookup patterns: posts and comments by user, comments by post, threaded comment lookups, ledger lookups by post/comment, and follower/following lookups.

---

## Features

### Authentication
- Sign up with username, email, and password
- Log in / log out
- Multi-account support with a session switcher (click the ▾ chevron next to your username)

### Posts
- Create posts (up to 280 characters) with an optional private flag
- Edit and delete your own posts (soft-delete)
- Archive posts (removes them from your feed without deleting)
- Toggle a post between public and private from your profile
- Like or dislike any post; reactions are mutually exclusive and togglable

### Feed (For You tab)
- Shows public posts from accounts you follow
- Ranked by an engagement + recency score: `(likes + 1) / (age_hours + 2)^1.8`

### Comments
- Comment on any post from the floating comments panel
- Threaded replies (one level of nesting)
- Edit and delete your own comments
- Like or dislike any comment

### Profiles
- Click any username or avatar (in the feed, comments panel, or Discover tab) to open that user's profile
- Profile shows avatar, follower/following/post counts, and all public posts
- **Followers** and **Following** counts are buttons — click to browse the full list with follow/unfollow controls
- Your own profile has a Private tab showing only your private posts
- Follow or unfollow any user directly from their profile page

### Discover tab
**Suggested Follows** — accounts you don't follow whose follower-bases overlap most with your own follows (self-join on `Follows_ledger`, ranked by mutual-follower count).

**Going Viral** — public posts liked by people you follow, from accounts you don't follow yet (multi-join across `Posts`, `Posts_ledger`, and `Follows_ledger`).

Both sections show follow/unfollow buttons and clickable names.

### Top tab
Most-liked public posts from the **last 48 hours**, globally. Full post cards with live like/dislike and comment access.

### Social graph
- Follow and unfollow any user
- Block and unblock (blocked users' posts are excluded from your feed)

### Notifications
The `Notifications` table records follow, like, and reply events. Seeded with realistic data so the table is populated from the first run.

---

## Interesting queries

Two non-trivial analytical queries are implemented in `pizzaparty/db.py`.

### Query 1 — Suggested follows (`get_suggested_follows`)

Finds accounts you don't follow whose follower-bases overlap most with your own, using a self-join on `Follows_ledger`.

```sql
SELECT f2.follower_u_id, u.username, COUNT(*) AS overlap
FROM   Follows_ledger f1
JOIN   Follows_ledger f2 ON f2.follows_u_id = f1.follows_u_id
JOIN   Users u ON u.u_id = f2.follower_u_id
WHERE  f1.follower_u_id = ?
  AND  f2.follower_u_id != ?
  AND  f2.follower_u_id NOT IN (
           SELECT follows_u_id FROM Follows_ledger WHERE follower_u_id = ?)
  AND  u.is_deleted = 0
GROUP  BY f2.follower_u_id
ORDER  BY overlap DESC
LIMIT  10;
```

**How to exercise it in the UI:**
1. `python seed.py --force && python run.py`
2. Log in as **Alice** — click **Discover** — ranked suggestions appear.

**How to exercise it from Python:**
```python
from pizzaparty import db
for row in db.get_suggested_follows(1):   # Alice is u_id 1
    print(row)
```

### Query 2 — Going viral (`get_viral_posts`)

Finds public posts liked by people you follow, from accounts you don't follow — posts spreading through your extended network.

```sql
SELECT p.post_id, p.u_id, u.username, p.content, p.like_count,
       COUNT(pl.u_id) AS liked_by_follows
FROM   Posts p
JOIN   Users u ON u.u_id = p.u_id
JOIN   Posts_ledger pl ON pl.post_id = p.post_id AND pl.is_like = 1
JOIN   Follows_ledger f ON f.follows_u_id = pl.u_id
                       AND f.follower_u_id = ?
WHERE  p.u_id NOT IN (
           SELECT follows_u_id FROM Follows_ledger WHERE follower_u_id = ?)
  AND  p.u_id != ?
  AND  p.is_deleted = 0 AND p.is_private = 0
GROUP  BY p.post_id
ORDER  BY liked_by_follows DESC, p.like_count DESC
LIMIT  20;
```

**How to exercise it in the UI:**
1. Log in as **Alice** — click **Discover** — scroll past suggested follows.
2. Try as **Bob** (`bob@example.com` / `hunter2`) for a different result set.

**How to exercise it from Python:**
```python
from pizzaparty import db
for row in db.get_viral_posts(1):
    print(row)
```

### Additional queries (basic)

All basic CRUD queries are in `pizzaparty/db.py`. Key examples:

| Function | Query type | Description |
|---|---|---|
| `get_feed_posts(u_id)` | SELECT + JOIN | Posts from followed accounts, scored in Python |
| `get_user_posts(profile_u_id, viewer_u_id)` | SELECT + JOIN | Public posts for a profile page |
| `get_post_comments(post_id, viewer_u_id)` | SELECT + LEFT JOIN | All comments on a post with viewer's reactions |
| `get_followers(u_id)` / `get_following(u_id)` | SELECT + JOIN | Follower and following lists |
| `toggle_post_reaction(post_id, u_id, kind)` | INSERT … ON CONFLICT | Upsert like/dislike with mutual exclusion |
| `get_top_posts(u_id)` | SELECT + LEFT JOIN | Most-liked posts in the last 48 hours |

---

## Project layout

```
run.py              entry point — launches the GUI
seed.py             entry point — creates schema and seeds test data
DEPENDENCIES.md     full dependency list (all standard library)
pizzaparty/
    db.py           all database queries and session management
    app.py          app shell, window management, screen routing
    screens.py      auth, main feed, profile, discover, top, user list
    panels.py       comments panel, post cards, account switcher
    theme.py        colors, fonts, and widget factory functions
    sql/
        pp_creation.sql   table definitions
        pp_indices.sql    index definitions
        pp_triggers.sql   trigger definitions
```
