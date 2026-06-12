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
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>60</integer>
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
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>60</integer>
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

# Archive any existing log files BEFORE loading. Root cause of the
# 2026-06-11 EX_CONFIG/78 outage: launchd opens Standard{Out,Error}Path
# with its own TCC identity before exec; a log file created by another
# process inside ~/Documents (com.apple.provenance, no com.apple.macl
# grant) gets DENIED, the spawn stub dies at init in ~13ms, and the job
# never runs — with empty logs, invisibly. Files launchd creates itself
# carry the macl grant and keep working.
STAMP=$(date +%Y%m%d-%H%M%S)
for f in watcher telegram heartbeat; do
  for ext in log err; do
    if [ -s "$ROOT/journal/logs/$f.$ext" ]; then
      mv "$ROOT/journal/logs/$f.$ext" "$ROOT/journal/logs/$f.$ext.$STAMP"
    else
      rm -f "$ROOT/journal/logs/$f.$ext"
    fi
  done
done

for svc in watcher telegram heartbeat; do
  launchctl bootout "gui/$(id -u)/com.trade-agent.$svc" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$AGENTS_DIR/com.trade-agent.$svc.plist"
done

echo "installed (market-hours policy):"
launchctl list | grep com.trade-agent || true
echo "watcher+telegram start weekday mornings, exit after the close, and"
echo "are auto-restarted by launchd if they CRASH (clean exits stay down)."
echo "manual control: ops/firm up | down | status"

# ── TCC self-test ───────────────────────────────────────────────────
# macOS denies launchd agents access to ~/Documents until the interpreter
# is granted Full Disk Access (2026-06-12: every job died at spawn with
# EX_CONFIG/78 and empty logs — invisible without this probe). Run the
# real python binary under launchd and try to read the repo.
PROBE_LABEL="com.trade-agent.tcc-probe"
PROBE_PLIST="/tmp/$PROBE_LABEL.plist"
PROBE_OUT="/tmp/$PROBE_LABEL.out"
rm -f "$PROBE_OUT"
cat > "$PROBE_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$PROBE_LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$PY</string><string>-c</string>
    <string>import os; os.listdir("$ROOT"); open("$PROBE_OUT","w").write("ok")</string>
  </array>
  <key>RunAtLoad</key><true/>
</dict></plist>
EOF
launchctl unload "$PROBE_PLIST" 2>/dev/null || true
launchctl load "$PROBE_PLIST"
sleep 3
launchctl unload "$PROBE_PLIST" 2>/dev/null || true
rm -f "$PROBE_PLIST"
if [ -f "$PROBE_OUT" ]; then
  rm -f "$PROBE_OUT"
  echo "TCC self-test: OK — launchd jobs can read the repo."
else
  REAL_PY="$(readlink -f "$PY")"
  cat <<MSG

╔═══════════════════════════════════════════════════════════════════╗
║  TCC self-test FAILED — launchd jobs CANNOT read ~/Documents.      ║
║  Every daemon will die at spawn (exit 78, empty logs).             ║
║                                                                    ║
║  FIX (one-time, human-only):                                       ║
║    System Settings -> Privacy & Security -> Full Disk Access      ║
║    -> '+' -> add this binary (Cmd+Shift+G to paste the path):      ║
║      $REAL_PY
║    Then re-run: bash ops/install-watcher.sh                        ║
╚═══════════════════════════════════════════════════════════════════╝
MSG
fi
