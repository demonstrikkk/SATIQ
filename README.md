# Satiq

Monorepo for geospatial analysis — React + MapLibre frontend, Node/Express gateway, Python orchestrator, isolated capabilities, adaptation and evaluation harness.

## Structure

```
satiq/
├── frontend/                    # React + TS + MapLibre
│   ├── src/
│   │   ├── workspace/           # map + chat + evidence inspector
│   │   ├── components/
│   │   │   ├── ExecutionTrace/  # the key UI differentiator
│   │   │   ├── EvidencePanel/
│   │   │   └── ModalityView/    # optical vs SAR split
│   │   └── hooks/
├── gateway/                     # Node/Express + TypeScript
│   ├── routes/
│   ├── upload/                  # GeoTIFF handling
│   └── session/
├── orchestrator/                # Python — the core system
│   ├── models/
│   │   ├── raster_asset.py
│   │   └── analysis_result.py
│   ├── ingestion/
│   │   └── validator.py         # CRS hard gate
│   ├── understanding/
│   │   └── query_normalizer.py
│   ├── planner/
│   │   └── llm_planner.py
│   ├── registry/
│   │   ├── capability_registry.py
│   │   └── topo_resolver.py
│   ├── engine/
│   │   ├── execution_engine.py
│   │   └── result_cache.py
│   ├── evidence/
│   │   ├── evidence_graph.py
│   │   └── confidence_engine.py
│   └── composer/
│       └── vlm_composer.py
├── capabilities/
│   ├── single_image/
│   │   ├── vqa.py
│   │   ├── caption.py
│   │   └── grounding.py
│   ├── temporal/
│   │   ├── change_vqa.py
│   │   ├── change_map.py
│   │   └── alignment.py
│   ├── fusion/
│   │   └── optical_sar.py
│   └── geospatial/
│       ├── area_calculator.py
│       ├── ndvi.py
│       └── spectral_indices.py
├── adaptation/
│   ├── train.py
│   ├── eval.py
│   └── configs/
├── evaluation/
│   ├── evaluate.py
│   ├── suites/
│   │   ├── vrsbench.py
│   │   ├── rsvqa.py
│   │   └── cdvqa.py
│   └── reports/
└── docker-compose.yml
```

## Status

Scaffold only — directories initialized, no implementation yet.

## Getting Started

```bash
docker compose up --build
```

> Services are stubbed in `docker-compose.yml` — uncomment as each service is implemented.
