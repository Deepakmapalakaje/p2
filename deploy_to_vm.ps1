# Quick deployment script for Compute Engine VM (PowerShell)
# Run this from your local Windows machine

$ErrorActionPreference = "Stop"

Write-Host "🚀 Deploying TrendVision to Compute Engine VM..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# Configuration
$PROJECT_ID = "trendvision-471404"
$INSTANCE_NAME = "instance-20250922-072947"
$ZONE = "asia-south1-b"
$APP_DIR = "/opt/trendvision"

Write-Host "`n📋 Configuration:" -ForegroundColor Yellow
Write-Host "  Project: $PROJECT_ID"
Write-Host "  Instance: $INSTANCE_NAME"
Write-Host "  Zone: $ZONE"
Write-Host "  App Directory: $APP_DIR"
Write-Host ""

# Step 1: Commit and push changes
Write-Host "📦 Step 1: Committing and pushing changes..." -ForegroundColor Green
try {
    git add .
    git commit -m "Fix: Add GAE support, WSGI config, and deployment fixes"
} catch {
    Write-Host "No changes to commit" -ForegroundColor Yellow
}
git push origin main
Write-Host "✅ Code pushed to GitHub" -ForegroundColor Green
Write-Host ""

# Step 2: SSH to VM and pull latest code
Write-Host "🔄 Step 2: Pulling latest code on VM..." -ForegroundColor Green
gcloud compute ssh $INSTANCE_NAME `
  --zone=$ZONE `
  --project=$PROJECT_ID `
  --command="cd $APP_DIR && sudo -u trendvision git fetch origin && sudo -u trendvision git reset --hard origin/main"
Write-Host "✅ Code updated on VM" -ForegroundColor Green
Write-Host ""

# Step 3: Restart services
Write-Host "🔄 Step 3: Restarting services..." -ForegroundColor Green
gcloud compute ssh $INSTANCE_NAME `
  --zone=$ZONE `
  --project=$PROJECT_ID `
  --command="sudo systemctl restart trendvision-web trendvision-pipeline"
Write-Host "✅ Services restarted" -ForegroundColor Green
Write-Host ""

# Step 4: Check service status
Write-Host "📊 Step 4: Checking service status..." -ForegroundColor Green
gcloud compute ssh $INSTANCE_NAME `
  --zone=$ZONE `
  --project=$PROJECT_ID `
  --command="sudo systemctl status trendvision-web trendvision-pipeline --no-pager"
Write-Host ""

# Step 5: Show recent logs
Write-Host "📝 Step 5: Recent pipeline logs..." -ForegroundColor Green
gcloud compute ssh $INSTANCE_NAME `
  --zone=$ZONE `
  --project=$PROJECT_ID `
  --command="sudo journalctl -u trendvision-pipeline -n 20 --no-pager"
Write-Host ""

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Access your application at:" -ForegroundColor Yellow
Write-Host "   https://trendvision2004.com" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Monitor logs with:" -ForegroundColor Yellow
Write-Host "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='sudo journalctl -u trendvision-pipeline -f'" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Check status with:" -ForegroundColor Yellow
Write-Host "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='sudo systemctl status trendvision-web trendvision-pipeline'" -ForegroundColor White
Write-Host ""
