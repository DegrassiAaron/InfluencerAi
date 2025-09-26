const form = document.getElementById("influencer-form");
const statusEl = document.getElementById("influencer-status");
const profileEl = document.getElementById("influencer-profile");
const metricsEl = document.getElementById("influencer-metrics");
const mediaEl = document.getElementById("influencer-media");

const methodLabels = {
  official: "API ufficiali",
  scrape: "Web scraping",
};

const downloadMimeFallback = "application/octet-stream";

function getFirstAvailable(item, keys) {
  return keys.map((key) => item?.[key]).find((value) => value != null && value !== "");
}

async function downloadFromSource(source, filename, mimeType = downloadMimeFallback) {
  if (!source) return false;

  let blob;
  try {
    if (source instanceof Blob) {
      blob = source;
    } else if (source instanceof ArrayBuffer) {
      blob = new Blob([source], { type: mimeType });
    } else if (ArrayBuffer.isView(source)) {
      const { buffer, byteOffset, byteLength } = source;
      const sliced = buffer.slice(byteOffset, byteOffset + byteLength);
      blob = new Blob([sliced], { type: mimeType });
    } else if (typeof source !== "string") {
      blob = new Blob([JSON.stringify(source)], { type: mimeType });
    } else if (/^https?:\/\//i.test(source)) {
      const response = await fetch(source);
      blob = await response.blob();
    } else if (source.startsWith("data:")) {
      const response = await fetch(source);
      blob = await response.blob();
    } else {
      const cleaned = source.replace(/\s+/g, "");
      const byteCharacters = atob(cleaned);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i += 1) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      blob = new Blob([byteArray], { type: mimeType });
    }
  } catch (error) {
    console.error("Errore durante il recupero del contenuto da scaricare", error);
    return false;
  }

  try {
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
    return true;
  } catch (error) {
    console.error("Errore durante il download del file", error);
    return false;
  }
}

function createIconButton(icon, label, title) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "media-action";
  button.title = title || label;

  const iconSpan = document.createElement("span");
  iconSpan.className = "media-action-icon";
  iconSpan.textContent = icon;

  const labelSpan = document.createElement("span");
  labelSpan.className = "media-action-label";
  labelSpan.textContent = label;

  button.append(iconSpan, labelSpan);
  return button;
}

function ensureToastContainer() {
  let toastContainer = document.querySelector(".toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.className = "toast-container";
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

function showToast(message, state = "info") {
  const container = ensureToastContainer();
  const toast = document.createElement("div");
  toast.className = `toast toast-${state}`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.add("visible");
  });
  setTimeout(() => {
    toast.classList.remove("visible");
    setTimeout(() => {
      toast.remove();
      if (!container.childElementCount) {
        container.remove();
      }
    }, 250);
  }, 2000);
}

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

    const textContent = getFirstAvailable(item, ["testo", "descrizione", "caption", "text"]);
    if (textContent) {
      const textParagraph = document.createElement("p");
      textParagraph.textContent = textContent;
      card.appendChild(textParagraph);
    }

    if (item.url) {
      const link = document.createElement("a");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = item.url;
      card.appendChild(link);
    }

    const actions = document.createElement("div");
    actions.className = "media-actions";

    const mainImageSource = getFirstAvailable(item, [
      "immagine_principale",
      "immagine",
      "media",
      "image",
      "image_url",
      "media_url",
    ]);
    if (mainImageSource) {
      const downloadMainBtn = createIconButton("⬇️", "Scarica immagine", "Scarica immagine principale");
      downloadMainBtn.addEventListener("click", async () => {
        const success = await downloadFromSource(mainImageSource, `${item.id || "media"}.jpg`, "image/jpeg");
        showToast(success ? "Immagine scaricata." : "Impossibile scaricare l'immagine.", success ? "success" : "error");
      });
      actions.appendChild(downloadMainBtn);
    }

    const thumbnailSource = getFirstAvailable(item, [
      "thumbnail",
      "miniatura",
      "anteprima",
      "thumbnail_url",
      "preview",
    ]);
    if (thumbnailSource) {
      const downloadThumbBtn = createIconButton("🖼️", "Scarica thumbnail", "Scarica immagine di anteprima");
      downloadThumbBtn.addEventListener("click", async () => {
        const success = await downloadFromSource(thumbnailSource, `${item.id || "media"}-thumbnail.jpg`, "image/jpeg");
        showToast(success ? "Thumbnail scaricata." : "Impossibile scaricare la thumbnail.", success ? "success" : "error");
      });
      actions.appendChild(downloadThumbBtn);
    }

    if (textContent) {
      const copyTextBtn = createIconButton("📋", "Copia testo", "Copia il testo associato");
      copyTextBtn.addEventListener("click", async () => {
        try {
          if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(textContent);
          } else {
            const textarea = document.createElement("textarea");
            textarea.value = textContent;
            textarea.setAttribute("readonly", "true");
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.select();
            const copied = document.execCommand("copy");
            textarea.remove();
            if (!copied) {
              throw new Error("Fallback copy failed");
            }
          }
          showToast("Testo copiato negli appunti.", "success");
        } catch (error) {
          console.error("Errore durante la copia del testo", error);
          showToast("Impossibile copiare il testo.", "error");
        }
      });
      actions.appendChild(copyTextBtn);
    }

    const transcript = getFirstAvailable(item, [
      "trascrizione",
      "trascrizione_testuale",
      "transcription",
      "captions",
    ]);
    if (transcript) {
      const downloadTranscriptBtn = createIconButton("📝", "Scarica trascrizione", "Scarica trascrizione in formato testo");
      downloadTranscriptBtn.addEventListener("click", async () => {
        const blob = new Blob([transcript], { type: "text/plain;charset=utf-8" });
        const success = await downloadFromSource(blob, `${item.id || "media"}-trascrizione.txt`, "text/plain;charset=utf-8");
        showToast(success ? "Trascrizione scaricata." : "Impossibile scaricare la trascrizione.", success ? "success" : "error");
      });
      actions.appendChild(downloadTranscriptBtn);
    }

    const linkSource = getFirstAvailable(item, ["url", "link", "permalink"]);
    if (linkSource) {
      const openLinkBtn = createIconButton("🔗", "Apri link", "Apri il contenuto in una nuova scheda");
      openLinkBtn.addEventListener("click", () => {
        const opened = window.open(linkSource, "_blank", "noopener,noreferrer");
        if (opened) {
          showToast("Link aperto in una nuova scheda.", "success");
        } else {
          showToast("Impossibile aprire il link.", "error");
        }
      });
      actions.appendChild(openLinkBtn);
    }

    if (actions.childElementCount > 0) {
      card.appendChild(actions);
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
