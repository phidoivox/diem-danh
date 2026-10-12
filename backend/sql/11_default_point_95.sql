-- 11. Đổi điểm khởi đầu SV thường 85 -> 95 (cán sự giữ 100).
-- Chạy 1 lần trên DB production đã có dữ liệu.
ALTER TABLE student_profiles ALTER COLUMN total_point SET DEFAULT 95;

-- Nâng SV chưa chấm lần nào (đang đúng 85 gốc) lên 95.
-- Không đụng điểm đã biến động (ledger đã ghi) để giữ lịch sử.
UPDATE student_profiles SET total_point = 95
WHERE COALESCE(is_officer, FALSE) = FALSE AND total_point = 85;
