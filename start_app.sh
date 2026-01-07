#!/bin/bash

# Kill background processes on exit
trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

echo "Starting Backend (FastAPI)..."
python3 -m uvicorn api:app --port 8000 --reload &
BACKEND_PID=$!

echo "Starting Frontend (Next.js)..."
cd web
npm install
npm run dev -- -p 3001 &
FRONTEND_PID=$!

echo "=================================================="
echo "Simulator is ready!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3001"
echo "=================================================="

wait $BACKEND_PID $FRONTEND_PID
