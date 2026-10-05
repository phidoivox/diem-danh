# ponytail: Task 9 shim cleanup
import sys
from detect_ai.modules.recognition.infrastructure import config as _impl
sys.modules[__name__] = _impl
from detect_ai.modules.recognition.infrastructure.config import *  # noqa: F403
