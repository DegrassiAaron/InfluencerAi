const listEl = document.getElementById('data-list');
const emptyStateEl = document.getElementById('data-empty');
const createForm = document.getElementById('data-form');
const createStatus = document.getElementById('data-form-status');
const editSection = document.querySelector('.data-editor');
const editForm = document.getElementById('data-edit-form');
const editStatus = document.getElementById('edit-status');
const cancelEditBtn = document.getElementById('cancel-edit');

let dataItems = [];
let editingId = null;

function setStatus(element, message, type = 'info') {
  element.textContent = message;
  element.classList.remove('empty', 'error', 'loading');
  if (type === 'loading') {
    element.classList.add('loading');
  } else if (type === 'error') {
    element.classList.add('error');
  } else if (type === 'empty') {
    element.classList.add('empty');
  } else if (!message) {
    element.classList.add('empty');
  }
}

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatDate(value) {
  if (!value) {
    return 'n/d';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('it-IT', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date);
}

async function parseError(response) {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === 'string') {
      return payload.detail;
    }
    if (payload?.detail?.message) {
      return payload.detail.message;
    }
    if (Array.isArray(payload?.detail) && payload.detail.length > 0) {
      const detail = payload.detail[0];
      if (typeof detail?.msg === 'string') {
        return detail.msg;
      }
    }
    return response.statusText || 'Richiesta non riuscita';
  } catch (error) {
    return response.statusText || 'Richiesta non riuscita';
  }
}

function renderList() {
  if (!Array.isArray(dataItems) || dataItems.length === 0) {
    listEl.hidden = true;
    emptyStateEl.hidden = false;
    setStatus(
      emptyStateEl,
      'Nessun dato disponibile. Aggiungi una nuova voce per iniziare.',
      'empty',
    );
    return;
  }

  listEl.hidden = false;
  emptyStateEl.hidden = true;

  const fragments = dataItems.map((item) => {
    const li = document.createElement('li');
    li.dataset.id = String(item.id);

    const header = document.createElement('div');
    header.className = 'data-item-header';

    const title = document.createElement('strong');
    title.innerHTML = escapeHtml(item.name);
    header.appendChild(title);

    if (item.category) {
      const tag = document.createElement('span');
      tag.className = 'data-tag';
      tag.innerHTML = escapeHtml(item.category);
      header.appendChild(tag);
    }

    li.appendChild(header);

    if (item.description) {
      const description = document.createElement('p');
      description.innerHTML = escapeHtml(item.description);
      li.appendChild(description);
    }

    const meta = document.createElement('div');
    meta.className = 'data-item-meta';
    meta.innerHTML = `ID #${escapeHtml(String(item.id))} · Creato ${escapeHtml(
      formatDate(item.created_at),
    )} · Aggiornato ${escapeHtml(formatDate(item.updated_at))}`;
    li.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'data-item-actions';

    const editBtn = document.createElement('button');
    editBtn.type = 'button';
    editBtn.textContent = 'Modifica';
    editBtn.addEventListener('click', () => startEdit(item.id));
    actions.appendChild(editBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.textContent = 'Elimina';
    deleteBtn.addEventListener('click', () => deleteItem(item.id));
    actions.appendChild(deleteBtn);

    li.appendChild(actions);
    return li;
  });

  listEl.replaceChildren(...fragments);
}

async function loadData() {
  setStatus(createStatus, 'Caricamento dati…', 'loading');
  try {
    const response = await fetch('/api/data');
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    const payload = await response.json();
    dataItems = Array.isArray(payload?.items) ? payload.items : [];
    renderList();
    setStatus(createStatus, 'Archivio aggiornato.');
  } catch (error) {
    setStatus(createStatus, `Errore durante il caricamento: ${error.message}`, 'error');
    listEl.hidden = true;
    emptyStateEl.hidden = false;
    setStatus(emptyStateEl, 'Impossibile caricare i dati.', 'error');
  }
}

function resetEdit() {
  editingId = null;
  editSection.hidden = true;
  editForm.reset();
  setStatus(editStatus, 'Seleziona una voce dall\'elenco per modificarla o rimuoverla.', 'info');
}

function startEdit(id) {
  const item = dataItems.find((entry) => entry.id === id);
  if (!item) {
    return;
  }
  editingId = id;
  editSection.hidden = false;
  editForm.querySelector('#edit-id').value = String(item.id);
  editForm.querySelector('#edit-name').value = item.name ?? '';
  editForm.querySelector('#edit-category').value = item.category ?? '';
  editForm.querySelector('#edit-description').value = item.description ?? '';
  setStatus(editStatus, 'Modifica i campi e salva le modifiche.');
}

async function deleteItem(id) {
  setStatus(editStatus, 'Rimozione in corso…', 'loading');
  try {
    const response = await fetch(`/api/data/${id}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    if (editingId === id) {
      resetEdit();
    }
    await loadData();
    setStatus(editStatus, 'Voce eliminata.');
  } catch (error) {
    setStatus(editStatus, `Errore: ${error.message}`, 'error');
  }
}

createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(createForm);
  const payload = {
    name: String(formData.get('name') || '').trim(),
    category: String(formData.get('category') || '').trim() || null,
    description: String(formData.get('description') || '').trim() || null,
  };

  if (!payload.name) {
    setStatus(createStatus, 'Il nome è obbligatorio.', 'error');
    return;
  }

  setStatus(createStatus, 'Salvataggio in corso…', 'loading');
  try {
    const response = await fetch('/api/data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    createForm.reset();
    setStatus(createStatus, 'Voce salvata con successo.');
    await loadData();
  } catch (error) {
    setStatus(createStatus, `Errore: ${error.message}`, 'error');
  }
});

editForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!editingId) {
    setStatus(editStatus, 'Nessuna voce selezionata.', 'error');
    return;
  }
  const formData = new FormData(editForm);
  const payload = {
    name: String(formData.get('name') || '').trim() || undefined,
    category: String(formData.get('category') || '').trim(),
    description: String(formData.get('description') || '').trim(),
  };

  if (!payload.name) {
    setStatus(editStatus, 'Il nome è obbligatorio.', 'error');
    return;
  }

  if (!payload.category) {
    payload.category = null;
  }
  if (!payload.description) {
    payload.description = null;
  }

  setStatus(editStatus, 'Aggiornamento in corso…', 'loading');
  try {
    const response = await fetch(`/api/data/${editingId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    setStatus(editStatus, 'Voce aggiornata.');
    await loadData();
  } catch (error) {
    setStatus(editStatus, `Errore: ${error.message}`, 'error');
  }
});

cancelEditBtn.addEventListener('click', () => {
  resetEdit();
});

loadData().finally(() => {
  if (dataItems.length === 0) {
    resetEdit();
  }
});
