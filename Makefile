.PHONY: preflight test-offline compose-check health tools eval weights report

preflight:
	@powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1

preflight-sh:
	@bash scripts/preflight.sh

test-offline:
	@pytest tests/e2e/test_replay.py -v

compose-check:
	@docker compose config --quiet && echo "compose config: valid"

health:
	@curl -sf http://localhost:8000/health | python -m json.tool

tools:
	@curl -sf http://localhost:8000/api/v1/tools | python -m json.tool | head -n 60

eval:
	@MOCK_EVAL=1 python tests/benchmarks/eval_suite.py

weights:
	@python scripts/download_weights.py --model all

weights-check:
	@python scripts/download_weights.py --check

report:
	@cat tests/benchmarks/report.md 2>/dev/null || echo "run 'make eval' first"

memory:
	@curl -sf http://localhost:8000/api/v1/memory/demo_sess?n=3 | python -m json.tool | head -n 40

metrics:
	@curl -sf http://localhost:8000/api/v1/metrics | python -m json.tool | head -n 60
