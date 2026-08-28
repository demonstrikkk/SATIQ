import * as React from "react";
import { AlertTriangle, RefreshCw, Home, Bug } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props { children: React.ReactNode; }
interface State { hasError: boolean; error?: Error; }

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[Satiq ErrorBoundary]", error, info);
  }

  render() {
    if (this.state.hasError) {
      return <ErrorPage error={this.state.error} onReset={() => this.setState({ hasError: false, error: undefined })} />;
    }
    return this.props.children;
  }
}

export function ErrorPage({ error, onReset }: { error?: Error; onReset?: () => void }) {
  const isBarError = error?.message?.includes("bar");
  return (
    <div className="min-h-screen w-full bg-[#02070D] flex flex-col items-center justify-center p-6 text-center">
      <div className="w-full max-w-[520px] rounded-2xl border border-white/[0.06] bg-[#07111C] p-8 shadow-[0_16px_40px_rgba(0,0,0,0.5)]">
        <div className="h-12 w-12 rounded-xl bg-[#FF4D5E]/10 border border-[#FF4D5E]/20 grid place-items-center mx-auto">
          <AlertTriangle size={20} className="text-[#FF4D5E]" />
        </div>
        <h1 className="text-xl font-semibold tracking-tight text-white mt-4">Unexpected Application Error</h1>
        <p className="text-sm text-white/55 mt-2 leading-relaxed">
          {isBarError ? "A chart failed to render. This usually happens when chart data is incomplete while streaming. Try again — the next response will render cleanly." : "Something broke while rendering this view."}
        </p>
        {error && (
          <div className="mt-4 rounded-xl bg-[#02070D] border border-white/10 p-3 text-left">
            <div className="flex items-center gap-1.5 text-xs font-mono text-white/40"><Bug size={12} /> {error.name}: {error.message}</div>
            <div className="text-[11px] font-mono text-white/25 mt-1 line-clamp-3">{error.stack?.slice(0, 300)}</div>
          </div>
        )}
        <div className="mt-6 flex items-center justify-center gap-2">
          <Button onClick={() => (onReset ? onReset() : window.location.reload())} className="bg-[#38D6FF] text-[#02070D] hover:bg-[#38D6FF]/90">
            <RefreshCw size={14} /> Try again
          </Button>
          <Button variant="outline" onClick={() => (window.location.href = "/workspace")} className="border-white/10 text-white/70 hover:text-white">
            <Home size={14} /> Go to workspace
          </Button>
        </div>
        <div className="mt-4 text-[11px] text-white/25">If this persists, check console or clear <code className="px-1 py-0.5 rounded bg-white/5 border border-white/10">node_modules/.vite</code> and restart.</div>
      </div>
    </div>
  );
}
