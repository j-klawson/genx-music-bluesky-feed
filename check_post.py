#!/usr/bin/env python3
"""Check posts in the database that might be false positives."""

from server.database import db, Post

# Connect to database
db.connect()

# Get recent posts
posts = Post.select().order_by(Post.indexed_at.desc()).limit(20)

print("Recent posts in feed database:\n")
for post in posts:
    print(f"URI: {post.uri}")
    print(f"CID: {post.cid}")
    print(f"Indexed at: {post.indexed_at}")
    print("-" * 80)

db.close()
