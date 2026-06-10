#!/bin/bash
# Install the watcher daemon + heartbeat check as launchd services.
# Run once: bash ops/install-watcher.sh   (re-run to update after changes)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS_DIR" "$ROOT/journal/logs"

cat > "$AGENTS_DIR/com.trade-agent.watcher.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.trade-agent.watcher</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$ROOT/scanner/watcher.py</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/journal/logs/watcher.log</string>
  <key>StandardErrorPath</key><string>$ROOT/journal/logs/watcher.err</string>
</dict></plist>
EOF

cat > "$AGENTS_DIR/com.trade-agent.heartbeat.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.trade-agent.heartbeat</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$ROOT/scanner/heartbeat_check.py</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartInterval</key><integer>300</integer>
  <key>StandardOutPath</key><string>$ROOT/journal/logs/heartbeat.log</string>
  <key>StandardErrorPath</key><string>$ROOT/journal/logs/heartbeat.err</string>
</dict></plist>
EOF

cat > "$AGENTS_DIR/com.trade-agent.telegram.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.trade-agent.telegram</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$ROOT/scanner/telegram_bot.py</string><string>daemon</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/journal/logs/telegram.log</string>
  <key>StandardErrorPath</key><string>$ROOT/journal/logs/telegram.err</string>
</dict></plist>
EOF

launchctl unload "$AGENTS_DIR/com.trade-agent.telegram.plist" 2>/dev/null || true
launchctl unload "$AGENTS_DIR/com.trade-agent.watcher.plist" 2>/dev/null || true
launchctl unload "$AGENTS_DIR/com.trade-agent.heartbeat.plist" 2>/dev/null || true
launchctl load "$AGENTS_DIR/com.trade-agent.watcher.plist"
launchctl load "$AGENTS_DIR/com.trade-agent.heartbeat.plist"
launchctl load "$AGENTS_DIR/com.trade-agent.telegram.plist"

echo "installed + started:"
launchctl list | grep com.trade-agent || true
echo "logs: journal/logs/watcher.log | stop: launchctl unload ~/Library/LaunchAgents/com.trade-agent.*.plist"
