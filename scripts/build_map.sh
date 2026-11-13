#!/usr/bin/env bash
# Build the site's map files from Natural Earth (public domain) and vendor the map libraries.
# Usage: scripts/build_map.sh [NE_DIR]   (NE_DIR holds the .geojson files; downloaded if missing)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NE="${1:-$(mktemp -d)}"
BASE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson
for f in ne_110m_admin_0_countries ne_50m_admin_0_countries ne_10m_admin_1_states_provinces; do
  [ -f "$NE/$f.geojson" ] || curl -sSfL -o "$NE/$f.geojson" "$BASE/$f.geojson"
done
TOOLS="$(mktemp -d)"
(cd "$TOOLS" && npm init -y >/dev/null && npm install --silent mapshaper@0.6 d3-geo@3 d3-array@3 topojson-client@3)
MS="$TOOLS/node_modules/.bin/mapshaper"
mkdir -p "$ROOT/site/map" "$ROOT/site/vendor"

# World overview: countries only, small.
"$MS" -i "$NE/ne_110m_admin_0_countries.geojson" name=countries \
  -each 'iso = ISO_A2_EH' -filter-fields iso \
  -o "$ROOT/site/map/world.topo.json" format=topojson quantization=1e5 precision=0.01

# Detail: finer coastlines + first-level region borders (lines only), simplified for phones.
"$MS" -i "$NE/ne_50m_admin_0_countries.geojson" name=countries \
  -each 'iso = ISO_A2_EH' -filter-fields iso -simplify 40% keep-shapes \
  -i "$NE/ne_10m_admin_1_states_provinces.geojson" name=admin1 \
  -simplify 4% keep-shapes target=admin1 -innerlines target=admin1 \
  -o "$ROOT/site/map/detail.topo.json" format=topojson target=countries,admin1 combine-layers quantization=1e5

cp "$TOOLS/node_modules/d3-array/dist/d3-array.min.js" "$ROOT/site/vendor/"
cp "$TOOLS/node_modules/d3-geo/dist/d3-geo.min.js" "$ROOT/site/vendor/"
cp "$TOOLS/node_modules/topojson-client/dist/topojson-client.min.js" "$ROOT/site/vendor/"
cp "$TOOLS/node_modules/d3-geo/LICENSE" "$ROOT/site/vendor/LICENSE.d3-geo"
cp "$TOOLS/node_modules/d3-array/LICENSE" "$ROOT/site/vendor/LICENSE.d3-array"
cp "$TOOLS/node_modules/topojson-client/LICENSE" "$ROOT/site/vendor/LICENSE.topojson-client"
ls -la "$ROOT/site/map" "$ROOT/site/vendor"
