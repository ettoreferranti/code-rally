#!/bin/bash
# Development server startup script for CodeRally (Backend + Frontend)

# Exit on error
set -e

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting CodeRally Development Environment...${NC}"
echo ""

# Store PIDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"

    if [ ! -z "$BACKEND_PID" ]; then
        echo "Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
    fi

    if [ ! -z "$FRONTEND_PID" ]; then
        echo "Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
    fi

    echo -e "${GREEN}Servers stopped. Goodbye!${NC}"
    exit 0
}

# Set up trap for Ctrl+C
trap cleanup SIGINT SIGTERM

# ==================== BACKEND SETUP ====================
echo -e "${BLUE}[Backend]${NC} Setting up backend server..."

cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo -e "${BLUE}[Backend]${NC} Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Start backend server in background
echo -e "${BLUE}[Backend]${NC} Starting uvicorn server on port 8000..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd ..

# ==================== FRONTEND SETUP ====================
echo -e "${BLUE}[Frontend]${NC} Setting up frontend server..."

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}node_modules not found. Installing dependencies...${NC}"
    npm install
fi

# Start frontend server in foreground
echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  CodeRally Development Ready!${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "${BLUE}API Docs:${NC} http://localhost:8000/docs"
echo -e "${BLUE}Frontend:${NC} http://localhost:5173"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo ""

npm run dev &
FRONTEND_PID=$!

# Wait for frontend to finish (or Ctrl+C)
wait $FRONTEND_PID
