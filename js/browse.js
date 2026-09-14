document.addEventListener('DOMContentLoaded', () => {
  populateFilterOptions();
  bindBrowseControls();
  applyBrowseFilters();
});

function populateFilterOptions() {
  const categoryFilter = document.getElementById('categoryFilter');
  const cuisineFilter = document.getElementById('cuisineFilter');
  const areaFilter = document.getElementById('areaFilter');

  if (!categoryFilter || !cuisineFilter || !areaFilter) return;

  const categories = [...new Set(foodFinderData.map(item => item.category))];
  const cuisines = [...new Set(foodFinderData.map(item => item.cuisine))];
  const areas = [...new Set(foodFinderData.map(item => item.area))];

  categoryFilter.innerHTML = '<option value="all">All categories</option>' + categories.map(cat => `<option value="${cat}">${cat}</option>`).join('');
  cuisineFilter.innerHTML = '<option value="all">All cuisines</option>' + cuisines.map(item => `<option value="${item}">${item}</option>`).join('');
  areaFilter.innerHTML = '<option value="all">All areas</option>' + areas.map(item => `<option value="${item}">${item}</option>`).join('');

  const params = new URLSearchParams(window.location.search);
  const q = params.get('q');
  if (q) {
    document.getElementById('searchInput').value = q;
  }
}

function bindBrowseControls() {
  ['searchInput', 'categoryFilter', 'cuisineFilter', 'areaFilter', 'priceFilter', 'gradeFilter', 'sortSelect']
    .forEach(id => {
      const element = document.getElementById(id);
      if (element) {
        element.addEventListener('input', applyBrowseFilters);
        element.addEventListener('change', applyBrowseFilters);
      }
    });
}

function applyBrowseFilters() {
  const searchInput = document.getElementById('searchInput');
  const categoryFilter = document.getElementById('categoryFilter');
  const cuisineFilter = document.getElementById('cuisineFilter');
  const areaFilter = document.getElementById('areaFilter');
  const priceFilter = document.getElementById('priceFilter');
  const gradeFilter = document.getElementById('gradeFilter');
  const sortSelect = document.getElementById('sortSelect');
  const resultsCount = document.getElementById('resultsCount');
  const container = document.getElementById('establishmentList');

  if (!container) return;

  const searchTerm = (searchInput?.value || '').trim().toLowerCase();
  const category = categoryFilter?.value || 'all';
  const cuisine = cuisineFilter?.value || 'all';
  const area = areaFilter?.value || 'all';
  const priceRange = priceFilter?.value || 'all';
  const grade = gradeFilter?.value || 'all';
  const sort = sortSelect?.value || 'rating_desc';

  let filtered = [...foodFinderData].filter(item => {
    const matchesSearch = !searchTerm ||
      item.name.toLowerCase().includes(searchTerm) ||
      item.cuisine.toLowerCase().includes(searchTerm) ||
      item.area.toLowerCase().includes(searchTerm);

    const matchesCategory = category === 'all' || item.category === category;
    const matchesCuisine = cuisine === 'all' || item.cuisine === cuisine;
    const matchesArea = area === 'all' || item.area === area;
    const matchesGrade = grade === 'all' || item.hygieneGrade === grade;

    let matchesPrice = true;
    if (priceRange === 'under-5') matchesPrice = item.price < 5;
    if (priceRange === '5-10') matchesPrice = item.price >= 5 && item.price <= 10;
    if (priceRange === '10-20') matchesPrice = item.price > 10 && item.price <= 20;
    if (priceRange === '20-plus') matchesPrice = item.price > 20;

    return matchesSearch && matchesCategory && matchesCuisine && matchesArea && matchesGrade && matchesPrice;
  });

  filtered.sort((a, b) => {
    if (sort === 'price_asc') return a.price - b.price;
    if (sort === 'name_asc') return a.name.localeCompare(b.name);
    return b.rating - a.rating;
  });

  resultsCount.textContent = `${filtered.length} results`;

  if (!filtered.length) {
    container.innerHTML = '<div class="empty-state">No food spots match your current filters. Try another combination.</div>';
    return;
  }

  container.innerHTML = filtered.map(item => `
    <article class="establishment-card">
      <div class="card-image" style="background-image: linear-gradient(180deg, rgba(21, 20, 20, 0.05), rgba(21,20,20,0.38)), url('${item.image || 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80'}');">
        <span>${item.cuisine}</span>
      </div>
      <div class="card-body">
        <div class="card-meta">
          <span class="tag">${item.category}</span>
          <button class="icon-button" data-favourite="${item.id}" aria-label="Favourite ${item.name}">
            ${getFavouriteStatus(item.id) ? '♥' : '♡'}
          </button>
        </div>
        <div class="establishment-name">${item.name}</div>
        <div class="location-meta">${item.area} • ${item.hygieneGrade} grade</div>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${item.rating.toFixed(1)}</span>
        </div>
        <div class="tag-row">
          ${item.tags.slice(0, 3).map(tag => `<span class="tag">${tag}</span>`).join('')}
        </div>
        <div class="card-actions">
          <span class="price-badge">From $${item.price.toFixed(2)}</span>
          <a class="small-action" href="restaurant.html?id=${item.id}">View</a>
        </div>
      </div>
    </article>
  `).join('');

  container.querySelectorAll('[data-favourite]').forEach(button => {
    button.addEventListener('click', (event) => {
      if (!requireLoginForFavourite()) return;
      const id = Number(event.currentTarget.dataset.favourite);
      toggleFavourite(id);
      applyBrowseFilters();
    });
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
