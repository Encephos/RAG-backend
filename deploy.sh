#!/bin/bash

# Deploy Script for RAG Backend

echo "🚀 Starting Deployment..."

# 1. Pull latest changes
echo "📥 Stashing local changes and pulling latest code..."
# Determine current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "   On branch: $BRANCH"

# Stash local changes (e.g. random edits on server) to avoid conflicts
git stash

# Pull
git pull origin $BRANCH

# 2. Rebuild and restart the container
echo "🔄 Rebuilding 'backend' container..."
docker compose up -d --build backend

# 3. Prune old images to save space (optional)
# docker image prune -f

echo "✅ Deployment Complete! Backend is running with new code."
docker compose logs -f backend
