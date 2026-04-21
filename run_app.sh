#!/bin/bash
# ZK9500 Biometric Server Wrapper
# This script ensures the biometric scanner drivers are found correctly.

# Get the absolute path of the project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CORE_DIR="$PROJECT_DIR/core"

# Library path is now handled internally by zk_sdk.py
# export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$CORE_DIR"

echo "=================================================="
echo " Starting Barangay Management System with ZK9500 "
echo "=================================================="
echo "Library Path: $CORE_DIR"

# Check if libraries are present
if [ ! -f "$CORE_DIR/libzkfp.so" ]; then
    echo "[!] Warning: libzkfp.so not found in $CORE_DIR"
fi

# Run the Django server
./venv/bin/python manage.py runserver 127.0.0.1:8001
