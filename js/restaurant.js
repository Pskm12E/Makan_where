let placeContent = [];
let selectedPlaceId = Number(new URLSearchParams(location.search).get('id'));
let reviewPage = 1;
const reviewsPerPage = 10;

document.addEventListener('DOMContentLoaded', async () => {
  if (!await appReady) return;
  await withAction(null, async () => {
    await reloadRestaurant();
    if (foodFinderData.some(item => item.id === selectedPlaceId)) recordDiscovery('place_view', selectedPlaceId);
  });
});

async function reloadRestaurant() {
  placeContent = await apiAll(`/content?place_id=${selectedPlaceId}`, 'content');
  await refreshPlaces();
  renderRestaurantDetail();
}

function contentCard(item) {
  const user = getCurrentUser();
  return `<li class="review-item" data-content="${item.id}">
    <div class="meta-row"><strong>${escapeHtml(item.reviewer)} ${item.isDemo ? '<small class="tag">Demonstration data</small>' : ''}</strong><span>${item.rating ? (item.isExample ? 'Example rating: ' : '') + '★'.repeat(item.rating) + '☆'.repeat(5 - item.rating) : new Date(item.createdAt).toLocaleDateString('en-SG')}</span></div>
    ${item.title ? `<h4>${escapeHtml(item.title)}</h4>` : ''}<p class="user-content">${escapeHtml(item.text)}</p>
    ${item.dishes.map(link => `<p><small>${escapeHtml(link.name || foodFinderData.find(p => p.id === selectedPlaceId)?.menu.find(d => d.id === link.id)?.name)}: ${escapeHtml(link.feedback || '')}</small></p>`).join('')}
    <div class="content-actions"><button class="secondary-btn" data-vote="${item.id}">${item.upvoted ? '♥' : '♡'} Helpful (${item.upvoteCount})</button>
    ${user ? `<button class="secondary-btn" data-report="${item.id}">Report</button>` : ''}
    ${user?.id === item.authorId ? `<button class="secondary-btn" data-edit-content="${item.id}">Edit</button>` : ''}
    ${user && (user.id === item.authorId || user.role === 'admin') ? `<button class="danger-btn" data-remove-content="${item.id}">Remove</button>` : ''}</div>
  </li>`;
}

function renderRestaurantDetail() {
  const container = document.getElementById('restaurantDetail');
  const restaurant = foodFinderData.find(item => item.id === selectedPlaceId);
  if (!restaurant) { container.innerHTML = '<div class="empty-state">Restaurant not found.</div>'; return; }
  const newestFirst = (a, b) => new Date(b.createdAt) - new Date(a.createdAt) || b.id - a.id;
  const reviews = placeContent.filter(item => item.kind === 'review').sort(newestFirst);
  const exampleReviews = reviews.filter(item => item.isExample).length;
  const reviewSummary = `${reviews.length - exampleReviews} reviews${exampleReviews ? ` · ${exampleReviews} example reviews` : ''}`;
  const reviewPages = Math.max(1, Math.ceil(reviews.length / reviewsPerPage));
  reviewPage = Math.min(reviewPage, reviewPages);
  const visibleReviews = reviews.slice((reviewPage - 1) * reviewsPerPage, reviewPage * reviewsPerPage);
  const threads = placeContent.filter(item => item.kind === 'thread').sort(newestFirst);
  const user = getCurrentUser();
  container.innerHTML = `
    <div class="detail-hero">
      ${photoMarkup(restaurant, true)}
      <div class="detail-hero-overlay"><p class="eyebrow light">${escapeHtml(restaurant.category)}</p><h1>${escapeHtml(restaurant.name)}</h1><div class="rating-row"><span class="star">★</span><span>${ratingLabel(restaurant.rating)} · ${reviewSummary}</span></div></div>
      <button class="small-action" id="detailFavouriteBtn">${getFavouriteStatus(restaurant.id) ? 'Remove favourite' : 'Add favourite'}</button>
    </div>
    <nav class="detail-shortcuts" aria-label="Venue sections"><a class="secondary-btn" href="#venueMenu">Menu</a><a class="secondary-btn" href="#venueReviews">Reviews (${reviews.length})</a><a class="secondary-btn" href="#reviewForm">Write a review</a><a class="secondary-btn" href="#venueDiscussions">Discussions (${threads.length})</a></nav>
    <div class="detail-grid"><div>
      ${listingLabel(restaurant)}
      <div class="detail-meta"><div><strong>Address:</strong> ${escapeHtml(restaurant.address === 'Address not listed' ? 'Use the map pin for this listing' : restaurant.address)}</div><div><strong>Area:</strong> ${escapeHtml(restaurant.area)}</div>${restaurant.hygieneGrade !== 'Not provided' ? `<div><strong>Hygiene grade:</strong> ${escapeHtml(restaurant.hygieneGrade)}</div>` : ''}${restaurant.price !== null ? `<div><strong>From:</strong> ${priceLabel(restaurant.price)}</div>` : ''}</div>
      ${venueLinks(restaurant)}
      ${restaurant.phone ? `<p><strong>Business phone:</strong> ${escapeHtml(restaurant.phone)}</p>` : ''}
      ${Object.keys(restaurant.detailSources || {}).length ? `<p class="source-detail">Business sources: ${Object.entries(restaurant.detailSources).map(([key, url]) => externalLink(url, key === 'menuUrl' ? 'menu' : key)).join(' · ')}</p>` : ''}
      <p class="source-detail">${restaurant.photo.kind === 'illustrative' ? 'Illustrative food photo; not a photograph of this outlet or its dishes. ' : ''}${externalLink(restaurant.photo.sourceUrl, restaurant.photo.credit)}</p>
      ${sourceLink(restaurant) ? `<p>${sourceLink(restaurant)} · Retrieved ${escapeHtml(new Date(restaurant.sourceFetchedAt).toLocaleDateString('en-SG'))}</p>` : ''}
      ${restaurant.openingHours ? `<p><strong>Opening hours (as listed):</strong> ${escapeHtml(restaurant.openingHours)}</p>` : ''}
      <div class="tag-row">${restaurant.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>
      <p>${escapeHtml(restaurant.description)}</p><h3 id="venueMenu">Menu</h3>${restaurant.hasReferenceMenu ? '<p class="menu-reference-note">Chain reference menu. These are published chain prices; this outlet’s selection, availability and prices may differ. Check the linked source before ordering.</p>' : ''}${user?.role === 'admin' ? `<p><a href="admin.html?menu=${restaurant.id}">Manage or import this menu</a></p>` : ''}<ul class="menu-list" id="venueMenuItems">${restaurant.menu.length ? restaurant.menu.map(d => `<li class="menu-item"><div class="meta-row"><strong>${escapeHtml(d.name)}</strong><span>${priceLabel(d.price)}</span></div><div class="meta-row"><span>${escapeHtml(d.dietary)}</span><span>${d.isReference ? 'Chain reference' : (d.availability ? 'Available' : 'Unavailable')}</span></div>${d.description ? `<p>${escapeHtml(d.description)}</p>` : ''}${menuSourceMarkup(d)}</li>`).join('') : menuHighlightsMarkup(restaurant)}</ul>${restaurant.menu.length > 8 ? `<button type="button" class="secondary-btn" id="showAllMenuItems" aria-expanded="false" aria-controls="venueMenuItems">Show all ${restaurant.menu.length} menu items</button>` : ''}
      ${user?.role === 'admin' ? `<h3>Add a dish</h3><form class="review-form" id="dishForm"><label>Dish name<input name="name" maxlength="150" required></label><label>Price (SGD)<input name="price" type="number" min="0" step="0.01" required></label><label>Dietary information<input name="dietary" maxlength="80"></label><button type="submit" class="small-action">Save dish</button></form>` : ''}
    </div><div><h3 id="venueReviews">Reviews</h3>${exampleReviews ? '<p class="menu-reference-note">Example reviews are fictional and excluded from this venue’s rating and rankings.</p>' : ''}<ul class="review-list">${reviews.length ? visibleReviews.map(contentCard).join('') : '<li class="review-item">No reviews yet. Be the first to share your experience.</li>'}</ul>
    ${reviewPages > 1 ? `<nav class="review-pagination" aria-label="Review pages"><button class="secondary-btn" id="previousReviews" ${reviewPage === 1 ? 'disabled' : ''}>Previous reviews</button><span aria-live="polite">Page ${reviewPage} of ${reviewPages}</span><button class="secondary-btn" id="nextReviews" ${reviewPage === reviewPages ? 'disabled' : ''}>Next reviews</button></nav>` : ''}
    ${user ? `<h3>Write a review</h3><form class="review-form" id="reviewForm"><label>Title<input name="title" maxlength="150" required></label><label>Rating<select name="rating">${[5,4,3,2,1].map(n => `<option value="${n}">${n} stars</option>`).join('')}</select></label><label>Your review<textarea name="text" maxlength="5000" required></textarea></label><label>Dish (optional)<select name="dish"><option value="">No specific dish</option>${restaurant.menu.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('')}</select></label><label>Dish feedback (optional)<input name="feedback" maxlength="1000"></label><button type="submit" class="small-action">Submit review</button></form>` : '<p><a href="auth.html?mode=login">Log in</a> to write a review.</p>'}
    </div></div>
    <section class="discussion-section" id="venueDiscussions"><h2>Food discussions</h2>${threads.length ? threads.map(thread => `<article class="discussion"><ul class="review-list">${contentCard(thread)}</ul><ul class="review-list discussion-replies">${placeContent.filter(c => c.threadId === thread.id).map(contentCard).join('')}</ul>${user ? `<form class="review-form reply-form" data-thread="${thread.id}"><label>Reply<textarea name="text" maxlength="5000" required></textarea></label><button type="submit" class="small-action">Reply</button></form>` : ''}</article>`).join('') : '<p>No discussions yet.</p>'}
    ${user ? '<form class="review-form" id="threadForm"><h3>Start a discussion</h3><label>Title<input name="title" maxlength="150" required></label><label>Message<textarea name="text" maxlength="5000" required></textarea></label><button type="submit" class="small-action">Post discussion</button></form>' : ''}</section>`;

  document.getElementById('showAllMenuItems')?.addEventListener('click', event => {
    const expanded = document.getElementById('venueMenuItems').classList.toggle('expanded');
    event.currentTarget.setAttribute('aria-expanded', String(expanded));
    event.currentTarget.textContent = expanded ? 'Show fewer menu items' : `Show all ${restaurant.menu.length} menu items`;
  });
  document.getElementById('detailFavouriteBtn').addEventListener('click', event => withAction(event.currentTarget, async () => {
    if (!requireLoginForFavourite()) return;
    await toggleFavourite(selectedPlaceId); renderRestaurantDetail();
  }));
  // The whole feed remains reachable without an unbounded review column.
  for (const [id, direction] of [['previousReviews', -1], ['nextReviews', 1]]) {
    document.getElementById(id)?.addEventListener('click', () => {
      reviewPage += direction;
      renderRestaurantDetail();
      document.getElementById('venueReviews').scrollIntoView({block: 'start'});
    });
  }
  if (!user) {
    container.querySelector('a[href="#reviewForm"]').href = `auth.html?mode=login&next=${encodeURIComponent('restaurant.html?id=' + selectedPlaceId)}`;
  }
  for (const kind of ['review', 'thread']) {
    document.getElementById(`${kind}Form`)?.addEventListener('submit', event => {
      event.preventDefault();
      const form = event.currentTarget;
      withAction(form.querySelector('button'), async () => {
        const data = Object.fromEntries(new FormData(form));
        const body = {kind, placeId:selectedPlaceId, title:data.title, text:data.text};
        if (kind === 'review') { body.rating = Number(data.rating); body.dishes = data.dish ? [{id:Number(data.dish),feedback:data.feedback}] : []; }
        await api('/content', {method:'POST', body});
        reviewPage = 1;
        await reloadRestaurant();
        document.getElementById(kind === 'review' ? 'venueReviews' : 'venueDiscussions').scrollIntoView({block:'start'});
      });
    });
  }
  container.querySelectorAll('.reply-form').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    withAction(form.querySelector('button'), async () => {
      await api('/content', {method:'POST', body:{kind:'comment',placeId:selectedPlaceId,threadId:Number(form.dataset.thread),text:new FormData(form).get('text')}});
      await reloadRestaurant();
    });
  }));
  document.getElementById('dishForm')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    withAction(form.querySelector('button'), async () => {
      await api(`/admin/establishments/${selectedPlaceId}/dishes`, {method:'POST',body:Object.fromEntries(new FormData(form))});
      await reloadRestaurant();
    });
  });
  container.querySelectorAll('[data-vote],[data-report],[data-remove-content],[data-edit-content]').forEach(button => button.addEventListener('click', event => withAction(event.currentTarget, async () => {
    if (!requireLoginForFavourite()) return;
    const id = Number(button.dataset.vote || button.dataset.report || button.dataset.removeContent || button.dataset.editContent);
    const item = placeContent.find(c => c.id === id);
    if (button.dataset.vote) await api(`/content/${id}/upvote`, {method:item.upvoted ? 'DELETE' : 'PUT'});
    if (button.dataset.report) {
      const reason = prompt('Why are you reporting this content?');
      if (!reason?.trim()) return;
      await api(`/content/${id}/reports`, {method:'POST',body:{reason}});
      button.textContent = 'Reported'; return;
    }
    if (button.dataset.removeContent) {
      if (!confirm('Remove this content from public view?')) return;
      await api(`/content/${id}`, {method:'DELETE'});
    }
    if (button.dataset.editContent) {
      const text = prompt('Edit your message:', item.text);
      if (!text?.trim()) return;
      await api(`/content/${id}`, {method:'PATCH',body:{text,title:item.title,rating:item.rating}});
    }
    await reloadRestaurant();
  })));
}

function menuHighlightsMarkup(place) {
  if (!place.menuHighlights?.length) return `<li class="menu-item">${place.menuUrl ? externalLink(place.menuUrl, 'Open the menu from this listing’s source') : 'Menu details have not been published here yet. Check the venue website or contact the business.'}</li>`;
  return `<li class="menu-item"><strong>From the published chain menu</strong><p>Selection may differ by outlet. Prices are not published in this source; check the linked menu before ordering.</p><div class="menu-highlights">${place.menuHighlights.map(name => `<span>${escapeHtml(name)}</span>`).join('')}</div>${externalLink(place.menuHighlightsSource || place.menuUrl, 'View the full source menu')}</li>`;
}
