# ponytail: Task 9 shim cleanup
import sys
from detect_ai.modules.recognition.infrastructure import uniform_engine as _impl
sys.modules[__name__] = _impl
from detect_ai.modules.recognition.infrastructure.uniform_engine import *  # noqa: F403
