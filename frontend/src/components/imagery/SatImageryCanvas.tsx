import * as React from "react";
import { drawOptical, drawSAR, drawChangeMap, drawMapView } from "@/lib/satqueryCanvas";

type Mode = "optical" | "sar" | "change" | "map";

export function SatCanvas({
  mode,
  seed,
  growth,
  className,
  height,
}: {
  mode: Mode;
  seed?: number;
  growth?: number;
  className?: string;
  height?: number;
}) {
  const ref = React.useRef<HTMLCanvasElement>(null);
  const draw = React.useCallback(() => {
    const c = ref.current;
    if (!c) return;
    if (mode === "optical") drawOptical(c, seed ?? 11, growth ?? 0.5);
    else if (mode === "sar") drawSAR(c, seed ?? 22);
    else if (mode === "change") drawChangeMap(c, seed ?? 33);
    else drawMapView(c);
  }, [mode, seed, growth]);

  React.useEffect(() => {
    draw();
    const onResize = () => draw();
    window.addEventListener("resize", onResize);
    const ro = new ResizeObserver(draw);
    if (ref.current) ro.observe(ref.current);
    return () => {
      window.removeEventListener("resize", onResize);
      ro.disconnect();
    };
  }, [draw]);

  return <canvas ref={ref} className={className} style={height ? { height } : undefined} />;
}

export function SatOptical({ growth, seed, className }: { growth?: number; seed?: number; className?: string }) {
  return <SatCanvas mode="optical" seed={seed} growth={growth} className={className} />;
}
export function SatSAR({ seed, className }: { seed?: number; className?: string }) {
  return <SatCanvas mode="sar" seed={seed} className={className} />;
}
export function SatChange({ seed, className }: { seed?: number; className?: string }) {
  return <SatCanvas mode="change" seed={seed} className={className} />;
}
export function SatMap({ className }: { className?: string }) {
  return <SatCanvas mode="map" className={className} />;
}
