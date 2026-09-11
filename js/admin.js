document.addEventListener('DOMContentLoaded', () => {
  renderAdminEstablishments();
  attachAdminForm();
});

function renderAdminEstablishments() {
  const list = document.getElementById('adminEstablishments');
  const statsCount = document.getElementById('statsCount');
  const statsAvgPrice = document.getElementById('statsAvgPrice');
  if (!list) return;

  const totalAverage = foodFinderData.reduce((sum, item) => sum + item.price, 0) / foodFinderData.length;
  statsCount.textContent = foodFinderData.length;
  statsAvgPrice.textContent = `$${totalAverage.toFixed(2)}`;

  list.innerHTML = foodFinderData.map(item => `
    <div class="admin-row">
      <div>
        <strong>${item.name}</strong><br />
        <small>${item.area} • ${item.cuisine}</small>
      </div>
      <div class="admin-row-actions">
        <button class="small-action" data-edit="${item.id}">Edit</button>
        <button class="danger-btn" data-delete="${item.id}">Delete</button>
      </div>
    </div>
  `).join('');

  list.querySelectorAll('[data-delete]').forEach(button => {
    button.addEventListener('click', (event) => {
      const id = Number(event.currentTarget.dataset.delete);
      const index = foodFinderData.findIndex(item => item.id === id);
      if (index >= 0) {
        foodFinderData.splice(index, 1);
        renderAdminEstablishments();
      }
    });
  });

  list.querySelectorAll('[data-edit]').forEach(button => {
    button.addEventListener('click', (event) => {
      const id = Number(event.currentTarget.dataset.edit);
      const target = foodFinderData.find(item => item.id === id);
      if (!target) return;

      document.getElementById('editId').value = String(target.id);
      document.getElementById('adminName').value = target.name;
      document.getElementById('adminArea').value = target.area;
      document.getElementById('adminCategory').value = target.category;
      document.getElementById('adminCuisine').value = target.cuisine;
      document.getElementById('adminAddress').value = target.address;

      document.getElementById('adminFormTitle').textContent = 'Edit establishment';
      document.getElementById('adminSubmitBtn').textContent = 'Save changes';
      document.getElementById('cancelEditBtn').classList.remove('hidden');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
}

function attachAdminForm() {
  const form = document.getElementById('adminForm');
  const cancelBtn = document.getElementById('cancelEditBtn');
  if (!form) return;

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const name = document.getElementById('adminName').value.trim();
    const area = document.getElementById('adminArea').value.trim();
    const category = document.getElementById('adminCategory').value.trim();
    const cuisine = document.getElementById('adminCuisine').value.trim();
    const address = document.getElementById('adminAddress').value.trim();

    if (!name || !area || !category || !cuisine || !address) return;

    const editId = document.getElementById('editId').value;

    if (editId) {
      const target = foodFinderData.find(item => item.id === Number(editId));
      if (target) {
        target.name = name;
        target.area = area;
        target.category = category;
        target.cuisine = cuisine;
        target.address = address;
      }
    } else {
      foodFinderData.push({
        id: Date.now(),
        name,
        category,
        cuisine,
        area,
        address,
        hygieneGrade: 'A',
        rating: 4.3,
        price: 10,
        image: 'https://images.unsplash.com/photo-1559339352-11d035aa65de?auto=format&fit=crop&w=900&q=80',
        tags: ['new', 'local'],
        menu: [{ name: 'House Special', price: 10, dietary: 'General', availability: true }],
        description: 'Newly added establishment in the mock dataset.'
      });
    }

    resetAdminForm();
    renderAdminEstablishments();
  });

  cancelBtn.addEventListener('click', resetAdminForm);
}

function resetAdminForm() {
  document.getElementById('adminForm').reset();
  document.getElementById('editId').value = '';
  document.getElementById('adminFormTitle').textContent = 'Add establishment';
  document.getElementById('adminSubmitBtn').textContent = 'Add establishment';
  document.getElementById('cancelEditBtn').classList.add('hidden');
}
