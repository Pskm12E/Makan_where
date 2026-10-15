document.addEventListener('DOMContentLoaded', async () => {
  if (!await appReady) return;
  renderFavouriteList();
});

function renderFavouriteList() {
  const container = document.getElementById('favouriteList');
  if (!container) return;

  if (!getCurrentUser()) {
    container.innerHTML = `
      <div class="favourite-empty">
        <strong>Log in to see your favourites.</strong>
        <p>Save food spots you love and find them here later.</p>
        <a class="small-action" href="auth.html?mode=login">Go to login</a>
      </div>
    `;
    return;
  }

  const savedIds = favouriteIds;
  const favourites = foodFinderData.filter(item => savedIds.includes(item.id));

  if (!favourites.length) {
    container.innerHTML = '<div class="favourite-empty">No favourites yet. Browse and save a few food spots you love.</div>';
    return;
  }

  container.innerHTML = favourites.map(item => `
    <article class="establishment-card">
      <div class="card-image">
        ${photoMarkup(item)}<span>${escapeHtml(item.cuisines.length ? item.cuisine : item.category)}</span>
      </div>
      <div class="card-body">
        <div class="card-meta">
          <span class="tag">${escapeHtml(item.category)}</span>
          ${listingLabel(item)}
          <button class="icon-button" data-favourite="${item.id}" aria-label="Remove ${escapeHtml(item.name)} from favourites">♥</button>
        </div>
        <div class="establishment-name">${escapeHtml(item.name)}</div>
        <div class="location-meta">${escapeHtml(item.area)} • ${escapeHtml(item.address)}</div>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${ratingLabel(item.rating)}</span>
        </div>
        <div class="tag-row">
          ${item.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
        <div class="card-actions">
          <span class="price-badge">${cataloguePrice(item)}</span>
          <div class="admin-row-actions">
            <a class="small-action" href="restaurant.html?id=${item.id}">Open</a>
            <button class="danger-btn" data-remove="${item.id}">Remove</button>
          </div>
        </div>
      </div>
    </article>
  `).join('');

  container.querySelectorAll('[data-remove],[data-favourite]').forEach(button => {
    button.addEventListener('click', (event) => {
      if (!requireLoginForFavourite()) return;
      const id = Number(event.currentTarget.dataset.remove || event.currentTarget.dataset.favourite);
      withAction(event.currentTarget, async () => { await toggleFavourite(id); renderFavouriteList(); });
    });
  });
}
