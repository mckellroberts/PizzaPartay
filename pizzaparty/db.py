import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "PizzaParty.db"))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ── Sessions (in-memory) ──────────────────────────────────────────────────────

_sessions: list = []  # list of u_id ints, most-recent first, max 20

def save_session(u_id: int):
    global _sessions
    _sessions = [uid for uid in _sessions if uid != u_id]
    _sessions.insert(0, u_id)
    if len(_sessions) > 20:
        _sessions = _sessions[:20]

def get_sessions():
    """Returns list of (u_id, username, is_deleted) tuples."""
    if not _sessions:
        return []
    with get_conn() as conn:
        placeholders = ",".join("?" * len(_sessions))
        rows = conn.execute(
            f"SELECT u_id, username, is_deleted FROM Users WHERE u_id IN ({placeholders})",
            _sessions
        ).fetchall()
    by_id = {row[0]: row for row in rows}
    return [by_id[uid] for uid in _sessions if uid in by_id]

def remove_session(u_id: int):
    global _sessions
    _sessions = [uid for uid in _sessions if uid != u_id]

def clear_sessions():
    global _sessions
    _sessions = []

# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(email: str, password: str, username: str) -> int:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Users (email_address, password, username) VALUES (?, ?, ?)",
            (email, password, username)
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def delete_user(u_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE Users SET is_deleted = 1 WHERE u_id = ?", (u_id,))

def attempt_login(email: str, password: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT u_id, username FROM Users "
            "WHERE email_address = ? AND password = ? AND is_deleted = 0",
            (email, password)
        ).fetchone()

def attempt_signup(email: str, password: str, username: str) -> bool:
    try:
        create_user(email, password, username)
        return True
    except sqlite3.IntegrityError:
        return False

# ── Social ────────────────────────────────────────────────────────────────────

def follow(follower_u_id: int, follows_u_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Follows_ledger (follower_u_id, follows_u_id) VALUES (?, ?)",
            (follower_u_id, follows_u_id)
        )

def unfollow(follower_u_id: int, follows_u_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM Follows_ledger WHERE follower_u_id = ? AND follows_u_id = ?",
            (follower_u_id, follows_u_id)
        )

def get_followers(u_id: int):
    """Returns (u_id, username) for every user that follows u_id."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT u.u_id, u.username
            FROM   Follows_ledger f
            JOIN   Users u ON u.u_id = f.follower_u_id
            WHERE  f.follows_u_id = ? AND u.is_deleted = 0
            ORDER  BY u.username
        """, (u_id,)).fetchall()

def get_following(u_id: int):
    """Returns (u_id, username) for every user that u_id follows."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT u.u_id, u.username
            FROM   Follows_ledger f
            JOIN   Users u ON u.u_id = f.follows_u_id
            WHERE  f.follower_u_id = ? AND u.is_deleted = 0
            ORDER  BY u.username
        """, (u_id,)).fetchall()

def is_following(follower_u_id: int, follows_u_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM Follows_ledger WHERE follower_u_id = ? AND follows_u_id = ?",
            (follower_u_id, follows_u_id)
        ).fetchone() is not None

def block(blocker_u_id: int, blocks_u_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Blocked_ledger (blocker_u_id, blocks_u_id) VALUES (?, ?)",
            (blocker_u_id, blocks_u_id)
        )

def unblock(blocker_u_id: int, blocks_u_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM Blocked_ledger WHERE blocker_u_id = ? AND blocks_u_id = ?",
            (blocker_u_id, blocks_u_id)
        )

# ── Feed ──────────────────────────────────────────────────────────────────────

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

# ── Profile ───────────────────────────────────────────────────────────────────

def get_profile(u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT u.username, u.total_followers, u.total_follows, COUNT(p.post_id)
            FROM   Users u
            LEFT JOIN Posts p ON p.u_id = u.u_id AND p.is_deleted = 0 AND p.is_archived = 0
            WHERE  u.u_id = ?
            GROUP  BY u.u_id
        """, (u_id,)).fetchone()

def get_private_posts(u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.post_id, p.u_id, u.username, p.content, p.created_at,
                   p.like_count, p.dlike_count, p.comment_count, p.been_edited,
                   COALESCE(pl.is_like,  0),
                   COALESCE(pl.is_dlike, 0),
                   p.is_private
            FROM   Posts p
            JOIN   Users u ON p.u_id = u.u_id
            LEFT JOIN Posts_ledger pl ON p.post_id = pl.post_id AND pl.u_id = ?
            WHERE  p.u_id = ? AND p.is_private = 1
              AND  p.is_deleted = 0 AND p.is_archived = 0
            ORDER  BY p.created_at DESC
        """, (u_id, u_id)).fetchall()

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
              AND  p.is_private = 0
            ORDER  BY p.created_at DESC
        """, (viewer_u_id, profile_u_id)).fetchall()

# ── Posts ─────────────────────────────────────────────────────────────────────

def create_post(u_id: int, content: str, is_private: int = 0) -> int:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Posts (u_id, content, is_private) VALUES (?, ?, ?)",
            (u_id, content, is_private)
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def edit_post(post_id: int, new_content: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE Posts SET content = ?, been_edited = 1 WHERE post_id = ?",
            (new_content, post_id)
        )

def delete_post(post_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE Posts SET is_deleted = 1 WHERE post_id = ?", (post_id,))

def archive_post(post_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE Posts SET is_archived = 1 WHERE post_id = ?", (post_id,))

def toggle_post_privacy(post_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE Posts SET is_private = 1 - is_private WHERE post_id = ?", (post_id,)
        )

def like_post(post_id: int, u_id: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike) VALUES (?, ?, 1, 0)
               ON CONFLICT(post_id, u_id) DO UPDATE SET is_like = 1, is_dlike = 0""",
            (post_id, u_id)
        )

def dislike_post(post_id: int, u_id: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike) VALUES (?, ?, 0, 1)
               ON CONFLICT(post_id, u_id) DO UPDATE SET is_like = 0, is_dlike = 1""",
            (post_id, u_id)
        )

def remove_post_reaction(post_id: int, u_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM Posts_ledger WHERE post_id = ? AND u_id = ?",
            (post_id, u_id)
        )

# ── Comments ──────────────────────────────────────────────────────────────────

def get_post_header(post_id: int, viewer_u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.post_id, p.u_id, u.username, p.content, p.created_at, p.been_edited
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

def create_comment(post_id: int, u_id: int, content: str, parent_c_id=None) -> int:
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

def like_comment(comment_id: int, u_id: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO Comments_ledger (comment_id, u_id, is_like, is_dlike) VALUES (?, ?, 1, 0)
               ON CONFLICT(comment_id, u_id) DO UPDATE SET is_like = 1, is_dlike = 0""",
            (comment_id, u_id)
        )

def dislike_comment(comment_id: int, u_id: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO Comments_ledger (comment_id, u_id, is_like, is_dlike) VALUES (?, ?, 0, 1)
               ON CONFLICT(comment_id, u_id) DO UPDATE SET is_like = 0, is_dlike = 1""",
            (comment_id, u_id)
        )

def remove_comment_reaction(comment_id: int, u_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM Comments_ledger WHERE comment_id = ? AND u_id = ?",
            (comment_id, u_id)
        )

# ── Notifications ─────────────────────────────────────────────────────────────

def create_notification(u_id: int, kind: str, from_u_id: int, post_id=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO Notifications (u_id, kind, from_u_id, post_id) VALUES (?, ?, ?, ?)",
            (u_id, kind, from_u_id, post_id)
        )

def get_notifications(u_id: int):
    with get_conn() as conn:
        return conn.execute("""
            SELECT n.notif_id, n.kind, n.from_u_id, u.username,
                   n.post_id, n.created_at, n.is_read
            FROM   Notifications n
            JOIN   Users u ON u.u_id = n.from_u_id
            WHERE  n.u_id = ?
            ORDER  BY n.created_at DESC
            LIMIT  50
        """, (u_id,)).fetchall()

def mark_notifications_read(u_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE Notifications SET is_read = 1 WHERE u_id = ?", (u_id,)
        )

# ── Interesting queries ───────────────────────────────────────────────────────

def get_suggested_follows(u_id: int):
    """Accounts you don't follow whose follower-base overlaps most with yours."""
    with get_conn() as conn:
        return conn.execute("""
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
            LIMIT  10
        """, (u_id, u_id, u_id)).fetchall()

def get_viral_posts(u_id: int):
    """Public posts liked by people you follow, from accounts you don't follow."""
    with get_conn() as conn:
        return conn.execute("""
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
            LIMIT  20
        """, (u_id, u_id, u_id)).fetchall()

def get_top_posts(u_id: int):
    """Most-liked public posts from the last 48 hours."""
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.post_id, p.u_id, u.username, p.content, p.created_at,
                   p.like_count, p.dlike_count, p.comment_count, p.been_edited,
                   COALESCE(pl.is_like,  0),
                   COALESCE(pl.is_dlike, 0)
            FROM   Posts p
            JOIN   Users u ON u.u_id = p.u_id
            LEFT JOIN Posts_ledger pl ON pl.post_id = p.post_id AND pl.u_id = ?
            WHERE  p.is_deleted = 0 AND p.is_private = 0 AND p.is_archived = 0
              AND  u.is_deleted = 0
              AND  p.created_at >= datetime('now', '-48 hours')
            ORDER  BY p.like_count DESC, p.comment_count DESC
            LIMIT  30
        """, (u_id,)).fetchall()
