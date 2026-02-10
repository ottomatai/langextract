from __future__ import annotations

import os
import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SERVICE_ROOT) not in sys.path:
  sys.path.insert(0, str(SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("SERVICE_API_KEY", "test-service-key")
os.environ.setdefault("LANGEXTRACT_API_KEY", "test-langextract-key")
