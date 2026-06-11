#!/bin/bash
# Install the firm's daemons as launchd services — MARKET-HOURS ONLY policy.
# Run once: bash ops/install-watcher.sh   (re-run to update after changes)
#
# watcher + telegram: started by calendar on weekday mornings (07:25 and
#   08:25 local — both possible Mexico City offsets of 9:25am ET across US
#   DST; the wrong-season start exits in <1s via session_should_run) and
#   self-terminate shortly after the close. Nothing runs overnight/weekends.
# heartbeat: a 5-minute cron that exits instantly when the market is closed;
#   during market hours it verifies the watcher AND IB Gateway are alive.
# Manual override anytime: ops/firm up|down|status
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS_DIR" "$ROOT/journal/logs"

# StartCalendarInterval entries: Mon-Fri at 07:25 and 08:25 local time
calendar_entries() {
  for wd in 1 2 3 4 5; do
    for hr in 7 8; do
      cat <<ENTRY
    <dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>$hr</integer><key>Minute</key><integer>25</integer></dict>
ENTRY
    done
  done
}

cat > "$AGENTS_DIR/com.trade-agent.watcher.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.trade-agent.watcher</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>$ROOT/scanner/watcher.py</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><false/>
  <key>StartCalendarInterval</key><array>
$(calendar_entries)
  </array>
  <key>StandardOutPath</key><string>$ROOT/journal/logs/watcher.log</string>
  <key>StandardErrorPath</key><string>$ROOT/journal/logs/watcher.err</string>
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
  <key>RunAtLoad</key><false/>
  <key>StartCalendarInterval</key><array>
$(calendar_entries)
  </array>
  <key>StandardOutPath</key><string>$ROOT/journal/logs/telegram.log</string>
  <key>StandardErrorPath</key><string>$ROOT/journal/logs/telegram.err</string>
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

for svc in watcher telegram heartbeat; do
  launchctl unload "$AGENTS_DIR/com.trade-agent.$svc.plist" 2>/dev/null || true
  launchctl load "$AGENTS_DIR/com.trade-agent.$svc.plist"
done

echo "installed (market-hours policy):"
launchctl list | grep com.trade-agent || true
echo "watcher+telegram start weekday mornings and exit after the close."
echo "manual control: ops/firm up | down | status"
