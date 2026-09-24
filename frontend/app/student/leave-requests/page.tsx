"use client";

import React, { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RoleGuard } from "@/components/layout/role-guard";
import { formatDateTime as formatDateTimeVN } from "@/lib/date";
import {
  getStudentLeaveRequests,
  getStudentSchedule,
  mediaUrl,
  StudentLeaveRequest,
  StudentSchedule,
} from "@/lib/api";
import { LeaveRequestModal } from "@/components/student/leave-request-modal";
import {
  FileText,
  PlusCircle,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  ExternalLink,
  MessageSquare,
  Calendar,
  Paperclip,
} from "lucide-react";

interface LeaveRequestCardProps {
  req: StudentLeaveRequest;
  renderStatusBadge: (status: string) => React.ReactNode;
  formatDateTime: (dtStr?: string | null) => string;
}

function LeaveRequestCard({
  req,
  renderStatusBadge,
  formatDateTime,
}: LeaveRequestCardProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3.5 space-y-3 shadow-xs">
      {/* Header: Tên môn, mã lớp, Status badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-semibold text-slate-900 leading-snug line-clamp-1">
            {req.course_name || "Môn học"}
          </h4>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
            {req.class_code || `Schedule #${req.schedule_id}`}
          </div>
        </div>
        <div className="shrink-0">{renderStatusBadge(req.status)}</div>
      </div>

      {/* Khối thông tin buổi học */}
      <div className="bg-slate-50 rounded-md p-2.5 border border-slate-100 text-xs space-y-1.5 font-mono text-slate-600">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-slate-700 font-medium">
            <Calendar size={13} className="text-slate-400 shrink-0" />
            <span>{req.study_date ? String(req.study_date) : "Buổi học"}</span>
          </div>
          {req.start_time && req.end_time && (
            <div className="text-[11px] text-slate-500">
              {String(req.start_time).slice(0, 5)} - {String(req.end_time).slice(0, 5)}
            </div>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 text-[11px] text-slate-500 pt-1 border-t border-slate-200/60">
          <span>
            Phòng: <strong className="text-slate-700 font-semibold">{req.room_name || "--"}</strong>
          </span>
          <span>
            Nộp: <span className="tabular-nums">{formatDateTime(req.created_at)}</span>
          </span>
        </div>
      </div>

      {/* Lý do xin nghỉ */}
      <div className="text-xs text-slate-700">
        <span className="font-medium text-slate-500 mr-1.5">Lý do:</span>
        <span className="text-slate-800 break-words">{req.reason}</span>
      </div>

      {/* Minh chứng */}
      <div className="text-xs flex items-center justify-between pt-1.5 border-t border-slate-100">
        <span className="text-slate-500 text-[11px] font-medium">Minh chứng:</span>
        {req.proof_image ? (
          <a
            href={mediaUrl(req.proof_image)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[11px] font-medium text-sky-700 hover:text-sky-800 bg-sky-50 hover:bg-sky-100 px-2 py-0.5 rounded border border-sky-200 transition-colors"
          >
            <Paperclip size={12} />
            <span>Xem tài liệu</span>
            <ExternalLink size={10} />
          </a>
        ) : (
          <span className="text-[11px] text-slate-400 italic">Không có minh chứng</span>
        )}
      </div>

      {/* Phản hồi từ giảng viên */}
      {req.teacher_feedback ? (
        <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 text-xs text-amber-900 space-y-1">
          <div className="flex items-center gap-1.5 font-medium text-amber-800 text-[11px]">
            <MessageSquare size={13} className="shrink-0 text-amber-600" />
            <span>Phản hồi từ giảng viên:</span>
          </div>
          <p className="italic text-amber-950 pl-4 break-words">{req.teacher_feedback}</p>
        </div>
      ) : req.status === "PENDING" ? (
        <div className="text-[11px] text-slate-400 italic flex items-center gap-1">
          <Clock size={11} />
          <span>Đang chờ giảng viên phản hồi...</span>
        </div>
      ) : null}
    </div>
  );
}

export default function StudentLeaveRequestsPage() {
  const queryClient = useQueryClient();
  const leavesQuery = useQuery({
    queryKey: ["student-leaves"],
    queryFn: getStudentLeaveRequests,
  });
  const schedulesQuery = useQuery({
    queryKey: ["student-schedule"],
    queryFn: () => getStudentSchedule().catch(() => [] as StudentSchedule[]),
  });
  const requests: StudentLeaveRequest[] = useMemo(() => leavesQuery.data ?? [], [leavesQuery.data]);
  const schedules: StudentSchedule[] = useMemo(() => schedulesQuery.data ?? [], [schedulesQuery.data]);
  const loading = leavesQuery.isPending;
  const error = leavesQuery.isError
    ? leavesQuery.error instanceof Error
      ? leavesQuery.error.message
      : "Không thể tải danh sách đơn xin nghỉ phép."
    : null;

  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const fetchData = () => {
    queryClient.invalidateQueries({ queryKey: ["student-leaves"] });
    queryClient.invalidateQueries({ queryKey: ["student-schedule"] });
  };

  // Filtered requests
  const filteredRequests = useMemo(() => {
    if (statusFilter === "ALL") return requests;
    return requests.filter((r) => r.status === statusFilter);
  }, [requests, statusFilter]);

  // Statistics
  const stats = useMemo(() => {
    let pending = 0;
    let approved = 0;
    let rejected = 0;

    requests.forEach((r) => {
      if (r.status === "PENDING") pending++;
      else if (r.status === "APPROVED") approved++;
      else if (r.status === "REJECTED") rejected++;
    });

    return { total: requests.length, pending, approved, rejected };
  }, [requests]);

  const formatDateTime = (dtStr?: string | null) => {
    if (!dtStr) return "--";
    try {
      return formatDateTimeVN(dtStr);
    } catch {
      return dtStr;
    }
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case "APPROVED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 size={12} />
            Đã chấp nhận
          </span>
        );
      case "REJECTED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle size={12} />
            Bị từ chối
          </span>
        );
      case "PENDING":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock size={12} />
            Chờ duyệt
          </span>
        );
    }
  };

  return (
    <RoleGuard allowedRoles={["STUDENT", "ADMIN"]}>
      <div className="space-y-4 sm:space-y-6 max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200">
          <div>
            <h1 className="text-lg font-semibold text-slate-900 tracking-tight">
              Đơn xin nghỉ phép trực tuyến
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Nộp đơn xin phép vắng mặt kèm minh chứng và theo dõi kết quả phê duyệt của giảng viên
            </p>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex-1 sm:flex-initial h-9 sm:h-8 px-3 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center justify-center gap-1.5 shadow-sm min-h-[38px] sm:min-h-0"
            >
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
              <span>Làm mới</span>
            </button>
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex-1 sm:flex-initial h-9 sm:h-8 px-3 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition-colors inline-flex items-center justify-center gap-1.5 shadow-sm min-h-[38px] sm:min-h-0"
            >
              <PlusCircle size={14} />
              <span>+ Nộp đơn xin nghỉ phép</span>
            </button>
          </div>
        </div>

        {/* Stats Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
              Tổng số đơn đã nộp
            </span>
            <div className="text-xl font-semibold text-slate-900 font-mono tabular-nums mt-0.5">
              {stats.total}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-amber-600">
              Đang chờ duyệt
            </span>
            <div className="text-xl font-semibold text-amber-700 font-mono tabular-nums mt-0.5">
              {stats.pending}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-emerald-600">
              Đã chấp nhận
            </span>
            <div className="text-xl font-semibold text-emerald-700 font-mono tabular-nums mt-0.5">
              {stats.approved}
            </div>
          </div>

          <div className="p-3.5 rounded-lg bg-white border border-slate-200 shadow-sm">
            <span className="text-[11px] font-medium uppercase tracking-wider text-rose-600">
              Bị từ chối
            </span>
            <div className="text-xl font-semibold text-rose-700 font-mono tabular-nums mt-0.5">
              {stats.rejected}
            </div>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:flex-wrap sm:items-center justify-between gap-2.5 sm:gap-3">
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-0.5 sm:pb-0">
            <span className="text-xs text-slate-500 font-medium shrink-0">Trạng thái:</span>
            <div className="inline-flex rounded-md p-0.5 bg-slate-100 border border-slate-200 shrink-0">
              <button
                type="button"
                onClick={() => setStatusFilter("ALL")}
                className={`px-2.5 py-1 text-xs font-medium rounded whitespace-nowrap transition-colors ${
                  statusFilter === "ALL"
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Tất cả ({requests.length})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("PENDING")}
                className={`px-2.5 py-1 text-xs font-medium rounded whitespace-nowrap transition-colors ${
                  statusFilter === "PENDING"
                    ? "bg-white text-amber-800 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Chờ duyệt ({stats.pending})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("APPROVED")}
                className={`px-2.5 py-1 text-xs font-medium rounded whitespace-nowrap transition-colors ${
                  statusFilter === "APPROVED"
                    ? "bg-white text-emerald-800 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Đã chấp nhận ({stats.approved})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("REJECTED")}
                className={`px-2.5 py-1 text-xs font-medium rounded whitespace-nowrap transition-colors ${
                  statusFilter === "REJECTED"
                    ? "bg-white text-rose-800 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Bị từ chối ({stats.rejected})
              </button>
            </div>
          </div>

          <div className="text-xs text-slate-500 font-mono">
            Hiển thị <span className="font-semibold text-slate-900">{filteredRequests.length}</span> đơn
          </div>
        </div>

        {/* Requests Container (Dual-View: Desktop Table, Mobile Card Feed) */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <RefreshCw size={24} className="animate-spin text-slate-400 mx-auto mb-2" />
              <p className="text-xs text-slate-500">Đang tải danh sách đơn xin nghỉ phép...</p>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-rose-700 bg-rose-50 text-xs">
              {error}
            </div>
          ) : filteredRequests.length === 0 ? (
            <div className="p-12 text-center">
              <FileText size={36} className="text-slate-300 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-slate-800">Chưa có đơn xin nghỉ phép nào</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                Khi cần nghỉ học vì việc cá nhân hoặc ốm đau, bạn có thể nộp đơn trực tuyến kèm minh chứng.
              </p>
              <button
                onClick={() => setIsModalOpen(true)}
                className="mt-4 h-9 sm:h-8 px-3 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition-colors inline-flex items-center gap-1.5"
              >
                <PlusCircle size={14} />
                <span>Nộp đơn ngay</span>
              </button>
            </div>
          ) : (
            <>
              {/* Desktop Table: md:block */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50/75 border-b border-slate-200 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    <tr>
                      <th className="px-4 py-3">Môn học & Mã lớp</th>
                      <th className="px-4 py-3">Buổi học xin nghỉ</th>
                      <th className="px-4 py-3">Ngày nộp</th>
                      <th className="px-4 py-3">Lý do xin nghỉ</th>
                      <th className="px-4 py-3">Minh chứng</th>
                      <th className="px-4 py-3">Trạng thái</th>
                      <th className="px-4 py-3">Phản hồi của giảng viên</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-slate-700">
                    {filteredRequests.map((req) => (
                      <tr key={req.id} className="hover:bg-slate-50/70 transition-colors">
                        {/* Course */}
                        <td className="px-4 py-3 font-medium text-slate-900">
                          <div className="font-semibold text-slate-900">{req.course_name || "Môn học"}</div>
                          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                            {req.class_code || `Schedule #${req.schedule_id}`}
                          </div>
                        </td>

                        {/* Schedule info */}
                        <td className="px-4 py-3 font-mono tabular-nums text-slate-600 whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Calendar size={13} className="text-slate-400" />
                            <span>{req.study_date ? String(req.study_date) : "Buổi học"}</span>
                          </div>
                          {req.start_time && req.end_time && (
                            <div className="text-[11px] text-slate-400 mt-0.5">
                              {String(req.start_time).slice(0, 5)} - {String(req.end_time).slice(0, 5)}
                              {req.room_name ? ` (${req.room_name})` : ""}
                            </div>
                          )}
                        </td>

                        {/* Created At */}
                        <td className="px-4 py-3 font-mono tabular-nums text-slate-500 whitespace-nowrap">
                          {formatDateTime(req.created_at)}
                        </td>

                        {/* Reason */}
                        <td className="px-4 py-3 text-slate-800 max-w-xs">
                          <p className="line-clamp-2">{req.reason}</p>
                        </td>

                        {/* Proof file */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          {req.proof_image ? (
                            <a
                              href={mediaUrl(req.proof_image)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-sky-700 hover:text-sky-800 bg-sky-50 hover:bg-sky-100 px-2 py-0.5 rounded border border-sky-200 transition-colors"
                            >
                              <Paperclip size={12} />
                              <span>Xem tài liệu</span>
                              <ExternalLink size={10} />
                            </a>
                          ) : (
                            <span className="text-[11px] text-slate-400 italic">Không đính kèm</span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="px-4 py-3 whitespace-nowrap">
                          {renderStatusBadge(req.status)}
                        </td>

                        {/* Teacher feedback */}
                        <td className="px-4 py-3 max-w-xs text-slate-600">
                          {req.teacher_feedback ? (
                            <div className="flex items-start gap-1.5 text-xs text-slate-700 bg-slate-50 p-2 rounded border border-slate-200">
                              <MessageSquare size={13} className="text-slate-400 shrink-0 mt-0.5" />
                              <span className="italic">{req.teacher_feedback}</span>
                            </div>
                          ) : req.status === "PENDING" ? (
                            <span className="text-[11px] text-slate-400 italic">Đang chờ phản hồi...</span>
                          ) : (
                            <span className="text-slate-400">--</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Card Feed: md:hidden */}
              <div className="md:hidden space-y-3 p-3">
                {filteredRequests.map((req) => (
                  <LeaveRequestCard
                    key={req.id}
                    req={req}
                    renderStatusBadge={renderStatusBadge}
                    formatDateTime={formatDateTime}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Modal */}
        <LeaveRequestModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSuccess={fetchData}
          schedules={schedules}
        />
      </div>
    </RoleGuard>
  );
}
