#!/bin/bash
# Run orchestration locally with proper environment setup

set -e

echo "🚀 Starting AI Orchestration Platform (Local)"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.example to .env and configure your API keys"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment"
    source venv/bin/activate
else
    echo "⚠️  Warning: No virtual environment found"
    echo "Consider creating one with: python -m venv venv"
fi

# Initialize database if needed
if [ ! -f orchestration.db ]; then
    echo "🗄️  Initializing database"
    python -m src.cli.init_db
fi

# Start the API server
echo "🌐 Starting API server on http://localhost:8000"
uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
