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
-- 5. (TUỲ CHỌN) Dọn bảng của lớp legacy đã xoá khỏi mã nguồn.
--    3 bảng này không còn model nào ánh xạ tới. Bỏ comment nếu muốn xoá hẳn.
--    Thứ tự quan trọng: legacy_attendance tham chiếu students.
-- ---------------------------------------------------------------------
-- DROP TABLE IF EXISTS legacy_attendance;
-- DROP TABLE IF EXISTS uniform_rules;
-- DROP TABLE IF EXISTS students;
