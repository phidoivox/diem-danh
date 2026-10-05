# ponytail: shim strangler, xóa ở Task 9
from ..modules.identity.presentation.routes import *  # noqa: F401, F403
from ..modules.identity.presentation.routes import (  # noqa: F401
    LoginRequest,
    LoginResponse,
    StudentProfileResponse,
    TeacherProfileResponse,
    UserOut,
    UserResponse,
    get_me,
    login,
    router,
    serialize_user,
)
