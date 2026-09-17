"use client";

import React, { useEffect, useRef, useState } from "react";
import { CheckCircle2, AlertTriangle, XCircle, Clock, ShieldCheck, ShieldAlert, UserCheck } from "lucide-react";
import type { KioskRecordResponse } from "@/lib/api";

export interface AttendanceResultCardProps {
  result: (KioskRecordResponse & { violations?: string[]; error?: string }) | null;
  onDismiss?: () => void;
  autoDismissMs?: number;
}

/**
 * Pure Web Audio API tone generator for audio feedback.
 * No external mp3 files required.
 */
export function playKioskAudioFeedback(type: "success" | "warning" | "error"): void {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;

    const ctx = new AudioCtx();
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.connect(gain);
    gain.connect(ctx.destination);

    if (type === "success") {
      // Pleasant sweep 800Hz -> 1200Hz
      osc.type = "sine";
      osc.frequency.setValueAtTime(800, now);
      osc.frequency.exponentialRampToValueAtTime(1200, now + 0.12);

      gain.gain.setValueAtTime(0.01, now);
      gain.gain.linearRampToValueAtTime(0.18, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);

      osc.start(now);
      osc.stop(now + 0.2);
    } else {
      // Warning / Error low buzz 300Hz
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(300, now);

      gain.gain.setValueAtTime(0.01, now);
      gain.gain.linearRampToValueAtTime(0.15, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);

      osc.start(now);
      osc.stop(now + 0.3);
    }
  } catch {
    // Ignore audio permission or browser restriction errors silently
  }
}

export function AttendanceResultCard({
  result,
  onDismiss,
  autoDismissMs = 4000,
}: AttendanceResultCardProps) {
  const [progress, setProgress] = useState(100);
  const lastPlayedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!result) {
      setProgress(100);
      return;
    }

    // Play corresponding beep tone once per new scan result
    const resultKey = `${result.student_code}_${result.time || result.check_in_time || result.check_out_time || Date.now()}`;
    if (lastPlayedIdRef.current !== resultKey) {
      lastPlayedIdRef.current = resultKey;
      if (result.error) {
        playKioskAudioFeedback("error");
      } else if (!result.has_uniform) {
        playKioskAudioFeedback("warning");
      } else {
        playKioskAudioFeedback("success");
      }
    }

    // Auto-dismiss countdown
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, 100 - (elapsed / autoDismissMs) * 100);
      setProgress(remaining);

      if (elapsed >= autoDismissMs) {
        clearInterval(interval);
        onDismiss?.();
      }
    }, 40);

    return () => clearInterval(interval);
  }, [result, autoDismissMs, onDismiss]);

  if (!result) return null;

  const isError = Boolean(result.error);
  const isCheckIn = result.type === "CHECK_IN";
  const isCheckOut = result.type === "CHECK_OUT";
  const isLate = result.status === "LATE";
  const isUniformOk = result.has_uniform;

  // Format timestamp for display
  const rawTime = result.time || result.check_out_time || result.check_in_time || new Date().toISOString();
  let displayTime = "--:--:--";
  try {
    const d = new Date(rawTime);
    displayTime = d.toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    displayTime = new Date().toLocaleTimeString();
  }

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-700/80 bg-slate-900/95 p-5 text-slate-100 shadow-2xl transition-all duration-300">
      {/* Top Banner: Transaction Badge + Time */}
      <div className="flex items-center justify-between gap-2 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          {isError ? (
            <span className="inline-flex items-center gap-1.5 rounded border border-rose-800/80 bg-rose-950/60 px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-rose-300">
              <XCircle className="h-3.5 w-3.5 text-rose-400" />
              Lỗi xác thực
            </span>
          ) : isCheckIn ? (
            <span className="inline-flex items-center gap-1.5 rounded border border-emerald-700/80 bg-emerald-950/60 px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
              CHECK-IN (VÀO LỚP)
            </span>
          ) : isCheckOut ? (
            <span className="inline-flex items-center gap-1.5 rounded border border-blue-700/80 bg-blue-950/60 px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-blue-300">
              <span className="h-2 w-2 rounded-full bg-blue-400" />
              CHECK-OUT (TAN LỚP)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-300">
              GHI NHẬN ĐIỂM DANH
            </span>
          )}

          {isLate && !isError && (
            <span className="inline-flex items-center rounded border border-amber-800/80 bg-amber-950/60 px-2 py-0.5 text-[11px] font-medium text-amber-300">
              Đi muộn
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 text-xs font-mono tabular-nums text-slate-400">
          <Clock className="h-3.5 w-3.5 text-slate-500" />
          <span>{displayTime}</span>
        </div>
      </div>

      {/* Main Student Info */}
      <div className="mt-4 flex items-start gap-4">
        {/* Avatar / Icon Badge */}
        <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border font-bold text-lg ${
          isError
            ? "border-rose-700 bg-rose-950/50 text-rose-300"
            : !isUniformOk
            ? "border-amber-700 bg-amber-950/50 text-amber-300"
            : "border-emerald-700 bg-emerald-950/50 text-emerald-300"
        }`}>
          {isError ? (
            <XCircle className="h-7 w-7 text-rose-400" />
          ) : (
            <UserCheck className="h-7 w-7 text-emerald-400" />
          )}
        </div>

        {/* Identity Details */}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-white">
            {result.student_name || "Chưa xác định"}
          </h3>
          <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs">
            <span className="font-mono tabular-nums font-medium text-slate-300 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/60">
              {result.student_code}
            </span>
            {result.class_code && (
              <span className="text-slate-400">
                Lớp: <span className="text-slate-200 font-medium">{result.class_code}</span>
              </span>
            )}
            {result.room_name && (
              <span className="text-slate-400">
                Phòng: <span className="text-slate-200 font-medium">{result.room_name}</span>
              </span>
            )}
          </div>

          {/* Error description if any */}
          {result.error && (
            <p className="mt-2 text-xs text-rose-300 bg-rose-950/40 p-2 rounded border border-rose-800/40">
              {result.error}
            </p>
          )}
        </div>
      </div>

      {/* Uniform Status Section */}
      {!isError && (
        <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/70 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Trạng thái đồng phục:</span>
            {isUniformOk ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-950/80 px-2.5 py-0.5 text-xs font-medium text-emerald-300 border border-emerald-800/60">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                ĐÚNG ĐỒNG PHỤC
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-950/80 px-2.5 py-0.5 text-xs font-medium text-rose-300 border border-rose-800/60">
                <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
                VI PHẠM TÁC PHONG
              </span>
            )}
          </div>

          {/* Violations detail if any */}
          {!isUniformOk && result.violations && result.violations.length > 0 && (
            <div className="mt-2 text-[11px] text-rose-400/90 flex items-start gap-1">
              <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
              <span>Phát hiện: {result.violations.join(", ")}</span>
            </div>
          )}
        </div>
      )}

      {/* Auto-dismissing Progress Line */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-slate-800">
        <div
          className={`h-full transition-all ease-linear ${
            isError ? "bg-rose-500" : !isUniformOk ? "bg-amber-500" : "bg-emerald-500"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
