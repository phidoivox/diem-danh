# ponytail: shim strangler, xóa ở Task 9
from detect_ai.modules.recognition.infrastructure.bench.train_yolo import *  # noqa: F401, F403
from detect_ai.modules.recognition.infrastructure.bench.train_yolo import main  # noqa: F401

if __name__ == '__main__':
    main()
