-- 0059: Add GoMag and ContentSpeed to the feed_source_type enum.
--
-- Both are Romanian e-commerce platforms added as new feed source options.

ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'gomag';
ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'contentspeed';
