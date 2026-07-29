#!/usr/bin/env bash
# Installiert AutoPlay Start-/Stop-Apps auf dem macOS-Desktop.
# Eigene Namen (AutoPlay.app) — überschreibt nicht Theatermaschine.app vom Burgtheater-Projekt.
#
#   ./tools/desktop/install-desktop-apps.sh
#   make desktop-install

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DESKTOP="${HOME}/Desktop"
START_SH="${ROOT}/tools/desktop/start-autoplay.sh"
STOP_SH="${ROOT}/tools/desktop/stop-autoplay.sh"
ICONS_BUILD="${ROOT}/tools/desktop/icons/build-icons.sh"
START_APP="${DESKTOP}/AutoPlay.app"
STOP_APP="${DESKTOP}/AutoPlay Stop.app"

chmod +x "$START_SH" "$STOP_SH" "$ICONS_BUILD" "$0"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Desktop-Apps sind nur für macOS vorgesehen." >&2
  exit 1
fi

compile_terminal_app() {
  local app_path=$1
  local script_path=$2
  local title=$3
  local tmp
  tmp="$(mktemp -t autoplay-launcher).applescript"
  cat >"$tmp" <<EOF
on run
  set shPath to "${script_path}"
  set winTitle to "${title}"
  tell application "Terminal"
    activate
    do script "clear; printf '\\\\033]0;%s\\\\007' " & quoted form of winTitle & "; exec " & quoted form of shPath
  end tell
end run
EOF
  rm -rf "$app_path"
  osacompile -o "$app_path" "$tmp"
  rm -f "$tmp"
}

apply_app_icon() {
  local app_path=$1
  local icns_path=$2
  if [[ ! -f "$icns_path" ]]; then
    return 0
  fi
  cp "$icns_path" "$app_path/Contents/Resources/applet.icns"
  touch "$app_path"
}

ICON_OUTPUT="$("$ICONS_BUILD")"
START_ICNS="$(printf '%s\n' "$ICON_OUTPUT" | sed -n '1p')"
STOP_ICNS="$(printf '%s\n' "$ICON_OUTPUT" | sed -n '2p')"

compile_terminal_app "$START_APP" "$START_SH" "AutoPlay"
compile_terminal_app "$STOP_APP" "$STOP_SH" "AutoPlay Stop"

apply_app_icon "$START_APP" "$START_ICNS"
apply_app_icon "$STOP_APP" "$STOP_ICNS"

echo "Installiert:"
echo "  $START_APP"
echo "  $STOP_APP"
echo ""
echo "Doppelklick auf „AutoPlay“ startet make run und öffnet http://localhost:3004/productions"
echo "Doppelklick auf „AutoPlay Stop“ beendet den Stack."
echo ""
echo "Hinweis: Burgtheater-Launcher heißen „Theatermaschine“ — dort separat mit make desktop-install installieren."
