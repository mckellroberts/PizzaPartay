import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "PizzaParty.db"))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    """Belt-and-suspenders: ensure Active_sessions exists at GUI startup."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Active_sessions (
                u_id      INTEGER PRIMARY KEY REFERENCES Users(u_id),
                last_used DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

# ── Sessions ──────────────────────────────────────────────────────────────────

def save_session(u_id: int):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO Active_sessions (u_id, last_used)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(u_id) DO UPDATE SET last_used = CURRENT_TIMESTAMP
        """, (u_id,))
        conn.execute("""
            DELETE FROM Active_sessions
            WHERE u_id NOT IN (
                SELECT u_id FROM Active_sessions
                ORDER BY last_used DESC LIMIT 20
            )
        """)

def get_sessions():
    with get_conn() as conn:
        return conn.execute("""
            SELECT s.u_id, u.username, u.is_deleted, s.last_used
            FROM   Active_sessions s
            JOIN   Users u ON u.u_id = s.u_id
            ORDER  BY s.last_used DESC
        """).fetchall()

def remove_session(u_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM Active_sessions WHERE u_id = ?", (u_id,))

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
              AND  (p.is_private = 0 OR p.u_id = ?)
            ORDER  BY p.created_at DESC
        """, (viewer_u_id, profile_u_id, viewer_u_id)).fetchall()

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
            SELECT p.post_id, u.username, p.content, p.created_at, p.been_edited
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
