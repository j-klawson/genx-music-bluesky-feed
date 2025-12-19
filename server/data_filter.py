import datetime
import re

from collections import defaultdict

from atproto import models

from server import config
from server.logger import logger
from server.database import db, Post


def has_word_match(text: str, words: list[str]) -> bool:
    """Check if any word from the list appears as a whole word in text."""
    if not words:
        return False
    pattern = r'\b(' + '|'.join(re.escape(word) for word in words) + r')\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def is_archive_post(record: 'models.AppBskyFeedPost.Record') -> bool:
    # Sometimes users will import old posts from Twitter/X which con flood a feed with
    # old posts. Unfortunately, the only way to test for this is to look an old
    # created_at date. However, there are other reasons why a post might have an old
    # date, such as firehose or firehose consumer outages. It is up to you, the feed
    # creator to weigh the pros and cons, amd and optionally include this function in
    # your filter conditions, and adjust the threshold to your liking.
    #
    # See https://github.com/MarshalX/bluesky-feed-generator/pull/21

    archived_threshold = datetime.timedelta(days=1)
    created_at = datetime.datetime.fromisoformat(record.created_at)
    now = datetime.datetime.now(datetime.UTC)

    return now - created_at > archived_threshold


def should_ignore_post(created_post: dict) -> bool:
    record = created_post['record']
    uri = created_post['uri']

    if config.IGNORE_ARCHIVED_POSTS and is_archive_post(record):
        logger.debug(f'Ignoring archived post: {uri}')
        return True

    if config.IGNORE_REPLY_POSTS and record.reply:
        logger.debug(f'Ignoring reply post: {uri}')
        return True

    return False


def operations_callback(ops: defaultdict) -> None:
    # Here we can filter, process, run ML classification, etc.
    # After our feed alg we can save posts into our DB
    # Also, we should process deleted posts to remove them from our DB and keep it in sync

    # for example, let's create our custom feed that will contain all posts that contains 'python' related text

    posts_to_create = []
    for created_post in ops[models.ids.AppBskyFeedPost]['created']:
        author = created_post['author']
        record = created_post['record']

        post_with_images = isinstance(record.embed, models.AppBskyEmbedImages.Main)
        post_with_video = isinstance(record.embed, models.AppBskyEmbedVideo.Main)
        inlined_text = record.text.replace('\n', ' ')

        # print all texts just as demo that data stream works
        logger.debug(
            f'NEW POST '
            f'[CREATED_AT={record.created_at}]'
            f'[AUTHOR={author}]'
            f'[WITH_IMAGE={post_with_images}]'
            f'[WITH_VIDEO={post_with_video}]'
            f': {inlined_text}'
        )

        if should_ignore_post(created_post):
            continue

        # Gen X music filter with word boundary matching and context awareness
        text_lower = record.text.lower()

        # Expand acronyms/synonyms to full band names
        synonym_map = {
            'nin': 'nine inch nails',
            'stp': 'stone temple pilots',
            'rhcp': 'red hot chili peppers',
            'ratm': 'rage against the machine',
            'aic': 'alice in chains'
        }

        # Replace synonyms with their full names (using word boundaries)
        for acronym, full_name in synonym_map.items():
            text_lower = re.sub(r'\b' + re.escape(acronym) + r'\b', full_name, text_lower)

        # High-confidence matches - unambiguous band names
        clear_bands = [
            'nirvana', 'pearl jam', 'soundgarden', 'alice in chains',
            'stone temple pilots', 'radiohead', 'smashing pumpkins',
            'foo fighters', 'r.e.m.', 'rem', 'pixies', 'sonic youth',
            'pavement', 'dinosaur jr', 'rage against the machine',
            'nine inch nails', 'green day', 'the offspring',
            'blink-182', 'my bloody valentine', 'slowdive',
            'the breeders', 'pj harvey', 'bjork',
            'butthole surfers', 'portishead', 'massive attack',
            'red hot chili peppers', 'guided by voices', 'sleater-kinney',
            'toad the wet sprocket', 'neutral milk hotel',
            'presidents of the united states of america',
            'the jesus and mary chain', 'marcy playground', 'cocteau twins',
            'the dandy warhols', 'mercury rev', 'archers of loaf',
            'the brian jonestown massacre', 'soul coughing', 'primitive radio gods'
        ]

        # Ambiguous terms that need music context (common English words)
        ambiguous_bands = [
            'blur', 'hole', 'garbage', 'ride', 'pulp', 'suede',
            'beck', 'weezer', 'oasis', 'tricky', 'no doubt'
        ]

        # Clear genre indicators
        clear_genres = [
            'grunge', 'shoegaze', 'britpop', 'trip-hop', 'post-punk',
            'college rock', 'lo-fi'
        ]

        # Ambiguous genres that need context
        ambiguous_genres = [
            'alternative rock', 'alternative', 'punk rock', 'punk',
            'indie rock', 'indie'
        ]

        # Decade/era specific terms (high confidence)
        era_terms = [
            'gen x music', 'generation x music', '90s music', '90s rock',
            '90s alternative', '90s grunge', '90s indie', '90s punk',
            'nineties music', 'nineties rock'
        ]

        # Music context words to validate ambiguous matches
        music_context = [
            'music', 'band', 'album', 'song', 'concert', 'tour', 'show',
            'listening', 'playlist', 'spotify', 'bandcamp', 'track',
            'lyrics', 'musician', 'singer', 'guitar', 'drums'
        ]

        # Check matches using word boundaries
        has_clear_band = has_word_match(text_lower, clear_bands)
        has_clear_genre = has_word_match(text_lower, clear_genres)
        has_era_term = has_word_match(text_lower, era_terms)
        has_music_context = has_word_match(text_lower, music_context)
        has_ambiguous = has_word_match(text_lower, ambiguous_bands + ambiguous_genres)

        # Filter logic: clear matches OR (ambiguous matches WITH music context)
        is_genx_music = (
            has_clear_band or
            has_clear_genre or
            has_era_term or
            (has_ambiguous and has_music_context)
        )

        if is_genx_music:
            reply_root = reply_parent = None
            if record.reply:
                reply_root = record.reply.root.uri
                reply_parent = record.reply.parent.uri

            post_dict = {
                'uri': created_post['uri'],
                'cid': created_post['cid'],
                'reply_parent': reply_parent,
                'reply_root': reply_root,
            }
            posts_to_create.append(post_dict)

    posts_to_delete = ops[models.ids.AppBskyFeedPost]['deleted']
    if posts_to_delete:
        post_uris_to_delete = [post['uri'] for post in posts_to_delete]
        Post.delete().where(Post.uri.in_(post_uris_to_delete)).execute()
        logger.debug(f'Deleted from feed: {len(post_uris_to_delete)}')

    if posts_to_create:
        with db.atomic():
            for post_dict in posts_to_create:
                Post.create(**post_dict)
        logger.debug(f'Added to feed: {len(posts_to_create)}')
