# Bluesky Feed Generator - Deployment Guide

Production deployment guide for custom Bluesky feeds using Docker, Nginx, and GitHub Actions.

For project overview and filtering logic, see [README.md](README.md).

## Table of Contents

- [Quick Reference](#quick-reference)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Security](#security)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Known Issues](#known-issues)

---

## Quick Reference

**Production Stack**
- Docker + Docker Compose for containerization
- Waitress WSGI server (production-ready)
- SQLite database
- Nginx reverse proxy
- Let's Encrypt SSL
- GitHub Actions for CI/CD

**Deployment Flow**
```
Local Dev → Git Push → GitHub Actions → SSH to Server → Docker Rebuild → Live
```

**Example Feed**
- **URL**: https://bsky-feeds.9600baud.net
- **Feed**: https://bsky.app/profile/did:plc:ua3bkfmmdsfeljfevkma3btq/feed/genx-music

---

## Local Development

### Setup

```bash
# Clone and setup
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Edit with your settings
```

### Environment Variables

```bash
# Server
HOSTNAME=your-domain.com
SERVICE_DID=did:web:your-domain.com
FEED_URI=  # Leave empty until first publish

# Bluesky (create app password at Settings → App Passwords)
HANDLE=your-handle.bsky.social
PASSWORD=xxxx-xxxx-xxxx-xxxx  # App password

# Feed metadata
RECORD_NAME=my-feed
DISPLAY_NAME=My Custom Feed
DESCRIPTION=Description of your feed
AVATAR_PATH=./path/to/avatar.png  # Optional

# Options
IGNORE_ARCHIVED_POSTS=true
IGNORE_REPLY_POSTS=false
```

### Development Workflow

```bash
# Run dev server
flask --debug run

# Customize filter
nano server/data_filter.py

# Publish feed (first time)
python publish_feed.py
# Copy FEED_URI to .env

# Update feed metadata
python publish_feed.py  # Re-run after changing .env
```

---

## Docker Deployment

### Configuration Files

**Dockerfile**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt waitress
COPY . .
EXPOSE 8080
CMD ["waitress-serve", "--listen=0.0.0.0:8080", "server.app:app"]
```

**docker-compose.yml**
```yaml
services:
  feedgen:
    build: .
    container_name: bsky-feedgen
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./feed_database.db:/app/feed_database.db
    ports:
      - "127.0.0.1:8080:8080"
    networks:
      - feedgen-network

networks:
  feedgen-network:
    driver: bridge
```

**.dockerignore**
```
.env
*.db
.git
.venv
__pycache__
*.pyc
```

### Server Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install docker-compose-plugin

# Deploy
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
nano .env  # Add production config

# Initialize database
touch feed_database.db
chmod 666 feed_database.db

# Start
docker-compose up -d --build
docker-compose logs -f
```

### Nginx Configuration

`/etc/nginx/sites-available/feedgen`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/feedgen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### SSL Certificate

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo certbot renew --dry-run
```

---

## CI/CD Pipeline

### 1. SSH Key Setup

```bash
# Generate deployment key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-server-ip
ssh -i ~/.ssh/github_deploy user@your-server-ip  # Test
```

### 2. GitHub Secrets

Repository → Settings → Secrets and variables → Actions

Add:
- `SERVER_HOST` - Server IP/domain
- `SERVER_USER` - Deployment username
- `SSH_PRIVATE_KEY` - Contents of `~/.ssh/github_deploy`

### 3. GitHub Actions Workflow

`.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /home/feedgen/bluesky-feed-generator
            git pull origin main
            docker-compose down
            docker-compose up -d --build
            docker-compose logs --tail=50
```

### 4. Environment Protection

GitHub Repository → Settings → Environments → New environment

- Name: `production`
- Enable "Required reviewers"
- Add yourself as reviewer

This requires manual approval for deployments.

---

## Security

### Firewall

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### SSH Hardening

Edit `/etc/ssh/sshd_config`:

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart sshd
```

### Git Security

Never commit:
- `.env` - Credentials
- `*.db` - Database
- `.venv/` - Virtual environment

Ensure `.gitignore`:
```
.env
*.db
.venv/
__pycache__/
*.pyc
```

---

## Monitoring

### Logs

```bash
# Real-time
docker-compose logs -f

# Recent
docker-compose logs --tail=100

# Since time
docker-compose logs --since 1h
```

### Container Management

```bash
# Status
docker-compose ps
docker stats bsky-feedgen

# Restart
docker-compose restart

# Rebuild
docker-compose down
docker-compose up -d --build
```

### Test Endpoints

```bash
curl https://your-domain.com/.well-known/did.json
curl https://your-domain.com/xrpc/app.bsky.feed.describeFeedGenerator
curl "https://your-domain.com/xrpc/app.bsky.feed.getFeedSkeleton?feed=YOUR_FEED_URI&limit=10"
```

### Database

```bash
# Backup
cp feed_database.db feed_database.db.backup-$(date +%Y%m%d)

# Size
du -h feed_database.db

# Reset (WARNING: deletes all posts)
docker-compose down
rm feed_database.db
touch feed_database.db
chmod 666 feed_database.db
docker-compose up -d
```

---

## Troubleshooting

### Container Won't Start

```bash
docker-compose logs --tail=50
sudo netstat -tlnp | grep 8080
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database Permissions

```bash
touch feed_database.db
chmod 666 feed_database.db
docker-compose up -d
```

### Environment Variables

```bash
ls -la .env
docker exec bsky-feedgen env | grep HOSTNAME
```

### Wrong Posts in Feed

```bash
git pull origin main
docker-compose down
docker-compose up -d --build
docker exec bsky-feedgen cat server/data_filter.py | head -20
```

### SSL Issues

```bash
sudo certbot renew
sudo certbot certificates
```

### Performance

```bash
docker stats
df -h
docker system prune -a
```

---

## Known Issues

### 1. Post Deletion Bug (FIXED)

**Location:** `server/data_filter.py` line ~180

**Fix:**
```python
# Add .execute()
Post.delete().where(Post.uri.in_(post_uris_to_delete)).execute()
```

### 2. Deprecated datetime.utcnow

**Location:** `database.py` line ~18

**Fix:**
```python
from datetime import datetime, timezone
indexed_at = peewee.DateTimeField(default=lambda: datetime.now(timezone.utc))
```

### 3. False Positive Matches

**Issue:** Common words matching unintended posts

**Solution:** Use context-aware filtering with word boundaries

See README.md for filtering patterns and `server/data_filter.py` for implementation.

---

## Resources

- [README.md](README.md) - Project overview and filter design
- [AT Protocol Docs](https://atproto.com/)
- [Bluesky API](https://docs.bsky.app/)
- [atproto SDK](https://github.com/MarshalX/atproto)
- [Docker Docs](https://docs.docker.com/)

---

**Last Updated:** 2025-12-20
