# ponytail: Task 9 shim cleanup
import sys
from detect_ai.modules.recognition.infrastructure import liveness as _impl
sys.modules[__name__] = _impl
from detect_ai.modules.recognition.infrastructure.liveness import *  # noqa: F403
