#!/bin/bash
# OSONE Underling Agent Installer
# Usage: curl http://100.104.30.60:8000/agent/install.sh | OSONE_IP=100.104.30.60 bash
set -e
OSONE_IP="${OSONE_IP:-100.104.30.60}"
echo "======================================"
echo "  OSONE Underling Agent Installer"
echo "  Commander: $OSONE_IP"
echo "======================================"
if command -v apt &>/dev/null; then apt-get install -y python3 python3-pip curl 2>/dev/null; fi
if command -v pacman &>/dev/null; then pacman -S --noconfirm python python-pip curl 2>/dev/null; fi
pip3 install psutil --break-system-packages 2>/dev/null || pip3 install psutil
if ! command -v tailscale &>/dev/null; then
    echo "[*] Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    echo "[!] Run: tailscale up --authkey=<your-reusable-key>"
fi
echo "[*] Downloading skyd-agent..."
curl -fsSL http://$OSONE_IP:8000/agent/skyd-agent.py -o /usr/local/bin/skyd-agent.py
chmod +x /usr/local/bin/skyd-agent.py
cat > /etc/systemd/system/skyd-agent.service << SVCEOF
[Unit]
Description=OSONE Underling Agent
After=network.target tailscaled.service

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/skyd-agent.py
Restart=always
RestartSec=10
Environment=OSONE_IP=$OSONE_IP
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF
systemctl daemon-reload
systemctl enable skyd-agent
systemctl start skyd-agent
echo "[OK] Underling agent running — node will appear in OSONE Hive"
