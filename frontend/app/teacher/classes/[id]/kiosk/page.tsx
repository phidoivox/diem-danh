"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { RoleGuard } from "@/components/layout/role-guard";
import {
  getKioskGalleryStatus,
  getTeacherLiveAttendance,
  getToken,
  kioskCheckin,
  kioskResetSession,
  kioskWsUrl,
  KioskFaceBox,
  KioskGalleryStatus,
} from "@/lib/api";
import {
  boxColor,
  boxLabel,
  filterFreshChecked,
  stabilizeDecisions,
} from "@/lib/kiosk-decisions";
import {
  getClientFaceDetector,
  LocalFaceBox,
  matchServerIdentities,
} from "@/lib/face-detector";
import type { FaceDetector, Detection } from "@mediapipe/tasks-vision";
import {
  ArrowLeft,
  Camera,
  CameraOff,
  ScanFace,
  RotateCcw,
  CircleCheck,
  TriangleAlert,
  RefreshCw,
  UserRound,
  History,
} from "lucide-react";

const FALLBACK_POLL_MS = 450;

// boxColor/boxLabel/stabilize/filter tách ra lib/kiosk-decisions.ts (test được).
// MediaPipe face-detector.ts giữ nguyên.

export default function KioskPage() {
  const params = useParams();
  const classId = Number(params?.id);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const busyRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const wsOkRef = useRef(false);
  // Adaptive do server dặn: infer chậm -> gửi thưa + ảnh nhỏ lại.
  const intervalRef = useRef(FALLBACK_POLL_MS);
  const widthRef = useRef(480);
  // MediaPipe client-side tracking: mượt 60 FPS, độ trễ 0ms.
  const detectorRef = useRef<FaceDetector | null>(null);
  const localBoxesRef = useRef<LocalFaceBox[]>([]);
  // Lưu box từ server (đã suy luận danh tính).
  const boxesRef = useRef<KioskFaceBox[]>([]);
  const rafRef = useRef<number>(0);
  // Cooldown hiển thị: 1 SV chỉ thêm lịch sử 1 lần/12s, tránh spam.
  const seenAtRef = useRef<Map<string, number>>(new Map());
  // Hysteresis quyết định: chỉ đổi màu box khi cùng decision 2 msg liên tiếp
  // hoặc decision mới giữ >800ms — 1 msg SPOOF đơn lẻ không làm nhảy màu.
  const stableRef = useRef<Map<string, { shown: string; pending: string | null; pendingCount: number; lastChange: number }>>(new Map());
  // Ping-Pong 1-in-flight điều khiển gửi frame.
  const inFlightRef = useRef(false);
  const sentAtRef = useRef<number>(0);
  const timeoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nextSendTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [running, setRunning] = useState(false);
  const [camError, setCamError] = useState<string | null>(null);
  const [faces, setFaces] = useState<KioskFaceBox[]>([]);
  // SV vừa nhận diện (thẻ thông tin bên phải) — done: đã tick, verifying: đang xác nhận dở.
  const [current, setCurrent] = useState<{
    name: string;
    code: string;
    time: string;
    score: number;
    liveness: number;
    state: "done" | "verifying";
  } | null>(null);
  const [recent, setRecent] = useState<
    { name: string; code: string; time: string; score: number }[]
  >([]);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [gallery, setGallery] = useState<KioskGalleryStatus | null>(null);
  const [resetting, setResetting] = useState(false);

  const liveQuery = useQuery({
    queryKey: ["teacher-live", classId],
    queryFn: () => getTeacherLiveAttendance(classId),
    enabled: !!classId && !isNaN(classId),
    refetchInterval: 5000,
  });
  const scheduleId = liveQuery.data?.schedule_id ?? null;

  const refreshGallery = useCallback(async () => {
    if (!classId || isNaN(classId)) return;
    try {
      setGallery(await getKioskGalleryStatus(classId));
    } catch {
      // Kiosk vẫn chạy được khi gallery lỗi — checkin sẽ báo gallery_size=0.
    }
  }, [classId]);

  useEffect(() => {
    let mounted = true;
    if (classId && !isNaN(classId)) {
      getKioskGalleryStatus(classId)
        .then((data) => {
          if (mounted) setGallery(data);
        })
        .catch(() => {});
    }
    return () => {
      mounted = false;
    };
  }, [classId]);

  const paint = useCallback((vw: number, vh: number, localBoxes?: LocalFaceBox[]) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const displayWidth = video.clientWidth || canvas.clientWidth || 640;
    const displayHeight = video.clientHeight || canvas.clientHeight || 360;
    if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
      canvas.width = displayWidth;
      canvas.height = displayHeight;
    }
    const cw = canvas.width;
    const ch = canvas.height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, cw, ch);

    if (localBoxes && localBoxes.length > 0) {
      // 1. Chế độ MediaPipe: Toạ độ bám trực tiếp theo khuôn mặt hiện tại (60 FPS, độ trễ 0ms)
      const sx = cw / Math.max(1, vw);
      const sy = ch / Math.max(1, vh);

      for (const b of localBoxes) {
        const x1 = b.x1 * sx;
        const y1 = b.y1 * sy;
        const w = (b.x2 - b.x1) * sx;
        const h = (b.y2 - b.y1) * sy;
        const color = boxColor(b.decision || "UNKNOWN");

        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.strokeRect(x1, y1, w, h);

        const label = boxLabel(b);

        ctx.font = "bold 12px sans-serif";
        const tw = ctx.measureText(label).width + 14;
        ctx.fillStyle = color;
        ctx.fillRect(x1, y1 - 20, tw, 20);
        ctx.fillStyle = "#fff";
        ctx.fillText(label, x1 + 6, y1 - 6);
      }
      return;
    }

    // 2. Chế độ Fallback: Dùng toạ độ server khi MediaPipe chưa sẵn sàng
    const baseW = widthRef.current || 480;
    const baseH = Math.round((baseW * vh) / Math.max(1, vw));
    const sx = cw / baseW;
    const sy = ch / Math.max(1, baseH);
    const cur = boxesRef.current;

    for (const b of cur) {
      if (!b.bbox || b.bbox.length < 4) continue;
      const [x1, y1, x2, y2] = b.bbox;
      const color = boxColor(b.decision);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1 * sx, y1 * sy, (x2 - x1) * sx, (y2 - y1) * sy);
      const label = boxLabel(b);
      ctx.font = "12px sans-serif";
      const tw = ctx.measureText(label).width + 12;
      ctx.fillStyle = color;
      ctx.fillRect(x1 * sx, y1 * sy - 18, tw, 18);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, x1 * sx + 6, y1 * sy - 5);
    }
  }, []);

  const handleFaces = useCallback((faces: KioskFaceBox[], latency: number | null) => {
    if (latency !== null) setLatencyMs(latency);
    // Ổn định decision từng người: SPOOF đơn lẻ bị giữ lại 1 nhịp (lib/kiosk-decisions).
    const nowMs0 = Date.now();
    const stabilized = stabilizeDecisions(faces, stableRef.current, nowMs0);
    setFaces(stabilized);
    boxesRef.current = stabilized;
    const video = videoRef.current;
    if (video && video.videoWidth) paint(video.videoWidth, video.videoHeight);
    const nowStr = new Date().toLocaleTimeString("vi-VN");
    const nowMs = Date.now();
    // Lọc cooldown 12s/người để lịch sử không spam khi đứng yên trước camera.
    const fresh = filterFreshChecked(stabilized, seenAtRef.current, nowMs);
    if (fresh.length > 0) {
      const first = fresh[0];
      fresh.forEach((f) => seenAtRef.current.set(f.user_code || "", nowMs));
      setCurrent({
        name: first.full_name || "",
        code: first.user_code || "",
        time: nowStr,
        score: first.score,
        liveness: first.liveness,
        state: "done",
      });
      setRecent((prev) =>
        [...fresh.map((f) => ({ name: f.full_name || "", code: f.user_code || "", time: nowStr, score: f.score })), ...prev].slice(0, 20)
      );
    } else {
      const verifying = stabilized.find((f) => (f.decision === "VERIFYING" || f.decision === "CHALLENGE") && f.full_name);
      if (verifying) {
        setCurrent({
          name: verifying.full_name || "",
          code: verifying.user_code || "",
          time: nowStr,
          score: verifying.score,
          liveness: verifying.liveness,
          state: "verifying",
        });
      }
    }
  }, [paint]);

  const captureAndSend = useCallback(async () => {
    const video = videoRef.current;
    if (!video || video.readyState < 2 || busyRef.current || !scheduleId) return;
    // Ưu tiên WebSocket (nhanh, rớt frame cũ); HTTP chỉ fallback.
    if (wsOkRef.current && wsRef.current?.readyState === WebSocket.OPEN) return;
    busyRef.current = true;
    try {
      const vw = video.videoWidth;
      const vh = video.videoHeight;
      const targetW = widthRef.current || 480;
      const targetH = Math.round((targetW * vh) / Math.max(1, vw));
      const off = document.createElement("canvas");
      off.width = targetW;
      off.height = targetH;
      off.getContext("2d")?.drawImage(video, 0, 0, targetW, targetH);
      const blob: Blob | null = await new Promise((res) =>
        off.toBlob((b) => res(b), "image/jpeg", 0.6)
      );
      if (!blob) return;
      const t0 = performance.now();
      const res = await kioskCheckin(scheduleId, blob);
      if (res.next_interval_ms) intervalRef.current = res.next_interval_ms;
      if (res.next_width) widthRef.current = res.next_width;
      handleFaces(res.faces, Math.round(performance.now() - t0));
      // Lần quét 2 = check-out: gắn nhãn "(ra)" vào lịch sử để phân biệt giờ vào/ra.
      if (res.checked_out && res.checked_out.length > 0) {
        const nowStr = new Date().toLocaleTimeString("vi-VN");
        const outNames = new Map(
          res.faces
            .filter((f) => f.student_id && res.checked_out!.includes(f.student_id))
            .map((f) => [f.student_id!, f])
        );
        const outs = res.checked_out
          .map((sid) => outNames.get(sid))
          .filter((f): f is NonNullable<typeof f> => !!f);
        if (outs.length > 0) {
          setRecent((prev) =>
            [
              ...outs.map((f) => ({
                name: `${f.full_name || ""} (ra)`,
                code: f.user_code || "",
                time: nowStr,
                score: f.score,
              })),
              ...prev,
            ].slice(0, 20)
          );
        }
      }
    } catch {
      // Bỏ qua lỗi 1 frame (mạng lag) — vòng sau thử lại, không dừng kiosk.
    } finally {
      busyRef.current = false;
    }
  }, [scheduleId, handleFaces]);

  const startCamera = useCallback(async () => {
    setCamError(null);
    // Kiosk chỉ mở khi có tiết (đúng ngày học mới có schedule_id).
    if (!scheduleId) {
      setCamError("Hôm nay lớp không có tiết — điểm danh đang đóng.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      // Khởi tạo trước MediaPipe detector chạy nền
      getClientFaceDetector().then((det) => {
        detectorRef.current = det;
      });
      setRunning(true);
    } catch {
      setCamError("Không mở được camera. Kiểm tra quyền trình duyệt (HTTPS/localhost) và thử lại.");
    }
  }, [scheduleId]);

  const stopCamera = useCallback(() => {
    if (timeoutTimerRef.current) clearTimeout(timeoutTimerRef.current);
    if (nextSendTimerRef.current) clearTimeout(nextSendTimerRef.current);
    inFlightRef.current = false;
    try { wsRef.current?.close(); } catch { /* ignore */ }
    wsRef.current = null;
    wsOkRef.current = false;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setRunning(false);
    setFaces([]);
    boxesRef.current = [];
    localBoxesRef.current = [];
    setCurrent(null);
    const canvas = canvasRef.current;
    canvas?.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  }, []);

  // Render loop 60 FPS: MediaPipe phát hiện vị trí khuôn mặt thời gian thực (0ms delay)
  useEffect(() => {
    if (!running) return;
    let active = true;
    const loop = () => {
      if (!active) return;
      const video = videoRef.current;
      if (video && video.readyState >= 2 && video.videoWidth > 0) {
        const vw = video.videoWidth;
        const vh = video.videoHeight;
        const detector = detectorRef.current;

        if (detector) {
          try {
            const now = performance.now();
            const res = detector.detectForVideo(video, now);
            const detections = res.detections || [];
            const baseW = widthRef.current || 480;
            const baseH = Math.round((baseW * vh) / vw);
            const rawLocal: LocalFaceBox[] = detections.map((d: Detection) => {
              const bb = d.boundingBox;
              const ox = bb?.originX ?? 0;
              const oy = bb?.originY ?? 0;
              const w = bb?.width ?? 0;
              const h = bb?.height ?? 0;
              return {
                x1: ox,
                y1: oy,
                x2: ox + w,
                y2: oy + h,
                score: d.categories?.[0]?.score ?? 0.8,
              };
            });
            // Khớp nhãn danh tính từ server vào các local box
            const matched = matchServerIdentities(
              rawLocal,
              boxesRef.current,
              baseW,
              baseH,
              vw,
              vh,
              localBoxesRef.current
            );
            localBoxesRef.current = matched;
            paint(vw, vh, matched);
          } catch {
            paint(vw, vh);
          }
        } else {
          // Fallback: vẽ box từ server nếu MediaPipe chưa tải xong
          paint(vw, vh);
        }
      }
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => {
      active = false;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [running, paint]);

  // WebSocket chính (Ping-Pong 1-in-flight: không dồn frame, đo RTT chuẩn)
  useEffect(() => {
    if (!running || !scheduleId) return;
    let dead = false;
    let ws: WebSocket | null = null;
    const token = getToken();
    if (!token) return;
    try {
      ws = new WebSocket(kioskWsUrl(scheduleId));
      wsRef.current = ws;
    } catch {
      wsOkRef.current = false;
      return;
    }

    const sendFrame = () => {
      if (dead) return;
      const video = videoRef.current;
      if (!video || video.readyState < 2 || ws?.readyState !== WebSocket.OPEN) return;
      if (inFlightRef.current) return; // Tuyệt đối không gửi chồng frame khi frame trước đang xử lý

      inFlightRef.current = true;
      sentAtRef.current = performance.now();

      // Timeout an toàn 2s để tránh kẹt nếu server bị mất kết nối đột ngột
      if (timeoutTimerRef.current) clearTimeout(timeoutTimerRef.current);
      timeoutTimerRef.current = setTimeout(() => {
        inFlightRef.current = false;
        if (!dead && ws?.readyState === WebSocket.OPEN) {
          sendFrame();
        }
      }, 2000);

      const vw = video.videoWidth || 640;
      const vh = video.videoHeight || 480;
      const targetW = widthRef.current || 480;
      const targetH = Math.round((targetW * vh) / Math.max(1, vw));
      const off = document.createElement("canvas");
      off.width = targetW;
      off.height = targetH;
      const ctx = off.getContext("2d", { willReadFrequently: true });
      ctx?.drawImage(video, 0, 0, targetW, targetH);
      off.toBlob(
        (blob) => {
          if (blob && ws?.readyState === WebSocket.OPEN && !dead) {
            ws.send(blob);
          } else {
            inFlightRef.current = false;
          }
        },
        "image/jpeg",
        0.6
      );
    };

    ws.onopen = () => {
      if (dead) return;
      wsOkRef.current = true;
      inFlightRef.current = false;
      sendFrame();
    };

    ws.onmessage = (ev) => {
      if (dead) return;
      try {
        const msg = JSON.parse(ev.data);
        if (msg.error) return;
        if (timeoutTimerRef.current) clearTimeout(timeoutTimerRef.current);
        inFlightRef.current = false;

        // Tính độ trễ RTT thực tế của frame vừa nhận
        const now = performance.now();
        const rtt = sentAtRef.current > 0 ? Math.round(now - sentAtRef.current) : (msg.infer_ms ?? null);
        if (msg.next_interval_ms) intervalRef.current = msg.next_interval_ms;
        if (msg.next_width) widthRef.current = msg.next_width;

        handleFaces(msg.faces || [], rtt);

        // Đã đủ check-in + check-out: hiện trạng thái hoàn thành thay vì tick lại.
        if (msg.already_done && msg.already_done.length > 0) {
          const doneMap = new Map(
            (msg.faces || [])
              .filter((f: KioskFaceBox) => f.student_id && msg.already_done.includes(f.student_id))
              .map((f: KioskFaceBox) => [f.student_id!, f])
          );
          const firstDone = msg.already_done
            .map((sid: number) => doneMap.get(sid))
            .find((f: KioskFaceBox | undefined) => !!f);
          if (firstDone) {
            setCurrent({
              name: firstDone.full_name || "",
              code: `${firstDone.user_code || ""} · đã đủ 2 lượt`,
              time: new Date().toLocaleTimeString("vi-VN"),
              score: firstDone.score,
              liveness: firstDone.liveness,
              state: "done",
            });
          }
        }

        // Ping-Pong: sau khi nhận kết quả, gửi frame tiếp theo sau khoảng throttle ngắn
        const throttle = Math.max(30, Math.min(intervalRef.current || 150, 120));
        if (nextSendTimerRef.current) clearTimeout(nextSendTimerRef.current);
        nextSendTimerRef.current = setTimeout(sendFrame, throttle);
      } catch {
        inFlightRef.current = false;
      }
    };

    ws.onclose = () => {
      wsOkRef.current = false;
      inFlightRef.current = false;
    };
    ws.onerror = () => {
      wsOkRef.current = false;
      inFlightRef.current = false;
    };

    return () => {
      dead = true;
      if (timeoutTimerRef.current) clearTimeout(timeoutTimerRef.current);
      if (nextSendTimerRef.current) clearTimeout(nextSendTimerRef.current);
      try { ws?.close(); } catch { /* ignore */ }
      if (wsRef.current === ws) { wsRef.current = null; wsOkRef.current = false; }
    };
  }, [running, scheduleId, handleFaces]);

  useEffect(() => {
    if (running && scheduleId && !wsOkRef.current) {
      // Fallback HTTP khi chưa có WS: dùng interval adaptive.
      timerRef.current = setInterval(captureAndSend, intervalRef.current || FALLBACK_POLL_MS);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [running, scheduleId, captureAndSend]);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const handleReset = async () => {
    if (!scheduleId) return;
    setResetting(true);
    try {
      await kioskResetSession(scheduleId);
      setRecent([]);
      setCurrent(null);
    } finally {
      setResetting(false);
    }
  };

  return (
    <RoleGuard allowedRoles={["TEACHER"]}>
      <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4 sm:space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-4 sm:pb-5 border-b border-slate-200">
          <div className="min-w-0 flex-1">
            <Link
              href={`/teacher/classes/${classId}/live`}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors mb-2"
            >
              <ArrowLeft size={14} />
              <span>Về trang điểm danh trực tiếp</span>
            </Link>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
                <ScanFace size={24} className="text-emerald-600" />
                Kiosk điểm danh khuôn mặt
              </h1>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {liveQuery.data
                ? `${liveQuery.data.class_code} – ${liveQuery.data.course_name} · Ca ${liveQuery.data.start_time || "--"}–${liveQuery.data.end_time || "--"} · Phòng ${liveQuery.data.room_name || "?"}`
                : "Đang tải thông tin buổi học..."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto shrink-0">
            {!running ? (
              <button
                onClick={startCamera}
                disabled={!scheduleId}
                className="inline-flex items-center justify-center gap-1.5 min-h-[40px] px-4 py-2 rounded-md text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title={!scheduleId ? "Hôm nay lớp không có tiết — điểm danh đang đóng" : "Mở camera điểm danh"}
              >
                <Camera size={15} />
                Mở camera
              </button>
            ) : (
              <button
                onClick={stopCamera}
                className="inline-flex items-center justify-center gap-1.5 min-h-[40px] px-4 py-2 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 transition-colors"
              >
                <CameraOff size={15} />
                Dừng
              </button>
            )}
            <button
              onClick={handleReset}
              disabled={!scheduleId || resetting}
              className="inline-flex items-center justify-center gap-1.5 min-h-[40px] px-3.5 py-2 rounded-md text-xs sm:text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 transition-colors disabled:opacity-50"
              title="Xoá trạng thái voting trong RAM (dùng khi đổi ca)"
            >
              <RotateCcw size={13} />
              Reset ca
            </button>
          </div>
        </div>

        {camError && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center gap-2">
            <TriangleAlert size={15} />
            {camError}
          </div>
        )}
        {!scheduleId && !liveQuery.isPending && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm">
            Hôm nay lớp không có tiết — điểm danh đang đóng. Kiosk chỉ mở vào ngày có
            buổi học. Mỗi người tối đa 2 lượt: quét lần 1 là giờ vào, quét lần 2 là giờ ra.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Camera + overlay */}
          <div className="lg:col-span-2 bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <div className="relative bg-slate-900 w-full aspect-video flex items-center justify-center overflow-hidden">
              <video
                ref={videoRef}
                muted
                playsInline
                className="w-full h-full object-cover"
              />
              <canvas
                ref={canvasRef}
                className="absolute inset-0 w-full h-full pointer-events-none"
              />
              {!running && (
                <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm">
                  Bấm “Mở camera” để bắt đầu quét
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-xs text-slate-500 border-t border-slate-100 font-mono tabular-nums">
              <span className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${running ? "bg-emerald-500 animate-pulse" : "bg-slate-300"}`} />
                {running ? "Đang quét" : "Đã dừng"}
              </span>
              <span>Độ trễ: {latencyMs !== null ? `${latencyMs}ms` : "--"}</span>
              <span>Mặt thấy: {faces.length}</span>
              <span>Gallery: {gallery ? `${gallery.enrolled}/${gallery.total} SV` : "--"}</span>
            </div>
          </div>

          {/* Cột phải: thông tin SV vừa nhận diện + lịch sử bên dưới */}
          <div className="space-y-4">
            {/* Thẻ SV vừa nhận diện */}
            <div
              className={`bg-white rounded-lg border shadow-sm p-4 ${
                current?.state === "done"
                  ? "border-emerald-200"
                  : current?.state === "verifying"
                    ? "border-amber-200"
                    : "border-slate-200"
              }`}
            >
              <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5 mb-3">
                <UserRound size={14} className="text-slate-500" />
                Sinh viên vừa nhận diện
              </h2>
              {current ? (
                <div className="flex items-start gap-3">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center text-base font-bold shrink-0 ${
                      current.state === "done"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700 animate-pulse"
                    }`}
                  >
                    {current.name.trim().charAt(0).toUpperCase() || "?"}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-900 truncate">{current.name}</p>
                    <p className="font-mono tabular-nums text-xs text-slate-500">
                      {current.code} · {current.time}
                    </p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold border ${
                          current.state === "done"
                            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                            : "bg-amber-50 text-amber-700 border-amber-200"
                        }`}
                      >
                        <CircleCheck size={11} />
                        {current.state === "done" ? "Đã điểm danh" : "Đang xác nhận..."}
                      </span>
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono tabular-nums bg-slate-100 text-slate-600">
                        {(current.score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-slate-400">
                  {running ? "Hướng camera về phía cửa — SV đi qua sẽ hiện ở đây." : "Mở camera để bắt đầu quét."}
                </p>
              )}
            </div>

            {/* Lịch sử điểm danh trong ca */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4">
              <h2 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5 mb-2">
                <History size={14} className="text-slate-500" />
                Lịch sử
                {recent.length > 0 && (
                  <span className="ml-auto font-mono tabular-nums text-[11px] text-slate-400">
                    {recent.length}
                  </span>
                )}
              </h2>
              {recent.length === 0 ? (
                <p className="text-xs text-slate-400">Chưa có lượt nào trong ca này.</p>
              ) : (
                <ul className="space-y-1.5 max-h-64 overflow-y-auto pr-0.5">
                  {recent.map((r, i) => (
                    <li
                      key={`${r.code}-${r.time}-${i}`}
                      className="flex items-center justify-between gap-2 text-xs px-2 py-1.5 rounded bg-emerald-50/60 border border-emerald-100"
                    >
                      <span className="font-medium text-slate-900 truncate">
                        {r.name} <span className="font-mono font-normal text-slate-500">{r.code}</span>
                      </span>
                      <span className="font-mono tabular-nums text-slate-500 shrink-0">{r.time}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Trạng thái gallery gọn — ảnh FaceID do admin đăng ký */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Dữ liệu khuôn mặt
                </h2>
                <button
                  onClick={refreshGallery}
                  className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                  title="Làm mới"
                >
                  <RefreshCw size={13} />
                </button>
              </div>
              <p className="text-xs text-slate-600">
                Đã đăng ký{" "}
                <strong className="font-mono">
                  {gallery ? `${gallery.enrolled}/${gallery.total}` : "--"}
                </strong>{" "}
                SV.
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                Ảnh khuôn mặt do Quản trị viên đăng ký ở trang Quản lý người dùng. SV chưa đăng ký
                vẫn vào lớp bình thường, GV tick tay.
              </p>
            </div>
          </div>
        </div>
      </div>
    </RoleGuard>
  );
}
