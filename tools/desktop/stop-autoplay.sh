#!/usr/bin/env bash
# Stoppt AutoPlay (stop.sh). Für Desktop-App-Launcher.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "=== AutoPlay stoppen ==="
./stop.sh
echo ""
echo "Fertig. Fenster kann geschlossen werden."
sleep 2
