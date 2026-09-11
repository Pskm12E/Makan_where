document.addEventListener('DOMContentLoaded', () => {
  renderFavouriteList();
});

function renderFavouriteList() {
  const container = document.getElementById('favouriteList');
  if (!container) return;

  const favouriteIds = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  const favourites = foodFinderData.filter(item => favouriteIds.includes(item.id));

  if (!favourites.length) {
    container.innerHTML = '<div class="favourite-empty">No favourites yet. Browse and save a few food spots you love.</div>';
    return;
  }

  container.innerHTML = favourites.map(item => `
    <article class="establishment-card">
      <div class="card-image" style="background-image: linear-gradient(180deg, rgba(21, 20, 20, 0.05), rgba(21,20,20,0.38)), url('${item.image || 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80'}');">
        <span>${item.cuisine}</span>
      </div>
      <div class="card-body">
        <div class="card-meta">
          <span class="tag">${item.category}</span>
          <button class="icon-button" data-favourite="${item.id}" aria-label="Remove ${item.name} from favourites">♥</button>
        </div>
        <div class="establishment-name">${item.name}</div>
        <div class="location-meta">${item.area} • ${item.hygieneGrade} grade</div>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${item.rating.toFixed(1)}</span>
        </div>
        <div class="tag-row">
          ${item.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
        </div>
        <div class="card-actions">
          <span class="price-badge">From $${item.price.toFixed(2)}</span>
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
      const id = Number(event.currentTarget.dataset.remove || event.currentTarget.dataset.favourite);
      toggleFavourite(id);
      renderFavouriteList();
    });
  });
}

function toggleFavourite(id) {
  const favourites = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  const index = favourites.indexOf(id);
  if (index >= 0) {
    favourites.splice(index, 1);
  }
  localStorage.setItem(favouriteStorageKey, JSON.stringify(favourites));
}
