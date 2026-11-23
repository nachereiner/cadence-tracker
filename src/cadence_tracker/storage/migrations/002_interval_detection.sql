-- 002 — Interval detection on running seconds only (see docs/specs/F03, F06).
-- `speed_cv` is now computed on running seconds (stops excluded) and
-- `fast_blocks` counts segments run >= 15 % faster than the session median.
ALTER TABLE activity_metrics ADD COLUMN fast_blocks INTEGER;
