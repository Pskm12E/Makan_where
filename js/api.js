let currentUser = null;
let favouriteIds = [];
let csrfToken = '';
let foodFinderData = [];
let reviewsData = [];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function imageUrl(value) {
  if (/^\/assets\/[A-Za-z0-9_/-]+\.(jpg|jpeg|png|webp)$/.test(value || '')) return value;
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && ['images.unsplash.com', 'upload.wikimedia.org'].includes(url.hostname) && !url.username && !url.password) {
      return url.href.replace(/["'()<>]/g, char => encodeURIComponent(char).replace(/'/g, '%27'));
    }
  } catch (_) { /* Use the known fallback for missing/invalid images. */ }
  return '/assets/place-placeholder.svg';
}

function listingLabel(place) {
  return (place.isSample ? '<span class="tag">Sample listing</span>' : '') +
    (place.hasReferenceMenu ? '<span class="tag">Chain reference menu</span>' : '');
}

function externalLink(url, label, className = '') {
  try {
    const parsed = new URL(url);
    if (['https:', 'http:'].includes(parsed.protocol) && !parsed.username && !parsed.password) return `<a class="${className}" href="${escapeHtml(parsed.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
  } catch (_) {}
  return '';
}

function photoMarkup(place, hero = false) {
  const caption = place.photo?.kind === 'venue' ? 'Venue photo' : 'Illustrative photo';
  return `<img class="listing-photo" src="${imageUrl(place.image)}" alt="${escapeHtml(place.photo?.alt || caption)}" loading="${hero ? 'eager' : 'lazy'}" decoding="async" referrerpolicy="no-referrer"><small class="photo-caption">${externalLink(place.photo?.sourceUrl, caption) || caption}</small>`;
}

// Real IMG elements provide alt text, lazy loading and a reliable fallback if
// a remote photo is deleted. CSP does not allow inline onerror handlers.
document.addEventListener('error', event => {
  const img = event.target;
  if (img instanceof HTMLImageElement && img.matches('.listing-photo, .admin-row-photo, .admin-photo-preview') && !img.dataset.failed) {
    img.dataset.failed = 'true';
    img.src = '/assets/place-placeholder.svg';
    img.alt = 'Photo temporarily unavailable';
    const caption = img.parentElement.querySelector('.photo-caption');
    if (caption) caption.textContent = 'Photo temporarily unavailable';
  }
}, true);

function cataloguePrice(place) {
  return place.price === null ? (place.menuUrl ? 'View linked menu' : 'Explore listing') : `From ${priceLabel(place.price)}`;
}

function venueLinks(place) {
  let links = externalLink(place.website, 'Website', 'secondary-btn') + externalLink(place.menuUrl, place.menuLinkKind === 'chain' ? 'Official chain menu' : 'Menu from source', 'secondary-btn');
  if (Number.isFinite(place.latitude) && Number.isFinite(place.longitude)) links += externalLink(`https://www.openstreetmap.org/?mlat=${place.latitude}&mlon=${place.longitude}#map=18/${place.latitude}/${place.longitude}`, 'View map', 'secondary-btn');
  return `<div class="venue-links">${links}</div>`;
}

function menuSourceMarkup(dish) {
  if (!dish.sourceName) return '';
  let source = escapeHtml(dish.sourceName);
  try {
    const url = new URL(dish.sourceUrl);
    if (url.protocol === 'https:' && !url.username && !url.password) source = `<a href="${escapeHtml(url.href)}" target="_blank" rel="noopener noreferrer">${source}</a>`;
  } catch (_) { /* Keep source text when there is no usable URL. */ }
  const date = dish.sourceObservedAt ? ` · observed ${new Date(dish.sourceObservedAt).toLocaleDateString('en-SG')}` : ' · edited by administrator';
  return `<small class="menu-source">${source}${escapeHtml(date)}</small>`;
}

function sourceLink(place) {
  if (place.source === 'OpenStreetMap' && /^https:\/\/www\.openstreetmap\.org\/(node|way|relation)\/\d+$/.test(place.sourceUrl || '')) {
    return `<a href="${escapeHtml(place.sourceUrl)}" target="_blank" rel="noopener noreferrer">View location and source on OpenStreetMap</a>`;
  }
  return '';
}

function priceLabel(value) { return value === null ? 'Price not listed' : `$${value.toFixed(2)}`; }
function ratingLabel(value) { return value ? value.toFixed(1) : 'No reviews yet'; }

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    credentials: 'same-origin', ...options,
    headers: {'Content-Type':'application/json', 'X-CSRF-Token':csrfToken, ...options.headers},
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status}). Please try again.`);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function apiAll(path, key) {
  const items = [];
  let cursor = null;
  do {
    const page = await api(`${path}${path.includes('?') ? '&' : '?'}cursor=${cursor || 0}`);
    items.push(...page[key]);
    cursor = page.nextCursor;
  } while (cursor !== null);
  return items;
}

function showError(error) {
  let notice = document.getElementById('appNotice');
  if (!notice) {
    notice = document.createElement('div');
    notice.id = 'appNotice';
    notice.className = 'app-notice';
    notice.setAttribute('role', 'alert');
    document.body.prepend(notice);
  }
  notice.textContent = error.message || String(error);
}

async function withAction(button, action) {
  if (button?.disabled) return;
  if (button) button.disabled = true;
  try { await action(); } catch (error) { showError(error); }
  finally { if (button) button.disabled = false; }
}

function getCurrentUser() { return currentUser; }
function getFavouriteStatus(id) { return favouriteIds.includes(id); }
async function toggleFavourite(id) {
  if (!requireLoginForFavourite()) return;
  const saved = getFavouriteStatus(id);
  const result = await api(`/favourites/${id}`, {method: saved ? 'DELETE' : 'PUT'});
  favouriteIds = result.favourites;
}

async function refreshPlaces() {
  if (/\/restaurant\.html$/.test(location.pathname)) {
    const id = Number(new URLSearchParams(location.search).get('id'));
    const result = await api(`/establishments/${id}`);
    foodFinderData = [result.establishment];
  } else {
    foodFinderData = (await api('/catalogue')).establishments;
  }
}

function recordDiscovery(type, placeId) {
  // Discovery counts never block browsing; do not collect search terms or location.
  return api('/events', {method:'POST', body:{type, placeId}}).catch(() => {});
}

const appReady = (async () => {
  // Remove the obsolete prototype's plaintext credentials from this origin.
  try { ['makanwheresg-users', 'makanwheresg-session', 'makanwheresg-favourites'].forEach(key => localStorage.removeItem(key)); } catch (_) {}
  const result = await api('/session');
  currentUser = result.user;
  favouriteIds = result.favourites;
  csrfToken = result.csrfToken;
  if (result.sampleCatalogue) {
    const addSampleNotice = () => {
      const note = document.createElement('p');
      note.className = 'sample-notice';
      note.textContent = 'Listings marked “Sample listing” contain demonstration prices and details.';
      document.body.appendChild(note);
    };
    if (document.body) addSampleNotice();
    else document.addEventListener('DOMContentLoaded', addSampleNotice, {once:true});
  }
  const addAttribution = () => {
    const note = document.createElement('p');
    note.className = 'sample-notice';
    note.innerHTML = 'Place data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a> · <a href="https://opendatacommons.org/licenses/odbl/1-0/" target="_blank" rel="noopener noreferrer">ODbL 1.0</a> · <a href="/assets/data/singapore_food_places.csv" download>Download listings CSV</a>. Community data may be incomplete or outdated.';
    document.body.appendChild(note);
  };
  if (document.body) addAttribution();
  else document.addEventListener('DOMContentLoaded', addAttribution, {once:true});
  if (!/\/(auth|settings|analytics|database-lab)\.html$/.test(location.pathname)) await refreshPlaces();
  return true;
})().catch(error => {
  if (document.body) showError(error);
  else document.addEventListener('DOMContentLoaded', () => showError(error), {once:true});
  return false;
});
