import { Search, X } from "lucide-react";

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
  /** Width wrapper, default `w-full sm:max-w-xs`. */
  className?: string;
}

/**
 * Ô tìm kiếm thống nhất toàn app: gõ là lọc live, không nút Tìm.
 * Server-side kết hợp `useDebouncedValue(..., 300)` ở page;
 * client-side lọc trực tiếp trên mảng đã fetch.
 */
export function SearchInput({ value, onChange, placeholder, ariaLabel, className = "w-full sm:max-w-xs" }: SearchInputProps) {
  return (
    <div className={`relative ${className}`}>
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
        className="w-full pl-8 pr-7 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-900 focus:border-slate-900"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          title="Xóa tìm kiếm"
          aria-label="Xóa tìm kiếm"
          className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-slate-600 rounded cursor-pointer"
        >
          <X size={13} />
        </button>
      )}
    </div>
  );
}
