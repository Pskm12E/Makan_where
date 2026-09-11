document.addEventListener('DOMContentLoaded', () => {
  renderAnalytics();
});

function renderAnalytics() {
  const container = document.getElementById('analyticsCards');
  if (!container) return;

  const topRated = [...foodFinderData].sort((a, b) => b.rating - a.rating).slice(0, 3);
  const mostFavourited = [...foodFinderData].sort((a, b) => getFavouriteCount(b.id) - getFavouriteCount(a.id)).slice(0, 3);
  const topCuisines = Object.entries(
    foodFinderData.reduce((acc, item) => {
      acc[item.cuisine] = (acc[item.cuisine] || 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]).slice(0, 3);

  const affordable = [...foodFinderData]
    .flatMap(item => item.menu.map(menuItem => ({ name: menuItem.name, price: menuItem.price, establishment: item.name })))
    .sort((a, b) => a.price - b.price)
    .slice(0, 3);

  const reviewTags = mockReviews.flatMap(item => item.tags).reduce((acc, tag) => {
    acc[tag] = (acc[tag] || 0) + 1;
    return acc;
  }, {});

  container.innerHTML = `
    <article class="analytics-card">
      <h3>Top-rated establishments</h3>
      <ul>
        ${topRated.map(item => `<li>${item.name} — ${item.rating.toFixed(1)}</li>`).join('')}
      </ul>
    </article>

    <article class="analytics-card">
      <h3>Most favourited</h3>
      <ul>
        ${mostFavourited.map(item => `<li>${item.name} — ${getFavouriteCount(item.id)} saves</li>`).join('')}
      </ul>
    </article>

    <article class="analytics-card">
      <h3>Popular cuisines</h3>
      <ul>
        ${topCuisines.map(([cuisine, count]) => `<li>${cuisine} — ${count} venues</li>`).join('')}
      </ul>
    </article>

    <article class="analytics-card">
      <h3>Affordable items</h3>
      <ul>
        ${affordable.map(item => `<li>${item.name} (${item.establishment}) — $${item.price.toFixed(2)}</li>`).join('')}
      </ul>
    </article>

    <article class="analytics-card">
      <h3>Common review tags</h3>
      <ul>
        ${Object.entries(reviewTags).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([tag, count]) => `<li>${tag} — ${count}</li>`).join('')}
      </ul>
    </article>
  `;
}

function getFavouriteCount(id) {
  const favourites = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  return favourites.filter(itemId => itemId === id).length;
}
