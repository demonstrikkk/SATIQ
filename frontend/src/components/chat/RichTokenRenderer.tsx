import { MapPin } from 'lucide-react';

/**
 * Satiq-adapted generative UI chips for geospatial tokens.
 * Parses [[bbox:x1,y1,x2,y2|Label]] and [[coords|Label]] into interactive pills
 * that trigger map focus. Falls back to existing [View ...](#bbox) handling.
 */
export function RichTokenRenderer({ text, onBboxClick }: { text: string; onBboxClick: (coords: string) => void }) {
  // Supports both [[bbox:120,45,310,210|Northern Water Body]] and legacy [[bbox:coords|label]]
  const parts = text.split(/(\[\[bbox:[^\]]+\]\]|\[\[coords:[^\]]+\]\])/g);

  if (parts.length === 1) {
    return <span>{text}</span>;
  }

  return (
    <span className="leading-relaxed">
      {parts.map((part, idx) => {
        if (part.startsWith('[[bbox:') || part.startsWith('[[coords:')) {
          const match = part.match(/\[\[(?:bbox|coords):(.*?)\|(.*?)\]\]/);
          if (!match) return null;
          const [, coords, label] = match;
          return (
            <button
              key={idx}
              onClick={() => onBboxClick(coords)}
              className="inline-flex items-center gap-1.5 mx-1 px-2.5 py-1 rounded-full bg-[#0D121F] border border-[#06B6D4]/30 text-cyan-300 hover:bg-slate-800/60 hover:border-[#06B6D4]/50 text-xs font-mono transition-colors group align-middle max-w-[180px]"
              title={`BBox ${coords}`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#06B6D4] animate-pulse group-hover:animate-none shrink-0" />
              <MapPin size={10} className="text-[#06B6D4] shrink-0" />
              <span className="truncate max-w-[180px] inline-block align-middle">{label}</span>
              <span className="text-[10px] text-slate-500 hidden sm:inline">[{coords.split(',').slice(0,2).join(',')}…]</span>
            </button>
          );
        }
        return <span key={idx}>{part}</span>;
      })}
    </span>
  );
}
