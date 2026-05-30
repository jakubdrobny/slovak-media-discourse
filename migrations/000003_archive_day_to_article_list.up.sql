PRAGMA foreign_keys=off;
BEGIN TRANSACTION;

CREATE TABLE scrape_queue_new (
  url TEXT PRIMARY KEY,
  type TEXT CHECK (type IN ('article_list', 'article', 'discussion', 'user_profile')) NOT NULL, 
  status TEXT CHECK (status IN ('pending', 'processing', 'done', 'failed')) DEFAULT 'pending' NOT NULL
);

INSERT INTO scrape_queue_new (url, type, status)
SELECT 
    url, 
    CASE WHEN type = 'archive_day' THEN 'article_list' ELSE type END, 
    status 
FROM scrape_queue;

DROP TABLE scrape_queue;
ALTER TABLE scrape_queue_new RENAME TO scrape_queue;

COMMIT;
PRAGMA foreign_keys=on;
