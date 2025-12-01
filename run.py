#!/usr/bin/env python3
"""Simple runner for stages pipeline (skeleton).

Usage:
  python run.py --list
  python run.py --init   # ensure folders exist
  python run.py --stage 01
  python run.py --run --input examples/example_bbox.json --out stages/06_output/
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(__file__)
STAGES = [
    ("01", "01_bbox_input"),
    ("02", "02_filter"),
    ("03", "03_graph"),
    ("04", "04_cluster"),
    ("05", "05_tsp"),
    ("06", "06_output"),
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


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true", help="List stages")
    p.add_argument("--init", action="store_true", help="Create stage dirs if missing")
    p.add_argument("--stage", help="Run single stage number (eg 01)")
    p.add_argument("--run", action="store_true", help="Run full pipeline")
    p.add_argument("--input", help="Path to input JSON")
    p.add_argument("--out", help="Output dir for final stage")
    return p.parse_args()


def main():
    args = parse_args()
    if args.list:
        list_stages()
        return
    if args.init:
        init_dirs()
        return
    if args.stage:
        sys.exit(run_stage(args.stage, args.input, args.out))
    if args.run:
        sys.exit(run_pipeline(args.input, args.out))
    print("No action specified. Use --list, --init, --stage N or --run")


if __name__ == '__main__':
    main()
