# Influencer AI – Pipeline ibrida OpenRouter + Stable Diffusion

> Toolkit completo per generare, ripulire e addestrare influencer virtuali combinando servizi cloud (OpenRouter) e strumenti locali GPU-ready.

## Indice
- [Panoramica](#panoramica)
- [Architettura del repository](#architettura-del-repository)
- [Prerequisiti](#prerequisiti)
- [Setup rapido](#setup-rapido)
- [Esecuzione della pipeline](#esecuzione-della-pipeline)
  - [1. Preparazione del dataset](#1-preparazione-del-dataset)
  - [2. Storyboard e copy con OpenRouter](#2-storyboard-e-copy-con-openrouter)
  - [3. Generazione batch di immagini](#3-generazione-batch-di-immagini)
  - [4. Controllo qualità](#4-controllo-qualità)
  - [5. Augment e captioning](#5-augment-e-captioning)
  - [6. Training LoRA](#6-training-lora)
- [Control Hub web](#control-hub-web)
- [Struttura delle cartelle dati](#struttura-delle-cartelle-dati)
- [Interfacce alternative](#interfacce-alternative)
- [Test e sviluppo](#test-e-sviluppo)
- [Documentazione aggiuntiva e licenza](#documentazione-aggiuntiva-e-licenza)

## Panoramica
Il progetto **Influencer AI** fornisce un flusso end-to-end per costruire una persona virtuale partendo da un piccolo set di immagini reali, espandere il dataset con generazioni guidate da prompt, verificarne la qualità e addestrare un LoRA fotorealistico su Stable Diffusion XL. Il repository include:

- stack Docker ottimizzato per GPU NVIDIA con servizi "tools" (Python utility), "comfyui" e "kohya" per l'addestramento;
- script Python per la preparazione del dataset, la generazione tramite OpenRouter e la creazione di caption augmentate;
- una webapp FastAPI per consultare i modelli OpenRouter, lanciare generazioni testo/immagine/video e simulare l'analisi dei profili social;
- automazioni opzionali (GUI desktop e workflow n8n) per orchestrare l'intero ciclo.

## Architettura del repository
- `ai_influencer/docker/docker-compose.yaml` – definisce i container `tools`, `comfyui`, `kohya` e `webapp` con runtime NVIDIA, montando dati, script e modelli sul file system condiviso.
- `ai_influencer/scripts/` – raccolta di utility CLI, fra cui:
  - `prepare_dataset.py` per remove.bg, face crop e normalizzazione immagini;
  - `openrouter_text.py`, `openrouter_images.py` e `openrouter_batch.py` per interrogare le API OpenRouter;
  - `qc_face_sim.py` per filtrare il dataset tramite similarità facciale e nitidezza;
  - `augment_and_caption.py` per augment e generazione caption coerenti con i metadati;
  - `train_lora.sh` per avviare `sd-scripts` all'interno del container `kohya`.
- `ai_influencer/webapp/` – applicazione FastAPI + frontend vanilla JS che espone endpoint `/api/models`, `/api/generate/*` e `/api/influencer` per pilotare i servizi OpenRouter e raccogliere insight.
- `ai_influencer/scripts/gui_app.py` – interfaccia Tkinter che incapsula i principali step della pipeline CLI.
- `ai_influencer/n8n/flow.json` – workflow n8n che esegue gli script chiave via webhook Docker.
- `tests/` – suite Pytest che copre l'SDK OpenRouter asincrono e gli endpoint principali della webapp.

## Prerequisiti
- **Hardware**: GPU NVIDIA compatibile con CUDA, preferibilmente >= 12 GB VRAM.
- **Software**: Docker Desktop (o Docker Engine) con supporto GPU attivo, Docker Compose v2, Git.
- **Account/Asset**:
  - chiave API OpenRouter (`OPENROUTER_API_KEY`), opzionalmente endpoint personalizzato (`OPENROUTER_BASE_URL`);
  - modello base Stable Diffusion XL copiato in `ai_influencer/models/base/sdxl.safetensors`.
- **Storage**: almeno 40 GB liberi per dataset, modelli e checkpoint LoRA.

## Setup rapido
1. Clona il repository e posizionati nella root del progetto:
   ```bash
   git clone https://github.com/<org>/InfluencerAi.git
   cd InfluencerAi
   ```
2. Copia il modello SDXL base in `ai_influencer/models/base/sdxl.safetensors`.
3. Esporta la chiave OpenRouter nel terminale corrente (o aggiungila a un file `.env` richiamato da Docker Compose):
   ```bash
   export OPENROUTER_API_KEY="sk-or-..."
   ```
4. Avvia lo stack GPU:
   ```bash
   docker compose -f ai_influencer/docker/docker-compose.yaml up -d
   ```
   I container principali saranno:
   - `ai_influencer_tools` (utility Python + CLI pipeline)
   - `comfyui_local` (interfaccia ComfyUI su http://localhost:8188)
   - `kohya_local` (ambiente kohya_ss per LoRA)
   - `ai_influencer_webapp` (Control Hub su http://localhost:8000)

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
  --model stabilityai/sdxl \
  --out data/synth_openrouter \
  --per_scene 12 \
  --size 1024x1024
```
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

### 6. Training LoRA
Dal container `kohya_local` avvia lo script di training:
```bash
docker exec -it kohya_local bash -lc "bash /workspace/scripts/train_lora.sh"
```
Il comando richiama `accelerate` per eseguire `sd-scripts/train_network.py` con risoluzione 1024², salvando gli output in `models/lora/`.

## Control Hub web
Il servizio `ai_influencer_webapp` espone un pannello su [http://localhost:8000](http://localhost:8000) per:
- consultare i modelli OpenRouter filtrabili per capacità (testo/immagine/video);
- inviare prompt testuali, visualizzare immagini inline (base64) o scaricare asset remoti;
- lanciare generazioni video e ottenere URL/base64 pronti all'uso;
- simulare la raccolta di insight su un influencer (profilo, metriche, top media) attraverso l'endpoint `/api/influencer`.

La webapp è implementata con FastAPI (`ai_influencer/webapp/main.py`) e utilizza `ai_influencer/webapp/openrouter.py` come client asincrono con caching dei modelli e gestione errori.

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
│   ├── base/             # modello SDXL di partenza
│   └── lora/             # checkpoint LoRA addestrati
└── workflows/
    └── comfyui/          # workflow personalizzati ComfyUI
```

## Interfacce alternative
- **GUI desktop** (`scripts/gui_app.py`): fornisce una finestra Tkinter con wizard per API key, preparazione dataset, generazione testo/immagini, QC e augment. Ogni pulsante invoca gli script CLI corrispondenti mostrando i log in tempo reale.
- **Workflow n8n** (`n8n/flow.json`): definisce un webhook che esegue sequenzialmente `prepare_dataset.py`, `openrouter_batch.py` e step collegati all'interno del container Docker, utile per automazioni server-side.
- **Script PowerShell** (`scripts/start_machine.ps1`, `scripts/stop_machine.ps1`): facilitano l'avvio/arresto dei container su Windows.

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
