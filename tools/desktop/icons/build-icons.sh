#!/usr/bin/env bash
# Erzeugt .icns aus den SVG-Quellen (macOS: qlmanage + iconutil).
set -euo pipefail

ICONS_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${ICONS_DIR}/generated"
mkdir -p "$OUT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Icon-Build nur unter macOS möglich." >&2
  exit 1
fi

svg_to_png() {
  local svg=$1
  local png=$2
  local size=$3
  local tmp_dir
  tmp_dir="$(mktemp -d -t tm-icon)"
  qlmanage -t -s "$size" -o "$tmp_dir" "$svg" >/dev/null 2>&1
  local rendered="${tmp_dir}/$(basename "$svg").png"
  if [[ ! -f "$rendered" ]]; then
    echo "Icon-Rendering fehlgeschlagen: $svg" >&2
    rm -rf "$tmp_dir"
    exit 1
  fi
  sips -z "$size" "$size" "$rendered" --out "$png" >/dev/null
  rm -rf "$tmp_dir"
}

build_icns() {
  local svg=$1
  local icns=$2
  local iconset="${OUT_DIR}/$(basename "$icns" .icns).iconset"
  local master="${OUT_DIR}/$(basename "$icns" .icns)-1024.png"

  rm -rf "$iconset"
  mkdir -p "$iconset"
  svg_to_png "$svg" "$master" 1024

  sips -z 16 16 "$master" --out "${iconset}/icon_16x16.png" >/dev/null
  sips -z 32 32 "$master" --out "${iconset}/icon_16x16@2x.png" >/dev/null
  sips -z 32 32 "$master" --out "${iconset}/icon_32x32.png" >/dev/null
  sips -z 64 64 "$master" --out "${iconset}/icon_32x32@2x.png" >/dev/null
  sips -z 128 128 "$master" --out "${iconset}/icon_128x128.png" >/dev/null
  sips -z 256 256 "$master" --out "${iconset}/icon_128x128@2x.png" >/dev/null
  sips -z 256 256 "$master" --out "${iconset}/icon_256x256.png" >/dev/null
  sips -z 512 512 "$master" --out "${iconset}/icon_256x256@2x.png" >/dev/null
  sips -z 512 512 "$master" --out "${iconset}/icon_512x512.png" >/dev/null
  cp "$master" "${iconset}/icon_512x512@2x.png"

  iconutil -c icns "$iconset" -o "$icns"
  rm -rf "$iconset"
}

build_icns "${ICONS_DIR}/autoplay-start.svg" "${OUT_DIR}/autoplay-start.icns"
build_icns "${ICONS_DIR}/autoplay-stop.svg" "${OUT_DIR}/autoplay-stop.icns"

echo "${OUT_DIR}/autoplay-start.icns"
echo "${OUT_DIR}/autoplay-stop.icns"
