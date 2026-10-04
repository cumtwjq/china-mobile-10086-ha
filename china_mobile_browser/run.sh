#!/usr/bin/env bash
set -euo pipefail

mkdir -p /data/browser_profiles /share/china_mobile_10086/accounts \
  /share/china_mobile_10086/commands /share/china_mobile_10086/responses
chmod 700 /data/browser_profiles

Xvfb :99 -screen 0 1280x900x24 -nolisten tcp &
sleep 1
x11vnc -display :99 -localhost -forever -shared -rfbport 5900 -nopw -quiet &
websockify --web=/usr/share/novnc 0.0.0.0:6080 localhost:5900 &

exec python /app/worker.py
