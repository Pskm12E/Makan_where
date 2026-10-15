"""Attributed business details and explicitly illustrative catalogue photography."""
import json
import re
from functools import lru_cache
from urllib.parse import urlsplit
from flask import abort
from sqlalchemy import select
from .config import BASE_DIR
from .models import db, FoodPlace
from .services import field

PHOTO_HOSTS = {'images.unsplash.com', 'upload.wikimedia.org'}


def safe_url(value, *, image=False):
    if image and re.fullmatch(r'/assets/[A-Za-z0-9_/-]+\.(?:jpg|jpeg|png|webp)', value or ''):
        return value
    try:
        url = urlsplit(value)
        if (url.scheme not in ({'https'} if image else {'https', 'http'}) or not url.hostname
                or url.username or url.password or any(c.isspace() or ord(c) < 32 for c in value)
                or '\\' in value or (image and url.hostname not in PHOTO_HOSTS)):
            return ''
        return value
    except (TypeError, ValueError):
        return ''


@lru_cache(maxsize=1)
def photos():
    return json.loads((BASE_DIR / 'data/enrichment/illustrative_photos.json').read_text(encoding='utf-8'))


def fallback_photo(place):
    cuisine = ' '.join(c.cuisine_name.lower() for c in place.cuisines)
    category = place.category.category_name.lower()
    name = place.place_name.casefold()
    if 'burger' in cuisine or name in {"mcdonald's", 'mcdonald’s', 'burger king'}:
        key = 'burger'
    elif any(t in cuisine for t in ['vegetarian', 'vegan', 'salad']): key = 'vegetarian'
    elif any(t in cuisine for t in ['japanese', 'sushi']): key = 'japanese'
    elif any(t in cuisine for t in ['indian', 'curry', 'malay', 'indonesian']): key = 'curry'
    elif any(t in cuisine for t in ['coffee', 'tea', 'dessert', 'ice cream']) or category == 'cafe': key = 'coffee'
    else: key = 'food'
    return photos()[key]


def listing_details(place):
    details = place.enrichment or {}
    fallback = fallback_photo(place)
    actual = safe_url(place.image_url, image=True)
    # Existing sample images were illustrative before this feature too.
    kind = details.get('photoKind', 'illustrative') if actual else 'illustrative'
    photo = {'url': actual or fallback['image'], 'kind': kind,
             'credit': details.get('photoCredit') or ('Unsplash' if actual else fallback['credit']),
             'sourceUrl': details.get('photoSourceUrl') or ('https://unsplash.com/license' if actual else fallback['sourceUrl']),
             'alt': f'{place.place_name} photo' if kind == 'venue' else ('Illustrative photo' if actual else fallback['alt'])}
    return {'image': photo['url'], 'photo': photo, 'customImage': place.image_url,
            'website': details.get('website', ''), 'menuUrl': details.get('menuUrl', ''),
            'phone': details.get('phone', ''), 'detailsSourceUrl': details.get('sourceUrl', ''),
            'detailSources': details.get('fieldSources', {}),
            'detailsObservedAt': details.get('observedAt', ''),
            'menuHighlights': details.get('menuHighlights', []),
            'menuHighlightsSource': details.get('menuHighlightsSource', ''),
            'menuLinkKind': details.get('menuLinkKind', 'venue'),
            'description': place.description or f'{place.place_name} is listed as a {place.category.category_name.lower()} in {place.area.area_name}. Explore its location and available menu information below.'}


def save_details(place, data):
    details = dict(place.enrichment or {})
    for key in ['website', 'menuUrl', 'photoSourceUrl']:
        if key in data:
            value = field(data, key, 1000, False)
            if value and not safe_url(value): abort(400, f'{key} must be a valid HTTP or HTTPS link.')
            details[key] = value
    for key in ['phone', 'photoCredit']:
        if key in data: details[key] = field(data, key, 100, False)
    if 'phone' in data and details['phone'] and not re.fullmatch(r'[+0-9 ()/;.,-]{3,100}', details['phone']):
        abort(400, 'Enter a valid public business phone number.')
    if 'photoKind' in data:
        if data['photoKind'] not in {'venue', 'illustrative'}: abort(400, 'Choose venue or illustrative for photoKind.')
        details['photoKind'] = data['photoKind']
    if 'image' in data:
        value = field(data, 'image', 1000, False)
        if value and not safe_url(value, image=True):
            abort(400, 'Use an HTTPS Unsplash/Wikimedia image or an image under /assets/.')
        if value and (not details.get('photoSourceUrl') or not details.get('photoCredit')):
            abort(400, 'Provide the photo source link and credit before saving an image.')
        place.image_url = value
    if 'description' in data: place.description = field(data, 'description', 2000, False)
    if 'openingHours' in data: place.opening_hours = field(data, 'openingHours', 1000, False) or None
    # Keep a per-field override, including deliberate blanks, so imports cannot
    # silently restore a link/photo/contact removed by an administrator.
    edited = set(details.get('editedFields', []))
    edited.update(k for k in ['website', 'menuUrl', 'phone'] if k in data)
    if edited: details['editedFields'] = sorted(edited)
    if 'menuUrl' in data and details.get('menuUrl') != (place.enrichment or {}).get('menuUrl'):
        details.pop('menuHighlights', None)
        details.pop('menuHighlightsSource', None)
        details['menuLinkKind'] = 'venue'
    place.enrichment = details


def enrich_listings(*, apply=False):
    root = BASE_DIR / 'data/enrichment'
    osm = json.loads((root / 'osm_business_details.json').read_text(encoding='utf-8'))
    source = {r['sourceId']: r for r in osm['places']}
    chains = json.loads((root / 'chain_links.json').read_text(encoding='utf-8'))
    chain_map = {name: chain for chain in chains for name in chain['names']}
    counts = {'placesChanged': 0, 'website': 0, 'menuUrl': 0, 'phone': 0, 'menuHighlights': 0, 'invalidSkipped': 0}
    for place in db.session.scalars(select(FoodPlace).where(FoodPlace.archived_at.is_(None), FoodPlace.is_sample.is_(False))):
        before = dict(place.enrichment or {})
        details = dict(before)
        row = source.get(place.source_id) if place.source_name == 'OpenStreetMap' else None
        candidates = []
        if row and row['name'] == place.place_name:
            candidates.append({**row, 'observedAt': osm['sourceTimestamp']})
        if place.place_name in chain_map:
            candidates.append({**chain_map[place.place_name], 'menuLinkKind': 'chain'})
        for candidate in candidates:
            for key in ['website', 'menuUrl', 'phone']:
                if details.get(key) or key in details.get('editedFields', []): continue
                value = candidate.get(key, '').strip()
                if not value: continue
                if (len(value) > (100 if key == 'phone' else 1000) or
                    (key != 'phone' and not safe_url(value)) or
                    (key == 'phone' and not re.fullmatch(r'[+0-9 ()/;.,-]{3,100}', value))):
                    counts['invalidSkipped'] += 1
                    continue
                details[key] = value
                details.setdefault('fieldSources', {})
                details['fieldSources'] = {**details['fieldSources'], key: candidate['sourceUrl']}
                details['sourceUrl'] = candidate['sourceUrl']
                details['observedAt'] = candidate['observedAt']
                if key == 'menuUrl': details['menuLinkKind'] = candidate.get('menuLinkKind', 'venue')
                counts[key] += 1
            if candidate.get('menuHighlights') and not details.get('menuHighlights') and 'menuUrl' not in details.get('editedFields', []):
                details['menuHighlights'] = candidate['menuHighlights']
                details['menuHighlightsSource'] = candidate['sourceUrl']
                counts['menuHighlights'] += 1
        if details != before:
            counts['placesChanged'] += 1
            if apply: place.enrichment = details
    if apply: db.session.commit()
    return {**counts, 'applied': apply, 'illustrativePhotos': 'Automatic for every listing without a supplied photo'}
