const statusMessage = document.querySelector('#data-status');
const tableBody = document.querySelector('#data-table tbody');
const createButton = document.querySelector('#create-data');
const modal = document.querySelector('#data-modal');
const modalTitle = document.querySelector('#data-modal-title');
const modalSubtitle = document.querySelector('#data-modal-subtitle');
const modalDetails = document.querySelector('#data-details');
const form = document.querySelector('#data-form');
const payloadField = document.querySelector('#data-payload');
const saveButton = document.querySelector('#data-save');
const closeButton = document.querySelector('#data-close');
const formError = document.querySelector('#data-form-error');

let entries = [];
let currentEntry = null;
let currentMode = 'view';

function setStatus({ message, tone }) {
  if (!statusMessage) return;
  statusMessage.hidden = false;
  statusMessage.textContent = message;
  statusMessage.classList.remove('error', 'loading', 'empty');
  if (tone) {
    statusMessage.classList.add(tone);
  }
}

function hideStatus() {
  if (!statusMessage) return;
  statusMessage.hidden = true;
  statusMessage.classList.remove('error', 'loading', 'empty');
}

function pickField(entry, keys, fallback = '') {
  if (!entry || typeof entry !== 'object') {
    return fallback;
  }
  for (const key of keys) {
    if (entry[key] !== undefined && entry[key] !== null && `${entry[key]}`.trim() !== '') {
      return entry[key];
    }
  }
  return fallback;
}

function formatDateValue(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return `${value}`;
  }
  return date.toLocaleString('it-IT', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function renderTable(data) {
  tableBody.innerHTML = '';

  if (!data.length) {
    setStatus({ message: 'Nessun dato disponibile. Crea un nuovo record per iniziare.', tone: 'empty' });
    return;
  }

  hideStatus();

  data.forEach((entry) => {
    const row = document.createElement('tr');
    const entryId = getEntryId(entry);
    if (entryId) {
      row.dataset.id = entryId;
    }
    const canMutate = Boolean(entryId);

    const nameCell = document.createElement('td');
    nameCell.textContent = pickField(entry, ['name', 'title', 'label', 'display_name', 'id'], '—');
    row.appendChild(nameCell);

    const categoryCell = document.createElement('td');
    categoryCell.textContent = pickField(entry, ['category', 'type', 'segment', 'status'], '—');
    row.appendChild(categoryCell);

    const updatedCell = document.createElement('td');
    const updatedValue = pickField(entry, ['updated_at', 'updated', 'modified_at', 'created_at', 'timestamp']);
    updatedCell.textContent = formatDateValue(updatedValue) || '—';
    row.appendChild(updatedCell);

    const actionsCell = document.createElement('td');
    const actionsWrapper = document.createElement('div');
    actionsWrapper.className = 'model-actions';

    actionsWrapper.appendChild(createActionButton('Visualizza', 'view'));
    actionsWrapper.appendChild(
      createActionButton('Modifica', 'edit', '', { disabled: !canMutate })
    );
    actionsWrapper.appendChild(
      createActionButton('Elimina', 'delete', 'button-secondary', { disabled: !canMutate })
    );

    actionsCell.appendChild(actionsWrapper);
    row.appendChild(actionsCell);

    tableBody.appendChild(row);
  });
}

function createActionButton(label, action, extraClass = '', options = {}) {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = label;
  button.dataset.action = action;
  if (extraClass) {
    button.classList.add(extraClass);
  }
  if (options.disabled) {
    button.disabled = true;
    button.title = 'Operazione non disponibile per questo record';
  }
  return button;
}

function getEntryId(entry) {
  const value = pickField(entry, ['id', 'uuid', 'slug']);
  return value ? `${value}` : '';
}

async function fetchData() {
  setStatus({ message: 'Caricamento dati...', tone: 'loading' });
  try {
    const response = await fetch('/api/data');
    if (!response.ok) {
      throw new Error('Impossibile recuperare i dati');
    }
    const payload = await response.json().catch(() => ({}));
    const data = Array.isArray(payload) ? payload : payload.data || [];
    entries = Array.isArray(data) ? data : [];
    renderTable(entries);
  } catch (error) {
    tableBody.innerHTML = '';
    setStatus({ message: error.message || 'Errore inatteso', tone: 'error' });
  }
}

function cloneEntry(entry) {
  if (entry === null || entry === undefined) return null;
  if (typeof entry !== 'object') return entry;
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(entry);
    } catch (error) {
      // Ignore and fallback to JSON clone
    }
  }
  try {
    return JSON.parse(JSON.stringify(entry));
  } catch (error) {
    return { ...entry };
  }
}

function openModal(mode, entry = null) {
  currentMode = mode;
  currentEntry = entry ? cloneEntry(entry) : null;
  formError.classList.add('hidden');
  formError.textContent = '';

  if (mode === 'view') {
    modalTitle.textContent = 'Dettaglio record';
    modalSubtitle.textContent = currentEntry ? describeEntry(currentEntry) : '';
    renderDetails(currentEntry);
    form.classList.add('hidden');
    saveButton.classList.add('hidden');
  } else if (mode === 'edit') {
    modalTitle.textContent = 'Modifica record';
    modalSubtitle.textContent = currentEntry ? describeEntry(currentEntry) : '';
    renderDetails(null);
    form.classList.remove('hidden');
    payloadField.value = JSON.stringify(currentEntry ?? {}, null, 2);
    payloadField.focus();
    saveButton.textContent = 'Salva modifiche';
    saveButton.classList.remove('hidden');
  } else {
    modalTitle.textContent = 'Nuovo record';
    modalSubtitle.textContent = 'Compila il payload JSON per creare un nuovo elemento.';
    renderDetails(null);
    form.classList.remove('hidden');
    payloadField.value = JSON.stringify({ name: '', category: '', payload: {} }, null, 2);
    payloadField.focus();
    saveButton.textContent = 'Crea record';
    saveButton.classList.remove('hidden');
  }

  toggleDialog(true);
}

function describeEntry(entry) {
  if (!entry) return '';
  if (typeof entry !== 'object') {
    return formatDetailValue(entry);
  }
  const name = pickField(entry, ['name', 'title', 'label', 'display_name', 'id'], 'Record');
  const category = pickField(entry, ['category', 'type', 'segment', 'status']);
  if (category) {
    return `${name} · ${category}`;
  }
  return `${name}`;
}

function renderDetails(entry) {
  modalDetails.innerHTML = '';
  if (entry === null || entry === undefined) {
    modalDetails.classList.add('hidden');
    modalDetails.setAttribute('aria-hidden', 'true');
    return;
  }
  modalDetails.classList.remove('hidden');
  modalDetails.setAttribute('aria-hidden', 'false');
  if (typeof entry !== 'object') {
    const row = document.createElement('div');
    row.className = 'data-detail-row';

    const keyElement = document.createElement('span');
    keyElement.className = 'data-detail-key';
    keyElement.textContent = 'valore';

    const valueElement = document.createElement('span');
    valueElement.className = 'data-detail-value';
    valueElement.textContent = formatDetailValue(entry);

    row.append(keyElement, valueElement);
    modalDetails.appendChild(row);
    return;
  }

  const entriesList = Object.entries(entry);
  if (!entriesList.length) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = 'Nessun dettaglio disponibile per questo record.';
    modalDetails.appendChild(empty);
    return;
  }

  entriesList.forEach(([key, value]) => {
    const row = document.createElement('div');
    row.className = 'data-detail-row';

    const keyElement = document.createElement('span');
    keyElement.className = 'data-detail-key';
    keyElement.textContent = key;

    const valueElement = document.createElement('span');
    valueElement.className = 'data-detail-value';
    valueElement.textContent = formatDetailValue(value);

    row.append(keyElement, valueElement);
    modalDetails.appendChild(row);
  });
}

function formatDetailValue(value) {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2);
    } catch (error) {
      return '[Oggetto]';
    }
  }
  return `${value}`;
}

function toggleDialog(shouldOpen) {
  if (!modal) return;
  if (shouldOpen) {
    if (typeof modal.showModal === 'function') {
      modal.showModal();
    } else {
      modal.setAttribute('open', '');
    }
  } else {
    if (typeof modal.close === 'function') {
      modal.close();
    }
    modal.removeAttribute('open');
  }
}

function closeModal() {
  toggleDialog(false);
  currentEntry = null;
  currentMode = 'view';
  formError.classList.add('hidden');
  formError.textContent = '';
  modalSubtitle.textContent = '';
  payloadField.value = '';
  renderDetails(null);
}

async function handleSave() {
  formError.classList.add('hidden');
  formError.textContent = '';
  let payload;
  try {
    payload = JSON.parse(payloadField.value || '{}');
  } catch (error) {
    formError.textContent = 'Payload JSON non valido.';
    formError.classList.remove('hidden');
    return;
  }

  try {
    if (currentMode === 'edit') {
      const entryId = getEntryId(currentEntry || {});
      if (!entryId) {
        throw new Error('ID del record non disponibile.');
      }
      await mutate(`/api/data/${encodeURIComponent(entryId)}`, 'PUT', payload);
    } else {
      await mutate('/api/data', 'POST', payload);
    }
    closeModal();
    await fetchData();
  } catch (error) {
    formError.textContent = error.message || 'Impossibile salvare il record.';
    formError.classList.remove('hidden');
  }
}

async function mutate(url, method, body) {
  const config = { method };
  const upperMethod = (method || '').toUpperCase();
  if (upperMethod === 'POST' || upperMethod === 'PUT' || upperMethod === 'PATCH') {
    config.headers = { 'Content-Type': 'application/json' };
    config.body = JSON.stringify(body ?? {});
  } else if (body !== undefined) {
    config.headers = { 'Content-Type': 'application/json' };
    config.body = JSON.stringify(body);
  }

  const response = await fetch(url, config);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload?.detail || payload?.message;
    throw new Error(detail || 'Richiesta non riuscita.');
  }
  return response.json().catch(() => ({}));
}

async function handleTableClick(event) {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const row = button.closest('tr');
  if (!row) return;
  const entryId = row.dataset.id;
  const entry = entries.find((item) => getEntryId(item) === entryId) || null;
  const action = button.dataset.action;

  if (action === 'view') {
    openModal('view', entry);
  } else if (action === 'edit') {
    openModal('edit', entry);
  } else if (action === 'delete' && entryId) {
    const confirmed = window.confirm('Eliminare definitivamente questo record?');
    if (!confirmed) return;
    try {
      await mutate(`/api/data/${encodeURIComponent(entryId)}`, 'DELETE');
      await fetchData();
    } catch (error) {
      setStatus({ message: error.message || 'Impossibile eliminare il record.', tone: 'error' });
    }
  }
}

function registerEvents() {
  createButton?.addEventListener('click', () => openModal('create'));
  tableBody?.addEventListener('click', handleTableClick);
  saveButton?.addEventListener('click', handleSave);
  closeButton?.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('cancel', (event) => {
      event.preventDefault();
      closeModal();
    });
    modal.addEventListener('close', () => {
      currentEntry = null;
      currentMode = 'view';
    });
  }
}

registerEvents();
fetchData();
