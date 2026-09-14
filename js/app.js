document.addEventListener('DOMContentLoaded', () => {
  renderFeaturedEstablishments();
  renderPopularTags();
  bindHomeSearch();
});

function renderFeaturedEstablishments() {
  const container = document.getElementById('featuredGrid');
  if (!container) return;

  const featured = [...foodFinderData].sort((a, b) => b.rating - a.rating).slice(0, 3);
  container.innerHTML = featured.map(establishment => `
    <article class="establishment-card">
      <div class="card-image" style="background-image: linear-gradient(180deg, rgba(21, 20, 20, 0.05), rgba(21,20,20,0.38)), url('${establishment.image || 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80'}');">
        <span>${establishment.cuisine}</span>
      </div>
      <div class="card-body">
        <div class="card-meta">
          <span class="tag">${establishment.category}</span>
          <button class="icon-button" data-favourite="${establishment.id}" aria-label="Favourite ${establishment.name}">
            ${getFavouriteStatus(establishment.id) ? '♥' : '♡'}
          </button>
        </div>
        <div class="establishment-name">${establishment.name}</div>
        <div class="location-meta">${establishment.area} • ${establishment.address}</div>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${establishment.rating.toFixed(1)}</span>
        </div>
        <div class="tag-row">
          ${establishment.tags.slice(0, 3).map(tag => `<span class="tag">${tag}</span>`).join('')}
        </div>
        <div class="card-actions">
          <span class="price-badge">From $${establishment.price.toFixed(2)}</span>
          <a class="small-action" href="restaurant.html?id=${establishment.id}">View</a>
        </div>
      </div>
    </article>
  `).join('');

  document.querySelectorAll('[data-favourite]').forEach(button => {
    button.addEventListener('click', (event) => {
      if (!requireLoginForFavourite()) return;
      const id = Number(event.currentTarget.dataset.favourite);
      toggleFavourite(id);
      renderFeaturedEstablishments();
    });
  });
}

function renderPopularTags() {
  const container = document.getElementById('homePopularTags');
  if (!container) return;

  const tags = ['Chinese', 'Malay', 'Indian', 'Japanese', 'Vegetarian', 'Budget'];
  container.innerHTML = tags.map(tag => `<button class="chip" data-tag="${tag}">${tag}</button>`).join('');

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

function getFavouriteStatus(id) {
  if (!getCurrentUser()) return false;
  const favourites = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  return favourites.includes(id);
}

function toggleFavourite(id) {
  if (!requireLoginForFavourite()) return;
  const favourites = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  const index = favourites.indexOf(id);
  if (index >= 0) {
    favourites.splice(index, 1);
  } else {
    favourites.push(id);
  }
  localStorage.setItem(favouriteStorageKey, JSON.stringify(favourites));
}
