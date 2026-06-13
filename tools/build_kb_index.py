#!/usr/bin/env python3
"""Pre-build the FAISS KB index and save it to disk.
 
Run this script once during CI/CD or Docker image build so that the FastAPI
app never has to pay the embedding cost at cold-start time:
 
    python build_kb_index.py [--index-path data/kb_index]
 
The script is idempotent: pass --force to always rebuild even when the index
already exists on disk.
 
Exit codes
----------
0  success
1  failure (details printed to stderr)
"""
from __future__ import annotations
 
import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Make the backend package importable and load its .env, so this script can run
# standalone (e.g. `python tools/build_kb_index.py`) without manual env juggling.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if _BACKEND_DIR.is_dir() and str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND_DIR / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
logger = logging.getLogger("build_kb_index")
 
 
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pre-build FAISS KB index")
    p.add_argument(
        "--index-path",
        default=os.environ.get("KB_INDEX_PATH", str(_BACKEND_DIR / "data" / "kb_index")),
        help="Directory where the FAISS index will be written "
        "(default: backend/data/kb_index)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("KB_FORCE_REBUILD", "0") == "1",
        help="Rebuild even if the index already exists",
    )
    return p.parse_args()
 
 
def main() -> int:
    args = parse_args()
    index_dir = Path(args.index_path)
 
    # Expose as env-vars so the agent module respects the same paths.
    os.environ["KB_INDEX_PATH"] = str(index_dir)
    if args.force:
        os.environ["KB_FORCE_REBUILD"] = "1"
 
    # Check whether we can skip the build.
    index_faiss = index_dir / "index.faiss"
    index_pkl = index_dir / "index.pkl"
    if not args.force and index_faiss.is_file() and index_pkl.is_file():
        logger.info("Index already exists at %s — skipping (use --force to rebuild)", index_dir)
        return 0
 
    logger.info("Starting KB index build → %s", index_dir)
    t0 = time.perf_counter()
 
    try:
        # Import here so the module picks up the env-vars set above.
        from agent.kb import build_index  # noqa: PLC0415
 
        store = build_index()
        elapsed = time.perf_counter() - t0
 
        # Quick sanity check.
        results = store.similarity_search("allergen gluten", k=1)
        if not results:
            logger.warning("Sanity search returned no results — index may be empty")
 
        logger.info(
            "Index built and saved in %.2fs  (%s)",
            elapsed,
            index_dir,
        )
        return 0
 
    except Exception:
        logger.exception("Index build failed after %.2fs", time.perf_counter() - t0)
        return 1
 
 
if __name__ == "__main__":
    sys.exit(main())