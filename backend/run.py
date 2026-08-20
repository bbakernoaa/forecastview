"""Development server entry point.

Run from project root:
    python -m backend.run

Or directly:
    python backend/run.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so 'backend.app' resolves
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(project_root / "backend")],
    )
