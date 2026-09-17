-- =====================================================================
-- SMART CLASSROOM MANAGEMENT SYSTEM - SEED DATA
-- Default roles, demo users (Admin, Teacher, Student), Class & Settings
-- Password for all accounts: 123456
-- Hash: $2b$12$j7D8K3jeMgvKWaxk6Uwa6OrY37nj/dAJ2Ouel7iCMrZnT/Y.5ISvC
-- =====================================================================

-- 1. ROLES
INSERT INTO roles (id, role_name) VALUES
    (1, 'ADMIN'),
    (2, 'TEACHER'),
    (3, 'STUDENT')
ON CONFLICT (id) DO UPDATE SET role_name = EXCLUDED.role_name;

-- Reset sequence for roles if needed
SELECT setval('roles_id_seq', (SELECT MAX(id) FROM roles));

-- 2. USERS & PROFILES
-- 2.1 Admin
INSERT INTO users (id, user_code, full_name, email, password_hash, role_id, is_active, created_at)
VALUES (
    1,
    'ADMIN01',
    'Quản trị viên Hệ thống',
    'admin@school.edu.vn',
    '$2b$12$j7D8K3jeMgvKWaxk6Uwa6OrY37nj/dAJ2Ouel7iCMrZnT/Y.5ISvC',
    1,
    TRUE,
    NOW()
) ON CONFLICT (user_code) DO NOTHING;

-- 2.2 Teacher
INSERT INTO users (id, user_code, full_name, email, password_hash, role_id, is_active, created_at)
VALUES (
    2,
    'GV01',
    'TS. Nguyễn Văn A',
    'nguyenvana@school.edu.vn',
    '$2b$12$j7D8K3jeMgvKWaxk6Uwa6OrY37nj/dAJ2Ouel7iCMrZnT/Y.5ISvC',
    2,
    TRUE,
    NOW()
) ON CONFLICT (user_code) DO NOTHING;

INSERT INTO teacher_profiles (user_id, department, academic_title, office_room)
SELECT id, 'Khoa Công nghệ Thông tin', 'Tiến sĩ', 'A1-204'
FROM users WHERE user_code = 'GV01'
ON CONFLICT (user_id) DO NOTHING;

-- 2.3 Student
INSERT INTO users (id, user_code, full_name, email, password_hash, role_id, is_active, created_at)
VALUES (
    3,
    'SV2026001',
    'Trần Thị Mai',
    'maitt@student.edu.vn',
    '$2b$12$j7D8K3jeMgvKWaxk6Uwa6OrY37nj/dAJ2Ouel7iCMrZnT/Y.5ISvC',
    3,
    TRUE,
    NOW()
) ON CONFLICT (user_code) DO NOTHING;

INSERT INTO student_profiles (user_id, total_point, class_name, major)
SELECT id, 100, 'CNTT-K24A', 'Kỹ thuật Phần mềm'
FROM users WHERE user_code = 'SV2026001'
ON CONFLICT (user_id) DO NOTHING;

-- Reset sequence for users
SELECT setval('users_id_seq', (SELECT GREATEST(MAX(id), 3) FROM users));

-- 3. DEMO CLASS & ENROLLMENT
INSERT INTO classes (id, class_code, course_name, teacher_id, semester, total_sessions)
SELECT 1, 'CS101.1', 'Nhập môn Trí tuệ Nhân tạo', u.id, 'HK1_2026', 15
FROM users u WHERE u.user_code = 'GV01'
ON CONFLICT (class_code) DO NOTHING;

SELECT setval('classes_id_seq', (SELECT GREATEST(MAX(id), 1) FROM classes));

INSERT INTO class_students (class_id, student_id)
SELECT c.id, s.id
FROM classes c
CROSS JOIN users s
WHERE c.class_code = 'CS101.1' AND s.user_code = 'SV2026001'
ON CONFLICT (class_id, student_id) DO NOTHING;

-- 4. SYSTEM SETTINGS
INSERT INTO system_settings (key, value, description) VALUES
    ('POINT_FULL_ATTENDANCE', '2', 'Cộng điểm khi tham gia đủ buổi, đúng giờ, đủ đồng phục'),
    ('POINT_LATE', '-1', 'Trừ điểm nếu đi muộn'),
    ('POINT_HALF_ABSENCE', '-2', 'Trừ điểm nếu vắng nửa buổi'),
    ('POINT_ABSENCE_WITHOUT_LEAVE', '-5', 'Trừ điểm nếu vắng không phép'),
    ('POINT_UNIFORM_VIOLATION', '-2', 'Trừ điểm nếu vi phạm đồng phục'),
    ('LATE_TOLERANCE_MINUTES', '15', 'Số phút cho phép đi muộn'),
    ('REQUIRE_CHECKOUT', 'false', 'Bắt buộc cả check-in và check-out mới tính đủ buổi'),
    ('MAX_ABSENCE_PERCENT_EXAM_BAN', '20', 'Ngưỡng % vắng tính trên cả kỳ để cấm thi'),
    ('WARNING_ABSENCE_PERCENT', '15', 'Ngưỡng % vắng gửi cảnh báo học vụ sớm')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    description = EXCLUDED.description;
