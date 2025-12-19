# Bluesky Feed Generator - Docker Deployment Guide

This guide documents the complete workflow for developing and deploying your custom Bluesky feed generator to a Debian Linux server using Docker and GitHub Actions CI/CD.

## Table of Contents

- [Overview](#overview)
- [Initial Setup](#initial-setup)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Security Best Practices](#security-best-practices)
- [Development Workflow](#development-workflow)
- [Monitoring & Troubleshooting](#monitoring--troubleshooting)
- [Known Issues](#known-issues)

---

## Overview

This deployment workflow uses:
- **Docker** for containerization
- **Docker Compose** for orchestration
- **GitHub** for version control and CI/CD (GitHub Actions)
- **Debian Linux** server for hosting
- **Nginx** as reverse proxy
- **Let's Encrypt** for SSL certificates
- **Waitress** as production WSGI server

### Architecture

```
GitHub Push → GitHub Actions → SSH to Server → Docker Rebuild → Container Restart
Internet → Nginx (HTTPS) → Docker Container (Waitress) → SQLite DB
```

### Why Docker?

- **Isolation**: App runs in its own container, no system Python conflicts
- **Consistency**: Same environment locally and in production
- **Easy rollback**: Simple to restart or roll back to previous versions
- **Auto-restart**: Container restarts automatically if it crashes
- **Clean deployment**: No need for virtual environments or system packages
- **Easy updates**: Rebuild and restart with one command

### Example Feed

This guide uses the **Gen X Music** feed as a working example:
- **Feed URL**: https://bsky-feeds.9600baud.net
- **Bluesky Feed**: https://bsky.app/profile/did:plc:ua3bkfmmdsfeljfevkma3btq/feed/genx-music
- **Filter**: Posts about Generation X era music (grunge, alternative rock, punk, 90s bands)

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

# Bluesky credentials for publishing (create app password first!)
HANDLE=your-handle.bsky.social  # WITHOUT the @ symbol
PASSWORD=xxxx-xxxx-xxxx-xxxx     # App password from Bluesky settings

# Feed metadata
RECORD_NAME=my-feed
DISPLAY_NAME=My Custom Feed
DESCRIPTION=Description of what your feed filters for

# Optional settings
IGNORE_ARCHIVED_POSTS=true
IGNORE_REPLY_POSTS=false
```

### Create Bluesky App Password

Before publishing your feed:
1. Open Bluesky app or web
2. Go to Settings → Privacy and Security → App Passwords
3. Click "Add App Password"
4. Name it "Feed Generator"
5. Copy the generated password (you can't view it again!)
6. Add it to your `.env` file

### Run Development Server

```bash
# Run with auto-reload
flask --debug run

# The server will start on http://localhost:5000
```

### Customize Your Feed

Edit `server/data_filter.py` to implement your custom feed logic.

**Example: Gen X Music Feed with Context-Aware Filtering**

The Gen X Music feed uses word boundary matching and context awareness to reduce false positives:

```python
import re

def has_word_match(text: str, words: list[str]) -> bool:
    """Check if any word appears as a whole word in text."""
    if not words:
        return False
    pattern = r'\b(' + '|'.join(re.escape(word) for word in words) + r')\b'
    return bool(re.search(pattern, text, re.IGNORECASE))

# High-confidence matches - unambiguous band names
clear_bands = ['nirvana', 'pearl jam', 'soundgarden', 'radiohead']
clear_genres = ['grunge', 'shoegaze', 'britpop']

# Ambiguous terms that need music context
ambiguous_bands = ['blur', 'hole', 'garbage', 'ride']
ambiguous_genres = ['alternative', 'indie', 'punk']

# Music context words
music_context = ['music', 'band', 'album', 'song', 'concert', 'spotify']

# Filter logic: clear matches OR (ambiguous matches WITH context)
has_clear_band = has_word_match(text_lower, clear_bands)
has_clear_genre = has_word_match(text_lower, clear_genres)
has_music_context = has_word_match(text_lower, music_context)
has_ambiguous = has_word_match(text_lower, ambiguous_bands + ambiguous_genres)

is_genx_music = (
    has_clear_band or
    has_clear_genre or
    (has_ambiguous and has_music_context)
)

if is_genx_music:
    posts_to_create.append(post_dict)
```

**Key improvements:**
- **Word boundaries**: Prevents "blur" from matching "blurry photo"
- **Context awareness**: Generic terms like "alternative" only match when music context words are present
- **Clear vs ambiguous**: Separates unambiguous indicators from common words that need validation

### Publish Your Feed

Once configured and tested locally:

```bash
python publish_feed.py
```

This will:
- Register your feed with Bluesky
- Give you a FEED_URI to add to `.env`
- Make your feed discoverable in the app

**Important:** After getting the FEED_URI, add it to `.env` and restart your development server.

---

## Docker Deployment

For comprehensive Docker deployment instructions, see **[SERVER-SETUP.md](SERVER-SETUP.md)**.

### Quick Start

#### 1. Create Docker Configuration Files

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir waitress
COPY . .
EXPOSE 8080
CMD ["waitress-serve", "--listen=0.0.0.0:8080", "server.app:app"]
```

**docker-compose.yml:**
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

**.dockerignore:**
```
.env
*.db
.git
.venv
__pycache__
*.pyc
```

#### 2. Server Prerequisites

On your Debian server:
```bash
# Install Docker if not already installed
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt update
sudo apt install docker-compose-plugin

# Add user to docker group (optional)
sudo usermod -aG docker $USER
```

#### 3. Deploy to Server

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO

# Create .env file (DO NOT commit to git!)
nano .env
# Add your production configuration

# Create empty database file
touch feed_database.db
chmod 666 feed_database.db

# Build and start container
docker-compose up -d --build

# View logs
docker-compose logs -f
```

#### 4. Configure Nginx

Create `/etc/nginx/sites-available/feedgen`:
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

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/feedgen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 5. Setup SSL Certificate

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo certbot renew --dry-run  # Test auto-renewal
```

---

## CI/CD Pipeline

### 1. Generate SSH Key for Deployment

On your local machine:

```bash
# Generate dedicated deployment key
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy

# Copy public key to server
ssh-copy-id -i ~/.ssh/github_deploy.pub user@your-server-ip

# Test connection
ssh -i ~/.ssh/github_deploy user@your-server-ip
```

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:
- **`SERVER_HOST`**: Your server IP address or domain
- **`SERVER_USER`**: Your deployment username
- **`SSH_PRIVATE_KEY`**: Contents of `~/.ssh/github_deploy` (the private key)

To get the private key:
```bash
cat ~/.ssh/github_deploy
# Copy entire output including BEGIN and END lines
```

### 3. Create GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval

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

### 4. Configure Environment Protection

**Important:** Protect your production environment from unauthorized deployments:

1. Go to: **GitHub Repository → Settings → Environments → New environment**
2. Name it `production`
3. Add protection rules:
   - Check "Required reviewers"
   - Add yourself as a reviewer
4. Save protection rules

This ensures you must manually approve each deployment, even on public repos.

### 5. Configure Branch Protection (Optional)

Go to: **GitHub Repository → Settings → Branches → Add rule**

For branch `main`:
- Require pull request reviews before merging
- Require status checks to pass
- Restrict who can push to branch

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

### Protecting Public Repositories

Multi-layered protection:
1. **GitHub Actions triggers only on push to main** - PRs don't trigger deployments
2. **Environment protection with manual approval** - Even main branch pushes require your approval
3. **Branch protection rules** - Prevent unauthorized merges to main
4. **SSH key isolation** - Deployment key stored only in GitHub Secrets
5. **You control merges** - Review all PRs before merging

---

## Development Workflow

### Daily Development Cycle

```bash
# 1. Create feature branch
git checkout -b feature/improve-filter

# 2. Make changes to feed logic
nano server/data_filter.py

# 3. Test locally
source .venv/bin/activate
flask --debug run

# 4. Commit changes
git add .
git commit -m "Improve: Refine music filter keywords"

# 5. Push to GitHub
git push origin feature/improve-filter

# 6. Create Pull Request on GitHub
# Review changes, then merge to main

# 7. Approve deployment in GitHub Actions
# GitHub Actions will automatically deploy via Docker rebuild
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
cp feed_database.db feed_database.db.backup-$(date +%Y%m%d)

# Reset database (WARNING: deletes all data)
docker-compose down
rm feed_database.db
touch feed_database.db
chmod 666 feed_database.db
docker-compose up -d
```

---

## Monitoring & Troubleshooting

### View Logs

```bash
# Real-time logs
docker-compose logs -f

# Recent logs
docker-compose logs --tail=100

# Logs from specific service
docker-compose logs -f feedgen

# Logs since specific time
docker-compose logs --since 1h
```

### Check Container Status

```bash
# Container status
docker ps

# Container details
docker-compose ps

# Resource usage
docker stats bsky-feedgen

# Restart container
docker-compose restart

# Stop and remove container
docker-compose down

# Rebuild and restart
docker-compose up -d --build
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

**Container won't start:**
```bash
# Check logs for errors
docker-compose logs --tail=50

# Check if port is already in use
sudo netstat -tlnp | grep 8080

# Rebuild container from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**Database permission errors:**
```bash
# Create database file before starting container
touch feed_database.db
chmod 666 feed_database.db
docker-compose up -d
```

**Environment variables not loading:**
```bash
# Verify .env file exists in same directory as docker-compose.yml
ls -la .env

# Check variables are loaded in container
docker exec bsky-feedgen env | grep HOSTNAME
```

**Feed showing old/wrong posts:**
```bash
# Server may be running old container image
# Pull latest code and rebuild
git pull origin main
docker-compose down
docker-compose up -d --build

# Check if new code is deployed
docker exec bsky-feedgen cat server/data_filter.py | grep "your-keyword"
```

**Firehose connection issues:**
```bash
# Check network connectivity
ping bsky.network

# Check container logs for connection errors
docker-compose logs | grep -i error

# Restart container
docker-compose restart
```

**SSL certificate issues:**
```bash
# Renew certificate manually
sudo certbot renew

# Check certificate expiry
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal
```

### Performance Monitoring

```bash
# Check resource usage
docker stats

# Monitor database size
du -h feed_database.db

# Check disk space
df -h

# Clean up unused Docker resources
docker system prune -a
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

### 2. Filter Accuracy Problem (FIXED)

**Issue:** Generic keywords can match posts that aren't about your intended topic.

**Example:** For the Gen X Music feed, words like "alternative", "punk", "indie", "blur", "hole", "garbage" are common English words that appear in non-music contexts.

**Impact:** Feed captures false positives - posts that match keywords but aren't relevant.

**Solution (Implemented):** The current filter uses word boundary matching and context awareness:
```python
import re

def has_word_match(text: str, words: list[str]) -> bool:
    """Check if any word appears as a whole word in text."""
    pattern = r'\b(' + '|'.join(re.escape(word) for word in words) + r')\b'
    return bool(re.search(pattern, text, re.IGNORECASE))

# Separate clear indicators from ambiguous terms
clear_bands = ['nirvana', 'pearl jam', 'radiohead']
ambiguous_bands = ['blur', 'hole', 'garbage']
music_context = ['music', 'band', 'album', 'song']

# Require context for ambiguous matches
has_clear = has_word_match(text, clear_bands)
has_ambiguous = has_word_match(text, ambiguous_bands)
has_context = has_word_match(text, music_context)

is_match = has_clear or (has_ambiguous and has_context)
```

**Testing:** Always test your filter locally with `flask --debug run` and monitor the captured posts before deploying to production.

### 3. Deprecated datetime.utcnow

**Issue:** `database.py:18` uses deprecated `datetime.utcnow`

**Impact:** Low - will work but shows deprecation warning in Python 3.12+

**Recommended fix:**
```python
# Replace
indexed_at = peewee.DateTimeField(default=datetime.utcnow)

# With
from datetime import datetime, timezone
indexed_at = peewee.DateTimeField(default=lambda: datetime.now(timezone.utc))
```

### 4. Thread Safety

**Issue:** Database operations happen in firehose callback thread

**Impact:** Medium - potential race conditions under high load

**Mitigation:** Current implementation uses `db.atomic()` which helps, but for high-traffic feeds, consider using a message queue.

---

## Additional Resources

- [SERVER-SETUP.md](SERVER-SETUP.md) - Comprehensive Docker deployment guide
- [AT Protocol Documentation](https://atproto.com/)
- [Bluesky API Docs](https://docs.bsky.app/)
- [Python atproto SDK](https://github.com/MarshalX/atproto)
- [Feed Generator Overview](https://github.com/bluesky-social/feed-generator#overview)
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

---

## Support & Contributing

- Report issues on GitHub
- Submit pull requests for improvements
- Update this documentation as you learn more

---

**Last Updated:** 2025-12-19
**License:** MIT
