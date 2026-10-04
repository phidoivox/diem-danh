# SQL apply order (Supabase / fresh DB)

1. `01_schema.sql` — base schema
2. `02_seed.sql` — roles, settings, demo accounts
3. `03_migrate_existing_db.sql` — bring old DBs to 01 shape
4. `04_enable_pgvector.sql` — `CREATE EXTENSION vector` (run BEFORE face tables)
5. `04_face_tables.sql` — `face_embeddings`, `face_events`
6. `05_recognition_v2.sql` — recognition v2 columns
7. `05_drop_face_embedding.sql` — drop legacy column (AFTER v2)
8. `06_pgvector_gallery.sql` — gallery version table
9. `07_minimize_face_schema.sql`
10. `08_attendance_snapshots.sql`
11. `09_split_classes_courses_admin.sql`

Do NOT rename files in this pass (Supabase may already reference names).
Full alembic migration is a separate project — see `docs/COMPLEXITY_AUDIT.md` §5.
