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

# Run the Django server
./venv/bin/python manage.py runserver 127.0.0.1:8001
