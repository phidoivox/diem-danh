# Thiết Kế Tối Ưu Hóa Responsive Toàn Diện Front-end (Responsive Optimization Design)

- **Ngày ban hành:** 2026-09-24
- **Dự án:** Smart Classroom Management System (Học vụ & Điểm danh AI)
- **Mục tiêu:** Tối ưu hóa trải nghiệm người dùng (UX) và giao diện (UI) thích ứng hoàn chỉnh trên mọi kích thước màn hình (Mobile 360px–430px, Tablet 768px–1024px, Desktop/Laptop 1280px+), loại bỏ triệt để các lỗi vỡ khung, cắt cụt màn hình do thanh điều hướng trình duyệt và sai lệch toạ độ nhận diện khuôn mặt Kiosk AI.

---

## 1. Bối Cảnh & Vấn Đề Cần Giải Quyết

Hệ thống phục vụ 3 nhóm đối tượng với thói quen thiết bị khác nhau:
1. **Sinh viên (Mobile-first, ~90% smartphone):** Tra cứu thời khóa biểu, xem điểm rèn luyện, kiểm tra lịch sử điểm danh, nộp đơn xin nghỉ phép kèm ảnh minh chứng.
2. **Giảng viên (Hybrid - Laptop & Tablet/Mobile tại lớp):** Quản lý lớp, theo dõi sĩ số trực tiếp (Live room), duyệt đơn nghỉ phép, xuất báo cáo cấm thi và vận hành Kiosk điểm danh khuôn mặt.
3. **Quản trị viên (Desktop/Laptop-first):** Quản lý người dùng, phân quyền, xếp lớp & thời khóa biểu, cấu hình tham số rèn luyện/ngưỡng cấm thi, đối soát học vụ toàn trường.

### Các khiếm khuyết giao diện hiện tại:
- **Lỗi Viewport trên Mobile:** `AppShell` sử dụng `h-screen w-screen overflow-hidden`. Trên iOS Safari và Chrome Mobile, thanh URL bar co giãn làm che mất hàng tài khoản ở đáy sidebar hoặc nút tác vụ ở cuối trang. `w-screen` trên Windows gây giật/cuộn ngang ẩn do tính cả thanh scrollbar.
- **Lệch Toạ Độ Camera Kiosk AI:** Video dùng `w-full max-h-[60vh] object-contain` trong khi canvas overlay dùng `absolute inset-0 w-full h-full`. Khi tỷ lệ khung hình video không khớp với khung chứa (sinh ra viền đen letterbox), toạ độ bounding box khuôn mặt của MediaPipe/Server bị vẽ lệch hoàn toàn so với mặt thật của sinh viên.
- **Hội chứng "Bảng ép chặt" (Table Cramming):** Các trang sinh viên (`student/attendance`, `student/conduct-points`, `student/leave-requests`) hiển thị bảng nhiều cột trên màn hình điện thoại 360px–390px, người dùng phải kéo ngang liên tục, thông tin rời rạc, khó nắm bắt.
- **Modal chưa tối ưu cho ngón tay:** Các modal form trên điện thoại vẫn là hộp thoại căn giữa lơ lửng, nút đóng [X] ở góc trên xa tầm với, bàn phím ảo bật lên che mất nút bấm lưu dữ liệu.
- **Thanh lọc trạng thái (Toolbar Filter):** Bị rớt dòng lộn xộn (wrap lởm chởm) trên màn hình hẹp.
- **Thiếu Sticky cột định danh:** Khi cuộn ngang bảng báo cáo 10 cột, người dùng trôi mất cột Mã SV / Họ tên.
- **Lỗi thiếu overflow trong modal ghi danh:** Modal sinh viên trong `admin/academic` thiếu `overflow-x-auto`, gây vỡ layout trên mobile.

---

## 2. Các Trụ Cột Kiến Trúc Tối Ưu (Design Architecture)

### Trụ cột 1: Chuẩn hóa Viewport, Safe-Area & Layout Shell
1. **Đơn vị Viewport động (`dvh`):**
   - Chuyển `h-screen` thành `h-[100dvh]` hoặc `min-h-[100dvh]`. Khi thanh địa chỉ trình duyệt co lại hay nở ra, layout tự động co dãn chuẩn xác không bao giờ bị cắt chân.
   - Chuyển `w-screen` thành `w-full` để triệt tiêu lỗi cuộn ngang ảo do scrollbar Windows.
2. **Hỗ trợ Safe-Area Inset:**
   - Cung cấp các lớp tiện ích CSS trong `globals.css` cho thanh điều hướng đáy và tai thỏ: `padding-bottom: env(safe-area-inset-bottom)`.
3. **Sidebar Drawer Ergonomics:**
   - Khu vực tài khoản người dùng ở đáy Sidebar có padding an toàn với mép dưới màn hình.
   - Nút đóng [X] và các mục menu có kích thước tối thiểu đạt chuẩn ngón tay 44x44px.

### Trụ cột 2: Mô Hình Hiển Thị Kép (Dual-View: Table trên Desktop ➔ Feed/Card trên Mobile)
Áp dụng cho 3 trang cốt lõi của Cổng Sinh viên:
1. **Trang Lịch sử Điểm danh (`student/attendance`):**
   - **Desktop (`≥ md`):** Bảng dữ liệu TanStack Table đầy đủ 9 cột, có `min-w-[800px]`, thanh cuộn ngang mỏng.
   - **Mobile (`< md`):** Chuyển sang danh sách Thẻ Buổi học (`AttendanceCard`):
     - Dòng 1: Tên môn học, Mã lớp, Ngày học.
     - Dòng 2: Ca học, Phòng học.
     - Dòng 3: Huy hiệu Trạng thái (Có mặt / Đi muộn / Vắng / Nghỉ phép) nổi bật.
     - Dòng 4: Giờ Check-in & Check-out kèm thumbnail ảnh chụp (nếu có).
     - Dòng 5: Trạng thái đồng phục (Đúng quy định / Vi phạm) và Số điểm rèn luyện bị trừ (nếu có).
2. **Trang Sổ cái Rèn luyện (`student/conduct-points`):**
   - **Desktop (`≥ md`):** Bảng sổ cái phân loại thời gian, biến động, mã lý do, diễn giải.
   - **Mobile (`< md`):** Chuyển sang Feed Biến động Điểm (`ConductLedgerCard`):
     - Thể hiện dạng dòng thời gian giao dịch giống app ngân hàng: Biến động to rõ (`+2 điểm` màu xanh, `-5 điểm` màu đỏ), thời gian ghi nhận, lý do cụ thể và diễn giải tự động hoàn điểm.
   - **Toolbar lọc:** Chuyển sang thanh trượt ngang dạng viên thuốc không ngắt dòng (`flex-nowrap overflow-x-auto no-scrollbar`).
3. **Trang Đơn xin Nghỉ phép (`student/leave-requests`):**
   - **Desktop (`≥ md`):** Bảng theo dõi 7 cột.
   - **Mobile (`< md`):** Chuyển sang Danh sách Thẻ Đơn (`LeaveRequestCard`):
     - Hiển thị ngày nộp, môn học, buổi xin nghỉ, lý do, nút xem nhanh tệp minh chứng và ô phản hồi của giảng viên (nếu đã được duyệt/từ chối).

### Trụ cột 3: Chuẩn Hóa Modal Thành Responsive Bottom Sheet
Tối ưu hóa `components/ui/modal.tsx`:
- **Desktop (`sm:` trở lên):** Modal dạng hộp thoại căn giữa màn hình (`fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-lg max-w-lg`).
- **Mobile (`< sm`):** Tự động chuyển thành **Bottom Sheet**:
  - Đặt vị trí: `fixed inset-x-0 bottom-0 top-auto translate-y-0 rounded-t-2xl max-h-[90dvh] w-full`.
  - Có thanh kéo nhỏ (drag handle indicator) ở mép trên cùng.
  - Vùng cuộn `body` tự động co dãn theo bàn phím ảo.
  - Footer chứa các nút hành động (Hủy, Xác nhận, Gửi đơn) cố định sát đáy, toàn bộ nút dàn đều `w-full` dễ thao tác một tay.
- **Áp dụng đồng bộ:** Chuẩn hóa cả `UserFormModal`, `ScheduleFormModal`, `LeaveRequestModal`, `ManualOverrideModal`, `AttendanceHistoryModal`, và chuyển các modal tự chế trong `admin/academic` sang dùng `Modal` chuẩn.

### Trụ cột 4: Đồng Bộ Khung Hình Camera Kiosk AI Face Tracking
Sửa lỗi lệch bounding box nhận diện khuôn mặt trong `teacher/classes/[id]/kiosk/page.tsx`:
1. **Khóa tỷ lệ khung hình (Aspect Ratio Lock):**
   - Bọc video và canvas trong cùng một container có tỷ lệ khung hình cố định (mặc định `aspect-video` 16:9).
   - Video sử dụng `w-full h-full object-cover` (hoặc canvas được resize chính xác theo rect hiển thị thực tế của video thay vì toàn bộ container).
2. **Tính toán toạ độ vẽ Canvas:**
   - Hàm `paint()` tính toán hệ số tỷ lệ `sx, sy` dựa trên `video.videoWidth` và `canvas.clientWidth` thực tế đang render, loại bỏ hoàn toàn hiện tượng lệch hộp nhận diện khi xoay ngang/dọc thiết bị.
3. **Bố cục Kiosk:**
   - Desktop: Cột camera chiếm 2/3 (bên trái), thông tin SV vừa nhận diện và lịch sử chiếm 1/3 (bên phải).
   - Mobile / Tablet dọc: Xếp chồng dọc 1 cột hợp lý, thông tin SV vừa nhận diện nổi bật ngay bên dưới camera.

### Trụ cột 5: Bảng Báo Cáo Nhiều Cột Có Cột Cố Định (Sticky Columns)
Áp dụng cho các bảng nhiều cột: `teacher/reports`, `admin/reports`, `teacher/classes/[id]/live`:
1. **Sticky Header:** Dòng tiêu đề ghim ở đỉnh bảng (`sticky top-0 bg-slate-50 z-20`).
2. **Sticky Identity Columns:** Ghim cố định 2 cột đầu (Cột STT + Cột Mã SV & Họ tên) ở mép trái (`sticky left-0 bg-white z-10`). Khi người dùng cuộn ngang xem tỷ lệ vắng tích lũy hay điểm quy đổi, họ tên sinh viên luôn hiển thị rõ ràng, không bị trôi mất.
3. **Thanh phân trang thích ứng (Responsive Pagination):** Thanh đếm "Hiển thị x / y dòng" và cụm nút Trang trước/sau tự động wrap gọn gàng trên mobile mà không tràn viền.

### Trụ cột 6: Chuẩn Hóa Touch Target (WCAG 44x44px) & Bộ Lọc Toolbar
1. Tất cả các nút bấm icon (Sửa, Xóa, Xem lịch sử, ScanFace) đều có kích thước tối thiểu `min-h-[36px] min-w-[36px]` hoặc đệm padding vô hình đảm bảo vùng chạm đạt tối thiểu 44x44px.
2. Các thanh phân loại (Filter tabs) trên toàn hệ thống chuyển thành thanh trượt ngang dạng pill (`flex-nowrap overflow-x-auto no-scrollbar`), có padding đệm hai đầu giúp cuộn mượt bằng ngón tay.

---

## 3. Danh Sách Tệp Cần Can Thiệp & Kế Hoạch Chỉnh Sửa

| Tệp tin | Trách nhiệm thay đổi |
| :--- | :--- |
| `frontend/app/globals.css` | Bổ sung class hỗ trợ `dvh`, `safe-area-inset`, `no-scrollbar` tiện lợi. |
| `frontend/components/layout/app-shell.tsx` | Chuyển `h-screen w-screen` sang `h-[100dvh] w-full`, xử lý overflow & padding an toàn. |
| `frontend/components/layout/sidebar.tsx` | Tối ưu vùng chạm menu mobile, padding an toàn đáy màn hình. |
| `frontend/components/layout/topbar.tsx` | Tối ưu nút mở drawer 44x44px, breadcrumbs co giãn trên màn hình siêu hẹp. |
| `frontend/components/ui/modal.tsx` | Thêm responsive mode: Modal căn giữa trên `sm:` và Bottom Sheet trên `<sm:`. |
| `frontend/app/student/attendance/page.tsx` | Bổ sung Card View cho mobile (`<md:`) và giữ Table cho desktop (`md:`). |
| `frontend/app/student/conduct-points/page.tsx` | Bổ sung Ledger Card View cho mobile, tối ưu thanh filter trượt ngang. |
| `frontend/app/student/leave-requests/page.tsx` | Bổ sung Leave Request Card View cho mobile. |
| `frontend/app/teacher/classes/[id]/kiosk/page.tsx` | Đồng bộ tỷ lệ khung hình video-canvas, fix lệch bounding box trên mobile/tablet. |
| `frontend/app/teacher/classes/[id]/live/page.tsx` | Tối ưu header controls responsive, bổ sung sticky columns cho bảng điểm danh live. |
| `frontend/app/teacher/reports/page.tsx` | Bổ sung sticky column (STT + Mã SV + Họ tên) cho bảng báo cáo 10 cột. |
| `frontend/app/admin/reports/page.tsx` | Bổ sung sticky column (STT + Họ tên) và tối ưu phân trang. |
| `frontend/app/admin/academic/page.tsx` | Bọc `overflow-x-auto` cho modal ghi danh SV, chuyển modal tạo lớp sang chuẩn `Modal`. |
| `frontend/app/admin/settings/page.tsx` | Tối ưu form nhập liệu và nút chạy cron trên mobile. |

---

## 4. Tiêu Chí Nghiệm Thu (Acceptance Criteria)

1. **Kiểm thử trên thiết bị hẹp (Viewport 360px - 390px - iPhone SE / Galaxy S):**
   - Không xuất hiện thanh cuộn ngang ngoài ý muốn ở cấp trang (`no window horizontal scrollbar`).
   - Cổng sinh viên (`schedule`, `attendance`, `conduct-points`, `leave-requests`) đọc và thao tác 100% bằng thẻ dọc, không cần kéo ngang màn hình.
   - Mở modal form hiển thị dạng Bottom Sheet trơn tru, nút bấm nằm sát tầm với ngón tay cái.
2. **Kiểm thử trên Tablet (Viewport 768px - 1024px - iPad dọc/ngang):**
   - Chuyển tiếp mượt mà giữa dạng thẻ và dạng bảng.
   - Các bảng báo cáo nhiều cột cuộn ngang mượt, cột họ tên sinh viên ghim cố định ở mép trái.
3. **Kiểm thử Kiosk Camera:**
   - Khi thay đổi kích thước cửa sổ hoặc xoay ngang/dọc, viền xanh nhận diện khuôn mặt luôn ôm sát khuôn mặt thực tế, không bị méo hay bay lệch ra ngoài.
4. **Kiểm thử Build & Lint:**
   - Dự án chạy `npm run build` hoặc `npm run lint` trong thư mục `frontend` không phát sinh lỗi TypeScript hoặc cú pháp.
