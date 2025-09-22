#!/bin/bash
# TrendVision VM Deployment Script
# This script sets up the complete TrendVision application on a VM

set -e  # Exit on any error

echo "🚀 Starting TrendVision VM Deployment..."
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_error "This script should not be run as root"
    exit 1
fi

# Update system
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.11 if not present
print_status "Installing Python 3.11..."
if ! command -v python3.11 &> /dev/null; then
    sudo apt install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt update
    sudo apt install -y python3.11 python3.11-venv python3.11-dev
    print_success "Python 3.11 installed"
else
    print_success "Python 3.11 already installed"
fi

# Install pip if not present
if ! command -v pip3.11 &> /dev/null; then
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11
fi

# Create application directory
print_status "Creating application directory..."
APP_DIR="/opt/trendvision"
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR

# Copy application files
print_status "Copying application files to $APP_DIR..."
cp -r . $APP_DIR/
cd $APP_DIR

# Create virtual environment
print_status "Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install flask flask-limiter werkzeug python-multipart psutil zoneinfo

# Make scripts executable
print_status "Making scripts executable..."
chmod +x *.py
chmod +x *.sh

# Create database directory
print_status "Creating database directory..."
mkdir -p database

# Initialize database
print_status "Initializing database..."
python3 init_database.py

# Create systemd service files
print_status "Creating systemd service files..."

# Web service
sudo tee /etc/systemd/system/trendvision-web.service > /dev/null <<EOF
[Unit]
Description=TrendVision Web Application
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
Environment=FLASK_APP=app.py
Environment=FLASK_ENV=production
ExecStart=$APP_DIR/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Pipeline service (placeholder)
sudo tee /etc/systemd/system/trendvision-pipeline.service > /dev/null <<EOF
[Unit]
Description=TrendVision Trading Pipeline
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python pipeline.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

print_success "Systemd service files created"

# Enable and start services
print_status "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable trendvision-web.service
sudo systemctl start trendvision-web.service

# Create nginx configuration (optional)
print_status "Creating nginx configuration..."
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
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/trendvision /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

print_success "Nginx configuration created"

# Create firewall rules
print_status "Configuring firewall..."
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# Create backup script
print_status "Creating backup script..."
cat > backup.sh << 'EOF'
#!/bin/bash
# TrendVision Backup Script

BACKUP_DIR="/var/backups/trendvision"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup databases
cp database/*.db $BACKUP_DIR/

# Backup configuration
cp config/config.json $BACKUP_DIR/config_$TIMESTAMP.json

# Create archive
tar -czf $BACKUP_DIR/trendvision_backup_$TIMESTAMP.tar.gz \
    $BACKUP_DIR/*.db \
    $BACKUP_DIR/config_$TIMESTAMP.json \
    --exclude=$BACKUP_DIR/*.tar.gz

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/trendvision_backup_$TIMESTAMP.tar.gz"
EOF

chmod +x backup.sh

# Create log rotation
print_status "Setting up log rotation..."
sudo tee /etc/logrotate.d/trendvision > /dev/null <<EOF
$APP_DIR/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
}
EOF

print_success "Log rotation configured"

# Create monitoring script
print_status "Creating monitoring script..."
cat > monitor.sh << 'EOF'
#!/bin/bash
# TrendVision Monitoring Script

echo "=== TrendVision System Status ==="
echo "Date: $(date)"
echo "Uptime: $(uptime -p)"
echo "Disk Usage: $(df -h / | tail -1)"
echo "Memory Usage: $(free -h | head -2 | tail -1)"
echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}')"
echo "Active Services:"

# Check services
services=("trendvision-web" "trendvision-pipeline")
for service in "${services[@]}"; do
    if systemctl is-active --quiet $service; then
        echo "  ✅ $service - Running"
    else
        echo "  ❌ $service - Stopped"
    fi
done

echo "=== Application Logs (Last 10 lines) ==="
tail -10 app.log 2>/dev/null || echo "No logs found"

echo "=== Database Status ==="
if [ -f "database/users.db" ]; then
    echo "  ✅ User database exists"
    sqlite3 database/users.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "  ❌ User database corrupted"
fi

if [ -f "database/upstox_v3_live_trading.db" ]; then
    echo "  ✅ Trading database exists"
    sqlite3 database/upstox_v3_live_trading.db "SELECT COUNT(*) FROM latest_candles;" 2>/dev/null || echo "  ❌ Trading database corrupted"
fi
EOF

chmod +x monitor.sh

# Create update script
print_status "Creating update script..."
cat > update.sh << 'EOF'
#!/bin/bash
# TrendVision Update Script

echo "=== TrendVision Update ==="
echo "Date: $(date)"

# Backup current installation
./backup.sh

# Pull latest changes (if using git)
if [ -d ".git" ]; then
    git pull origin main
fi

# Stop services
sudo systemctl stop trendvision-web.service
sudo systemctl stop trendvision-pipeline.service

# Update dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Update database schema
python3 init_database.py

# Start services
sudo systemctl start trendvision-web.service
sudo systemctl start trendvision-pipeline.service

# Check status
./monitor.sh

echo "Update completed successfully!"
EOF

chmod +x update.sh

# Set proper permissions
print_status "Setting proper permissions..."
sudo chown -R $USER:$USER $APP_DIR
chmod -R 755 $APP_DIR

# Create symbolic links for easy access
print_status "Creating symbolic links..."
sudo ln -sf $APP_DIR/monitor.sh /usr/local/bin/trendvision-monitor
sudo ln -sf $APP_DIR/update.sh /usr/local/bin/trendvision-update
sudo ln -sf $APP_DIR/backup.sh /usr/local/bin/trendvision-backup

print_success "Symbolic links created"

# Final verification
print_status "Performing final verification..."
./monitor.sh

print_success "TrendVision VM deployment completed successfully!"
print_status ""
print_status "=== ACCESS INFORMATION ==="
print_status "Application URL: http://$(hostname -I | awk '{print $1}')"
print_status "Admin Login: dsar / dsar"
print_status "Test Users: testuser1/password123, testuser2/password123"
print_status ""
print_status "=== USEFUL COMMANDS ==="
print_status "Monitor system: trendvision-monitor"
print_status "Update application: trendvision-update"
print_status "Backup data: trendvision-backup"
print_status "Check logs: journalctl -u trendvision-web.service -f"
print_status "Restart web service: sudo systemctl restart trendvision-web.service"
print_status ""
print_status "=== SECURITY NOTES ==="
print_status "1. Change default passwords immediately"
print_status "2. Configure SSL certificate for HTTPS"
print_status "3. Set up firewall rules as needed"
print_status "4. Configure email settings in config/config.json"
print_status "5. Set up log rotation and monitoring"
print_status ""
print_success "Deployment completed! The application is ready to use."
