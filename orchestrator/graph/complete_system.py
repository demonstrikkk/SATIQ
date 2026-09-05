"""Generate COMPLETE system graph — pipeline + tools + capabilities + memory + storage + cache."""
from __future__ import annotations
import os
from pathlib import Path

# ------------------------------------------------------------------
#  Mermaid — full system (use with mermaid.live, GitHub, docs)
# ------------------------------------------------------------------
MERMAID_COMPLETE = r"""```mermaid
flowchart TB
    %% ───────── CLIENT ─────────
    subgraph Frontend["🖥️ Frontend 5173 — React + Vite + MapLibre"]
        C1[Composer<br/>100MB + createObjectURL<br/>drag-drop + mic STT]
        C2[Chat + StreamMarkdown<br/>bbox ?bbox= parse • chart ApexCharts<br/>heuristic disabled → null]
        C3[MapLibre GeoCanvas<br/>bbox overlay]
        C4[ExecutionTrace<br/>thinking_delta + answer_delta]
        C5[analysisClient.ts<br/>abort-safe SSE • Finally only if !failed]
        C1 --> C2 --> C3
        C2 --> C4
        C1 -. FormData image .-> C5
    end

    %% ───────── GATEWAY ─────────
    subgraph Gateway["🚪 Gateway 4000 — Express + TS"]
        G1[index.ts<br/>keepAlive 70s / headers 71s]
        G2[routes/upload.ts<br/>createReadStream duplex:half 60s<br/>forward Authorization + w/h/crs/gsd]
        G3[routes/query.ts<br/>inject Authorization]
        G4[analysis/providers/agentic<br/>dedup event:ts:payload • maxAttempts 32<br/>getReader vs AsyncIterable + _authHeader]
        G5[middleware/upload<br/>randomUUID + .jp2]
        G6[middleware/rateLimiter<br/>key=userId||ip]
        G1 --> G2 --> G3 --> G4
    end

    %% ───────── ORCHESTRATOR PIPE ─────────
    subgraph Orchestrator["⚙️ Orchestrator 8000 — FastAPI + LangGraph 8-node (Ollama qwen3.5:9b ONLY)"]
        direction TB
        IV[input_validator<br/> CRS hard gate • GSD>0 • 100Mpix cap<br/>16-4000 chars • jailbreak • request_key/deadline 45s]
        CR[coreference_resolver<br/>alias→[RESOLVED:bbox] • entity_registry <1ms]
        R[router<br/>Ollama qwen3.5:9b • ROUTER_TOOLS 4<br/>tool_choice auto → via to_thread]
        P[planner<br/>Ollama qwen3.5:9b + REGISTERED_TOOLS 10<br/>PlanSchema • guardrails • step cap 10<br/>RAG hybrid + registry_prompt_fragment]
        TA[task_agent<br/>VRAM_SEMAPHORE 2 + queue 4→503 queue_position<br/>asyncio.to_thread • call_model→shim + reproject warp]
        PP[post_processing<br/>conf≥0.6 • bbox clamp [0,1]<br/>evidence grounding • chart real only<br/>retry <2]
        RC[response_composer<br/>Ollama qwen3.5:9b stream 2048 tok<br/>thinking_delta • ApexCharts]
        EH[error_handler<br/>MODEL_NOT_LINKED permanent<br/>queue_full 503 • MODEL_INFERENCE_ERROR transient]
        IV -->|fail| EH
        IV -->|pass| CR --> R --> P
        P -->|skip_models=greeting/chitchat/help/out_of_scope| RC
        P -->|geospatial| TA
        TA -->|MODEL_NOT_LINKED| EH
        TA -->|ok| PP
        PP -->|retry conf<0.6 x2| TA
        PP -->|fail| EH
        PP -->|ok| RC
        EH --> ENDPIPE([END])
        RC --> ENDPIPE
    end

    %% ───────── TOOLS ─────────
    subgraph Tools["🧰 Tool Schemas (helpers/tool_schemas.py)"]
        direction LR
        T1[run_vqa<br/>model1 GeoChat-7B]
        T2[run_grounding<br/>model2 GroundingDINO]
        T3[run_change_vqa<br/>model3 Prithvi+Vicuna]
        T4[run_fusion<br/>model4 CROMA]
        T5[compute_spectral_indices<br/>NDVI/NDWI/NDBI/EVI fail-closed]
        T6[calculate_area<br/>bbox+gsd→ha/km2]
        T7[geocode_region<br/>gazetteer → WGS84 bbox]
        T8[crop_bbox<br/>FFmpeg CPU -vf crop]
        T9[generate_visual_evidence<br/>visualisation_tool]
        T10[retrieve_history<br/>RAG top_k 3]
    end

    %% ───────── CAPABILITIES ─────────
    subgraph Capabilities["📚 Capability Registry (capability_registry.py)"]
        CAP1[vqa / captioning<br/>needs 1 opt]
        CAP2[grounding<br/>needs 1 opt]
        CAP3[change_vqa<br/>needs 2 opt]
        CAP4[optical_sar_fusion<br/>needs opt+sar]
        CAPD[DETERMINISTIC<br/>area/spectral]
    end

    %% ───────── SHIMS / MODELS ─────────
    subgraph Shims["🤖 Shims — internal encoders (no external encoders)"]
        S1[model1_shim<br/>load_model 4bit → ask_geochat]
        S2[model2_shim<br/>load_and_convert_s2 2-98% → build_groundingdino → bbox xyxy]
        S3[model3_shim<br/>compute_indices + classify_deltas + fusion_change_confidence]
        S4[model4_shim<br/>Model4Engine → 12+2 bands → per_modality]
        M1[(models/model1<br/>run_inference.py)]
        M2[(models/model2<br/>visualize_pipeline_graph.py + vendor config/train)]
        M3[(models/model3<br/>visualize_index_hybrid.py)]
        M4[(models/model4<br/>infer.py + vendor engine/data)]
        S1 --- M1
        S2 --- M2
        S3 --- M3
        S4 --- M4
    end

    %% ───────── MEMORY ─────────
    subgraph Memory["🧠 Memory — 4-Tier (GAP-6)"]
        MEM1[conversation.py<br/>load_history_hybrid 4-tier<br/>save_history + consolidate]
        MEM2[rag_store.py<br/>Chroma dual: satiq_conversation 90d<br/>satiq_semantic 180d + where=session_id<br/>hybrid 0.7/0.3 + decay + ttl_cleanup]
        MEM3[memory_orchestrator.py<br/>working 3 (<1k) + episodic hybrid<br/>+ semantic consolidate/4]
        MEM3b[entity_registry.py<br/>alias→bbox + pronouns + ts]
        CHROMA[(Chroma 8001<br/>dual collections)]
        SQLITE[(SQLite<br/>memory.db 50/session)]
        MEM3 --> MEM2 --> CHROMA
        MEM1 <--> MEM2
        MEM1 <--> SQLITE
        MEM3b --> MEM1
    end

    %% ───────── CACHE ─────────
    subgraph Cache["⚡ Cache + Resilience"]
        Q1[query_cache.py<br/>TTLCache 3600/1024]
        Q2[metrics p50/p95/p99<br/>+ vram peak/queue]
        REDIS[(Redis<br/>satiq-exec-id setex 3600<br/>Last-Event-ID + queue_position)]
        CKPT[checkpoint<br/>sorted-hash request_key]
        TO[timeouts<br/>TOTAL 45s wait_for • 8 nodes tight]
        CB[circuit_breaker<br/>qwen_circuit]
        QG[queue_gate 429<br/>+ VRAM queue 4→503]
        DLQ[dlq]
        Q1 -.-> REDIS
        CKPT -.-> REDIS
        TO -.-> IV
        CB -.-> R & P & RC
        Q2 -.-> REDIS
    end

    %% ───────── STORAGE ─────────
    subgraph Storage["💾 Storage — MinIO + Disk fallback"]
        MINIO[(MinIO 9000<br/>rs-outputs bucket)]
        DISK[(Disk fallback<br/>orchestrator/storage/ingest<br/>orchestrator/storage/audit.db<br/>outputs/)]
        GEO[(GeoTIFF ingest<br/>/api/v1/ingest → ingest_file<br/>EXIF GPS + validate_geotiff<br/>thumbnail)]
        GEN[(geojson_export<br/>report_generator<br/>tiling 512+64 Window)]
        MINIO --- DISK
        GEO --> DISK
    end

    %% ───────── SERVICES ─────────
    subgraph Services["🔧 Deterministic Services (no synthetic)"]
        SVC1[image_pipeline.resolve_asset<br/>sanitize + rglob .geotiff/.gtiff/.jp2]
        SVC2[ffmpeg_preprocessor<br/>crop_bbox_to_png CPU -vf crop]
        SVC3[spectral<br/>NDVI/NDWI/NDBI/EVI pure numpy<br/>fail-closed raise]
        SVC4[geocoder<br/>BUILTIN_GAZETTEER]
        SVC5[transcription<br/>whisper no mock]
        SVC6[tiling reproject_to_target<br/>warp EPSG:4326 nearest]
        SVC7[query_analyzer<br/>temporal/spatial]
        SVC8[embedding bge<br/>mock only PYTEST]
        SVC9[download_weights.py<br/>HF snapshot all 4]
    end

    %% ───────── CROSS LINKS ─────────
    Frontend -->|POST /api/query<br/>SSE stream| Gateway
    Gateway -->|POST /api/v1/task<br/>GET /api/v1/task/(id)/stream<br/>Last-Event-ID| Orchestrator
    Gateway -->|POST /api/v1/ingest<br/>multipart| GEO
    R <-->|tools| Tools
    P <-->|tools| Tools
    R & P <-. registry_prompt_fragment .-> Capabilities
    TA <-. call_model .-> Shims
    TA -. image_path via SVC1 .-> Shims
    TA -. crop via SVC2 .-> Shims
    P <-. RAG retrieve .-> Memory
    CR <-. entity_registry .-> Memory
    TA -. load_history_hybrid .-> Memory
    PP -. evidence grounding .-> SVC3 & SVC4
    Orchestrator <-. persist sat iq:exec .-> REDIS
    Orchestrator <-. Q1 .-> Cache
    Orchestrator --> Storage
    Orchestrator --> Services
```

"""

ASCII_COMPLETE = r"""
COMPLETE SATIQ SYSTEM — 8-NODE ORCHESTRATOR + TOOLS + MEMORY + STORAGE + CACHE

 LAYERS
 ──────
 [Frontend 5173] React/Vite/MapLibre ──► [Gateway 4000] Express ──► [Orchestrator 8000] FastAPI/LangGraph (Ollama qwen3.5:9b) ──► [Models model1-4 shims]
        │                                      │                          │
        │ Composer 100MB createObjectURL       │ upload duplex:half 60s   │ 8 nodes: input_validator → coreference → router → planner → task_agent → post_processing → error/response
        │ StreamMarkdown ?bbox= parse          │ agentic dedup 32         │   router/planner: ROUTER_TOOLS 4 / REGISTERED_TOOLS 10 via ollama.chat tool_choice auto, to_thread
        │ MapLibre bbox overlay                │ rateLimiter userId||ip   │   task_agent: VRAM_SEMAPHORE 2 + asyncio.to_thread → shim internal encoders (no external)
        │ analysisClient abort-safe            │ keepAlive 70s            │   post_processing: conf≥0.6, bbox [0,1], chart real-only
        └──────────────────────────────────────┴──────────────────────────┘   error_handler: MODEL_NOT_LINKED permanent / MODEL_INFERENCE_ERROR transient

 TOOLS (helpers/tool_schemas.py) — exposed to Ollama via tools param
  MODEL: run_vqa (GeoChat-7B) • run_grounding (GroundingDINO Swin-T 2-98%) • run_change_vqa (Prithvi+Vicuna) • run_fusion (CROMA 12+2)
  DETERMINISTIC (6): compute_spectral_indices (fail-closed B04/B08) • calculate_area (bbox+gsd) • geocode_region (gazetteer) • crop_bbox (FFmpeg CPU -vf crop) • generate_visual_evidence • retrieve_history (Chroma top_k 3)

 CAPABILITIES (capability_registry.py)
  vqa/captioning needs 1 opt • grounding needs 1 opt • change_vqa needs 2 opt • optical_sar_fusion needs opt+sar • DETERMINISTIC area/spectral
  validate_legality + registry_prompt_fragment → guardrails PlanSchema step cap 10

 SHIMS → MODELS (no edits to inference scripts)
  model1_shim → models/model1/run_inference.py (load_model ask_geochat) • model2_shim → models/model2/visualize_pipeline_graph.py + vendor config/train (GroundingDINO) • model3_shim → visualize_index_hybrid (indices+fusion) • model4_shim → infer.py + vendor engine/data (CROMA)

 MEMORY — Hybrid RAG (no mock)
  conversation.py load_history_hybrid (Chroma vector + SQLite recency) + save_history add_turn fire-and-forget • rag_store.py Chroma satiq_conversation 8001 + chroma_data volume • entity_registry extract_entities alias→bbox • memory.db SQLite turn_history

 CACHE + RESILIENCE
  query_cache TTLCache 3600/1024 • TTL tile/encoder • Redis satiq-exec-id setex 3600 + Last-Event-ID id: replay • checkpoint sorted-hash request_key • timeouts TOTAL 45s • circuit_breaker qwen_circuit • queue_gate semaphore 429 • dlq

 STORAGE — MinIO + Disk fallback
  MinIO 9000 rs-outputs • Disk orchestrator/storage/ingest/<stem>.tif + audit.db + outputs/ • ingest_file → EXIF GPS + validate_geotiff + thumbnail • geojson_export/report_generator/tiling 512+64 Window

 SERVICES (deterministic, fail-closed)
  image_pipeline.resolve_asset (sanitize asset_/file_ → rglob) • ffmpeg_preprocessor crop_bbox_to_png CPU • spectral NDVI/NDWI/NDBI/EVI (dummy→raise) • geocoder BUILTIN_GAZETTEER • transcription Groq whisper no mock • query_analyzer temporal/spatial • embedding bge

 FLOW
  [User Query + image] → input_validator (fail→error) → coreference (RAG) → router Ollama tools → planner Ollama tools + guardrails → {skip_models→composer | geospatial→task_agent→shims→post_processing→composer} → SSE answer_delta/final_answer + assets /api/assets/{name} → Frontend StreamMarkdown
"""

def save_complete_mermaid(path: str = "orchestrator/graph/complete_system.mmd"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(MERMAID_COMPLETE)
    return path

def save_complete_ascii(path: str = "orchestrator/graph/complete_system.txt"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ASCII_COMPLETE)
    return path


def try_complete_png(path: str = "orchestrator/graph/complete_system.png"):
    """High-res PNG via Pillow — layered system view (Pillow only, no matplotlib)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 2400, 3300
        BG = (11, 15, 26)
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        try:
            f_title = ImageFont.truetype("arial.ttf", 52)
            f_sub = ImageFont.truetype("arial.ttf", 22)
            f_small = ImageFont.truetype("arial.ttf", 18)
            f_mono = ImageFont.truetype("consola.ttf", 16)
        except Exception:
            f_title = ImageFont.load_default()
            f_sub = ImageFont.load_default()
            f_small = ImageFont.load_default()
            f_mono = ImageFont.load_default()

        def hex_to_rgb(h): return tuple(int(h[i:i+2], 16) for i in (1,3,5))
        COLORS_P = {"Frontend": "#7C3AED","Gateway": "#06B6D4","Ollama": "#EAB308","Orch": "#1E293B","Tools": "#10B981","Cap": "#8B5CF6","Shims": "#EF4444","Memory": "#EC4899","Cache": "#F97316","Storage": "#14B8A6","Services": "#6366F1"}

        def block(x, y, w, h, title, subtitle, color_hex):
            col = hex_to_rgb(color_hex)
            draw.rounded_rectangle([x, y, x+w, y+h], radius=28, fill=col, outline=(255,255,255), width=3)
            draw.text((x+w//2, y+38), title, fill="white", font=f_sub, anchor="mm")
            if subtitle:
                yy = y+72
                for ln in subtitle.split("\n"):
                    draw.text((x+18, yy), ln, fill=(11,15,26), font=f_mono, anchor="lm")
                    yy += 26

        draw.text((W//2, 70), "SATIQ — COMPLETE SYSTEM", fill="white", font=f_title, anchor="mm")
        draw.text((W//2, 118), "8-node LangGraph (Ollama qwen3.5:9b)  •  10 Tools  •  Memory Hybrid RAG  •  Storage MinIO/Disk  •  Cache Redis  •  No mocks", fill=(148,163,184), font=f_small, anchor="mm")

        y0 = 160
        block(40, y0, 760, 185, "FRONTEND 5173", "Composer 100MB createObjectURL  •  StreamMarkdown ?bbox=  •  ApexCharts\nMapLibre GeoCanvas bbox overlay  •  ExecutionTrace thinking_delta", COLORS_P["Frontend"])
        block(820, y0, 760, 185, "GATEWAY 4000", "upload duplex:half 60s  •  _authHeader forward\nagentic dedup event:ts:payload 32  •  keepAlive 70s\nrateLimiter userId||ip  •  randomUUID + .jp2", COLORS_P["Gateway"])
        block(1600, y0, 760, 185, "LLM  Ollama qwen3.5:9b", "Ollama serve  •  qwen3.5:9b\nollama.chat tools= ROUTER/REGISTERED tool_choice auto\nno Groq  •  no mock  •  to_thread", COLORS_P["Ollama"])

        y1 = y0 + 220
        draw.rounded_rectangle([40, y1, 40+2320, y1+420], radius=28, fill=hex_to_rgb(COLORS_P["Orch"]), outline=(245,158,11), width=3)
        draw.text((W//2, y1+32), "ORCHESTRATOR 8000 — 8-NODE LANGGRAPH  (models bundle CLIP/Swin/Prithvi/CROMA)", fill=(245,158,11), font=f_sub, anchor="mm")
        nodes = [
            ("input_validator", "CRS hard\ngate 100Mpix", COLORS_P["Orch"]),
            ("coreference\nresolver", "alias\n[RESOLVED]", "#FBBF24"),
            ("router", "Ollama\nROUTER_TOOLS 4", COLORS_P["Orch"]),
            ("planner", "Ollama\nREGISTERED 10", COLORS_P["Orch"]),
            ("task_agent", "VRAM 2\nto_thread", "#EF4444"),
            ("post_\nprocessing", "conf 0.6\nbbox [0,1]", COLORS_P["Tools"]),
            ("error_\nhandler", "NOT_LINKED\npermanent", "#64748B"),
            ("response_\ncomposer", "Ollama\nstream 2048", COLORS_P["Gateway"]),
        ]
        nx = 70
        for i,(lbl,sub,col) in enumerate(nodes):
            x = nx + i*283
            block(x, y1+60, 268, 200, lbl, sub, col)
            if i>0:
                draw.line([x-15, y1+160, x+8, y1+160], fill="white", width=4)
                draw.polygon([x+8, y1+152, x+8, y1+168, x+22, y1+160], fill="white")
        draw.text((W//2, y1+390), "skip_models=greeting/chitchat/help/out_of_scope → response_composer  •  MODEL_NOT_LINKED → error_handler  •  conf<0.6 retry x3 → task_agent", fill=(148,163,184), font=f_mono, anchor="mm")

        y2 = y1 + 455
        block(40, y2, 760, 300, "TOOLS  helpers/tool_schemas.py", "MODEL 4: run_vqa • run_grounding • run_change_vqa • run_fusion\nDETERMINISTIC 6: compute_spectral_indices (B04/B08 fail-closed)\n calculate_area • geocode_region • crop_bbox FFmpeg CPU\n generate_visual_evidence • retrieve_history Chroma top_k 3", COLORS_P["Tools"])
        block(820, y2, 740, 300, "CAPABILITIES  capability_registry.py", "vqa/captioning needs 1 opt\n grounding needs 1 opt  •  change_vqa needs 2 opt\n optical_sar_fusion needs opt+sar\nvalidate_legality → guardrails PlanSchema step cap 10", COLORS_P["Cap"])
        block(1580, y2, 780, 300, "SHIMS → MODELS", "model1_shim → run_inference GeoChat-7B 4bit\nmodel2_shim → GroundingDINO 2-98% + vendor config/train\nmodel3_shim → Prithvi+Vicuna indices+fusion\nmodel4_shim → CROMA 12+2 + vendor engine/data", COLORS_P["Shims"])

        y3 = y2 + 335
        block(40, y3, 760, 335, "MEMORY  Hybrid RAG", "conversation.load_history_hybrid n=3\n rag_store Chroma satiq_conversation 8001 chroma_data\n entity_registry alias→bbox\n memory.db SQLite turn_history\n save_history add_turn fire-and-forget", COLORS_P["Memory"])
        block(820, y3, 740, 335, "CACHE + RESILIENCE", "query_cache TTLCache 3600/1024\n Redis satiq-exec-id setex 3600 + Last-Event-ID\n checkpoint sorted-hash request_key\n timeouts TOTAL 45s • circuit_breaker qwen_circuit\n queue_gate semaphore 429 • dlq", COLORS_P["Cache"])
        block(1580, y3, 780, 335, "STORAGE  MinIO + Disk fallback", "MinIO 9000 rs-outputs bucket\n Disk orchestrator/storage/ingest/*.tif\n audit.db + outputs/ 4-panel\n ingest_file EXIF GPS + validate_geotiff\n tiling 512+64 Window • geojson_export", COLORS_P["Storage"])

        y4 = y3 + 370
        block(40, y4, 1520, 305, "DETERMINISTIC SERVICES  (fail-closed, no synthetic)", "image_pipeline.resolve_asset  sanitize asset_/file_ → rglob ingest   •   ffmpeg_preprocessor crop_bbox_to_png CPU -vf crop\n spectral NDVI/NDWI/NDBI/EVI (dummy→raise)   •   geocoder BUILTIN_GAZETTEER   •   transcription whisper no mock\n query_analyzer temporal/spatial/comparison   •   embedding bge pad 0   •   geojson_export / report_generator", COLORS_P["Services"])
        block(1580, y4, 780, 305, "FLOW  (single-GPU)", "User Query+image → input_validator → coreference (RAG)\n → router/planner Ollama tools → {skip→composer | geospatial→task_agent→shims}\n → post_processing → composer SSE answer_delta + /api/assets\n → StreamMarkdown bbox overlay", "#1E293B")

        draw.text((40, H-38), "Single-GPU: asyncio.to_thread + VRAM_SEMAPHORE(2)  •  100Mpix guard  •  Ollama qwen3.5:9b only  •  No dummy  •  vendor shims: model2 config/train, model4 engine/data", fill=(100,116,139), font=f_mono, anchor="lm")
        draw.rounded_rectangle([18, 18, W-18, H-18], radius=32, outline=(51,65,85), width=2)

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return path
    except Exception as e:
        import traceback
        return f"Pillow PNG failed: {e}\n{traceback.format_exc()[:800]}"

if __name__ == "__main__":
    print(save_complete_mermaid())
    print(save_complete_ascii())
    print(try_complete_png())
