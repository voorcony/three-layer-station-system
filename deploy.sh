#!/bin/bash
# Deployment script for Three-Layer Station System
# Run on the target server: bash deploy.sh

set -e

echo "================================================"
echo "  Three-Layer Station System - Deployment"
echo "================================================"

# Configuration
PROJECT_DIR="/opt/three-layer-stations"
SERVICE_NAME="three-layer-stations"
GIT_REPO="https://github.com/nousresearch/three-layer-station-system.git"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[x]${NC} $1"; }

# Step 1: Install system dependencies
log "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    redis-server \
    python3-pip \
    python3-venv \
    nginx \
    git \
    curl \
    ufw

# Step 2: Enable and start services
log "Starting redis-server..."
systemctl enable redis-server
systemctl start redis-server

# Step 3: Create project directory
log "Creating project directory at ${PROJECT_DIR}..."
mkdir -p ${PROJECT_DIR}
mkdir -p ${PROJECT_DIR}/app/templates

if [ -d "${PROJECT_DIR}/.git" ]; then
    log "Repository already exists, pulling latest..."
    cd ${PROJECT_DIR} && git pull
else
    log "Cloning repository..."
    git clone ${GIT_REPO} ${PROJECT_DIR} 2>/dev/null || true
fi

# Step 4: Set up Python virtual environment
log "Setting up Python virtual environment..."
if [ ! -d "${PROJECT_DIR}/venv" ]; then
    python3 -m venv ${PROJECT_DIR}/venv
fi
source ${PROJECT_DIR}/venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r ${PROJECT_DIR}/requirements.txt

# Step 5: Create .env file
log "Creating .env file..."
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    cat > ${PROJECT_DIR}/.env << 'EOF'
# Shopify Configuration
SHOPIFY_STORE=147xvt-jc.myshopify.com
SHOPIFY_STOREFRONT_TOKEN=48382a763d8f47c5bf40b7983eeb2d73

# Application Settings
BASE_URL=http://43.154.181.44
DOMAIN_NAME=43.154.181.44

# Database Path
DATABASE_PATH=/opt/three-layer-stations/orders.db
EOF
    log "Created .env file"
fi

# Step 6: Create systemd service
log "Creating systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << 'SERVICEEOF'
[Unit]
Description=Three-Layer Station System (三层站群支付系统)
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/three-layer-stations
EnvironmentFile=/opt/three-layer-stations/.env
ExecStart=/opt/three-layer-stations/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --log-level info
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}

# Step 7: Configure nginx
log "Configuring nginx reverse proxy..."
cat > /etc/nginx/sites-available/three-layer-stations << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 30s;
    }

    location /static/ {
        alias /opt/three-layer-stations/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    access_log /var/log/nginx/three-layer-stations-access.log;
    error_log /var/log/nginx/three-layer-stations-error.log;
}
NGINXEOF

# Enable the site
if [ -f /etc/nginx/sites-enabled/default ]; then
    rm /etc/nginx/sites-enabled/default
fi
ln -sf /etc/nginx/sites-available/three-layer-stations /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Step 8: Configure firewall
log "Configuring firewall..."
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw --force enable 2>/dev/null || true

# Step 9: Start the application
log "Starting the application..."
systemctl restart ${SERVICE_NAME}

# Step 10: Verify deployment
log "Verifying deployment..."
sleep 3
if curl -s http://localhost:8000/health > /dev/null; then
    log "Application is running! Health check passed."
    curl -s http://localhost:8000/health
    echo ""
else
    warn "Health check failed. Check logs: journalctl -u ${SERVICE_NAME} -f"
fi

echo ""
echo "================================================"
echo "  Deployment Complete!"
echo "  URL: http://43.154.181.44"
echo "  Health: http://43.154.181.44/health"
echo "================================================"
