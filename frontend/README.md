# Frontend - Detect AI (Giao diện Quản trị & Điểm danh Lớp học)

Ứng dụng Web dành cho Sinh viên, Giảng viên và Quản trị viên của Hệ thống Quản lý Lớp học Thông minh Detect AI.

Xây dựng trên nền tảng **Next.js 16 (App Router)**, **React 19**, **Tailwind CSS v4**, và **TanStack Query**.

---

## 1. Yêu cầu hệ thống

* **Node.js**: Phiên bản `>= 18.18.0` (Khuyến nghị Node 20 LTS)
* **Trình quản lý gói**: `npm`, `pnpm` hoặc `yarn`

---

## 2. Hướng dẫn cài đặt & Khởi chạy

### Bước 1: Di chuyển vào thư mục frontend
```bash
cd frontend
```

### Bước 2: Cài đặt thư viện dependencies
```bash
npm install
```

### Bước 3: Cấu hình biến môi trường
Tạo file `.env.local` từ mẫu `.env.example`:
```bash
cp .env.example .env.local
```
Nội dung file `.env.local`:
```env
NEXT_PUBLIC_API=http://localhost:8000
```
*(Thay thế bằng địa chỉ IP / Domain thực tế của máy chủ Backend nếu triển khai phân tán).*

### Bước 4: Khởi chạy môi trường phát triển (Development)
```bash
npm run dev
```
Mở trình duyệt tại: `http://localhost:3000`

---

## 3. Đóng gói cho môi trường Production

### Biên dịch ứng dụng:
```bash
npm run build
```

### Khởi chạy ứng dụng production:
```bash
npm run start -p 3000
```

---

## 4. Kiểm tra mã nguồn (Linting)

Kiểm tra cú pháp và quy chuẩn React/Next.js:
```bash
npm run lint
```

---

## 5. Cấu trúc thư mục

```text
frontend/
├── app/                  # Next.js App Router (Routing, Layouts, Pages theo role)
│   ├── admin/            # Trang Quản trị: Users, Academic, Reports, Settings, Conduct
│   ├── teacher/          # Trang Giảng viên: Classes, Live Kiosk, Leave Reviews, Reports
│   ├── student/          # Trang Sinh viên: Schedule, Attendance, Conduct Points, Leave
│   └── login/            # Trang Đăng nhập hệ thống
├── features/             # Các Feature Modules tự quản (Hexagonal/Modular UI pattern)
│   ├── academic/         # Quản lý môn học, lớp và xếp lịch hàng loạt
│   ├── attendance/       # Điểm danh trực tiếp, modal ghi đè thủ công, lịch sử ca học
│   ├── evaluation/       # Điểm rèn luyện, xếp loại hạnh kiểm, trang chủ nhiệm
│   ├── identity/         # Modal import sinh viên từ Excel, quản lý tài khoản
│   ├── leave/            # Nộp đơn nghỉ phép, xem ảnh minh chứng
│   ├── recognition/      # Giao diện camera Kiosk, phát hiện mặt, kết nối WebSocket
│   ├── reporting/        # Báo cáo chuyên cần, cấm thi và xuất Excel
│   └── shell/            # Layout chung, Sidebar, Topbar, Auth Context, Data Table
└── public/               # Static assets, icons
```
