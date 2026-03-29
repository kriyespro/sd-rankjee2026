#!/bin/bash

# One-Click SkillLoop Docker Deployer
echo "🚀 Starting SkillLoop One-Click Deployment..."

# 1. Stop existing containers
echo "Stopping old containers..."
docker compose down

# 2. Build and Start containers in background
echo "Building and starting containers..."
docker compose up --build -d

# 3. Wait for database to initialize
echo "Waiting for database to settle..."
sleep 5

# 4. Check status
docker compose ps

echo "✅ Deployment Successful!"
echo "📍 Access your app at: http://localhost:8000"
echo "🛠 Admin at: http://localhost:8000/sd/"
