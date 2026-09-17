"use client";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { addStudent, deleteStudent, getStudents, studentPhoto, updateStudent, type Student } from "@/lib/api";

export default function Students() {
  const [list, setList] = useState<Student[]>([]);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState<Student | null>(null);
  const { register, handleSubmit, reset } = useForm();
  const { register: regEdit, handleSubmit: submitEdit, reset: resetEdit, setValue: setEditVal } = useForm();

  const load = () => getStudents(page, 50, q).then((p) => {
    const arr = Array.isArray(p) ? p as unknown as Student[] : p.items;
    setList(arr);
    setTotal(Array.isArray(p) ? arr.length : (p as { total: number }).total);
  }).catch(() => {});
  useEffect(() => { load(); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  const onAdd = handleSubmit(async (v) => {
    setErr("");
    const fd = new FormData();
    fd.append("code", v.code);
    fd.append("name", v.name);
    fd.append("class_name", v.class_name ?? "");
    fd.append("photo", v.photo[0]);
    try {
      await addStudent(fd);
      reset();
      setPage(1);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "loi");
    }
  });

  const startEdit = (s: Student) => {
    setEditing(s);
    setEditVal("name", s.name);
    setEditVal("class_name", s.class_name);
  };

  const onEdit = submitEdit(async (v) => {
    if (!editing) return;
    setErr("");
    const fd = new FormData();
    fd.append("name", v.name);
    fd.append("class_name", v.class_name ?? "");
    if (v.photo?.[0]) fd.append("photo", v.photo[0]);
    try {
      await updateStudent(editing.id, fd);
      setEditing(null);
      resetEdit();
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "loi");
    }
  });

  const onDel = async (s: Student) => {
    if (!confirm(`Xóa ${s.code} - ${s.name}?`)) return;
    setErr("");
    try {
      await deleteStudent(s.id);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "loi");
    }
  };

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="text-2xl font-bold">Học sinh / Sinh viên</h1>
      <form onSubmit={onAdd} className="mt-4 grid gap-2 rounded border p-4 sm:grid-cols-4">
        <input {...register("code", { required: true })} placeholder="MSSV" className="rounded border px-2 py-1" />
        <input {...register("name", { required: true })} placeholder="Họ tên" className="rounded border px-2 py-1" />
        <input {...register("class_name")} placeholder="Lớp" className="rounded border px-2 py-1" />
        <input {...register("photo", { required: true })} type="file" accept="image/*" className="text-sm" />
        <button className="rounded bg-black px-3 py-1 text-white sm:col-span-4">Thêm (chụp/upload ảnh mặt)</button>
        {err && <p className="text-sm text-red-700 sm:col-span-4">{err}</p>}
      </form>
      <div className="mt-4 flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm MSSV/tên…"
          className="flex-1 rounded border px-2 py-1" onKeyDown={(e) => e.key === "Enter" && (setPage(1), load())} />
        <button onClick={() => { setPage(1); load(); }} className="rounded border px-3 py-1">Tìm</button>
      </div>
      <table className="mt-4 w-full text-sm">
        <thead><tr className="text-left text-zinc-500"><th>Ảnh</th><th>MSSV</th><th>Tên</th><th>Lớp</th><th></th></tr></thead>
        <tbody>{list.map((s) => (
          <tr key={s.id} className="border-t">
            <td>{s.photo ? <img src={studentPhoto(s.photo)} alt={s.code} className="h-10 w-10 rounded object-cover" /> : <span className="text-zinc-400">—</span>}</td>
            <td>{s.code}</td><td>{s.name}</td><td>{s.class_name}</td>
            <td className="flex gap-2 py-1">
              <button onClick={() => startEdit(s)} className="rounded border px-2 py-0.5">Sửa</button>
              <button onClick={() => onDel(s)} className="rounded border px-2 py-0.5 text-red-700">Xóa</button>
            </td></tr>
        ))}</tbody>
      </table>
      {editing && (
        <form onSubmit={onEdit} className="mt-4 grid gap-2 rounded border border-amber-500 p-4 sm:grid-cols-3">
          <p className="font-medium sm:col-span-3">Sửa {editing.code} (đổi ảnh = cập nhật lại embedding)</p>
          <input {...regEdit("name", { required: true })} placeholder="Họ tên" className="rounded border px-2 py-1" />
          <input {...regEdit("class_name")} placeholder="Lớp" className="rounded border px-2 py-1" />
          <input {...regEdit("photo")} type="file" accept="image/*" className="text-sm" />
          <div className="flex gap-2 sm:col-span-3">
            <button className="rounded bg-black px-3 py-1 text-white">Lưu</button>
            <button type="button" onClick={() => { setEditing(null); resetEdit(); }} className="rounded border px-3 py-1">Hủy</button>
          </div>
          {err && <p className="text-sm text-red-700 sm:col-span-3">{err}</p>}
        </form>
      )}
      <div className="mt-2 flex items-center gap-2 text-sm">
        <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded border px-2 py-1">‹</button>
        <span>Trang {page} / {Math.max(1, Math.ceil(total / 50))}</span>
        <button onClick={() => setPage((p) => p + 1)} className="rounded border px-2 py-1">›</button>
      </div>
    </main>
  );
}
