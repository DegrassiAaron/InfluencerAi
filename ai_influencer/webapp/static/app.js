const modelsList = document.querySelector('#models-list');
const template = document.querySelector('#model-template');
const filterSelect = document.querySelector('#capability-filter');

const textForm = document.querySelector('#text-form');
const textOutput = document.querySelector('#text-output');
const imageForm = document.querySelector('#image-form');
const imageOutput = document.querySelector('#image-output');
const videoForm = document.querySelector('#video-form');
const videoOutput = document.querySelector('#video-output');

let modelsCache = [];

const PRICING_LABELS = {
  input: 'Input',
  output: 'Output',
  image: 'Immagini',
  image_generation: 'Generazione immagini',
  video: 'Video',
  video_generation: 'Generazione video',
  audio: 'Audio',
  audio_generation: 'Generazione audio',
};

function formatPriceAmount(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return null;
  }
  const abs = Math.abs(amount);
  let fractionDigits = 2;
  if (abs > 0 && abs < 0.01) {
    fractionDigits = 6;
  } else if (abs < 0.1) {
    fractionDigits = 4;
  }
  let formatted = amount.toFixed(fractionDigits);
  formatted = formatted.replace(/0+$/, '').replace(/\.$/, '');
  return `$${formatted || '0'}`;
}

function formatPricingValue(value) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number') {
    return formatPriceAmount(value);
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const numeric = formatPriceAmount(trimmed);
    return numeric || trimmed;
  }
  return null;
}

function humanizeKey(key) {
  if (!key) return '';
  if (PRICING_LABELS[key]) return PRICING_LABELS[key];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatPricing(pricing) {
  if (!pricing || typeof pricing !== 'object') {
    return 'Prezzi non disponibili';
  }

  const entries = [];

  const visit = (key, value, prefix = '') => {
    if (value === null || value === undefined) {
      return;
    }

    const label = prefix ? `${prefix} ${humanizeKey(key)}` : humanizeKey(key);

    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const nested = Object.entries(value);
      if (!nested.length) return;
      nested.forEach(([nestedKey, nestedValue]) => visit(nestedKey, nestedValue, label));
      return;
    }

    const formatted = formatPricingValue(value);
    if (formatted) {
      entries.push(`${label}: ${formatted}`);
    }
  };

  Object.entries(pricing).forEach(([key, value]) => visit(key, value));

  if (!entries.length) {
    return 'Prezzi non disponibili';
  }

  return entries.join(' • ');
}

async function fetchModels() {
  modelsList.innerHTML = '<p class="loading">Caricamento modelli...</p>';
  try {
    const response = await fetch('/api/models');
    if (!response.ok) throw new Error('Impossibile recuperare i modelli');
    const payload = await response.json();
    modelsCache = payload.models || [];
    renderModels(modelsCache);
  } catch (err) {
    modelsList.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

function renderModels(models) {
  modelsList.innerHTML = '';
  if (!models.length) {
    modelsList.innerHTML = '<p class="empty">Nessun modello disponibile</p>';
    return;
  }
  const selected = filterSelect.value;
  models
    .filter((model) => selected === 'all' || (model.capabilities || []).includes(selected))
    .forEach((model) => {
      const clone = template.content.cloneNode(true);
      const card = clone.querySelector('.model-card');
      card.dataset.capabilities = (model.capabilities || []).join(',');
      clone.querySelector('.model-name').textContent = model.name;
      clone.querySelector('.model-provider').textContent = model.provider || '';
      const capabilities = model.capabilities?.length
        ? model.capabilities.join(', ')
        : 'Sconosciute';
      clone.querySelector('.model-capabilities').textContent = `Capacità: ${capabilities}`;
      clone.querySelector('.model-pricing').textContent = formatPricing(model.pricing);
      clone.querySelectorAll('button[data-target]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const target = document.querySelector(`#${btn.dataset.target}`);
          if (target) {
            target.value = model.id;
            target.focus();
          }
        });
      });
      modelsList.appendChild(clone);
    });
}

filterSelect.addEventListener('change', () => renderModels(modelsCache));

async function handleTextSubmit(event) {
  event.preventDefault();
  const model = document.querySelector('#text-model').value.trim();
  const prompt = document.querySelector('#text-prompt').value.trim();
  if (!model || !prompt) return;
  textOutput.textContent = 'Generazione in corso...';
  try {
    const response = await fetch('/api/generate/text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, prompt }),
    });
    if (!response.ok) throw new Error((await response.json()).detail || 'Errore');
    const payload = await response.json();
    textOutput.textContent = payload.content;
  } catch (err) {
    textOutput.textContent = `Errore: ${err.message}`;
  }
}

async function handleImageSubmit(event) {
  event.preventDefault();
  const model = document.querySelector('#image-model').value.trim();
  const prompt = document.querySelector('#image-prompt').value.trim();
  const negative = document.querySelector('#image-negative').value.trim();
  const width = Number(document.querySelector('#image-width').value);
  const height = Number(document.querySelector('#image-height').value);
  if (!model || !prompt) return;
  imageOutput.innerHTML = '<p class="loading">Generazione in corso...</p>';
  try {
    const response = await fetch('/api/generate/image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, prompt, negative_prompt: negative || null, width, height }),
    });
    if (!response.ok) throw new Error((await response.json()).detail || 'Errore');
    const payload = await response.json();
    if (payload.is_remote) {
      imageOutput.innerHTML = `<a href="${payload.image}" target="_blank" rel="noopener">Scarica immagine</a>`;
    } else {
      imageOutput.innerHTML = `<img src="data:image/png;base64,${payload.image}" alt="Generazione" />`;
    }
  } catch (err) {
    imageOutput.innerHTML = `<p class="error">Errore: ${err.message}</p>`;
  }
}

async function handleVideoSubmit(event) {
  event.preventDefault();
  const model = document.querySelector('#video-model').value.trim();
  const prompt = document.querySelector('#video-prompt').value.trim();
  const duration = document.querySelector('#video-duration').value;
  const size = document.querySelector('#video-size').value.trim();
  if (!model || !prompt) return;
  videoOutput.innerHTML = '<p class="loading">Generazione in corso...</p>';
  try {
    const response = await fetch('/api/generate/video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, prompt, duration: duration ? Number(duration) : null, size: size || null }),
    });
    if (!response.ok) throw new Error((await response.json()).detail || 'Errore');
    const payload = await response.json();
    if (payload.is_remote) {
      videoOutput.innerHTML = `<a href="${payload.video}" target="_blank" rel="noopener">Scarica video</a>`;
    } else {
      videoOutput.innerHTML = `<video controls src="data:video/mp4;base64,${payload.video}"></video>`;
    }
  } catch (err) {
    videoOutput.innerHTML = `<p class="error">Errore: ${err.message}</p>`;
  }
}

textForm.addEventListener('submit', handleTextSubmit);
imageForm.addEventListener('submit', handleImageSubmit);
videoForm.addEventListener('submit', handleVideoSubmit);

fetchModels();
