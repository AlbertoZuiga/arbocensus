#!/bin/bash
set -e

mkdir -p data
cd data

if [ ! -f chile-latest.osm.pbf ]; then
  echo "Descargando mapa de Chile..."
  if command -v wget >/dev/null 2>&1; then
    wget https://download.geofabrik.de/south-america/chile-latest.osm.pbf
  elif command -v curl >/dev/null 2>&1; then
    curl -L -o chile-latest.osm.pbf https://download.geofabrik.de/south-america/chile-latest.osm.pbf
  else
    echo "Error: necesitas instalar wget o curl"
    exit 1
  fi
else
  echo "Mapa ya existe, saltando descarga"
fi

cd ..

echo "Procesando OSRM..."

docker run -t -v "${PWD}/data:/data" osrm/osrm-backend \
osrm-extract -p /opt/foot.lua /data/chile-latest.osm.pbf

docker run -t -v "${PWD}/data:/data" osrm/osrm-backend \
osrm-partition /data/chile-latest.osrm

docker run -t -v "${PWD}/data:/data" osrm/osrm-backend \
osrm-customize /data/chile-latest.osrm

echo "OSRM listo"