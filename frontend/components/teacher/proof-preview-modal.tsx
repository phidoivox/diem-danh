"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ZoomIn,
  ZoomOut,
  RotateCw,
  ExternalLink,
  AlertCircle,
  Download,
  FileText,
} from "lucide-react";
import { Modal } from "@/components/ui/modal";

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

  const handleReset = useCallback(() => {
    setScale(1);
    setRotation(0);
    setHasError(false);
  }, []);

  // Mở lần 2 hết zoom cũ: reset mỗi khi đổi isOpen/proofUrl.
  useEffect(() => {
    if (isOpen) {
      handleReset();
    }
  }, [isOpen, proofUrl, handleReset]);

  const handleZoomIn = () => setScale((s) => Math.min(s + 0.25, 3));
  const handleZoomOut = () => setScale((s) => Math.max(s - 0.25, 0.5));
  const handleRotate = () => setRotation((r) => (r + 90) % 360);

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      handleReset();
      onClose();
    }
  };

  const isPdf = proofUrl?.toLowerCase().endsWith(".pdf");

  const description =
    studentName || studentCode
      ? `Sinh viên: ${studentName ?? ""}${studentCode ? ` (${studentCode})` : ""}`
      : undefined;

  return (
    <Modal
      open={isOpen}
      onOpenChange={handleOpenChange}
      title="Minh chứng đơn xin nghỉ phép"
      description={description}
      contentClassName="max-w-3xl"
      headerActions={
        proofUrl ? (
          <a
            href={proofUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
            title="Mở tab mới"
          >
            <ExternalLink size={13} />
            <span>Mở tab mới</span>
          </a>
        ) : undefined
      }
      footer={
        <button
          type="button"
          onClick={() => {
            handleReset();
            onClose();
          }}
          className="rounded-md border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-100"
        >
          Đóng
        </button>
      }
    >
      {/* Reason summary if available */}
      {reason && (
        <div className="flex items-start gap-2 border-b border-slate-100 bg-slate-50 px-6 py-2.5 text-xs text-slate-600">
          <span className="shrink-0 font-semibold text-slate-700">Lý do xin nghỉ:</span>
          <span className="italic">{reason}</span>
        </div>
      )}

      {/* Floating Toolbar (for images) */}
      {!isPdf && proofUrl && !hasError && (
        <div className="flex items-center justify-between border-b border-slate-100 bg-white px-6 py-2 text-xs text-slate-500">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleZoomOut}
              className="rounded p-1.5 text-slate-700 transition-colors hover:bg-slate-100"
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
              className="rounded p-1.5 text-slate-700 transition-colors hover:bg-slate-100"
              title="Phóng to"
            >
              <ZoomIn size={16} />
            </button>
            <span className="mx-1 h-4 w-px bg-slate-200" />
            <button
              type="button"
              onClick={handleRotate}
              className="rounded p-1.5 text-slate-700 transition-colors hover:bg-slate-100"
              title="Xoay 90 độ"
            >
              <RotateCw size={16} />
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="rounded px-2 py-1 text-[11px] text-slate-600 transition-colors hover:bg-slate-100"
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
      <div className="flex min-h-[360px] flex-1 items-center justify-center overflow-auto bg-slate-100 p-4 select-none">
        {!proofUrl ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-slate-400">
            <AlertCircle size={36} className="mb-2 text-slate-300" />
            <p className="text-sm font-medium text-slate-600">
              Không tìm thấy minh chứng đính kèm
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Sinh viên không tải lên tệp minh chứng cho đơn này.
            </p>
          </div>
        ) : isPdf ? (
          <div className="flex h-[500px] w-full flex-col items-center justify-center rounded border border-slate-200 bg-white p-6">
            <FileText size={48} className="mb-3 text-rose-500" />
            <p className="text-sm font-semibold text-slate-800">
              Tệp minh chứng định dạng PDF
            </p>
            <p className="mt-1 mb-4 max-w-sm text-center text-xs text-slate-500">
              Trình duyệt không hỗ trợ xem trước trực tiếp tập tin PDF tại khung nhỏ này.
            </p>
            <a
              href={proofUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-slate-800"
            >
              <Download size={15} />
              <span>Mở và Tải về tập tin PDF</span>
            </a>
          </div>
        ) : hasError ? (
          <div className="flex flex-col items-center justify-center rounded border border-slate-200 bg-white p-8 text-center text-slate-500">
            <AlertCircle size={36} className="mb-2 text-amber-500" />
            <p className="text-sm font-medium text-slate-700">
              Không thể tải hình ảnh minh chứng
            </p>
            <p className="mt-1 mb-3 text-xs text-slate-400">
              Đường dẫn tệp có thể đã hết hạn hoặc bị lỗi.
            </p>
            <a
              href={proofUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
            >
              <span>Thử mở bằng đường dẫn gốc</span>
              <ExternalLink size={12} />
            </a>
          </div>
        ) : (
          <div className="flex max-h-full max-w-full items-center justify-center overflow-auto">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={proofUrl}
              alt="Minh chứng nghỉ phép"
              onError={() => setHasError(true)}
              style={{
                transform: `scale(${scale}) rotate(${rotation}deg)`,
                transition: "transform 0.15s ease-out",
              }}
              className="max-h-[70vh] max-w-full rounded border border-slate-200 bg-white object-contain shadow-sm"
            />
          </div>
        )}
      </div>
    </Modal>
  );
}
