#!/bin/bash
# Local development setup script
set -e

echo "🚀 Setting up AI Orchestration Platform locally..."

# Check prerequisites
echo "✅ Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3.10+ is required"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js 20+ is required"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "⚠️  Docker not found (optional but recommended)"
fi

echo "✅ Prerequisites met"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📥 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install Perplexity MCP server
echo "🔧 Installing Perplexity MCP server..."
npm install -g @perplexity-ai/mcp-server

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your API keys"
fi

# Initialize database
echo "🗄️ Initializing database..."
python -m src.cli.init_db

# Run tests
echo "🧪 Running tests..."
pytest tests/ -v || echo "⚠️  Some tests failed (expected on first setup)"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Activate venv: source venv/bin/activate"
echo "  3. Run API server: uvicorn src.api.server:app --reload"
echo "  4. Or use CLI: python -m src.cli.orchestrate --help"
echo ""
