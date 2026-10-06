"use client";

import React, { useEffect, useState } from "react";
import { fetchAuthedFileUrl, isPrivateFileUrl, mediaUrl, type AdminUser, type User } from "./http";

type AvatarSize = "sm" | "md" | "lg" | "xl";

const SIZE_CLASS: Record<AvatarSize, string> = {
  sm: "h-8 w-8 text-[10px]",
  md: "h-10 w-10 text-xs",
  lg: "h-16 w-16 text-sm",
  xl: "h-24 w-24 text-xl",
};

const DOT_SIZE: Record<AvatarSize, string> = {
  sm: "h-2.5 w-2.5",
  md: "h-3 w-3",
  lg: "h-3.5 w-3.5",
  xl: "h-4 w-4",
};

function initialsOf(name?: string | null, fallback?: string | null): string {
  const base = (name || fallback || "?").trim();
  if (!base) return "?";
  return (
    base
      .split(/\s+/)
      .slice(-2)
      .map((w) => w[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}

interface UserAvatarProps {
  user?: AdminUser | User | null;
  /** Ghi đè src hiển thị (dùng cho preview blob trong modal). */
  src?: string | null;
  name?: string | null;
  size?: AvatarSize;
  showStatusDot?: boolean;
  /** Trạng thái online/offline: khi truyền vào sẽ thay chấm FaceID bằng chấm presence. */
  presence?: "online" | "offline" | null;
  className?: string;
}

/**
 * Avatar mặc định toàn hệ thống: có ảnh thì hiện ảnh tròn, chưa có ảnh thì
 * vòng tròn xanh đặc + initials trắng (2 ký tự cuối của họ tên).
 * Avatar đọc qua /api/v1/files/avatar (auth) nên fetch blob có token
 * (giống AuthedSnapshotImg); <img src> trần không kèm token sẽ 401.
 */
export function UserAvatar({
  user,
  src,
  name,
  size = "md",
  showStatusDot = true,
  presence = null,
  className = "",
}: UserAvatarProps) {
  const rawSrc = src !== undefined ? src : user?.avatar_url ?? null;
  const needsAuth = !!rawSrc && isPrivateFileUrl(rawSrc);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let url: string | null = null;
    if (!needsAuth || !rawSrc) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync reset when no authed fetch needed; fetch path sets state in async callback
      setObjectUrl(null);
      return;
    }
    fetchAuthedFileUrl(rawSrc)
      .then((u) => {
        if (cancelled) {
          window.URL.revokeObjectURL(u);
          return;
        }
        url = u;
        setObjectUrl(u);
      })
      .catch(() => {
        if (!cancelled) setObjectUrl(null);
      });
    return () => {
      cancelled = true;
      if (url) window.URL.revokeObjectURL(url);
    };
  }, [rawSrc, needsAuth]);

  const resolvedSrc = needsAuth ? objectUrl : mediaUrl(rawSrc);
  const displayName = name ?? user?.full_name ?? user?.user_code ?? "?";
  const hasAvatar = Boolean(resolvedSrc);
  const initials = initialsOf(displayName, user?.user_code);

  return (
    <span className={`relative inline-flex shrink-0 ${className}`} title={displayName}>
      {resolvedSrc ? (
        // eslint-disable-next-line @next/next/no-img-element -- blob: URL cannot be optimized by next/image
        <img
          src={resolvedSrc}
          alt={displayName}
          loading="lazy"
          className={`${SIZE_CLASS[size]} rounded-full object-cover ring-2 ring-white shadow-sm border border-slate-200 bg-slate-100`}
        />
      ) : (
        <span
          aria-label={displayName}
          className={`${SIZE_CLASS[size]} inline-flex items-center justify-center rounded-full bg-blue-600 text-white font-bold ring-2 ring-white shadow-sm`}
        >
          {initials}
        </span>
      )}
      {presence ? (
        <span
          title={presence === "online" ? "Đang online" : "Ngoại tuyến"}
          className={`absolute -bottom-0.5 -right-0.5 ${DOT_SIZE[size]} rounded-full border-2 border-white ${
            presence === "online" ? "bg-emerald-500" : "bg-slate-400"
          }`}
        />
      ) : (
        showStatusDot && (
          <span
            title={hasAvatar ? "Đã có ảnh / FaceID" : "Chưa có ảnh"}
            className={`absolute -bottom-0.5 -right-0.5 ${DOT_SIZE[size]} rounded-full border-2 border-white ${
              hasAvatar ? "bg-emerald-500" : "bg-slate-300"
            }`}
          />
        )
      )}
    </span>
  );
}
