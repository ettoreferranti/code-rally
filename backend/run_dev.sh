#!/bin/bash
# Development server startup script for CodeRally backend

# Exit on error
set -e

echo "Starting CodeRally Development Server..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "Virtual environment created."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "Starting server..."
echo "API will be available at: http://localhost:8000"
echo "API docs will be available at: http://localhost:8000/docs"

# Detect the LAN IP of the interface used for the default route
DEFAULT_IFACE=$(route -n get default 2>/dev/null | awk '/interface:/ {print $2}')
if [ -n "$DEFAULT_IFACE" ]; then
    LAN_IP=$(ipconfig getifaddr "$DEFAULT_IFACE" 2>/dev/null || true)
    if [ -n "$LAN_IP" ]; then
        echo "LAN (share with other devices on this Wi-Fi): http://${LAN_IP}:8000"
    fi
fi

echo "Press Ctrl+C to stop the server"
echo ""

# Run the server with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
