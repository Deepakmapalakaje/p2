# 🚀 Quick Deployment Guide - Option A (VM Only)

## ⚡ One-Command Deployment

### Windows (PowerShell)
```powershell
.\deploy_to_vm.ps1
```

### Linux/Mac (Bash)
```bash
bash deploy_to_vm.sh
```

---

## 📋 What the Script Does

1. ✅ Commits and pushes your code to GitHub
2. ✅ SSHs to your VM and pulls latest code
3. ✅ Restarts both web and pipeline services
4. ✅ Shows service status
5. ✅ Displays recent logs

---

## 🔧 Manual Deployment (If Script Fails)

### Step 1: Push Code
```bash
git add .
git commit -m "Deploy fixes"
git push origin main
```

### Step 2: SSH to VM
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b
```

### Step 3: Pull Latest Code
```bash
cd /opt/trendvision
sudo -u trendvision git fetch origin
sudo -u trendvision git reset --hard origin/main
```

### Step 4: Restart Services
```bash
sudo systemctl restart trendvision-web trendvision-pipeline
```

### Step 5: Verify
```bash
sudo systemctl status trendvision-web trendvision-pipeline
sudo journalctl -u trendvision-pipeline -f
```

---

## 🌐 Access Your Application

**Main URL**: https://trendvision2004.com

**Admin Panel**: https://trendvision2004.com/admin/login
- Username: `dsar`
- Password: `dsar`

---

## 📊 Monitoring Commands

### Check Service Status
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo systemctl status trendvision-web trendvision-pipeline"
```

### View Pipeline Logs (Live)
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo journalctl -u trendvision-pipeline -f"
```

### View Web App Logs (Live)
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo journalctl -u trendvision-web -f"
```

### View Application Log File
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="tail -f /opt/trendvision/logs/upstox_v3_trading.log"
```

---

## 🔍 Troubleshooting

### Pipeline Not Running?

**Check if it's market hours:**
- Pipeline only runs: 9:15 AM - 3:30 PM IST
- Monday - Friday only
- Outside hours = graceful exit (normal behavior)

**Check access token:**
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="cat /opt/trendvision/config/config.json | grep TOKEN_UPDATE_DATE"
```
- Token must be updated daily via admin panel

**Check CSV file:**
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="wc -l /opt/trendvision/extracted_data.csv"
```
- Should have ~60 option rows

### Web App Not Accessible?

**Check Nginx:**
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo systemctl status nginx"
```

**Check SSL Certificate:**
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo certbot certificates"
```

**Test local connection:**
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="curl http://localhost:8080/api/summary"
```

### Database Issues?

**Check database files:**
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="ls -lh /opt/trendvision/database/"
```

**Check database tables:**
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sqlite3 /opt/trendvision/database/upstox_v3_live_trading.db '.tables'"
```

---

## 🔄 Daily Operations

### Morning Routine (Before Market Open)
1. Update access token via admin panel
2. Verify pipeline service is running
3. Check logs for any errors

### During Market Hours
1. Monitor dashboard: https://trendvision2004.com/dashboard
2. Check cash flow data
3. Review buy signals

### After Market Close
1. Pipeline auto-exits (normal behavior)
2. Review day's data
3. Backup database if needed

---

## 💾 Backup Database

```bash
# SSH to VM
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b

# Create backup
sudo -u trendvision cp /opt/trendvision/database/upstox_v3_live_trading.db \
  /opt/trendvision/database/backup_$(date +%Y%m%d).db

# Download to local machine (exit SSH first)
gcloud compute scp instance-20250922-072947:/opt/trendvision/database/backup_*.db \
  ./backups/ --zone=asia-south1-b
```

---

## 🆘 Emergency Commands

### Restart Everything
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo systemctl restart trendvision-web trendvision-pipeline nginx"
```

### Stop Pipeline (Emergency)
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo systemctl stop trendvision-pipeline"
```

### View All Logs
```bash
gcloud compute ssh instance-20250922-072947 --zone=asia-south1-b \
  --command="sudo journalctl -u trendvision-web -u trendvision-pipeline -n 100"
```

### Reboot VM (Last Resort)
```bash
gcloud compute instances reset instance-20250922-072947 --zone=asia-south1-b
```

---

## ✅ Success Indicators

### Pipeline Running Correctly
- ✅ Service status: `active (running)`
- ✅ Logs show: "LOCK-FREE Stats: Messages: X | Ticks: Y"
- ✅ Database growing: `ls -lh database/upstox_v3_live_trading.db`
- ✅ Cash flow updating: Check dashboard

### Web App Working
- ✅ Service status: `active (running)`
- ✅ Port 8080 listening: `netstat -tlnp | grep 8080`
- ✅ Nginx proxying: `sudo systemctl status nginx`
- ✅ Dashboard accessible: https://trendvision2004.com

---

## 📞 Quick Reference

| Component | Port | Service Name | Log Command |
|-----------|------|--------------|-------------|
| Web App | 8080 | trendvision-web | `journalctl -u trendvision-web -f` |
| Pipeline | - | trendvision-pipeline | `journalctl -u trendvision-pipeline -f` |
| Nginx | 80/443 | nginx | `journalctl -u nginx -f` |
| App Logs | - | - | `tail -f logs/upstox_v3_trading.log` |

---

## 🎯 Expected Behavior

### During Market Hours (9:15 AM - 3:30 PM IST, Mon-Fri)
- Pipeline: **Running** (collecting data)
- Web App: **Running** (serving dashboard)
- Logs: Active with tick data
- Dashboard: Live updates

### Outside Market Hours
- Pipeline: **Stopped** (graceful exit - NORMAL)
- Web App: **Running** (serving dashboard)
- Logs: "Outside market hours" message
- Dashboard: Shows last session data

---

**🎉 You're all set! Run `.\deploy_to_vm.ps1` to deploy.**
