# Influencer AI – Pipeline ibrida OpenRouter + Stable Diffusion

> Toolkit completo per generare, ripulire e addestrare influencer virtuali combinando servizi cloud (OpenRouter) e strumenti locali GPU-ready.

## Indice
- [Panoramica](#panoramica)
- [Architettura del repository](#architettura-del-repository)
- [Prerequisiti](#prerequisiti)
- [Setup rapido](#setup-rapido)
- [Variabili d'ambiente chiave](#variabili-dambiente-chiave)
- [Esecuzione della pipeline](#esecuzione-della-pipeline)
  - [1. Preparazione del dataset](#1-preparazione-del-dataset)
  - [2. Storyboard e copy con OpenRouter](#2-storyboard-e-copy-con-openrouter)
  - [3. Generazione batch di immagini](#3-generazione-batch-di-immagini)
  - [4. Controllo qualità](#4-controllo-qualità)
  - [5. Augment e captioning](#5-augment-e-captioning)
  - [6. Training LoRA](#6-training-lora)
- [Gestione dei checkpoint base](#gestione-dei-checkpoint-base)
- [Control Hub web](#control-hub-web)
- [Struttura delle cartelle dati](#struttura-delle-cartelle-dati)
- [Interfacce alternative](#interfacce-alternative)
- [Troubleshooting rapido](#troubleshooting-rapido)
- [Test e sviluppo](#test-e-sviluppo)
- [Documentazione aggiuntiva e licenza](#documentazione-aggiuntiva-e-licenza)

## Variabili d'ambiente chiave
Configura queste variabili prima di avviare gli script o i container. Possono essere esportate nel terminale locale, inserite in un file `.env` caricato da Docker Compose oppure definite direttamente nei servizi (`docker compose ... --env-file`).

| Variabile | Obbligatoria | Descrizione | Utilizzata da |
| --------- | ------------ | ----------- | ------------- |
| `OPENROUTER_API_KEY` | ✅ | Chiave privata per autenticare tutte le chiamate verso OpenRouter. | Script CLI, webapp FastAPI |
| `OPENROUTER_BASE_URL` | ➖ | Endpoint personalizzato (ad es. proxy self-hosted); di default `https://openrouter.ai/api/v1`. | Script CLI, webapp |
| `OPENROUTER_APP_TITLE` | ➖ | Nome dell'applicazione riportato negli header verso OpenRouter, utile per il billing dashboard. | Webapp |
| `OPENROUTER_APP_URL` | ➖ | URL pubblico del progetto da mostrare nel billing dashboard di OpenRouter. | Webapp |
| `BASE_MODEL` | ➖ | Percorso del checkpoint SDXL da utilizzare di default nel training LoRA. | Script `train_lora.sh`, workflow n8n |
| `N8N_BASIC_AUTH_ACTIVE` | ➖ | Abilita/disabilita la Basic Auth sul pannello e sui webhook (`true` di default). | Servizio Docker `n8n_local` |
| `N8N_BASIC_AUTH_USER` | ➖ | Username per l'accesso all'interfaccia n8n e ai webhook protetti. | Servizio Docker `n8n_local` |
| `N8N_BASIC_AUTH_PASSWORD` | ➖ | Password associata allo user Basic Auth n8n. | Servizio Docker `n8n_local` |
| `N8N_WEBHOOK_URL` | ➖ | URL pubblico dei webhook (utile dietro tunnel/reverse proxy). | Servizio Docker `n8n_local` |
| `HF_TOKEN` | ➖ | Token Hugging Face per scaricare modelli privati o ad accesso limitato. | Script `bootstrap_models.py`, CLI |

> Suggerimento: crea un file `ai_influencer/docker/.env` copiando `ai_influencer/docker/.env.example` e aggiorna i valori sensibili una sola volta.

## Panoramica
Il progetto **Influencer AI** fornisce un flusso end-to-end per costruire una persona virtuale partendo da un piccolo set di immagini reali, espandere il dataset con generazioni guidate da prompt, verificarne la qualità e addestrare un LoRA fotorealistico su Stable Diffusion XL. Il repository include:

- stack Docker ottimizzato per GPU NVIDIA con servizi "tools" (Python utility), "comfyui" e "kohya" per l'addestramento;
- script Python per la preparazione del dataset, la generazione tramite OpenRouter e la creazione di caption augmentate;
- un servizio FastAPI che espone API REST (documentate via Swagger) per consultare i modelli OpenRouter, lanciare generazioni testo/immagine/video e simulare l'analisi dei profili social;
- automazioni opzionali (GUI desktop e workflow n8n) per orchestrare l'intero ciclo.

## Architettura del repository
- `ai_influencer/docker/docker-compose.yaml` – definisce i container `tools`, `comfyui`, `kohya` e `webapp` con runtime NVIDIA, montando dati, script e modelli sul file system condiviso.
- `ai_influencer/scripts/` – raccolta di utility CLI, fra cui:
  - `prepare_dataset.py` per remove.bg, face crop e normalizzazione immagini;
  - `openrouter_text.py`, `openrouter_images.py` e `openrouter_batch.py` per interrogare le API OpenRouter;
  - `qc_face_sim.py` per filtrare il dataset tramite similarità facciale e nitidezza;
  - `augment_and_caption.py` per augment e generazione caption coerenti con i metadati;
  - `train_lora.sh` per avviare `sd-scripts` all'interno del container `kohya`.
- `ai_influencer/webapp/` – applicazione FastAPI che espone endpoint REST (`/api/models`, `/api/generate/*`, `/api/influencer`, `/api/services/*`) e genera automaticamente la documentazione interattiva Swagger su `/docs`.
- `ai_influencer/scripts/gui_app.py` – interfaccia Tkinter che incapsula i principali step della pipeline CLI.
- `ai_influencer/n8n/flow.json` – workflow n8n che esegue gli script chiave via webhook Docker.
- `tests/` – suite Pytest che copre l'SDK OpenRouter asincrono e gli endpoint principali della webapp.

## Prerequisiti
- **Hardware**: GPU NVIDIA compatibile con CUDA, preferibilmente >= 12 GB VRAM.
- **Software**: Docker Desktop (o Docker Engine) con supporto GPU attivo, Docker Compose v2, Git.
- **Account/Asset**:
  - chiave API OpenRouter (`OPENROUTER_API_KEY`), opzionalmente endpoint personalizzato (`OPENROUTER_BASE_URL`);
  - accesso a Hugging Face (token opzionale) per scaricare automaticamente il modello base SDXL al primo avvio.
- **Storage**: almeno 40 GB liberi per dataset, modelli e checkpoint LoRA.

## Setup rapido
1. Clona il repository e posizionati nella root del progetto:
   ```bash
   git clone https://github.com/<org>/InfluencerAi.git
   cd InfluencerAi
   ```
2. Esporta la chiave OpenRouter nel terminale corrente (o aggiungila a un file `.env` richiamato da Docker Compose):
   ```bash
   export OPENROUTER_API_KEY="sk-or-..."
   ```
3. Avvia lo stack GPU (al primo avvio scarica automaticamente ~6.5 GiB di pesi SDXL in `ai_influencer/models/base/`):
   ```bash
   docker compose -f ai_influencer/docker/docker-compose.yaml up -d
   ```
   I container principali saranno:
   - `ai_influencer_tools` (utility Python + CLI pipeline)
   - `comfyui_local` (interfaccia ComfyUI su http://localhost:8188)
   - `kohya_local` (ambiente kohya_ss per LoRA)
   - `ai_influencer_webapp` (Control Hub su http://localhost:8000)
   - `n8n_local` (automazione no-code n8n su http://localhost:5678)

## Esecuzione della pipeline
Esegui i comandi nel container `ai_influencer_tools` salvo diversa indicazione:
```bash
docker exec -it ai_influencer_tools bash
```

### 1. Preparazione del dataset
Raccogli almeno due immagini del soggetto in `ai_influencer/data/input_raw/`, quindi lancia:
```bash
python3 scripts/prepare_dataset.py \
  --in data/input_raw \
  --out data/cleaned \
  --do_rembg \
  --do_facecrop
```
Lo script applica remove.bg, ritaglia automaticamente il volto (InsightFace) e salva i file puliti.

### 2. Storyboard e copy con OpenRouter
Genera storyboard, script e caption seed a partire dal prompt bank YAML:
```bash
export OPENROUTER_API_KEY="sk-or-..."
python3 scripts/openrouter_text.py \
  --prompt_bank scripts/prompt_bank.yaml \
  --model meta-llama/llama-3.1-70b-instruct \
  --out data/text/storyboard.json
```
Il risultato è un JSON strutturato con scene, dialoghi e caption per guidare i passi successivi.

### 3. Generazione batch di immagini
Crea batch coerenti con le scene e i controlli creativi:
```bash
python3 scripts/openrouter_images.py \
  --prompt_bank scripts/prompt_bank.yaml \
  --model sdxl \
  --out data/synth_openrouter \
  --per_scene 12 \
  --size 1024x1024
```
`--model` accetta sia l'ID completo OpenRouter sia i seguenti alias pronti all'uso:

> Consulta anche [README_OPENROUTER.md](README_OPENROUTER.md) per il catalogo completo degli alias e le tariffe aggiornate.

| Alias | ID completo | Scheda OpenRouter |
| ----- | ----------- | ----------------- |
| `sdxl` | `stabilityai/sdxl` | <https://openrouter.ai/models/stabilityai/sdxl> |
| `sdxl-turbo` | `stabilityai/sdxl-turbo` | <https://openrouter.ai/models/stabilityai/sdxl-turbo> |
| `flux` | `black-forest-labs/flux-1.1-pro` | <https://openrouter.ai/models/black-forest-labs/flux-1.1-pro> |
| `flux-dev` | `black-forest-labs/flux-dev` | <https://openrouter.ai/models/black-forest-labs/flux-dev> |
| `playground-v25` | `playgroundai/playground-v2.5` | <https://openrouter.ai/models/playgroundai/playground-v2.5> |
| `sdxl-lightning` | `luma-photon/stable-diffusion-xl-lightning` | <https://openrouter.ai/models/luma-photon/stable-diffusion-xl-lightning> |

Puoi anche fornire un ID non presente nella tabella (ad esempio un modello privato) e verrà usato direttamente.

Il manifest `manifest.json` associa ad ogni immagine scena, pose, outfit, setup luci e prompt.

### 4. Controllo qualità
Confronta i render con il volto di riferimento e scarta immagini sfocate o non coerenti:
```bash
python3 scripts/qc_face_sim.py \
  --ref data/cleaned \
  --cand data/synth_openrouter \
  --out data/qc_passed \
  --minsim 0.34 \
  --minblur 80
```
Lo script salva un report CSV con similarità coseno e punteggio di nitidezza.

### 5. Augment e captioning
Amplia il dataset e crea caption descrittive pronte per l'addestramento:
```bash
python3 scripts/augment_and_caption.py \
  --in data/qc_passed \
  --out data/augment \
  --captions data/captions \
  --meta data/synth_openrouter/manifest.json \
  --num_aug 1
```
Ogni immagine originale viene duplicata con trasformazioni leggere (albumentations) e accompagnata dalla relativa caption `.txt`.

## Gestione dei checkpoint base
Copia uno o più checkpoint SDXL (o modelli compatibili) in `ai_influencer/models/base/` mantenendo l'estensione `.safetensors`:
```bash
cp ~/Downloads/sdxl_base_1.0.safetensors ai_influencer/models/base/sdxl.safetensors
cp ~/models/dreamshaperXL10.safetensors ai_influencer/models/base/dreamshaper_xl.safetensors
```
Lo script `train_lora.sh` utilizza per default `/workspace/models/base/sdxl.safetensors`, ma puoi sostituire il percorso con il flag `--base-model` oppure impostando la variabile d'ambiente `BASE_MODEL`.

### 6. Training LoRA
Dal container `kohya_local` avvia lo script di training scegliendo il modello base desiderato:
```bash
docker exec -it kohya_local bash -lc "bash /workspace/scripts/train_lora.sh --base-model /workspace/models/base/dreamshaper_xl.safetensors"
```
In alternativa esporta la variabile d'ambiente prima dell'esecuzione:
```bash
docker exec -it kohya_local bash -lc "BASE_MODEL=/workspace/models/base/dreamshaper_xl.safetensors bash /workspace/scripts/train_lora.sh"
```
Se non specifichi nulla verrà usato `/workspace/models/base/sdxl.safetensors`. Il comando richiama `accelerate` per eseguire `sd-scripts/train_network.py` con risoluzione 1024², salvando gli output in `models/lora/`.

> 💡 Smoke test rapido: esegui `bash /workspace/scripts/train_lora.sh --base-model /workspace/models/base/sdxl.safetensors` e verifica nei log la riga `[train_lora] Modello base selezionato: ...` per assicurarti che il parametro venga propagato correttamente.

## Control Hub web
Il servizio `ai_influencer_webapp` fornisce un **Control Hub API-first** su [http://localhost:8000](http://localhost:8000). Tutte le interazioni avvengono via endpoint REST; l'interfaccia HTML è stata rimossa a favore della documentazione interattiva generata automaticamente.

### Endpoint API
| Endpoint | Metodo | Payload richiesto | Campi principali della risposta |
| -------- | ------ | ----------------- | -------------------------------- |
| `/api/models` | GET | Nessun payload. | Oggetto con chiave `models`, lista di modelli con `id`, `name`, `provider`, `capabilities`, `context_length`, `pricing`, `pricing_display`. |
| `/api/generate/text` | POST | JSON `{ "model": string, "prompt": string }`. | Oggetto `{ "content": string }` con il testo generato. |
| `/api/generate/image` | POST | JSON `{ "model": string, "prompt": string, "negative_prompt"?: string, "width": int, "height": int, "steps"?: int, "guidance"?: float }`. | Oggetto `{ "image": string, "is_remote": bool }`, dove `image` è base64 o URL remoto. |
| `/api/generate/video` | POST | JSON `{ "model": string, "prompt": string, "duration"?: number, "size"?: string }`. | Oggetto `{ "video": string, "is_remote": bool }`, con base64 inline o URL streaming. |
| `/api/influencer` | POST | JSON `{ "identifier": string, "method"?: "official" \| "scrape" }`. | Oggetto con `profile`, `metrics`, `media`, `identifier`, `method`, `retrieved_at`. `media` contiene schede con `id`, `titolo`, `tipo`, `testo_post`, `image_url`, `image_base64`, `thumbnail_url`, `success_score`, `original_url`, `pubblicato_il`, `transcript`. |
| `/healthz` | GET | Nessun payload. | Oggetto `{ "status": "ok" }`. |

Per i dettagli completi consulta [docs/funzionalita.rm](docs/funzionalita.rm).

### Swagger / OpenAPI
- Avvia lo stack Docker (`docker compose -f ai_influencer/docker/docker-compose.yaml up -d`).
- Apri <http://localhost:8000/docs> per accedere alla pagina Swagger auto-generata da FastAPI.
- Da qui puoi testare ogni endpoint direttamente dal browser, consultare gli schemi dei payload e verificare le risposte attese.
- Per una descrizione testuale completa delle rotte REST (metodi, payload, codici di risposta ed esempi di integrazione) consulta [docs/funzionalita.rm](docs/funzionalita.rm).

### Esempi di richieste API
I seguenti esempi assumono che la variabile `OPENROUTER_API_KEY` sia configurata nel container `ai_influencer_webapp` (tramite `.env` o variabili d'ambiente Docker).

- **Elenco modelli disponibili (GET `/api/models`)**
  ```bash
  curl http://localhost:8000/api/models | jq '.[0]'
  ```
  La risposta contiene metadati sui modelli OpenRouter (nome, tipo di media supportato, provider).

- **Generazione di testo (POST `/api/generate/text`)**
  ```bash
  curl -X POST http://localhost:8000/api/generate/text \
    -H 'Content-Type: application/json' \
    -d '{
      "model": "meta-llama/llama-3.1-70b-instruct",
      "prompt": "Scrivi una caption Instagram per il lancio di un nuovo prodotto skincare."
    }'
  ```
  L'API risponde con il testo generato dal modello selezionato (campo `content`).

- **Generazione di immagini (POST `/api/generate/image`)**
  ```bash
  curl -X POST http://localhost:8000/api/generate/image \
    -H 'Content-Type: application/json' \
    -d '{
      "model": "stabilityai/sdxl",
      "prompt": "ritratto fotografico di un influencer immerso nella luce dorata del tramonto",
      "negative_prompt": "sfocato, distorsioni",
      "width": 1024,
      "height": 1024
    }'
  ```
  L'output include i dati dell'immagine codificati in Base64 e gli eventuali URL remoti.

- **Insight su un profilo (POST `/api/influencer`)**
  ```bash
  curl -X POST http://localhost:8000/api/influencer \
    -H 'Content-Type: application/json' \
    -d '{
      "identifier": "@influencer_demo",
      "method": "official"
    }'
  ```
  La risposta restituisce un payload JSON con profilo, metriche e top media simulati.

FastAPI (`ai_influencer/webapp/main.py`) utilizza `ai_influencer/webapp/openrouter.py` come client asincrono con caching dei modelli e gestione errori per orchestrare le chiamate verso OpenRouter.

## Struttura delle cartelle dati
```
ai_influencer/
├── data/
│   ├── input_raw/        # immagini sorgente
│   ├── cleaned/          # output di prepare_dataset.py
│   ├── synth_openrouter/ # batch generati (più manifest.json)
│   ├── qc_passed/        # render validati dal QC
│   ├── augment/          # dataset finale per il training
│   └── captions/         # caption .txt allineate alle immagini
├── models/
│   ├── base/             # modelli base SDXL (più checkpoint .safetensors)
│   └── lora/             # checkpoint LoRA addestrati
└── workflows/
    └── comfyui/          # workflow personalizzati ComfyUI
```

- **GUI desktop** (`scripts/gui_app.py`): fornisce una finestra Tkinter con wizard per API key, preparazione dataset, generazione testo/immagini, QC e augment. Ogni pulsante invoca gli script CLI corrispondenti mostrando i log in tempo reale.
- **Workflow n8n** (`n8n/flow.json` + servizio `n8n_local`): espone il webhook `/webhook/ai-influencer-hybrid` e, tramite `docker exec`, orchestra gli script nei container `ai_influencer_tools` e `kohya_local` (con supporto al parametro JSON `base_model`).
- **Script PowerShell** (`scripts/start_machine.ps1`, `scripts/stop_machine.ps1`): facilitano l'avvio/arresto dei container su Windows.

## Troubleshooting rapido
- **GPU non rilevata dai container** – verifica che `nvidia-smi` funzioni sull'host e riavvia Docker Desktop; assicurati che `docker compose` sia lanciato con supporto GPU (`--profile gpu` non è necessario perché il compose file utilizza l'estensione NVIDIA automaticamente).
- **Errori 401/403 dalle API OpenRouter** – controlla che `OPENROUTER_API_KEY` sia presente nel container `ai_influencer_tools`/`webapp` (`docker compose exec <service> printenv | grep OPENROUTER`). Rigenera la chiave dal dashboard se è stata ruotata.
- **Download modelli SDXL bloccato** – esporta `HF_TOKEN` con permessi di lettura per il repo richiesto oppure scarica manualmente il file `.safetensors` e copialo in `ai_influencer/models/base/`.
- **Timeout nelle chiamate alle API** – imposta `OPENROUTER_BASE_URL` su un mirror locale o riduci il parametro `--sleep` negli script batch per diluire le richieste.

## Test e sviluppo
- Installa le dipendenze di sviluppo:
  ```bash
  pip install -r requirements-dev.txt
  ```
- Esegui la suite:
  ```bash
  pytest
  ```
  I test validano il client OpenRouter (cache, gestione errori, payload chunked) e l'endpoint `/api/influencer` della webapp.

Per modifiche al Control Hub puoi utilizzare l'ambiente Docker `webapp` oppure avviare FastAPI in locale:
```bash
uvicorn ai_influencer.webapp.main:app --reload
```
Assicurati di esportare `OPENROUTER_API_KEY` e, se necessario, `OPENROUTER_APP_TITLE`/`OPENROUTER_APP_URL` per personalizzare gli header verso OpenRouter.

## Documentazione aggiuntiva e licenza
- `ai_influencer/README.md` – manuale operativo dettagliato della pipeline.
- Cartella root – include guide PDF/Docx per ambienti Windows/WSL e configurazioni Docker.
- `ai_influencer/CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` – linee guida comunitarie.
- Licenza: vedere `ai_influencer/LICENSE`.
