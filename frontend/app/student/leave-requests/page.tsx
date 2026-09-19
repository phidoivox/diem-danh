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
  AlertCircle,
  Paperclip,
} from "lucide-react";

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
  const requests: StudentLeaveRequest[] = leavesQuery.data ?? [];
  const schedules: StudentSchedule[] = schedulesQuery.data ?? [];
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
      <div className="space-y-6">
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
          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              disabled={loading}
              className="h-8 px-3 rounded-md text-xs font-medium border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 transition-colors inline-flex items-center gap-1.5 shadow-sm"
            >
              <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
              <span>Làm mới</span>
            </button>
            <button
              onClick={() => setIsModalOpen(true)}
              className="h-8 px-3 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition-colors inline-flex items-center gap-1.5 shadow-sm"
            >
              <PlusCircle size={14} />
              <span>+ Nộp đơn xin nghỉ phép</span>
            </button>
          </div>
        </div>

        {/* Stats Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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
        <div className="p-3 bg-white rounded-lg border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">Trạng thái:</span>
            <div className="inline-flex rounded-md p-0.5 bg-slate-100 border border-slate-200">
              <button
                type="button"
                onClick={() => setStatusFilter("ALL")}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
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
                className={`px-2.5 py-1 text-xs font-medium rounded ${
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
                className={`px-2.5 py-1 text-xs font-medium rounded ${
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
                className={`px-2.5 py-1 text-xs font-medium rounded ${
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

        {/* Requests Table */}
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
                className="mt-4 h-8 px-3 rounded-md text-xs font-medium bg-slate-900 text-white hover:bg-slate-800 transition-colors inline-flex items-center gap-1.5"
              >
                <PlusCircle size={14} />
                <span>Nộp đơn ngay</span>
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
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
