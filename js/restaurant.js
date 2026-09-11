document.addEventListener('DOMContentLoaded', () => {
  renderRestaurantDetail();
});

function renderRestaurantDetail() {
  const container = document.getElementById('restaurantDetail');
  if (!container) return;

  const params = new URLSearchParams(window.location.search);
  const id = Number(params.get('id'));
  const restaurant = foodFinderData.find(item => item.id === id);

  if (!restaurant) {
    container.innerHTML = '<div class="empty-state">Restaurant not found.</div>';
    return;
  }

  const favouriteIds = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  const isFavourite = favouriteIds.includes(id);
  const reviews = mockReviews.filter(review => review.establishmentId === id);

  container.innerHTML = `
    <div class="detail-hero" style="background-image: linear-gradient(180deg, rgba(20, 20, 20, 0.16), rgba(20, 20, 20, 0.58)), url('${restaurant.image || 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80'}');">
      <div class="detail-hero-overlay">
        <p class="eyebrow light">${restaurant.category}</p>
        <h1>${restaurant.name}</h1>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${restaurant.rating.toFixed(1)} • ${reviews.length} reviews</span>
        </div>
      </div>
      <button class="small-action" id="detailFavouriteBtn">${isFavourite ? 'Remove favourite' : 'Add favourite'}</button>
    </div>

    <div class="detail-header">
      <div>
        <p class="eyebrow">${restaurant.category}</p>
        <h1>${restaurant.name}</h1>
        <div class="rating-row">
          <span class="star">★</span>
          <span>${restaurant.rating.toFixed(1)} • ${reviews.length} reviews</span>
        </div>
      </div>
      <button class="small-action" id="detailFavouriteBtnSecondary">${isFavourite ? 'Remove favourite' : 'Add favourite'}</button>
    </div>

    <div class="detail-grid">
      <div>
        <div class="detail-meta">
          <div><strong>Address:</strong> ${restaurant.address}</div>
          <div><strong>Area:</strong> ${restaurant.area}</div>
          <div><strong>Hygiene Grade:</strong> ${restaurant.hygieneGrade}</div>
          <div><strong>Average Price:</strong> $${restaurant.price.toFixed(2)}</div>
        </div>

        <div class="tag-row">
          ${restaurant.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
        </div>

        <p>${restaurant.description}</p>

        <h3>Menu</h3>
        <ul class="menu-list">
          ${restaurant.menu.map(item => `
            <li class="menu-item">
              <div class="meta-row">
                <strong>${item.name}</strong>
                <span>$${item.price.toFixed(2)}</span>
              </div>
              <div class="meta-row">
                <span>${item.dietary}</span>
                <span>${item.availability ? 'Available' : 'Unavailable'}</span>
              </div>
            </li>
          `).join('')}
        </ul>
      </div>

      <div>
        <h3>Reviews</h3>
        <ul class="review-list">
          ${reviews.length ? reviews.map(review => `
            <li class="review-item">
              <div class="meta-row">
                <strong>${review.reviewer}</strong>
                <span>${'★'.repeat(review.rating)}${'☆'.repeat(5 - review.rating)}</span>
              </div>
              <h4>${review.title}</h4>
              <p>${review.text}</p>
              <div class="tag-row">
                ${review.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
              </div>
            </li>
          `).join('') : '<li class="review-item">No reviews yet.</li>'}
        </ul>

        <form class="review-form" id="reviewForm">
          <input type="text" id="reviewTitle" placeholder="Review title" required />
          <input type="text" id="reviewerName" placeholder="Your name" required />
          <select id="reviewRating">
            <option value="5">5 stars</option>
            <option value="4">4 stars</option>
            <option value="3">3 stars</option>
            <option value="2">2 stars</option>
            <option value="1">1 star</option>
          </select>
          <textarea id="reviewText" placeholder="Write your review" required></textarea>
          <button type="submit" class="small-action">Submit review</button>
        </form>
      </div>
    </div>
  `;

  const favouriteButton = document.getElementById('detailFavouriteBtn');
  const favouriteSecondaryButton = document.getElementById('detailFavouriteBtnSecondary');

  [favouriteButton, favouriteSecondaryButton].forEach((button) => {
    if (!button) return;
    button.addEventListener('click', () => {
      toggleFavourite(id);
      renderRestaurantDetail();
    });
  });

  const reviewForm = document.getElementById('reviewForm');
  reviewForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const title = document.getElementById('reviewTitle').value.trim();
    const reviewer = document.getElementById('reviewerName').value.trim();
    const rating = Number(document.getElementById('reviewRating').value);
    const text = document.getElementById('reviewText').value.trim();

    if (!title || !reviewer || !text) return;

    mockReviews.unshift({
      establishmentId: id,
      reviewer,
      rating,
      title,
      text,
      tags: ['new-review']
    });

    reviewForm.reset();
    renderRestaurantDetail();
  });
}

function getFavouriteStatus(id) {
  const favourites = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  return favourites.includes(id);
}

function toggleFavourite(id) {
  const favourites = JSON.parse(localStorage.getItem(favouriteStorageKey) || '[]');
  const index = favourites.indexOf(id);
  if (index >= 0) {
    favourites.splice(index, 1);
  } else {
    favourites.push(id);
  }
  localStorage.setItem(favouriteStorageKey, JSON.stringify(favourites));
}
