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

const statusEl = document.querySelector('#config-status');
const form = document.querySelector('#openrouter-form');
const apiKeyInput = document.querySelector('#openrouter-api-key');
const baseUrlInput = document.querySelector('#openrouter-base-url');
const clearButton = document.querySelector('#clear-settings');

function renderStatus(payload) {
  if (!statusEl) return;
  statusEl.className = 'status-message';
  const lines = [];
  if (payload.has_api_key) {
    const preview = payload.api_key_preview || '••••';
    lines.push(`Chiave configurata: ${preview}`);
  } else {
    lines.push('Nessuna chiave configurata.');
    statusEl.classList.add('empty');
  }
  if (payload.base_url) {
    lines.push(`Endpoint personalizzato: ${payload.base_url}`);
  }
  statusEl.textContent = lines.join('\n');
}

async function loadConfig() {
  if (!statusEl) return;
  statusEl.textContent = 'Caricamento configurazione...';
  statusEl.className = 'status-message loading';
  try {
    const response = await fetch('/api/config/openrouter');
    if (!response.ok) {
      throw new Error('Impossibile recuperare la configurazione');
    }
    const payload = await response.json();
    renderStatus(payload);
  } catch (error) {
    statusEl.className = 'status-message error';
    statusEl.textContent = error.message;
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  if (!form) return;
  const apiKey = apiKeyInput?.value.trim() ?? '';
  const baseUrl = baseUrlInput?.value.trim() ?? '';
  const payload = {};
  if (apiKey) payload.api_key = apiKey;
  if (baseUrl) payload.base_url = baseUrl;
  if (!payload.api_key && !payload.base_url) {
    showToast('Inserisci almeno un valore da salvare', 'error');
    return;
  }
  try {
    const response = await fetch('/api/config/openrouter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || 'Salvataggio non riuscito');
    }
    renderStatus(data);
    showToast('Configurazione aggiornata', 'success');
    form.reset();
    apiKeyInput?.focus();
  } catch (error) {
    showToast(error.message, 'error');
    if (statusEl) {
      statusEl.className = 'status-message error';
      statusEl.textContent = error.message;
    }
  }
}

function handleClear() {
  form?.reset();
  apiKeyInput?.focus();
  showToast('Modulo pulito', 'success');
}

form?.addEventListener('submit', handleSubmit);
clearButton?.addEventListener('click', handleClear);

loadConfig();
