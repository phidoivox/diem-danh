"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, X, FileText } from "lucide-react";
import { validateUploadFile } from "@/lib/validation";

interface FileDropzoneProps {
  value: File | null;
  onChange: (file: File | null) => void;
  accept?: Record<string, string[]>;
  maxSize?: number;
  hint?: string;
}

/**
 * Upload drag-drop dùng chung (dùng ở leave-request-modal và các form upload ảnh).
 * Validate type+size ngay khi thả file, tự revoke preview URL cũ.
 */
export function FileDropzone({
  value,
  onChange,
  accept = { "image/*": [], "application/pdf": [] },
  maxSize = 5 * 1024 * 1024,
  hint = "Kéo thả file vào đây hoặc bấm để chọn (JPEG/PNG/PDF, tối đa 5MB)",
}: FileDropzoneProps) {
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  // Preview URL cho ảnh (revoke khi đổi file/unmount để khỏi leak).
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    if (!value) {
      setPreview(null);
      return;
    }
    const url = value.type.startsWith("image/") ? URL.createObjectURL(value) : null;
    setPreview(url);
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [value]);

  const onDrop = useCallback(
    (accepted: File[]) => {
      const file = accepted[0];
      if (!file) return;
      const err = validateUploadFile(file, {
        maxSize,
        types: ["image/jpeg", "image/png", "application/pdf"],
      });
      if (err) {
        setError(err);
        return;
      }
      setError(null);
      onChange(file);
    },
    [maxSize, onChange]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    maxSize,
    multiple: false,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className={`border border-dashed rounded-md p-4 text-center cursor-pointer transition-colors ${
          isDragActive ? "border-slate-900 bg-slate-50" : "border-slate-300 hover:bg-slate-50"
        }`}
      >
        <input {...getInputProps()} />
        {value ? (
          <div className="flex items-center gap-3 text-left">
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="preview" className="w-12 h-12 rounded object-cover border" />
            ) : (
              <FileText size={24} className="text-slate-400 shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-slate-800 truncate">{value.name}</p>
              <p className="text-[11px] text-slate-500">{(value.size / 1024).toFixed(0)} KB</p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
                setError(null);
              }}
              className="p-1 text-slate-400 hover:text-rose-600"
              aria-label="Xoá file"
            >
              <X size={16} />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5 text-slate-500">
            <UploadCloud size={20} />
            <p className="text-xs">{hint}</p>
          </div>
        )}
      </div>
      {error && <p className="mt-1 text-[11px] text-rose-600">{error}</p>}
    </div>
  );
}
