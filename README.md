# Influencer AI — Panoramica del progetto

Questo repository raccoglie il materiale per costruire un flusso di lavoro "ibrido" che combina servizi cloud (OpenRouter) e strumenti locali basati su Stable Diffusion XL per creare e addestrare influencer virtuali. Il progetto mette a disposizione container Docker ottimizzati per GPU NVIDIA, script Python per la preparazione del dataset e dell'addestramento LoRA, oltre a documentazione di supporto.

## Contenuto principale

- `ai_influencer/` – Codice della pipeline **AI Influencer — Hybrid Pro** con script, configurazioni Docker e documentazione di progetto.
  - `docker/` – Dockerfile e `docker-compose.yaml` per avviare i container `tools`, `comfyui` e `kohya` con supporto CUDA.
  - `scripts/` – Script Python per pulizia immagini, generazione batch tramite OpenRouter (`openrouter_images.py`, `openrouter_text.py`), controllo qualità, augmenting/captioning e train LoRA.
  - `README.md` – Istruzioni operative dettagliate (in italiano) per eseguire la pipeline completa.
- Documentazione aggiuntiva (`.pdf`, `.docx`) con guide passo-passo per l'installazione in ambienti Windows/WSL, configurazione Docker e best practice operative.

## Requisiti

- Docker Desktop (o Docker Engine) con supporto GPU NVIDIA abilitato.
- Account OpenRouter e relativa API key (`OPENROUTER_API_KEY`) per le generazioni testuali e grafiche.
- Modello **Stable Diffusion XL** base posizionato in `ai_influencer/models/base/sdxl.safetensors`.
- Python 3.10+ all'interno del container `tools` (installato automaticamente via `pip` all'avvio grazie a `scripts/requirements.txt`).

## Avvio rapido

1. Avvia Docker Desktop/Engine e assicurati che il modello base **Stable Diffusion XL** sia presente in `ai_influencer/models/base/sdxl.safetensors`.
2. Popola il dataset iniziale copiando almeno due immagini di riferimento del tuo personaggio in `ai_influencer/data/input_raw/`.
3. Avvia il servizio web Lovable, che funge da interfaccia per orchestrare le generazioni di prompt e immagini (richiede `OPENROUTER_API_KEY`):
   ```bash
   docker compose -f ai_influencer/docker/docker-compose.yaml up -d webapp
   # in alternativa usa "up -d" senza servizio per alzare l'intero stack (webapp, tools, comfyui, kohya)
   ```
   Raggiungi il pannello su `http://localhost:8000` per configurare i job e verificare lo stato dei container.
4. Esporta `OPENROUTER_API_KEY` (necessaria sia per Lovable sia per gli script CLI) ed esegui dal container `ai_influencer_tools` la preparazione del dataset:
   ```bash
   docker exec -it ai_influencer_tools bash
   export OPENROUTER_API_KEY=...  # disponibile anche via docker compose env
   python3 scripts/prepare_dataset.py --in data/input_raw --out data/cleaned --do_rembg --do_facecrop
   ```
5. Dal medesimo container lancia gli script di generazione batch (`scripts/openrouter_images.py`, `scripts/openrouter_text.py`) seguendo i workflow impostati via Lovable.
6. Completa il controllo qualità, augment/caption e avvia l'addestramento LoRA nel container `kohya`:
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
│   ├── synth_openrouter/   # batch generati da OpenRouter
│   ├── qc_passed/          # immagini che superano il controllo qualità
│   └── augment/            # dataset finale per il training
├── models/
│   └── base/sdxl.safetensors
└── workflows/
    └── comfyui/            # workflow personalizzati per ComfyUI
```

## Contribuire

Le linee guida per contribuire, il codice di condotta e le policy di sicurezza sono disponibili all'interno di `ai_influencer/CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` e `SECURITY.md`.

## CI/CD

Il repository include una pipeline GitHub Actions (`.github/workflows/ci.yml`) che esegue automaticamente i test Pytest e la compilazione dei moduli web ad ogni push o pull request. Per replicare lo stesso flusso in locale:

```bash
pip install -r requirements-dev.txt
pytest
python -m compileall ai_influencer/webapp
```

Mantieni la pipeline verde aggiungendo nuovi test ogni volta che introduci funzionalità o correzioni.

## Licenza

Il progetto è distribuito secondo i termini della licenza riportata in `ai_influencer/LICENSE`.
