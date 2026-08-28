import { useState } from "react";
import { MapPin, Layers, Navigation, PenTool, Copy, Ruler, Box, Locate, Plus, Minus, Crosshair, AlertTriangle } from "lucide-react";
import { MapCanvas } from "@/components/map/MapCanvas";
import { useMapStore } from "@/store/map.store";

export function GeoCanvas() {
  const [period, setPeriod] = useState<"24h" | "7d" | "30d">("7d");
  const [showFlood, setShowFlood] = useState(true);
  const [showWater, setShowWater] = useState(true);
  const { layers, toggleLayer } = useMapStore();

  return (
    <div className="relative h-full rounded-xl overflow-hidden border-0 bg-[#090D14]">
      <div className="h-full min-h-[520px] relative">
        <MapCanvas />

        {/* overlays — flood / water / change — rendered as absolute spatial layers on top of map for intelligence feel */}
        {showFlood && (
          <>
            <div className="absolute left-[32%] top-[34%] h-[18%] w-[22%] rounded-[14px] bg-[#FF4D5E]/18 border border-[#FF4D5E]/45 shadow-[0_0_22px_rgba(255,77,94,0.28)] backdrop-blur-[0.5px]" />
            <div className="absolute left-[38%] top-[42%] h-2 w-2 rounded-full bg-[#FF4D5E] shadow-[0_0_10px_rgba(255,77,94,0.9)] animate-pulse" />
          </>
        )}
        {showWater && (
          <div className="absolute right-[18%] top-[28%] h-[26%] w-[18%] rounded-[16px] border border-[#06B6D4]/50 bg-[#06B6D4]/12 shadow-[0_0_18px_rgba(6,182,212,0.22)]" />
        )}
        <div className="absolute left-[14%] bottom-[26%] h-[14%] w-[16%] rounded-xl border border-[#FF9A4A]/45 bg-[#FF9A4A]/10" />

        {/* top-left geographic controls */}
        <div className="absolute top-3 left-3 flex items-center gap-2 z-10">
          <div className="flex items-center gap-2 rounded-full bg-[#090D14]/85 backdrop-blur border border-slate-800/60 px-3 py-1.5 text-xs text-white">
            <MapPin size={12} className="text-[#06B6D4]" /> Bengaluru, Karnataka
          </div>
          <div className="hidden md:flex items-center gap-1 rounded-full bg-[#090D14]/85 backdrop-blur border border-slate-800/60 p-1">
            {(["24h", "7d", "30d"] as const).map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-all ${period === p ? "bg-[#06B6D4] text-[#090D14] shadow-[0_0_10px_rgba(6,182,212,0.4)]" : "text-white/60 hover:text-white"}`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* map tool rail */}
        <div className="absolute left-3 top-1/2 -translate-y-1/2 hidden lg:flex flex-col gap-1.5 z-10">
          <div className="rounded-xl bg-[#090D14]/85 backdrop-blur border border-slate-800/60 p-1.5 flex flex-col gap-1">
            {[
              { icon: Layers, active: true },
              { icon: Navigation, active: false },
              { icon: PenTool, active: false },
              { icon: Copy, active: false },
              { icon: Ruler, active: false },
              { icon: Box, active: false },
            ].map((t, i) => (
              <button key={i} className={`h-7 w-7 grid place-items-center rounded-lg border text-white/70 hover:text-white transition-colors ${t.active ? "bg-slate-800/60 border-slate-800/60 text-white" : "border-transparent hover:bg-white/5"}`}>
                <t.icon size={13} />
              </button>
            ))}
          </div>
        </div>

        {/* intelligence popup — flood */}
        <div className="absolute left-[30%] top-[18%] z-10 hidden md:block">
          <div className="w-[240px] rounded-xl bg-[#0D121F] border border-slate-800/60 shadow-[0_16px_40px_rgba(0,0,0,0.6)] overflow-hidden">
            <div className="px-3 pt-3 flex items-start gap-2">
              <span className="h-6 w-6 rounded-full bg-[#FF4D5E]/15 border border-[#FF4D5E]/20 grid place-items-center shrink-0">
                <AlertTriangle size={12} className="text-[#FF4D5E]" />
              </span>
              <div>
                <div className="text-xs font-semibold text-white leading-none">Flood Risk Detected</div>
                <div className="text-[11px] text-white/55 mt-1">Low-lying area · 2.3 km²</div>
              </div>
            </div>
            <div className="px-3 py-2.5 flex items-center justify-between">
              <div className="text-[11px] text-white/60">
                Confidence: <span className="text-[#06B6D4] font-semibold">92%</span>
              </div>
              <button className="text-xs font-medium text-[#06B6D4] hover:text-white transition-colors">View Details →</button>
            </div>
          </div>
          <div className="mx-auto h-2 w-2 rotate-45 bg-[#0D121F] border-r border-b border-slate-800/60 -mt-1 ml-6" />
        </div>

        {/* land use change card */}
        <div className="absolute left-3 bottom-[72px] z-10 hidden xl:flex w-[240px] rounded-xl bg-[#0D121F] border border-slate-800/60 shadow-[0_16px_40px_rgba(0,0,0,0.6)] overflow-hidden">
          <div className="h-[86px] w-full bg-gradient-to-br from-slate-800/60 via-[#0D121F] to-[#090D14] grid place-items-center border-b border-slate-800/60">
            <span className="text-[11px] font-mono text-slate-500">Agricultural → Urban · RGB</span>
          </div>
          <div className="p-3">
            <div className="text-xs font-semibold text-white flex items-center gap-1.5">🌿 Land Use Change</div>
            <div className="text-[11px] text-white/60 mt-1">Agricultural → Urban</div>
            <div className="flex items-center justify-between mt-2 text-[11px]">
              <span className="text-white/60">Area: <span className="text-white font-medium">1.8 km²</span></span>
              <span className="text-[#06B6D4] font-medium">87%</span>
            </div>
            <button className="mt-2 text-xs font-medium text-[#06B6D4] hover:text-white">View Details →</button>
          </div>
        </div>

        {/* bottom controls — legend chips toggle overlays */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between z-10 pointer-events-none">
          <div className="hidden md:flex items-center gap-1 rounded-full bg-[#090D14]/85 backdrop-blur border border-slate-800/60 px-2 py-1 text-[11px] text-white/70 pointer-events-auto">
            <button onClick={() => setShowFlood((v) => !v)} className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 transition-colors ${showFlood ? "bg-[#FF4D5E]/15 text-white" : "opacity-50 hover:opacity-80 text-white/70"}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-[#FF4D5E]" /> Flood Risk Zone
            </button>
            <button onClick={() => setShowWater((v) => !v)} className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 transition-colors ${showWater ? "bg-[#06B6D4]/15 text-white" : "opacity-50 hover:opacity-80 text-white/70"}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-[#06B6D4]" /> Water Body
            </button>
            <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 opacity-70">
              <span className="h-1.5 w-1.5 rounded-full bg-[#FF9A4A]" /> Land Use
            </span>
          </div>
          <div className="flex items-center gap-2 pointer-events-auto">
            <div className="hidden sm:flex items-center gap-1 rounded-full bg-[#090D14]/85 backdrop-blur border border-slate-800/60 p-1 text-xs">
              <span className="px-3 py-1 rounded-full bg-white text-[#090D14] font-medium">Satellite</span>
              <span className="px-3 py-1 text-white/60">Map</span>
            </div>
            <div className="flex items-center gap-1 rounded-full bg-[#090D14]/85 backdrop-blur border border-slate-800/60 p-1">
              <button className="h-7 w-7 grid place-items-center rounded-full text-white/70 hover:text-white">
                <Locate size={12} />
              </button>
              <div className="h-4 w-px bg-white/10" />
              <button className="h-7 w-7 grid place-items-center rounded-full text-white/70 hover:text-white">
                <Plus size={12} />
              </button>
              <button className="h-7 w-7 grid place-items-center rounded-full text-white/70 hover:text-white">
                <Minus size={12} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
