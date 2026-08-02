#!/usr/bin/env bash
set -euo pipefail

# Downloads the Chile OSM PBF from Geofabrik, extracts the Gran Santiago bbox,
# and places the result at /srv/arbocensus/data/osm/santiago.osm.pbf.
# Run once on the production droplet before the first `docker compose up`.
#
# Bbox covers Gran Santiago with margin for pedestrian routing around edges:
#   left=-70.90  bottom=-33.70  right=-70.40  top=-33.25

DATA_DIR="/srv/arbocensus/data/osm"
TMP_PBF="/tmp/chile-latest.osm.pbf"
OUT_PBF="$DATA_DIR/santiago.osm.pbf"
BBOX="-70.90,-33.70,-70.40,-33.25"
GEOFABRIK_URL="https://download.geofabrik.de/south-america/chile-latest.osm.pbf"

mkdir -p "$DATA_DIR"

if [ -f "$OUT_PBF" ]; then
  echo "santiago.osm.pbf already exists — skipping download."
  exit 0
fi

echo "Downloading Chile PBF (~326 MB)..."
curl -L --progress-bar "$GEOFABRIK_URL" -o "$TMP_PBF"

echo "Extracting bbox $BBOX with osmium-tool..."
docker run --rm \
  -v "$TMP_PBF":/in/chile-latest.osm.pbf:ro \
  -v "$DATA_DIR":/out \
  --entrypoint sh \
  debian:bookworm-slim -c "
    apt-get update -qq &&
    apt-get install -y --no-install-recommends osmium-tool &&
    osmium extract --bbox=$BBOX -o /out/santiago.osm.pbf /in/chile-latest.osm.pbf
  "

echo "Removing Chile PBF..."
rm -f "$TMP_PBF"

echo "Done: $OUT_PBF"
ls -lh "$OUT_PBF"
