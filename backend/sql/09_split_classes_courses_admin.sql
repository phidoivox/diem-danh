-- =====================================================================
-- MIGRATION 09: SPLIT COURSES, ADMINISTRATIVE CLASSES & COURSE CLASSES
-- =====================================================================

-- 1. Bảng Môn học / Học phần (courses)
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    course_code VARCHAR(50) UNIQUE NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    credits INT NOT NULL DEFAULT 3,
    default_sessions INT NOT NULL DEFAULT 15,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;

-- 2. Bảng Lớp sinh hoạt / Lớp niên chế (administrative_classes)
CREATE TABLE IF NOT EXISTS administrative_classes (
    id SERIAL PRIMARY KEY,
    class_code VARCHAR(50) UNIQUE NOT NULL,
    academic_year VARCHAR(50) NOT NULL DEFAULT '',
    faculty VARCHAR(100) NOT NULL DEFAULT '',
    homeroom_teacher_id INT NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE administrative_classes ENABLE ROW LEVEL SECURITY;

-- 3. Migrate dữ liệu sang courses từ classes cũ
INSERT INTO courses (course_code, course_name, credits, default_sessions)
SELECT 'INT101', course_name, 3, total_sessions
FROM classes
LIMIT 1
ON CONFLICT (course_code) DO NOTHING;

-- 4. Thêm course_id vào classes (Lớp học phần)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'classes' AND column_name = 'course_id'
    ) THEN
        ALTER TABLE classes ADD COLUMN course_id INT REFERENCES courses(id) ON DELETE RESTRICT;
    END IF;
END $$;

UPDATE classes c
SET course_id = (SELECT id FROM courses LIMIT 1)
WHERE c.course_id IS NULL;

ALTER TABLE classes ALTER COLUMN course_id SET NOT NULL;

-- 5. Migrate dữ liệu sang administrative_classes từ student_profiles cũ
INSERT INTO administrative_classes (class_code, academic_year, faculty)
SELECT DISTINCT class_name, '2024-2028', 'Công nghệ Thông tin'
FROM student_profiles
WHERE class_name IS NOT NULL AND class_name != ''
ON CONFLICT (class_code) DO NOTHING;

-- 6. Thêm admin_class_id vào student_profiles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'student_profiles' AND column_name = 'admin_class_id'
    ) THEN
        ALTER TABLE student_profiles ADD COLUMN admin_class_id INT REFERENCES administrative_classes(id) ON DELETE SET NULL;
    END IF;
END $$;

UPDATE student_profiles sp
SET admin_class_id = ac.id
FROM administrative_classes ac
WHERE sp.class_name = ac.class_code AND sp.admin_class_id IS NULL;
