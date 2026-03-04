-- Posts_ledger triggers

CREATE TRIGGER ledger_p_insert
AFTER INSERT ON Posts_ledger BEGIN
    UPDATE Posts SET
        like_count  = like_count  + new.is_like,
        dlike_count = dlike_count + new.is_dlike
    WHERE post_id = new.post_id;
END;

CREATE TRIGGER ledger_p_update
AFTER UPDATE ON Posts_ledger BEGIN
    UPDATE Posts SET
        like_count  = like_count  + (new.is_like  - old.is_like),
        dlike_count = dlike_count + (new.is_dlike - old.is_dlike)
    WHERE post_id = new.post_id;
END;

CREATE TRIGGER ledger_p_delete
AFTER DELETE ON Posts_ledger BEGIN
    UPDATE Posts SET
        like_count  = like_count  - old.is_like,
        dlike_count = dlike_count - old.is_dlike
    WHERE post_id = old.post_id;
END;

-- Comments_ledger triggers

CREATE TRIGGER ledger_c_insert
AFTER INSERT ON Comments_ledger BEGIN
    UPDATE Comments SET
        like_count  = like_count  + new.is_like,
        dlike_count = dlike_count + new.is_dlike
    WHERE (post_id = new.post_id) AND (comment_id = new.comment_id);
END;

CREATE TRIGGER ledger_c_update
AFTER UPDATE ON Comments_ledger BEGIN
    UPDATE Comments SET
        like_count  = like_count  + (new.is_like  - old.is_like),
        dlike_count = dlike_count + (new.is_dlike - old.is_dlike)
    WHERE (post_id = new.post_id) AND (comment_id = new.comment_id);
END;

CREATE TRIGGER ledger_c_delete
AFTER DELETE ON Comments_ledger BEGIN
    UPDATE Comments SET
        like_count  = like_count  - old.is_like,
        dlike_count = dlike_count - old.is_dlike
    WHERE (post_id = new.post_id) AND (comment_id = new.comment_id);
END;

-- Follows_ledger triggers

CREATE TRIGGER ledger_f_insert
AFTER INSERT ON Follows_ledger BEGIN
    UPDATE Users SET
        total_followers = total_followers + 1
    WHERE u_id = new.follows_u_id;
    UPDATE Users SET
        total_follows = total_follows + 1
    WHERE u_id = new.follower_u_id;
END;

CREATE TRIGGER ledger_f_delete
AFTER DELETE ON Follows_ledger BEGIN
    UPDATE Users SET
        total_followers = total_followers - 1
    WHERE u_id = old.follows_u_id;
    UPDATE Users SET
        total_follows = total_follows - 1
    WHERE u_id = old.follower_u_id;
END;
