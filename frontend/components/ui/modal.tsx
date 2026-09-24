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
  /** Ghi đè class vùng body cuộn (VD: tắt scroll ngoài khi body tự quản lý cuộn con). */
  bodyClassName?: string;
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
  bodyClassName,
  showClose = true,
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            "fixed inset-x-0 bottom-0 top-auto z-50 flex max-h-[90dvh] w-full translate-x-0 translate-y-0 flex-col overflow-hidden rounded-t-2xl border-t border-slate-200 bg-white shadow-2xl",
            "sm:inset-auto sm:left-[50%] sm:top-[50%] sm:bottom-auto sm:max-h-[90vh] sm:w-full sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-lg sm:border sm:border-slate-200",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-bottom-10 sm:data-[state=open]:slide-in-from-bottom-0 sm:data-[state=open]:zoom-in-95 data-[state=open]:duration-200",
            contentClassName
          )}
        >
          {/* Pull indicator for mobile bottom sheet */}
          <div className="sm:hidden flex items-center justify-center pt-2.5 pb-1 shrink-0">
            <span className="w-10 h-1.5 rounded-full bg-slate-300" />
          </div>

          <div className="flex items-start justify-between gap-3 border-b border-slate-200 bg-slate-50/50 px-4 sm:px-6 py-3 sm:py-4 shrink-0">
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
                    className="inline-flex min-h-[36px] min-w-[36px] items-center justify-center rounded-md p-1.5 sm:p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                  >
                    <X size={18} />
                  </button>
                </Dialog.Close>
              )}
            </div>
          </div>

          <div className={cn("min-h-0 flex-1 overflow-y-auto overscroll-contain", bodyClassName)}>{children}</div>

          {footer && (
            <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end flex-wrap gap-2 border-t border-slate-200 bg-slate-50 px-4 sm:px-6 pt-3 pb-[max(12px,env(safe-area-inset-bottom))] sm:py-3 shrink-0 [&>button]:w-full [&>button]:sm:w-auto [&>a]:w-full [&>a]:sm:w-auto [&>button]:justify-center [&>a]:justify-center [&>button]:min-h-[42px] [&>button]:sm:min-h-[36px]">
              {footer}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
