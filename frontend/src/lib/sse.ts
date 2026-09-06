import { ExecutionEventSchema, type ExecutionEvent } from "@/schemas/execution";

export type SSEHandler = (ev: ExecutionEvent) => void;

export function parseSSELine(line: string): ExecutionEvent | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith(":")) return null;
  if (trimmed.startsWith("data:")) {
    const json = trimmed.slice(5).trim();
    if (!json) return null;
    try {
      const obj = JSON.parse(json);
      const parsed = ExecutionEventSchema.safeParse(obj);
      return parsed.success ? parsed.data : null;
    } catch { return null; }
  }
  return null;
}

export async function consumeSSE(url: string, handler: SSEHandler, signal?: AbortSignal): Promise<void> {
  const res = await fetch(url, { headers: { Accept: "text/event-stream" }, signal });
  if (!res.body) return;
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      for (const line of part.split("\n")) {
        const ev = parseSSELine(line);
        if (ev) handler(ev);
      }
    }
    if (signal?.aborted) break;
  }
}
