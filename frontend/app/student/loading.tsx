export default function StudentLoading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Đang tải dữ liệu sinh viên">
      <div className="h-8 w-56 rounded-md bg-slate-100 animate-pulse" />
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-24 rounded-lg bg-slate-100 border border-slate-200 animate-pulse"
          />
        ))}
      </div>
      <div className="h-64 rounded-lg bg-slate-100 border border-slate-200 animate-pulse" />
    </div>
  );
}
