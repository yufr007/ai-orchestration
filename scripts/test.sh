#!/bin/bash
# Run tests for AI Orchestration Platform

set -e

echo "🧪 Running AI Orchestration Platform Tests"
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run ./scripts/setup.sh first"
    exit 1
fi

# Run linting
echo "🔍 Running linters..."
ruff check src/
black --check src/

# Run type checking
echo "
📝 Running type checker..."
mypy src/ --ignore-missing-imports

# Run tests
echo "
✅ Running tests..."
pytest tests/ -v --cov=src --cov-report=html --cov-report=term

echo "
✅ All tests passed!"
echo "📊 Coverage report: htmlcov/index.html"
