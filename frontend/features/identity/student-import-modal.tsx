"use client";

import React, { useRef, useState } from "react";
import { FileSpreadsheet, Loader2, X, Download, Upload } from "lucide-react";
import { downloadStudentImportTemplate, importStudentsExcel, StudentImportResult } from "@/features/shell";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (created: number) => void;
}

// ponytail: parse/preview client-side skipped — backend auto-detects header + returns per-row errors. Add SheetJS preview when users need pre-upload review.
export function StudentImportModal({ isOpen, onClose, onSuccess }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [result, setResult] = useState<StudentImportResult | null>(null);

  if (!isOpen) return null;

  const pick = (f?: File | null) => {
    setResult(null);
    setError(null);
    if (!f) { setFile(null); return; }
    if (!/\.xlsx?$|\.xlsm$/i.test(f.name)) { setError("Chỉ nhận file .xlsx / .xlsm"); return; }
    if (f.size > 10 * 1024 * 1024) { setError("File vượt quá 10MB"); return; }
    setFile(f);
  };

  const doTemplate = async () => {
    setDownloading(true);
    try { await downloadStudentImportTemplate(); }
    catch (e) { setError(e instanceof Error ? e.message : "Không tải được file mẫu"); }
    finally { setDownloading(false); }
  };

  const doImport = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      const r = await importStudentsExcel(file);
      setResult(r);
      if (r.created > 0) onSuccess(r.created);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import thất bại");
    } finally {
      setBusy(false);
    }
  };

  const close = () => {
    setFile(null); setResult(null); setError(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 backdrop-blur-xs p-3 sm:p-4">
      <div className="flex min-h-full items-center justify-center">
        <div className="relative w-full max-w-lg bg-white rounded-lg shadow-xl border border-slate-200 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-slate-50/50">
            <div>
              <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                <FileSpreadsheet size={17} className="text-emerald-600" />
                Nhập sinh viên từ Excel
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Tự dò tiêu đề (MSSV, họ tên, email, lớp, ngành). Mật khẩu mặc định{" "}
                <code className="font-mono font-semibold text-slate-700">123456</code>
              </p>
            </div>
            <button onClick={close} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 cursor-pointer">
              <X size={18} />
            </button>
          </div>

          <div className="p-5 space-y-3">
            <button
              onClick={doTemplate}
              disabled={downloading}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700 hover:text-emerald-800 cursor-pointer disabled:opacity-50"
            >
              <Download size={14} />
              {downloading ? "Đang tải mẫu..." : "Tải file mẫu mau_nhap_sinh_vien.xlsx"}
            </button>

            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files?.[0]); }}
              onClick={() => inputRef.current?.click()}
              className="border border-dashed rounded-md p-5 text-center cursor-pointer border-slate-300 hover:bg-slate-50 transition-colors"
            >
              <input
                ref={inputRef}
                type="file"
                accept=".xlsx,.xlsm"
                className="hidden"
                onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }}
              />
              <Upload size={20} className="mx-auto text-slate-400" />
              <p className="text-xs text-slate-600 mt-1.5">
                {file ? <span className="font-mono font-medium">{file.name}</span> : "Kéo-thả hoặc bấm chọn file .xlsx (tối đa 10MB)"}
              </p>
            </div>

            {error && (
              <div className="p-3 text-xs rounded-md border bg-rose-50 text-rose-800 border-rose-200">{error}</div>
            )}

            {result && (
              <div className="p-3 text-xs rounded-md border bg-slate-50 border-slate-200 space-y-1.5">
                <p className="font-semibold text-slate-800">
                  Tạo {result.created} SV · bỏ qua {result.skipped} dòng · mật khẩu{" "}
                  <code className="font-mono">{result.default_password}</code>
                </p>
                {result.errors.length > 0 && (
                  <ul className="max-h-36 overflow-y-auto space-y-1">
                    {result.errors.map((e, i) => (
                      <li key={i} className="text-rose-700 font-mono text-[11px]">
                        Dòng {e.row} [{e.user_code || "?"}]: {e.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-slate-50/50">
            <button
              onClick={close}
              className="px-4 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50 cursor-pointer"
            >
              {result ? "Đóng" : "Hủy bỏ"}
            </button>
            <button
              onClick={doImport}
              disabled={!file || busy}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium text-white bg-slate-900 hover:bg-slate-800 rounded-md disabled:opacity-50 cursor-pointer"
            >
              {busy && <Loader2 size={14} className="animate-spin" />}
              Nhập Excel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
