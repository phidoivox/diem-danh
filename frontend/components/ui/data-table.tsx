"use client";

import React from "react";
import {
  ColumnDef,
  PaginationState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";

interface ManualPagination {
  pageCount: number;
  pageIndex: number;
  onPageChange: (pageIndex: number) => void;
  totalRows?: number;
}

interface DataTableProps<T> {
  columns: ColumnDef<T, any>[];
  data: T[];
  searchPlaceholder?: string;
  pageSize?: number;
  isLoading?: boolean;
  emptyMessage?: string;
  /** Server-side pagination (bỏ client paging, sort/filter tại chỗ). */
  manualPagination?: ManualPagination;
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
          onPaginationChange: (updater: any) => {
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
        <input
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          placeholder={searchPlaceholder}
          className="w-full max-w-sm px-3 py-2 text-xs rounded-md border border-slate-200 bg-white focus:outline-none focus:ring-1 focus:ring-slate-900"
        />
      )}
      <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 border-b border-slate-200">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    onClick={h.column.getToggleSortingHandler()}
                    className={`px-3 py-2.5 text-left font-semibold text-slate-700 uppercase tracking-wide text-[11px] ${
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
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>
          Hiển thị {shownRows} / {totalLabel} dòng
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="p-1.5 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
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
            className="p-1.5 rounded border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
            aria-label="Trang sau"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
