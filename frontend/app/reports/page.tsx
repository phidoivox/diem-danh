"use client";
import { useEffect, useMemo, useState } from "react";
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { API, getAtt, toCsv, type Att } from "@/lib/api";

export default function Reports() {
  const [rows, setRows] = useState<Att[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const load = () => getAtt(200, status, q).then(setRows).catch(() => []);
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const cols = useMemo<ColumnDef<Att>[]>(() => [
    { accessorKey: "code", header: "MSSV" },
    { accessorKey: "uniform", header: "Đồng phục" },
    { accessorKey: "violations", header: "Vi phạm" },
    { accessorKey: "at", header: "Lúc" },
    {
      id: "snap", header: "Ảnh",
      cell: ({ row }) => row.original.snapshot ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={`${API}/api/attendance/snapshot/${row.original.snapshot}`} alt="" className="h-12 w-16 rounded object-cover" />
      ) : null,
    },
  ], []);
  const table = useReactTable({ data: rows, columns: cols, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  const bad = rows.filter((r) => r.uniform === "violation").length;

  return (
    <main className="mx-auto max-w-5xl p-6">
      <h1 className="text-2xl font-bold">Báo cáo</h1>
      <p className="mt-1 text-sm text-zinc-600">Tổng {rows.length} lượt, vi phạm đồng phục {bad}.</p>
      <div className="mt-3 flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm MSSV…" className="flex-1 rounded border px-2 py-1" />
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded border px-2 py-1">
          <option value="">Tất cả</option>
          <option value="ok">Đạt</option>
          <option value="violation">Vi phạm</option>
        </select>
        <button onClick={load} className="rounded border px-3 py-1">Lọc</button>
        <a href={URL.createObjectURL(new Blob([toCsv(rows)], { type: "text/csv" }))} download="diemdanh.csv"
          className="rounded bg-black px-3 py-1 text-white">CSV</a>
      </div>
      <table className="mt-4 w-full text-sm">
        <thead>{table.getHeaderGroups().map((hg) => (
          <tr key={hg.id}>{hg.headers.map((h) => (
            <th key={h.id} onClick={h.column.getToggleSortingHandler()} className="cursor-pointer text-left text-zinc-500">
              {flexRender(h.column.columnDef.header, h.getContext())}
            </th>))}</tr>))}</thead>
        <tbody>{table.getRowModel().rows.map((r) => (
          <tr key={r.id} className="border-t">{r.getVisibleCells().map((c) => (
            <td key={c.id} className="p-1">{flexRender(c.column.columnDef.cell, c.getContext())}</td>))}</tr>))}</tbody>
      </table>
    </main>
  );
}
