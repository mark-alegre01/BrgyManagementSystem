#!/bin/bash
# ==============================================================================
# Full Reinstallation Script for Barangay Management System (Orange Pi)
# ==============================================================================

if [ "$EUID" -ne 0 ]; then
  echo "Please run this script with sudo: sudo ./orange_pi_reinstall.sh"
  exit
fi

# Determine the actual non-root user who ran sudo
ACTUAL_USER="${SUDO_USER:-root}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================="
echo " Starting Full Reinstallation & Setup"
echo " User: $ACTUAL_USER"
echo " Project Directory: $PROJECT_DIR"
echo "================================================="

# 1. Update system and install all necessary dependencies
echo -e "\n[1/5] Installing system dependencies..."
apt-get update
apt-get upgrade -y
apt-get install -y python3-venv python3-pip python3-dev libpq-dev postgresql postgresql-contrib network-manager hostapd dnsmasq iptables-persistent git curl

# 2. Setup PostgreSQL Database
echo -e "\n[2/5] Setting up PostgreSQL Database..."
# Start PostgreSQL service if not running
systemctl start postgresql
systemctl enable postgresql
sleep 2

sudo -u postgres psql -c "CREATE DATABASE brgy_db;" || echo "Database brgy_db already exists or error."
sudo -u postgres psql -c "CREATE USER brgy_user WITH PASSWORD 'admin123';" || echo "User brgy_user already exists or error."
sudo -u postgres psql -c "ALTER ROLE brgy_user SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE brgy_user SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE brgy_user SET timezone TO 'UTC';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE brgy_db TO brgy_user;"
sudo -u postgres psql -c "ALTER DATABASE brgy_db OWNER TO brgy_user;"

# 3. Setup Python Virtual Environment & Install Django Requirements
echo -e "\n[3/5] Setting up Python Virtual Environment & Django..."
sudo -u $ACTUAL_USER bash -c "cd '$PROJECT_DIR' && python3 -m venv venv"
sudo -u $ACTUAL_USER bash -c "cd '$PROJECT_DIR' && source venv/bin/activate && pip install -r requirements.txt"
sudo -u $ACTUAL_USER bash -c "cd '$PROJECT_DIR' && source venv/bin/activate && python manage.py migrate"

# 4. Setup Hotspot & Permanent Network Fix
echo -e "\n[4/5] Setting up Hotspot and Network Routing..."
if [ -f "$PROJECT_DIR/fix_hotspot.sh" ]; then
    chmod +x "$PROJECT_DIR/fix_hotspot.sh"
    bash "$PROJECT_DIR/fix_hotspot.sh"
else
    echo "Warning: fix_hotspot.sh not found in $PROJECT_DIR"
fi

# 5. Setup Autostart for Django Server
echo -e "\n[5/5] Setting up Django Autostart..."
if [ -f "$PROJECT_DIR/setup_autostart.sh" ]; then
    chmod +x "$PROJECT_DIR/setup_autostart.sh"
    bash "$PROJECT_DIR/setup_autostart.sh"
else
    echo "Warning: setup_autostart.sh not found in $PROJECT_DIR"
fi

echo -e "\n================================================="
echo " SUCCESS! The system is fully reinstalled."
echo " Please reboot the Orange Pi now: sudo reboot"
echo "================================================="
