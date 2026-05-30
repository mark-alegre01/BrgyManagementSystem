#!/bin/bash
# ==============================================================================
# Barangay Management System — Online Deployment Setup
# ==============================================================================
# This script sets up Tailscale Funnel on the Orange Pi so that the resident
# web app can be accessed from anywhere on the internet securely, without
# paying for online hosting or changing the PostgreSQL database location.
# ==============================================================================

echo "=================================================="
echo " Setting up Public Internet Access (Tailscale)    "
echo "=================================================="

# 1. Install Tailscale if not installed
if ! command -v tailscale &> /dev/null; then
    echo "[1/3] Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
else
    echo "[1/3] Tailscale is already installed. ✅"
fi

# 2. Authenticate and bring Tailscale online
echo ""
echo "[2/3] Connecting Orange Pi to Tailscale..."
echo "If you haven't logged in, it will give you a link to click."
sudo tailscale up

# 3. Enable Funnel to expose port 8001 to the public internet
echo ""
echo "[3/3] Setting up Public URL for the Resident Portal..."
echo "This will create a public HTTPS link that routes to Django on port 8001."
echo ""
echo "--------------------------------------------------"
echo " IMPORTANT: You need to run this command manually "
echo " to keep the tunnel running in the background:"
echo ""
echo "     tailscale serve --bg --set-path / http://127.0.0.1:8001"
echo "     tailscale funnel --bg 443"
echo ""
echo "--------------------------------------------------"
echo "To see your permanent public URL, run:"
echo "     tailscale status"
echo ""
echo "Your URL will look something like:"
echo "     https://orangepi.tailxxx.ts.net"
echo "=================================================="
