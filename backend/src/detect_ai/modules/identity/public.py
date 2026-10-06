from __future__ import annotations

from .infrastructure.models import Role, StudentProfile, TeacherProfile, User  # noqa: F401
from .presentation.deps import get_current_user, oauth2_scheme, require_admin, require_role, require_student, require_teacher, verify_kiosk_api_key  # noqa: F401
from .presentation.schemas import UserOut  # noqa: F401

__all__ = [
    "Role",
    "User",
    "StudentProfile",
    "TeacherProfile",
    "get_current_user",
    "oauth2_scheme",
    "require_admin",
    "require_role",
    "require_student",
    "require_teacher",
    "verify_kiosk_api_key",
    "UserOut",
    "auth_router",
    "admin_users_router",
]

_ROUTERS = {
    "auth_router": (".presentation.routes", "router"),
    "admin_users_router": (".presentation.admin_routes", "router"),
}


def __getattr__(name: str):
    # Lazy: xem academic/public.py (admin_routes import api.files + application).
    if name in _ROUTERS:
        import importlib

        mod_name, attr = _ROUTERS[name]
        mod = importlib.import_module(mod_name, __name__.rpartition(".")[0])
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
