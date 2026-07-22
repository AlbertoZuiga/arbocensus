import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

COLUMNS = [
    "source",
    "instance",
    "n",
    "cell",
    "seed",
    "k",
    "travel_sec",
    "relleno_sec",
    "msf_k_sec",
    "relleno_msf_sec",
    "ub_k_sec",
    "relleno_ub_sec",
]


class Command(BaseCommand):
    help = (
        "Recompute the padding metric of already-published sweep CSVs against a "
        "reachable zero point. The old metric measures travel over the sum of "
        "nearest-neighbour distances, which no path can attain; this one measures it "
        "over the minimum spanning forest of k components, which a path can. MSF_k "
        "depends only on the instance and k, both present in the stored rows, so no "
        "solver or OSRM call is needed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--decomposition", type=str, required=True)
        parser.add_argument("--sweep", type=str, nargs="+", required=True)
        parser.add_argument("--out", type=str, required=True)
        parser.add_argument(
            "--anchor",
            type=str,
            help="instance_tsp_anchor CSV; adds the constructed upper-bound anchor",
        )

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        msf = self._bound_table(root / options["decomposition"], "msf_k_sec")
        anchor = (
            self._bound_table(root / options["anchor"], "ub_k_sec")
            if options["anchor"]
            else {}
        )

        rows = []
        missing = set()
        for sweep in options["sweep"]:
            path = root / sweep
            with path.open(newline="", encoding="utf-8") as handle:
                for raw in csv.DictReader(handle):
                    key = (raw["instance"], int(raw["k"]))
                    if key not in msf:
                        missing.add(key)
                        continue
                    travel = float(raw["travel_sec"])
                    rows.append(
                        {
                            "source": Path(sweep).name,
                            "instance": raw["instance"],
                            "n": raw["n"],
                            "cell": raw["cell"],
                            "seed": raw["seed"],
                            "k": raw["k"],
                            "travel_sec": raw["travel_sec"],
                            "relleno_sec": raw["relleno_sec"],
                            "msf_k_sec": round(msf[key]),
                            "relleno_msf_sec": self._relleno_msf(
                                raw, travel, msf[key], sweep
                            ),
                            "ub_k_sec": round(anchor[key]) if key in anchor else "",
                            "relleno_ub_sec": self._relleno_ub(
                                raw, travel, anchor.get(key)
                            ),
                        }
                    )

        if missing:
            raise CommandError(
                "decomposition CSV lacks MSF_k for: "
                + ", ".join(f"{i} k={k}" for i, k in sorted(missing))
            )

        out_path = root / options["out"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Re-judged {len(rows)} rows: {out_path}"))

    def _relleno_msf(self, raw, travel, msf_k, sweep):
        # The forest bound spans every node, so it stops bounding a solution that
        # abandons some of them: clamping those rows at zero would report the runs
        # that dropped trees as the ones with no padding at all.
        if int(raw["drops"] or 0):
            return ""
        if travel < msf_k - 1:
            raise CommandError(
                f"{sweep} {raw['instance']} {raw['cell']} seed={raw['seed']}: "
                f"travel {travel:.0f} below the spanning-forest bound "
                f"MSF_{raw['k']}={msf_k:.0f} — the bound or the stored travel is wrong"
            )
        return max(0, round(travel - msf_k))

    def _relleno_ub(self, raw, travel, ub_k):
        # No clamping and no abort, unlike the forest bound: UB_k is a constructed
        # solution, not a bound, so a solver run beating it is a real and reportable
        # outcome rather than an accounting error.
        if ub_k is None or int(raw["drops"] or 0):
            return ""
        return round(travel - ub_k)

    def _bound_table(self, path, column):
        with path.open(newline="", encoding="utf-8") as handle:
            return {
                (r["instance"], int(r["k"])): float(r[column])
                for r in csv.DictReader(handle)
            }
