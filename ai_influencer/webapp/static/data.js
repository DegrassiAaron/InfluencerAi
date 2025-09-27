const API_ENDPOINT = "/api/data";
const tableBody = document.querySelector("#data-table tbody");
const statusBox = document.getElementById("data-status");
const form = document.getElementById("data-form");
const idInput = document.getElementById("record-id");
const nameInput = document.getElementById("record-name");
const valueInput = document.getElementById("record-value");
const cancelEditButton = document.getElementById("cancel-edit");
const saveButton = document.getElementById("save-record");

function showStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
  statusBox.classList.toggle("empty", !isError && !tableBody.children.length);
}

function resetForm() {
  form.reset();
  idInput.value = "";
  cancelEditButton.hidden = true;
  saveButton.textContent = "Salva record";
  nameInput.focus();
}

function renderRecords(records) {
  tableBody.innerHTML = "";
  if (!records.length) {
    showStatus("Nessun record presente.");
    return;
  }

  records.forEach((record) => {
    const row = document.createElement("tr");
    row.dataset.id = record.id;

    const idCell = document.createElement("td");
    idCell.textContent = record.id;
    row.appendChild(idCell);

    const nameCell = document.createElement("td");
    nameCell.textContent = record.name;
    row.appendChild(nameCell);

    const valueCell = document.createElement("td");
    valueCell.textContent = record.value;
    row.appendChild(valueCell);

    const updatedCell = document.createElement("td");
    updatedCell.textContent = new Date(record.updated_at).toLocaleString();
    row.appendChild(updatedCell);

    const actionsCell = document.createElement("td");
    actionsCell.className = "actions";

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Modifica";
    editButton.addEventListener("click", () => startEdit(record));

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button-secondary";
    deleteButton.textContent = "Elimina";
    deleteButton.addEventListener("click", () => deleteRecord(record.id));

    actionsCell.append(editButton, deleteButton);
    row.appendChild(actionsCell);

    tableBody.appendChild(row);
  });

  showStatus(`Record disponibili: ${records.length}`);
}

async function loadRecords() {
  try {
    const response = await fetch(API_ENDPOINT);
    if (!response.ok) {
      throw new Error(`Impossibile caricare i dati (${response.status})`);
    }
    const payload = await response.json();
    renderRecords(payload.items ?? []);
  } catch (error) {
    console.error(error);
    showStatus("Errore durante il caricamento dei dati", true);
  }
}

function startEdit(record) {
  idInput.value = record.id;
  nameInput.value = record.name;
  valueInput.value = record.value;
  saveButton.textContent = "Aggiorna record";
  cancelEditButton.hidden = false;
  nameInput.focus();
}

async function submitData(event) {
  event.preventDefault();
  const payload = {
    name: nameInput.value.trim(),
    value: valueInput.value.trim(),
  };

  if (!payload.name || !payload.value) {
    showStatus("Compila tutti i campi prima di salvare", true);
    return;
  }

  const recordId = idInput.value ? Number(idInput.value) : null;
  const method = recordId ? "PUT" : "POST";
  const url = recordId ? `${API_ENDPOINT}/${recordId}` : API_ENDPOINT;

  try {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      const message = detail.detail || "Errore durante il salvataggio";
      throw new Error(message);
    }

    resetForm();
    await loadRecords();
    showStatus("Record salvato correttamente");
  } catch (error) {
    console.error(error);
    showStatus(error.message, true);
  }
}

async function deleteRecord(recordId) {
  if (!Number.isInteger(recordId)) {
    return;
  }

  try {
    const response = await fetch(`${API_ENDPOINT}/${recordId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      const message = detail.detail || "Impossibile eliminare il record";
      throw new Error(message);
    }
    await loadRecords();
    showStatus("Record eliminato");
  } catch (error) {
    console.error(error);
    showStatus(error.message, true);
  }
}

cancelEditButton.addEventListener("click", () => {
  resetForm();
  showStatus("Modifica annullata");
});

form.addEventListener("submit", submitData);

document.addEventListener("DOMContentLoaded", loadRecords);
