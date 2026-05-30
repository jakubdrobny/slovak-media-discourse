ALTER TABLE comments ADD COLUMN platformId TEXT;
ALTER TABLE comments ADD COLUMN platformParentId TEXT;
CREATE UNIQUE INDEX idx_platform_id ON comments(platformId);
