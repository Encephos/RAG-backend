#!/bin/bash

# Deploy Script for RAG Backend

echo "🚀 Starting Deployment..."

# 1. Pull latest changes
echo "📥 Pulling latest code..."
git pull origin version10

# 2. Rebuild and restart the container
echo "🔄 Rebuilding 'backend' container..."
docker compose up -d --build backend

# 3. Prune old images to save space (optional)
# docker image prune -f

echo "✅ Deployment Complete! Backend is running with new code."
docker compose logs -f backend
