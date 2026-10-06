-- 07_minimize_face_schema.sql: tối giản schema mặt về 1 cột duy nhất.
-- Chạy lại an toàn (toàn IF EXISTS / DROP có điều kiện).
--
-- Làm gì:
-- 1. Xóa cột chết student_profiles.face_embedding (không code nào dùng).
-- 2. Xóa face_embeddings.embedding_vec (trùng với embedding JSON).
-- 3. Xóa face_embeddings.model_version + det_score (chưa bao giờ có giá trị thật).
-- 4. Giữ tìm kiếm vector nhanh bằng EXPRESSION INDEX trên embedding JSON
--    (Postgres tự cast lúc search, không cần cột thứ 2, không backfill).
--
-- Rollback (nếu cần): restore từ backend/data/schema_backup_07.json rồi:
--   ALTER TABLE student_profiles ADD COLUMN face_embedding vector(512);
--   ALTER TABLE face_embeddings ADD COLUMN embedding_vec vector(512);
--   ALTER TABLE face_embeddings ADD COLUMN model_version VARCHAR(32) DEFAULT 'buffalo_s';
--   ALTER TABLE face_embeddings ADD COLUMN det_score FLOAT DEFAULT 0.0;
--   ... rồi UPDATE từng row từ file backup.

-- 1. Cột chết ở student_profiles (script 05 đã viết sẵn, gộp vào đây cho gọn 1 lần).
ALTER TABLE student_profiles DROP COLUMN IF EXISTS face_embedding;

-- 2. Bỏ index cũ trên cột vector thừa (nếu có), rồi xóa cột.
DROP INDEX IF EXISTS idx_face_embeddings_vec;
ALTER TABLE face_embeddings DROP COLUMN IF EXISTS embedding_vec;

-- 3. Xóa 2 cột trang trí.
ALTER TABLE face_embeddings DROP COLUMN IF EXISTS model_version;
ALTER TABLE face_embeddings DROP COLUMN IF EXISTS det_score;

-- 4. Expression index: tìm cosine trực tiếp trên cột JSON, không cần cột thứ 2.
-- (cast kèm vector(512) vì HNSW yêu cầu số chiều cố định).
CREATE INDEX IF NOT EXISTS idx_face_embeddings_vec_expr
    ON face_embeddings USING hnsw ((embedding::vector(512)) vector_cosine_ops);
