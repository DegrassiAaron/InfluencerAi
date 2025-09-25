# Influencer AI — Panoramica del progetto

Questo repository raccoglie il materiale per costruire un flusso di lavoro "ibrido" che combina servizi cloud (Leonardo.ai) e strumenti locali basati su Stable Diffusion XL per creare e addestrare influencer virtuali. Il progetto mette a disposizione container Docker ottimizzati per GPU NVIDIA, script Python per la preparazione del dataset e dell'addestramento LoRA, oltre a documentazione di supporto.

## Contenuto principale

- `ai_influencer/` – Codice della pipeline **AI Influencer — Hybrid Pro** con script, configurazioni Docker e documentazione di progetto.
  - `docker/` – Dockerfile e `docker-compose.yaml` per avviare i container `tools`, `comfyui` e `kohya` con supporto CUDA.
  - `scripts/` – Script Python per pulizia immagini, generazione batch con Leonardo.ai, controllo qualità, augmenting/captioning e train LoRA.
  - `README.md` – Istruzioni operative dettagliate (in italiano) per eseguire la pipeline completa.
- Documentazione aggiuntiva (`.pdf`, `.docx`) con guide passo-passo per l'installazione in ambienti Windows/WSL, configurazione Docker e best practice operative.

## Requisiti

- Docker Desktop (o Docker Engine) con supporto GPU NVIDIA abilitato.
- Account Leonardo.ai e relativa API key per la generazione remota delle immagini.
- Modello **Stable Diffusion XL** base posizionato in `ai_influencer/models/base/sdxl.safetensors`.
- Python 3.10+ all'interno del container `tools` (installato automaticamente via `pip` all'avvio grazie a `scripts/requirements.txt`).

## Avvio rapido

1. Copia due immagini di riferimento del tuo personaggio in `ai_influencer/data/input_raw/`.
2. Avvia l'infrastruttura locale:
   ```bash
   cd ai_influencer
   docker compose -f docker/docker-compose.yaml up -d
   ```
3. Entra nel container `ai_influencer_tools` per preparare il dataset:
   ```bash
   docker exec -it ai_influencer_tools bash
   python3 scripts/prepare_dataset.py --in data/input_raw --out data/cleaned --do_rembg --do_facecrop
   ```
4. Esporta la variabile `LEONARDO_API_KEY` e lancia la generazione remota tramite `scripts/leonardo_batch.py`.
5. Esegui controllo qualità e augment/caption con gli script dedicati.
6. Avvia l'addestramento LoRA nel container `kohya`:
   ```bash
   docker exec -it kohya bash -lc "bash /workspace/scripts/train_lora.sh"
   ```

Per dettagli, parametri e suggerimenti operativi consulta `ai_influencer/README.md` e le guide in PDF.

## Struttura dati consigliata

```
ai_influencer/
├── data/
│   ├── input_raw/          # immagini di partenza
│   ├── cleaned/            # dataset pulito
│   ├── synth_leonardo/     # batch generati da Leonardo.ai
│   ├── qc_passed/          # immagini che superano il controllo qualità
│   └── augment/            # dataset finale per il training
├── models/
│   └── base/sdxl.safetensors
└── workflows/
    └── comfyui/            # workflow personalizzati per ComfyUI
```

## Contribuire

Le linee guida per contribuire, il codice di condotta e le policy di sicurezza sono disponibili all'interno di `ai_influencer/CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` e `SECURITY.md`.

## Licenza

Il progetto è distribuito secondo i termini della licenza riportata in `ai_influencer/LICENSE`.
