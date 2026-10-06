-- 08. Snapshot điểm danh: 2 ảnh local/người/tiết (check-in + check-out).
-- File ảnh nằm ở backend/data/storage/snapshots/<schedule_id>/, DB chỉ giữ URL.
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS check_in_snapshot_url VARCHAR(500) NULL;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS check_out_snapshot_url VARCHAR(500) NULL;

-- Khoảng cách tối thiểu giữa check-in và check-out (phút), tránh đứng yên
-- trước camera bị tính out ngay. Kiosk đọc hằng số mặc định 5 nếu thiếu.
INSERT INTO system_settings (key, value, description) VALUES
    ('CHECKOUT_MIN_GAP_MINUTES', '5', 'Số phút tối thiểu giữa check-in và check-out')
ON CONFLICT (key) DO NOTHING;
