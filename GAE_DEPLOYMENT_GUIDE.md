# Google App Engine Deployment Guide for TrendVision

## ⚠️ IMPORTANT: Architecture Limitation

**Google App Engine Standard does NOT support long-running WebSocket connections.**

Your `pipeline1.py` WebSocket client **CANNOT run on GAE Standard**. You have two options:

### Option 1: Hybrid Architecture (Recommended)
- **GAE Standard**: Run `app.py` (web dashboard + APIs)
- **Compute Engine VM**: Run `pipeline1.py` (WebSocket data collection)
- Both connect to the same SQLite database (or migrate to Cloud SQL)

### Option 2: Full Migration to Compute Engine
- Keep your current VM setup (already working)
- Use the existing systemd services
- This is what you currently have deployed

## 🚀 Deploying Web App to GAE (Option 1)

### Prerequisites
```bash
# Install Google Cloud SDK
# Download from: https://cloud.google.com/sdk/docs/install

# Login to GCP
gcloud auth login

# Set your project
gcloud config set project trendvision-471404
```

### Step 1: Initialize Database
```bash
# Create database directory
mkdir -p database

# Initialize databases
python init_database.py
```

### Step 2: Update Configuration
```bash
# Edit config/config.json with your ACCESS_TOKEN
# Make sure TOKEN_UPDATE_DATE is current
```

### Step 3: Deploy to GAE
```bash
# Deploy the application
gcloud app deploy app.yaml --project=trendvision-471404

# View logs
gcloud app logs tail -s default

# Open in browser
gcloud app browse
```

### Step 4: Set up Pipeline on Compute Engine
```bash
# SSH to your existing VM
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b

# Pull latest code
cd /opt/trendvision
sudo -u trendvision git pull origin main

# Restart pipeline service
sudo systemctl restart trendvision-pipeline

# Check status
sudo systemctl status trendvision-pipeline
sudo journalctl -u trendvision-pipeline -f
```

## 📊 Database Considerations

### Current Setup (SQLite)
- ✅ Simple, no external dependencies
- ❌ Cannot be shared between GAE and VM easily
- ❌ GAE instances are ephemeral (data loss on restart)

### Recommended: Migrate to Cloud SQL
```bash
# Create Cloud SQL instance
gcloud sql instances create trendvision-db \
    --database-version=POSTGRES_14 \
    --tier=db-f1-micro \
    --region=asia-south1

# Create database
gcloud sql databases create trading_db --instance=trendvision-db

# Get connection name
gcloud sql instances describe trendvision-db --format="value(connectionName)"
```

Then update your code to use PostgreSQL instead of SQLite.

## 🔧 Configuration Files Created

### `app.yaml`
- Runtime: Python 3.11
- Instance class: F2 (512MB RAM, 1.2GHz CPU)
- Gunicorn WSGI server with 2 workers
- Environment variables for database paths
- Auto-scaling: 1-3 instances

### `.gcloudignore`
- Excludes development files
- Excludes large CSV files
- Excludes test scripts

### `requirements.txt`
- Added `gunicorn==21.2.0` for production WSGI server

### `app.py`
- Exported `app` instance at module level for WSGI
- Compatible with both GAE and local development

## 🎯 Current Status

### ✅ Fixed Issues
1. Created `app.yaml` for GAE deployment
2. Added `gunicorn` to requirements
3. Exported `app` instance for WSGI servers
4. Created `.gcloudignore` for clean deployments
5. Database directories auto-created

### ⚠️ Known Limitations
1. **Pipeline cannot run on GAE** - Use Compute Engine VM
2. **SQLite not ideal for GAE** - Consider Cloud SQL migration
3. **Ephemeral storage** - Database resets on GAE restart

## 🔄 Recommended Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Users / Browsers                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Google App Engine (app.py)                  │
│  • Web Dashboard                                         │
│  • API Endpoints                                         │
│  • User Authentication                                   │
│  • Admin Panel                                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Cloud SQL Connection
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Cloud SQL (PostgreSQL)                      │
│  • Trading Data                                          │
│  • User Data                                             │
│  • Persistent Storage                                    │
└────────────────────▲────────────────────────────────────┘
                     │
                     │ SQL Connection
                     │
┌─────────────────────────────────────────────────────────┐
│         Compute Engine VM (pipeline1.py)                 │
│  • WebSocket Connection to Upstox                        │
│  • Real-time Data Processing                             │
│  • Cash Flow Calculations                                │
│  • Buy Signal Generation                                 │
└─────────────────────────────────────────────────────────┘
```

## 💰 Cost Estimate

### GAE Standard (F2 Instance)
- 1 instance always running: ~$40/month
- Additional instances (auto-scale): ~$40/instance/month

### Compute Engine (Current VM)
- e2-micro: ~$7/month (free tier eligible)
- e2-small: ~$14/month

### Cloud SQL (db-f1-micro)
- PostgreSQL instance: ~$10/month

**Total Estimated Cost: $17-60/month** (depending on configuration)

## 🚦 Deployment Commands

### Quick Deploy (Web App Only)
```bash
gcloud app deploy --quiet
```

### Full System Restart
```bash
# Deploy web app
gcloud app deploy --quiet

# Restart pipeline on VM
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b --command="sudo systemctl restart trendvision-pipeline"
```

### Check Status
```bash
# GAE logs
gcloud app logs tail -s default

# VM pipeline logs
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b --command="sudo journalctl -u trendvision-pipeline -n 50"
```

## 📝 Next Steps

1. **Test locally first**:
   ```bash
   gunicorn -b :8080 -w 2 --threads 4 app:app
   ```

2. **Deploy to GAE**:
   ```bash
   gcloud app deploy
   ```

3. **Verify deployment**:
   ```bash
   gcloud app browse
   ```

4. **Monitor logs**:
   ```bash
   gcloud app logs tail -s default
   ```

5. **Consider Cloud SQL migration** for production reliability

## 🆘 Troubleshooting

### App won't start on GAE
- Check logs: `gcloud app logs tail -s default`
- Verify `app.yaml` syntax
- Ensure all dependencies in `requirements.txt`

### Database errors
- GAE instances are ephemeral
- Database resets on restart
- **Solution**: Migrate to Cloud SQL

### Pipeline not collecting data
- Pipeline must run on Compute Engine VM
- Check VM status: `gcloud compute instances list`
- Check pipeline service: `sudo systemctl status trendvision-pipeline`

### 502 Bad Gateway
- App initialization timeout
- Increase timeout in `app.yaml`: `--timeout 300`
- Check for startup errors in logs

---

**For immediate deployment to your current VM (recommended):**
```bash
# SSH to VM
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b

# Pull latest code
cd /opt/trendvision
sudo -u trendvision git pull origin main

# Restart services
sudo systemctl restart trendvision-web trendvision-pipeline

# Check status
sudo systemctl status trendvision-web trendvision-pipeline
```
