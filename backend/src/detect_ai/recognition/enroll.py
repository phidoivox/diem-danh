# ponytail: Task 9 shim cleanup
import sys
from detect_ai.modules.recognition.infrastructure import enroll as _impl
sys.modules[__name__] = _impl
from detect_ai.modules.recognition.infrastructure.enroll import *  # noqa: F403
