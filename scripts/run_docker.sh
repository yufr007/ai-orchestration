#!/bin/bash
# Run orchestration using Docker Compose

set -e

echo "🐳 Starting AI Orchestration Platform (Docker)"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.example to .env and configure your API keys"
    exit 1
fi

# Build and start services
echo "🏗️  Building Docker images"
docker-compose build

echo "🚀 Starting services"
docker-compose up -d

echo "✅ Services started!"
echo ""
echo "📊 Service URLs:"
echo "  - API Server: http://localhost:8000"
echo "  - Health Check: http://localhost:8000/health"
echo "  - PostgreSQL: localhost:5432"
echo ""
echo "📝 View logs with: docker-compose logs -f orchestration"
echo "🛑 Stop services with: docker-compose down"
