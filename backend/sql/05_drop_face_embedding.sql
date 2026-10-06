-- =====================================================================
-- SMART CLASSROOM MANAGEMENT SYSTEM - MIGRATION 05: DROP FACE EMBEDDING
-- Dọn sạch chức năng điểm danh khuôn mặt (FaceID) đã bị loại bỏ khỏi mã nguồn.
-- Chạy 1 lần trong Supabase SQL Editor (hoặc psql). Idempotent — chạy lại an toàn.
-- SQLite (dev offline): cột thừa không gây lỗi, nhưng nên xoá
-- backend/data/detect_ai.db* rồi khởi động lại để tạo schema mới sạch.
-- =====================================================================

-- 1. Xoá chỉ mục HNSW phục vụ tìm kiếm khuôn mặt (nếu còn)
DROP INDEX IF EXISTS idx_student_profiles_face_vector;

-- 2. Xoá cột vector khuôn mặt (nếu còn)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'student_profiles'
          AND column_name = 'face_embedding'
    ) THEN
        ALTER TABLE student_profiles DROP COLUMN face_embedding;
        RAISE NOTICE 'Da xoa cot student_profiles.face_embedding.';
    ELSE
        RAISE NOTICE 'Cot student_profiles.face_embedding khong ton tai, bo qua.';
    END IF;
END $$;
