# Kế Hoạch Triển Khai Tối Ưu Hóa Responsive Toàn Diện Front-end (Responsive Optimization Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hiện đại hóa và tối ưu hóa 100% trải nghiệm Responsive của hệ thống Smart Classroom Management System trên các phân hệ Sinh viên, Giảng viên, Quản trị viên và Kiosk điểm danh khuôn mặt, hỗ trợ hoàn hảo từ smartphone (360px) đến desktop (1280px+).

**Architecture:** Áp dụng mô hình Dual-View (Table trên Desktop ➔ Feed/Card trên Mobile) cho cổng sinh viên; chuẩn hóa `Modal` thành Responsive Bottom Sheet trên di động; sửa lỗi Viewport `100dvh` và Safe-Area Inset trên AppShell; khắc phục triệt để lỗi lệch bounding box nhận diện khuôn mặt Kiosk AI; và thêm Sticky Columns cho các bảng báo cáo nhiều cột.

**Tech Stack:** Next.js 16 (App Router), React 19, Tailwind CSS v4, Radix UI Dialog, Lucide React, TanStack Query & Table, MediaPipe Vision.

**Spec:** `docs/superpowers/specs/2026-09-24-responsive-optimization-design.md`

## Global Constraints

- Không làm phá vỡ hoặc thay đổi cấu trúc dữ liệu API hiện tại (`lib/api.ts`).
- Tuân thủ chuẩn WCAG Touch Target: vùng chạm tối thiểu 44x44px trên thiết bị di động.
- Không gây ra thanh cuộn ngang cấp trang (`no window horizontal scrollbar`).
- Hỗ trợ đầy đủ màn hình siêu hẹp (từ 360px - iPhone SE / Galaxy A).
- Mọi thay đổi phải vượt qua kiểm tra `npm run build` và `npm run lint` trong `frontend/`.

---

### Task 1: Nền tảng Viewport, Safe-Area & Layout Shell

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/components/layout/app-shell.tsx`
- Modify: `frontend/components/layout/sidebar.tsx`
- Modify: `frontend/components/layout/topbar.tsx`

**Interfaces:**
- Consumes: Tailwind CSS v4 `@import "tailwindcss";`, Web standard `env(safe-area-inset-*)`.
- Produces: Layout nền tảng không bao giờ bị cắt đáy trên iOS/Android, hỗ trợ safe area, menu mobile đạt chuẩn 44px.

- [ ] **Step 1: Cập nhật `globals.css` bổ sung utility classes cho Safe-Area và No-Scrollbar**

Thêm các tiện ích CSS vào `frontend/app/globals.css`:
```css
/* Tiện ích Safe-Area Insets cho tai thỏ và thanh Home Bar */
.pb-safe {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
.pt-safe {
  padding-top: env(safe-area-inset-top, 0px);
}
.h-safe-screen {
  height: 100dvh;
}
```

- [ ] **Step 2: Cập nhật `AppShell` trong `app-shell.tsx`**

Sửa `h-screen w-screen overflow-hidden` thành `h-[100dvh] w-full overflow-hidden`:
```tsx
  // Unified SaaS Shell Layout
  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-slate-50 text-slate-900 font-sans antialiased">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNavigate={() => setSidebarOpen(false)}
      />
      <div className="flex flex-col flex-1 min-w-0 h-[100dvh] overflow-hidden">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-3 sm:p-5 lg:p-8 bg-slate-50 pb-safe">
          {children}
        </main>
      </div>
    </div>
  );
```

- [ ] **Step 3: Cập nhật `Sidebar` và `Topbar` đảm bảo Touch Target 44x44px & Safe Area**

Trong `frontend/components/layout/sidebar.tsx`:
- Drawer mobile: Bổ sung `pb-safe` và đảm bảo hàng thông tin user ở đáy có đệm an toàn `pb-[max(12px,env(safe-area-inset-bottom))]`.
- Các nút đóng [X] và nút đăng xuất có `min-w-[44px] min-h-[44px]`.

Trong `frontend/components/layout/topbar.tsx`:
- Nút mở drawer có kích thước chuẩn `w-11 h-11 min-w-[44px] min-h-[44px]`.
- Breadcrumb tiêu đề hiển thị linh hoạt với `truncate min-w-0`.

- [ ] **Step 4: Kiểm tra lint và build sơ bộ**

Run: `cd frontend && npm run lint`
Expected: PASS không có lỗi cú pháp.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/globals.css frontend/components/layout/app-shell.tsx frontend/components/layout/sidebar.tsx frontend/components/layout/topbar.tsx
git commit -m "fix(shell): optimize viewport dvh, safe area insets and mobile touch targets"
```

---

### Task 2: Chuẩn Hóa Modal Thành Responsive Bottom Sheet

**Files:**
- Modify: `frontend/components/ui/modal.tsx`

**Interfaces:**
- Consumes: `@radix-ui/react-dialog`, `clsx`, `tailwind-merge`.
- Produces: `Modal` component tự động chuyển đổi giữa Center Modal (`sm:`) và Bottom Sheet (`<sm:`).

- [ ] **Step 1: Viết lại style cho `Modal` trong `components/ui/modal.tsx`**

Cập nhật `Dialog.Content` để trên điện thoại (`< sm`) ghim xuống đáy, bo tròn 2 góc trên (`rounded-t-2xl sm:rounded-lg`), có thanh kéo (pull indicator) trực quan:
```tsx
        <Dialog.Content
          className={cn(
            // Mobile: Bottom Sheet dính đáy
            "fixed inset-x-0 bottom-0 top-auto z-50 flex max-h-[90dvh] w-full translate-x-0 translate-y-0 flex-col overflow-hidden rounded-t-2xl border-t border-slate-200 bg-white shadow-2xl",
            // Desktop (sm:): Center Dialog
            "sm:inset-auto sm:left-[50%] sm:top-[50%] sm:bottom-auto sm:max-h-[90vh] sm:w-full sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-lg sm:border sm:border-slate-200",
            // Animation
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-bottom-10 sm:data-[state=open]:slide-in-from-bottom-0 sm:data-[state=open]:zoom-in-95 data-[state=open]:duration-200",
            contentClassName
          )}
        >
          {/* Thanh kéo Bottom Sheet trên mobile */}
          <div className="sm:hidden flex items-center justify-center pt-2.5 pb-1 shrink-0">
            <span className="w-10 h-1.5 rounded-full bg-slate-300" />
          </div>

          {/* Header */}
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 bg-slate-50/50 px-4 sm:px-6 py-3 sm:py-4 shrink-0">
            ...
          </div>
```
Và footer trên mobile:
```tsx
          {footer && (
            <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-end flex-wrap gap-2 border-t border-slate-200 bg-slate-50 px-4 sm:px-6 py-3 pb-[max(12px,env(safe-area-inset-bottom))] shrink-0 [&>button]:w-full [&>button]:sm:w-auto [&>a]:w-full [&>a]:sm:w-auto [&>button]:justify-center [&>a]:justify-center [&>button]:min-h-[42px] [&>button]:sm:min-h-[36px]">
              {footer}
            </div>
          )}
```

- [ ] **Step 2: Kiểm thử lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ui/modal.tsx
git commit -m "feat(ui): transform Modal into responsive bottom sheet on mobile"
```

---

### Task 3: Dual-View cho Cổng Sinh viên: Lịch Sử Điểm Danh

**Files:**
- Modify: `frontend/app/student/attendance/page.tsx`

**Interfaces:**
- Consumes: `getStudentAttendance`, `mediaUrl`, `StudentAttendance`.
- Produces: Dual-view: Bảng đầy đủ trên Desktop (`md:block`), Danh sách thẻ bài trực quan trên Mobile (`md:hidden`).

- [ ] **Step 1: Viết Component Thẻ Điểm Danh Mobile (`AttendanceCard`) trong `student/attendance/page.tsx`**

Tạo component `AttendanceCard`:
```tsx
function AttendanceCard({ item, formatTime, renderPointDelta, renderStatusBadge }: {
  item: StudentAttendance;
  formatTime: (t?: string | null) => string;
  renderPointDelta: (p?: number | null) => React.ReactNode;
  renderStatusBadge: (s: string) => React.ReactNode;
}) {
  return (
    <div className="p-3.5 bg-white rounded-lg border border-slate-200 shadow-2xs space-y-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="font-semibold text-slate-900 text-sm leading-snug line-clamp-1">{item.course_name}</h4>
          <p className="text-[11px] text-slate-500 font-mono mt-0.5">{item.class_code} · Ngày {item.study_date}</p>
        </div>
        <div>{renderStatusBadge(item.status)}</div>
      </div>

      <div className="grid grid-cols-2 gap-2 p-2 rounded-md bg-slate-50 text-xs border border-slate-100">
        <div>
          <span className="text-[10px] text-slate-400 block font-medium">Giờ vào (Check-in)</span>
          <span className="font-mono font-semibold text-emerald-700">{formatTime(item.check_in_time)}</span>
        </div>
        <div>
          <span className="text-[10px] text-slate-400 block font-medium">Giờ ra (Check-out)</span>
          <span className="font-mono font-medium text-slate-700">{formatTime(item.check_out_time)}</span>
        </div>
      </div>

      <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-xs">
        <div className="flex items-center gap-1.5">
          {item.has_uniform ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              Đồng phục chuẩn
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
              Lỗi đồng phục
            </span>
          )}
          {item.check_in_snapshot_url && (
            <a href={mediaUrl(item.check_in_snapshot_url)} target="_blank" rel="noreferrer" className="text-[11px] font-medium text-sky-600 underline">
              Xem ảnh
            </a>
          )}
        </div>
        <div>{renderPointDelta(item.point_delta)}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Tích hợp Dual-View và tối ưu Toolbar**

- Bọc bảng hiện tại bằng `hidden md:block`.
- Bổ sung `<div className="md:hidden space-y-2.5">` render danh sách `AttendanceCard`.
- Tối ưu KPI cards từ `grid-cols-2 sm:grid-cols-3 lg:grid-cols-6` sang các ô co giãn tự nhiên không tràn số.

- [ ] **Step 3: Kiểm tra lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/student/attendance/page.tsx
git commit -m "feat(student): implement dual-view card layout for attendance history"
```

---

### Task 4: Dual-View cho Cổng Sinh viên: Điểm Rèn Luyện & Sổ Cái Biến Động

**Files:**
- Modify: `frontend/app/student/conduct-points/page.tsx`

**Interfaces:**
- Consumes: `getStudentConductLedger`, `StudentConductLedger`.
- Produces: Dual-view: Bảng đầy đủ trên Desktop (`md:block`), Feed giao dịch rèn luyện trên Mobile (`md:hidden`), Toolbar lọc trượt ngang không rớt dòng.

- [ ] **Step 1: Viết Component Feed Giao Dịch Mobile (`ConductLedgerCard`) trong `conduct-points/page.tsx`**

Tạo component `ConductLedgerCard`:
```tsx
function ConductLedgerCard({ item, formatTimestamp, getReasonLabel }: {
  item: StudentConductLedger["items"][number];
  formatTimestamp: (ts: string) => string;
  getReasonLabel: (c: string) => string;
}) {
  const isPositive = item.point_delta > 0;
  return (
    <div className="p-3.5 bg-white rounded-lg border border-slate-200 shadow-2xs space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-semibold text-slate-900 text-xs">{getReasonLabel(item.reason_code)}</span>
          <p className="text-[11px] text-slate-400 font-mono mt-0.5">{formatTimestamp(item.created_at)}</p>
        </div>
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold font-mono tabular-nums ${
          isPositive ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-rose-50 text-rose-700 border border-rose-200"
        }`}>
          {isPositive ? `+${item.point_delta}` : item.point_delta} điểm
        </span>
      </div>
      {item.description && (
        <p className="text-xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100 leading-relaxed">
          {item.description}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Cập nhật Toolbar Lọc thành Scrollable Pills**

Sửa Toolbar bộ lọc:
```tsx
<div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1">
  <button onClick={() => setReasonFilter("ALL")} className="...">Tất cả</button>
  <button onClick={() => setReasonFilter("PLUS")} className="...">Cộng điểm</button>
  <button onClick={() => setReasonFilter("MINUS")} className="...">Trừ điểm</button>
</div>
```

- [ ] **Step 3: Tích hợp Dual-View vào trang**

Bọc `table` bằng `hidden md:block`, và hiển thị `<div className="md:hidden space-y-2.5">` render danh sách thẻ.

- [ ] **Step 4: Kiểm tra lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/student/conduct-points/page.tsx
git commit -m "feat(student): add mobile transaction feed and scrollable filter for conduct ledger"
```

---

### Task 5: Dual-View cho Cổng Sinh viên: Đơn Xin Nghỉ Phép

**Files:**
- Modify: `frontend/app/student/leave-requests/page.tsx`

**Interfaces:**
- Consumes: `getStudentLeaveRequests`, `StudentLeaveRequest`.
- Produces: Dual-view: Bảng đầy đủ trên Desktop (`md:block`), Danh sách thẻ đơn trên Mobile (`md:hidden`).

- [ ] **Step 1: Viết Component Thẻ Đơn Nghỉ Phép (`LeaveRequestCard`) trong `student/leave-requests/page.tsx`**

Tạo component `LeaveRequestCard`:
```tsx
function LeaveRequestCard({ req, renderStatusBadge, formatDateTime }: {
  req: StudentLeaveRequest;
  renderStatusBadge: (st: string) => React.ReactNode;
  formatDateTime: (dt?: string | null) => string;
}) {
  return (
    <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-2xs space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h4 className="font-semibold text-slate-900 text-sm">{req.course_name || "Môn học"}</h4>
          <p className="text-[11px] text-slate-500 font-mono mt-0.5">{req.class_code || `Lớp #${req.schedule_id}`}</p>
        </div>
        <div>{renderStatusBadge(req.status)}</div>
      </div>

      <div className="p-2.5 rounded-md bg-slate-50 text-xs border border-slate-100 space-y-1">
        <div className="flex items-center justify-between text-slate-600">
          <span>Buổi học:</span>
          <span className="font-semibold text-slate-900 font-mono">{String(req.study_date)} ({req.start_time?.slice(0, 5)} - {req.end_time?.slice(0, 5)})</span>
        </div>
        <div className="flex items-center justify-between text-slate-500 text-[11px]">
          <span>Ngày nộp đơn:</span>
          <span className="font-mono">{formatDateTime(req.created_at)}</span>
        </div>
      </div>

      <div className="text-xs text-slate-700">
        <span className="font-medium text-slate-900 block mb-0.5">Lý do:</span>
        <p className="bg-slate-50/50 p-2 rounded border border-slate-100">{req.reason}</p>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
        {req.proof_image ? (
          <a href={mediaUrl(req.proof_image)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sky-600 font-medium underline">
            Xem minh chứng đính kèm
          </a>
        ) : (
          <span className="text-slate-400 italic">Không có minh chứng</span>
        )}
      </div>

      {req.teacher_feedback && (
        <div className="p-2.5 rounded bg-amber-50/70 border border-amber-200 text-xs text-amber-900">
          <span className="font-semibold block mb-0.5">Phản hồi của giảng viên:</span>
          <p className="italic">{req.teacher_feedback}</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Tích hợp Dual-View và chuyển Toolbar lọc thành thanh trượt ngang**

Bọc `table` bằng `hidden md:block`, và hiển thị `<div className="md:hidden space-y-3">` render danh sách thẻ.

- [ ] **Step 3: Kiểm tra lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/student/leave-requests/page.tsx
git commit -m "feat(student): implement responsive card layout for leave requests"
```

---

### Task 6: Khắc Phục Lệch Toạ Độ Camera Kiosk AI Face Tracking

**Files:**
- Modify: `frontend/app/teacher/classes/[id]/kiosk/page.tsx`

**Interfaces:**
- Consumes: `videoRef`, `canvasRef`, `MediaStream`, `getClientFaceDetector`.
- Produces: Khung camera và lớp vẽ AI đồng bộ 1:1, không lệch bounding box trên mobile/tablet hoặc màn hình xoay dọc.

- [ ] **Step 1: Khóa Tỷ Lệ Aspect-Ratio Đồng Bộ Cho Video và Canvas trong `kiosk/page.tsx`**

Sửa container video:
```tsx
          {/* Camera + overlay */}
          <div className="lg:col-span-2 bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
            <div className="relative bg-slate-900 w-full aspect-video flex items-center justify-center overflow-hidden">
              <video
                ref={videoRef}
                muted
                playsInline
                className="w-full h-full object-cover"
              />
              <canvas
                ref={canvasRef}
                className="absolute inset-0 w-full h-full pointer-events-none"
              />
              {!running && (
                <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm">
                  Bấm “Mở camera” để bắt đầu quét
                </div>
              )}
            </div>
            ...
```

- [ ] **Step 2: Cập nhật hàm `paint()` để khớp toạ độ pixel chuẩn xác**

Đảm bảo `paint()` đo `canvas.clientWidth` và `canvas.clientHeight` thực tế để gán `canvas.width` và `canvas.height` tương ứng, giúp tỉ lệ scale `sx, sy` luôn trùng khớp 100% với khung video đang chiếu.

- [ ] **Step 3: Kiểm tra lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/teacher/classes/[id]/kiosk/page.tsx
git commit -m "fix(kiosk): lock aspect ratio and align bounding box canvas coordinates"
```

---

### Task 7: Sticky Columns Cho Bảng Báo Cáo & Bảng Sĩ Số Live

**Files:**
- Modify: `frontend/app/teacher/classes/[id]/live/page.tsx`
- Modify: `frontend/app/teacher/reports/page.tsx`
- Modify: `frontend/app/admin/reports/page.tsx`

**Interfaces:**
- Consumes: Bảng HTML nhiều cột.
- Produces: Ghim cố định cột STT + Mã SV / Họ tên khi cuộn ngang trên thiết bị nhỏ, tối ưu Header control.

- [ ] **Step 1: Cập nhật `teacher/classes/[id]/live/page.tsx`**

- Tối ưu header: Cụm nút checkbox "Tự động cập nhật (5s)", nút "Làm mới", và "Mở Kiosk Face" chuyển thành `grid grid-cols-2 sm:flex sm:items-center` để trên mobile không bị tràn màn hình.
- Thêm `sticky left-0 bg-white z-10` cho cột Mã SV và Họ tên để khi vuốt ngang xem Nguồn và Trạng thái không bị mất tên sinh viên.

- [ ] **Step 2: Cập nhật `teacher/reports/page.tsx` và `admin/reports/page.tsx`**

Thêm thuộc tính cố định cột định danh:
```tsx
{/* Cột STT cố định */}
<th className="sticky left-0 bg-slate-50 z-20 px-3 py-3 w-12 text-center">STT</th>
{/* Cột Mã SV cố định */}
<th className="sticky left-12 bg-slate-50 z-20 px-4 py-3">Mã SV</th>
...
<td className="sticky left-0 bg-white z-10 px-3 py-3 text-center ...">{idx + 1}</td>
<td className="sticky left-12 bg-white z-10 px-4 py-3 font-mono ...">{st.student_code}</td>
```

- [ ] **Step 3: Kiểm tra lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/teacher/classes/[id]/live/page.tsx frontend/app/teacher/reports/page.tsx frontend/app/admin/reports/page.tsx
git commit -m "feat(reports): add sticky identity columns for wide table responsive scrolling"
```

---

### Task 8: Sửa Lỗi Modal Ghi Danh Sinh Viên & Tối Ưu Quản Trị

**Files:**
- Modify: `frontend/app/admin/academic/page.tsx`
- Modify: `frontend/app/admin/settings/page.tsx`

**Interfaces:**
- Consumes: `getAdminClassStudents`, `updateAdminSettings`.
- Produces: Modal ghi danh có `overflow-x-auto`, form cấu hình tham số co giãn đẹp trên mobile.

- [ ] **Step 1: Sửa lỗi thiếu overflow trong modal ghi danh SV `admin/academic/page.tsx`**

Sửa dòng 874:
```tsx
{/* Bổ sung overflow-x-auto để bảng 7 cột không bị vỡ trên mobile */}
<div className="overflow-y-auto flex-1 p-3 sm:p-4">
  <div className="overflow-x-auto [scrollbar-width:thin]">
    <table className="w-full min-w-[560px] text-left border-collapse">
    ...
    </table>
  </div>
</div>
```

- [ ] **Step 2: Tối ưu form `admin/settings/page.tsx` trên mobile**

Tối ưu các cụm nhập số và nút "Chạy tính điểm ngay (Run Now)" để co giãn tự nhiên trên màn hình hẹp (`w-full sm:w-auto`).

- [ ] **Step 3: Kiểm tra lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/admin/academic/page.tsx frontend/app/admin/settings/page.tsx
git commit -m "fix(admin): add table overflow to academic student modal and optimize settings form"
```

---

### Task 9: Kiểm Thử Toàn Diện & Nghiệm Thu (Verification)

**Files:**
- Toàn bộ các trang đã chỉnh sửa.

- [ ] **Step 1: Chạy build production toàn bộ frontend**

Run: `cd frontend && npm run build`
Expected: `Compiled successfully`, không có bất kỳ lỗi TypeScript hay CSS nào.

- [ ] **Step 2: Chạy kiểm tra lint toàn dự án**

Run: `cd frontend && npm run lint`
Expected: Không có cảnh báo hoặc lỗi ESLint vi phạm.

- [ ] **Step 3: Kiểm tra tổng thể git status**

Run: `git status`
Expected: Cây thư mục sạch sẽ, mọi thay đổi đều được phân tách commit rõ ràng.

- [ ] **Step 4: Commit kết thúc kế hoạch**

```bash
git commit --allow-empty -m "chore: complete responsive optimization plan across all frontend portals"
```
