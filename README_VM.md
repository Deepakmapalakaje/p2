# TrendVision VM Deployment Guide

## Overview
TrendVision is a comprehensive trading application with real-time market data, AI-powered signals, and user management. This guide provides complete instructions for deploying TrendVision on a VM.

## System Requirements
- Ubuntu 20.04+ or Debian-based Linux
- Python 3.11+
- 2GB RAM minimum
- 10GB disk space
- Internet connection

## Quick Start (Automated Deployment)

### 1. Copy Files to VM
```bash
# Upload all files from this directory to your VM
# Place them in /opt/trendvision or your preferred directory
```

### 2. Run Automated Deployment
```bash
# Make the deployment script executable
chmod +x deploy_vm.sh

# Run the deployment script
./deploy_vm.sh
```

### 3. Access the Application
- **URL**: http://your-vm-ip
- **Admin Login**: dsar / dsar
- **Test Users**: testuser1/password123, testuser2/password123

## Manual Deployment Steps

### Step 1: Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Python 3.11
```bash
# Install Python 3.11
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Verify installation
python3.11 --version
```

### Step 3: Setup Application Directory
```bash
# Create application directory
sudo mkdir -p /opt/trendvision
sudo chown -R $USER:$USER /opt/trendvision

# Copy application files
cp -r . /opt/trendvision/
cd /opt/trendvision
```

### Step 4: Create Virtual Environment
```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Step 5: Install Dependencies
```bash
# Install required packages
pip install -r requirements.txt
```

### Step 6: Initialize Database
```bash
# Run database initialization
python3 init_database.py
```

### Step 7: Create Systemd Services

#### Web Service
```bash
sudo tee /etc/systemd/system/trendvision-web.service > /dev/null <<EOF
[Unit]
Description=TrendVision Web Application
After=network.target

[Service]
User=$USER
WorkingDirectory=/opt/trendvision
Environment=PATH=/opt/trendvision/venv/bin
Environment=FLASK_APP=app.py
Environment=FLASK_ENV=production
ExecStart=/opt/trendvision/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

#### Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable trendvision-web.service
sudo systemctl start trendvision-web.service
```

### Step 8: Setup Nginx (Optional)
```bash
sudo apt install -y nginx
sudo tee /etc/nginx/sites-available/trendvision > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias /opt/trendvision/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/trendvision /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Step 9: Configure Firewall
```bash
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable
```

## Database Information

### User Database
- **Location**: `/opt/trendvision/database/users.db`
- **Tables**: users, sessions
- **Admin User**: dsar / dsar
- **Test Users**: testuser1/password123, testuser2/password123

### Trading Database
- **Location**: `/opt/trendvision/database/upstox_v3_live_trading.db`
- **Tables**: table_registry, trend, latest_candles, options_cash_flow, buy_signals, option_tracking

## Management Scripts

### Monitor System Status
```bash
# Using the installed script
trendvision-monitor

# Or run directly
./monitor.sh
```

### Backup Data
```bash
# Using the installed script
trendvision-backup

# Or run directly
./backup.sh
```

### Update Application
```bash
# Using the installed script
trendvision-update

# Or run directly
./update.sh
```

## Configuration Files

### Email Configuration
Edit `/opt/trendvision/config/config.json`:
```json
{
  "EMAIL_CONFIG": {
    "ENABLE_EMAIL": true,
    "SENDER_EMAIL": "your-gmail@gmail.com",
    "SENDER_PASSWORD": "your-app-password",
    "SMTP_SERVER": "smtp.gmail.com",
    "SMTP_PORT": 587
  }
}
```

### Trading Configuration
Update API keys and trading parameters in the same config file.

## Security Considerations

1. **Change Default Passwords**
   - Change admin password from 'dsar'
   - Update test user passwords
   - Use strong passwords

2. **SSL Certificate**
   ```bash
   sudo apt install -y certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

3. **Firewall Rules**
   - Only open necessary ports (80, 443)
   - Use fail2ban for SSH protection

4. **Regular Backups**
   - Database backups created automatically
   - Monitor backup script execution

## Troubleshooting

### Check Service Status
```bash
sudo systemctl status trendvision-web.service
sudo journalctl -u trendvision-web.service -f
```

### Check Application Logs
```bash
tail -f /opt/trendvision/app.log
```

### Database Issues
```bash
# Reinitialize database
python3 init_database.py

# Check database integrity
sqlite3 database/users.db "PRAGMA integrity_check;"
sqlite3 database/upstox_v3_live_trading.db "PRAGMA integrity_check;"
```

### Permission Issues
```bash
# Fix permissions
sudo chown -R $USER:$USER /opt/trendvision
chmod -R 755 /opt/trendvision
```

## API Endpoints

### User Management
- `POST /login` - User login (email-based)
- `POST /signup` - User registration
- `GET/POST /profile` - User profile management
- `POST /logout` - User logout

### Trading Data
- `GET /api/summary` - Market summary data
- `GET /api/cash-flow` - Cash flow data
- `GET /api/buy-signals` - Trading signals
- `GET /api/itm-options` - ITM options data

### Admin Only
- `GET /admin` - Admin dashboard
- `GET/POST /api/config` - Configuration management
- `POST /api/restart-pipeline` - Restart trading pipeline

## Support

For issues or questions:
1. Check the logs: `journalctl -u trendvision-web.service -f`
2. Run diagnostics: `./monitor.sh`
3. Check database: `python3 init_database.py`
4. Verify configuration: Check `/opt/trendvision/config/config.json`

## Version Information
- **Application**: TrendVision v3.0
- **Python**: 3.11+
- **Flask**: 2.3.3
- **Database**: SQLite 3
- **Deployment**: Ubuntu/Debian Linux
