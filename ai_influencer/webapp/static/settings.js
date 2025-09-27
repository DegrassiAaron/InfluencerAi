function ensureToastContainer() {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  return container;
}

function showToast(message, state = 'info') {
  const container = ensureToastContainer();
  const toast = document.createElement('div');
  toast.className = `toast toast-${state}`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.add('visible');
  });
  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => {
      toast.remove();
      if (!container.childElementCount) {
        container.remove();
      }
    }, 250);
  }, 2000);
}

const tableBody = document.querySelector('#services-table-body');
const dialog = document.querySelector('#service-dialog');
const form = document.querySelector('#service-form');
const titleEl = document.querySelector('#service-dialog-title');
const envHintEl = document.querySelector('#service-env-hint');
const serviceIdInput = document.querySelector('#service-id');
const apiKeyInput = document.querySelector('#service-api-key');
const endpointInput = document.querySelector('#service-endpoint');
const cancelButton = document.querySelector('#service-cancel');

let servicesCache = [];
let activeService = null;

function renderEmptyState(message) {
  if (!tableBody) return;
  tableBody.innerHTML = '';
  const row = document.createElement('tr');
  row.className = 'empty';
  const cell = document.createElement('td');
  cell.colSpan = 4;
  cell.textContent = message;
  row.appendChild(cell);
  tableBody.appendChild(row);
}

function renderServicesTable(services) {
  if (!tableBody) return;
  tableBody.innerHTML = '';
  if (!services.length) {
    renderEmptyState('Nessun servizio configurabile.');
    return;
  }

  services.forEach((service) => {
    const row = document.createElement('tr');

    const serviceCell = document.createElement('td');
    serviceCell.textContent = service.name;
    row.appendChild(serviceCell);

    const endpointCell = document.createElement('td');
    if (service.endpoint) {
      endpointCell.textContent = service.endpoint;
      if (service.uses_default_endpoint && service.default_endpoint) {
        const badge = document.createElement('span');
        badge.className = 'table-hint';
        badge.textContent = 'predefinito';
        endpointCell.append(' ', badge);
      }
    } else {
      endpointCell.textContent = '—';
    }
    row.appendChild(endpointCell);

    const keyCell = document.createElement('td');
    if (service.has_api_key) {
      keyCell.textContent = service.api_key_preview ?? '••••';
      keyCell.title = 'Chiave configurata';
    } else {
      keyCell.textContent = '—';
      keyCell.title = 'Nessuna chiave configurata';
    }
    row.appendChild(keyCell);

    const actionsCell = document.createElement('td');
    actionsCell.className = 'actions';
    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'button-secondary';
    editButton.textContent = 'Modifica';
    editButton.addEventListener('click', () => openServiceDialog(service.id));
    actionsCell.appendChild(editButton);
    row.appendChild(actionsCell);

    tableBody.appendChild(row);
  });
}

async function loadServices() {
  if (!tableBody) return;
  renderEmptyState('Caricamento servizi...');
  try {
    const response = await fetch('/api/config/services');
    if (!response.ok) {
      throw new Error('Impossibile recuperare i servizi');
    }
    const payload = await response.json();
    servicesCache = Array.isArray(payload.services) ? payload.services : [];
    renderServicesTable(servicesCache);
  } catch (error) {
    renderEmptyState(error.message || 'Errore durante il caricamento.');
    showToast(error.message || 'Errore durante il caricamento', 'error');
  }
}

function openServiceDialog(serviceId) {
  const service = servicesCache.find((item) => item.id === serviceId);
  if (!service || !dialog || !form) return;

  activeService = service;
  form.reset();
  serviceIdInput.value = service.id;
  titleEl.textContent = `Modifica ${service.name}`;

  const envHints = [];
  if (service.env && typeof service.env === 'object') {
    Object.entries(service.env).forEach(([key, value]) => {
      if (!value) return;
      let label;
      if (key === 'api_key') {
        label = `Chiave: ${value}`;
      } else if (key === 'endpoint') {
        label = `Endpoint: ${value}`;
      } else {
        const friendlyKey = key
          .split('_')
          .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
          .join(' ');
        label = `${friendlyKey}: ${value}`;
      }
      envHints.push(label);
    });
  }
  envHintEl.textContent = envHints.length
    ? `Variabili ambiente: ${envHints.join(' · ')}`
    : '';

  apiKeyInput.value = '';
  apiKeyInput.placeholder = 'sk-...';
  endpointInput.value = '';
  endpointInput.placeholder = service.default_endpoint || '';
  if (service.endpoint && !service.uses_default_endpoint) {
    endpointInput.value = service.endpoint;
  }

  if (typeof dialog.showModal === 'function') {
    dialog.showModal();
  } else {
    dialog.setAttribute('open', '');
  }
  apiKeyInput.focus();
}

function closeServiceDialog() {
  if (!dialog || !form) return;
  form.reset();
  activeService = null;
  if (typeof dialog.close === 'function') {
    dialog.close();
  } else {
    dialog.removeAttribute('open');
  }
}

async function submitService(event) {
  event.preventDefault();
  if (!form || !activeService) return;

  const payload = {};
  const apiKeyValue = apiKeyInput.value.trim();
  const endpointValue = endpointInput.value.trim();

  if (apiKeyValue) {
    payload.api_key = apiKeyValue;
  }
  if (endpointValue) {
    payload.endpoint = endpointValue;
  } else if (!endpointValue && activeService && !activeService.uses_default_endpoint) {
    payload.endpoint = null;
  }

  if (Object.keys(payload).length === 0) {
    showToast('Inserisci almeno un valore da salvare', 'error');
    return;
  }

  try {
    const response = await fetch(`/api/config/services/${activeService.id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || 'Salvataggio non riuscito');
    }

    showToast('Configurazione aggiornata', 'success');
    closeServiceDialog();
    await loadServices();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

form?.addEventListener('submit', submitService);
cancelButton?.addEventListener('click', closeServiceDialog);

loadServices();
