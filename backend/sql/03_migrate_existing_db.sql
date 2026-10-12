-- =====================================================================
-- MIGRATION cho CSDL Supabase ĐÃ TỒN TẠI
-- Dành cho project đã chạy 01_schema.sql bản CŨ (bản còn CREATE TYPE ... AS ENUM).
--
-- Chạy 1 lần trong Supabase SQL Editor. Script idempotent — chạy lại vẫn an toàn.
-- Nếu bạn tạo project mới từ đầu bằng 01_schema.sql bản mới thì KHÔNG cần file này.
--
-- Vì sao cần: bản cũ tạo ENUM native của Postgres, nhưng ORM khai
-- native_enum=False + create_constraint=True (tức VARCHAR + CHECK). Hai đường tạo
-- bảng cho ra hai schema vật lý khác nhau, khiến asyncpg có thể báo lỗi
-- "column status is of type attendance_status but expression is of type text".
-- Migration này đưa CSDL đang có về đúng dạng VARCHAR + CHECK.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. attendance.status: ENUM native -> VARCHAR(11) + CHECK
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'attendance'
          AND column_name = 'status' AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE attendance ALTER COLUMN status DROP DEFAULT;
        ALTER TABLE attendance ALTER COLUMN status TYPE VARCHAR(11) USING status::text;
        ALTER TABLE attendance ALTER COLUMN status SET DEFAULT 'ABSENT';
        RAISE NOTICE 'attendance.status -> VARCHAR(11)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'attendance_status' AND conrelid = 'attendance'::regclass
    ) THEN
        ALTER TABLE attendance ADD CONSTRAINT attendance_status
            CHECK (status IN ('PRESENT', 'LATE', 'HALF_ABSENT', 'ABSENT', 'EXCUSED'));
        RAISE NOTICE 'da them CHECK attendance_status';
    END IF;
END $$;


-- ---------------------------------------------------------------------
-- 2. leave_requests.status: ENUM native -> VARCHAR(8) + CHECK
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'leave_requests'
          AND column_name = 'status' AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE leave_requests ALTER COLUMN status DROP DEFAULT;
        ALTER TABLE leave_requests ALTER COLUMN status TYPE VARCHAR(8) USING status::text;
        ALTER TABLE leave_requests ALTER COLUMN status SET DEFAULT 'PENDING';
        RAISE NOTICE 'leave_requests.status -> VARCHAR(8)';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'leave_status' AND conrelid = 'leave_requests'::regclass
    ) THEN
        ALTER TABLE leave_requests ADD CONSTRAINT leave_status
            CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'));
        RAISE NOTICE 'da them CHECK leave_status';
    END IF;
END $$;


-- ---------------------------------------------------------------------
-- 3. Dọn các ENUM type không còn dùng (bỏ qua nếu còn phụ thuộc)
-- ---------------------------------------------------------------------
DROP TYPE IF EXISTS attendance_status;
DROP TYPE IF EXISTS leave_status;
DROP TYPE IF EXISTS user_role;


-- ---------------------------------------------------------------------
-- 4. Ràng buộc chống nộp trùng đơn nghỉ phép
--    Trước đây chỉ có pre-check ở tầng API nên 2 request đồng thời vẫn lọt.
--    Kiểm tra trùng trước, báo lỗi rõ ràng thay vì để CREATE INDEX thất bại khó hiểu.
-- ---------------------------------------------------------------------
DO $$
DECLARE dup_count int;
BEGIN
    SELECT count(*) INTO dup_count FROM (
        SELECT schedule_id, student_id
        FROM leave_requests
        WHERE status IN ('PENDING', 'APPROVED')
        GROUP BY schedule_id, student_id
        HAVING count(*) > 1
    ) d;

    IF dup_count > 0 THEN
        RAISE EXCEPTION
            'Có % cặp (schedule_id, student_id) đang có nhiều hơn 1 đơn hiệu lực. '
            'Hãy xử lý thủ công (chuyển bớt sang REJECTED) rồi chạy lại script.', dup_count;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_leave_requests_active
    ON leave_requests (schedule_id, student_id)
    WHERE status IN ('PENDING', 'APPROVED');


-- ---------------------------------------------------------------------
-- 5. Cờ ban cán sự (student_profiles.is_officer)
--    DB tạo trước bản thêm cột này thì login vỡ 500 (UndefinedColumnError).
--    App đã tự vá lúc khởi động, nhưng chạy tay SQL này nếu muốn fix ngay.
-- ---------------------------------------------------------------------
ALTER TABLE student_profiles
    ADD COLUMN IF NOT EXISTS is_officer BOOLEAN NOT NULL DEFAULT FALSE;

-- Đổi default điểm khởi đầu: SV 95, cán sự tạo mới 100 (do app quyết lúc insert).
ALTER TABLE student_profiles ALTER COLUMN total_point SET DEFAULT 95;


-- ---------------------------------------------------------------------
-- 6. Hạ điểm hàng loạt non-officer đang 100 về 85.
--    Chỉ chạy 1 lần sau khi tick cán sự xong. Ledger KHÔNG ghi bù để giữ
--    lịch sử; total_point mới = 85, lần chấm sau cộng dồn từ 85.
-- ---------------------------------------------------------------------
-- UPDATE student_profiles SET total_point = 85
-- WHERE COALESCE(is_officer, FALSE) = FALSE AND total_point = 100;


-- ---------------------------------------------------------------------
-- 7. (TUỲ CHỌN) Dọn bảng của lớp legacy đã xoá khỏi mã nguồn.
--    3 bảng này không còn model nào ánh xạ tới. Bỏ comment nếu muốn xoá hẳn.
--    Thứ tự quan trọng: legacy_attendance tham chiếu students.
-- ---------------------------------------------------------------------
-- DROP TABLE IF EXISTS legacy_attendance;
-- DROP TABLE IF EXISTS uniform_rules;
-- DROP TABLE IF EXISTS students;
