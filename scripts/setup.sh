#!/bin/bash
# Setup script for local development

set -e

echo "=== AI Orchestration Platform Setup ==="
echo ""

# Check prerequisites
echo "Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3.10+ required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Error: Node.js 20+ required"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "Error: Git required"; exit 1; }

echo "  ✓ Python $(python3 --version)"
echo "  ✓ Node $(node --version)"
echo "  ✓ Git $(git --version)"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip >/dev/null 2>&1
pip install -r requirements.txt >/dev/null 2>&1
echo "  ✓ Python packages installed"

# Install Perplexity MCP server
echo "Installing Perplexity MCP server..."
npm install -g @perplexity-ai/mcp-server >/dev/null 2>&1
echo "  ✓ Perplexity MCP server installed"

# Setup environment file
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "  ⚠️  Please edit .env and add your API keys"
else
    echo "  ✓ .env file exists"
fi

# Initialize database
echo "Initializing database..."
python -m src.cli.init_db

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Activate venv: source venv/bin/activate"
echo "  3. Run tests: pytest"
echo "  4. Start server: uvicorn src.api.server:app --reload"
echo "  5. Or use CLI: python -m src.cli.orchestrate --help"
echo ""
