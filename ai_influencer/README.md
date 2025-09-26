# AI Influencer — Manuale operativo della pipeline ibrida

Questo documento accompagna la cartella `ai_influencer/` e descrive nel dettaglio come eseguire ogni fase del flusso di lavoro: dalla preparazione del dataset alla generazione tramite OpenRouter, fino all'addestramento di un LoRA SDXL.

## Indice
- [Componenti principali](#componenti-principali)
- [Prerequisiti](#prerequisiti)
- [Preparazione dell'ambiente](#preparazione-dellambiente)
- [Workflow passo-passo](#workflow-passo-passo)
  - [1. Normalizzazione delle immagini di partenza](#1-normalizzazione-delle-immagini-di-partenza)
  - [2. Pianificazione creativa (testo)](#2-pianificazione-creativa-testo)
  - [3. Generazione immagini con OpenRouter](#3-generazione-immagini-con-openrouter)
  - [4. Controllo qualità del dataset](#4-controllo-qualità-del-dataset)
  - [5. Augment + captioning](#5-augment--captioning)
  - [6. Addestramento LoRA SDXL](#6-addestramento-lora-sdxl)
- [Control Hub web](#control-hub-web)
- [GUI desktop](#gui-desktop)
- [Automazione via n8n](#automazione-via-n8n)
- [Suggerimenti e note operative](#suggerimenti-e-note-operative)

## Componenti principali
- **Docker Compose** (`docker/docker-compose.yaml`): definisce i container GPU `tools`, `comfyui`, `kohya` e `webapp`, condividendo le cartelle `data/`, `models/` e `scripts/`.
- **Script CLI** (`scripts/`): contengono gli step atomici della pipeline (preparazione dataset, generazione OpenRouter, QC, augment, training) e gli script PowerShell per Windows.
- **Prompt bank** (`scripts/prompt_bank.yaml`): archivio di persona, scene, luci, pose e outfit utilizzato dagli script OpenRouter per costruire prompt coerenti.
- **Control Hub web** (`webapp/`): FastAPI + frontend statico per esplorare modelli, lanciare generazioni e simulare analisi profili.
- **Workflow n8n** (`n8n/flow.json`): esegue gli script principali tramite webhook per scenari automatizzati.

## Prerequisiti
- GPU NVIDIA con driver recenti e supporto CUDA (12.x consigliato).
- Docker Desktop/Engine con estensione NVIDIA attiva.
- Chiave API OpenRouter (`OPENROUTER_API_KEY`). Facoltativi `OPENROUTER_BASE_URL`, `OPENROUTER_APP_TITLE`, `OPENROUTER_APP_URL`.
- File modello `models/base/sdxl.safetensors` già presente.
- Almeno 2 immagini reference posizionate in `data/input_raw/`.

## Preparazione dell'ambiente
1. Avvia Docker Desktop e assicurati che la GPU sia visibile (`docker info | grep -i nvidia`).
2. Esporta la chiave API nel terminale che userà Docker Compose:
   ```bash
   export OPENROUTER_API_KEY="sk-or-..."
   ```
3. Avvia i container:
   ```bash
   docker compose -f docker/docker-compose.yaml up -d
   ```
   In alternativa su Windows:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\start_machine.ps1
   ```
4. Verifica lo stato dei container (`docker ps`) e apri una shell nel servizio `ai_influencer_tools` per gli step CLI:
   ```bash
   docker exec -it ai_influencer_tools bash
   ```

## Workflow passo-passo
Le cartelle indicate sono relative alla root `ai_influencer/`. Ogni comando seguente va eseguito all'interno del container `ai_influencer_tools` salvo dove indicato diversamente.

### 1. Normalizzazione delle immagini di partenza
```bash
python3 scripts/prepare_dataset.py \
  --in data/input_raw \
  --out data/cleaned \
  --do_rembg \
  --do_facecrop
```
- **remove.bg locale** (`rembg[gpu]`) elimina lo sfondo.
- **Face crop** (InsightFace `buffalo_l`) centra e ritaglia il soggetto.
- Output: immagini normalizzate in `data/cleaned/`.

### 2. Pianificazione creativa (testo)
```bash
python3 scripts/openrouter_text.py \
  --prompt_bank scripts/prompt_bank.yaml \
  --model meta-llama/llama-3.1-70b-instruct \
  --out data/text/storyboard.json
```
- Costruisce un prompt in base a persona, scene e controlli creativi definiti nel YAML.
- Chiama l'endpoint `/chat/completions` di OpenRouter tramite `httpx`.
- Output: JSON con storyboard, script parlato e almeno 5 caption seed.

### 3. Generazione immagini con OpenRouter
Due opzioni:
- **Granularità completa (`openrouter_images.py`)** – gestisce pausa tra richieste, negative prompt e manifest JSON:
  ```bash
  python3 scripts/openrouter_images.py \
    --prompt_bank scripts/prompt_bank.yaml \
    --model stabilityai/sdxl \
    --out data/synth_openrouter \
    --per_scene 12 \
    --size 1024x1024 \
    --sleep 3
  ```
- **Versione compatta (`openrouter_batch.py`)** – usa lo stesso YAML ma espone meno flag; utile nelle automazioni n8n.

Ogni immagine viene salvata come PNG con nome hash e metadati registrati in `manifest.json`.

### 4. Controllo qualità del dataset
```bash
python3 scripts/qc_face_sim.py \
  --ref data/cleaned \
  --cand data/synth_openrouter \
  --out data/qc_passed \
  --minsim 0.34 \
  --minblur 80
```
- Calcola embedding facciali via InsightFace e confronta con il centroid dei riferimenti.
- Misura la nitidezza (varianza Laplaciana) e applica soglie personalizzabili (`--minsim`, `--minblur`).
- Output: immagini approvate in `data/qc_passed/` + `qc_report.csv` con coseno/nitidezza.

### 5. Augment + captioning
```bash
python3 scripts/augment_and_caption.py \
  --in data/qc_passed \
  --out data/augment \
  --captions data/captions \
  --meta data/synth_openrouter/manifest.json \
  --num_aug 1
```
- Applica trasformazioni leggere (crop random, flip, regolazioni luce, rumore) tramite Albumentations.
- Mantiene l'originale e genera versioni `*_augX.jpg` a 95% qualità JPEG.
- Produce caption descrittive utilizzando scena/luce/outfit dal manifest (fallback su valori predefiniti).

### 6. Addestramento LoRA SDXL
Dal container `kohya_local`:
```bash
docker exec -it kohya_local bash -lc "bash /workspace/scripts/train_lora.sh"
```
- Lancia `accelerate` con `sd-scripts/train_network.py` (dim 32, alpha 16, risoluzione 1024).
- `TRAIN_DIR=/workspace/data/augment` e `OUT_DIR=/workspace/models/lora` configurati nello script.
- Il checkpoint LoRA viene salvato come `models/lora/influencer_lora.safetensors`.

## Control Hub web
Il servizio FastAPI (`webapp/main.py`) gira nel container `ai_influencer_webapp` e offre:
- elenco modelli `/api/models` con caching TTL (gestito da `webapp/openrouter.py`);
- endpoint `/api/generate/text|image|video` con gestione errori e risposta standardizzata (immagini inline base64 oppure URL);
- pagina `/influencer` che chiama `/api/influencer` per simulare insight su profili social, con metriche ordinate per `success_score`.

Per sviluppo locale:
```bash
uvicorn ai_influencer.webapp.main:app --reload --port 8000
```
Assicurati di esportare `OPENROUTER_API_KEY` e personalizza `OPENROUTER_APP_TITLE` per gli header consigliati da OpenRouter.

## GUI desktop
`scripts/gui_app.py` fornisce un'interfaccia Tkinter con:
- sezioni configurabili per cartelle input/output, API key, modelli testo/immagine, soglie QC;
- bottoni che invocano gli script CLI e mostrano i log in streaming (via `subprocess.Popen` + coda thread-safe);
- pulsante "Interrompi" per terminare il processo corrente e pulsante "Pulisci log".

Avvio (dal container `tools` o da un ambiente con Tk installato):
```bash
python3 scripts/gui_app.py
```

## Automazione via n8n
`n8n/flow.json` definisce un webhook (`/ai-influencer-hybrid`) che:
1. Riceve la richiesta HTTP.
2. Esegue `python3 scripts/prepare_dataset.py ...` nel container tramite nodo `executeCommand`.
3. Avvia `python3 scripts/openrouter_batch.py ...` per popolare `data/synth_openrouter`.
4. (Ulteriori nodi possono essere collegati per QC/augment).

Importa il file in n8n, aggiorna percorsi/comandi in base alla tua infrastruttura Docker e proteggi il webhook con credenziali.

## Suggerimenti e note operative
- Mantieni il modello SDXL base fuori dal versionamento Git per motivi di licenza.
- Calibra `--minsim` in `qc_face_sim.py` osservando falsi positivi/negativi per il tuo soggetto.
- Per prompt personalizzati aggiorna `scripts/prompt_bank.yaml` aggiungendo nuove scene/pose senza modificare l'indentazione YAML.
- Gli script PowerShell supportano `-Recreate` (start) e `-RemoveVolumes` (stop) per gestire rebuild e cleanup completi.
- I requisiti Python degli script CLI sono definiti in `scripts/requirements.txt` (OpenCV, rembg GPU, InsightFace, Albumentations).
