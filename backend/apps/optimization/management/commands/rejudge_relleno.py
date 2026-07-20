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

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        msf = self._msf_table(root / options["decomposition"])

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

    def _msf_table(self, path):
        with path.open(newline="", encoding="utf-8") as handle:
            return {
                (r["instance"], int(r["k"])): float(r["msf_k_sec"])
                for r in csv.DictReader(handle)
            }
