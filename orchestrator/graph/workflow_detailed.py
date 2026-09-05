"""Workflow-detailed graph — how everything is ACTUALLY connected now (code-accurate)."""
from pathlib import Path

WORKFLOW_MERMAID = r"""```mermaid
flowchart TB
    %% ===== ENTRY =====
    USER([User: query + images]) --> FE_COMP[Frontend Composer<br/>Composer.tsx:114 100MB createObjectURL<br/>FormData image + query]
    FE_COMP --> FE_CLIENT[analysisClient.ts:57<br/>POST /api/query SSE<br/>abort-safe]
    FE_CLIENT --> GW_Q[gateway routes/query.ts:23<br/>inject Authorization]
    FE_CLIENT --> GW_U[gateway upload.ts:37<br/>createReadStream duplex:half 60s<br/>forward w/h/crs/gsd]
    GW_U --> INGEST[orchestrator POST /api/v1/ingest<br/>api/main.py:981 ingest_file<br/>EXIF GPS + validate_geotiff<br/>thumbnail → orchestrator/storage/ingest/<stem>.tif]
    INGEST --> DISK[(Disk orchestrator/storage/ingest)]
    GW_Q --> ORCH_POST[ORCH POST /api/v1/task<br/>main.py:743 _normalize_assets<br/>CRS mismatch 400 • 100Mpix 413<br/>queue_gate.acquire 429<br/>EXECUTIONS[(id)] + Redis setex 3600]
    ORCH_POST --> REDIS[(Redis satiq-exec-id<br/>_persist_exec + Last-Event-ID)]
    ORCH_POST --> RUN[run_pipeline main.py:155<br/>_broadcast query_started/input_done/composer_started<br/>pipeline.ainvoke(state)]

    RUN --> IV[input_validator<br/>agents/input_validator.py:23<br/>request_key + deadline 45s<br/>len 16-4000 • jailbreak via guardrails/check_prompt_injection<br/>CRS hard gate _crs_mismatch • GSD>0 • pixel cap w*h>100Mpix<br/>_corrupt/malformed_geotiff]
    IV -->|validation_passed=false<br/>empty_query/greeting/injection/crs_mismatch/image_too_large| EH[error_handler]
    IV -->|pass pending_llm| CR[coreference_resolver<br/>agents/coreference_resolver.py<br/>entity_registry extract_entities<br/>conversation augment_state_with_history]

    CR --> R[router<br/>agents/router_agent.py:11<br/>query_analyzer detect_temporal/spatial/comparison<br/>augment_state_with_history<br/>to_thread call_qwen_router]
    R --> LLM_R["Ollama qwen3.5:9b<br/>core/llm_client.py:500 call_qwen_router<br/>ollama.chat tools=ROUTER_TOOLS 4 tool_choice auto<br/>prompt single-word task_type}}
    LLM_R --> TOOL_R[/ROUTER_TOOLS<br/>helpers/tool_schemas.py:13<br/>run_vqa / run_grounding / run_change_vqa / run_fusion/]
    TOOL_R -. tool_call run_grounding .-> R
    R --> REG1[registry/capability_registry.py<br/>validate_legality + warn change_vqa<2 assets]
    R --> TRACE_R[(add_trace router ok<br/>emit thinking_delta)]

    R --> P[planner<br/>agents/planner_agent.py:9<br/>registry_prompt_fragment<br/>load_history_hybrid n=3 Chroma+SQLite<br/>rag_store.retrieve top_k 3<br/>entity_registry<br/>to_thread call_qwen_planner]
    P --> LLM_P["Ollama qwen3.5:9b<br/>core/llm_client.py:560 call_qwen_planner<br/>ollama.chat tools=REGISTERED_TOOLS 10<br/>JSON GoalPlan}}
    LLM_P --> TOOL_P[/REGISTERED_TOOLS<br/>MODEL 4 + DETERMINISTIC 6<br/>compute_spectral_indices fail-closed<br/>geocode_region / crop_bbox / retrieve_history/]
    TOOL_P -. tool run_fusion .-> P
    P --> GUARD[helpers/guardrails.py<br/>validate_plan hard block<br/>capability_illegal / step cap 10<br/>PlanSchema]
    GUARD -->|guardrail fail permanent| EH
    GUARD --> TRACE_P[(add_trace planner ok<br/>requires_coreg / sub_queries<br/>spatial_aggregation / region_of_interest)]

//    P --> CACHE_Q[(query_cache.py TTLCache 3600/1024)]
//    P -. cache hit? .-> RC_FAST
    P -->|skip_models=greeting/chitchat/help/out_of_scope/REFUSE| RC
    P -->|geospatial vqa/grounding/change/fusion| TA

    TA[task_agent<br/>agents/task_agents.py:34<br/>VRAM_SEMAPHORE 2 + to_thread<br/>_resolve via image_pipeline.resolve_asset<br/>sanitize asset_/file_ → rglob ingest<br/>NO resampling before model]
    TA --> RESOLVE[services/image_pipeline.py<br/>resolve_asset + content_hash<br/>gateway/upload ↔ storage/ingest]
    RESOLVE --> DISK
    TA --> SHIM["model_adapter.py:20 call_model<br/>MODEL_MAP shim pref<br/>probe inference/ask_geochat<br/>MODEL_NOT_LINKED permanent<br/>MODEL_INFERENCE_ERROR transient}}
    SHIM --> S1[model1_shim<br/>load_model 4bit → ask_geochat<br/>models/model1/run_inference.py]
    SHIM --> S2[model2_shim<br/>load_and_convert_s2 2-98% → build_groundingdino<br/>models/model2/visualize + vendor config/train]
    SHIM --> S3[model3_shim<br/>compute_indices NDVI/NDWI + classify_deltas<br/>fusion_change_confidence → Vicuna<br/>models/model3/visualize_index_hybrid]
    SHIM --> S4[model4_shim<br/>Model4Engine → 12+2 bands predict<br/>models/model4/infer + vendor engine/data]
    S1 & S2 & S3 & S4 --> RAW_OUT[(raw dict text/bbox/confidence)]
    RAW_OUT --> FFMPEG[services/ffmpeg_preprocessor.py:14<br/>crop_bbox_to_png CPU -vf crop<br/>only grounding bbox → last_crop_path]
    FFMPEG --> VIS[tools/visualisation_tool<br/>generate_visual_evidence.invoke<br/>bbox overlay / change map / CROMA 4-panel]
    TA --> MERGE[helpers/result_merger.py<br/>sub_queries >1 → merge_sub_results]
    TA --> TRACE_TA[(add_trace task_agent ok<br/>confidence / tmp_files / entity_registry)]

    TA -->|MODEL_NOT_LINKED| EH
    TA -->|error no task_output| EH
    TA -->|ok| PP[post_processing<br/>agents/post_processing.py<br/>conf≥0.6 • bbox clamp [0,1]<br/>evidence grounding • chart real only<br/>build_chart_from_task_output]

    PP -->|_needs_retry conf<0.6 retry≤3| TA
    PP -->|final_result null + error| EH
    PP -->|ok| RC[response_composer<br/>agents/response_composer.py<br/>call_qwen_composer_stream Ollama 2048 tok<br/>to_thread + emit thinking_delta/answer_delta]
    RC --> LLM_C["Ollama qwen3.5:9b stream<br/>core/llm_client.py ollama.chat stream True}}
    LLM_C --> CHART[helpers/chart_spec.py<br/>validate_chart_spec → ```chart]
    RC --> MEM_WRITE[services/conversation.py<br/>save_history fire-and-forget add_turn<br/>→ rag_store add_turn → Chroma + SQLite<br/>→ entity_registry extract_entities]
    MEM_WRITE --> CHROMA[(Chroma 8001 chroma_data<br/>satiq_conversation)]
    MEM_WRITE --> SQLITE[(SQLite memory.db<br/>turn_history)]
    MEM_WRITE --> AUDIT[(audit.db execution_traces)]
    RC --> MINIO_OUT[(MinIO 9000 rs-outputs<br/>+ Disk outputs/ 4-panel)]
    RC --> SSE_OUT[SSE answer_delta + chart + bbox table<br/>+ input image /api/assets/{name} 768px<br/>main.py:233 broadcast + gateway agentic dedup]

    SSE_OUT --> GW_STREAM[gateway agentic-analysis.provider:40<br/>unified getReader/AsyncIterable<br/>dedup event:ts:payload maxAttempts 32]
    GW_STREAM --> FE_STREAM[Frontend StreamMarkdown<br/>?bbox= / alt JSON parse else null<br/>ApexCharts ChartBlock<br/>copy/inspect thinking]
    FE_STREAM --> MAP[MapLibre GeoCanvas<br/>bbox overlay + satellite beam 108s]
    FE_STREAM --> TRACE_UI[ExecutionTrace RightThinkingPanel<br/>planner → models → evidence → composer]

    EH --> ENDPIPE([END __end__])

    %% Side deps
    IV -. request_key .-> CKPT[core/checkpoint.py<br/>compute_request_key sorted-hash]
    IV -. deadline .-> TO[core/timeouts.py<br/>TOTAL 45s per-node tight]
    R & P & RC -. circuit .-> CB[core/circuit_breaker<br/>qwen_circuit]
    R & P & RC -. timeout .-> TO
    ORCH_POST -. metrics .-> MET[core/metrics snapshot<br/>core/structured_logging log_node]
    TA -. tiling .-> TILE[services/tiling.py 512+64 Window<br/>rasterio or passthrough]
    TA -. spectral .-> SPEC[services/spectral.py<br/>NDVI/NDWI pure numpy fail-closed]
    P -. geocode .-> GEO2[services/geocoder.py<br/>BUILTIN_GAZETTEER + GeoJSON]
    P -. query_analyzer .-> QA2[services/query_analyzer.py]
    IV -. validate_geotiff .-> INGEST
    GW_U -. w/h/crs/gsd .-> IV

    style USER fill:#0EA5E9,stroke:#fff,color:#fff
    style ORCH_POST fill:#F59E0B,stroke:#fff,color:#000
    style TA fill:#EF4444,stroke:#fff,color:#fff
    style LLM_R fill:#EAB308,stroke:#000,color:#000
    style LLM_P fill:#EAB308,stroke:#000,color:#000
    style LLM_C fill:#EAB308,stroke:#000,color:#000
    style EH fill:#64748B,stroke:#fff,color:#fff
```

"""

WORKFLOW_ASCII = r"""
WORKFLOW — HOW IT IS ACTUALLY WIRED (no mocks, Ollama qwen3.5:9b, 8-node)

USER (query + image files)
  │
  ├─► Frontend Composer.tsx:114 — 100MB createObjectURL, FormData(image) + query + chips
  │     └─► analysisClient.ts:57 — fetch POST /api/query SSE (abort-safe)
  │           ├─► Gateway upload.ts:37 — createReadStream duplex:half 60s, randomUUID+.jp2, forward Authorization + w/h/crs/gsd, no base64
  │           │     └─► Orchestrator POST /api/v1/ingest main.py:981 — ingest_file() → EXIF GPS + validate_geotiff (rasterio→PIL) + thumbnail → orchestrator/storage/ingest/<stem>.tif + DISK
  │           └─► Gateway query.ts:23 inject Authorization → agentic-analysis.provider:40 (unified getReader/AsyncIterable, dedup event:ts:payload, maxAttempts 32, _authHeader)
  │                 └─► ORCH POST /api/v1/task main.py:743 — _normalize_assets (allow_synthetic false → 400), CRS mismatch 400, pixel 100Mpix 413, queue_gate.acquire 429, EXECUTIONS[(id)] + Redis setex 3600 (satiq-exec-id), Last-Event-ID replay, BackgroundTasks run_pipeline
  │
  └─► RUN_PIPELINE main.py:155 — _broadcast query_started/input_done/composer_started (pre-creates assistant message so answer_delta not dropped), pipeline.ainvoke(state)

        ┌─► input_validator agents/input_validator.py:23 — compute_request_key (sorted-hash) + deadline 45s (core/timeouts), len 16-4000, jailbreak guardrails/check_prompt_injection, CRS _crs_mismatch hard gate, GSD>0, pixel w*h>100Mpix, _corrupt/malformed, add_trace + structured_logging + metrics
        │     ├─ fail (empty_query/greeting/injection/crs_mismatch/image_too_large/malformed) → error_handler → END
        │     └─ pass (pending_llm) → coreference_resolver
        │
        ├─► coreference_resolver — entity_registry extract_entities + conversation augment_state_with_history (followup anchor)
        │
        ├─► router agents/router_agent.py:11 — query_analyzer detect_temporal/spatial/comparison → store query_analysis, to_thread call_qwen_router (Ollama)
        │     └─► LLM Router core/llm_client call_qwen_router — ollama.chat(model=qwen3.5:9b, tools=ROUTER_TOOLS 4 tool_choice auto) → TOOL_NAME_TO_TASK mapping (run_vqa→vqa etc) else single-word regex vqa|grounding|change_vqa|optical_sar_fusion|greeting|chitchat|help|out_of_scope → registry/capability_registry validate_legality → add_trace + emit thinking_delta → sets state task_type/plan
        │
        ├─► planner agents/planner_agent.py:9 — registry_prompt_fragment + load_history_hybrid n=3 (Chroma satiq_conversation 8001 + SQLite) + rag_store.retrieve top_k3 + entity_registry + to_thread call_qwen_planner (Ollama, tools=REGISTERED_TOOLS 10)
        │     └─► LLM Planner — ollama.chat tools=REGISTERED_TOOLS → tool run_fusion/run_grounding etc OR JSON GoalPlan (task_type, reasoning, required_assets, fusion_needed...) → helpers/guardrails validate_plan hard block (capability_illegal/step cap 10, PlanSchema) → sets requires_coreg, sub_queries, spatial_aggregation, region_of_interest via geocoder resolve_from_query, add_trace thinking_delta
        │           ├─ query_cache TTLCache 3600/1024 (future) • checkpoint sorted-hash (hit → ok_cached)
        │           ├─ fail permanent (guardrail) → error_handler
        │           ├─ skip_models (greeting/chitchat/help/out_of_scope/REFUSE) ──► response_composer
        │           └─ geospatial ──► task_agent
        │
        ├─► task_agent agents/task_agents.py:34 — VRAM_SEMAPHORE(2) + asyncio.to_thread, _resolve via services/image_pipeline resolve_asset (sanitize asset_/file_ → rglob gateway/upload↔storage/ingest, NO resampling), modality pick optical/sar, call_model via model_adapter MODEL_MAP shim pref → probe inference/ask_geochat
        │     ├─► Shims: model1_shim load_model 4bit → ask_geochat(image_path,query) → text/conf None • model2_shim load_and_convert_s2 2-98% percentile → build_groundingdino → run_inference → bbox_xyxy pixel + bbox_normalized [0,1] (vendor config/train) • model3_shim compute_indices → classify_deltas threshold 0.05 → fusion_change_confidence → Vicuna text-only • model4_shim Model4Engine 12+2 bands → per_modality (vendor engine/data)
        │     ├─► On error: MODEL_NOT_LINKED permanent → error_handler ; MODEL_INFERENCE_ERROR transient retry 1
        │     ├─► Post-shim: FFmpeg crop_bbox_to_png CPU -vf crop w:h:x:y (only grounding, CPU no VRAM) → last_crop_path + tmp_files + entity_registry/coreference_map • visualisation_tool generate_visual_evidence.invoke (bbox overlay/change map/CROMA 4-panel) • result_merger sub_queries>1 • _cleanup_vram torch.cuda.empty_cache+gc
        │     └─► ok → post_processing
        │
        ├─► post_processing agents/post_processing.py — conf≥0.6 gate (conf None bypass), bbox clamp [0,1], evidence grounding, chart real only via helpers/chart_spec build_chart_from_task_output validate_chart_spec else None (no dummy Sector A), add_trace
        │     ├─ _needs_retry conf<0.6 retry≤3 ↺ task_agent
        │     ├─ fail → error_handler
        │     └─ ok → response_composer
        │
        ├─► response_composer agents/response_composer.py — call_qwen_composer_stream Ollama qwen3.5:9b stream 2048 tok (ollama.chat stream True), emit thinking_delta/answer_delta, chart block ```chart, bbox table, modality table, input image /api/assets/{name} (768px gateway/upload, not base64), save_history fire-and-forget → rag_store add_turn → Chroma + SQLite memory.db + audit.db execution_traces + MinIO rs-outputs
        │     └─► main.py broadcast final_answer + query_completed → Redis persist + SSE answer_delta loop
        │
        └─► error_handler → END

        SSE path: orchestrator GET /api/v1/task/(id)/stream (StreamingResponse + Last-Event-ID id: replay from Redis) → gateway agentic stream → Frontend StreamMarkdown (parse ?bbox= / alt JSON, else null, ApexCharts), MapLibre bbox overlay, ExecutionTrace panel

        Side systems (always available, no mock):
          checkpoint: compute_request_key sorted-hash (core/checkpoint) • timeouts: TOTAL 45s, per-node tight, check_deadline_or_raise • circuit_breaker: qwen_circuit (R/P/RC) • queue_gate: semaphore 429 + dlq • metrics + structured_logging • tiling: 512+64 Window via rasterio or passthrough • spectral: NDVI/NDWI pure numpy (dummy→raise) • geocoder: BUILTIN_GAZETTEER → WGS84 bbox • query_analyzer • embedding: bge pad 0 • transcription: Groq whisper no mock text
"""

def save_workflow_mermaid(path: str = "orchestrator/graph/workflow_detailed.mmd"):
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(WORKFLOW_MERMAID, encoding="utf-8")
    return path

def save_workflow_ascii(path: str = "orchestrator/graph/workflow_detailed.txt"):
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(WORKFLOW_ASCII, encoding="utf-8")
    return path


"""Workflow-detailed graph — how everything is ACTUALLY connected now (code-accurate)."""
from pathlib import Path

WORKFLOW_MERMAID = r"""```mermaid
flowchart TB
    %% ===== ENTRY =====
    USER([User: query + images]) --> FE_COMP[Frontend Composer<br/>Composer.tsx:114 100MB createObjectURL<br/>FormData image + query]
    FE_COMP --> FE_CLIENT[analysisClient.ts:57<br/>POST /api/query SSE<br/>abort-safe]
    FE_CLIENT --> GW_Q[gateway routes/query.ts:23<br/>inject Authorization]
    FE_CLIENT --> GW_U[gateway upload.ts:37<br/>createReadStream duplex:half 60s<br/>forward w/h/crs/gsd]
    GW_U --> INGEST[orchestrator POST /api/v1/ingest<br/>api/main.py:981 ingest_file<br/>EXIF GPS + validate_geotiff<br/>thumbnail → orchestrator/storage/ingest/<stem>.tif]
    INGEST --> DISK[(Disk orchestrator/storage/ingest)]
    GW_Q --> ORCH_POST[ORCH POST /api/v1/task<br/>main.py:743 _normalize_assets<br/>CRS mismatch 400 • 100Mpix 413<br/>queue_gate.acquire 429<br/>EXECUTIONS[(id)] + Redis setex 3600]
    ORCH_POST --> REDIS[(Redis satiq-exec-id<br/>_persist_exec + Last-Event-ID)]
    ORCH_POST --> RUN[run_pipeline main.py:155<br/>_broadcast query_started/input_done/composer_started<br/>pipeline.ainvoke(state)]

    RUN --> IV[input_validator<br/>agents/input_validator.py:23<br/>request_key + deadline 45s<br/>len 16-4000 • jailbreak via guardrails/check_prompt_injection<br/>CRS hard gate _crs_mismatch • GSD>0 • pixel cap w*h>100Mpix<br/>_corrupt/malformed_geotiff]
    IV -->|validation_passed=false<br/>empty_query/greeting/injection/crs_mismatch/image_too_large| EH[error_handler]
    IV -->|pass pending_llm| CR[coreference_resolver<br/>agents/coreference_resolver.py<br/>entity_registry extract_entities<br/>conversation augment_state_with_history]

    CR --> R[router<br/>agents/router_agent.py:11<br/>query_analyzer detect_temporal/spatial/comparison<br/>augment_state_with_history<br/>to_thread call_qwen_router]
    R --> LLM_R["Ollama qwen3.5:9b<br/>core/llm_client.py:500 call_qwen_router<br/>ollama.chat tools=ROUTER_TOOLS 4 tool_choice auto<br/>prompt single-word task_type}}
    LLM_R --> TOOL_R[/ROUTER_TOOLS<br/>helpers/tool_schemas.py:13<br/>run_vqa / run_grounding / run_change_vqa / run_fusion/]
    TOOL_R -. tool_call run_grounding .-> R
    R --> REG1[registry/capability_registry.py<br/>validate_legality + warn change_vqa<2 assets]
    R --> TRACE_R[(add_trace router ok<br/>emit thinking_delta)]

    R --> P[planner<br/>agents/planner_agent.py:9<br/>registry_prompt_fragment<br/>load_history_hybrid n=3 Chroma+SQLite<br/>rag_store.retrieve top_k 3<br/>entity_registry<br/>to_thread call_qwen_planner]
    P --> LLM_P["Ollama qwen3.5:9b<br/>core/llm_client.py:560 call_qwen_planner<br/>ollama.chat tools=REGISTERED_TOOLS 10<br/>JSON GoalPlan}}
    LLM_P --> TOOL_P[/REGISTERED_TOOLS<br/>MODEL 4 + DETERMINISTIC 6<br/>compute_spectral_indices fail-closed<br/>geocode_region / crop_bbox / retrieve_history/]
    TOOL_P -. tool run_fusion .-> P
    P --> GUARD[helpers/guardrails.py<br/>validate_plan hard block<br/>capability_illegal / step cap 10<br/>PlanSchema]
    GUARD -->|guardrail fail permanent| EH
    GUARD --> TRACE_P[(add_trace planner ok<br/>requires_coreg / sub_queries<br/>spatial_aggregation / region_of_interest)]

//    P --> CACHE_Q[(query_cache.py TTLCache 3600/1024)]
//    P -. cache hit? .-> RC_FAST
    P -->|skip_models=greeting/chitchat/help/out_of_scope/REFUSE| RC
    P -->|geospatial vqa/grounding/change/fusion| TA

    TA[task_agent<br/>agents/task_agents.py:34<br/>VRAM_SEMAPHORE 2 + to_thread<br/>_resolve via image_pipeline.resolve_asset<br/>sanitize asset_/file_ → rglob ingest<br/>NO resampling before model]
    TA --> RESOLVE[services/image_pipeline.py<br/>resolve_asset + content_hash<br/>gateway/upload ↔ storage/ingest]
    RESOLVE --> DISK
    TA --> SHIM["model_adapter.py:20 call_model<br/>MODEL_MAP shim pref<br/>probe inference/ask_geochat<br/>MODEL_NOT_LINKED permanent<br/>MODEL_INFERENCE_ERROR transient}}
    SHIM --> S1[model1_shim<br/>load_model 4bit → ask_geochat<br/>models/model1/run_inference.py]
    SHIM --> S2[model2_shim<br/>load_and_convert_s2 2-98% → build_groundingdino<br/>models/model2/visualize + vendor config/train]
    SHIM --> S3[model3_shim<br/>compute_indices NDVI/NDWI + classify_deltas<br/>fusion_change_confidence → Vicuna<br/>models/model3/visualize_index_hybrid]
    SHIM --> S4[model4_shim<br/>Model4Engine → 12+2 bands predict<br/>models/model4/infer + vendor engine/data]
    S1 & S2 & S3 & S4 --> RAW_OUT[(raw dict text/bbox/confidence)]
    RAW_OUT --> FFMPEG[services/ffmpeg_preprocessor.py:14<br/>crop_bbox_to_png CPU -vf crop<br/>only grounding bbox → last_crop_path]
    FFMPEG --> VIS[tools/visualisation_tool<br/>generate_visual_evidence.invoke<br/>bbox overlay / change map / CROMA 4-panel]
    TA --> MERGE[helpers/result_merger.py<br/>sub_queries >1 → merge_sub_results]
    TA --> TRACE_TA[(add_trace task_agent ok<br/>confidence / tmp_files / entity_registry)]

    TA -->|MODEL_NOT_LINKED| EH
    TA -->|error no task_output| EH
    TA -->|ok| PP[post_processing<br/>agents/post_processing.py<br/>conf≥0.6 • bbox clamp [0,1]<br/>evidence grounding • chart real only<br/>build_chart_from_task_output]

    PP -->|_needs_retry conf<0.6 retry≤3| TA
    PP -->|final_result null + error| EH
    PP -->|ok| RC[response_composer<br/>agents/response_composer.py<br/>call_qwen_composer_stream Ollama 2048 tok<br/>to_thread + emit thinking_delta/answer_delta]
    RC --> LLM_C["Ollama qwen3.5:9b stream<br/>core/llm_client.py ollama.chat stream True}}
    LLM_C --> CHART[helpers/chart_spec.py<br/>validate_chart_spec → ```chart]
    RC --> MEM_WRITE[services/conversation.py<br/>save_history fire-and-forget add_turn<br/>→ rag_store add_turn → Chroma + SQLite<br/>→ entity_registry extract_entities]
    MEM_WRITE --> CHROMA[(Chroma 8001 chroma_data<br/>satiq_conversation)]
    MEM_WRITE --> SQLITE[(SQLite memory.db<br/>turn_history)]
    MEM_WRITE --> AUDIT[(audit.db execution_traces)]
    RC --> MINIO_OUT[(MinIO 9000 rs-outputs<br/>+ Disk outputs/ 4-panel)]
    RC --> SSE_OUT[SSE answer_delta + chart + bbox table<br/>+ input image /api/assets/{name} 768px<br/>main.py:233 broadcast + gateway agentic dedup]

    SSE_OUT --> GW_STREAM[gateway agentic-analysis.provider:40<br/>unified getReader/AsyncIterable<br/>dedup event:ts:payload maxAttempts 32]
    GW_STREAM --> FE_STREAM[Frontend StreamMarkdown<br/>?bbox= / alt JSON parse else null<br/>ApexCharts ChartBlock<br/>copy/inspect thinking]
    FE_STREAM --> MAP[MapLibre GeoCanvas<br/>bbox overlay + satellite beam 108s]
    FE_STREAM --> TRACE_UI[ExecutionTrace RightThinkingPanel<br/>planner → models → evidence → composer]

    EH --> ENDPIPE([END __end__])

    %% Side deps
    IV -. request_key .-> CKPT[core/checkpoint.py<br/>compute_request_key sorted-hash]
    IV -. deadline .-> TO[core/timeouts.py<br/>TOTAL 45s per-node tight]
    R & P & RC -. circuit .-> CB[core/circuit_breaker<br/>qwen_circuit]
    R & P & RC -. timeout .-> TO
    ORCH_POST -. metrics .-> MET[core/metrics snapshot<br/>core/structured_logging log_node]
    TA -. tiling .-> TILE[services/tiling.py 512+64 Window<br/>rasterio or passthrough]
    TA -. spectral .-> SPEC[services/spectral.py<br/>NDVI/NDWI pure numpy fail-closed]
    P -. geocode .-> GEO2[services/geocoder.py<br/>BUILTIN_GAZETTEER + GeoJSON]
    P -. query_analyzer .-> QA2[services/query_analyzer.py]
    IV -. validate_geotiff .-> INGEST
    GW_U -. w/h/crs/gsd .-> IV

    style USER fill:#0EA5E9,stroke:#fff,color:#fff
    style ORCH_POST fill:#F59E0B,stroke:#fff,color:#000
    style TA fill:#EF4444,stroke:#fff,color:#fff
    style LLM_R fill:#EAB308,stroke:#000,color:#000
    style LLM_P fill:#EAB308,stroke:#000,color:#000
    style LLM_C fill:#EAB308,stroke:#000,color:#000
    style EH fill:#64748B,stroke:#fff,color:#fff
```

"""

WORKFLOW_ASCII = r"""
WORKFLOW — HOW IT IS ACTUALLY WIRED (no mocks, Ollama qwen3.5:9b, 8-node)

USER (query + image files)
  │
  ├─► Frontend Composer.tsx:114 — 100MB createObjectURL, FormData(image) + query + chips
  │     └─► analysisClient.ts:57 — fetch POST /api/query SSE (abort-safe)
  │           ├─► Gateway upload.ts:37 — createReadStream duplex:half 60s, randomUUID+.jp2, forward Authorization + w/h/crs/gsd, no base64
  │           │     └─► Orchestrator POST /api/v1/ingest main.py:981 — ingest_file() → EXIF GPS + validate_geotiff (rasterio→PIL) + thumbnail → orchestrator/storage/ingest/<stem>.tif + DISK
  │           └─► Gateway query.ts:23 inject Authorization → agentic-analysis.provider:40 (unified getReader/AsyncIterable, dedup event:ts:payload, maxAttempts 32, _authHeader)
  │                 └─► ORCH POST /api/v1/task main.py:743 — _normalize_assets (allow_synthetic false → 400), CRS mismatch 400, pixel 100Mpix 413, queue_gate.acquire 429, EXECUTIONS[(id)] + Redis setex 3600 (satiq-exec-id), Last-Event-ID replay, BackgroundTasks run_pipeline
  │
  └─► RUN_PIPELINE main.py:155 — _broadcast query_started/input_done/composer_started (pre-creates assistant message so answer_delta not dropped), pipeline.ainvoke(state)

        ┌─► input_validator agents/input_validator.py:23 — compute_request_key (sorted-hash) + deadline 45s (core/timeouts), len 16-4000, jailbreak guardrails/check_prompt_injection, CRS _crs_mismatch hard gate, GSD>0, pixel w*h>100Mpix, _corrupt/malformed, add_trace + structured_logging + metrics
        │     ├─ fail (empty_query/greeting/injection/crs_mismatch/image_too_large/malformed) → error_handler → END
        │     └─ pass (pending_llm) → coreference_resolver
        │
        ├─► coreference_resolver — entity_registry extract_entities + conversation augment_state_with_history (followup anchor)
        │
        ├─► router agents/router_agent.py:11 — query_analyzer detect_temporal/spatial/comparison → store query_analysis, to_thread call_qwen_router (Ollama)
        │     └─► LLM Router core/llm_client call_qwen_router — ollama.chat(model=qwen3.5:9b, tools=ROUTER_TOOLS 4 tool_choice auto) → TOOL_NAME_TO_TASK mapping (run_vqa→vqa etc) else single-word regex vqa|grounding|change_vqa|optical_sar_fusion|greeting|chitchat|help|out_of_scope → registry/capability_registry validate_legality → add_trace + emit thinking_delta → sets state task_type/plan
        │
        ├─► planner agents/planner_agent.py:9 — registry_prompt_fragment + load_history_hybrid n=3 (Chroma satiq_conversation 8001 + SQLite) + rag_store.retrieve top_k3 + entity_registry + to_thread call_qwen_planner (Ollama, tools=REGISTERED_TOOLS 10)
        │     └─► LLM Planner — ollama.chat tools=REGISTERED_TOOLS → tool run_fusion/run_grounding etc OR JSON GoalPlan (task_type, reasoning, required_assets, fusion_needed...) → helpers/guardrails validate_plan hard block (capability_illegal/step cap 10, PlanSchema) → sets requires_coreg, sub_queries, spatial_aggregation, region_of_interest via geocoder resolve_from_query, add_trace thinking_delta
        │           ├─ query_cache TTLCache 3600/1024 (future) • checkpoint sorted-hash (hit → ok_cached)
        │           ├─ fail permanent (guardrail) → error_handler
        │           ├─ skip_models (greeting/chitchat/help/out_of_scope/REFUSE) ──► response_composer
        │           └─ geospatial ──► task_agent
        │
        ├─► task_agent agents/task_agents.py:34 — VRAM_SEMAPHORE(2) + asyncio.to_thread, _resolve via services/image_pipeline resolve_asset (sanitize asset_/file_ → rglob gateway/upload↔storage/ingest, NO resampling), modality pick optical/sar, call_model via model_adapter MODEL_MAP shim pref → probe inference/ask_geochat
        │     ├─► Shims: model1_shim load_model 4bit → ask_geochat(image_path,query) → text/conf None • model2_shim load_and_convert_s2 2-98% percentile → build_groundingdino → run_inference → bbox_xyxy pixel + bbox_normalized [0,1] (vendor config/train) • model3_shim compute_indices → classify_deltas threshold 0.05 → fusion_change_confidence → Vicuna text-only • model4_shim Model4Engine 12+2 bands → per_modality (vendor engine/data)
        │     ├─► On error: MODEL_NOT_LINKED permanent → error_handler ; MODEL_INFERENCE_ERROR transient retry 1
        │     ├─► Post-shim: FFmpeg crop_bbox_to_png CPU -vf crop w:h:x:y (only grounding, CPU no VRAM) → last_crop_path + tmp_files + entity_registry/coreference_map • visualisation_tool generate_visual_evidence.invoke (bbox overlay/change map/CROMA 4-panel) • result_merger sub_queries>1 • _cleanup_vram torch.cuda.empty_cache+gc
        │     └─► ok → post_processing
        │
        ├─► post_processing agents/post_processing.py — conf≥0.6 gate (conf None bypass), bbox clamp [0,1], evidence grounding, chart real only via helpers/chart_spec build_chart_from_task_output validate_chart_spec else None (no dummy Sector A), add_trace
        │     ├─ _needs_retry conf<0.6 retry≤3 ↺ task_agent
        │     ├─ fail → error_handler
        │     └─ ok → response_composer
        │
        ├─► response_composer agents/response_composer.py — call_qwen_composer_stream Ollama qwen3.5:9b stream 2048 tok (ollama.chat stream True), emit thinking_delta/answer_delta, chart block ```chart, bbox table, modality table, input image /api/assets/{name} (768px gateway/upload, not base64), save_history fire-and-forget → rag_store add_turn → Chroma + SQLite memory.db + audit.db execution_traces + MinIO rs-outputs
        │     └─► main.py broadcast final_answer + query_completed → Redis persist + SSE answer_delta loop
        │
        └─► error_handler → END

        SSE path: orchestrator GET /api/v1/task/(id)/stream (StreamingResponse + Last-Event-ID id: replay from Redis) → gateway agentic stream → Frontend StreamMarkdown (parse ?bbox= / alt JSON, else null, ApexCharts), MapLibre bbox overlay, ExecutionTrace panel

        Side systems (always available, no mock):
          checkpoint: compute_request_key sorted-hash (core/checkpoint) • timeouts: TOTAL 45s, per-node tight, check_deadline_or_raise • circuit_breaker: qwen_circuit (R/P/RC) • queue_gate: semaphore 429 + dlq • metrics + structured_logging • tiling: 512+64 Window via rasterio or passthrough • spectral: NDVI/NDWI pure numpy (dummy→raise) • geocoder: BUILTIN_GAZETTEER → WGS84 bbox • query_analyzer • embedding: bge pad 0 • transcription: Groq whisper no mock text
"""

def save_workflow_mermaid(path: str = "orchestrator/graph/workflow_detailed.mmd"):
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(WORKFLOW_MERMAID, encoding="utf-8")
    return path

def save_workflow_ascii(path: str = "orchestrator/graph/workflow_detailed.txt"):
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(WORKFLOW_ASCII, encoding="utf-8")
    return path


def try_workflow_png(path: str = "orchestrator/graph/workflow_detailed.png"):
    """Vertical workflow PNG via Pillow — properly spaced, orthogonal links, no overlap."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        W = 2800
        # dynamic height: top 180 + nodes*220 + side gaps + bottom 180
        NUM_NODES = 8
        NODE_H = 168
        GAP = 38
        TOP_H = 190
        SIDE_W = 980
        LEFT_W = 620
        SPINE_X = 440
        LEFT_X = 80
        RIGHT_X = 1120
        # Compute height
        H = TOP_H + NUM_NODES * (NODE_H + GAP) + 520
        BG = (9, 12, 24)
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)

        # Fonts — try Windows absolute paths
        def load_font(name, size):
            import pathlib
            candidates = [
                f"C:\\Windows\\Fonts\\{name}",
                f"/Windows/Fonts/{name}",
                name,
            ]
            for cand in candidates:
                try:
                    if pathlib.Path(cand).exists():
                        return ImageFont.truetype(cand, size)
                except Exception:
                    pass
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                return ImageFont.load_default()

        f_title = load_font("arial.ttf", 46)
        f_subtitle = load_font("arial.ttf", 18)
        f_head = load_font("arialbd.ttf", 20)
        # fallback to arial if bold missing
        if f_head == ImageFont.load_default():
            f_head = load_font("arial.ttf", 20)
        f_body = load_font("arial.ttf", 16)
        f_mono = load_font("consola.ttf", 14)
        if f_mono == ImageFont.load_default():
            f_mono = load_font("consol.ttf", 14)
        f_small = load_font("arial.ttf", 13)

        def col(h): 
            h = h.lstrip("#")
            return tuple(int(h[i:i+2], 16) for i in (0,2,4))

        C = {"fe": "#7C3AED", "gw": "#06B6D4", "or": "#F59E0B", "llm": "#EAB308", "mem": "#EC4899", "stor": "#14B8A6", "cache": "#F97316", "svc": "#6366F1", "err": "#475569", "ok": "#10B981"}

        def wrap_lines(text, width=52):
            out = []
            for para in text.split("\n"):
                if not para.strip():
                    out.append("")
                else:
                    out.extend(textwrap.wrap(para, width=width))
            return out

        def block(x, y, w, h, title, body, color_hex, title_color="white", body_color=None):
            # body_color: text color inside, default dark for light bg, white for dark bg
            is_dark = color_hex in ("#1E293B", "#0B1224", "#475569")
            if body_color is None:
                body_color = (226, 232, 240) if is_dark else (15, 23, 42)
            # shadow
            draw.rounded_rectangle([x+4, y+4, x+w+4, y+h+4], radius=18, fill=(0,0,0,40))
            draw.rounded_rectangle([x, y, x+w, y+h], radius=18, fill=col(color_hex), outline=(255,255,255), width=2)
            # title bar
            draw.rounded_rectangle([x, y, x+w, y+34], radius=18, fill=(0,0,0,18))
            # redraw top to keep rounded only at top — cheat with overlay
            draw.rectangle([x+18, y+18, x+w-18, y+34], fill=col(color_hex))
            draw.text((x+w//2, y+17), title, fill=title_color, font=f_head, anchor="mm")
            yy = y+44
            for para in body.split("\n"):
                if not para.strip():
                    yy += 8
                    continue
                # wrap to fit width
                max_chars = 58 if w > 700 else 42
                wrapped = textwrap.wrap(para, width=max_chars)
                for ln in wrapped:
                    draw.text((x+14, yy), ln, fill=body_color, font=f_mono, anchor="lm")
                    yy += 16
                yy += 2
            return yy

        # ── Title ──
        draw.text((W//2, 52), "SATIQ — HOW IT IS ACTUALLY WIRED  (Ollama qwen3.5:9b  •  no mocks)", fill="white", font=f_title, anchor="mm")
        draw.text((W//2, 96), "Frontend 5173  →  Gateway 4000  →  Orchestrator 8000  8-node LangGraph  •  Tools 10  •  Shims 4  •  Memory / Storage / Cache", fill=(148,163,184), font=f_small, anchor="mm")
        draw.text((W//2, 118), "solid = main pipeline   •   dashed = side dependency (short orthogonal stub, no diagonal crossing)", fill=(100,116,139), font=f_small, anchor="mm")

        # Top row — three entry blocks
        y_top = 140
        block(30, y_top, 860, 132, "USER  +  FRONTEND  5173", "Composer.tsx:114  100 MB createObjectURL  •  FormData(image)+query+chips\nanalysisClient.ts:57  fetch POST /api/query  SSE  abort-safe, Finally only if !failed", C["fe"])
        block(920, y_top, 860, 132, "GATEWAY  4000  Express", "routes/upload.ts:37  createReadStream duplex:half 60 s  randomUUID+.jp2  forward w/h/crs/gsd\nagentic dedup event:ts:payload  maxAttempts 32  keepAlive 70 s  rateLimiter userId||ip", C["gw"])
        block(1810, y_top, 960, 132, "ORCH  POST /api/v1/task  (api/main.py:743)", "_normalize_assets  CRS 400  •  100 Mpix 413  •  queue_gate 429\nEXECUTIONS[(id)] + Redis setex 3600  +  Last-Event-ID id: replay  •  BackgroundTasks run_pipeline", C["or"])
        # top arrows
        def h_arrow(x1, y1, x2, y2):
            draw.line([x1, y1, x2, y2], fill="white", width=3)
            draw.polygon([x2-10, y2-7, x2-10, y2+7, x2+6, y2], fill="white")
        h_arrow(890, y_top+66, 920, y_top+66)
        h_arrow(1780, y_top+66, 1810, y_top+66)
        # down to spine
        spine_top_y = y_top + 132 + 18
        draw.line([W//2, spine_top_y, W//2, spine_top_y+28], fill="white", width=3)
        draw.polygon([W//2-7, spine_top_y+22, W//2+7, spine_top_y+22, W//2, spine_top_y+34], fill="white")
        draw.text((W//2, spine_top_y+14), "pipeline.ainvoke(state)  main.py:155", fill=(226,232,240), font=f_small, anchor="mm")

        # ── Vertical pipeline + aligned side boxes ──
        # Each pipeline node has a right-aligned side box at same Y, connected by short horizontal stub (no diagonal)
        nodes = [
            ("1  input_validator", "agents/input_validator.py:23  •  request_key sorted-hash  •  deadline 45 s\nlen 16–4000  •  guardrails check_prompt_injection (jailbreak)\nCRS _crs_mismatch hard gate  •  GSD>0  •  pixel w*h>100 Mpix\n_corrupt / malformed_geotiff  →  validation_passed", C["or"],
             "SIDE  checkpoint + timeouts + guardrails", "checkpoint compute_request_key\ntimeouts TOTAL 45 s  per-node tight\nvalidate_geotiff  →  ingest\nvalidate_geotiff_integrity"),

            ("2  coreference_resolver", "agents/coreference_resolver  •  entity_registry.extract_entities\nconversation augment_state_with_history\nfollowup anchor  <1 ms  •  alias → [RESOLVED:bbox]", C["or"],
             "SIDE  memory: entity + history", "entity_registry  alias → bbox\nconversation history  is_followup"),

            ("3  router", "agents/router_agent.py:11  •  query_analyzer temporal/spatial/comparison\nto_thread  call_qwen_router  Ollama qwen3.5:9b\ntools = ROUTER_TOOLS 4  tool_choice auto  →  task_type", C["llm"],
             "SIDE  ROUTER_TOOLS 4  →  Ollama", "helpers/tool_schemas.py:13\nrun_vqa  run_grounding  run_change_vqa  run_fusion\ncapability_registry validate_legality"),

            ("4  planner", "agents/planner_agent.py:9  •  registry_prompt_fragment\nload_history_hybrid n=3  Chroma 8001 + SQLite\nrag_store.retrieve top_k 3  •  entity_registry\nto_thread  call_qwen_planner  REGISTERED_TOOLS 10", C["llm"],
             "SIDE  PLANNER  RAG + guardrails", "REGISTERED_TOOLS 10  MODEL 4 + DETERMINISTIC 6\ngeocode_region  query_analyzer  •  guardrails\nPlanSchema  step cap 10  capability_illegal → error"),

            ("5  task_agent", "agents/task_agents.py:34  •  VRAM_SEMAPHORE(2)  +  to_thread\nimage_pipeline.resolve_asset  rglob ingest  NO resampling\nmodel_adapter MODEL_MAP  shim pref  probe inference/ask_geochat", C["or"],
             "SIDE  SHIMS → MODELS  (internal encoders)", "model1 GeoChat-7B 4-bit ask_geochat\nmodel2 GroundingDINO 2-98%  vendor config/train\nmodel3 Prithvi+Vicuna  •  model4 CROMA 12+2\n+ FFmpeg CPU crop  tiling 512+64  spectral fail-closed"),

            ("6  post_processing", "agents/post_processing.py  •  conf ≥0.6 gate (None bypass)\nbbox clamp [0,1]  •  evidence grounding\nchart real only  validate_chart_spec (no dummy Sector A)", C["ok"],
             "SIDE  evidence + chart", "helpers/chart_spec  chart_spec → ```chart\nspectral NDVI/NDWI  geocoder  •  bbox clamp"),

            ("7  response_composer", "agents/response_composer.py  •  call_qwen_composer_stream\nOllama qwen3.5:9b  stream 2048 tok  to_thread\nemit thinking_delta / answer_delta  •  chart + bbox table\nsave_history → Chroma/SQLite/audit  +  MinIO", C["gw"],
             "SIDE  persist + stream", "Chroma satiq_conversation  memory.db SQLite\naudit.db execution_traces  MinIO rs-outputs\nSSE answer_delta  /api/assets 768 px"),

            ("8  error_handler", "permanent  MODEL_NOT_LINKED  (add inference.py)\ntransient  MODEL_INFERENCE_ERROR  retry 1\nlow_confidence  retry ×3 → task_agent  →  END", C["err"],
             None),

        ]

        cur_y = spine_top_y + 42
        spine_x = LEFT_X + LEFT_W//2  # center of left column
        right_x = RIGHT_X
        # keep track for bottom arrow
        first_node_center = None
        last_node_center = None

        for idx, item in enumerate(nodes):
            title, body, color = item[0], item[1], item[2]
            side_title = "\n".join(str(x) for x in item[3:]) if len(item)>3 else None
            is_last = idx == len(nodes)-1
            # left pipeline block
            left_h = 148
            # adjust height for longer bodies (planner, task_agent)
            if idx == 3: left_h = 172
            if idx == 4: left_h = 168
            if idx == 6: left_h = 162
            block(LEFT_X, cur_y, LEFT_W, left_h, title, body, color)

            # right side block aligned to same Y (short stub, no diagonal)
            if side_title is not None:
                side_body = side_title
                # side_title in our tuple is actually "SIDE ..." header, body is next string
                # we packed as 4-tuple: title, body, color, side_combined; need split
                # Our nodes tuple is (title, body, color, side_text) where side_text contains title+body
                # So extract side title/body
                side_text = side_title
                # side_text contains "SIDE  ...\n..." — split first line as title
                parts = side_text.split("\n", 1)
                side_t = parts[0].replace("SIDE  ", "")
                side_b = parts[1] if len(parts) > 1 else ""
                # choose color per side
                side_color = "#334155" if "SIDE" in side_t else "#1E293B"
                # map side_t to color
                if "ROUTER_TOOLS" in side_t: side_color = C["llm"]
                elif "PLANNER" in side_t: side_color = "#8B5CF6"
                elif "SHIMS" in side_t: side_color = "#EF4444"
                elif "evidence" in side_t.lower(): side_color = C["ok"]
                elif "persist" in side_t.lower(): side_color = C["mem"]
                elif "checkpoint" in side_t.lower(): side_color = "#475569"
                elif "entity" in side_t.lower(): side_color = C["mem"]
                block(right_x, cur_y, SIDE_W, left_h, side_t, side_b, side_color)
                # short horizontal stub
                sx1 = LEFT_X + LEFT_W + 10
                sx2 = right_x - 10
                sy = cur_y + left_h//2
                draw.line([sx1, sy, sx2, sy], fill=(148,163,184), width=2)
                draw.line([sx1, sy-8, sx1, sy+8], fill=(148,163,184), width=2)
                draw.polygon([sx2, sy-6, sx2, sy+6, sx2+10, sy], fill=(148,163,184))
                draw.text(((sx1+sx2)//2, sy-10), "uses", fill=(148,163,184), font=f_small, anchor="mm")

            # vertical spine arrow to next node
            if not is_last:
                nxt_y = cur_y + left_h + GAP
                # spine line
                draw.line([spine_x, cur_y+left_h, spine_x, nxt_y], fill="white", width=3)
                draw.polygon([spine_x-7, nxt_y-8, spine_x+7, nxt_y-8, spine_x, nxt_y+6], fill="white")
                # labels between nodes
                if idx == 0:
                    draw.text((spine_x+22, cur_y+left_h+12), "pass  pending_llm", fill=(16,185,129), font=f_small, anchor="lm")
                    # fail branch to error (drawn later as separate path, not diagonal)
                    # draw fail stub to right then down to error_handler
                    fail_y = cur_y + left_h - 28
                    draw.line([LEFT_X+LEFT_W, fail_y, LEFT_X+LEFT_W+40, fail_y], fill=(239,68,68), width=2)
                    draw.text((LEFT_X+LEFT_W+46, fail_y), "fail → error_handler", fill=(239,68,68), font=f_small, anchor="lm")
                if idx == 3:
                    draw.text((spine_x+22, cur_y+left_h+12), "geospatial → task_agent", fill="white", font=f_small, anchor="lm")
                    draw.text((LEFT_X+LEFT_W+22, cur_y+left_h+26), "skip_models  greeting/chitchat/help/out_of_scope → response_composer", fill=(100,116,139), font=f_small, anchor="lm")
                if idx == 5:
                    draw.text((spine_x+22, cur_y+left_h+12), "ok → response_composer", fill="white", font=f_small, anchor="lm")
                    draw.text((LEFT_X+LEFT_W+22, cur_y+left_h+26), "_needs_retry conf<0.6 ×3 ↺ task_agent", fill=(251,146,60), font=f_small, anchor="lm")
                cur_y = nxt_y
                if idx == 0:
                    first_node_center = (spine_x, cur_y)
            else:
                last_node_center = (spine_x, cur_y+left_h//2)
                cur_y += left_h

        # Bottom SSE block — spans width, connected from response_composer
        by = cur_y + 32
        block(80, by, W-160, 118, "RESPONSE  SSE  →  Gateway agentic dedup 32  →  Frontend StreamMarkdown (?bbox= parse, ApexCharts)  +  MapLibre bbox overlay  +  ExecutionTrace", "response_composer  ollama stream 2048  →  broadcast answer_delta + chart + bbox table + /api/assets/{name} 768 px (not base64)  →  gateway upload  →  frontend\npersist:  MinIO rs-outputs  •  audit.db execution_traces  •  Redis satiq-exec-id  •  Chroma/SQLite  •  metrics + structured_logging", "#0F172A")
        # arrow from last pipeline node (error_handler is separate, response_composer is node 7)
        # response_composer was at idx 6, its center is at cur_y - left_h - GAP ...
        # draw vertical from response_composer (node 7) down to bottom block
        # find response_composer y
        rc_y = cur_y - left_h - GAP - 162 - GAP  # approximate, but compute from stored
        # Instead draw from spine
        draw.line([spine_x, cur_y - left_h - GAP//2, spine_x, by], fill="white", width=3)
        draw.polygon([spine_x-7, by-8, spine_x+7, by-8, spine_x, by+6], fill="white")
        # also error_handler → END branch
        draw.text((LEFT_X+LEFT_W+40, cur_y - left_h//2), "error_handler → END  __end__", fill=(100,116,139), font=f_small, anchor="lm")

        # Outer border + footer
        draw.rounded_rectangle([12, 12, W-12, by+118+42], radius=28, outline=(51,65,85), width=2)
        draw.text((24, by+118+22), "Single-GPU: asyncio.to_thread + VRAM_SEMAPHORE(2)  •  100 Mpix guard  •  Ollama qwen3.5:9b only  •  No dummy  •  vendor shims: model2 config/train, model4 engine/data  •  file:line refs are current  •  lateral stubs = short orthogonal, no diagonal overlap", fill=(100,116,139), font=f_small, anchor="lm")

        # Crop to content height (remove trailing blank)
        final_h = by + 118 + 60
        if final_h > H: final_h = H
        if final_h < 100: final_h = H
        img_cropped = img.crop((0,0,W, final_h))
        import pathlib as _P
        _P.Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Remove existing file lock if any
        try:
            if _P.Path(path).exists():
                _P.Path(path).unlink()
        except Exception:
            pass
        img_cropped.save(path, "PNG")
        return path
    except Exception as e2:
        import traceback
        return f"workflow PNG failed: {e2}\n{traceback.format_exc()[:1800]}"


if __name__ == "__main__":
    print(save_workflow_mermaid())
    print(save_workflow_ascii())
    print(try_workflow_png())
if __name__ == "__main__":
    print(save_workflow_mermaid())
    print(save_workflow_ascii())
    print(try_workflow_png())
