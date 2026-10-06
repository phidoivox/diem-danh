"use client";

// Shell: khung app, providers, UI dùng chung, date, validation.
// Whitelist duy nhất app/ và các features khác được phép import.
export { AuthProvider, useAuth } from "./auth-context";
export { QueryProvider } from "./query-provider";
export { AppShell } from "./app-shell";
export { RoleGuard } from "./role-guard";
export { Sidebar } from "./sidebar";
export { Topbar } from "./topbar";
export { Modal, cn } from "./modal";
export { ConfirmDialog } from "./confirm-dialog";
export { DataTable } from "./data-table";
export { SearchInput } from "./search-input";
export { StatusBadge } from "./status-badge";
export type { AttendanceStatus } from "./status-badge";
export { FileDropzone } from "./file-dropzone";
export { AuthedSnapshotImg } from "./authed-snapshot-img";
export { UserAvatar } from "./user-avatar";
export { useDebouncedValue } from "./use-debounced-value";
export * from "./http";
export * from "./date";
export * from "./validation";
// Pages thuộc shell: home redirect, layout đã dùng AppShell/Providers trực tiếp.
export { default as HomePage } from "./home-page";
export { default as AdminSettingsPage } from "./settings-page";
