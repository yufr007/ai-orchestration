#!/bin/bash
# Azure deployment script
set -e

echo "🚀 Deploying AI Orchestration Platform to Azure..."

# Configuration
RESOURCE_GROUP="ai-orchestration-rg"
LOCATION="australiaeast"
CONTAINER_REGISTRY="aiorchestration"
APP_NAME="ai-orchestration-app"
DB_SERVER_NAME="ai-orchestration-db"

# Login to Azure
echo "🔐 Logging into Azure..."
az login

# Create resource group
echo "📦 Creating resource group..."
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create container registry
echo "🐳 Creating container registry..."
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $CONTAINER_REGISTRY \
  --sku Basic \
  --admin-enabled true

# Build and push Docker image
echo "🏗️ Building Docker image..."
az acr build \
  --registry $CONTAINER_REGISTRY \
  --image ai-orchestration:latest \
  --image ai-orchestration:$(git rev-parse --short HEAD) \
  --file Dockerfile \
  .

# Create PostgreSQL server
echo "🗄️ Creating PostgreSQL server..."
az postgres flexible-server create \
  --resource-group $RESOURCE_GROUP \
  --name $DB_SERVER_NAME \
  --location $LOCATION \
  --admin-user orchestration \
  --admin-password "$(openssl rand -base64 24)" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16

# Configure firewall
echo "🔥 Configuring firewall..."
az postgres flexible-server firewall-rule create \
  --resource-group $RESOURCE_GROUP \
  --name $DB_SERVER_NAME \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Create database
echo "📊 Creating database..."
az postgres flexible-server db create \
  --resource-group $RESOURCE_GROUP \
  --server-name $DB_SERVER_NAME \
  --database-name orchestration

# Create Container App
echo "📱 Creating Container App..."
az containerapp create \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --image $CONTAINER_REGISTRY.azurecr.io/ai-orchestration:latest \
  --registry-server $CONTAINER_REGISTRY.azurecr.io \
  --environment $APP_NAME-env \
  --ingress external \
  --target-port 8000 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --env-vars \
    ENVIRONMENT=production \
    DATABASE_URL=secretref:database-url \
    PERPLEXITY_API_KEY=secretref:perplexity-key \
    ANTHROPIC_API_KEY=secretref:anthropic-key \
    GITHUB_TOKEN=secretref:github-token

echo "✅ Deployment complete!"
echo "🌐 Application URL: https://$APP_NAME.azurecontainerapps.io"
