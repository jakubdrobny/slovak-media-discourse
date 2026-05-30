UPDATE comments 
SET replyToId = (
    SELECT parent.id 
    FROM comments AS parent 
    WHERE parent.platformId = comments.platformParentId
)
WHERE platformParentId IS NOT NULL;
