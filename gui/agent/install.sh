#!/bin/bash
# OSONE Hive Node Installer
# Works on: Linux, macOS, Termux (Android), a-Shell (iOS)
# Does NOT require root

OSONE_URL="${OSONE_URL:-https://app.osone.org}"
HIVE_TOKEN="${HIVE_TOKEN:-}"
NODE_ID="${NODE_ID:-$(hostname 2>/dev/null || echo hive-node)}"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     OSONE Hive Node Installer        ║"
echo "╚══════════════════════════════════════╝"
echo ""

if [ -z "$HIVE_TOKEN" ]; then
  echo "[error] HIVE_TOKEN is required."
  echo "  Visit osone.org → scroll to Install → get your token"
  exit 1
fi

# ── Detect environment ────────────────────────────────────────────────────────
IS_ROOT=false
IS_TERMUX=false
IS_SYSTEMD=false
IS_MACOS=false

[ "$(id -u)" = "0" ] && IS_ROOT=true
[ -n "$TERMUX_VERSION" ] || [ -d "/data/data/com.termux" ] && IS_TERMUX=true
command -v systemctl >/dev/null 2>&1 && systemctl is-system-running >/dev/null 2>&1 && IS_SYSTEMD=true
[ "$(uname)" = "Darwin" ] && IS_MACOS=true

echo "[+] Environment detected:"
echo "    Root:    $IS_ROOT"
echo "    Termux:  $IS_TERMUX"
echo "    systemd: $IS_SYSTEMD"
echo "    macOS:   $IS_MACOS"
echo ""

# ── Install Python deps ───────────────────────────────────────────────────────
echo "[+] Installing Python dependencies..."
if $IS_TERMUX; then
  pkg install -y python curl 2>/dev/null | tail -1
  pip install websockets psutil -q
elif $IS_MACOS; then
  pip3 install websockets psutil -q 2>/dev/null || python3 -m pip install websockets psutil -q
else
  python3 -m pip install websockets psutil -q 2>/dev/null || pip3 install websockets psutil -q 2>/dev/null || true
fi

# ── Pick install dir (no root needed) ────────────────────────────────────────
if $IS_TERMUX; then
  INSTALL_DIR="$HOME/.osone"
elif $IS_ROOT; then
  INSTALL_DIR="/usr/local/bin"
else
  INSTALL_DIR="$HOME/.local/bin"
  mkdir -p "$INSTALL_DIR"
fi

echo "[+] Downloading node agent to $INSTALL_DIR..."
curl -fsSL "$OSONE_URL/agent/node.py" -o "$INSTALL_DIR/osone-node.py"
chmod +x "$INSTALL_DIR/osone-node.py"

# ── Set up persistence ────────────────────────────────────────────────────────
if $IS_TERMUX; then
  # Termux: use ~/.bashrc autostart or termux-boot
  BOOT_SCRIPT="$HOME/.osone/start.sh"
  mkdir -p "$HOME/.osone"
  cat > "$BOOT_SCRIPT" << BOOTEOF
#!/data/data/com.termux/files/usr/bin/bash
export OSONE_URL="$OSONE_URL"
export HIVE_TOKEN="$HIVE_TOKEN"
export NODE_ID="$NODE_ID"
nohup python3 $INSTALL_DIR/osone-node.py >> $HOME/.osone/node.log 2>&1 &
echo "[osone] node started (pid \$!)"
BOOTEOF
  chmod +x "$BOOT_SCRIPT"

  # Add to .bashrc if not already there
  if ! grep -q "osone" "$HOME/.bashrc" 2>/dev/null; then
    echo "" >> "$HOME/.bashrc"
    echo "# OSONE Hive Node — auto-start" >> "$HOME/.bashrc"
    echo "bash $BOOT_SCRIPT" >> "$HOME/.bashrc"
  fi

  # Try termux-boot too
  if command -v termux-boot >/dev/null 2>&1 || [ -d "$HOME/.termux/boot" ]; then
    mkdir -p "$HOME/.termux/boot"
    cp "$BOOT_SCRIPT" "$HOME/.termux/boot/osone-node.sh"
    echo "[+] termux-boot autostart configured"
  fi

  echo ""
  echo "✓ Node agent installed!"
  echo "  Starting now..."
  bash "$BOOT_SCRIPT"
  echo ""
  echo "  Log: tail -f $HOME/.osone/node.log"
  echo "  To run again: bash $BOOT_SCRIPT"

elif $IS_SYSTEMD && $IS_ROOT; then
  # Linux with systemd + root — full service
  cat > /etc/systemd/system/osone-node.service << SVCEOF
[Unit]
Description=OSONE Hive Node Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=OSONE_URL=$OSONE_URL
Environment=HIVE_TOKEN=$HIVE_TOKEN
Environment=NODE_ID=$NODE_ID
ExecStart=python3 $INSTALL_DIR/osone-node.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF
  systemctl daemon-reload
  systemctl enable osone-node
  systemctl start osone-node
  echo "✓ Node agent installed as systemd service!"
  echo "  Status: systemctl status osone-node"

elif $IS_SYSTEMD; then
  # systemd user service (no root needed)
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/osone-node.service" << SVCEOF
[Unit]
Description=OSONE Hive Node Agent
After=network.target

[Service]
Type=simple
Environment=OSONE_URL=$OSONE_URL
Environment=HIVE_TOKEN=$HIVE_TOKEN
Environment=NODE_ID=$NODE_ID
ExecStart=python3 $INSTALL_DIR/osone-node.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
SVCEOF
  systemctl --user daemon-reload
  systemctl --user enable osone-node
  systemctl --user start osone-node
  loginctl enable-linger "$USER" 2>/dev/null || true
  echo "✓ Node agent installed as user systemd service!"
  echo "  Status: systemctl --user status osone-node"

elif $IS_MACOS; then
  # macOS launchd plist
  PLIST="$HOME/Library/LaunchAgents/org.osone.node.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>org.osone.node</string>
  <key>ProgramArguments</key><array>
    <string>python3</string><string>$INSTALL_DIR/osone-node.py</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>OSONE_URL</key><string>$OSONE_URL</string>
    <key>HIVE_TOKEN</key><string>$HIVE_TOKEN</string>
    <key>NODE_ID</key><string>$NODE_ID</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.osone/node.log</string>
  <key>StandardErrorPath</key><string>$HOME/.osone/node.log</string>
</dict></plist>
PLISTEOF
  mkdir -p "$HOME/.osone"
  launchctl load "$PLIST"
  echo "✓ Node agent installed via launchd!"
  echo "  Log: tail -f $HOME/.osone/node.log"

else
  # Fallback — just run it in background with nohup
  mkdir -p "$HOME/.osone"
  OSONE_URL="$OSONE_URL" HIVE_TOKEN="$HIVE_TOKEN" NODE_ID="$NODE_ID" \
    nohup python3 "$INSTALL_DIR/osone-node.py" >> "$HOME/.osone/node.log" 2>&1 &
  echo "✓ Node agent started (pid $!)"
  echo "  Log: tail -f $HOME/.osone/node.log"
  echo "  Note: add the above nohup command to your shell profile for persistence"
fi

echo ""
echo "  Node ID:     $NODE_ID"
echo "  Commander:   $OSONE_URL"
echo "  Dashboard:   $OSONE_URL (Hive tab)"
echo ""
