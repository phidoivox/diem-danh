-- 10_notifications: log chống gửi trùng mail nhắc lịch / cảnh báo / cấm thi.
CREATE TABLE IF NOT EXISTS notification_logs (
    id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    schedule_id INT NULL REFERENCES schedules(id) ON DELETE SET NULL,
    kind VARCHAR(20) NOT NULL,
    dedup_key VARCHAR(200) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    error VARCHAR(500) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notif_dedup ON notification_logs (dedup_key);
CREATE INDEX IF NOT EXISTS idx_notif_student ON notification_logs (student_id);

-- Công tắc mail + cấu hình SMTP (nguồn duy nhất: database, sửa trên UI admin).
INSERT INTO system_settings (key, value, description) VALUES
    ('EMAIL_ENABLED', 'true', 'Bật/tắt toàn bộ gửi mail'),
    ('EMAIL_REMINDER_ENABLED', 'true', 'Bật mail nhắc lịch học'),
    ('EMAIL_WARNING_ENABLED', 'true', 'Bật mail cảnh báo cấm thi'),
    ('EMAIL_BAN_ENABLED', 'true', 'Bật mail cấm thi chính thức'),
    ('SMTP_ENABLED', 'false', 'Bật gửi SMTP thật (false = log-only)'),
    ('SMTP_HOST', '', 'SMTP host, VD smtp.gmail.com'),
    ('SMTP_PORT', '587', 'SMTP port'),
    ('SMTP_USER', '', 'SMTP user đăng nhập'),
    ('SMTP_PASSWORD', '', 'SMTP password / app password'),
    ('SMTP_FROM', '', 'Địa chỉ From'),
    ('SMTP_USE_TLS', 'true', 'Bật STARTTLS'),
    ('SMTP_TIMEOUT_S', '10', 'Timeout kết nối SMTP (giây)')
ON CONFLICT (key) DO NOTHING;
