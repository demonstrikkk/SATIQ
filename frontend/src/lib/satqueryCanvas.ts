/** Synthetic satellite canvas renderers — exact port from satquery-ai.html for visual parity. */
export function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fitCanvas(canvas: HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(1, Math.round(rect.width || canvas.width || 300));
  const h = Math.max(1, Math.round(rect.height || canvas.height || 150));
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

export function drawOptical(canvas: HTMLCanvasElement, seed = 11, growth = 0.5) {
  const { ctx, w, h } = fitCanvas(canvas);
  const rnd = mulberry32(seed);
  ctx.fillStyle = "#232b1f";
  ctx.fillRect(0, 0, w, h);
  for (let i = 0; i < 140; i++) {
    const x = rnd() * w, y = rnd() * h, r = 6 + rnd() * 22;
    const g = 60 + Math.floor(rnd() * 70);
    ctx.fillStyle = `rgba(${40 + g * 0.3},${g + 30},${25 + g * 0.25},0.5)`;
    ctx.beginPath();
    ctx.ellipse(x, y, r, r * 0.6, rnd() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.strokeStyle = "rgba(10,15,10,0.35)";
  ctx.lineWidth = 1;
  for (let x = 0; x < w; x += w / 7) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
  for (let y = 0; y < h; y += h / 5) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
  ctx.strokeStyle = "rgba(80,120,150,0.55)";
  ctx.lineWidth = Math.max(2, h * 0.04);
  ctx.beginPath();
  ctx.moveTo(0, h * 0.75);
  ctx.bezierCurveTo(w * 0.3, h * 0.6, w * 0.6, h * 0.9, w, h * 0.7);
  ctx.stroke();
  const bx = w * 0.62, by = h * 0.28;
  const count = Math.floor(10 + growth * 26);
  for (let i = 0; i < count; i++) {
    const x = bx + (rnd() - 0.5) * w * (0.28 + growth * 0.22);
    const y = by + (rnd() - 0.5) * h * (0.34 + growth * 0.22);
    const s = 3 + rnd() * 5;
    ctx.fillStyle = `rgba(${170 + rnd() * 40},${165 + rnd() * 30},${150 + rnd() * 30},0.85)`;
    ctx.fillRect(x, y, s, s * 0.7);
  }
  ctx.strokeStyle = "rgba(210,205,190,0.5)";
  ctx.lineWidth = 1.4;
  ctx.beginPath(); ctx.moveTo(w * 0.35, h); ctx.lineTo(w * 0.68, h * 0.15); ctx.stroke();
}

export function drawSAR(canvas: HTMLCanvasElement, seed = 22) {
  const { ctx, w, h } = fitCanvas(canvas);
  const rnd = mulberry32(seed);
  const imgW = Math.max(1, Math.floor(w)), imgH = Math.max(1, Math.floor(h));
  // Use fill loop for speed instead of createImageData pixel loop in original
  ctx.fillStyle = "#2a2f2a";
  ctx.fillRect(0, 0, w, h);
  // speckle mottling via semi-transparent dots
  for (let i = 0; i < 4000; i++) {
    const x = rnd() * w, y = rnd() * h;
    const v = 40 + rnd() * 50;
    ctx.fillStyle = `rgba(${v},${v * 1.02},${v * 0.98},0.9)`;
    ctx.fillRect(x, y, 1, 1);
  }
  ctx.fillStyle = "rgba(6,10,9,0.55)";
  ctx.beginPath(); ctx.ellipse(w * 0.15, h * 0.78, w * 0.22, h * 0.14, 0.3, 0, Math.PI * 2); ctx.fill();
  for (let i = 0; i < 80; i++) {
    const x = w * 0.55 + rnd() * w * 0.35, y = h * 0.15 + rnd() * h * 0.35;
    ctx.fillStyle = `rgba(230,230,225,${0.25 + rnd() * 0.5})`;
    ctx.fillRect(x, y, 1.5 + rnd() * 2, 1.5 + rnd() * 2);
  }
}

export function drawChangeMap(canvas: HTMLCanvasElement, seed = 33) {
  const { ctx, w, h } = fitCanvas(canvas);
  const rnd = mulberry32(seed);
  ctx.fillStyle = "#161b19"; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "rgba(91,141,191,0.55)";
  ctx.beginPath(); ctx.ellipse(w * 0.15, h * 0.78, w * 0.2, h * 0.13, 0.3, 0, Math.PI * 2); ctx.fill();
  for (let i = 0; i < 10; i++) {
    const x = w * 0.7 + rnd() * w * 0.25, y = h * 0.55 + rnd() * h * 0.35;
    ctx.fillStyle = "rgba(6,182,212,0.35)";
    ctx.beginPath(); ctx.ellipse(x, y, 4 + rnd() * 6, 3 + rnd() * 4, rnd() * Math.PI, 0, Math.PI * 2); ctx.fill();
  }
  for (let i = 0; i < 36; i++) {
    const x = w * 0.6 + rnd() * w * 0.3, y = h * 0.14 + rnd() * h * 0.32;
    ctx.fillStyle = rnd() > 0.5 ? "rgba(193,85,74,0.85)" : "rgba(217,164,65,0.85)";
    ctx.fillRect(x, y, 3 + rnd() * 4, 3 + rnd() * 4);
  }
}

export function drawMapView(canvas: HTMLCanvasElement) {
  const { ctx, w, h } = fitCanvas(canvas);
  ctx.fillStyle = "#0b0f0d"; ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "rgba(90,105,98,0.25)"; ctx.lineWidth = 1;
  for (let x = 0; x < w; x += 28) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
  for (let y = 0; y < h; y += 28) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
  ctx.strokeStyle = "#06B6D4"; ctx.lineWidth = 1.5; ctx.setLineDash([4, 3]);
  ctx.strokeRect(w * 0.32, h * 0.18, w * 0.4, h * 0.5);
  ctx.setLineDash([]);
  ctx.fillStyle = "rgba(193,85,74,0.7)";
  for (let i = 0; i < 5; i++) { ctx.beginPath(); ctx.arc(w * 0.45 + i * 14, h * 0.3 + ((i % 2) * 18), 4, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = "rgba(91,141,191,0.7)";
  ctx.beginPath(); ctx.arc(w * 0.2, h * 0.72, 10, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = "rgba(233,236,233,0.5)"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(w / 2 - 6, h / 2); ctx.lineTo(w / 2 + 6, h / 2); ctx.moveTo(w / 2, h / 2 - 6); ctx.lineTo(w / 2, h / 2 + 6); ctx.stroke();
}
