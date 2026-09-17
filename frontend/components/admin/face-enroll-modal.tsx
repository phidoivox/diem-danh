"use client";

import React, { useState, useRef } from "react";
import { AdminUser, enrollUserFace } from "@/lib/api";
import {
  X,
  Camera,
  Upload,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Info,
  User,
} from "lucide-react";

interface FaceEnrollModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  user: AdminUser | null;
}

export function FaceEnrollModal({
  isOpen,
  onClose,
  onSuccess,
  user,
}: FaceEnrollModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen || !user) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        setErrorMessage("Vui lòng chọn file hình ảnh (JPG, PNG, WEBP)");
        return;
      }
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        setErrorMessage("Vui lòng chọn file hình ảnh (JPG, PNG, WEBP)");
        return;
      }
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setErrorMessage(null);
      setSuccessMessage(null);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setErrorMessage(null);
    setSuccessMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile) {
      setErrorMessage("Vui lòng chọn ảnh chân dung trước khi thực hiện đăng ký FaceID");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await enrollUserFace(user.id, selectedFile);
      setSuccessMessage(
        "Đăng ký FaceID thành công! Hệ thống AI đã phát hiện khuôn mặt và lưu vector đặc trưng (512-dim embedding)."
      );
      setTimeout(() => {
        onSuccess();
        onClose();
        handleReset();
      }, 1800);
    } catch (err: any) {
      setErrorMessage(
        err.message || "Không thể trích xuất vector khuôn mặt từ ảnh. Hãy chụp lại ảnh rõ nét hơn."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="relative w-full max-w-lg bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-md">
              <Camera size={18} />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-900">
                Đăng ký nhận diện FaceID
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                {user.user_code} - {user.full_name}
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              handleReset();
              onClose();
            }}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {errorMessage && (
            <div className="flex items-start gap-2.5 p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-md">
              <AlertCircle size={16} className="shrink-0 text-rose-500 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="flex items-start gap-2.5 p-3 text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md">
              <CheckCircle2 size={16} className="shrink-0 text-emerald-600 mt-0.5" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Upload Area */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              previewUrl
                ? "border-emerald-300 bg-emerald-50/20"
                : "border-slate-300 hover:border-slate-400 bg-slate-50/50 hover:bg-slate-50"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
            />

            {previewUrl ? (
              <div className="space-y-3">
                <div className="relative w-36 h-44 mx-auto rounded-md overflow-hidden border border-slate-300 shadow-xs">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={previewUrl}
                    alt="Face Preview"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-700">
                    {selectedFile?.name}
                  </p>
                  <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                    {selectedFile && `${(selectedFile.size / 1024).toFixed(1)} KB`} - Nhấn để chọn ảnh khác
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-2 py-4">
                <div className="w-12 h-12 mx-auto rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                  <Upload size={22} />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-700">
                    Kéo thả ảnh chân dung vào đây, hoặc nhấn để duyệt
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Hỗ trợ file JPG, PNG, WEBP tối đa 5MB
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Guidelines */}
          <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-slate-600 text-xs space-y-1.5">
            <div className="font-semibold text-slate-800 flex items-center gap-1">
              <Info size={13} className="text-slate-500" />
              Yêu cầu ảnh chụp để trích xuất AI chính xác:
            </div>
            <ul className="list-disc list-inside space-y-0.5 text-[11px] text-slate-500 pl-1">
              <li>Chụp chính diện góc 0°, nhìn thẳng ống kính camera.</li>
              <li>Không đeo khẩu trang, kính râm; khuôn mặt đủ sáng.</li>
              <li>Một khuôn mặt duy nhất trong khung hình.</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50/50">
          <button
            type="button"
            onClick={() => {
              handleReset();
              onClose();
            }}
            disabled={isLoading}
            className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors disabled:opacity-50 cursor-pointer"
          >
            Đóng
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isLoading || !selectedFile}
            className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-md transition-colors disabled:opacity-50 cursor-pointer"
          >
            {isLoading && <Loader2 size={14} className="animate-spin" />}
            Trích xuất & Lưu FaceID
          </button>
        </div>
      </div>
    </div>
  );
}
