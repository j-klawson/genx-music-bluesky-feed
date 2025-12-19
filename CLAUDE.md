# Bluesky Feed Generator - Deployment Guide

This guide documents the complete workflow for developing and deploying your custom Bluesky feed generator to a Debian Linux server using GitHub Actions CI/CD.

## Table of Contents

- [Overview](#overview)
- [Initial Setup](#initial-setup)
- [Local Development](#local-development)
- [Server Setup](#server-setup)
- [CI/CD Pipeline](#cicd-pipeline)
- [Security Best Practices](#security-best-practices)
- [Development Workflow](#development-workflow)
- [Monitoring & Troubleshooting](#monitoring--troubleshooting)
- [Known Issues](#known-issues)

---

## Overview

This deployment workflow uses:
- **GitHub** for version control and CI/CD (GitHub Actions)
- **Debian Linux** server for hosting
- **Nginx** as reverse proxy
- **Let's Encrypt** for SSL certificates
- **Systemd** for process management
- **Waitress** as production WSGI server

### Architecture

```
GitHub Push → GitHub Actions → SSH to Server → Deploy → Systemd Restart
Internet → Nginx (HTTPS) → Waitress (Python App) → SQLite DB
```

---

## Initial Setup

### 1. Fork and Clone Repository

```bash
# Clone the repository
git clone https://github.com/MarshalX/bluesky-feed-generator.git my-bsky-feed
cd my-bsky-feed

# Create your own GitHub repository, then:
git remote set-url origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Fix Critical Bug

**IMPORTANT:** There's a bug in `server/data_filter.py` line 91 that prevents post deletion from working.

Edit `server/data_filter.py`:

```python
# BEFORE (line 91):
Post.delete().where(Post.uri.in_(post_uris_to_delete))

# AFTER (add .execute()):
Post.delete().where(Post.uri.in_(post_uris_to_delete)).execute()
```

Commit this fix:
```bash
git add server/data_filter.py
git commit -m "Fix: Add .execute() to post deletion query"
git push
```

---

## Local Development

### Setup Virtual Environment

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
nano .env
```

Required environment variables:
```bash
HOSTNAME=your-domain.com
SERVICE_DID=did:web:your-domain.com
FEED_URI=  # Leave empty until first publish

# Optional settings
IGNORE_ARCHIVED_POSTS=true
IGNORE_REPLY_POSTS=false
```

### Run Development Server

```bash
# Run with auto-reload
flask --debug run

# The server will start on http://localhost:5000
```

### Customize Your Feed

Edit these files to implement your custom feed logic:

1. **`server/data_filter.py`** - Filter posts from the firehose
   ```python
   # Example: Filter for posts containing specific keywords
   if 'python' in record.text.lower():
       posts_to_create.append(post_dict)
   ```

2. **`server/algos/feed.py`** - Feed generation logic
   ```python
   # Customize how posts are ordered and returned
   posts = Post.select().order_by(Post.indexed_at.desc()).limit(limit)
   ```

3. **`server/database.py`** - Add custom fields if needed
   ```python
   class Post(BaseModel):
       uri = peewee.CharField(index=True)
       # Add your custom fields here
   ```

### Publish Your Feed

Once configured and tested locally:

```bash
python publish_feed.py
```

This will:
- Register your feed with Bluesky
- Give you a FEED_URI to add to `.env`
- Make your feed discoverable in the app

---

## Server Setup

### 1. Prepare Debian Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git

# Create deployment user
sudo useradd -m -s /bin/bash feedgen
sudo usermod -aG sudo feedgen  # Optional: only if needed

# Switch to feedgen user
sudo su - feedgen
```

### 2. Clone Repository on Server

```bash
# As feedgen user
cd ~
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git app
cd app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install production server
pip install waitress
```

### 3. Configure Environment on Server

```bash
# Create .env file (DO NOT commit this to git!)
nano .env
```

Add your production configuration:
```bash
HOSTNAME=your-feed-domain.com
SERVICE_DID=did:web:your-feed-domain.com
FEED_URI=at://did:plc:YOUR_DID/app.bsky.feed.generator/YOUR_FEED
IGNORE_ARCHIVED_POSTS=true
IGNORE_REPLY_POSTS=false
```

### 4. Create Systemd Service

Exit to root user and create service file:

```bash
sudo nano /etc/systemd/system/bsky-feedgen.service
```

Add this configuration:

```ini
[Unit]
Description=Bluesky Feed Generator
After=network.target

[Service]
Type=simple
User=feedgen
WorkingDirectory=/home/feedgen/app
Environment="PATH=/home/feedgen/app/.venv/bin"
ExecStart=/home/feedgen/app/.venv/bin/waitress-serve --listen=127.0.0.1:8080 server.app:app
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bsky-feedgen
sudo systemctl start bsky-feedgen
sudo systemctl status bsky-feedgen
```

### 5. Configure Nginx

Create nginx site configuration:

```bash
sudo nano /etc/nginx/sites-available/feedgen
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name your-feed-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/feedgen /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

### 6. Setup SSL Certificate

```bash
sudo certbot --nginx -d your-feed-domain.com

# Follow prompts to configure HTTPS
# Certbot will automatically modify your nginx config
```

Test auto-renewal:
```bash
sudo certbot renew --dry-run
```

---

## CI/CD Pipeline

### 1. Generate SSH Key for Deployment

On your local machine:

```bash
# Generate dedicated deployment key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy

# Copy public key to server
ssh-copy-id -i ~/.ssh/github_deploy.pub feedgen@your-server-ip

# Test connection
ssh -i ~/.ssh/github_deploy feedgen@your-server-ip
```

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:
- **`SERVER_HOST`**: Your server IP address or domain
- **`SERVER_USER`**: `feedgen`
- **`SSH_PRIVATE_KEY`**: Contents of `~/.ssh/github_deploy` (the private key)

To get the private key:
```bash
cat ~/.ssh/github_deploy
# Copy entire output including BEGIN and END lines
```

### 3. Allow Service Restart Without Password

On the server, allow feedgen user to restart the service:

```bash
sudo visudo -f /etc/sudoers.d/feedgen
```

Add this line:
```
feedgen ALL=(ALL) NOPASSWD: /bin/systemctl restart bsky-feedgen
```

Save and exit.

### 4. Create GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Debian Server

on:
  push:
    branches: [ main ]
  workflow_dispatch:  # Allow manual trigger

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Deploy to production server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /home/feedgen/app

            # Pull latest code
            git pull origin main

            # Activate virtual environment and update dependencies
            source .venv/bin/activate
            pip install -r requirements.txt

            # Restart service
            sudo systemctl restart bsky-feedgen

            # Check status
            sleep 3
            sudo systemctl status bsky-feedgen --no-pager
```

Commit and push:

```bash
git add .github/workflows/deploy.yml
git commit -m "Add CI/CD deployment workflow"
git push
```

### 5. Test Deployment

Push any change to the main branch and watch the Actions tab in GitHub to see the deployment run.

---

## Security Best Practices

### Firewall Configuration

```bash
# Enable UFW firewall
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Check status
sudo ufw status
```

### SSH Hardening

Edit SSH configuration:

```bash
sudo nano /etc/ssh/sshd_config
```

Recommended settings:
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

### Git Security

**NEVER commit these files:**
- `.env` - Contains sensitive credentials
- `*.db` - Database files
- `.venv/` - Virtual environment

Ensure `.gitignore` contains:
```
.env
*.db
.venv/
__pycache__/
*.pyc
```

### Environment Variables

- Store all secrets in `.env` on the server only
- Never commit `.env` to version control
- Use GitHub Secrets for deployment credentials
- Rotate SSH keys periodically

---

## Development Workflow

### Daily Development Cycle

```bash
# 1. Create feature branch
git checkout -b feature/my-new-filter

# 2. Make changes to feed logic
nano server/data_filter.py

# 3. Test locally
source .venv/bin/activate
flask --debug run

# 4. Commit changes
git add .
git commit -m "Add: Filter for posts about technology"

# 5. Push to GitHub
git push origin feature/my-new-filter

# 6. Create Pull Request on GitHub
# Review changes, then merge to main

# 7. Automatic deployment triggers via GitHub Actions
```

### Updating Feed Metadata

To update your feed's name, description, or avatar:

```bash
# Edit .env with new values
nano .env

# Re-run publish script
python publish_feed.py
```

### Database Management

```bash
# On server: backup database
cp /home/feedgen/app/feed_database.db /home/feedgen/backups/feed_$(date +%Y%m%d).db

# Reset database (WARNING: deletes all data)
rm feed_database.db
python -c "from server.database import db; db.create_tables()"
```

---

## Monitoring & Troubleshooting

### View Logs

```bash
# Real-time logs
sudo journalctl -u bsky-feedgen -f

# Recent logs
sudo journalctl -u bsky-feedgen -n 100

# Logs from specific time
sudo journalctl -u bsky-feedgen --since "1 hour ago"
```

### Check Service Status

```bash
# Service status
sudo systemctl status bsky-feedgen

# Restart service
sudo systemctl restart bsky-feedgen

# Stop service
sudo systemctl stop bsky-feedgen

# Start service
sudo systemctl start bsky-feedgen
```

### Test Endpoints

```bash
# Test DID endpoint
curl https://your-domain.com/.well-known/did.json

# Test feed generator description
curl https://your-domain.com/xrpc/app.bsky.feed.describeFeedGenerator

# Test feed skeleton (replace with your feed URI)
curl "https://your-domain.com/xrpc/app.bsky.feed.getFeedSkeleton?feed=YOUR_FEED_URI&limit=10"
```

### Common Issues

**Service won't start:**
```bash
# Check logs for errors
sudo journalctl -u bsky-feedgen -n 50

# Check if port is already in use
sudo netstat -tlnp | grep 8080

# Verify virtual environment
/home/feedgen/app/.venv/bin/python --version
```

**Database locked errors:**
```bash
# Check if multiple instances are running
ps aux | grep python

# Kill stale processes
sudo systemctl restart bsky-feedgen
```

**Firehose connection issues:**
```bash
# Check network connectivity
ping bsky.network

# Check firewall isn't blocking outbound connections
sudo ufw status
```

**SSL certificate issues:**
```bash
# Renew certificate manually
sudo certbot renew

# Check certificate expiry
sudo certbot certificates
```

### Performance Monitoring

```bash
# Check resource usage
htop

# Monitor database size
du -h /home/feedgen/app/feed_database.db

# Check disk space
df -h
```

---

## Known Issues

### 1. Post Deletion Bug (FIXED)

**Issue:** Posts are not removed from the database when deleted from Bluesky.

**Location:** `server/data_filter.py:91`

**Fix:** Add `.execute()` to the delete query:
```python
Post.delete().where(Post.uri.in_(post_uris_to_delete)).execute()
```

### 2. Deprecated datetime.utcnow

**Issue:** `database.py:18` uses deprecated `datetime.utcnow`

**Impact:** Low - will work but shows deprecation warning in Python 3.12+

**Recommended fix:**
```python
# Replace
indexed_at = peewee.DateTimeField(default=datetime.utcnow)

# With
indexed_at = peewee.DateTimeField(default=lambda: datetime.now(timezone.utc))
```

### 3. Thread Safety

**Issue:** Database operations happen in firehose callback thread

**Impact:** Medium - potential race conditions under high load

**Mitigation:** Current implementation uses `db.atomic()` which helps, but for high-traffic feeds, consider using a message queue.

---

## Additional Resources

- [AT Protocol Documentation](https://atproto.com/)
- [Bluesky API Docs](https://docs.bsky.app/)
- [Python atproto SDK](https://github.com/MarshalX/atproto)
- [Feed Generator Overview](https://github.com/bluesky-social/feed-generator#overview)

---

## Support & Contributing

- Report issues on GitHub
- Submit pull requests for improvements
- Update this documentation as you learn more

---

**Last Updated:** 2025-12-19
**Maintainer:** Your Name
**License:** MIT
