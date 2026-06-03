#!/bin/bash
# ==============================================================================
# Barangay Management System — Auto-start Setup
# ==============================================================================
# Run this script ONCE on the Orange Pi to make Django start automatically
# every time the Orange Pi is powered on.
# Usage: sudo ./setup_autostart.sh
# ==============================================================================

# Make sure we are running as root
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Please run this script with sudo:"
    echo "        sudo ./setup_autostart.sh"
    exit 1
fi

# Detect the actual user (not root, since we use sudo)
ACTUAL_USER="${SUDO_USER:-admin}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo " Barangay System — Auto-start Setup              "
echo "=================================================="
echo " User           : $ACTUAL_USER"
echo " Project Path   : $PROJECT_DIR"
echo "=================================================="

# Make run_app.sh executable
chmod +x "$PROJECT_DIR/run_app.sh"

# Create the systemd service file
SERVICE_FILE="/etc/systemd/system/brgy-system.service"

echo "[1/4] Creating systemd service at $SERVICE_FILE..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Barangay Management System (Django)
Documentation=https://github.com/mark-alegre01/BrgyManagementSystem

# Wait for the network AND PostgreSQL before starting Django
After=network-online.target postgresql.service
Wants=network-online.target postgresql.service

[Service]
Type=simple
User=$ACTUAL_USER

# Project directory
WorkingDirectory=$PROJECT_DIR

# Start the Django app
ExecStart=$PROJECT_DIR/run_app.sh

# If Django crashes, wait 5 seconds then restart automatically
Restart=on-failure
RestartSec=5

# Log Django output to journald (view logs with: journalctl -u brgy-system -f)
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "    ✅ Service file created."

# Reload systemd to pick up the new service file
echo "[2/4] Reloading systemd daemon..."
systemctl daemon-reload
echo "    ✅ Done."

# Enable the service to start automatically on every boot
echo "[3/4] Enabling service to start on boot..."
systemctl enable brgy-system.service
echo "    ✅ Enabled."

# Start the service right now (don't wait for next reboot)
echo "[4/4] Starting the service now..."
systemctl start brgy-system.service
sleep 2

# Show the status
echo ""
echo "=================================================="
STATUS=$(systemctl is-active brgy-system.service)
if [ "$STATUS" = "active" ]; then
    echo " ✅ SUCCESS! Django is running and will auto-start on every boot."
else
    echo " ❌ WARNING: Service did not start correctly. Check logs below:"
    journalctl -u brgy-system.service -n 20 --no-pager
fi
echo "=================================================="
echo ""
echo " Useful commands:"
echo "   View live logs : sudo journalctl -u brgy-system -f"
echo "   Check status   : sudo systemctl status brgy-system"
echo "   Stop server    : sudo systemctl stop brgy-system"
echo "   Restart server : sudo systemctl restart brgy-system"
echo "   Disable autostart: sudo systemctl disable brgy-system"
echo "=================================================="
