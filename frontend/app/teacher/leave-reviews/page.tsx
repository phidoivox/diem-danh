"use client";

import React, { useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RoleGuard } from "@/components/layout/role-guard";
import { formatDateTime as formatDateTimeVN } from "@/lib/date";
import {
  getTeacherLeaveRequests,
  getTeacherClasses,
  mediaUrl,
  reviewLeaveRequest,
  TeacherLeaveRequest,
  TeacherClass,
} from "@/lib/api";
import { ProofPreviewModal } from "@/components/teacher/proof-preview-modal";
import {
  ClipboardCheck,
  CheckCircle2,
  XCircle,
  Clock,
  Search,
  Filter,
  RefreshCw,
  FileText,
  Calendar,
  MessageSquare,
  Check,
  X,
  AlertCircle,
  Loader2,
  BookOpen,
} from "lucide-react";

export default function TeacherLeaveReviewsPage() {
  const queryClient = useQueryClient();
  const leavesQuery = useQuery({
    queryKey: ["teacher-leaves"],
    queryFn: () => getTeacherLeaveRequests({ size: 100 }),
  });
  const classesQuery = useQuery({
    queryKey: ["teacher-classes"],
    queryFn: () => getTeacherClasses().catch(() => [] as TeacherClass[]),
  });
  const requests: TeacherLeaveRequest[] = leavesQuery.data?.items ?? [];
  const classes: TeacherClass[] = classesQuery.data ?? [];
  const loading = leavesQuery.isPending;
  const error = leavesQuery.isError
    ? leavesQuery.error instanceof Error
      ? leavesQuery.error.message
      : "Không thể tải danh sách đơn xin nghỉ phép."
    : null;

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [classFilter, setClassFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Review state
  const [feedbackInputs, setFeedbackInputs] = useState<Record<number, string>>({});
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<{ id: number; message: string } | null>(null);

  // Proof Modal state
  const [selectedProof, setSelectedProof] = useState<{
    url: string | null;
    studentName: string;
    studentCode: string;
    reason: string;
  } | null>(null);
  const [isProofModalOpen, setIsProofModalOpen] = useState<boolean>(false);

  const fetchData = () => {
    queryClient.invalidateQueries({ queryKey: ["teacher-leaves"] });
    queryClient.invalidateQueries({ queryKey: ["teacher-classes"] });
  };

  // Stats
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

  // Filtered requests
  const filteredRequests = useMemo(() => {
    return requests.filter((r) => {
      const matchStatus =
        statusFilter === "ALL" || r.status === statusFilter;

      const matchClass =
        classFilter === "ALL" ||
        (r.class_code && r.class_code === classFilter) ||
        (r.course_name && r.course_name === classFilter);

      const q = searchQuery.toLowerCase().trim();
      const matchSearch =
        !q ||
        (r.student_name && r.student_name.toLowerCase().includes(q)) ||
        (r.student_code && r.student_code.toLowerCase().includes(q)) ||
        (r.reason && r.reason.toLowerCase().includes(q)) ||
        (r.class_code && r.class_code.toLowerCase().includes(q));

      return matchStatus && matchClass && matchSearch;
    });
  }, [requests, statusFilter, classFilter, searchQuery]);

  const reviewMutation = useMutation({
    mutationFn: ({
      id,
      status,
      feedback,
    }: {
      id: number;
      status: "APPROVED" | "REJECTED";
      feedback: string;
    }) => reviewLeaveRequest(id, { status, feedback }),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["teacher-leaves"] });
    },
    onError: (err: unknown, variables) => {
      setActionError({
        id: variables.id,
        message:
          err instanceof Error ? err.message : "Không thể cập nhật trạng thái đơn.",
      });
    },
    onSettled: () => setActionLoadingId(null),
  });

  const handleReview = (id: number, status: "APPROVED" | "REJECTED") => {
    setActionLoadingId(id);
    setActionError(null);
    const feedback = feedbackInputs[id]?.trim() || "";
    reviewMutation.mutate({ id, status, feedback });
  };

  const handleOpenProof = (req: TeacherLeaveRequest) => {
    setSelectedProof({
      url: mediaUrl(req.proof_image),
      studentName: req.student_name || "Sinh viên",
      studentCode: req.student_code || "",
      reason: req.reason,
    });
    setIsProofModalOpen(true);
  };

  const formatDateTime = (dtStr?: string | null) => {
    if (!dtStr) return "--";
    try {
      return formatDateTimeVN(dtStr);
    } catch {
      return dtStr;
    }
  };

  return (
    <RoleGuard allowedRoles={["TEACHER"]}>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wider mb-1">
              <ClipboardCheck size={15} />
              <span>Phân hệ Giảng viên</span>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Duyệt đơn xin nghỉ phép
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              Xem xét lý do, minh chứng giấy khám bệnh và phê duyệt đơn vắng học cho sinh viên
            </p>
          </div>

          <button
            onClick={fetchData}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 shadow-sm transition-colors disabled:opacity-50 self-start md:self-auto"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            <span>Làm mới</span>
          </button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-white rounded-lg border border-slate-200 shadow-sm">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
              Tổng số đơn tiếp nhận
            </p>
            <p className="text-2xl font-bold font-mono tabular-nums text-slate-900 mt-1">
              {stats.total}
            </p>
          </div>

          <div className="p-4 bg-white rounded-lg border border-amber-200 shadow-sm bg-amber-50/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wider">
                  Chờ duyệt
                </p>
                <p className="text-2xl font-bold font-mono tabular-nums text-amber-700 mt-1">
                  {stats.pending}
                </p>
              </div>
              <div className="w-9 h-9 rounded-md bg-amber-100 border border-amber-200 flex items-center justify-center text-amber-700">
                <Clock size={18} />
              </div>
            </div>
          </div>

          <div className="p-4 bg-white rounded-lg border border-emerald-200 shadow-sm bg-emerald-50/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-emerald-700 uppercase tracking-wider">
                  Đã chấp nhận
                </p>
                <p className="text-2xl font-bold font-mono tabular-nums text-emerald-700 mt-1">
                  {stats.approved}
                </p>
              </div>
              <div className="w-9 h-9 rounded-md bg-emerald-100 border border-emerald-200 flex items-center justify-center text-emerald-700">
                <CheckCircle2 size={18} />
              </div>
            </div>
          </div>

          <div className="p-4 bg-white rounded-lg border border-rose-200 shadow-sm bg-rose-50/20">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-rose-700 uppercase tracking-wider">
                  Bị từ chối
                </p>
                <p className="text-2xl font-bold font-mono tabular-nums text-rose-700 mt-1">
                  {stats.rejected}
                </p>
              </div>
              <div className="w-9 h-9 rounded-md bg-rose-100 border border-rose-200 flex items-center justify-center text-rose-700">
                <XCircle size={18} />
              </div>
            </div>
          </div>
        </div>

        {/* Toolbar: Search, Filters */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 p-3 bg-white rounded-lg border border-slate-200 shadow-sm">
          <div className="flex flex-1 flex-wrap items-center gap-2.5">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px] md:max-w-xs">
              <Search
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="text"
                placeholder="Tìm tên SV, MSSV, lý do..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
              />
            </div>

            {/* Class filter */}
            {classes.length > 0 && (
              <select
                value={classFilter}
                onChange={(e) => setClassFilter(e.target.value)}
                className="px-3 py-1.5 text-xs rounded-md border border-slate-200 bg-slate-50/50 text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
              >
                <option value="ALL">Tất cả lớp học phần</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.class_code}>
                    {c.class_code} - {c.course_name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Status Tabs */}
          <div className="flex items-center gap-1 self-start md:self-auto">
            {[
              { id: "ALL", label: "Tất cả" },
              { id: "PENDING", label: `Chờ duyệt (${stats.pending})` },
              { id: "APPROVED", label: "Đã duyệt" },
              { id: "REJECTED", label: "Từ chối" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setStatusFilter(tab.id)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  statusFilter === tab.id
                    ? "bg-slate-900 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Global Error Notice */}
        {error && (
          <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={fetchData}
              className="text-xs font-semibold underline hover:no-underline ml-4"
            >
              Thử lại
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-32 rounded-lg bg-slate-100 border border-slate-200 animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredRequests.length === 0 && (
          <div className="p-12 text-center bg-white rounded-lg border border-slate-200 shadow-sm">
            <ClipboardCheck size={40} className="mx-auto text-slate-300 mb-3" />
            <h3 className="text-base font-semibold text-slate-800">
              Không có đơn xin nghỉ phép nào
            </h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {searchQuery || statusFilter !== "ALL" || classFilter !== "ALL"
                ? "Không tìm thấy đơn nghỉ phép phù hợp với tiêu chí lọc."
                : "Hiện tại không có đơn xin nghỉ phép nào từ sinh viên các lớp phụ trách."}
            </p>
          </div>
        )}

        {/* Requests List */}
        {!loading && filteredRequests.length > 0 && (
          <div className="space-y-4">
            {filteredRequests.map((req) => {
              const isPending = req.status === "PENDING";
              const isSubmittingThis = actionLoadingId === req.id;
              const thisError = actionError?.id === req.id ? actionError.message : null;

              return (
                <div
                  key={req.id}
                  className={`bg-white rounded-lg border transition-all shadow-sm overflow-hidden ${
                    isPending
                      ? "border-amber-200/80 ring-1 ring-amber-200/50"
                      : "border-slate-200"
                  }`}
                >
                  {/* Card Header */}
                  <div className="px-5 py-3.5 bg-slate-50/70 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 text-sm">
                            {req.student_name || "Sinh viên"}
                          </span>
                          <span className="font-mono tabular-nums text-xs font-medium text-slate-600 px-1.5 py-0.5 rounded bg-white border border-slate-200">
                            {req.student_code || "MSSV"}
                          </span>
                          {req.class_name && (
                            <span className="text-xs text-slate-500">
                              • Lớp: {req.class_name}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2.5">
                      {isPending ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          <Clock size={12} />
                          Chờ duyệt
                        </span>
                      ) : req.status === "APPROVED" ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 size={12} />
                          Đã chấp nhận
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                          <XCircle size={12} />
                          Bị từ chối
                        </span>
                      )}

                      <span className="text-xs text-slate-400 font-mono tabular-nums">
                        Nộp: {formatDateTime(req.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="p-5 space-y-4">
                    {/* Course & Schedule Meta */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 p-3 bg-slate-50 rounded-md border border-slate-200/80 text-xs">
                      <div>
                        <span className="text-slate-400 block mb-0.5">Môn học / Mã lớp:</span>
                        <span className="font-semibold text-slate-800">
                          {req.course_name || "Môn học"} ({req.class_code || "--"})
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block mb-0.5">Buổi học xin nghỉ:</span>
                        <span className="font-medium text-slate-800">
                          {req.study_date ? String(req.study_date) : "--"}
                          {req.start_time && ` (${req.start_time} - ${req.end_time || ""})`}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block mb-0.5">Phòng học:</span>
                        <span className="font-mono text-slate-800">
                          {req.room_name || "Không rõ"}
                        </span>
                      </div>
                    </div>

                    {/* Reason & Proof Button */}
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                      <div className="flex-1">
                        <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider block mb-1">
                          Lý do xin nghỉ:
                        </span>
                        <p className="text-sm text-slate-800 bg-white p-3 rounded-md border border-slate-200 leading-relaxed">
                          {req.reason}
                        </p>
                      </div>

                      <div className="shrink-0 sm:self-start pt-1">
                        {req.proof_image ? (
                          <button
                            type="button"
                            onClick={() => handleOpenProof(req)}
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 shadow-2xs hover:border-slate-300 transition-all"
                          >
                            <FileText size={14} className="text-blue-600" />
                            <span>Xem minh chứng đính kèm</span>
                          </button>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-slate-400 italic px-3 py-2">
                            Không có minh chứng
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Pending Action Controls */}
                    {isPending && (
                      <div className="pt-3 border-t border-slate-200/80 space-y-3">
                        {thisError && (
                          <div className="p-2 rounded bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
                            <AlertCircle size={14} />
                            <span>{thisError}</span>
                          </div>
                        )}

                        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                          <div className="flex-1">
                            <input
                              type="text"
                              placeholder="Nhập phản hồi / lý do duyệt hoặc từ chối (không bắt buộc)..."
                              value={feedbackInputs[req.id] || ""}
                              onChange={(e) =>
                                setFeedbackInputs({
                                  ...feedbackInputs,
                                  [req.id]: e.target.value,
                                })
                              }
                              className="w-full px-3 py-1.5 text-xs rounded-md border border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-400"
                            />
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              disabled={isSubmittingThis}
                              onClick={() => handleReview(req.id, "REJECTED")}
                              className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-md text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-colors disabled:opacity-50"
                            >
                              {isSubmittingThis ? (
                                <Loader2 size={13} className="animate-spin" />
                              ) : (
                                <X size={13} />
                              )}
                              <span>Từ chối</span>
                            </button>

                            <button
                              type="button"
                              disabled={isSubmittingThis}
                              onClick={() => handleReview(req.id, "APPROVED")}
                              className="inline-flex items-center gap-1 px-4 py-1.5 rounded-md text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 border border-emerald-600 shadow-xs transition-colors disabled:opacity-50"
                            >
                              {isSubmittingThis ? (
                                <Loader2 size={13} className="animate-spin" />
                              ) : (
                                <Check size={13} />
                              )}
                              <span>Chấp nhận</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Historical Review Feedback (if already reviewed) */}
                    {!isPending && req.teacher_feedback && (
                      <div className="pt-3 border-t border-slate-100 flex items-start gap-2 text-xs text-slate-600 bg-slate-50/50 p-2.5 rounded">
                        <MessageSquare size={14} className="mt-0.5 text-slate-400 shrink-0" />
                        <div>
                          <span className="font-medium text-slate-700">Phản hồi của giảng viên: </span>
                          <span>{req.teacher_feedback}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Proof Preview Modal */}
        <ProofPreviewModal
          isOpen={isProofModalOpen}
          onClose={() => setIsProofModalOpen(false)}
          proofUrl={selectedProof?.url || null}
          studentName={selectedProof?.studentName}
          studentCode={selectedProof?.studentCode}
          reason={selectedProof?.reason}
        />
      </div>
    </RoleGuard>
  );
}
