# ponytail: shim strangler, xóa ở Task 9
from ..modules.identity.presentation.deps import *  # noqa: F401, F403
from ..modules.identity.presentation.deps import (  # noqa: F401
    get_current_user,
    oauth2_scheme,
    require_admin,
    require_role,
    require_student,
    require_teacher,
    verify_kiosk_api_key,
)
