-- =====================================================================
-- 04_face_tables.sql — Điểm danh khuôn mặt Kiosk (InsightFace + Liveness)
-- Chạy sau 01_schema.sql. Idempotent (IF NOT EXISTS).
-- SQLite (dev) chạy nguyên file cũng OK (bỏ qua CREATE EXTENSION lỗi -> dùng sqlite3 CLI
-- thì xoá dòng 13; còn ORM create_all tự tạo 2 bảng này, file này chủ yếu cho Supabase).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS face_embeddings (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    embedding TEXT NOT NULL,
    quality DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    source VARCHAR(20) NOT NULL DEFAULT 'avatar',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_face_embeddings_user_active
    ON face_embeddings (user_id, is_active);

CREATE TABLE IF NOT EXISTS face_events (
    id SERIAL PRIMARY KEY,
    schedule_id INT NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    student_id INT NULL REFERENCES users(id) ON DELETE SET NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    liveness_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    decision VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_face_events_schedule_time
    ON face_events (schedule_id, created_at);
