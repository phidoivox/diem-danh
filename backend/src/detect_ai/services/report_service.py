# ponytail: shim strangler, xóa ở Task 9
import sys
from ..modules.reporting.application import build as _build
from ..modules.reporting.application.build import *  # noqa: F401, F403
from ..modules.reporting.application.build import (  # noqa: F401
    EXAM_BAN_HEADERS,
    calculate_all_classes_exam_ban,
    calculate_class_exam_ban,
    generate_excel_exam_ban,
    now_vn,
    today_vn,
)


class _Shim(sys.modules[__name__].__class__):
    def __setattr__(self, name, val):
        if hasattr(_build, name):
            setattr(_build, name, val)
        super().__setattr__(name, val)


sys.modules[__name__].__class__ = _Shim
