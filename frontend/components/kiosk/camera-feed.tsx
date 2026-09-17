"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Camera, CameraOff, Wifi, WifiOff, Activity, AlertCircle, RefreshCw } from "lucide-react";
import { WS, recordKioskAttendance, type KioskRecordResponse } from "@/lib/api";

export interface DetectionResult {
  tracker_id: number;
  bbox: number[]; // [x1, y1, x2, y2]
  student: string; // student code or "unknown"
  name: string;
  class_name: string;
  score: number;
  uniform: string; // "ok" or "violation" or other
  violations: string[];
  log: boolean;
}

export interface CameraFeedProps {
  currentRoom: string;
  onScanSuccess: (data: KioskRecordResponse) => void;
  onScanError?: (errorData: { student_code: string; error_message: string; room_name: string }) => void;
  cooldownSeconds?: number;
}

const COLOR_EMERALD = "#10b981";
const COLOR_AMBER = "#f59e0b";
const COLOR_ROSE = "#f43f5e";
const COLOR_SLATE = "#94a3b8";

export function CameraFeed({
  currentRoom,
  onScanSuccess,
  onScanError,
  cooldownSeconds = 12,
}: CameraFeedProps) {
  const [cameraActive, setCameraActive] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [inferMs, setInferMs] = useState(0);
  const [fps, setFps] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const boxesRef = useRef<DetectionResult[]>([]);

  // Cooldown & In-flight maps (student_code -> last_scan_timestamp)
  const cooldownMapRef = useRef<Map<string, number>>(new Map());
  const inFlightSetRef = useRef<Set<string>>(new Set());

  // FPS tracking
  const frameCountRef = useRef(0);
  const lastFpsTimeRef = useRef(Date.now());
  const stopRequestedRef = useRef(false);

  // Helper to check cooldown
  const isStudentInCooldown = useCallback(
    (code: string): boolean => {
      const last = cooldownMapRef.current.get(code);
      if (!last) return false;
      const elapsed = (Date.now() - last) / 1000;
      return elapsed < cooldownSeconds;
    },
    [cooldownSeconds]
  );

  // Trigger Kiosk Check-in/Check-out API
  const handleKioskRecord = useCallback(
    async (detection: DetectionResult) => {
      const code = detection.student;
      if (!code || code === "unknown") return;
      if (inFlightSetRef.current.has(code) || isStudentInCooldown(code)) return;

      inFlightSetRef.current.add(code);

      try {
        const payload = {
          room_name: currentRoom,
          student_code: code,
          has_uniform: detection.uniform === "ok",
          timestamp: new Date().toISOString(),
        };

        const res = await recordKioskAttendance(payload);
        cooldownMapRef.current.set(code, Date.now());
        onScanSuccess(res);
      } catch (err: unknown) {
        // Cooldown for 6 seconds on error to prevent request flooding
        cooldownMapRef.current.set(code, Date.now() - (cooldownSeconds - 6) * 1000);
        const errMsg = err instanceof Error ? err.message : "Điểm danh không thành công";
        onScanError?.({
          student_code: code,
          error_message: errMsg,
          room_name: currentRoom,
        });
      } finally {
        inFlightSetRef.current.delete(code);
      }
    },
    [currentRoom, isStudentInCooldown, onScanSuccess, onScanError, cooldownSeconds]
  );

  // Smooth overlay drawing loop using requestAnimationFrame
  useEffect(() => {
    let animationFrameId = 0;
    const interpolatedBoxes = new Map<number, number[]>();

    const draw = () => {
      animationFrameId = requestAnimationFrame(draw);
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.videoWidth === 0) return;

      // Match canvas resolution to video stream
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Model coordinates are calculated on 640x480
      const sx = canvas.width / 640;
      const sy = canvas.height / 480;

      const currentDetections = boxesRef.current;
      const activeIds = new Set(currentDetections.map((d) => d.tracker_id));

      // Remove stale trackers from cache
      for (const tid of Array.from(interpolatedBoxes.keys())) {
        if (!activeIds.has(tid)) {
          interpolatedBoxes.delete(tid);
        }
      }

      ctx.lineWidth = 2.5;

      for (const det of currentDetections) {
        if (!det.bbox || det.bbox.length < 4) continue;

        // Smooth position interpolation (0.35 factor)
        const prev = interpolatedBoxes.get(det.tracker_id) ?? det.bbox;
        const smoothBox = prev.map((val, idx) => val + (det.bbox[idx] - val) * 0.35);
        interpolatedBoxes.set(det.tracker_id, smoothBox);

        const x1 = smoothBox[0] * sx;
        const y1 = smoothBox[1] * sy;
        const x2 = smoothBox[2] * sx;
        const y2 = smoothBox[3] * sy;
        const w = x2 - x1;
        const h = y2 - y1;

        const isKnown = det.student && det.student !== "unknown";
        const isUniformOk = det.uniform === "ok";

        let strokeColor = COLOR_SLATE;
        if (isKnown) {
          strokeColor = isUniformOk ? COLOR_EMERALD : COLOR_ROSE;
        } else if (det.uniform === "violation") {
          strokeColor = COLOR_AMBER;
        }

        // Draw Bounding Box
        ctx.strokeStyle = strokeColor;
        ctx.beginPath();
        // Corner-accented rounded box
        ctx.strokeRect(x1, y1, w, h);

        // Header Label Tag
        const labelName = det.name || (isKnown ? det.student : "Đang nhận diện...");
        const labelStatus = isUniformOk ? "Đồng phục đạt" : "Sai đồng phục";
        const labelScore = det.score > 0 ? ` ${(det.score * 100).toFixed(0)}%` : "";
        const tagText = `${labelName} • ${labelStatus}${labelScore}`;

        ctx.font = "600 12px ui-sans-serif, system-ui, sans-serif";
        const textWidth = ctx.measureText(tagText).width;
        const tagHeight = 22;
        const tagY = Math.max(tagHeight, y1);

        // Label Background
        ctx.fillStyle = strokeColor;
        ctx.fillRect(x1 - 1, tagY - tagHeight, textWidth + 16, tagHeight);

        // Label Text
        ctx.fillStyle = "#ffffff";
        ctx.fillText(tagText, x1 + 6, tagY - 6);
      }
    };

    animationFrameId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  // Stop all camera and websocket resources
  const stopStreaming = useCallback(() => {
    stopRequestedRef.current = true;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    boxesRef.current = [];
    setCameraActive(false);
    setWsConnected(false);
  }, []);

  // Initialize Webcam & WebSocket connection
  const startStreaming = useCallback(async () => {
    stopRequestedRef.current = false;
    setErrorMessage(null);

    try {
      // 1. Get Camera MediaStream
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
        audio: false,
      });

      if (stopRequestedRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await new Promise<void>((resolve) => {
          if (!videoRef.current) return resolve();
          videoRef.current.onloadedmetadata = () => resolve();
        });
        await videoRef.current.play().catch(() => {});
        setCameraActive(true);
      }

      // 2. Connect WebSocket to backend inference pipeline
      const wsUrl = WS || "ws://localhost:8000/ws/attendance/webcam";
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!stopRequestedRef.current) {
          setWsConnected(true);
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
      };

      socket.onerror = () => {
        setWsConnected(false);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const results: DetectionResult[] = data.results || [];
          boxesRef.current = results;

          if (typeof data.infer_ms === "number") {
            setInferMs(data.infer_ms);
          }

          // Count frame for FPS calculation
          frameCountRef.current += 1;
          const now = Date.now();
          if (now - lastFpsTimeRef.current >= 1000) {
            setFps(frameCountRef.current);
            frameCountRef.current = 0;
            lastFpsTimeRef.current = now;
          }

          // Auto-trigger attendance for detected valid students
          for (const det of results) {
            if (det.log || (det.student && det.student !== "unknown")) {
              handleKioskRecord(det);
            }
          }
        } catch {
          // Ignore parsing errors
        }
      };

      // Wait for socket to open
      await new Promise<void>((resolve) => {
        if (socket.readyState === WebSocket.OPEN) return resolve();
        socket.addEventListener("open", () => resolve(), { once: true });
        setTimeout(() => resolve(), 3000); // 3s fallback timeout
      });

      // 3. Frame transmission loop (offscreen canvas -> JPEG Blob -> WebSocket)
      const captureCanvas = document.createElement("canvas");
      captureCanvas.width = 640;
      captureCanvas.height = 480;
      const captureCtx = captureCanvas.getContext("2d");

      const sendFrameLoop = () => {
        if (stopRequestedRef.current || !videoRef.current) return;

        if (
          socket.readyState === WebSocket.OPEN &&
          videoRef.current.videoWidth > 0 &&
          captureCtx
        ) {
          captureCtx.drawImage(videoRef.current, 0, 0, 640, 480);
          captureCanvas.toBlob(
            (blob) => {
              if (
                !stopRequestedRef.current &&
                socket.readyState === WebSocket.OPEN &&
                blob
              ) {
                socket.send(blob);
              }
              // Throttle to ~8-10 FPS transmission to conserve client/server CPU
              setTimeout(sendFrameLoop, 110);
            },
            "image/jpeg",
            0.6
          );
        } else {
          setTimeout(sendFrameLoop, 200);
        }
      };

      sendFrameLoop();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Không thể truy cập camera";
      setErrorMessage(msg);
      stopStreaming();
    }
  }, [handleKioskRecord, stopStreaming]);

  // Manage lifecycle: start on mount, clean up on unmount or tab switch
  useEffect(() => {
    startStreaming();

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopStreaming();
      } else {
        startStreaming();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      stopStreaming();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [startStreaming, stopStreaming]);

  return (
    <div className="relative flex flex-col items-center justify-center overflow-hidden rounded-xl border border-slate-800 bg-slate-950 shadow-2xl">
      {/* Video Stream + Smooth Canvas Overlay */}
      <div className="relative aspect-4/3 w-full max-w-4xl bg-black overflow-hidden rounded-lg">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="h-full w-full object-cover"
        />
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full"
        />

        {/* Camera Off / Error Fallback Screen */}
        {(!cameraActive || errorMessage) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 text-slate-300 p-6 text-center">
            <CameraOff className="h-12 w-12 text-slate-500 mb-3" />
            <p className="text-sm font-medium text-slate-300">
              {errorMessage || "Camera chưa được kích hoạt hoặc bị chặn quyền truy cập"}
            </p>
            <button
              onClick={() => startStreaming()}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-500 transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
              Thử lại kết nối
            </button>
          </div>
        )}

        {/* Live HUD Status Overlays */}
        <div className="pointer-events-none absolute top-3 left-3 flex flex-wrap items-center gap-2 text-xs font-mono tabular-nums">
          {/* WS Stream Status */}
          <div className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 border backdrop-blur-sm ${
            wsConnected
              ? "bg-slate-900/85 border-emerald-800/80 text-emerald-400"
              : "bg-slate-900/85 border-rose-800/80 text-rose-400"
          }`}>
            {wsConnected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
            <span>{wsConnected ? "AI ONLINE" : "DISCONNECTED"}</span>
          </div>

          {/* Infer Latency Metric */}
          <div className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 border backdrop-blur-sm ${
            inferMs > 400
              ? "bg-slate-900/85 border-amber-800/80 text-amber-400"
              : "bg-slate-900/85 border-slate-700/80 text-slate-300"
          }`}>
            <Activity className="h-3.5 w-3.5 text-slate-400" />
            <span>AI: {inferMs}ms</span>
          </div>

          {/* FPS Counter */}
          <div className="inline-flex items-center rounded-md bg-slate-900/85 border border-slate-700/80 px-2 py-1 text-slate-400 backdrop-blur-sm">
            <span>{fps} FPS</span>
          </div>
        </div>

        {/* Room Watermark Tag */}
        <div className="pointer-events-none absolute bottom-3 left-3 rounded-md bg-slate-900/80 border border-slate-800 px-2.5 py-1 text-[11px] font-medium text-slate-400 backdrop-blur-sm">
          Phòng: <span className="font-mono text-slate-200 font-semibold">{currentRoom}</span>
        </div>
      </div>
    </div>
  );
}
