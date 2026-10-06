-- 05_recognition_v2.sql: cột bổ sung cho recognition v2 (tương thích SQLite + Postgres).
-- Giữ cột embedding JSON cũ (SQLite). Postgres có thể thêm vector(512) sau (pgvector, optional).

-- face_embeddings: phiên bản model + điểm detect để lọc gallery kém chất lượng.
ALTER TABLE face_embeddings ADD COLUMN IF NOT EXISTS model_version VARCHAR(32) DEFAULT 'buffalo_s';
ALTER TABLE face_embeddings ADD COLUMN IF NOT EXISTS det_score FLOAT DEFAULT 0.0;

-- attendance: điểm đồng phục chi tiết (has_uniform giữ nguyên để tương thích).
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS uniform_score FLOAT DEFAULT 0.0;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS uniform_status VARCHAR(20) DEFAULT 'unknown';

-- face_events: lưu margin + backend liveness để tuning ngưỡng sau này.
ALTER TABLE face_events ADD COLUMN IF NOT EXISTS margin FLOAT DEFAULT 0.0;
ALTER TABLE face_events ADD COLUMN IF NOT EXISTS backend VARCHAR(32) DEFAULT '';
