# ponytail: Task 9 shim cleanup
import sys
from detect_ai.modules.recognition.infrastructure import tracks as _impl
sys.modules[__name__] = _impl
from detect_ai.modules.recognition.infrastructure.tracks import *  # noqa: F403
