# Generation X Music Feed for Bluesky

An example implementation ofa a custom Bluesky feed generator that surfaces posts about Generation X era music - grunge, alternative rock, shoegaze, britpop, and 90s music culture.

**Live Feed:** [Generation X Music on Bluesky](https://bsky.app/profile/did:plc:ua3bkfmmdsfeljfevkma3btq/feed/genx-music)

**Feed URL:** https://bsky-feeds.9600baud.net

## What Gets Included

This feed uses simple regular expressions and and filtering logic to build a feed. This still leads to a lot of false positives and would need work for a more accurate content feed. 

### Band & Artist Matches
- **Clear matches**: Nirvana, Pearl Jam, Soundgarden, Radiohead, Smashing Pumpkins, Pixies, Sonic Youth, and 60+ other bands
- **Ambiguous matches**: Bands with common English names (Blur, Hole, Garbage, Ride, No Doubt) only match when paired with music context words

### Genre & Era Terms
- **Genres**: Grunge, shoegaze, britpop, trip-hop, post-punk, college rock, lo-fi
- **Era terms**: "90s music", "90s rock", "generation x music", "nineties alternative"

### Smart Features

**Acronym Expansion** - Automatically expands common band acronyms:
- NIN → Nine Inch Nails
- STP → Stone Temple Pilots
- RHCP → Red Hot Chili Peppers
- RATM → Rage Against the Machine
- AIC → Alice in Chains

**Context-Aware Filtering** - Generic words like "alternative", "punk", "blur", or "no doubt" only match when music context is present (words like "music", "band", "album", "song", "concert", etc.)

**Word Boundary Matching** - Prevents false matches (e.g., "blur" won't match "blurry photo")

**Content Exclusions** - Filters out political content and off-topic posts

## Filter Logic

The filtering algorithm works in stages:

1. **Synonym expansion** - Expands acronyms to full band names
2. **Political filter** - Excludes posts containing political keywords 
3. **Music detection** - Checks for:
   - Clear band/genre matches (high confidence)
   - Ambiguous matches + music context (validated matches)
   - Era-specific terms (90s music, etc.)

Posts must match at least one criterion to be included in the feed.

## Technical Details

Built with:
- [AT Protocol SDK for Python](https://github.com/MarshalX/atproto)
- Python 3.11+
- SQLite database
- Docker for deployment
- Waitress WSGI server

Based on the [atproto Feed Generator](https://github.com/MarshalX/bluesky-feed-generator) template.

## Customizing for Your Own Feed

Want to create your own topic-based feed? This codebase is a great starting point.

### Quick Start

1. **Clone and setup**
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
   cd YOUR_REPO
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure your feed**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials and feed details
   ```

3. **Customize the filter**

   Edit `server/data_filter.py` to implement your filtering logic. The current implementation provides:
   - `has_word_match()` - Word boundary matching helper
   - Synonym/acronym expansion
   - Context-aware filtering
   - Content exclusions

4. **Test locally**
   ```bash
   flask --debug run
   # Server runs on http://localhost:5000
   ```

5. **Publish your feed**
   ```bash
   python publish_feed.py
   # Copy the FEED_URI to your .env file
   ```

### Filter Customization Tips

- **Clear vs Ambiguous**: Separate unique terms from common English words
- **Context validation**: Require topic-specific context for ambiguous terms
- **Synonym maps**: Expand abbreviations and acronyms before matching
- **Exclusion lists**: Filter out off-topic content early
- **Word boundaries**: Use regex `\b` patterns to prevent substring matches

See `server/data_filter.py` for the complete implementation example.

## Deployment

For production deployment with Docker, Nginx, SSL, and CI/CD:

See **[INSTALL.md](INSTALL.md)** for comprehensive installation documentation including:
- Docker containerization
- GitHub Actions CI/CD
- Server setup and security
- Monitoring and troubleshooting
- Database management

## Architecture

```
Bluesky Firehose → Filter Logic → SQLite DB → Feed API → Bluesky App
                     ↓
              - Synonym expansion
              - Content exclusions
              - Context validation
              - Word boundary matching
```

## Development

### Project Structure

```
├── server/
│   ├── data_filter.py      # Feed filtering logic
│   ├── algos/              # Feed generation algorithms
│   ├── database.py         # Database models
│   └── app.py             # Flask application
├── publish_feed.py         # Feed publishing script
├── .env                    # Configuration (not in git)
├── INSTALL.md             # Installation guide
├── CLAUDE.md              # Deployment documentation
└── README.md              # This file
```

### Running Tests

```bash
# Run development server with debugging
flask --debug run

# Monitor logs
docker-compose logs -f

# Test endpoints
curl http://localhost:5000/.well-known/did.json
```

### Database Management

```bash
# Backup database
cp feed_database.db feed_database.db.backup-$(date +%Y%m%d)

# Reset database (clears all posts)
rm feed_database.db
touch feed_database.db
chmod 666 feed_database.db
```

## Known Issues

See INSTALL.md for detailed issue tracking and solutions.

## Contributing

This is a personal feed generator project, but feel free to:
- Fork it for your own topic-based feed
- Report issues or bugs
- Submit pull requests with improvements

## License

MIT

## Credits

- Built with [AT Protocol SDK for Python](https://github.com/MarshalX/atproto)
- Based on [bluesky-feed-generator](https://github.com/MarshalX/bluesky-feed-generator) template
- Deployed at [bsky-feeds.9600baud.net](https://bsky-feeds.9600baud.net)

## Support

For technical questions about:
- Installation: See [INSTALL.md](INSTALL.md)
- Deployment: See [CLAUDE.md](CLAUDE.md)
- AT Protocol: See [AT Protocol Documentation](https://atproto.com/)
- Feed Generators: See [Bluesky Feed Generator Docs](https://github.com/bluesky-social/feed-generator)
