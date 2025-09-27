const modelsList = document.querySelector('#models-list');
const template = document.querySelector('#model-template');
const filterSelect = document.querySelector('#capability-filter');

const textForm = document.querySelector('#text-form');
const textOutput = document.querySelector('#text-output');
const imageForm = document.querySelector('#image-form');
const imageOutput = document.querySelector('#image-output');
const videoForm = document.querySelector('#video-form');
const videoOutput = document.querySelector('#video-output');
const textModelSelect = document.querySelector('#text-model');
const imageModelSelect = document.querySelector('#image-model');
const videoModelSelect = document.querySelector('#video-model');
const filterInputs = Array.from(document.querySelectorAll('input[data-filter-for]'));

const SELECT_CONFIG = [
  { select: textModelSelect, capability: 'text' },
  { select: imageModelSelect, capability: 'image' },
  { select: videoModelSelect, capability: 'video' },
];

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
    populateModelSelects(modelsCache);
    renderModels(modelsCache);
  } catch (err) {
    modelsList.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

function buildSelectOptions(models, capability) {
  return models.slice().sort((a, b) => {
    const aHas = (a.capabilities || []).includes(capability);
    const bHas = (b.capabilities || []).includes(capability);
    if (aHas === bHas) return 0;
    return aHas ? -1 : 1;
  });
}

function populateModelSelects(models) {
  SELECT_CONFIG.forEach(({ select, capability }) => {
    if (!select) return;
    const previousValue = select.value;
    const options = buildSelectOptions(models, capability);
    select.innerHTML = '';
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Seleziona un modello';
    select.appendChild(placeholder);
    options.forEach((model) => {
      const option = document.createElement('option');
      option.value = model.id;
      option.textContent = model.name || model.id;
      option.dataset.provider = model.provider || '';
      option.dataset.capabilities = (model.capabilities || []).join(',');
      select.appendChild(option);
    });
    if (previousValue && select.querySelector(`option[value="${previousValue.replace(/"/g, '\\"')}"]`)) {
      select.value = previousValue;
    } else {
      select.value = '';
    }
  });
}

function filterSelectOptions(input) {
  const targetId = input.dataset.filterFor;
  if (!targetId) return;
  const select = document.querySelector(`#${targetId}`);
  if (!select) return;
  const term = input.value.trim().toLowerCase();
  Array.from(select.options).forEach((option) => {
    if (!option.value) {
      option.hidden = false;
      return;
    }
    const text = `${option.textContent} ${option.value} ${option.dataset.provider || ''}`
      .trim()
      .toLowerCase();
    option.hidden = term && !text.includes(term);
  });
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
      const pricingElement = clone.querySelector('.model-pricing');
      if (model.pricing_display) {
        pricingElement.textContent = `Costo stimato: ${model.pricing_display}`;
      } else {
        pricingElement.textContent = formatPricing(model.pricing);
      }
      clone.querySelectorAll('button[data-target]').forEach((btn) => {
        btn.addEventListener('click', () => {
          selectModelForTarget(btn.dataset.target, model);
        });
      });
      modelsList.appendChild(clone);
    });
}

filterSelect.addEventListener('change', () => renderModels(modelsCache));

function ensureOption(select, model) {
  if (!select) return null;
  const existing = select.querySelector(`option[value="${model.id.replace(/"/g, '\\"')}"]`);
  if (existing) {
    existing.textContent = model.name || model.id;
    return existing;
  }
  const option = document.createElement('option');
  option.value = model.id;
  option.textContent = model.name || model.id;
  option.dataset.provider = model.provider || '';
  option.dataset.capabilities = (model.capabilities || []).join(',');
  select.appendChild(option);
  return option;
}

function selectModelForTarget(targetId, model) {
  if (!targetId) return;
  const select = document.querySelector(`#${targetId}`);
  if (!select) return;
  const filterInput = document.querySelector(`input[data-filter-for="${targetId}"]`);
  if (filterInput) {
    filterInput.value = '';
    filterSelectOptions(filterInput);
  }
  ensureOption(select, model);
  select.value = model.id;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  select.focus();
}

filterInputs.forEach((input) => {
  input.addEventListener('input', () => filterSelectOptions(input));
});

async function handleTextSubmit(event) {
  event.preventDefault();
  const model = textModelSelect.value.trim();
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
  const model = imageModelSelect.value.trim();
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
  const model = videoModelSelect.value.trim();
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
