"use client";

import * as React from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Tiêu đề bắt buộc — render trong <Dialog.Title> để a11y + Esc/Tab của Radix. */
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** Nút/link phụ cạnh nút X (VD: "Mở tab mới" ở proof-preview). */
  headerActions?: React.ReactNode;
  contentClassName?: string;
  showClose?: boolean;
}

/**
 * Modal dùng chung trên Radix Dialog (Portal + Overlay + FocusScope có sẵn:
 * Esc đóng, Tab nhốt focus). Thay các `fixed inset-0 z-50` viết tay.
 */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  headerActions,
  contentClassName,
  showClose = true,
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            "fixed left-[50%] top-[50%] z-50 flex max-h-[90vh] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-2xl",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=open]:duration-150",
            contentClassName
          )}
        >
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 bg-slate-50/50 px-6 py-4 shrink-0">
            <div className="min-w-0">
              <Dialog.Title className="text-base font-semibold text-slate-900">
                {title}
              </Dialog.Title>
              {description && (
                <Dialog.Description className="mt-0.5 text-xs text-slate-500">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {headerActions}
              {showClose && (
                <Dialog.Close asChild>
                  <button
                    type="button"
                    aria-label="Đóng"
                    className="rounded-md p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                  >
                    <X size={18} />
                  </button>
                </Dialog.Close>
              )}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>

          {footer && (
            <div className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3 shrink-0">
              {footer}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
