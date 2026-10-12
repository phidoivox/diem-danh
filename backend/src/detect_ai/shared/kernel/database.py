from __future__ import annotations
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    # Qua public (đăng ký Base.metadata qua re-export models, không import sâu infra).
    from detect_ai.modules.academic import public as _academic_public  # noqa: F401
    from detect_ai.modules.attendance import public as _attendance_public  # noqa: F401
    from detect_ai.modules.evaluation import public as _evaluation_public  # noqa: F401
    from detect_ai.modules.identity import public as _identity_public  # noqa: F401
    from detect_ai.modules.leave import public as _leave_public  # noqa: F401
    from detect_ai.modules.recognition import public as _recognition_public  # noqa: F401
    from detect_ai.shared.kernel import system_setting  # noqa: F401
    from detect_ai.shared.notifications import models as _notif_models  # noqa: F401
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
        # Ensure-column chạy mọi dialect (Postgres cũ thiếu cột -> 500 login).
        if is_sqlite:
            # Migration check for legacy sqlite table students
            cols = await c.run_sync(lambda sc: [r[1] for r in sc.exec_driver_sql("PRAGMA table_info(students)").fetchall()])
            if cols and "photo" not in cols:
                await c.exec_driver_sql("ALTER TABLE students ADD COLUMN photo VARCHAR(64) DEFAULT ''")

            async def _ensure_column(table: str, col: str, ddl: str) -> None:
                names = await c.run_sync(
                    lambda sc, t=table: [r[1] for r in sc.exec_driver_sql(f"PRAGMA table_info({t})").fetchall()]
                )
                if names and col not in names:
                    await c.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")

            await _ensure_column("courses", "description", "description TEXT")
            await _ensure_column("courses", "created_at", "created_at DATETIME")
            await _ensure_column("classes", "course_id", "course_id INTEGER")
            await _ensure_column("student_profiles", "admin_class_id", "admin_class_id INTEGER")
            await _ensure_column("student_profiles", "is_officer", "is_officer BOOLEAN DEFAULT 0")

            # Khởi tạo roles và tài khoản mặc định nếu DB SQLite chưa có dữ liệu
            role_cnt = await c.run_sync(lambda sc: sc.exec_driver_sql("SELECT COUNT(*) FROM roles").scalar())
            if not role_cnt:
                await c.exec_driver_sql("INSERT INTO roles (id, role_name) VALUES (1, 'ADMIN'), (2, 'TEACHER'), (3, 'STUDENT')")

            user_cnt = await c.run_sync(lambda sc: sc.exec_driver_sql("SELECT COUNT(*) FROM users").scalar())
            if not user_cnt:
                pwd_hash = "$2b$12$j7D8K3jeMgvKWaxk6Uwa6OrY37nj/dAJ2Ouel7iCMrZnT/Y.5ISvC"
                await c.exec_driver_sql(
                    "INSERT INTO users (id, user_code, full_name, email, password_hash, role_id, is_active, created_at) VALUES "
                    f"(1, 'ADMIN01', 'Quản trị viên Hệ thống', 'admin@school.edu.vn', '{pwd_hash}', 1, 1, CURRENT_TIMESTAMP), "
                    f"(2, 'GV01', 'TS. Nguyễn Văn A', 'nguyenvana@school.edu.vn', '{pwd_hash}', 2, 1, CURRENT_TIMESTAMP), "
                    f"(3, 'SV2026001', 'Trần Thị Mai', 'mai.tt2026@student.edu.vn', '{pwd_hash}', 3, 1, CURRENT_TIMESTAMP)"
                )
                await c.exec_driver_sql(
                    "INSERT INTO administrative_classes (id, class_code, academic_year, faculty) "
                    "VALUES (1, 'CNTT-K24A', '2024-2028', 'Khoa Công nghệ Thông tin')"
                )
                await c.exec_driver_sql(
                    "INSERT INTO teacher_profiles (user_id, department, academic_title, office_room) "
                    "VALUES (2, 'Khoa Công nghệ Thông tin', 'Tiến sĩ', 'A1-204')"
                )
                await c.exec_driver_sql(
                    "INSERT INTO student_profiles (user_id, student_code, total_point, attendance_count, absence_count, late_count, admin_class_id, is_officer) "
                    "VALUES (3, 'SV2026001', 95, 0, 0, 0, 1, 0)"
                )
        else:
            # Postgres/Supabase: information_schema thay PRAGMA.
            async def _ensure_pg_column(table: str, col: str, ddl: str) -> None:
                exists = await c.run_sync(
                    lambda sc, t=table, cl=col: sc.exec_driver_sql(
                        "SELECT 1 FROM information_schema.columns "
                        f"WHERE table_schema='public' AND table_name='{t}' AND column_name='{cl}'"
                    ).first() is not None
                )
                if not exists:
                    await c.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")

            await _ensure_pg_column("courses", "description", "description TEXT")
            await _ensure_pg_column("courses", "created_at", "created_at TIMESTAMPTZ")
            await _ensure_pg_column("classes", "course_id", "course_id INTEGER")
            await _ensure_pg_column("student_profiles", "admin_class_id", "admin_class_id INTEGER")
            await _ensure_pg_column(
                "student_profiles", "is_officer", "is_officer BOOLEAN NOT NULL DEFAULT FALSE"
            )
            # Default điểm khởi đầu mới 95 (cán sự tạo mới 100 do app quyết).
            await c.exec_driver_sql(
                "ALTER TABLE student_profiles ALTER COLUMN total_point SET DEFAULT 95"
            )
