#!/usr/bin/env python3
"""Simple runner for stages pipeline (skeleton).

"""
import argparse
import os
import subprocess
import sys

# Note: do not import package modules at top-level; we'll make `src/` available
# to imports at runtime in `main()` so `python run.py` works without PYTHONPATH.

ROOT = os.path.dirname(__file__)
STAGES = [
    ("01", "bbox_input"),
    ("02", "filter"),
    ("03", "graph"),
    ("04", "cluster"),
    ("05", "tsp"),
    ("06", "output"),
]


def list_stages():
    for num, name in STAGES:
        print(f"{num} - {name}")


def init_dirs():
    for _, name in STAGES:
        path = os.path.join(ROOT, "stages", name)
        os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(ROOT, "examples"), exist_ok=True)
    print("Init: ensured stage directories exist.")


def run_stage(stage_num, input_path=None, out_dir=None):
    # Find stage by number
    match = [s for s in STAGES if s[0] == stage_num]
    if not match:
        print(f"Stage {stage_num} not found")
        return 1
    _, stage_name = match[0]
    stage_dir = os.path.join(ROOT, "stages", stage_name)
    # Look for an executable script inside stage_dir (run.py, main.py, script.sh)
    candidates = ["run.py", "main.py", "script.sh"]
    for c in candidates:
        p = os.path.join(stage_dir, c)
        if os.path.isfile(p):
            print(f"Executing {p} ...")
            res = subprocess.call([sys.executable, p, input_path or "", out_dir or ""])
            return res
    print(f"No runnable script found in {stage_dir}. (Place a run.py or main.py there.)")
    return 0


def run_pipeline(input_file=None, out_dir=None):
    print("Running pipeline (skeleton):\n\
        - stages will be attempted in order; if a stage has no script it will be skipped.")
    for num, _ in STAGES:
        print(f"-> Stage {num}")
        res = run_stage(num, input_file, out_dir)
        if res != 0:
            print(f"Stage {num} failed with code {res}. Aborting.")
            return res
    print("Pipeline finished (skeleton).")
    return 0


def main():
    # Delegate exclusively to the new package CLI
    try:
        # Ensure `src/` is on sys.path so `import arbocensus_pipeline...` works
        from importlib import import_module
        src_path = os.path.join(ROOT, 'src')
        if os.path.isdir(src_path) and src_path not in sys.path:
            sys.path.insert(0, src_path)
        cli = import_module('arbocensus_pipeline.cli')
        cli.main()
    except Exception as e:
        print('Error: could not run package CLI:', e)
        print('Ensure the repository layout is intact (a `src/arbocensus_pipeline` package).')
        sys.exit(2)


if __name__ == '__main__':
    main()
