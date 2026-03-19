CREATE TABLE IF NOT EXISTS Users (
    u_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email_address   TEXT    NOT NULL UNIQUE,
    password        TEXT    NOT NULL,
    username        TEXT    NOT NULL,
    is_deleted      INTEGER NOT NULL DEFAULT 0,
    total_followers INTEGER NOT NULL DEFAULT 0,
    total_follows   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Posts (
    post_id       INTEGER  PRIMARY KEY AUTOINCREMENT,
    u_id          INTEGER  NOT NULL REFERENCES Users(u_id),
    content       TEXT     NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    been_edited   INTEGER  NOT NULL DEFAULT 0,
    is_deleted    INTEGER  NOT NULL DEFAULT 0,
    is_archived   INTEGER  NOT NULL DEFAULT 0,
    is_private    INTEGER  NOT NULL DEFAULT 0,
    like_count    INTEGER  NOT NULL DEFAULT 0,
    dlike_count   INTEGER  NOT NULL DEFAULT 0,
    comment_count INTEGER  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Comments (
    parent_c_id   INTEGER  DEFAULT NULL,
    comment_id    INTEGER  PRIMARY KEY AUTOINCREMENT,
    post_id       INTEGER  NOT NULL REFERENCES Posts(post_id),
    u_id          INTEGER  NOT NULL REFERENCES Users(u_id),
    content       TEXT     NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    been_edited   INTEGER  NOT NULL DEFAULT 0,
    is_deleted    INTEGER  NOT NULL DEFAULT 0,
    like_count    INTEGER  NOT NULL DEFAULT 0,
    dlike_count   INTEGER  NOT NULL DEFAULT 0,
    comment_count INTEGER  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Posts_ledger (
    post_id  INTEGER NOT NULL REFERENCES Posts(post_id),
    u_id     INTEGER NOT NULL REFERENCES Users(u_id),
    is_like  INTEGER NOT NULL DEFAULT 0,
    is_dlike INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (post_id, u_id),
    CHECK (NOT (is_like = 1 AND is_dlike = 1))
);

CREATE TABLE IF NOT EXISTS Comments_ledger (
    comment_id INTEGER NOT NULL REFERENCES Comments(comment_id),
    u_id       INTEGER NOT NULL REFERENCES Users(u_id),
    is_like    INTEGER NOT NULL DEFAULT 0,
    is_dlike   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (comment_id, u_id),
    CHECK (NOT (is_like = 1 AND is_dlike = 1))
);

CREATE TABLE IF NOT EXISTS Follows_ledger (
    follower_u_id INTEGER NOT NULL REFERENCES Users(u_id),
    follows_u_id  INTEGER NOT NULL REFERENCES Users(u_id),
    PRIMARY KEY (follower_u_id, follows_u_id),
    CHECK (follower_u_id != follows_u_id)
);

CREATE TABLE IF NOT EXISTS Blocked_ledger (
    blocker_u_id INTEGER NOT NULL REFERENCES Users(u_id),
    blocks_u_id  INTEGER NOT NULL REFERENCES Users(u_id),
    PRIMARY KEY (blocker_u_id, blocks_u_id),
    CHECK (blocker_u_id != blocks_u_id)
);

CREATE TABLE IF NOT EXISTS Active_sessions (
    u_id      INTEGER PRIMARY KEY REFERENCES Users(u_id),
    last_used DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
