import React, { useEffect, useRef, useState, useLayoutEffect } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useMapStore } from "@/store/map.store";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useUiStore } from "@/store/ui.store";
import { useChatStore } from "@/store/chat.store";
import { Skeleton } from "@/components/ui/skeleton";
import { Layers, Satellite, Map as MapIcon, Mountain } from "lucide-react";

const STYLE: Record<string, string> = {
  satellite: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  street: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  terrain: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};

export function MapCanvas({ compact = false }: { compact?: boolean }) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const { center, zoom, selectedFeatureId, setSelectedFeatureId, features, layers, toggleLayer, activeBasemap } = useMapStore();
  const { inspectorOpen, toggleInspector } = useWorkspaceStore();
  const { layerPanelOpen } = useUiStore();
  const [coords, setCoords] = useState<string>("31.48°N 80.37°W");
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const initRef = useRef(false);

  // Robust init: wait for non-zero container size (fixes race with background/sidebar animations)
  useLayoutEffect(() => {
    const el = mapContainer.current;
    if (!el || initRef.current) return;

    const tryInit = () => {
      if (initRef.current) return;
      const rect = el.getBoundingClientRect();
      if (rect.width < 10 || rect.height < 10) return false; // still hidden/collapsed
      initRef.current = true;

      let map: maplibregl.Map | null = null;
      try {
        map = new maplibregl.Map({
          container: el,
          style: STYLE[activeBasemap] ?? STYLE.satellite,
          center,
          zoom,
          attributionControl: false,
          fadeDuration: 0,
        });
      } catch (e: any) {
        setError(String(e?.message ?? "Map init failed"));
        initRef.current = false;
        return true;
      }
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "bottom-right");
      map.on("mousemove", e => setCoords(`${e.lngLat.lat.toFixed(4)}°N ${Math.abs(e.lngLat.lng).toFixed(4)}°W`));
      map.on("error", (e: any) => {
        if (!loaded) setError(e?.error?.message ?? "Style load failed — showing fallback");
      });
      map.on("load", () => {
        setLoaded(true);
        setError(null);
        try {
          map!.addSource("imagery-tint", { type: "geojson", data: { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[-80.55, 31.3], [-80.15, 31.3], [-80.15, 31.7], [-80.55, 31.7], [-80.55, 31.3]]] } }] } } as any);
          map!.addLayer({ id: "imagery-tint-fill", type: "fill", source: "imagery-tint", paint: { "fill-color": "#0EA5E9", "fill-opacity": 0.06 } } as any);
          map!.addSource("change-mask", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: [
                { type: "Feature", id: "sector_a", properties: { label: "Sector A", area: 9.2 }, geometry: { type: "Polygon", coordinates: [[[-80.38, 31.46], [-80.33, 31.46], [-80.33, 31.51], [-80.38, 31.51], [-80.38, 31.46]]] } },
                { type: "Feature", id: "sector_b", properties: { label: "Sector B", area: 6.1 }, geometry: { type: "Polygon", coordinates: [[[-80.44, 31.4], [-80.39, 31.4], [-80.39, 31.45], [-80.44, 31.45], [-80.44, 31.4]]] } },
              ],
            } as any,
          });
          map!.addLayer({ id: "change-mask-fill", type: "fill", source: "change-mask", paint: { "fill-color": "#F59E0B", "fill-opacity": 0.22 }, layout: { visibility: "none" } } as any);
          map!.addLayer({ id: "change-mask-line", type: "line", source: "change-mask", paint: { "line-color": "#F59E0B", "line-width": 1.5, "line-dasharray": [2, 2] }, layout: { visibility: "none" } } as any);
          map!.addSource("detections", { type: "geojson", data: detectionsFC(features) } as any);
          map!.addLayer({ id: "detections-fill", type: "fill", source: "detections", paint: { "fill-color": "#0EA5E9", "fill-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 0.28, 0.10] } } as any);
          map!.addLayer({ id: "detections-line", type: "line", source: "detections", paint: { "line-color": "#0EA5E9", "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1.5] } } as any);
          map!.addLayer({ id: "detections-label", type: "symbol", source: "detections", layout: { "text-field": ["get", "label"], "text-size": 11, "text-offset": [0, 1.2] }, paint: { "text-color": "#E2E8F0", "text-halo-color": "#05080D", "text-halo-width": 1 } } as any);
          map!.on("click", "detections-fill", (e: any) => {
            const f = e.features?.[0] as any;
            if (!f?.id) return;
            const fid = String(f.id);
            setSelectedFeatureId(fid);
            if (!inspectorOpen) toggleInspector();
            // D1: highlight corresponding message — find last assistant message containing this feature label/bbox
            try {
              const label = String(f.properties?.label ?? "");
              const msgs = useChatStore.getState().messages;
              // search from newest to oldest for matching label or bbox
              for (let i = msgs.length - 1; i >= 0; i--) {
                const m = msgs[i];
                if (m.role !== "assistant") continue;
                if (label && m.content.toLowerCase().includes(label.toLowerCase().slice(0, 8))) {
                  const el = document.getElementById(`msg-${m.id}`);
                  if (el) {
                    el.scrollIntoView({ behavior: "smooth", block: "center" });
                    el.classList.add("ring-1","ring-[#06B6D4]/30");
                    setTimeout(() => el.classList.remove("ring-1","ring-[#06B6D4]/30"), 1800);
                  }
                  break;
                }
              }
            } catch {}
          });
          map!.on("mouseenter", "detections-fill", () => (map!.getCanvas().style.cursor = "pointer"));
          map!.on("mouseleave", "detections-fill", () => (map!.getCanvas().style.cursor = ""));
        } catch (err: any) {
          setError(String(err?.message ?? "Layer init failed"));
        }
        // double rAF resize to ensure display after sidebar animations
        requestAnimationFrame(() => {
          map?.resize();
          setTimeout(() => map?.resize(), 120);
          setTimeout(() => map?.resize(), 400);
        });
      });
      return true;
    };

    // if already visible, init immediately, else observe
    if (tryInit()) return;

    const ro = new ResizeObserver(() => {
      if (tryInit()) ro.disconnect();
    });
    ro.observe(el);

    // also check via rAF loop for background image load race
    let raf = 0;
    const poll = () => {
      if (tryInit()) return;
      raf = requestAnimationFrame(poll);
    };
    raf = requestAnimationFrame(poll);

    return () => {
      ro.disconnect();
      cancelAnimationFrame(raf);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // re-resize when panel visibility changes (fixes compact inside sliding drawer)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    // delay to let drawer animation finish (300ms)
    const t1 = setTimeout(() => map.resize(), 60);
    const t2 = setTimeout(() => map.resize(), 320);
    const t3 = setTimeout(() => map.resize(), 650);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [inspectorOpen, compact]);

  // also resize on window + sidebar
  useEffect(() => {
    const onResize = () => mapRef.current?.resize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // sync detections
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const src = map.getSource("detections") as maplibregl.GeoJSONSource | undefined;
    if (src) src.setData(detectionsFC(features) as any);
  }, [features]);

  // selected state
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    features.forEach(f => {
      try { map.setFeatureState({ source: "detections", id: f.id } as any, { selected: f.id === selectedFeatureId }); } catch {}
    });
    if (selectedFeatureId) {
      const feat = features.find(f => f.id === selectedFeatureId);
      if (feat?.lngLat) {
        const c: [number, number] = [(feat.lngLat[0][0] + feat.lngLat[1][0]) / 2, (feat.lngLat[0][1] + feat.lngLat[1][1]) / 2];
        map.flyTo({ center: c, zoom: 11.2, duration: 700 });
      }
    }
  }, [selectedFeatureId, features]);

  // layer visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const vis = (on: boolean) => (on ? "visible" : "none");
    try {
      if (map.getLayer("detections-fill")) {
        map.setLayoutProperty("detections-fill", "visibility", vis(layers.detections));
        map.setLayoutProperty("detections-line", "visibility", vis(layers.detections));
        map.setLayoutProperty("detections-label", "visibility", vis(layers.detections));
      }
      if (map.getLayer("change-mask-fill")) {
        map.setLayoutProperty("change-mask-fill", "visibility", vis(layers.changeMask));
        map.setLayoutProperty("change-mask-line", "visibility", vis(layers.changeMask));
      }
    } catch {}
  }, [layers]);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className={`relative overflow-hidden bg-[var(--color-surface-2)] ${compact ? "h-full w-full" : "flex-1"}`}>
      <div ref={mapContainer} className="absolute inset-0" />
      {!loaded && !error && <Skeleton className="absolute inset-0 rounded-none" />}
      {error && (
        <div className="absolute inset-0 grid place-items-center bg-gradient-to-br from-[#0E1726] to-[#141F32] p-4">
          <div className="rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-1)]/80 backdrop-blur px-4 py-3 text-xs text-[var(--color-text-muted)] max-w-[260px] text-center">
            <div className="text-white font-medium mb-1">Map style unavailable</div>
            <div className="leading-relaxed">{error}</div>
            <div className="mt-2 h-[90px] rounded-lg bg-[var(--color-surface-3)] border border-[var(--color-border-subtle)] grid place-items-center text-[11px]">Fallback raster preview</div>
          </div>
        </div>
      )}
      {!compact && !error && (
        <div className="absolute top-3 left-3 right-3 flex items-center justify-between gap-2 z-10 pointer-events-none">
          <div className="pointer-events-auto flex items-center gap-2">
            <div className="rounded-full bg-[var(--color-surface-1)]/90 backdrop-blur border border-[var(--color-border-subtle)] px-3 py-1.5 text-xs text-[var(--color-text-secondary)] flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" /> SATIQ Geospatial Engine</div>
            <div className="hidden md:flex items-center gap-1 rounded-full bg-[var(--color-surface-1)]/90 backdrop-blur border border-[var(--color-border-subtle)] p-1">
              <button onClick={() => toggleLayer("detections")} className={`px-2.5 py-1 rounded-full text-xs ${layers.detections ? "bg-[var(--color-surface-3)] text-white" : "text-[var(--color-text-muted)]"}`}>Detections</button>
              <button onClick={() => toggleLayer("changeMask")} className={`px-2.5 py-1 rounded-full text-xs ${layers.changeMask ? "bg-amber-500 text-black" : "text-[var(--color-text-muted)]"}`}>Change</button>
              <button onClick={() => toggleLayer("sar")} className={`px-2.5 py-1 rounded-full text-xs ${layers.sar ? "bg-slate-600 text-white" : "text-[var(--color-text-muted)]"}`}>SAR</button>
            </div>
          </div>
          <div className="pointer-events-auto hidden sm:flex items-center gap-1 rounded-lg bg-[var(--color-surface-1)] border border-[var(--color-border-subtle)] p-1">
            <BasemapBtn active={activeBasemap === "satellite"} icon={<Satellite size={12} />} label="Satellite" />
            <BasemapBtn active={activeBasemap === "street"} icon={<MapIcon size={12} />} label="Street" />
            <BasemapBtn active={activeBasemap === "terrain"} icon={<Mountain size={12} />} label="Terrain" />
          </div>
        </div>
      )}
      <div className={`absolute z-10 rounded-md bg-[var(--color-surface-1)]/90 backdrop-blur border border-[var(--color-border-subtle)] px-2.5 py-1 text-[11px] font-mono text-[var(--color-text-muted)] ${compact ? "bottom-2 left-2 text-[10px] px-2 py-1" : "bottom-3 left-3"}`}>{coords} · EPSG:32617 · 10 m</div>
      {layerPanelOpen && (
        <div className="absolute top-14 right-3 z-20 w-[280px] rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-1)] shadow-2xl p-3 space-y-2">
          <div className="text-xs font-semibold tracking-widest text-[var(--color-text-muted)] flex items-center gap-2"><Layers size={12} /> LAYERS</div>
          {[
            ["Imagery", "imagery"],
            ["Detections", "detections"],
            ["Segmentation", "segmentation"],
            ["Change mask", "changeMask"],
            ["SAR", "sar"],
          ].map(([label, key]) => (
            <label key={key} className="flex items-center justify-between rounded-lg border border-[var(--color-border-subtle)] bg-[var(--color-surface-2)] px-3 py-2 text-sm">
              <span className="text-[var(--color-text-secondary)]">{label}</span>
              <button onClick={() => toggleLayer(key as any)} className={`h-5 w-9 rounded-full p-0.5 transition-colors ${(layers as any)[key] ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface-3)]"}`}><span className={`block h-4 w-4 rounded-full bg-white transition-transform ${(layers as any)[key] ? "translate-x-4" : "translate-x-0"}`} /></button>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function BasemapBtn({ active, icon, label }: { active: boolean; icon: React.ReactNode; label: string }) {
  return <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs ${active ? "bg-[var(--color-surface-3)] text-white border border-[var(--color-border-default)]" : "text-[var(--color-text-muted)]"}`}>{icon} {label}</span>;
}

function detectionsFC(features: any[]) {
  return {
    type: "FeatureCollection",
    features: features.map(f => ({
      type: "Feature",
      id: f.id,
      properties: { label: f.label, confidence: f.confidence },
      geometry: { type: "Polygon", coordinates: [[[f.lngLat?.[0][0] ?? -80.4, f.lngLat?.[0][1] ?? 31.45], [f.lngLat?.[1][0] ?? -80.35, f.lngLat?.[0][1] ?? 31.45], [f.lngLat?.[1][0] ?? -80.35, f.lngLat?.[1][1] ?? 31.5], [f.lngLat?.[0][0] ?? -80.4, f.lngLat?.[1][1] ?? 31.5], [f.lngLat?.[0][0] ?? -80.4, f.lngLat?.[0][1] ?? 31.45]]] },
    })),
  } as any;
}
