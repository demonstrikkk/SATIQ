"""Premium Architecture & Workflow — properly spaced, layered, no overlap."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap

W, H = 3200, 3600
BG = (8, 12, 24)
CARD_BG = (17, 24, 39)
CARD_BORDER = (51, 65, 85)
MUTED = (148, 163, 184)
ACCENT = {
    "violet": (124, 58, 237),
    "cyan": (6, 182, 212),
    "amber": (245, 158, 11),
    "emerald": (16, 185, 129),
    "pink": (236, 72, 153),
    "slate": (71, 85, 105),
}

def load_font(name, size, bold=False):
    candidates = [
        f"C:\\Windows\\Fonts\\{name}",
        f"/Windows/Fonts/{name}",
        name,
    ]
    # Try Segoe UI as premium alternative
    if "arial" in name.lower():
        for alt in ["SegoeUI.ttf", "segoeui.ttf", "Inter-Regular.ttf"]:
            for base in [f"C:\\Windows\\Fonts\\{alt}", alt]:
                try:
                    if Path(base).exists():
                        return ImageFont.truetype(base, size)
                except: pass
    for c in candidates:
        try:
            if Path(c).exists():
                return ImageFont.truetype(c, size)
        except: pass
    try:
        return ImageFont.truetype(name, size)
    except:
        return ImageFont.load_default()

f_title = load_font("arial.ttf", 52)
f_sub = load_font("arial.ttf", 19)
f_card_title = load_font("arialbd.ttf", 18)
if f_card_title == ImageFont.load_default():
    f_card_title = load_font("arial.ttf", 18)
f_card_body = load_font("consola.ttf", 13)
if f_card_body == ImageFont.load_default():
    f_card_body = load_font("consol.ttf", 13)
f_label = load_font("arial.ttf", 12)
f_small = load_font("arial.ttf", 11)

def hex_to_rgb(h): return tuple(int(h.lstrip("#")[i:i+2],16) for i in (0,2,4))

def draw_card(draw, x, y, w, h, title, subtitle, body_lines, accent, icon=None):
    # shadow
    draw.rounded_rectangle([x+6, y+6, x+w+6, y+h+6], radius=20, fill=(0,0,0,35))
    # card
    draw.rounded_rectangle([x, y, x+w, y+h], radius=20, fill=CARD_BG, outline=CARD_BORDER, width=1)
    # accent top bar
    draw.rounded_rectangle([x, y, x+w, y+6], radius=6, fill=accent)
    # icon circle
    if icon:
        cx, cy = x+28, y+28
        draw.ellipse([cx-16, cy-10, cx+16, cy+22], fill=accent, outline="white", width=1)
        draw.text((cx, cy+6), icon, fill="white", font=f_card_title, anchor="mm")
        tx = x+52
    else:
        tx = x+18
    draw.text((tx, y+22), title, fill="white", font=f_card_title, anchor="lm")
    if subtitle:
        draw.text((tx, y+38), subtitle, fill=MUTED, font=f_small, anchor="lm")
    yy = y+58
    for line in body_lines:
        if not line.strip():
            yy+=6
            continue
        # bullet or plain
        is_bullet = line.startswith("•") or line.startswith("↳") or line.startswith("-")
        wrapped = textwrap.wrap(line, width=62 if w>700 else 48)
        for i, wl in enumerate(wrapped):
            # first line keeps bullet, subsequent indent
            prefix = "" if i>0 else ""
            draw.text((x+18, yy), prefix+wl, fill=(226,232,240) if not is_bullet else (203,213,225), font=f_card_body, anchor="lm")
            yy+=17
        yy+=3
    return yy

def draw_arrow_h(draw, x1, y, x2, label=None, color=(255,255,255)):
    draw.line([x1, y, x2, y], fill=color, width=2)
    draw.polygon([x2-8, y-5, x2-8, y+5, x2+4, y], fill=color)
    if label:
        mx = (x1+x2)//2
        # pill background
        tw = len(label)*6 + 12
        draw.rounded_rectangle([mx-tw//2, y-14, mx+tw//2, y-6], radius=6, fill=(30,41,59), outline=color, width=1)
        draw.text((mx, y-10), label, fill=color, font=f_label, anchor="mm")

def draw_arrow_v(draw, x, y1, y2, label=None, color=(255,255,255)):
    draw.line([x, y1, x, y2], fill=color, width=2)
    draw.polygon([x-5, y2-8, x+5, y2-8, x, y2+4], fill=color)
    if label:
        draw.text((x+14, (y1+y2)//2), label, fill=color, font=f_label, anchor="lm")

# Create image
img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# Header — premium with subtle gradient line
draw.rounded_rectangle([24, 24, W-24, 118], radius=16, fill=(15,23,42), outline=CARD_BORDER, width=1)
draw.text((W//2, 58), "SATIQ  —  SATQUERY AI", fill="white", font=f_title, anchor="mm")
draw.text((W//2, 88), "Geospatial QA  •  8-Node LangGraph  •  Ollama qwen3.5:9b  •  10 Tools  •  4 Shims  •  No mocks  •  Single-GPU", fill=MUTED, font=f_sub, anchor="mm")
# Accent line
draw.line([W//2-320, 108, W//2+320, 108], fill=ACCENT["violet"], width=2)

# --- LAYER 1: ENTRY (3 cards) ---
y0 = 140
# Card dimensions
cw, ch = 980, 148
gap = 40
x1, x2, x3 = 32, 32+cw+gap, 32+2*(cw+gap)
# User + Frontend
draw_card(draw, x1, y0, cw, ch, "USER  +  FRONTEND  :5173", "React + Vite + MapLibre  •  Composer",
          ["• Composer.tsx:114  100 MB createObjectURL, FormData(image)+query+chips, drag-drop, mic STT",
           "• StreamMarkdown.tsx  ?bbox= parse (heuristic disabled → null), ApexCharts ChartBlock",
           "• analysisClient.ts:57  POST /api/query  SSE  abort-safe  •  MapLibre bbox overlay"], ACCENT["violet"], "1")
# Gateway
draw_card(draw, x2, y0, cw, ch, "GATEWAY  :4000  Express", "TypeScript  •  Auth + Rate Limit",
          ["• routes/upload.ts:37  createReadStream duplex:half 60s, randomUUID+.jp2, forward w/h/crs/gsd",
           "• agentic-analysis.provider:40  dedup event:ts:payload  maxAttempts 32  keepAlive 70s",
           "• routes/query.ts:23 inject Authorization  •  rateLimiter userId||ip"], ACCENT["cyan"], "2")
# Orchestrator Entry
draw_card(draw, x3, y0, cw, ch, "ORCHESTRATOR ENTRY  :8000", "FastAPI  •  POST /api/v1/task  •  ingestion",
          ["• api/main.py:743 _normalize_assets  CRS 400  •  100Mpix 413  •  queue_gate 429",
           "• EXECUTIONS[{id}] + Redis setex 3600  +  Last-Event-ID replay",
           "• BackgroundTasks run_pipeline  •  POST /api/v1/ingest  ingest_file → storage/ingest"], ACCENT["amber"], "3")
# Arrows
draw_arrow_h(draw, x1+cw, y0+ch//2, x2, "FormData")
draw_arrow_h(draw, x2+cw, y0+ch//2, x3, "SSE")
# Down arrow to pipeline
mid_x = W//2
draw_arrow_v(draw, mid_x, y0+ch+12, y0+ch+38, "pipeline.ainvoke(state)  main.py:155")

# --- LAYER 2: PIPELINE (vertical spine left, details right) ---
y_pipeline = y0+ch+58
# Spine line
spine_x = 420
# Define 8 nodes with their sidecars - properly structured
pipeline = [
    {
        "num": "01", "title": "input_validator", "subtitle": "agents/input_validator.py:23  •  Deterministic gate",
        "body": ["• request_key sorted-hash  •  deadline 45s (core/timeouts)", "• len 16–4000  •  guardrails check_prompt_injection", "• CRS _crs_mismatch hard gate  •  GSD>0  •  pixel w*h>100Mpix", "• _corrupt / malformed_geotiff  →  validation_passed"],
        "color": ACCENT["amber"], "side_title": "Resilience", "side_body": ["checkpoint  compute_request_key", "timeouts  TOTAL 45s  per-node tight", "validate_geotiff → ingest", "structured_logging + metrics"], "branch": "fail → error_handler"
    },
    {
        "num": "02", "title": "coreference_resolver", "subtitle": "agents/coreference_resolver  •  <1 ms",
        "body": ["• entity_registry.extract_entities  •  alias → [RESOLVED:bbox]", "• conversation augment_state_with_history", "• followup anchor  •  is_followup → history"],
        "color": ACCENT["amber"], "side_title": "Memory: Entity + History", "side_body": ["entity_registry  alias → bbox", "conversation history  is_followup", "turn_history  SQLite"], 
    },
    {
        "num": "03", "title": "router", "subtitle": "agents/router_agent.py:11  •  Ollama qwen3.5:9b",
        "body": ["• query_analyzer  temporal / spatial / comparison", "• to_thread  call_qwen_router  •  ollama.chat", "• tools = ROUTER_TOOLS 4  tool_choice auto → task_type", "• capability_registry validate_legality"],
        "color": ACCENT["amber"], "side_title": "ROUTER_TOOLS 4 → Ollama", "side_body": ["helpers/tool_schemas.py:13", "run_vqa  •  run_grounding", "run_change_vqa  •  run_fusion", "tool_call → task_type"], 
    },
    {
        "num": "04", "title": "planner", "subtitle": "agents/planner_agent.py:9  •  Ollama qwen3.5:9b",
        "body": ["• registry_prompt_fragment  •  load_history_hybrid n=3", "• rag_store.retrieve top_k 3  Chroma 8001 + SQLite", "• entity_registry  •  to_thread call_qwen_planner", "• REGISTERED_TOOLS 10  •  guardrails PlanSchema step cap 10"],
        "color": ACCENT["violet"], "side_title": "PLANNER  RAG + Guardrails", "side_body": ["REGISTERED_TOOLS 10  MODEL 4 + DETERMINISTIC 6", "geocode_region  •  query_analyzer", "PlanSchema  capability_illegal → error", "requires_coreg / sub_queries / region_of_interest"], 
    },
    {
        "num": "05", "title": "task_agent", "subtitle": "agents/task_agents.py:34  •  GPU-bound",
        "body": ["• VRAM_SEMAPHORE(2)  +  asyncio.to_thread", "• image_pipeline.resolve_asset  rglob ingest  NO resampling", "• model_adapter MODEL_MAP  shim pref  probe inference/ask_geochat", "• result_merger  sub_queries  •  _cleanup_vram"],
        "color": (239,68,68), "side_title": "SHIMS → MODELS  (internal encoders)", "side_body": ["model1  GeoChat-7B 4-bit  ask_geochat", "model2  GroundingDINO 2-98%  vendor config/train", "model3  Prithvi+Vicuna  hybrid  •  model4  CROMA 12+2", "FFmpeg CPU crop  •  visualisation_tool  •  tiling 512+64"], 
    },
    {
        "num": "06", "title": "post_processing", "subtitle": "agents/post_processing.py  •  Evidence gate",
        "body": ["• conf ≥0.6 gate  (None bypass)  •  bbox clamp [0,1]", "• evidence grounding  •  chart real only", "• validate_chart_spec → ```chart  (no dummy Sector A)", "• _needs_retry → task_agent"],
        "color": ACCENT["emerald"], "side_title": "Evidence + Chart", "side_body": ["helpers/chart_spec  →  ```chart", "spectral NDVI/NDWI  •  geocoder", "bbox clamp  •  confidence engine"], 
    },
    {
        "num": "07", "title": "response_composer", "subtitle": "agents/response_composer.py  •  Ollama stream",
        "body": ["• call_qwen_composer_stream  2048 tok  to_thread", "• emit thinking_delta / answer_delta  •  chart + bbox table", "• /api/assets 768px (not base64)  •  save_history → Chroma/SQLite", "• audit.db + MinIO rs-outputs"],
        "color": ACCENT["cyan"], "side_title": "Persist + Stream", "side_body": ["Chroma satiq_conversation  •  memory.db SQLite", "audit.db  execution_traces  •  MinIO rs-outputs", "SSE answer_delta  •  Redis persist", "metrics + structured_logging"], 
    },
    {
        "num": "08", "title": "error_handler", "subtitle": "permanent vs transient",
        "body": ["• permanent  MODEL_NOT_LINKED  (add inference.py)  →  END", "• transient  MODEL_INFERENCE_ERROR  retry 1  →  task_agent", "• low_confidence  retry ×3  →  task_agent  →  END", "• node_timeout / circuit_open"],
        "color": ACCENT["slate"], "side_title": None, "side_body": [], 
    },
]

left_x, left_w = 48, 760
right_x, right_w = 880, W-880-48
cur_y = y_pipeline
for idx, node in enumerate(pipeline):
    is_last = idx == len(pipeline)-1
    # Left card
    lh = 168 if idx not in [3,4] else 188
    if idx == 4: lh = 176
    # Draw left pipeline card with number circle
    draw.rounded_rectangle([left_x+6, cur_y+6, left_x+left_w+6, cur_y+lh+6], radius=18, fill=(0,0,0,28))
    draw.rounded_rectangle([left_x, cur_y, left_x+left_w, cur_y+lh], radius=18, fill=CARD_BG, outline=CARD_BORDER, width=1)
    draw.rounded_rectangle([left_x, cur_y, left_x+left_w, cur_y+32], radius=12, fill=node["color"])
    # Fix top rounding
    draw.rectangle([left_x+12, cur_y+16, left_x+left_w-12, cur_y+32], fill=node["color"])
    # Number circle
    cx, cy = left_x+28, cur_y+16
    draw.ellipse([cx-16, cy-12, cx+16, cy+20], fill="white", outline=CARD_BG, width=2)
    draw.text((cx, cy+4), node["num"], fill=node["color"], font=load_font("arialbd.ttf", 13), anchor="mm")
    draw.text((left_x+52, cur_y+16), node["title"], fill="white", font=f_card_title, anchor="lm")
    draw.text((left_x+52, cur_y+28), node["subtitle"], fill=(226,232,240), font=f_small, anchor="lm")
    yy = cur_y+48
    for ln in node["body"]:
        wrapped = textwrap.wrap(ln, width=56)
        for wl in wrapped:
            draw.text((left_x+18, yy), wl, fill=(203,213,225), font=f_card_body, anchor="lm")
            yy+=15
        yy+=2

    # Right sidecar - aligned to same Y, short orthogonal stub
    if node["side_title"]:
        rh = lh
        draw.rounded_rectangle([right_x+4, cur_y+4, right_x+right_w+4, cur_y+rh+4], radius=18, fill=(0,0,0,22))
        # side card with subtle left accent
        draw.rounded_rectangle([right_x, cur_y, right_x+right_w, cur_y+rh], radius=18, fill=(30,41,59), outline=CARD_BORDER, width=1)
        draw.rectangle([right_x, cur_y, right_x+6, cur_y+rh], fill=node["color"])
        draw.text((right_x+18, cur_y+16), node["side_title"], fill="white", font=f_card_title, anchor="lm")
        syy = cur_y+36
        for ln in node["side_body"]:
            wrapped = textwrap.wrap(ln, width=96)
            for wl in wrapped:
                draw.text((right_x+18, syy), wl, fill=MUTED, font=f_card_body, anchor="lm")
                syy+=15
            syy+=2
        # short orthogonal connector — no diagonal
        sx1, sx2 = left_x+left_w, right_x
        sy = cur_y + lh//2
        # horizontal line with small gap
        draw.line([sx1, sy, sx1+18, sy], fill=MUTED, width=2)
        draw.line([sx2-18, sy, sx2, sy], fill=MUTED, width=2)
        draw.line([sx1+18, sy, sx2-18, sy], fill=MUTED, width=1)
        # dots
        draw.ellipse([sx1+16, sy-3, sx1+22, sy+3], fill=MUTED)
        draw.ellipse([sx2-22, sy-3, sx2-16, sy+3], fill=MUTED)
        draw.text(((sx1+sx2)//2, sy-10), "uses", fill=MUTED, font=f_small, anchor="mm")

    # Vertical spine between left nodes
    if not is_last:
        # spine
        x_spine = left_x + left_w//2
        y1, y2 = cur_y+lh, cur_y+lh+32
        draw.line([x_spine, y1, x_spine, y2], fill="white", width=2)
        draw.polygon([x_spine-6, y2-7, x_spine+6, y2-7, x_spine, y2+5], fill="white")
        # branch labels
        if idx == 0:
            draw.text((x_spine+18, y1+10), "pass  pending_llm", fill=ACCENT["emerald"], font=f_label, anchor="lm")
            # fail branch to error (drawn as small right stub)
            fx, fy = left_x+left_w, cur_y+lh-28
            draw.line([fx, fy, fx+32, fy], fill=(239,68,68), width=2)
            draw.text((fx+36, fy), "fail → error_handler", fill=(239,68,68), font=f_label, anchor="lm")
        elif idx == 3:
            draw.text((x_spine+18, y1+8), "geospatial → task_agent", fill="white", font=f_label, anchor="lm")
            draw.text((x_spine+18, y1+20), "skip_models → response_composer", fill=MUTED, font=f_label, anchor="lm")
        elif idx == 5:
            draw.text((x_spine+18, y1+8), "ok → response_composer", fill="white", font=f_label, anchor="lm")
            draw.text((x_spine+18, y1+20), "_needs_retry ×3 ↺ task_agent", fill=ACCENT["amber"], font=f_label, anchor="lm")
        cur_y += lh + 32
    else:
        cur_y += lh

# Bottom response bar — spans full width
by = cur_y + 28
draw.rounded_rectangle([48+4, by+4, W-48+4, by+118+4], radius=18, fill=(0,0,0,30))
draw.rounded_rectangle([48, by, W-48, by+118], radius=18, fill=(15,23,42), outline=ACCENT["cyan"], width=2)
draw.text((W//2, by+22), "RESPONSE  —  SSE  →  Gateway agentic dedup 32  →  Frontend StreamMarkdown (?bbox= parse, ApexCharts)  +  MapLibre bbox overlay  +  ExecutionTrace", fill="white", font=f_card_title, anchor="mm")
draw.text((W//2, by+48), "response_composer  ollama stream 2048  →  broadcast answer_delta + chart + bbox table + /api/assets/{name} 768px (not base64)  →  gateway upload  →  frontend", fill=MUTED, font=f_card_body, anchor="mm")
draw.text((W//2, by+70), "persist:  MinIO rs-outputs  •  audit.db execution_traces  •  Redis satiq:exec:{id}  •  Chroma / SQLite  •  metrics + structured_logging  •  tiling 512+64 Window", fill=(100,116,139), font=f_small, anchor="mm")
draw.text((W//2, by+94), "Single-GPU  •  asyncio.to_thread + VRAM_SEMAPHORE(2)  •  100 Mpix guard  •  Ollama qwen3.5:9b only  •  No dummy  •  vendor shims: model2 config/train, model4 engine/data", fill=CARD_BORDER, font=f_small, anchor="mm")
# vertical from last spine to bottom
draw.line([left_x+left_w//2, cur_y, left_x+left_w//2, by], fill="white", width=2)
draw.polygon([left_x+left_w//2-6, by-8, left_x+left_w//2+6, by-8, left_x+left_w//2, by+4], fill="white")

# Footer outer border
draw.rounded_rectangle([16, 16, W-16, by+118+36], radius=24, outline=CARD_BORDER, width=1)
draw.text((24, by+118+22), "File:line refs are current  •  Lateral stubs are short orthogonal (no diagonal overlap)  •  Colors: violet=Frontend  cyan=Gateway  amber=Orchestrator  yellow=LLM  emerald=OK  pink=Memory  teal=Storage", fill=(71,85,105), font=f_small, anchor="lm")

# Crop to content
final_h = by + 118 + 56
img_cropped = img.crop((0,0,W, final_h))
out = Path("orchestrator/graph/premium_workflow.png")
out.parent.mkdir(parents=True, exist_ok=True)
img_cropped.save(out, "PNG")
print(str(out))
# also save a copy to docs
Path("docs/premium_workflow.png").parent.mkdir(parents=True, exist_ok=True)
img_cropped.save("docs/premium_workflow.png", "PNG")
print("docs/premium_workflow.png")

# Generate premium Mermaid with styling
mermaid_premium = r"""%%{init: {'theme':'dark', 'themeVariables':{'primaryColor':'#8B5CF6','primaryTextColor':'#fff','lineColor':'#64748B','tertiaryColor':'#1E293B'}}}%%
flowchart TB
    classDef frontend fill:#7C3AED,stroke:#fff,color:#fff,stroke-width:2px
    classDef gateway fill:#06B6D4,stroke:#fff,color:#000,stroke-width:2px
    classDef orch fill:#F59E0B,stroke:#fff,color:#000,stroke-width:2px
    classDef llm fill:#EAB308,stroke:#000,color:#000,stroke-width:2px
    classDef ok fill:#10B981,stroke:#fff,color:#000
    classDef err fill:#475569,stroke:#fff,color:#fff
    %% (full workflow mermaid is in workflow_detailed.mmd — this premium PNG is the visual)
"""
Path("orchestrator/graph/premium_workflow.mmd").write_text(mermaid_premium, encoding="utf-8")
print("premium mermaid stub")

