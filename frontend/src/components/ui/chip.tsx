import * as React from "react";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

export function Chip({ label, icon, onRemove, active, className, onClick }: { label: string; icon?: React.ReactNode; onRemove?: ()=>void; active?: boolean; className?: string; onClick?: ()=>void }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors", active ? "bg-[var(--color-accent-soft)] border-[var(--color-accent)]/30 text-[var(--color-accent)]" : "bg-[var(--color-surface-3)] border-[var(--color-border-default)] text-[var(--color-text-secondary)]", onClick && "cursor-pointer hover:border-[var(--color-border-active)]", className)} onClick={onClick}>
      {icon} {label} {onRemove && <button onClick={(e)=>{ e.stopPropagation(); onRemove();}} className="ml-0.5 hover:text-white"><X size={12}/></button>}
    </span>
  );
}
export function ContextChip(props: { label: string; confidence?: number; onRemove?: ()=>void; onClick?: ()=>void }) {
  return <Chip label={`${props.label}${props.confidence ? ` · ${Math.round(props.confidence*100)}%` : ""}`} active onClick={props.onClick} onRemove={props.onRemove} />;
}
