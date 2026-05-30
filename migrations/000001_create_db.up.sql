CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT UNIQUE,
  title TEXT,
  perex TEXT,
  content TEXT,
  category TEXT,
  timestamp INTEGER
);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE,
  city TEXT
);

CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  content TEXT,
  timestamp INTEGER,
  upvotes INTEGER DEFAULT 0,
  downvotes INTEGER DEFAULT 0,
  userId INTEGER NOT NULL REFERENCES users(id),
  articleId INTEGER NOT NULL REFERENCES articles(id),
  replyToId INTEGER REFERENCES comments(id),
  UNIQUE(content, timestamp, userId)
);

CREATE TABLE IF NOT EXISTS scrape_queue (
  url TEXT PRIMARY KEY,
  type TEXT CHECK (type IN ('archive_day', 'article', 'discussion', 'user_profile')) NOT NULL, 
  status TEXT CHECK (status IN ('pending', 'processing', 'done', 'failed')) DEFAULT 'pending' NOT NULL
);
