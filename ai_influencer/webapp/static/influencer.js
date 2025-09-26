const form = document.getElementById("influencer-form");
const statusEl = document.getElementById("influencer-status");
const profileEl = document.getElementById("influencer-profile");
const metricsEl = document.getElementById("influencer-metrics");
const mediaEl = document.getElementById("influencer-media");

const methodLabels = {
  official: "API ufficiali",
  scrape: "Web scraping",
};

function setStatus(message, state = "info") {
  if (!statusEl) return;
  statusEl.textContent = message;
  statusEl.className = "status-message";
  if (state === "loading") {
    statusEl.classList.add("loading");
  } else if (state === "error") {
    statusEl.classList.add("error");
  } else if (state === "empty") {
    statusEl.classList.add("empty");
  }
}

function showEmpty(container, message) {
  if (!container) return;
  container.classList.remove("error");
  container.classList.add("empty");
  container.textContent = message;
}

function clearContainer(container) {
  if (!container) return;
  container.classList.remove("empty", "error");
  container.innerHTML = "";
}

function formatLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatValue(value) {
  if (value == null) {
    return "—";
  }
  if (typeof value === "number") {
    return new Intl.NumberFormat("it-IT").format(value);
  }
  return String(value);
}

function renderKeyValue(container, data, emptyMessage) {
  if (!container) return;
  const entries = Object.entries(data || {});
  if (entries.length === 0) {
    showEmpty(container, emptyMessage);
    return;
  }
  clearContainer(container);
  const list = document.createElement("dl");
  for (const [key, value] of entries) {
    const dt = document.createElement("dt");
    dt.textContent = formatLabel(key);
    const dd = document.createElement("dd");
    dd.textContent = formatValue(value);
    list.append(dt, dd);
  }
  container.append(list);
}

function renderMedia(container, media) {
  if (!container) return;
  if (!Array.isArray(media) || media.length === 0) {
    showEmpty(container, "Nessun contenuto disponibile.");
    return;
  }

  clearContainer(container);
  const grid = document.createElement("div");
  grid.className = "media-grid";

  media.forEach((item) => {
    const card = document.createElement("div");
    card.className = "media-item";

    const title = document.createElement("strong");
    title.textContent = item.titolo ?? "Contenuto";
    card.appendChild(title);

    if (item.tipo) {
      const kind = document.createElement("span");
      kind.textContent = `Tipo: ${item.tipo}`;
      card.appendChild(kind);
    }

    if (item.pubblicato_il) {
      const published = document.createElement("span");
      try {
        const date = new Date(item.pubblicato_il);
        published.textContent = `Pubblicato il: ${date.toLocaleString("it-IT")}`;
      } catch (error) {
        published.textContent = `Pubblicato il: ${item.pubblicato_il}`;
      }
      card.appendChild(published);
    }

    if (item.url) {
      const link = document.createElement("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = item.url;
      card.appendChild(link);
    }

    grid.appendChild(card);
  });

  container.appendChild(grid);
}

function setLoadingState() {
  setStatus("Richiesta in corso...", "loading");
  showEmpty(profileEl, "Recupero profilo in corso...");
  showEmpty(metricsEl, "Recupero metriche in corso...");
  showEmpty(mediaEl, "Recupero contenuti in corso...");
}

function resetResults() {
  showEmpty(profileEl, "Nessun dato ancora disponibile.");
  showEmpty(metricsEl, "Nessun dato ancora disponibile.");
  showEmpty(mediaEl, "Nessun contenuto disponibile.");
}

if (form) {
  const methodRadios = form.querySelectorAll("input[name='method']");
  methodRadios.forEach((radio) => {
    radio.addEventListener("change", (event) => {
      const selected = event.target.value;
      const label = methodLabels[selected] ?? selected;
      setStatus(`Metodo selezionato: ${label}.`);
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(form);
    const identifier = String(formData.get("identifier") ?? "").trim();
    const method = String(formData.get("method") ?? "official");

    if (!identifier) {
      setStatus("Inserisci un username o un URL valido.", "error");
      return;
    }

    setLoadingState();

    try {
      const response = await fetch("/api/influencer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ identifier, method }),
      });

      if (!response.ok) {
        let detail = "Impossibile recuperare i dati dell'influencer.";
        try {
          const payload = await response.json();
          if (payload?.detail) {
            detail = payload.detail;
          }
        } catch (error) {
          // ignore
        }
        throw new Error(detail);
      }

      const payload = await response.json();
      const retrievedAt = payload.retrieved_at
        ? new Date(payload.retrieved_at).toLocaleString("it-IT")
        : null;
      const sourceLabel = methodLabels[payload.method] ?? methodLabels[method];

      renderKeyValue(profileEl, payload.profile, "Profilo non disponibile.");
      renderKeyValue(metricsEl, payload.metrics, "Metriche non disponibili.");
      renderMedia(mediaEl, payload.media);

      const summaryParts = [];
      if (sourceLabel) {
        summaryParts.push(`Fonte: ${sourceLabel}`);
      }
      if (retrievedAt) {
        summaryParts.push(`Aggiornato: ${retrievedAt}`);
      }
      if (summaryParts.length === 0) {
        summaryParts.push("Dati aggiornati.");
      }
      setStatus(summaryParts.join(" • "));
    } catch (error) {
      console.error(error);
      setStatus(error.message || "Errore imprevisto.", "error");
      resetResults();
    }
  });
} else {
  resetResults();
}
