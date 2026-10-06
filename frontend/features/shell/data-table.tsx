"use client";

import React from "react";
import {
  ColumnDef,
  PaginationState,
  Updater,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";

interface ManualPagination {
  pageCount: number;
  pageIndex: number;
  onPageChange: (pageIndex: number) => void;
  totalRows?: number;
}

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  searchPlaceholder?: string;
  pageSize?: number;
  isLoading?: boolean;
  emptyMessage?: string;
  /** Server-side pagination (bỏ client paging, sort/filter tại chỗ). */
  manualPagination?: ManualPagination;
  /** Min-width của <table> để scroll ngang trong card. Default `min-w-[720px]`. */
  minWidthClass?: string;
}

/**
 * Bảng dùng chung (dùng thật `@tanstack/react-table` đã cài từ trước nhưng bị
 * bỏ không). Thay các `<table>` tay + `STT=(page-1)*size+idx` + nút prev/next +
 * `useMemo filter includes` ở admin/users, academic, teacher/live, reports.
 */
export function DataTable<T>({
  columns,
  data,
  searchPlaceholder,
  pageSize = 10,
  isLoading = false,
  emptyMessage = "Không có dữ liệu",
  manualPagination,
  minWidthClass = "min-w-[720px]",
}: DataTableProps<T>) {
  const [globalFilter, setGlobalFilter] = React.useState("");
  const [pagination, setPagination] = React.useState<PaginationState>({ pageIndex: 0, pageSize });

  const table = useReactTable({
    columns,
    data,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
    ...(manualPagination
      ? {
          manualPagination: true,
          pageCount: manualPagination.pageCount,
          state: {
            pagination: { pageIndex: manualPagination.pageIndex, pageSize },
          },
          onPaginationChange: (updater: Updater<PaginationState>) => {
            const next =
              typeof updater === "function"
                ? updater({ pageIndex: manualPagination.pageIndex, pageSize })
                : updater;
            manualPagination.onPageChange(next.pageIndex);
          },
        }
      : {
          state: { pagination, globalFilter },
          onPaginationChange: setPagination,
          onGlobalFilterChange: setGlobalFilter,
        }),
  });

  const shownRows = table.getRowModel().rows.length;
  const totalLabel = manualPagination?.totalRows ?? table.getFilteredRowModel().rows.length;

  return (
    <div className="space-y-3">
      {searchPlaceholder && !manualPagination && (
        <div className="relative w-full sm:max-w-xs">
          <input
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            className="w-full pl-3 pr-7 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
          />
          {globalFilter && (
            <button
              type="button"
              onClick={() => setGlobalFilter("")}
              title="Xóa tìm kiếm"
              aria-label="Xóa tìm kiếm"
              className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-slate-600 rounded cursor-pointer"
            >
              <X size={13} />
            </button>
          )}
        </div>
      )}
      <div className="overflow-x-auto rounded-md border border-slate-200 bg-white [scrollbar-width:thin]">
        <table className={`w-full text-xs ${minWidthClass}`}>
          <thead className="bg-slate-50 border-b border-slate-200">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    onClick={h.column.getToggleSortingHandler()}
                    className={`px-3 py-2.5 text-left font-semibold text-slate-700 uppercase tracking-wide text-[11px] whitespace-nowrap ${
                      h.column.getCanSort() ? "cursor-pointer select-none hover:text-slate-900" : ""
                    }`}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? null}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-slate-400">
                  <Loader2 size={20} className="animate-spin mx-auto" />
                </td>
              </tr>
            ) : shownRows === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-3 py-8 text-center text-slate-400">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50/60">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2.5 text-slate-700">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between flex-wrap text-xs text-slate-500">
        <span>
          Hiển thị {shownRows} / {totalLabel} dòng
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="inline-flex items-center justify-center min-h-[36px] min-w-[36px] p-1.5 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
            aria-label="Trang trước"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="tabular-nums">
            {table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}
          </span>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="inline-flex items-center justify-center min-h-[36px] min-w-[36px] p-1.5 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
            aria-label="Trang sau"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
