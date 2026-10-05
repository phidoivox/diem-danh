# ponytail: shim strangler, xóa ở Task 9
from ..modules.identity.presentation.admin_routes import *  # noqa: F401, F403
from ..modules.identity.presentation.admin_routes import (  # noqa: F401
    AdminUserPage,
    AdminUserResponse,
    StudentProfileDTO,
    TeacherProfileDTO,
    UserCreateRequest,
    UserUpdateRequest,
    create_user,
    delete_user,
    list_users,
    router,
    serialize_admin_user,
    update_user,
    upload_user_avatar,
)
