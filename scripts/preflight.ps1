# Preflight — fail-fast checks for dev friend's first run (no docker up needed)
param([switch]$Json)
$err=0; $out=@{}
function ok($k,$v){ $out[$k]=$v; if($Json){} else { Write-Host "[OK] $k : $v" -ForegroundColor Green } }
function fail($k,$v){ $out[$k]="FAIL: $v"; $err=1; if($Json){} else { Write-Host "[FAIL] $k : $v" -ForegroundColor Red } }
function warn($k,$v){ $out[$k]="WARN: $v"; if($Json){} else { Write-Host "[WARN] $k : $v" -ForegroundColor Yellow } }

# 1. python .venv + py_compile
try { python -m py_compile orchestrator\helpers\guardrails.py orchestrator\graph\pipeline.py orchestrator\agents\error_handler.py orchestrator\api\main.py 2>&1 | Out-Null; if($LASTEXITCODE -eq 0){ ok "py_compile" "true" } else { fail "py_compile" "exit $LASTEXITCODE" } } catch { fail "py_compile" $_.Exception.Message }
# 2. compose config
try { docker compose config --quiet 2>&1 | Out-Null; if($LASTEXITCODE -eq 0){ ok "compose_config" "valid" } else { warn "compose_config" "docker compose config failed" } } catch { warn "compose_config" "docker not found - skip" }
# 3. Ollama probe
try {
  $base=(Get-Content orchestrator\.env.example -ErrorAction SilentlyContinue | Select-String "QWEN_BASE_URL" | Select-Object -First 1).ToString().Split("=")[1].Trim().Replace("/v1","")
  if(-not $base){ $base="http://localhost:11434" }
  $r=Invoke-WebRequest -Uri "$base/api/tags" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
  if($r.StatusCode -eq 200){ ok "ollama" "$base reachable"; if($r.Content -notmatch "qwen3.5:9b"){ warn "ollama_model" "qwen3.5:9b not in api/tags - run: ollama pull qwen3.5:9b" } } else { fail "ollama" "status $($r.StatusCode)" }
} catch { warn "ollama" "not reachable - run: ollama serve; ollama pull qwen3.5:9b" }
# 4. weights presence (warn only — pipeline fails closed MODEL_NOT_LINKED if absent)
$checks=@(
  @{name="model1_ckpt"; path="models\model1\merged_model"},
  @{name="model2_ckpt"; path="models\model2\pretrained"},
  @{name="model3_ckpt"; path="models\model3\checkpoints\stage1_final.pth"},
  @{name="model4_ckpt"; path="models\model4\fusion\croma_base.pt"}
)
foreach($c in $checks){ if(Test-Path $c.path){ ok $c.name "present" } else { warn $c.name "absent - MODEL_NOT_LINKED (see README Weights)" } }
# 5. ffmpeg
try { $fv=& ffmpeg -version 2>&1 | Select-Object -First 1; if($LASTEXITCODE -eq 0){ ok "ffmpeg" "$fv" } else { warn "ffmpeg" "not on PATH - crop_bbox will fail" } } catch { warn "ffmpeg" "not on PATH" }
# 6. cassette sanity
try { $n=(Get-Content tests\e2e\replay.jsonl | Measure-Object -Line).Lines; ok "cassette" "$n samples" } catch { fail "cassette" $_.Exception.Message }

if($Json){ $out | ConvertTo-Json -Depth 3; exit $err } else { Write-Host "`nPreflight done. Fix FAILs before docker compose up." -ForegroundColor Cyan; exit $err }
