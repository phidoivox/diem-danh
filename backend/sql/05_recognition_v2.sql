-- 05_recognition_v2.sql: cột bổ sung cho recognition v2 (tương thích SQLite + Postgres).
-- Giữ cột embedding JSON cũ (SQLite). Postgres có thể thêm vector(512) sau (pgvector, optional).
--
-- LƯU Ý: model_version + det_score đã bị 07_minimize_face_schema.sql xóa
-- (chưa bao giờ có giá trị thật). File này giữ lại để deploy cũ chạy lại an
-- toàn, nhưng DB mới chỉ cần uniform_* + face_events margin/backend.

-- face_embeddings: (đã xóa ở 07) phiên bản model + điểm detect.
-- ALTER TABLE face_embeddings ADD COLUMN IF NOT EXISTS model_version VARCHAR(32) DEFAULT 'buffalo_s';
-- ALTER TABLE face_embeddings ADD COLUMN IF NOT EXISTS det_score FLOAT DEFAULT 0.0;

-- attendance: điểm đồng phục chi tiết (has_uniform giữ nguyên để tương thích).
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS uniform_score FLOAT DEFAULT 0.0;
ALTER TABLE attendance ADD COLUMN IF NOT EXISTS uniform_status VARCHAR(20) DEFAULT 'unknown';

-- face_events: lưu margin + backend liveness để tuning ngưỡng sau này.
ALTER TABLE face_events ADD COLUMN IF NOT EXISTS margin FLOAT DEFAULT 0.0;
ALTER TABLE face_events ADD COLUMN IF NOT EXISTS backend VARCHAR(32) DEFAULT '';
