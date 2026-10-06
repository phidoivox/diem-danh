-- =====================================================================
-- SMART CLASSROOM MANAGEMENT SYSTEM - SUPABASE POSTGRESQL SCHEMA (DDL)
-- Architecture: Cách 2 (Tách biệt users và student_profiles / teacher_profiles)
-- =====================================================================

-- 1. EXTENSIONS & TRẠNG THÁI (thay cho ENUM native)
CREATE EXTENSION IF NOT EXISTS vector;
-- KHÔNG dùng CREATE TYPE ... AS ENUM nữa. ORM khai native_enum=False + create_constraint=True,
-- tức là VARCHAR(n) + CHECK. Nếu file này tạo ENUM native còn ORM tạo VARCHAR thì tuỳ đường
-- tạo bảng mà ra hai schema vật lý khác nhau (đúng loại drift đã phải vá tay trước đây).
-- Hai CHECK dưới đây phải khớp tên + giá trị với SQLAlchemy sinh ra:
--   CONSTRAINT attendance_status CHECK (status IN ('PRESENT','LATE','HALF_ABSENT','ABSENT','EXCUSED'))
--   CONSTRAINT leave_status      CHECK (status IN ('PENDING','APPROVED','REJECTED'))

-- 2. TABLE: roles
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL
);

-- 3. TABLE: users (Base identity, authentication & soft delete)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_code VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    avatar_url VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. TABLE: administrative_classes (Lớp sinh hoạt / Lớp niên chế)
CREATE TABLE IF NOT EXISTS administrative_classes (
    id SERIAL PRIMARY KEY,
    class_code VARCHAR(50) UNIQUE NOT NULL,
    academic_year VARCHAR(50) NOT NULL DEFAULT '',
    faculty VARCHAR(100) NOT NULL DEFAULT '',
    homeroom_teacher_id INT NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. TABLE: student_profiles (1-1 with users for students)
CREATE TABLE IF NOT EXISTS student_profiles (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_point INT NOT NULL DEFAULT 100,
    admin_class_id INT NULL REFERENCES administrative_classes(id) ON DELETE SET NULL,
    class_name VARCHAR(100) NOT NULL DEFAULT '',
    major VARCHAR(100) NOT NULL DEFAULT ''
);

-- 6. TABLE: teacher_profiles (1-1 with users for teachers)
CREATE TABLE IF NOT EXISTS teacher_profiles (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department VARCHAR(100) NOT NULL DEFAULT '',
    academic_title VARCHAR(100) NOT NULL DEFAULT '',
    office_room VARCHAR(50) NOT NULL DEFAULT ''
);

-- 7. TABLE: courses (Học phần / Môn học)
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    course_code VARCHAR(50) UNIQUE NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    credits INT NOT NULL DEFAULT 3,
    default_sessions INT NOT NULL DEFAULT 15,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. TABLE: classes (Lớp học phần)
CREATE TABLE IF NOT EXISTS classes (
    id SERIAL PRIMARY KEY,
    class_code VARCHAR(50) UNIQUE NOT NULL,
    course_id INT NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    course_name VARCHAR(100) NOT NULL DEFAULT '',
    teacher_id INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    semester VARCHAR(20) NOT NULL,
    total_sessions INT NOT NULL DEFAULT 15
);

-- 7. TABLE: class_students (Composite PK)
CREATE TABLE IF NOT EXISTS class_students (
    class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    PRIMARY KEY (class_id, student_id)
);

-- 8. TABLE: schedules (Thời khóa biểu từng buổi)
CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    class_id INT NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    room_name VARCHAR(50) NOT NULL,
    study_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    session_order INT NOT NULL,
    CONSTRAINT check_schedule_time_valid CHECK (start_time < end_time)
);

-- 9. TABLE: attendance (Lịch sử Điểm danh & Chuyên cần)
CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    schedule_id INT NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    check_in_time TIMESTAMPTZ NULL,
    check_out_time TIMESTAMPTZ NULL,
    has_uniform BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(11) NOT NULL DEFAULT 'ABSENT',
    is_manual_override BOOLEAN NOT NULL DEFAULT FALSE,
    is_evaluated BOOLEAN NOT NULL DEFAULT FALSE,
    evaluated_at TIMESTAMPTZ NULL,
    note VARCHAR(255) NULL,
    updated_by INT NULL REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_attendance_schedule_student UNIQUE (schedule_id, student_id),
    CONSTRAINT attendance_status CHECK (status IN ('PRESENT', 'LATE', 'HALF_ABSENT', 'ABSENT', 'EXCUSED'))
);

-- 10. TABLE: leave_requests (Đơn xin nghỉ phép trực tuyến)
CREATE TABLE IF NOT EXISTS leave_requests (
    id SERIAL PRIMARY KEY,
    schedule_id INT NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    student_id INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    proof_image VARCHAR(500) NULL,
    status VARCHAR(8) NOT NULL DEFAULT 'PENDING',
    teacher_feedback VARCHAR(255) NULL,
    reviewed_by INT NULL REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT leave_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

-- 11. TABLE: point_ledger (Sổ cái biến động điểm chuyên cần)
CREATE TABLE IF NOT EXISTS point_ledger (
    id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    schedule_id INT NULL REFERENCES schedules(id) ON DELETE SET NULL,
    point_delta INT NOT NULL,
    reason_code VARCHAR(50) NOT NULL,
    description VARCHAR(255) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 12. TABLE: system_settings (Cấu hình tham số hệ thống)
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value VARCHAR(255) NOT NULL,
    description VARCHAR(255) NULL
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_users_user_code ON users (user_code);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users (role_id);
CREATE INDEX IF NOT EXISTS idx_student_profiles_user_id ON student_profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_teacher_profiles_user_id ON teacher_profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_classes_teacher_id ON classes (teacher_id);
CREATE INDEX IF NOT EXISTS idx_schedules_class_id ON schedules (class_id);
CREATE INDEX IF NOT EXISTS idx_schedules_room_date ON schedules (room_name, study_date);
CREATE INDEX IF NOT EXISTS idx_schedules_room_conflict ON schedules (room_name, study_date, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_attendance_schedule_student ON attendance (schedule_id, student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_evaluated ON attendance (is_evaluated, schedule_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_student_id ON leave_requests (student_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_schedule_id ON leave_requests (schedule_id);
-- Chống nộp trùng đơn nghỉ phép khi có request đồng thời (pre-check ở API có khe hở TOCTOU).
-- Chỉ áp cho đơn còn hiệu lực; đơn REJECTED được phép nộp lại.
CREATE UNIQUE INDEX IF NOT EXISTS uq_leave_requests_active
    ON leave_requests (schedule_id, student_id)
    WHERE status IN ('PENDING', 'APPROVED');
CREATE INDEX IF NOT EXISTS idx_point_ledger_student ON point_ledger (student_id);
CREATE INDEX IF NOT EXISTS idx_point_ledger_schedule ON point_ledger (schedule_id);
