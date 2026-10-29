let placeContent = [];
let selectedPlaceId = Number(new URLSearchParams(location.search).get('id'));
let reviewPage = 1;
const reviewsPerPage = 10;
const reportedContentIds = new Set();
let composerPending = false;

document.addEventListener('DOMContentLoaded', async () => {
  if (!await appReady) return;
  await withAction(null, async () => {
    await reloadRestaurant();
    if (foodFinderData.some(item => item.id === selectedPlaceId)) recordDiscovery('place_view', selectedPlaceId);
  });
});

async function reloadRestaurant({submittedForm = null} = {}) {
  const drafts = [...document.querySelectorAll('#restaurantDetail .review-form')].filter(form => form !== submittedForm).map(form => ({
    key: form.id || `reply-${form.dataset.thread}`, fields: [...new FormData(form)], dataset: {...form.dataset}
  }));
  placeContent = await apiAll(`/content?place_id=${selectedPlaceId}`, 'content');
  await refreshPlaces();
  renderRestaurantDetail();
  for (const draft of drafts) {
    const form = [...document.querySelectorAll('#restaurantDetail .review-form')].find(node => (node.id || `reply-${node.dataset.thread}`) === draft.key);
    if (!form) continue;
    for (const [name, value] of draft.fields) if (form.elements.namedItem(name)) form.elements.namedItem(name).value = value;
    Object.assign(form.dataset, draft.dataset);
  }
}

function contentCard(item) {
  const user = getCurrentUser();
  return `<li class="review-item" data-content="${item.id}">
    <div class="meta-row"><strong>${escapeHtml(item.reviewer)} ${item.isDemo ? '<small class="tag">Demonstration data</small>' : ''}</strong><span>${item.rating ? (item.isExample ? 'Example rating: ' : '') + '★'.repeat(item.rating) + '☆'.repeat(5 - item.rating) : new Date(item.createdAt).toLocaleDateString('en-SG')}</span></div>
    <div class="post-copy">${item.title ? `<h4>${escapeHtml(item.title)}</h4>` : ''}<p class="user-content">${escapeHtml(item.text)}</p>
    ${item.dishes.map(link => `<p><small>${escapeHtml(link.name || foodFinderData.find(p => p.id === selectedPlaceId)?.menu.find(d => d.id === link.id)?.name)}: ${escapeHtml(link.feedback || '')}</small></p>`).join('')}
    </div><div class="content-actions"><button type="button" class="secondary-btn" data-vote="${item.id}">${item.upvoted ? '♥' : '♡'} Helpful (${item.upvoteCount})</button>
    ${user ? `<button type="button" class="secondary-btn" data-report="${item.id}" ${reportedContentIds.has(item.id) ? 'disabled' : ''}>${reportedContentIds.has(item.id) ? 'Reported' : 'Report'}</button>` : ''}
    ${user?.id === item.authorId ? `<button type="button" class="secondary-btn" data-edit-content="${item.id}" aria-expanded="false">Edit</button>` : ''}
    ${user && (user.id === item.authorId || user.role === 'admin') ? `<button type="button" class="danger-btn" data-remove-content="${item.id}" aria-expanded="false">Remove</button>` : ''}</div>
  </li>`;
}

function reviewFeedMarkup() {
  const reviews = placeContent.filter(item => item.kind === 'review').sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt) || b.id - a.id);
  const pages = Math.max(1, Math.ceil(reviews.length / reviewsPerPage));
  reviewPage = Math.min(reviewPage, pages);
  const visible = reviews.slice((reviewPage - 1) * reviewsPerPage, reviewPage * reviewsPerPage);
  return `<ul class="review-list">${visible.length ? visible.map(contentCard).join('') : '<li class="review-item">No reviews yet. Be the first to share your experience.</li>'}</ul>
    ${pages > 1 ? `<nav class="review-pagination" aria-label="Review pages"><button type="button" class="secondary-btn" id="previousReviews" ${reviewPage === 1 ? 'disabled' : ''}>Previous reviews</button><span aria-live="polite">Page ${reviewPage} of ${pages}</span><button type="button" class="secondary-btn" id="nextReviews" ${reviewPage === pages ? 'disabled' : ''}>Next reviews</button></nav>` : ''}`;
}

function attachReviewPagination() {
  for (const [id, direction] of [['previousReviews', -1], ['nextReviews', 1]]) {
    document.getElementById(id)?.addEventListener('click', () => {
      if (composerPending || !InlineActions.canLeave()) return;
      reviewPage += direction;
      const region = document.getElementById('reviewFeedRegion');
      region.innerHTML = reviewFeedMarkup();
      attachContentActions(region);
      attachReviewPagination();
      document.getElementById('venueReviews').scrollIntoView({block: 'start'});
    });
  }
}

function contentHeaders(item) {
  // Existing deployments without revisions still accept the same inline UI.
  return Number.isInteger(item.revision) ? {'If-Match': String(item.revision)} : {};
}

function replaceContentCard(item, message, focusAction) {
  const old = document.querySelector(`[data-content="${item.id}"]`);
  if (!old) return;
  const template = document.createElement('template');
  template.innerHTML = contentCard(item);
  const card = template.content.firstElementChild;
  old.replaceWith(card);
  attachContentActions(card);
  if (message) InlineActions.notice(card, message);
  if (focusAction) card.querySelector(`[data-${focusAction}]`)?.focus({preventScroll: true});
}

function refreshVenueSummary() {
  const summary = document.getElementById('venueRatingSummary');
  const reviews = placeContent.filter(item => item.kind === 'review');
  const examples = reviews.filter(item => item.isExample).length;
  const place = foodFinderData.find(item => item.id === selectedPlaceId);
  if (summary && place) summary.textContent = `${ratingLabel(place.rating)} · ${reviews.length - examples} reviews${examples ? ` · ${examples} example reviews` : ''}`;
  document.querySelector('.detail-shortcuts a[href="#venueReviews"]').textContent = `Reviews (${reviews.length})`;
  document.querySelector('.detail-shortcuts a[href="#venueDiscussions"]').textContent = `Discussions (${placeContent.filter(item => item.kind === 'thread').length})`;
}

function attachContentActions(scope) {
  scope.querySelectorAll('[data-vote],[data-report],[data-remove-content],[data-edit-content]').forEach(button => button.addEventListener('click', () => {
    if (composerPending) {
      InlineActions.notice(button.closest('[data-content]'), 'Your post is being saved. Try this action again in a moment.');
      return;
    }
    if (!requireLoginForFavourite()) return;
    const id = Number(button.dataset.vote || button.dataset.report || button.dataset.removeContent || button.dataset.editContent);
    const item = placeContent.find(post => post.id === id);
    const card = button.closest('[data-content]');
    if (!item || !card) return;
    const noun = item.kind === 'comment' ? 'reply' : item.kind === 'thread' ? 'discussion' : 'review';
    if (button.dataset.vote) {
      InlineActions.run(button, card, async () => {
        const result = await api(`/content/${id}/upvote`, {method: item.upvoted ? 'DELETE' : 'PUT'});
        Object.assign(item, result.content);
        replaceContentCard(item, '', 'vote');
      }, 'Updating…');
      return;
    }
    if (button.dataset.editContent) {
      InlineActions.open({host: card, trigger: button, title: `Edit your ${noun}`, editing: true,
        content: `${item.kind !== 'comment' ? `<div class="inline-edit-heading"><label for="__ACTION_ID__-title-input">Title<input id="__ACTION_ID__-title-input" name="title" maxlength="150" value="${escapeHtml(item.title)}" required></label>${item.kind === 'review' ? `<label for="__ACTION_ID__-rating">Rating<select id="__ACTION_ID__-rating" name="rating">${[5,4,3,2,1].map(n => `<option value="${n}" ${n === item.rating ? 'selected' : ''}>${n} ${n === 1 ? 'star' : 'stars'}</option>`).join('')}</select></label>` : ''}</div>` : ''}
          <label for="__ACTION_ID__-text">${item.kind === 'review' ? 'Your review' : 'Message'}<textarea id="__ACTION_ID__-text" name="text" rows="6" maxlength="5000" required>${escapeHtml(item.text)}</textarea></label>
          ${item.dishes.map((dish, index) => `<label for="__ACTION_ID__-dish-${index}">Feedback for ${escapeHtml(dish.name)}<textarea id="__ACTION_ID__-dish-${index}" name="feedback-${index}" data-dish-feedback maxlength="1000" rows="2">${escapeHtml(dish.feedback || '')}</textarea></label>`).join('')}`,
        submitLabel: 'Save changes', busyLabel: 'Saving…',
        submit: form => {
          const fields = form.elements;
          const body = {text: InlineActions.requireValue(fields.namedItem('text'), 'Write a message of up to 5,000 characters.', 5000)};
          if (item.kind !== 'comment') body.title = InlineActions.requireValue(fields.namedItem('title'), 'Enter a title of up to 150 characters.', 150);
          if (item.kind === 'review') body.rating = Number(fields.namedItem('rating').value);
          body.dishes = item.dishes.map((dish, index) => ({id: dish.id, feedback: fields.namedItem(`feedback-${index}`).value.trim()}));
          return api(`/content/${id}`, {method:'PATCH', body, headers:contentHeaders(item)}).then(result => ({body, result}));
        },
        success: ({body, result}) => {
          Object.assign(item, {text: body.text, title: body.title ?? item.title, rating: body.rating ?? item.rating,
            dishes: item.dishes.map((dish, index) => ({...dish, feedback: body.dishes[index].feedback})), revision: result.revision ?? item.revision});
          replaceContentCard(item, 'Changes saved.', 'edit-content');
          refreshPlaces().then(refreshVenueSummary).catch(() => {});
        }});
      return;
    }
    if (button.dataset.report) {
      InlineActions.open({host: card, trigger: button, title: `Report this ${noun}`,
        content: `<label for="__ACTION_ID__-reason">Reason<select id="__ACTION_ID__-reason" name="reason" required><option value="">Choose a reason</option><option>Spam or advertising</option><option>Abusive or offensive content</option><option>Misleading information</option><option>Other</option></select></label><label for="__ACTION_ID__-details">Additional details <small>(optional, required for Other)</small><textarea id="__ACTION_ID__-details" name="details" maxlength="850" rows="3"></textarea></label><p><small>Your report will be sent to the moderation team.</small></p>`,
        submitLabel:'Send report', busyLabel:'Sending…',
        submit: form => {
          const reason = InlineActions.requireValue(form.elements.namedItem('reason'), 'Choose a reason for your report.');
          const details = reason === 'Other' ? InlineActions.requireValue(form.elements.namedItem('details'), 'Tell the moderation team what is wrong with this post.', 850) : form.elements.namedItem('details').value.trim();
          return api(`/content/${id}/reports`, {method:'POST', body:{reason: reason + (details ? `: ${details}` : '')}});
        },
        success: () => {
          reportedContentIds.add(id);
          replaceContentCard(item, 'Report sent. A moderator will review it.');
          document.querySelector(`[data-content="${id}"] .inline-status`)?.focus({preventScroll:true});
        }});
      return;
    }
    InlineActions.open({host:card, trigger:button, title:`Remove this ${noun}?`, destructive:true,
      content:`<p>${item.kind === 'thread' ? 'This discussion and its replies will be hidden from the venue.' : `This ${noun} will be hidden from the venue.`}</p>`,
      submitLabel:`Remove ${noun}`, busyLabel:'Removing…',
      submit: () => api(`/content/${id}`, {method:'DELETE', headers:contentHeaders(item)}),
      success: () => {
        placeContent = placeContent.filter(post => post.id !== id && (item.kind !== 'thread' || post.threadId !== id));
        const target = item.kind === 'thread' ? card.closest('article.discussion') : card;
        const removed = document.createElement(item.kind === 'thread' ? 'p' : 'li');
        removed.className = 'post-removed';
        removed.setAttribute('role','status'); removed.tabIndex = -1;
        removed.textContent = `${noun[0].toUpperCase() + noun.slice(1)} removed.`;
        target.replaceWith(removed); removed.focus({preventScroll:true});
        refreshVenueSummary();
        refreshPlaces().then(refreshVenueSummary).catch(() => {});
      }});
  }));
}

async function submitComposer(form, task, label = 'Posting…') {
  if (composerPending || !InlineActions.canLeave()) return;
  composerPending = true;
  try { await InlineActions.run(form.querySelector('button'), form, task, label); }
  finally { composerPending = false; }
}

function renderRestaurantDetail() {
  const container = document.getElementById('restaurantDetail');
  const restaurant = foodFinderData.find(item => item.id === selectedPlaceId);
  if (!restaurant) { container.innerHTML = '<div class="empty-state">Restaurant not found.</div>'; return; }
  const newestFirst = (a, b) => new Date(b.createdAt) - new Date(a.createdAt) || b.id - a.id;
  const reviews = placeContent.filter(item => item.kind === 'review').sort(newestFirst);
  const exampleReviews = reviews.filter(item => item.isExample).length;
  const reviewSummary = `${reviews.length - exampleReviews} reviews${exampleReviews ? ` · ${exampleReviews} example reviews` : ''}`;
  const threads = placeContent.filter(item => item.kind === 'thread').sort(newestFirst);
  const user = getCurrentUser();
  const menuDishes = [...restaurant.menu].sort((a, b) => a.name.localeCompare(b.name));
  container.innerHTML = `
    <div class="detail-hero">
      ${photoMarkup(restaurant, true)}
      <div class="detail-hero-overlay"><p class="eyebrow light">${escapeHtml(restaurant.category)}</p><h1>${escapeHtml(restaurant.name)}</h1><div class="rating-row"><span class="star">★</span><span id="venueRatingSummary">${ratingLabel(restaurant.rating)} · ${reviewSummary}</span></div></div>
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
      <p>${escapeHtml(restaurant.description)}</p><h3 id="venueMenu">Menu</h3>${restaurant.hasReferenceMenu ? '<p class="menu-reference-note">Chain reference menu. Published chain items; prices are shown only where the source provides them. This outlet’s selection, availability and prices may differ. Check the linked source before ordering.</p>' : ''}${user?.role === 'admin' ? `<p><a href="admin.html?menu=${restaurant.id}">Manage or import this menu</a></p>` : ''}<ul class="menu-list" id="venueMenuItems">${restaurant.menu.length ? menuDishes.map(d => `<li class="menu-item"><div class="meta-row"><strong>${escapeHtml(d.name)}</strong><span>${priceLabel(d.price)}</span></div><div class="meta-row"><span>${escapeHtml(d.dietary)}</span><span>${d.isReference ? 'Chain reference' : (d.availability ? 'Available' : 'Unavailable')}</span></div>${d.description ? `<p>${escapeHtml(d.description)}</p>` : ''}${menuSourceMarkup(d)}</li>`).join('') : menuHighlightsMarkup(restaurant)}</ul>${restaurant.menu.length > 8 ? `<button type="button" class="secondary-btn" id="showAllMenuItems" aria-expanded="false" aria-controls="venueMenuItems">Show all ${restaurant.menu.length} menu items</button>` : ''}
      ${user?.role === 'admin' ? `<h3>Add a dish</h3><form class="review-form" id="dishForm"><label>Dish name<input name="name" maxlength="150" required></label><label>Price (SGD)<input name="price" type="number" min="0" step="0.01" required></label><label>Dietary information<input name="dietary" maxlength="80"></label><button type="submit" class="small-action">Save dish</button></form>` : ''}
    </div><div><h3 id="venueReviews">Reviews</h3>${exampleReviews ? '<p class="menu-reference-note">Example reviews are fictional and excluded from this venue’s rating and rankings.</p>' : ''}<div id="reviewFeedRegion">${reviewFeedMarkup()}</div>
    ${user ? `<h3>Write a review</h3><form class="review-form" id="reviewForm"><label>Title<input name="title" maxlength="150" required></label><label>Rating<select name="rating">${[5,4,3,2,1].map(n => `<option value="${n}">${n} stars</option>`).join('')}</select></label><label>Your review<textarea name="text" maxlength="5000" required></textarea></label><label>Dish (optional)<select name="dish"><option value="">No specific dish</option>${menuDishes.map(d => `<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('')}</select></label><label>Dish feedback (optional)<input name="feedback" maxlength="1000"></label><button type="submit" class="small-action">Submit review</button></form>` : '<p><a href="auth.html?mode=login">Log in</a> to write a review.</p>'}
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
    await toggleFavourite(selectedPlaceId);
    event.target.textContent = getFavouriteStatus(selectedPlaceId) ? 'Remove favourite' : 'Add favourite';
  }));
  attachReviewPagination();
  if (!user) {
    container.querySelector('a[href="#reviewForm"]').href = `auth.html?mode=login&next=${encodeURIComponent('restaurant.html?id=' + selectedPlaceId)}`;
  }
  for (const kind of ['review', 'thread']) {
    document.getElementById(`${kind}Form`)?.addEventListener('submit', event => {
      event.preventDefault();
      const form = event.currentTarget;
      submitComposer(form, async () => {
        const data = Object.fromEntries(new FormData(form));
        const body = {kind, placeId:selectedPlaceId, title:data.title, text:data.text};
        if (kind === 'review') { body.rating = Number(data.rating); body.dishes = data.dish ? [{id:Number(data.dish),feedback:data.feedback}] : []; }
        const signature = JSON.stringify(body);
        if (form.dataset.requestBody !== signature) {
          form.dataset.requestBody = signature;
          form.dataset.requestKey = crypto.randomUUID();
        }
        await api('/content', {method:'POST', body, headers:{'Idempotency-Key':form.dataset.requestKey}});
        reviewPage = 1;
        await reloadRestaurant({submittedForm:form});
        document.getElementById(kind === 'review' ? 'venueReviews' : 'venueDiscussions').scrollIntoView({block:'start'});
      }, 'Posting…');
    });
  }
  container.querySelectorAll('.reply-form').forEach(form => form.addEventListener('submit', event => {
    event.preventDefault();
    submitComposer(form, async () => {
      const body = {kind:'comment',placeId:selectedPlaceId,threadId:Number(form.dataset.thread),text:new FormData(form).get('text')};
      const signature = JSON.stringify(body);
      if (form.dataset.requestBody !== signature) {
        form.dataset.requestBody = signature;
        form.dataset.requestKey = crypto.randomUUID();
      }
      await api('/content', {method:'POST', body, headers:{'Idempotency-Key':form.dataset.requestKey}});
      await reloadRestaurant({submittedForm:form});
    }, 'Posting…');
  }));
  document.getElementById('dishForm')?.addEventListener('submit', event => {
    event.preventDefault();
    const form = event.currentTarget;
    submitComposer(form, async () => {
      await api(`/admin/establishments/${selectedPlaceId}/dishes`, {method:'POST',body:Object.fromEntries(new FormData(form))});
      await reloadRestaurant({submittedForm:form});
    }, 'Saving…');
  });
  attachContentActions(container);
}

function menuHighlightsMarkup(place) {
  if (!place.menuHighlights?.length) return `<li class="menu-item">${place.menuUrl ? externalLink(place.menuUrl, 'Open the menu from this listing’s source') : 'Menu details have not been published here yet. Check the venue website or contact the business.'}</li>`;
  return `<li class="menu-item"><strong>From the published chain menu</strong><p>Selection may differ by outlet. Prices are not published in this source; check the linked menu before ordering.</p><div class="menu-highlights">${place.menuHighlights.map(name => `<span>${escapeHtml(name)}</span>`).join('')}</div>${externalLink(place.menuHighlightsSource || place.menuUrl, 'View the full source menu')}</li>`;
}
