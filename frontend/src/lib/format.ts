export function formatConfidence(v: number): string {
  return `${Math.round(v * 100)}%`;
}
export function getConfidenceLevel(v: number): "low" | "moderate" | "high" | "very_high" {
  if (v >= 0.90) return "very_high";
  if (v >= 0.75) return "high";
  if (v >= 0.50) return "moderate";
  return "low";
}
export function getConfidenceTone(v: number): string {
  const l = getConfidenceLevel(v);
  if (l === "very_high") return "text-emerald-400";
  if (l === "high") return "text-sky-400";
  if (l === "moderate") return "text-amber-400";
  return "text-red-400";
}
export function formatArea(ha: number): string {
  if (ha >= 1000) return `${(ha/1000).toFixed(2)}k ha`;
  return `${ha.toFixed(1)} ha`;
}
export function formatDate(iso: string): string {
  try { return new Date(iso).toLocaleDateString("en-IN", { year:"numeric", month:"short", day:"numeric"}); } catch { return iso; }
}
export function relativeTime(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const mins = Math.floor(diff/60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins/60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs/24);
  if (days < 7) return `${days}d ago`;
  return formatDate(iso);
}
