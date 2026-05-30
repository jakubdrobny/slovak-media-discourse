ALTER TABLE comments ADD COLUMN sentiment TEXT;
ALTER TABLE comments ADD COLUMN sentiment_score REAL;

ALTER TABLE articles ADD COLUMN sentiment TEXT;
ALTER TABLE articles ADD COLUMN sentiment_score REAL;
