#!/usr/bin/env bash
set -e
ok(){ echo "[OK] $1 : $2"; }
fail(){ echo "[FAIL] $1 : $2"; ERR=1; }
warn(){ echo "[WARN] $1 : $2"; }
ERR=0
python -m py_compile orchestrator/helpers/guardrails.py orchestrator/graph/pipeline.py orchestrator/agents/error_handler.py orchestrator/api/main.py && ok "py_compile" "true" || fail "py_compile" "exit $?"
docker compose config --quiet 2>/dev/null && ok "compose_config" "valid" || warn "compose_config" "docker not found — skip"
BASE=$(grep -oP 'QWEN_BASE_URL=\K.*' orchestrator/.env.example 2>/dev/null | tr -d '\r' | sed 's|/v1||' || echo "http://localhost:11434")
if curl -sf --max-time 2 "$BASE/api/tags" >/dev/null 2>&1; then ok "ollama" "$BASE reachable"; curl -sf --max-time 2 "$BASE/api/tags" | grep -q "qwen3.5:9b" || warn "ollama_model" "qwen3.5:9b not in /api/tags — run: ollama pull qwen3.5:9b"; else warn "ollama" "not reachable — run: ollama serve; ollama pull qwen3.5:9b"; fi
for p in "models/model1/merged_model" "models/model2/pretrained" "models/model3/checkpoints/stage1_final.pth" "models/model4/fusion/croma_base.pt"; do [ -e "$p" ] && ok "$p" "present" || warn "$p" "absent → MODEL_NOT_LINKED"; done
ffmpeg -version >/dev/null 2>&1 && ok "ffmpeg" "$(ffmpeg -version 2>&1 | head -1)" || warn "ffmpeg" "not on PATH"
[ -f tests/e2e/replay.jsonl ] && ok "cassette" "$(wc -l < tests/e2e/replay.jsonl) samples" || fail "cassette" "missing tests/e2e/replay.jsonl"
echo ""; echo "Preflight done. Fix FAILs before docker compose up."; exit $ERR
