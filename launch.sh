#!/usr/bin/env bash
#
# Arooohi — one-command launcher.
#
# Java/build: this script is a thin wrapper over the cross-platform launcher
# (launch.py). It just locates a Python 3 interpreter and runs it, passing all
# arguments straight through. See launch.py --help for the full usage.
#
#   ./launch.sh                     start backend+frontend, show your browser
#   ./launch.sh --browser chrome    force the Chromium engine (helium /opt/helium)
#   ./launch.sh --browser firefox   force the Gecko engine (Zen via flatpak)
#   ./launch.sh --no-browser        boot servers only, never open a browser
#   ./launch.sh --windowed          open the browser without fullscreen
#   ./launch.sh stop                shut down backend+frontend now
#   ./launch.sh status              show what is running
#   ./launch.sh --detect            print which browser/engine would be used

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python

exec "$PY" "$ROOT/launch.py" "$@"