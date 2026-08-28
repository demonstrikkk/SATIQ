import { Satellite } from "lucide-react";

export function SatiqLogo({ size = 28 }: { size?: number }) {
  return (
    <div
      style={{ width: size, height: size }}
      className="relative rounded-xl bg-gradient-to-br from-[#38D6FF] to-[#0EA5E9] flex items-center justify-center shadow-[0_4px_16px_rgba(56,214,255,0.35),0_1px_0_rgba(255,255,255,0.2)_inset] overflow-hidden"
    >
      <div className="absolute inset-0 rounded-xl bg-gradient-to-tr from-white/10 to-transparent" />
      <Satellite size={size * 0.52} className="text-white relative z-10" strokeWidth={2.1} />
      <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.9)] animate-pulse" />
    </div>
  );
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-baseline gap-[1px] select-none">
      <span className="font-black tracking-[0.16em] text-[13px] text-white">SA</span>
      <span className="font-black tracking-[0.16em] text-[13px] text-[#38D6FF]">T</span>
      <span className="font-black tracking-[0.16em] text-[13px] text-white">IQ</span>
      {!compact && <span className="ml-1.5 h-1 w-1 rounded-full bg-[#38D6FF] animate-pulse hidden sm:inline-block" />}
    </span>
  );
}

export function SatiqMark({ size = 32 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <SatiqLogo size={size} />
      <div className="leading-none">
        <Wordmark />
        <div className="text-[9px] tracking-[0.18em] text-white/35 font-semibold -mt-0.5">ORBITAL INTELLIGENCE</div>
      </div>
    </div>
  );
}
