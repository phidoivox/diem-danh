-- =====================================================================
-- SMART CLASSROOM MANAGEMENT SYSTEM - MIGRATION 04: PGVECTOR SUPPORT
-- *** DEPRECATED: Chức năng điểm danh khuôn mặt (FaceID) đã bị loại bỏ. ***
-- File này được giữ lại chỉ để tham khảo lịch sử, KHÔNG chạy cho deploy mới.
-- Deploy mới dùng 01_schema.sql (bản không còn cột face_embedding).
-- CSDL cũ có cột face_embedding: chạy 05_drop_face_embedding.sql để dọn sạch.
-- =====================================================================
-- (Nội dung gốc đã xóa: CREATE EXTENSION vector + ALTER face_embedding TYPE
-- vector(512) + CREATE INDEX hnsw.)
SELECT 1;
