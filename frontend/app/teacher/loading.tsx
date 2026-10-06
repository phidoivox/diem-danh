export default function TeacherLoading() {
  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-4" aria-busy="true" aria-label="Đang tải dữ liệu giảng viên">
      <div className="h-8 w-64 rounded-md bg-slate-100 animate-pulse" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-48 rounded-lg bg-slate-100 border border-slate-200 animate-pulse"
          />
        ))}
      </div>
    </div>
  );
}
