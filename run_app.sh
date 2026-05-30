#!/bin/bash
# Biometric Server Wrapper
# This script starts the Barangay Management System.

# Get the absolute path of the project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CORE_DIR="$PROJECT_DIR/core"

echo "=================================================="
echo " Starting Barangay Management System "
echo "=================================================="
echo "Project Path: $PROJECT_DIR"

# Run the Django server (0.0.0.0 = listen on all interfaces, including LAN)
./venv/bin/python manage.py runserver 0.0.0.0:8001
