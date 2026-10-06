-- 06_pgvector_gallery.sql: gallery khuôn mặt lên pgvector (Postgres/Supabase).
-- SQLite dev bỏ qua file này (không có pgvector) — code tự fallback về cột JSON.
--
-- Sau migration:
-- - face_embeddings.embedding_vec: vector 512-d (nguồn sự thật), backfill từ JSON.
-- - gallery_versions: version theo lớp để mọi worker/backend biết khi nào cần nạp lại
--   gallery (thay version RAM cục bộ — hết lệch multi-worker).

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE face_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector(512);

-- Backfill từ JSON "[0.02, -0.03, ...]" (đã L2-normalize từ lúc enroll).
UPDATE face_embeddings
SET embedding_vec = embedding::vector
WHERE embedding_vec IS NULL;

-- Index cosine cho tìm kiếm gần nhất (dự phòng query trực tiếp bằng SQL).
CREATE INDEX IF NOT EXISTS idx_face_embeddings_vec
    ON face_embeddings USING hnsw (embedding_vec vector_cosine_ops);

-- Version gallery theo lớp (bump mỗi khi enroll/vô hiệu hoá vector).
CREATE TABLE IF NOT EXISTS gallery_versions (
    class_id INTEGER PRIMARY KEY REFERENCES classes(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
