"""Ensure repo root is on sys.path for top-level `capabilities.*` imports."""
import sys
from pathlib import Path
# Add SATIQ repo root (parents[2] from this file) so `import capabilities.single_image...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
