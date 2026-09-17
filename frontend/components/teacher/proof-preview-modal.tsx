"use client";

import React, { useState } from "react";
import {
  X,
  ZoomIn,
  ZoomOut,
  RotateCw,
  ExternalLink,
  FileText,
  AlertCircle,
  Download,
} from "lucide-react";

interface ProofPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  proofUrl: string | null;
  studentName?: string;
  studentCode?: string;
  reason?: string;
}

export function ProofPreviewModal({
  isOpen,
  onClose,
  proofUrl,
  studentName,
  studentCode,
  reason,
}: ProofPreviewModalProps) {
  const [scale, setScale] = useState<number>(1);
  const [rotation, setRotation] = useState<number>(0);
  const [hasError, setHasError] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleZoomIn = () => setScale((s) => Math.min(s + 0.25, 3));
  const handleZoomOut = () => setScale((s) => Math.max(s - 0.25, 0.5));
  const handleRotate = () => setRotation((r) => (r + 90) % 360);
  const handleReset = () => {
    setScale(1);
    setRotation(0);
  };

  const isPdf = proofUrl?.toLowerCase().endsWith(".pdf");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-[2px]">
      <div className="relative w-full max-w-3xl max-h-[90vh] bg-white rounded-lg border border-slate-200 shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/50 shrink-0">
          <div>
            <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <FileText size={18} className="text-slate-600" />
              <span>Minh chứng đơn xin nghỉ phép</span>
            </h3>
            {(studentName || studentCode) && (
              <p className="text-xs text-slate-500 mt-0.5">
                Sinh viên: <span className="font-medium text-slate-800">{studentName}</span>
                {studentCode && (
                  <span className="font-mono tabular-nums text-slate-600 ml-1.5">
                    ({studentCode})
                  </span>
                )}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {proofUrl && (
              <a
                href={proofUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200 transition-colors"
                title="Mở tab mới"
              >
                <ExternalLink size={13} />
                <span>Mở tab mới</span>
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                handleReset();
                onClose();
              }}
              className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Reason summary if available */}
        {reason && (
          <div className="px-6 py-2.5 bg-slate-50 border-b border-slate-100 text-xs text-slate-600 flex items-start gap-2 shrink-0">
            <span className="font-semibold text-slate-700 shrink-0">Lý do xin nghỉ:</span>
            <span className="italic">{reason}</span>
          </div>
        )}

        {/* Floating Toolbar (for images) */}
        {!isPdf && proofUrl && !hasError && (
          <div className="px-6 py-2 border-b border-slate-100 bg-white flex items-center justify-between text-xs text-slate-500 shrink-0">
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleZoomOut}
                className="p-1.5 rounded hover:bg-slate-100 text-slate-700 transition-colors"
                title="Thu nhỏ"
              >
                <ZoomOut size={16} />
              </button>
              <span className="w-12 text-center font-mono tabular-nums">
                {Math.round(scale * 100)}%
              </span>
              <button
                type="button"
                onClick={handleZoomIn}
                className="p-1.5 rounded hover:bg-slate-100 text-slate-700 transition-colors"
                title="Phóng to"
              >
                <ZoomIn size={16} />
              </button>
              <span className="h-4 w-px bg-slate-200 mx-1" />
              <button
                type="button"
                onClick={handleRotate}
                className="p-1.5 rounded hover:bg-slate-100 text-slate-700 transition-colors"
                title="Xoay 90 độ"
              >
                <RotateCw size={16} />
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="px-2 py-1 rounded hover:bg-slate-100 text-slate-600 text-[11px] transition-colors"
              >
                Đặt lại
              </button>
            </div>
            <span className="text-[11px] text-slate-400">
              Có thể cuộn hoặc mở tab mới để tải về
            </span>
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 overflow-auto bg-slate-100 p-4 flex items-center justify-center min-h-[360px] select-none">
          {!proofUrl ? (
            <div className="flex flex-col items-center justify-center text-slate-400 text-center p-8">
              <AlertCircle size={36} className="mb-2 text-slate-300" />
              <p className="text-sm font-medium text-slate-600">
                Không tìm thấy minh chứng đính kèm
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Sinh viên không tải lên tệp minh chứng cho đơn này.
              </p>
            </div>
          ) : isPdf ? (
            <div className="w-full h-[500px] flex flex-col items-center justify-center bg-white rounded border border-slate-200 p-6">
              <FileText size={48} className="text-rose-500 mb-3" />
              <p className="text-sm font-semibold text-slate-800">
                Tệp minh chứng định dạng PDF
              </p>
              <p className="text-xs text-slate-500 mt-1 mb-4 text-center max-w-sm">
                Trình duyệt không hỗ trợ xem trước trực tiếp tập tin PDF tại khung nhỏ này.
              </p>
              <a
                href={proofUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 shadow-sm transition-colors"
              >
                <Download size={15} />
                <span>Mở và Tải về tập tin PDF</span>
              </a>
            </div>
          ) : hasError ? (
            <div className="flex flex-col items-center justify-center text-slate-500 text-center p-8 bg-white rounded border border-slate-200">
              <AlertCircle size={36} className="mb-2 text-amber-500" />
              <p className="text-sm font-medium text-slate-700">
                Không thể tải hình ảnh minh chứng
              </p>
              <p className="text-xs text-slate-400 mt-1 mb-3">
                Đường dẫn tệp có thể đã hết hạn hoặc bị lỗi.
              </p>
              <a
                href={proofUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1"
              >
                <span>Thử mở bằng đường dẫn gốc</span>
                <ExternalLink size={12} />
              </a>
            </div>
          ) : (
            <div className="flex items-center justify-center overflow-auto max-w-full max-h-full">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={proofUrl}
                alt="Minh chứng nghỉ phép"
                onError={() => setHasError(true)}
                style={{
                  transform: `scale(${scale}) rotate(${rotation}deg)`,
                  transition: "transform 0.15s ease-out",
                }}
                className="max-w-full max-h-[70vh] object-contain rounded shadow-sm border border-slate-200 bg-white"
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-end shrink-0">
          <button
            type="button"
            onClick={() => {
              handleReset();
              onClose();
            }}
            className="px-4 py-1.5 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 transition-colors shadow-sm"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}
