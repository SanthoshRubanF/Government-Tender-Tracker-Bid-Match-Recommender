from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tender_tracker.config import load_config
from tender_tracker.db import init_db
from tender_tracker.services import sync_tenders


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a one-off tender synchronization outside Streamlit."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if the previous successful sync is still within the freshness window.",
    )
    args = parser.parse_args()

    config = load_config()
    init_db(config.database_path)
    result = sync_tenders(config, force=args.force)
    print(f"attempted={result.attempted}")
    print(f"performed={result.performed}")
    print(f"success={result.success}")
    print(f"fetched_count={result.fetched_count}")
    print(f"new_count={result.new_count}")
    print(f"updated_count={result.updated_count}")
    if result.message:
        print(f"message={result.message}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
