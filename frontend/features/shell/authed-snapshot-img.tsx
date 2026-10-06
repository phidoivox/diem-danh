"use client";

import React, { useEffect, useState } from "react";
import { fetchAuthedFileUrl, isPrivateFileUrl, mediaUrl } from "./http";

/** Thumbnail snapshot có auth: URL public (Supabase/cloud) dùng <img> trực
 * tiếp; URL /api/v1/files/* fetch blob có token rồi hiển thị object URL.
 * Click mở tab mới cũng qua blob (link trần không kèm token sẽ 401). */
export function AuthedSnapshotImg({
  src,
  alt,
  className,
  linkTitle,
}: {
  src: string;
  alt: string;
  className?: string;
  linkTitle?: string;
}) {
  const needsAuth = isPrivateFileUrl(src);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let url: string | null = null;
    if (!needsAuth) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync reset when no authed fetch needed; fetch path sets state in async callback
      setObjectUrl(null);
      return;
    }
    fetchAuthedFileUrl(src)
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
  }, [src, needsAuth]);

  const displaySrc = needsAuth ? objectUrl : mediaUrl(src);
  if (needsAuth && !objectUrl) {
    return (
      <span
        className="inline-block rounded border border-slate-200 bg-slate-100 animate-pulse"
        title="Đang tải ảnh..."
        style={{ width: 40, height: 40 }}
      />
    );
  }
  return (
    <a
      href={displaySrc || undefined}
      target="_blank"
      rel="noreferrer"
      title={linkTitle}
      className="inline-block"
      onClick={
        needsAuth
          ? (e) => {
              // Blob URL đã có auth nên mở trực tiếp, chặn href gốc.
              e.preventDefault();
              if (displaySrc) window.open(displaySrc, "_blank", "noopener");
            }
          : undefined
      }
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={displaySrc || undefined} alt={alt} className={className} loading="lazy" />
    </a>
  );
}
