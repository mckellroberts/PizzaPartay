-- Speeds up fetching all posts/comments by a user
CREATE INDEX idx_posts_u_id         ON Posts(u_id);
CREATE INDEX idx_comments_u_id      ON Comments(u_id);

-- Speeds up fetching all comments on a post
CREATE INDEX idx_comments_post_id   ON Comments(post_id);

-- Speeds up threaded comment lookups
CREATE INDEX idx_comments_parent    ON Comments(parent_c_id);

-- Speeds up ledger lookups triggered by post/comment interactions
-- (the trigger WHERE clauses hit these)
CREATE INDEX idx_pl_post_id         ON Posts_ledger(post_id);
CREATE INDEX idx_cl_comment_id      ON Comments_ledger(comment_id);

-- Speeds up "who follows me" and "who do I follow" queries
-- (also used by the follow triggers)
CREATE INDEX idx_fl_follows_u_id    ON Follows_ledger(follows_u_id);
CREATE INDEX idx_fl_follower_u_id   ON Follows_ledger(follower_u_id);

-- Speeds up block-checking (which you'll likely do on every feed query)
CREATE INDEX idx_bl_blocker         ON Blocked_ledger(blocker_u_id);
CREATE INDEX idx_bl_blocked         ON Blocked_ledger(blocks_u_id);
