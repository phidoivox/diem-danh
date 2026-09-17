"use client";
import { useEffect, useRef, useState } from "react";
import { API, WS, getAtt, type Att } from "@/lib/api";

type R = { tracker_id: number; student: string; name: string; class_name: string; score: number; uniform: string; violations: string[]; log: boolean; bbox: number[] };
type Student = { id: number; code: string; name: string; class_name: string };

const okColor = "#22c55e";
const badColor = "#ef4444";

// Ve box tren video (webcam) hoac img MJPEG (rtsp), noi suy giua 2 ket qua AI -> het giat.
function useSmoothBoxes(
  video: React.RefObject<HTMLVideoElement | null>,
  img: React.RefObject<HTMLImageElement | null>,
  canvas: React.RefObject<HTMLCanvasElement | null>,
  boxes: React.RefObject<R[]>,
) {
  useEffect(() => {
    let raf = 0;
    const cur = new Map<number, number[]>(); // tid -> bbox hien tai (noi suy)
    const base = () => {
      const v = video.current;
      if (v && v.videoWidth > 0) return { w: v.videoWidth, h: v.videoHeight };
      const im = img.current;
      if (im && im.naturalWidth > 0) return { w: im.clientWidth || im.naturalWidth, h: im.clientHeight || im.naturalHeight };
      return null;
    };
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const c = canvas.current, b0 = base();
      if (!c || !b0) return;
      if (c.width !== Math.round(b0.w) || c.height !== Math.round(b0.h)) {
        c.width = Math.round(b0.w);
        c.height = Math.round(b0.h);
      }
      const sx = c.width / 640, sy = c.height / 480; // bbox backend tinh tren 640x480
      const ctx = c.getContext("2d")!;
      ctx.clearRect(0, 0, c.width, c.height);
      const want = new Map(boxes.current.map((r) => [r.tracker_id, r]));
      for (const tid of [...cur.keys()]) if (!want.has(tid)) cur.delete(tid);
      ctx.lineWidth = 2;
      ctx.font = "14px sans-serif";
      for (const r of boxes.current) {
        const prev = cur.get(r.tracker_id) ?? r.bbox;
        const b = prev.map((p, i) => p + (r.bbox[i] - p) * 0.35);
        cur.set(r.tracker_id, b);
        const [x1, y1, x2, y2] = [b[0] * sx, b[1] * sy, b[2] * sx, b[3] * sy];
        const col = r.uniform === "ok" ? okColor : badColor;
        ctx.strokeStyle = col;
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        ctx.fillStyle = col;
        ctx.fillText(r.name || r.student, x1, Math.max(12, y1 - 4));
      }
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [video, img, canvas, boxes]);
}

export default function Attendance() {
  const [src, setSrc] = useState<"webcam" | "rtsp">("webcam");
  const [log, setLog] = useState<Att[]>([]);
  const [rtsp, setRtsp] = useState("");
  const [students, setStudents] = useState<Map<string, Student>>(new Map());
  const [focus, setFocus] = useState<R | null>(null);
  const [inferMs, setInferMs] = useState(0);
  const vref = useRef<HTMLVideoElement>(null);
  const iref = useRef<HTMLImageElement>(null);
  const cref = useRef<HTMLCanvasElement>(null);
  const boxes = useRef<R[]>([]); // webcam
  const rtspBoxes = useRef<R[]>([]); // rtsp
  const activeBoxes = src === "webcam" ? boxes : rtspBoxes;
  const ws = useRef<WebSocket | null>(null);
  const lastSpeak = useRef(0);
  const stopRef = useRef(false);
  useSmoothBoxes(vref, iref, cref, activeBoxes);

  const stopAll = () => {
    stopRef.current = true;
    if (ws.current) { ws.current.close(); ws.current = null; }
    const s = vref.current?.srcObject as MediaStream | null;
    s?.getTracks().forEach((t) => t.stop());
    if (vref.current) vref.current.srcObject = null;
    if (iref.current) iref.current.src = "";
    boxes.current = [];
    rtspBoxes.current = [];
    setFocus(null);
    fetch(`${API}/api/camera/close`, { method: "POST" }).catch(() => {});
  };

  // saver_loop ghi DB async sau khi ws bao log: doi 800ms moi GET keo miss
  const refreshLogSoon = () => {
    setTimeout(() => getAtt(20).then(setLog).catch(() => {}), 800);
  };

  // Tat camera khi roi trang (doi tab / chuyen route): khong de den sang.
  useEffect(() => {
    fetch(`${API}/api/students`).then((r) => r.json()).then((l: Student[] | { items: Student[] }) =>
      setStudents(new Map((Array.isArray(l) ? l : l.items).map((s) => [s.code, s])))).catch(() => {});
    getAtt(20).then(setLog).catch(() => {});
    const off = () => stopAll();
    const onVis = () => { if (document.hidden) stopAll(); };
    window.addEventListener("pagehide", off);
    window.addEventListener("beforeunload", off);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      off();
      window.removeEventListener("pagehide", off);
      window.removeEventListener("beforeunload", off);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  const speak = (t: string) => {
    const now = Date.now();
    if (now - lastSpeak.current < 3000) return;
    lastSpeak.current = now;
    speechSynthesis.cancel();
    speechSynthesis.speak(new SpeechSynthesisUtterance(t));
  };

  const startWebcam = async () => {
    stopRef.current = false;
    const s = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
    if (stopRef.current || !vref.current) { s.getTracks().forEach((t) => t.stop()); return; }
    vref.current.srcObject = s;
    await new Promise<void>((ok) => { vref.current!.onloadedmetadata = () => ok(); });
    const sock = new WebSocket(WS);
    ws.current = sock;
    sock.onmessage = (e) => {
      const d = JSON.parse(e.data);
      boxes.current = d.results;
      if (typeof d.infer_ms === "number") setInferMs(d.infer_ms);
      const hit = (d.results as R[]).find((r) => r.student !== "unknown");
      if (hit) setFocus(hit);
      for (const r of d.results as R[]) {
        if (r.log) {
          speak(`Điểm danh ${r.name || r.student}`);
          refreshLogSoon();
        } else if (r.student !== "unknown" && r.uniform === "violation") {
          speak("Sai đồng phục");
        }
      }
    };
    await new Promise((r) => sock.addEventListener("open", r, { once: true }));
    const c = document.createElement("canvas");
    c.width = 640; c.height = 480;
    const ctx = c.getContext("2d")!;
    // Gui throttled: chi gui frame moi khi socket ranh, khong setInterval blind.
    const loop = () => {
      if (stopRef.current || sock.readyState !== 1 || !vref.current || vref.current.videoWidth === 0) {
        if (!stopRef.current) setTimeout(loop, 200);
        return;
      }
      ctx.drawImage(vref.current, 0, 0, 640, 480);
      c.toBlob((b) => {
        if (!stopRef.current && sock.readyState === 1 && b) sock.send(b);
        setTimeout(loop, 120);
      }, "image/jpeg", 0.6);
    };
    loop();
  };

  const switchSrc = (s: "webcam" | "rtsp") => {
    stopAll();
    setSrc(s);
    if (s === "webcam") startWebcam().catch(() => {});
    else pollRtsp();
  };

  const pollRtsp = () => {
    // Poll ket qua AI rieng nhịp video: /results nhe (vai KB JSON),
    // khong kem theo anh nhu MJPEG+annotate -> video khong doi AI.
    const id = setInterval(async () => {
      if (stopRef.current) { clearInterval(id); return; }
      try {
        const r = await fetch(`${API}/api/camera/results`, { cache: "no-store" });
        const d = await r.json();
        rtspBoxes.current = d.results ?? [];
        if (typeof d.infer_ms === "number") setInferMs(d.infer_ms);
        const hit = (d.results as R[]).find((x) => x.student !== "unknown");
        if (hit) setFocus(hit);
        if ((d.results as R[]).some((x) => x.log)) refreshLogSoon();
      } catch { /* bo qua, poll tiep vong sau */ }
    }, 400);
  };

  const info = (r: R | null): Student | null =>
    r && r.student !== "unknown" ? students.get(r.student) ?? { id: 0, code: r.student, name: r.name, class_name: r.class_name } : null;
  const cur = info(focus);

  return (
    <main className="mx-auto max-w-6xl p-6">
      <div className="flex items-center gap-2">
        <button onClick={() => switchSrc("webcam")} className={`rounded border px-3 py-1 ${src === "webcam" ? "bg-black text-white" : ""}`}>Webcam</button>
        <button onClick={() => switchSrc("rtsp")} className={`rounded border px-3 py-1 ${src === "rtsp" ? "bg-black text-white" : ""}`}>Camera IP</button>
        <button onClick={stopAll} className="rounded border px-3 py-1 text-red-700">Tắt camera</button>
        <span className={`ml-auto rounded px-2 py-1 text-xs ${inferMs > 500 ? "bg-red-100 text-red-700" : "bg-zinc-100 text-zinc-600"}`}>
          AI {inferMs}ms{inferMs > 500 ? " — chậm, box trễ so với video là bình thường" : ""}
        </span>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-[2fr_1fr]">
        {/* Trai: video nhan dien, khung ve muot bang rAF noi suy */}
        <div>
          {src === "webcam" ? (
            <div className="relative">
              <video ref={vref} autoPlay muted playsInline className="w-full rounded border bg-black" />
              <canvas ref={cref} className="absolute inset-0 h-full w-full" />
            </div>
          ) : (
            <>
              <form className="mb-2 flex gap-2" onSubmit={(e) => {
                e.preventDefault();
                fetch(`${API}/api/camera/open?url=${encodeURIComponent(rtsp)}`, { method: "POST" });
              }}>
                <input value={rtsp} onChange={(e) => setRtsp(e.target.value)} placeholder="rtsp://…"
                  className="flex-1 rounded border px-2 py-1" />
                <button className="rounded bg-black px-3 py-1 text-white">Mở</button>
              </form>
              <div className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img ref={iref} src={`${API}/api/camera/stream`} alt="rtsp" className="w-full rounded border" />
                <canvas ref={cref} className="absolute inset-0 h-full w-full" />
              </div>
            </>
          )}
        </div>
        {/* Phai: thong tin hoc sinh dang focus + lich su */}
        <div className="space-y-4">
          <div className="rounded border p-3">
            <h2 className="font-semibold">Thông tin sinh viên</h2>
            {cur ? (
              <div className="mt-2 text-sm">
                <div className="text-lg font-bold">{cur.name}</div>
                <div>MSSV: {cur.code}</div>
                <div>Lớp: {cur.class_name || "—"}</div>
                <div>Độ tin cậy: {focus!.score}</div>
                <div className={focus!.uniform === "ok" ? "text-green-700" : "text-red-700"}>
                  Đồng phục: {focus!.uniform}{focus!.violations.length ? ` (${focus!.violations.join(", ")})` : ""}
                </div>
              </div>
            ) : (
              <p className="mt-2 text-sm text-zinc-500">Chưa nhận diện ai. Đứng trước camera…</p>
            )}
          </div>
          <div>
            <h2 className="font-semibold">Mới điểm danh</h2>
            <ul className="mt-2 space-y-1 text-sm">
              {log.map((a) => (
                <li key={a.id} className="rounded border p-2">
                  <b>{students.get(a.code)?.name ?? a.code}</b> <span className="text-zinc-500">({a.code})</span> — {a.uniform} <span className="text-zinc-500">{a.at}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </main>
  );
}
