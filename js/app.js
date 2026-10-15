document.addEventListener('DOMContentLoaded', async () => {
  if (!await appReady) return;
  renderFeaturedEstablishments();
  renderPopularTags();
  bindHomeSearch();
  document.getElementById('homePlaceCount').textContent = foodFinderData.length;
  const rated = foodFinderData.filter(place => place.rating > 0);
  document.getElementById('homeAverageRating').textContent = rated.length
    ? (rated.reduce((sum, place) => sum + place.rating, 0) / rated.length).toFixed(1) + '/5' : 'No reviews';
  document.getElementById('homeCuisineCount').textContent = new Set(foodFinderData.flatMap(place => place.cuisines)).size;
  document.getElementById('popularItems').innerHTML = foodFinderData.filter(place => place.menu.some(item => item.availability)).slice(0, 3).map(place => {
    const dish = place.menu.find(item => item.availability);
    return dish ? `<article class="menu-item">${listingLabel(place)}<strong>${escapeHtml(dish.name)}</strong><p>${escapeHtml(place.name)} · ${priceLabel(dish.price)}</p><a class="small-action" href="restaurant.html?id=${place.id}">View menu</a></article>` : '';
  }).join('');
});

function renderFeaturedEstablishments() {
  const container = document.getElementById('featuredGrid');
  if (!container) return;

  const featured = [...foodFinderData].sort((a, b) => Number(a.isSample) - Number(b.isSample) || b.rating - a.rating || Number(a.address === 'Address not listed') - Number(b.address === 'Address not listed')).slice(0, 3);
  container.innerHTML = featured.map(establishment => `
    <article class="establishment-card">
      <div class="card-image">
        ${photoMarkup(establishment)}<span>${escapeHtml(establishment.cuisines.length ? establishment.cuisine : establishment.category)}</span>
      </div>
      <div class="card-body">
        <div class="card-meta">
          <span class="tag">${escapeHtml(establishment.category)}</span>
          ${listingLabel(establishment)}
          <button class="icon-button" data-favourite="${establishment.id}" aria-label="Favourite ${escapeHtml(establishment.name)}">
            ${getFavouriteStatus(establishment.id) ? '♥' : '♡'}
          </button>
        </div>
        <div class="establishment-name">${escapeHtml(establishment.name)}</div>
        <div class="location-meta">${escapeHtml(establishment.area)} • ${escapeHtml(establishment.address)}</div>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${ratingLabel(establishment.rating)}</span>
        </div>
        <div class="tag-row">
          ${establishment.tags.slice(0, 3).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
        <div class="card-actions">
          <span class="price-badge">${cataloguePrice(establishment)}</span>
          <a class="small-action" href="restaurant.html?id=${establishment.id}">View</a>
        </div>
      </div>
    </article>
  `).join('');

  document.querySelectorAll('[data-favourite]').forEach(button => {
    button.addEventListener('click', (event) => {
      if (!requireLoginForFavourite()) return;
      const id = Number(event.currentTarget.dataset.favourite);
      withAction(event.currentTarget, async () => { await toggleFavourite(id); renderFeaturedEstablishments(); });
    });
  });
}

function renderPopularTags() {
  const container = document.getElementById('homePopularTags');
  if (!container) return;

  const tags = ['Chinese', 'Malay', 'Indian', 'Japanese', 'Coffee', 'Thai'];
  container.innerHTML = tags.map(tag => `<button class="chip" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`).join('');

  container.querySelectorAll('[data-tag]').forEach(button => {
    button.addEventListener('click', () => {
      window.location.href = `browse.html?q=${encodeURIComponent(button.dataset.tag)}`;
    });
  });
}

function bindHomeSearch() {
  const input = document.getElementById('homeSearch');
  const button = document.getElementById('homeSearchBtn');
  if (!input || !button) return;

  const search = () => {
    const value = input.value.trim();
    window.location.href = value ? `browse.html?q=${encodeURIComponent(value)}` : 'browse.html';
  };

  button.addEventListener('click', search);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') search();
  });
}
