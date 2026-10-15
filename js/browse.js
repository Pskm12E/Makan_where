let browsePage = 1;
let browseFilterKey = '';
const browsePageSize = 24;
document.addEventListener('DOMContentLoaded', async () => {
  if (!await appReady) return;
  populateFilterOptions();
  bindBrowseControls();
  applyBrowseFilters();
  if (new URLSearchParams(location.search).get('q')) recordDiscovery('search');
  let searchTimer;
  document.getElementById('searchInput').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => recordDiscovery('search'), 1000); });
});

function populateFilterOptions() {
  const categoryFilter = document.getElementById('categoryFilter');
  const cuisineFilter = document.getElementById('cuisineFilter');
  const areaFilter = document.getElementById('areaFilter');

  if (!categoryFilter || !cuisineFilter || !areaFilter) return;

  const categories = [...new Set(foodFinderData.map(item => item.category))];
  const cuisines = [...new Set(foodFinderData.flatMap(item => item.cuisines))];
  const areas = [...new Set(foodFinderData.map(item => item.area))];

  categoryFilter.innerHTML = '<option value="all">All categories</option>' + categories.map(cat => `<option value="${escapeHtml(cat)}">${escapeHtml(cat)}</option>`).join('');
  cuisineFilter.innerHTML = '<option value="all">All cuisines</option>' + cuisines.map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('');
  areaFilter.innerHTML = '<option value="all">All areas</option>' + areas.map(item => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join('');

  const params = new URLSearchParams(window.location.search);
  const q = params.get('q');
  const dataset = params.get('dataset');
  if (['all', 'real', 'demo'].includes(dataset)) document.getElementById('datasetFilter').value = dataset;
  if (q) {
    document.getElementById('searchInput').value = q;
  }
}

function bindBrowseControls() {
  ['searchInput', 'datasetFilter', 'categoryFilter', 'cuisineFilter', 'areaFilter', 'priceFilter', 'gradeFilter', 'sortSelect']
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
  const dataset = document.getElementById('datasetFilter').value;
  const filterKey = JSON.stringify([searchTerm, category, cuisine, area, priceRange, grade, sort, dataset]);
  if (filterKey !== browseFilterKey) { browsePage = 1; browseFilterKey = filterKey; }

  let filtered = [...foodFinderData].filter(item => {
    if (dataset === 'demo' && !item.isSample) return false;
    if (dataset === 'real' && item.isSample) return false;
    const matchesSearch = !searchTerm ||
      item.name.toLowerCase().includes(searchTerm) ||
      item.cuisine.toLowerCase().includes(searchTerm) ||
      item.area.toLowerCase().includes(searchTerm) || item.address.toLowerCase().includes(searchTerm);

    const matchesCategory = category === 'all' || item.category === category;
    const matchesCuisine = cuisine === 'all' || item.cuisines.includes(cuisine);
    const matchesArea = area === 'all' || item.area === area;
    const matchesGrade = grade === 'all' || item.hygieneGrade === grade;

    let matchesPrice = true;
    if (priceRange !== 'all' && item.price === null) return false;
    if (priceRange === 'under-5') matchesPrice = item.price < 5;
    if (priceRange === '5-10') matchesPrice = item.price >= 5 && item.price <= 10;
    if (priceRange === '10-20') matchesPrice = item.price > 10 && item.price <= 20;
    if (priceRange === '20-plus') matchesPrice = item.price > 20;

    return matchesSearch && matchesCategory && matchesCuisine && matchesArea && matchesGrade && matchesPrice;
  });

  filtered.sort((a, b) => {
    if (sort === 'price_asc') return (a.price ?? Infinity) - (b.price ?? Infinity);
    if (sort === 'name_asc') return a.name.localeCompare(b.name);
    return b.rating - a.rating || a.id - b.id;
  });

  resultsCount.textContent = `${filtered.length} results`;
  document.getElementById('datasetNotice').textContent = dataset === 'demo'
    ? 'These sample venues contain fictional reviews, menus and activity for testing. Sign in to add your own review or save a favourite.'
    : 'Imported listings keep their original source details. Sample venues contain demonstration prices and community activity.';
  const pagination = document.getElementById('browsePagination');
  pagination.replaceChildren();

  if (!filtered.length) {
    container.innerHTML = '<div class="empty-state">No food spots match your current filters. Try another combination.</div>';
    return;
  }

  const pages = Math.ceil(filtered.length / browsePageSize);
  browsePage = Math.min(browsePage, pages);
  if (pages > 1) {
    const previous = document.createElement('button'), next = document.createElement('button'), label = document.createElement('span');
    previous.textContent = 'Previous'; next.textContent = 'Next'; label.textContent = `Page ${browsePage} of ${pages}`;
    previous.disabled = browsePage === 1; next.disabled = browsePage === pages;
    previous.className = next.className = 'secondary-btn';
    previous.onclick = () => { browsePage--; applyBrowseFilters(); container.scrollIntoView({block:'start'}); };
    next.onclick = () => { browsePage++; applyBrowseFilters(); container.scrollIntoView({block:'start'}); };
    pagination.append(previous, label, next);
  }
  container.innerHTML = filtered.slice((browsePage - 1) * browsePageSize, browsePage * browsePageSize).map(item => `
    <article class="establishment-card">
      <div class="card-image">
        ${photoMarkup(item)}<span>${escapeHtml(item.cuisines.length ? item.cuisine : item.category)}</span>
      </div>
      <div class="card-body">
        <div class="card-meta">
          <span class="tag">${escapeHtml(item.category)}</span>
          ${listingLabel(item)}
          <button class="icon-button" data-favourite="${item.id}" aria-label="Favourite ${escapeHtml(item.name)}">
            ${getFavouriteStatus(item.id) ? '♥' : '♡'}
          </button>
        </div>
        <div class="establishment-name">${escapeHtml(item.name)}</div>
        <div class="location-meta">${escapeHtml(item.area)} • ${escapeHtml(item.address)}</div>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${ratingLabel(item.rating)}</span>
        </div>
        <div class="tag-row">
          ${item.tags.slice(0, 3).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
        </div>
        <div class="card-actions">
          <span class="price-badge">${cataloguePrice(item)}</span>
          <a class="small-action" href="restaurant.html?id=${item.id}">View</a>
        </div>
      </div>
    </article>
  `).join('');

  container.querySelectorAll('[data-favourite]').forEach(button => {
    button.addEventListener('click', (event) => {
      if (!requireLoginForFavourite()) return;
      const id = Number(event.currentTarget.dataset.favourite);
      withAction(event.currentTarget, async () => { await toggleFavourite(id); applyBrowseFilters(); });
    });
  });
}
