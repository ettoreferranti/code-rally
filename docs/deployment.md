# CodeRally Deployment Guide

This guide covers deploying CodeRally for local development, testing, and production environments.

## Table of Contents

- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Environment Configuration](#environment-configuration)
- [Database Management](#database-management)
- [Troubleshooting](#troubleshooting)

---

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/ettoreferranti/code-rally.git
cd code-rally

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Initialize database
python -c "from app.database import init_db; init_db()"

# Run backend (Terminal 1)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend setup (Terminal 2)
cd ../frontend
npm install
npm run dev
```

Access the application at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

---

## Production Deployment

### Prerequisites

- Ubuntu 20.04+ (or similar Linux distribution)
- Domain name (optional, for public access)
- SSL certificate (recommended for production)

### Step 1: System Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

### Step 2: Application Setup

```bash
# Create application directory
sudo mkdir -p /var/www/coderally
sudo chown $USER:$USER /var/www/coderally
cd /var/www/coderally

# Clone repository
git clone https://github.com/ettoreferranti/code-rally.git .

# Backend setup
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create production config (optional)
cp app/config.py app/config_prod.py
# Edit config_prod.py with production settings

# Initialize database
python -c "from app.database import init_db; init_db()"
```

### Step 3: Frontend Build

```bash
cd /var/www/coderally/frontend
npm install
npm run build
# Build output will be in frontend/dist/
```

### Step 4: Systemd Service Setup

Create backend service file:

```bash
sudo nano /etc/systemd/system/coderally-backend.service
```

Add the following content:

```ini
[Unit]
Description=CodeRally Backend Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/coderally/backend
Environment="PATH=/var/www/coderally/backend/venv/bin"
ExecStart=/var/www/coderally/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable coderally-backend
sudo systemctl start coderally-backend
sudo systemctl status coderally-backend
```

### Step 5: Nginx Configuration

Create Nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/coderally
```

Add the following:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    # Frontend (static files)
    location / {
        root /var/www/coderally/frontend/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /game/ws {
        proxy_pass http://localhost:8000/game/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/coderally /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 6: SSL Setup (Optional but Recommended)

Using Let's Encrypt with Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Certbot will automatically configure SSL and set up auto-renewal.

---

## Docker Deployment

### Dockerfile (Backend)

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile (Frontend)

Create `frontend/Dockerfile`:

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./data/coderally.db
    volumes:
      - ./backend/data:/app/data
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

Deploy with Docker Compose:

```bash
docker-compose up -d
```

---

## Environment Configuration

### Backend Environment Variables

Create `.env` file in `backend/` directory:

```bash
# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Database
DATABASE_URL=sqlite:///./data/coderally.db

# Game Settings
TICK_RATE=60
MAX_CONCURRENT_PLAYERS=8

# CORS (adjust for your domain)
ALLOWED_ORIGINS=https://your-domain.com
```

Update `config.py` to read from environment:

```python
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ServerConfig:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    # ... etc
```

Install python-dotenv:
```bash
pip install python-dotenv
```

### Frontend Environment Variables

Create `.env.production` in `frontend/`:

```bash
VITE_API_URL=https://your-domain.com/api
VITE_WS_URL=wss://your-domain.com/game/ws
```

Update services to use these:

```typescript
// frontend/src/services/config.ts
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/game/ws';
```

---

## Database Management

### Backup

```bash
# Backup SQLite database
cp backend/data/coderally.db backend/data/coderally.db.backup-$(date +%Y%m%d)

# Automated daily backups (add to crontab)
0 2 * * * cp /var/www/coderally/backend/data/coderally.db /var/backups/coderally-$(date +\%Y\%m\%d).db
```

### Database Migrations (Future)

When implementing database migrations with Alembic:

```bash
# Install Alembic
pip install alembic

# Initialize migrations
alembic init migrations

# Create migration
alembic revision --autogenerate -m "Add users table"

# Apply migrations
alembic upgrade head
```

---

## Monitoring and Logs

### View Backend Logs

```bash
# Systemd service logs
sudo journalctl -u coderally-backend -f

# Application logs (if using file logging)
tail -f /var/www/coderally/backend/logs/app.log
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Check active game sessions
curl http://localhost:8000/game/sessions
```

### Performance Monitoring

Consider installing:
- **Prometheus + Grafana** for metrics
- **Sentry** for error tracking
- **nginx access logs** for traffic analysis

---

## Troubleshooting

### Backend won't start

```bash
# Check logs
sudo journalctl -u coderally-backend -n 50

# Common issues:
# 1. Port already in use
sudo lsof -i :8000

# 2. Permission issues
sudo chown -R www-data:www-data /var/www/coderally/backend/data

# 3. Virtual environment issues
cd /var/www/coderally/backend
source venv/bin/activate
pip install -r requirements.txt
```

### WebSocket connection fails

```bash
# Check Nginx configuration
sudo nginx -t

# Ensure WebSocket headers are set
# See Nginx config above for proper WebSocket setup

# Check firewall
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Database is locked

```bash
# SQLite lock issues (multiple processes accessing)
# Solution: Use connection pooling or switch to PostgreSQL for production

# Quick fix: restart backend
sudo systemctl restart coderally-backend
```

### Frontend shows 404 for routes

```bash
# Ensure Nginx has try_files for SPA routing
# See Nginx config above: try_files $uri $uri/ /index.html;
```

---

## Production Checklist

Before going live:

- [ ] Set `DEBUG=false` in backend config
- [ ] Configure proper CORS origins (not wildcard)
- [ ] Set up SSL certificate
- [ ] Configure firewall rules
- [ ] Set up automated database backups
- [ ] Configure log rotation
- [ ] Set up monitoring/alerting
- [ ] Test WebSocket connections under load
- [ ] Document custom configuration changes
- [ ] Set up staging environment for testing

---

## Scaling Considerations

For larger deployments:

1. **Database**: Migrate from SQLite to PostgreSQL
2. **Load Balancing**: Use multiple backend instances with nginx load balancing
3. **Session Affinity**: WebSocket connections require sticky sessions
4. **Caching**: Add Redis for session storage and caching
5. **CDN**: Use CDN for static frontend assets

See `architecture.md` for more on scaling architecture.
