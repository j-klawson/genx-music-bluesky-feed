# Installation Guide - Docker Deployment

This guide covers deploying the Bluesky Feed Generator to a Debian Linux server using Docker.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Server Preparation](#server-preparation)
- [Deployment](#deployment)
- [Nginx Configuration](#nginx-configuration)
- [SSL Certificate](#ssl-certificate)
- [GitHub Actions Setup](#github-actions-setup)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Backup & Rollback](#backup--rollback)

---

## Prerequisites

### Required
- Debian Linux server with root/sudo access
- Docker and Docker Compose installed
- Domain name pointing to your server
- SSH key-based authentication configured
- Nginx installed

### Verify Docker Installation
```bash
docker --version
docker-compose --version  # or: docker compose version
```

If Docker is not installed:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose (if not included)
sudo apt update
sudo apt install docker-compose-plugin

# Add user to docker group (optional, allows docker without sudo)
sudo usermod -aG docker $USER
# Log out and back in for this to take effect
```

---

## Server Preparation

### 1. Create Deployment Directory
```bash
# Choose your deployment location
sudo mkdir -p /opt/bsky-feedgen
sudo chown $USER:$USER /opt/bsky-feedgen
cd /opt/bsky-feedgen
```

### 2. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git .
```

### 3. Create Environment File
**IMPORTANT**: Never commit the `.env` file to git!

```bash
cp .env.example .env
nano .env
```

Configure your `.env` file:
```bash
# Server configuration
HOSTNAME=your-domain.com
SERVICE_DID=did:web:your-domain.com

# After publishing feed (leave empty for now)
FEED_URI=

# Bluesky credentials (for publishing feed)
HANDLE=your-handle.bsky.social
PASSWORD=your-app-password-here

# Feed metadata
RECORD_NAME=genx-music
DISPLAY_NAME=Gen X Music
DESCRIPTION=Posts about Generation X era music - grunge, alternative rock, punk, and 90s music culture

# Optional settings
IGNORE_ARCHIVED_POSTS=true
IGNORE_REPLY_POSTS=false
ACCEPTS_INTERACTIONS=false
IS_VIDEO_FEED=false
```

Ensure `.env` is not tracked by git:
```bash
git update-index --assume-unchanged .env
```

---

## Deployment

### Build and Start Container
```bash
cd /opt/bsky-feedgen

# Build and start in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f

# Check container status
docker ps
```

The application will be running on `localhost:8080`.

### Verify Container is Running
```bash
# Check container status
docker ps | grep bsky-feedgen

# View recent logs
docker-compose logs --tail=100

# Test local endpoint
curl http://localhost:8080/
```

---

## Nginx Configuration

### 1. Create Nginx Site Configuration
```bash
sudo nano /etc/nginx/sites-available/feedgen
```

Add this configuration (replace `your-domain.com`):
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

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 2. Enable Site
```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/feedgen /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### 3. Test HTTP Access
```bash
curl http://your-domain.com/
```

---

## SSL Certificate

### Install Certbot (if not already installed)
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

### Obtain SSL Certificate
```bash
sudo certbot --nginx -d your-domain.com
```

Follow the prompts:
- Enter your email address
- Agree to terms of service
- Choose whether to redirect HTTP to HTTPS (recommended: yes)

### Test Auto-Renewal
```bash
sudo certbot renew --dry-run
```

Certificates auto-renew via systemd timer. Check status:
```bash
sudo systemctl status certbot.timer
```

### Verify HTTPS
```bash
curl https://your-domain.com/.well-known/did.json
```

---

## GitHub Actions Setup

This enables automatic deployment when you push to the main branch.

### 1. Generate SSH Key for Deployment
On your **local machine**:
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy
```

### 2. Add Public Key to Server
```bash
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-server-ip

# Or manually:
cat ~/.ssh/github_deploy.pub
# Copy the output and add to ~/.ssh/authorized_keys on server
```

### 3. Add Secrets to GitHub Repository
Go to: **GitHub Repository → Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:
- **`SERVER_HOST`**: Your server IP or domain
- **`SERVER_USER`**: Your SSH username
- **`SSH_PRIVATE_KEY`**: Contents of `~/.ssh/github_deploy` (the private key)

To get the private key:
```bash
cat ~/.ssh/github_deploy
# Copy the entire output including BEGIN and END lines
```

### 4. Create Production Environment
Go to: **GitHub Repository → Settings → Environments → New environment**

1. Name it `production`
2. Add protection rules:
   - Check "Required reviewers"
   - Add yourself as a reviewer
3. Save protection rules

This ensures you must manually approve each deployment.

### 5. Update Workflow File
Edit `.github/workflows/deploy.yml` and update the deployment path:
```yaml
script: |
  cd /opt/bsky-feedgen  # Update this to your actual path
  git pull origin main
  docker-compose down
  docker-compose up -d --build
  docker-compose logs --tail=50
```

### 6. Configure Branch Protection (Optional)
Go to: **GitHub Repository → Settings → Branches → Add rule**

For branch `main`:
- Require pull request reviews before merging
- Require status checks to pass
- Restrict who can push to branch (optional)

---

## Monitoring

### View Container Logs
```bash
# Real-time logs
docker-compose logs -f feedgen

# Last 100 lines
docker-compose logs --tail=100 feedgen

# Since specific time
docker-compose logs --since 1h feedgen
```

### Check Container Status
```bash
# Container health
docker ps

# Resource usage
docker stats bsky-feedgen

# Container details
docker inspect bsky-feedgen
```

### Database Management
```bash
# Check database size
ls -lh /opt/bsky-feedgen/feed_database.db

# Backup database
cp feed_database.db feed_database.db.backup-$(date +%Y%m%d)
```

### Test Feed Endpoints
```bash
# DID endpoint
curl https://your-domain.com/.well-known/did.json

# Feed generator description
curl https://your-domain.com/xrpc/app.bsky.feed.describeFeedGenerator

# Feed skeleton (replace FEED_URI)
curl "https://your-domain.com/xrpc/app.bsky.feed.getFeedSkeleton?feed=YOUR_FEED_URI&limit=10"
```

---

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker-compose logs feedgen

# Check if port is in use
sudo netstat -tlnp | grep 8080

# Rebuild container
docker-compose down
docker-compose up -d --build
```

### Database Locked Errors
```bash
# Stop container
docker-compose down

# Check for stale processes
ps aux | grep python

# Start fresh
docker-compose up -d
```

### High Memory Usage
```bash
# Check container resources
docker stats bsky-feedgen

# Restart container
docker-compose restart
```

### SSL Certificate Issues
```bash
# Renew manually
sudo certbot renew

# Check expiration
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal
```

### Deployment Fails
```bash
# SSH to server and check
cd /opt/bsky-feedgen
git status
docker-compose ps

# Manual deployment
git pull origin main
docker-compose down
docker-compose up -d --build
```

---

## Backup & Rollback

### Database Backup
```bash
# Automated backup script
cat > /opt/bsky-feedgen/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/bsky-feedgen/backups"
mkdir -p $BACKUP_DIR
cp feed_database.db "$BACKUP_DIR/feed_$(date +%Y%m%d_%H%M%S).db"

# Keep only last 7 days
find $BACKUP_DIR -name "feed_*.db" -mtime +7 -delete
EOF

chmod +x /opt/bsky-feedgen/backup.sh

# Add to cron (daily at 2am)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/bsky-feedgen/backup.sh") | crontab -
```

### Restore Database
```bash
docker-compose down
cp backups/feed_YYYYMMDD_HHMMSS.db feed_database.db
docker-compose up -d
```

### Rollback to Previous Version
```bash
cd /opt/bsky-feedgen

# Option 1: Git revert (preferred)
git log --oneline -n 5  # Find commit to revert
git revert COMMIT_HASH
git push  # Triggers auto-deployment

# Option 2: Hard reset (use cautiously)
git reset --hard HEAD~1
docker-compose down
docker-compose up -d --build

# Option 3: Quick restart
docker-compose restart
```

---

## Security Best Practices

### Firewall Configuration
```bash
# Install UFW
sudo apt install ufw

# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Regular Maintenance
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Clean up Docker
docker system prune -a

# Review logs for suspicious activity
docker-compose logs --since 24h | grep -i error
```

### SSH Hardening
Edit `/etc/ssh/sshd_config`:
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

---

## Useful Commands Reference

### Docker Management
```bash
# Start service
docker-compose up -d

# Stop service
docker-compose down

# Restart service
docker-compose restart

# Rebuild and restart
docker-compose up -d --build

# View logs
docker-compose logs -f

# Shell into container
docker exec -it bsky-feedgen /bin/bash
```

### Git Operations
```bash
# Check status
git status

# Pull latest changes
git pull origin main

# View commit history
git log --oneline -n 10

# Discard local changes
git reset --hard origin/main
```

### Service Status
```bash
# Nginx status
sudo systemctl status nginx

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Certbot timer
sudo systemctl status certbot.timer
```

---

## Support

For issues:
1. Check container logs: `docker-compose logs -f`
2. Review this troubleshooting guide
3. Check GitHub Issues
4. Verify environment variables in `.env`

---

**Last Updated**: 2025-12-20
