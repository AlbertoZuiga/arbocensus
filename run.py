#!/usr/bin/env python3
"""
Simple runner for stages pipeline (skeleton).
"""

import os
import sys
from importlib import import_module

ROOT = os.path.dirname(__file__)


def main():
    try:
        src_path = os.path.join(ROOT, "src")
        if os.path.isdir(src_path) and src_path not in sys.path:
            sys.path.insert(0, src_path)
        cli = import_module("arbocensus_pipeline.cli")
        cli.main()
    except (ImportError, AttributeError) as e:
        print("Error: could not run package CLI:", e)
        print(
            "Ensure the repository layout is intact (a `src/arbocensus_pipeline` package)."
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
