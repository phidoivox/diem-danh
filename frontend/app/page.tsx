import Link from "next/link";

const cards = [
  ["/attendance", "Điểm danh trực tiếp", "Webcam trình duyệt hoặc camera IP RTSP, nhận diện mặt + đồng phục realtime."],
  ["/students", "Học sinh / Sinh viên", "Đăng ký hồ sơ, chụp ảnh chân dung lấy vector khuôn mặt."],
  ["/reports", "Báo cáo", "Lịch sử điểm danh, lọc vi phạm đồng phục, xem ảnh bằng chứng."],
];

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-3xl font-bold">Web điểm danh AI</h1>
      <p className="mt-2 text-zinc-600">YOLO26 custom + Supervision track + thư viện nhận diện mặt có sẵn.</p>
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {cards.map(([href, t, d]) => (
          <Link key={href} href={href} className="rounded-xl border p-5 hover:bg-zinc-50">
            <div className="font-semibold">{t}</div>
            <div className="mt-1 text-sm text-zinc-600">{d}</div>
          </Link>
        ))}
      </div>
    </main>
  );
}
