export default function AdminLoading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Đang tải dữ liệu quản trị">
      <div className="h-8 w-72 rounded-md bg-slate-100 animate-pulse" />
      <div className="h-12 rounded-lg bg-slate-100 border border-slate-200 animate-pulse" />
      <div className="h-96 rounded-lg bg-slate-100 border border-slate-200 animate-pulse" />
    </div>
  );
}
