"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { Modal } from "./modal";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void | Promise<void>;
  isPending?: boolean;
  danger?: boolean;
}

/**
 * Hộp thoại xác nhận dùng chung (thay `window.confirm` chặn thread ở
 * admin/users + admin/academic). Dùng <Modal> nên có Esc/Tab-trap của Radix.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Xác nhận",
  cancelLabel = "Hủy bỏ",
  onConfirm,
  isPending = false,
  danger = true,
}: ConfirmDialogProps) {
  const handleConfirm = async () => {
    await onConfirm();
  };

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      contentClassName="max-w-md"
      footer={
        <>
          <button
            type="button"
            disabled={isPending}
            onClick={() => onOpenChange(false)}
            className="rounded-md border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={handleConfirm}
            className={
              danger
                ? "inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-rose-700 disabled:opacity-50"
                : "inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-slate-800 disabled:opacity-50"
            }
          >
            {isPending && <Loader2 size={14} className="animate-spin" />}
            {confirmLabel}
          </button>
        </>
      }
    >
      <div className="px-6 py-4">
        <p className="text-sm leading-relaxed text-slate-600">{description}</p>
      </div>
    </Modal>
  );
}
