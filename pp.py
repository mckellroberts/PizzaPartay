import sqlite3
import hashlib

DB = "PizzaParty.db"

def get_connection():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    return con

# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(cur, email, password, username):
    cur.execute(
        "INSERT INTO Users (email_address, password, username) VALUES (?, ?, ?)",
        (email, password, username)
    )
    return cur.lastrowid

def delete_user(cur, u_id):
    cur.execute("UPDATE Users SET is_deleted = 1 WHERE u_id = ?", (u_id,))

# ── Follows ───────────────────────────────────────────────────────────────────

def follow(cur, follower_u_id, follows_u_id):
    cur.execute(
        "INSERT INTO Follows_ledger (follower_u_id, follows_u_id) VALUES (?, ?)",
        (follower_u_id, follows_u_id)
    )

def unfollow(cur, follower_u_id, follows_u_id):
    cur.execute(
        "DELETE FROM Follows_ledger WHERE follower_u_id = ? AND follows_u_id = ?",
        (follower_u_id, follows_u_id)
    )

# ── Blocks ────────────────────────────────────────────────────────────────────

def block(cur, blocker_u_id, blocks_u_id):
    cur.execute(
        "INSERT INTO Blocked_ledger (blocker_u_id, blocks_u_id) VALUES (?, ?)",
        (blocker_u_id, blocks_u_id)
    )

def unblock(cur, blocker_u_id, blocks_u_id):
    cur.execute(
        "DELETE FROM Blocked_ledger WHERE blocker_u_id = ? AND blocks_u_id = ?",
        (blocker_u_id, blocks_u_id)
    )

# ── Posts ─────────────────────────────────────────────────────────────────────

def create_post(cur, u_id, content, is_private=0):
    cur.execute(
        "INSERT INTO Posts (u_id, content, is_private) VALUES (?, ?, ?)",
        (u_id, content, is_private)
    )
    return cur.lastrowid

def edit_post(cur, post_id, new_content):
    cur.execute(
        "UPDATE Posts SET content = ?, been_edited = 1 WHERE post_id = ?",
        (new_content, post_id)
    )

def delete_post(cur, post_id):
    cur.execute("UPDATE Posts SET is_deleted = 1 WHERE post_id = ?", (post_id,))

def archive_post(cur, post_id):
    cur.execute("UPDATE Posts SET is_archived = 1 WHERE post_id = ?", (post_id,))

def like_post(cur, post_id, u_id):
    cur.execute(
        """INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike) VALUES (?, ?, 1, 0)
           ON CONFLICT(post_id, u_id) DO UPDATE SET is_like = 1, is_dlike = 0""",
        (post_id, u_id)
    )

def dislike_post(cur, post_id, u_id):
    cur.execute(
        """INSERT INTO Posts_ledger (post_id, u_id, is_like, is_dlike) VALUES (?, ?, 0, 1)
           ON CONFLICT(post_id, u_id) DO UPDATE SET is_like = 0, is_dlike = 1""",
        (post_id, u_id)
    )

def remove_post_reaction(cur, post_id, u_id):
    cur.execute(
        "DELETE FROM Posts_ledger WHERE post_id = ? AND u_id = ?",
        (post_id, u_id)
    )

# ── Comments ──────────────────────────────────────────────────────────────────

def create_comment(cur, post_id, u_id, content, parent_c_id=None):
    cur.execute(
        "INSERT INTO Comments (parent_c_id, post_id, u_id, content) VALUES (?, ?, ?, ?)",
        (parent_c_id, post_id, u_id, content)
    )
    comment_id = cur.lastrowid
    if parent_c_id:
        cur.execute(
            "UPDATE Comments SET comment_count = comment_count + 1 WHERE comment_id = ?",
            (parent_c_id,)
        )
    cur.execute(
        "UPDATE Posts SET comment_count = comment_count + 1 WHERE post_id = ?",
        (post_id,)
    )
    return comment_id

def edit_comment(cur, comment_id, new_content):
    cur.execute(
        "UPDATE Comments SET content = ?, been_edited = 1 WHERE comment_id = ?",
        (new_content, comment_id)
    )

def delete_comment(cur, comment_id):
    cur.execute(
        "UPDATE Comments SET is_deleted = 1 WHERE comment_id = ?",
        (comment_id,)
    )

def like_comment(cur, comment_id, u_id):
    cur.execute(
        """INSERT INTO Comments_ledger (comment_id, u_id, is_like, is_dlike) VALUES (?, ?, 1, 0)
           ON CONFLICT(comment_id, u_id) DO UPDATE SET is_like = 1, is_dlike = 0""",
        (comment_id, u_id)
    )

def dislike_comment(cur, comment_id, u_id):
    cur.execute(
        """INSERT INTO Comments_ledger (comment_id, u_id, is_like, is_dlike) VALUES (?, ?, 0, 1)
           ON CONFLICT(comment_id, u_id) DO UPDATE SET is_like = 0, is_dlike = 1""",
        (comment_id, u_id)
    )

def remove_comment_reaction(cur, comment_id, u_id):
    cur.execute(
        "DELETE FROM Comments_ledger WHERE comment_id = ? AND u_id = ?",
        (comment_id, u_id)
    )

# ── Seed ──────────────────────────────────────────────────────────────────────

def seed():
    con = get_connection()
    cur = con.cursor()

    # Users
    alice = create_user(cur, "alice@example.com", "password123", "Alice")
    bob   = create_user(cur, "bob@example.com",   "hunter2",     "Bob")
    carol = create_user(cur, "carol@example.com", "letmein",     "Carol")
    dave  = create_user(cur, "dave@example.com",  "qwerty",      "Dave")
    eve   = create_user(cur, "eve@example.com",   "abc123",      "Eve")
    frank = create_user(cur, "frank@example.com", "iloveyou",    "Frank")

    # Follows
    follow(cur, alice, bob);   follow(cur, alice, carol)
    follow(cur, bob,   alice); follow(cur, bob,   carol); follow(cur, bob, dave)
    follow(cur, carol, alice)
    follow(cur, dave,  alice); follow(cur, dave,  eve)
    follow(cur, eve,   alice); follow(cur, eve,   bob);   follow(cur, eve, carol)
    follow(cur, frank, alice)

    # Blocks
    block(cur, alice, frank)
    block(cur, dave,  eve)

    # Posts
    p1  = create_post(cur, alice, "Just joined this platform, hello everyone!")
    p2  = create_post(cur, alice, "Hot take: pineapple on pizza is actually fine.")
    p3  = create_post(cur, bob,   "Finished a 10k this morning. Feeling great.")
    p4  = create_post(cur, bob,   "Does anyone actually read the terms and conditions?")
    p5  = create_post(cur, carol, "Unpopular opinion: dark mode is overrated.")
    p6  = create_post(cur, carol, "This post is getting archived.")
    p7  = create_post(cur, dave,  "Working on something exciting. Stay tuned.")
    p8  = create_post(cur, dave,  "This is a private post, just for me.", is_private=1)
    p9  = create_post(cur, eve,   "Reminder: drink water and go outside.")
    p10 = create_post(cur, frank, "I will regret posting this.")

    archive_post(cur, p6)
    edit_post(cur, p9, "Reminder: drink water, go outside, and touch grass.")
    delete_post(cur, p10)

    # Post reactions
    like_post(cur, p1, bob);    like_post(cur, p1, carol);   like_post(cur, p1, dave)
    dislike_post(cur, p2, bob); like_post(cur, p2, carol);   like_post(cur, p2, eve)
    like_post(cur, p3, alice);  like_post(cur, p3, carol)
    like_post(cur, p4, alice);  dislike_post(cur, p4, eve)
    dislike_post(cur, p5, alice); dislike_post(cur, p5, bob); like_post(cur, p5, dave)
    like_post(cur, p7, alice);  like_post(cur, p7, bob);     like_post(cur, p7, carol); like_post(cur, p7, eve)
    like_post(cur, p9, alice);  like_post(cur, p9, bob);     like_post(cur, p9, carol)

    # A changed mind
    dislike_post(cur, p3, carol)
    remove_post_reaction(cur, p3, alice)

    # Comments
    c1 = create_comment(cur, p2, bob,   "Hard disagree, it ruins the whole pizza.")
    c2 = create_comment(cur, p2, carol, "I'm with Alice on this one, it's a valid topping.")
    c3 = create_comment(cur, p3, alice, "Amazing! What's your target for next time?")
    c4 = create_comment(cur, p5, dave,  "Wait till you try it on a light background at 3am.")
    c5 = create_comment(cur, p9, carol, "Needed this reminder, thank you!")

    # Replies
    c1r1 = create_comment(cur, p2, alice, "Bold of you to be wrong on the internet, Bob.",  parent_c_id=c1)
    c1r2 = create_comment(cur, p2, eve,   "I also disagree with Bob, sorry.",               parent_c_id=c1)
    c3r1 = create_comment(cur, p3, bob,   "Aiming for sub-50 minutes next month!",          parent_c_id=c3)

    edit_comment(cur, c4, "Wait till you try it on a light background at 3am. Game changer.")
    delete_comment(cur, c2)

    # Comment reactions
    dislike_comment(cur, c1,   alice); dislike_comment(cur, c1,   carol)
    dislike_comment(cur, c1r1, bob)
    like_comment(cur, c3,   bob);     like_comment(cur, c3,   carol)
    like_comment(cur, c3r1, alice);   like_comment(cur, c3r1, carol)
    like_comment(cur, c5,   alice);   like_comment(cur, c5,   bob)

    con.commit()
    con.close()
    print("Database seeded successfully.")

if __name__ == "__main__":
    seed()