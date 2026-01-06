#!/bin/bash
# Setup script for AI Orchestration Platform

set -e

echo "🚀 Setting up AI Orchestration Platform..."
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d" " -f2 | cut -d"." -f1,2)
echo "✅ Python $PYTHON_VERSION found"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 20+"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "✅ Node.js $NODE_VERSION found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "
📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo "
📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Perplexity MCP server
echo "
🔧 Installing Perplexity MCP server..."
npm install -g @perplexity-ai/mcp-server

# Setup environment file
if [ ! -f ".env" ]; then
    echo "
⚙️  Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env created - please edit with your API keys"
else
    echo "
✅ .env file already exists"
fi

# Initialize database
echo "
💾 Initializing database..."
python -m src.cli.init_db init

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Activate venv: source venv/bin/activate"
echo "  3. Test setup: python -m src.tools.test_mcp"
echo "  4. Run orchestration: python -m src.cli.orchestrate --help"
echo ""
