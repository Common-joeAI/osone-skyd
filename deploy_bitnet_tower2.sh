#!/bin/bash
# deploy_bitnet_tower2.sh
# Installs and starts the BitNet b1.58 secondary agent on Tower2
# Run as: bash deploy_bitnet_tower2.sh

set -e

OSONE_DIR="/mnt/user/Data/osone"
SRC_DIR="$OSONE_DIR/src"
MODEL_DIR="$OSONE_DIR/models"
LLAMA_DIR="$OSONE_DIR/llama.cpp"

echo "══════════════════════════════════════════"
echo "  skyd BitNet Secondary Agent — Tower2"
echo "══════════════════════════════════════════"

# 1. Pull latest skyd source
echo "[1/5] Pulling latest skyd source..."
cd "$OSONE_DIR"
git pull origin main
echo "      ✅ Source updated"

# 2. Download BitNet GGUF model if not present
echo "[2/5] Checking BitNet model..."
mkdir -p "$MODEL_DIR"
MODEL_PATH="$MODEL_DIR/bitnet-b1.58-2B-4T.gguf"

if [ ! -f "$MODEL_PATH" ]; then
    echo "      Downloading BitNet b1.58-2B-4T GGUF (~1.1GB)..."
    curl -L --progress-bar \
        "https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf/resolve/main/ggml-model-i2_s.gguf" \
        -o "$MODEL_PATH"
    echo "      ✅ Model saved to $MODEL_PATH"
else
    echo "      ✅ Model already present ($(du -sh "$MODEL_PATH" | cut -f1))"
fi

# 3. Verify llama.cpp server binary exists
echo "[3/5] Checking llama.cpp server..."
if [ ! -f "$LLAMA_DIR/llama-server" ]; then
    echo "      Building llama.cpp (CPU-only)..."
    cd "$LLAMA_DIR"
    cmake -B build -DLLAMA_CUDA=OFF -DLLAMA_METAL=OFF 2>&1 | tail -3
    cmake --build build --config Release -j$(nproc) 2>&1 | tail -3
    cp build/bin/llama-server "$LLAMA_DIR/llama-server"
    echo "      ✅ llama-server built"
else
    echo "      ✅ llama-server present"
fi

# 4. Install systemd service for BitNet
echo "[4/5] Installing BitNet systemd service..."
cat > /etc/systemd/system/skyd-bitnet.service << 'SERVICE'
[Unit]
Description=skyd BitNet Secondary Agent (CPU inference)
After=network.target skyd.service
PartOf=skyd.service

[Service]
Type=simple
Restart=always
RestartSec=5
ExecStart=/mnt/user/Data/osone/llama.cpp/llama-server \
    -m /mnt/user/Data/osone/models/bitnet-b1.58-2B-4T.gguf \
    --host 127.0.0.1 \
    --port 8081 \
    -c 2048 \
    -t 8 \
    --no-mmap \
    -ngl 0 \
    --log-disable
StandardOutput=journal
StandardError=journal
SyslogIdentifier=skyd-bitnet

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable skyd-bitnet
systemctl restart skyd-bitnet
echo "      ✅ skyd-bitnet service started"

# 5. Test the endpoint
echo "[5/5] Testing BitNet endpoint..."
sleep 5

HTTP=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8081/health" || echo "000")
if [ "$HTTP" = "200" ]; then
    echo "      ✅ BitNet API responding on port 8081"
else
    echo "      ⚠️  BitNet not yet ready (HTTP $HTTP) — check: journalctl -u skyd-bitnet -f"
fi

echo ""
echo "══════════════════════════════════════════"
echo "  BitNet Agent Active:"
echo "    • API:   http://127.0.0.1:8081"
echo "    • Model: BitNet b1.58-2B-4T (CPU)"
echo "    • Roles: Router / Monitor / SkyLang / Media Triage"
echo "  Main LLM stays on RTX 4060 (port 8080)"
echo "══════════════════════════════════════════"
