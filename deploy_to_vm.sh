#!/bin/bash
# Quick deployment script for Compute Engine VM
# Run this from your local machine

set -e

echo "🚀 Deploying TrendVision to Compute Engine VM..."
echo "================================================"

# Configuration
PROJECT_ID="trendvision-471404"
INSTANCE_NAME="instance-20250922-072947"
ZONE="asia-south1-b"
APP_DIR="/opt/trendvision"

echo "📋 Configuration:"
echo "  Project: $PROJECT_ID"
echo "  Instance: $INSTANCE_NAME"
echo "  Zone: $ZONE"
echo "  App Directory: $APP_DIR"
echo ""

# Step 1: Commit and push changes
echo "📦 Step 1: Committing and pushing changes..."
git add .
git commit -m "Fix: Add GAE support, WSGI config, and deployment fixes" || echo "No changes to commit"
git push origin main
echo "✅ Code pushed to GitHub"
echo ""

# Step 2: SSH to VM and pull latest code
echo "🔄 Step 2: Pulling latest code on VM..."
gcloud compute ssh $INSTANCE_NAME \
  --zone=$ZONE \
  --project=$PROJECT_ID \
  --command="cd $APP_DIR && sudo -u trendvision git fetch origin && sudo -u trendvision git reset --hard origin/main"
echo "✅ Code updated on VM"
echo ""

# Step 3: Restart services
echo "🔄 Step 3: Restarting services..."
gcloud compute ssh $INSTANCE_NAME \
  --zone=$ZONE \
  --project=$PROJECT_ID \
  --command="sudo systemctl restart trendvision-web trendvision-pipeline"
echo "✅ Services restarted"
echo ""

# Step 4: Check service status
echo "📊 Step 4: Checking service status..."
gcloud compute ssh $INSTANCE_NAME \
  --zone=$ZONE \
  --project=$PROJECT_ID \
  --command="sudo systemctl status trendvision-web trendvision-pipeline --no-pager"
echo ""

# Step 5: Show recent logs
echo "📝 Step 5: Recent pipeline logs..."
gcloud compute ssh $INSTANCE_NAME \
  --zone=$ZONE \
  --project=$PROJECT_ID \
  --command="sudo journalctl -u trendvision-pipeline -n 20 --no-pager"
echo ""

echo "================================================"
echo "✅ Deployment Complete!"
echo ""
echo "🌐 Access your application at:"
echo "   https://trendvision2004.com"
echo ""
echo "📊 Monitor logs with:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='sudo journalctl -u trendvision-pipeline -f'"
echo ""
echo "🔧 Check status with:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='sudo systemctl status trendvision-web trendvision-pipeline'"
echo ""
