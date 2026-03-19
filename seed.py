import os
import sys
import sqlite3

from pizzaparty.db import (
    DB_PATH, create_user, follow, block,
    create_post, edit_post, delete_post, archive_post,
    like_post, dislike_post, remove_post_reaction,
    create_comment, edit_comment, delete_comment,
    like_comment, dislike_comment,
    create_notification,
)

SQL_DIR = os.path.join(os.path.dirname(__file__), "pizzaparty", "sql")


def init_schema():
    conn = sqlite3.connect(DB_PATH)
    try:
        for fname in ("pp_creation.sql", "pp_indices.sql", "pp_triggers.sql"):
            with open(os.path.join(SQL_DIR, fname)) as f:
                conn.executescript(f.read())
    except Exception:
        conn.close()
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        raise
    conn.close()


def seed():
    try:
        # Users
        alice = create_user("alice@example.com", "password123", "Alice")
        bob   = create_user("bob@example.com",   "hunter2",     "Bob")
        carol = create_user("carol@example.com", "letmein",     "Carol")
        dave  = create_user("dave@example.com",  "qwerty",      "Dave")
        eve   = create_user("eve@example.com",   "abc123",      "Eve")
        frank = create_user("frank@example.com", "iloveyou",    "Frank")
        greg  = create_user("greg@example.com",  "ilikefish",   "Greg")

        # Follows
        follow(alice, bob);   follow(alice, carol)
        follow(bob,   alice); follow(bob,   carol); follow(bob,   dave)
        follow(carol, alice)
        follow(dave,  alice); follow(dave,  eve)
        follow(eve,   alice); follow(eve,   bob);   follow(eve,   carol)
        follow(frank, alice)

        # Blocks
        block(alice, frank)
        block(dave,  eve)

        # Posts
        p1  = create_post(alice, "Just joined this platform, hello everyone!")
        p2  = create_post(alice, "Hot take: pineapple on pizza is actually fine.")
        p3  = create_post(bob,   "Finished a 10k this morning. Feeling great.")
        p4  = create_post(bob,   "Does anyone actually read the terms and conditions?")
        p5  = create_post(carol, "Unpopular opinion: dark mode is overrated.")
        p6  = create_post(carol, "This post is getting archived.")
        p7  = create_post(dave,  "Working on something exciting. Stay tuned.")
        p8  = create_post(dave,  "This is a private post, just for me.", is_private=1)
        p9  = create_post(eve,   "Reminder: drink water and go outside.")
        p10 = create_post(frank, "I will regret posting this.")

        archive_post(p6)
        edit_post(p9, "Reminder: drink water, go outside, and touch grass.")
        delete_post(p10)

        # Post reactions
        like_post(p1, bob);    like_post(p1, carol);   like_post(p1, dave)
        dislike_post(p2, bob); like_post(p2, carol);   like_post(p2, eve)
        like_post(p3, alice);  like_post(p3, carol)
        like_post(p4, alice);  dislike_post(p4, eve)
        dislike_post(p5, alice); dislike_post(p5, bob); like_post(p5, dave)
        like_post(p7, alice);  like_post(p7, bob);     like_post(p7, carol); like_post(p7, eve)
        like_post(p9, alice);  like_post(p9, bob);     like_post(p9, carol)

        # A changed mind
        dislike_post(p3, carol)
        remove_post_reaction(p3, alice)

        # Comments
        c1 = create_comment(p2, bob,   "Hard disagree, it ruins the whole pizza.")
        c2 = create_comment(p2, carol, "I'm with Alice on this one, it's a valid topping.")
        c3 = create_comment(p3, alice, "Amazing! What's your target for next time?")
        c4 = create_comment(p5, dave,  "Wait till you try it on a light background at 3am.")
        c5 = create_comment(p9, carol, "Needed this reminder, thank you!")

        # Replies
        create_comment(p2, alice, "Bold of you to be wrong on the internet, Bob.",  parent_c_id=c1)
        c1r2 = create_comment(p2, eve,   "I also disagree with Bob, sorry.",        parent_c_id=c1)
        c3r1 = create_comment(p3, bob,   "Aiming for sub-50 minutes next month!",   parent_c_id=c3)

        edit_comment(c4, "Wait till you try it on a light background at 3am. Game changer.")
        delete_comment(c2, p2, None)

        # Comment reactions
        dislike_comment(c1,   alice); dislike_comment(c1,   carol)
        dislike_comment(c1r2, bob)
        like_comment(c3,   bob);      like_comment(c3,   carol)
        like_comment(c3r1, alice);    like_comment(c3r1, carol)
        like_comment(c5,   alice);    like_comment(c5,   bob)

        # Notifications (follow, like, reply)
        create_notification(alice, "follow", bob)
        create_notification(alice, "follow", carol)
        create_notification(alice, "follow", dave)
        create_notification(alice, "follow", eve)
        create_notification(alice, "like",   bob,   post_id=p1)
        create_notification(alice, "like",   carol, post_id=p1)
        create_notification(alice, "like",   dave,  post_id=p1)
        create_notification(bob,   "follow", alice)
        create_notification(bob,   "follow", carol)
        create_notification(bob,   "like",   alice, post_id=p3)
        create_notification(bob,   "reply",  alice, post_id=p2)
        create_notification(carol, "follow", alice)
        create_notification(carol, "like",   bob,   post_id=p3)
        create_notification(dave,  "follow", alice)
        create_notification(dave,  "like",   alice, post_id=p7)
        create_notification(dave,  "like",   bob,   post_id=p7)
        create_notification(dave,  "like",   carol, post_id=p7)

    except Exception:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        raise


if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        print(f"DB already exists at {DB_PATH}.")
        if "--force" not in sys.argv:
            print("Run with --force to drop and reseed.")
            sys.exit(1)
        os.remove(DB_PATH)
        print("Existing DB removed.")

    print("Creating schema...")
    init_schema()
    print("Seeding data...")
    seed()
    print("Done.")
