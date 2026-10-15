document.addEventListener('DOMContentLoaded', async () => {
  if (!await appReady) return;
  await withAction(null, renderAnalytics);
});

async function renderAnalytics() {
  const {discovery, topRated, mostFavourited, cuisineCoverage, affordableItems, affordableMenus} = await api('/analytics');
  const sample = row => row.isSample ? ' (sample menu)' : '';
  const card = (title, rows, empty) => `<article class="analytics-card"><h3>${title}</h3>${rows.length ? `<ul>${rows.map(row => `<li>${row}</li>`).join('')}</ul>` : `<p>${empty}</p>`}</article>`;
  document.getElementById('analyticsCards').innerHTML =
    card('Top-rated establishments', topRated.map(p => `${escapeHtml(p.name)} — ${ratingLabel(p.rating)} (${p.reviewCount} reviews)${p.isSample ? ' · sample listing / demo activity' : ''}`), 'No reviews yet.') +
    card('Most favourited', mostFavourited.map(p => `${escapeHtml(p.name)} — ${p.favouriteCount} saves${p.isSample ? ' · sample listing / demo activity' : ''}`), 'No favourites yet.') +
    card('Cuisine coverage', cuisineCoverage.map(c => `${escapeHtml(c.name)} — ${c.venueCount} venues`), 'No cuisines yet.') +
    card('Affordable items', affordableItems.map(d => `${escapeHtml(d.name)} (${escapeHtml(d.place)}) — ${priceLabel(d.price)}${sample(d)}`), 'No available menu items.') +
    card('Menus averaging $12 or less', affordableMenus.map(p => `${escapeHtml(p.name)} — ${priceLabel(p.averagePrice)} average across ${p.dishCount} dishes${sample(p)}`), 'No qualifying menus with known prices.') +
    card('Discovery activity', [`${discovery.search || 0} searches`, `${discovery.place_view || 0} place views`], 'No activity yet.');
}
