import { FaceDetector, FilesetResolver, Detection } from "@mediapipe/tasks-vision";

let detectorInstance: FaceDetector | null = null;
let initPromise: Promise<FaceDetector | null> | null = null;

export async function getClientFaceDetector(): Promise<FaceDetector | null> {
  if (typeof window === "undefined") return null;
  if (detectorInstance) return detectorInstance;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    try {
      const vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
      );

      // Thử delegate GPU trước để đạt tốc độ 60fps tốt nhất; nếu GPU không hỗ trợ thì fallback CPU.
      try {
        detectorInstance = await FaceDetector.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          minDetectionConfidence: 0.5,
        });
        return detectorInstance;
      } catch (gpuErr) {
        console.warn("MediaPipe GPU delegate không khả dụng, chuyển sang CPU:", gpuErr);
        detectorInstance = await FaceDetector.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
            delegate: "CPU",
          },
          runningMode: "VIDEO",
          minDetectionConfidence: 0.5,
        });
        return detectorInstance;
      }
    } catch (err) {
      console.warn("Không thể khởi tạo MediaPipe FaceDetector (offline hoặc CDN chặn), fallback về server boxes:", err);
      return null;
    } finally {
      initPromise = null;
    }
  })();

  return initPromise;
}

export async function closeClientFaceDetector(): Promise<void> {
  try { detectorInstance?.close(); } catch { /* ignore */ }
  detectorInstance = null;
}

export type LocalFaceBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  score: number;
  // Nhãn danh tính được map từ server về
  decision?: string;
  fullName?: string;
  userCode?: string;
  liveness?: number;
  studentId?: number;
  lastMatchedAt?: number;
};

/**
 * Tính IoU giữa 2 bounding box chuẩn hoá [0..1]
 */
function computeIoU(
  b1: [number, number, number, number],
  b2: [number, number, number, number]
): number {
  const [x1A, y1A, x2A, y2A] = b1;
  const [x1B, y1B, x2B, y2B] = b2;

  const xLeft = Math.max(x1A, x1B);
  const yTop = Math.max(y1A, y1B);
  const xRight = Math.min(x2A, x2B);
  const yBottom = Math.min(y2A, y2B);

  if (xRight < xLeft || yBottom < yTop) return 0.0;

  const intersection = (xRight - xLeft) * (yBottom - yTop);
  const areaA = Math.max(0, x2A - x1A) * Math.max(0, y2A - y1A);
  const areaB = Math.max(0, x2B - x1B) * Math.max(0, y2B - y1B);
  const union = areaA + areaB - intersection;

  return union > 0 ? intersection / union : 0.0;
}

/**
 * Map kết quả danh tính từ server (vốn chậm hơn 200-400ms) vào các box MediaPipe cục bộ mới nhất (60 FPS).
 */
export function matchServerIdentities(
  localBoxes: LocalFaceBox[],
  serverFaces: {
    bbox: number[];
    decision: string;
    full_name?: string | null;
    user_code?: string | null;
    score: number;
    liveness?: number;
    student_id?: number | null;
  }[],
  serverBaseW: number,
  serverBaseH: number,
  videoW: number,
  videoH: number,
  previousMatches?: LocalFaceBox[]
): LocalFaceBox[] {
  const now = performance.now();
  const matched = localBoxes.map((loc) => {
    // Toạ độ chuẩn hoá của local box
    const normLocal: [number, number, number, number] = [
      loc.x1 / videoW,
      loc.y1 / videoH,
      loc.x2 / videoW,
      loc.y2 / videoH,
    ];

    let bestMatch: (typeof serverFaces)[0] | null = null;
    let bestIoU = 0.3; // Ngưỡng IoU tối thiểu để coi là cùng 1 mặt (0.15 cũ quá lỏng, dễ gán nhầm)

    for (const sf of serverFaces) {
      if (!sf.bbox || sf.bbox.length < 4) continue;
      const normServer: [number, number, number, number] = [
        sf.bbox[0] / serverBaseW,
        sf.bbox[1] / serverBaseH,
        sf.bbox[2] / serverBaseW,
        sf.bbox[3] / serverBaseH,
      ];
      const iou = computeIoU(normLocal, normServer);
      if (iou > bestIoU) {
        bestIoU = iou;
        bestMatch = sf;
      }
    }

    if (bestMatch) {
      return {
        ...loc,
        decision: bestMatch.decision,
        fullName: bestMatch.full_name || undefined,
        userCode: bestMatch.user_code || undefined,
        liveness: bestMatch.liveness,
        studentId: bestMatch.student_id || undefined,
        lastMatchedAt: now,
      };
    }

    // Nếu server frame này chưa kịp trả về, kiểm tra xem box trước đó trong vòng 0.8s có thông tin không
    if (previousMatches) {
      for (const prev of previousMatches) {
        if (!prev.decision || !prev.lastMatchedAt || now - prev.lastMatchedAt > 800) continue;
        const normPrev: [number, number, number, number] = [
          prev.x1 / videoW,
          prev.y1 / videoH,
          prev.x2 / videoW,
          prev.y2 / videoH,
        ];
        if (computeIoU(normLocal, normPrev) > 0.4) {
          return {
            ...loc,
            decision: prev.decision,
            fullName: prev.fullName,
            userCode: prev.userCode,
            liveness: prev.liveness,
            studentId: prev.studentId,
            lastMatchedAt: prev.lastMatchedAt,
          };
        }
      }
    }

    return loc;
  });

  return matched;
}
