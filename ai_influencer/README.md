# AI Influencer — Hybrid Pro (OpenRouter + Locale)

Pipeline per generare un dataset (da 2 foto iniziali a ~100+ immagini), verificare qualità, fare augment e addestrare un LoRA SDXL.

## Requisiti
- Windows + Docker Desktop + GPU NVIDIA (es. RTX 4070)
- Account OpenRouter (LLM + Images) — [Unverified] controlla limiti/licenza correnti.
- Modello SDXL base (metti il file in `models/base/sdxl.safetensors`).

## Setup rapido
1. Copia le tue 2 immagini in `data/input_raw/`.
2. Avvia i container:
   ```bash
   docker compose -f docker/docker-compose.yaml up -d
   ```
   Su Windows puoi usare anche lo script PowerShell incluso:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\start_machine.ps1
   ```
3. (Opzionale) Avvia l'interfaccia grafica locale:
   ```bash
   python3 scripts/gui_app.py
   ```
   L'app raccoglie i percorsi e lancia gli script sottostanti passo dopo passo (dataset, OpenRouter testi/immagini, QC, augment). In alternativa, continua con i comandi manuali sotto.

4. (Nuovo) Avvia il pannello web centralizzato per orchestrare testo/immagini/video tramite OpenRouter:
   ```bash
   docker compose -f docker/docker-compose.yaml up -d webapp
   ```
   L'interfaccia sar&agrave; raggiungibile su [http://localhost:8000](http://localhost:8000) e consente di:
   - Consultare i modelli disponibili su OpenRouter filtrando per capacit&agrave; (testo, immagini, video).
   - Lanciare generazioni testuali, grafiche o video scegliendo il modello e inserendo il prompt.
   - Copiare rapidamente gli identificativi modello nei form dedicati.

   Ricorda di esportare `OPENROUTER_API_KEY` nel tuo ambiente (o file `.env`) prima di avviare il servizio.

5. Esegui la suite di test automatizzati prima di sviluppare nuove funzionalità (approccio TDD/CI):
   ```bash
   pip install -r ../requirements-dev.txt
   pytest
   python -m compileall webapp
   ```
   I test convalidano il client OpenRouter asincrono e le utility di supporto; mantieni la suite verde aggiungendo casi per ogni nuovo comportamento introdotto. Lo stesso set di comandi viene eseguito automaticamente dalla pipeline CI su GitHub Actions.

6. Entra nel container `tools` e lancia pulizia:
   ```bash
   docker exec -it ai_influencer_tools bash
   python3 scripts/prepare_dataset.py --in data/input_raw --out data/cleaned --do_rembg --do_facecrop
   ```
7. Generazione testi creativi (storyboard/script/caption seed) con OpenRouter LLM:
   ```bash
   export OPENROUTER_API_KEY=YOUR_KEY
   python3 scripts/openrouter_text.py --prompt_bank scripts/prompt_bank.yaml --out data/text/storyboard.json
   ```
8. Genera immagini con l'API Images di OpenRouter (scegli il modello, es. `stabilityai/sdxl` o `black-forest-labs/flux`):
   ```bash
   python3 scripts/openrouter_images.py --prompt_bank scripts/prompt_bank.yaml --out data/synth_openrouter --model stabilityai/sdxl
   ```
9. Controllo qualità:
   ```bash
   python3 scripts/qc_face_sim.py --ref data/cleaned --cand data/synth_openrouter --out data/qc_passed --minsim 0.34
   ```
10. Augment + caption:
   ```bash
   python3 scripts/augment_and_caption.py --in data/qc_passed --out data/augment --captions data/captions --num_aug 1 --meta data/synth_openrouter/manifest.json
   ```
11. Addestra LoRA (metti SDXL in `models/base/`):
   ```bash
   docker exec -it kohya bash -lc "bash /workspace/scripts/train_lora.sh"
   ```

### Script PowerShell per Windows
- `scripts/start_machine.ps1` avvia i container Docker Compose preconfigurati. Puoi forzare la ricreazione dei container con il flag `-Recreate` oppure indicare un file alternativo con `-ComposeFile "percorso\al\docker-compose.yaml"`.
- `scripts/stop_machine.ps1` arresta e pulisce i container (usa `-RemoveVolumes` per eliminare anche i volumi associati).

Esempio di arresto completo:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_machine.ps1 -RemoveVolumes
```

## Note
- `openrouter_text.py` e `openrouter_images.py` sono scheletri: aggiorna modello/parametri secondo la documentazione ufficiale OpenRouter.
- La soglia `--minsim` va calibrata osservando i falsi positivi/negativi.
- Mantieni 2–3 preset luce/scene come “firma” del brand per la coerenza.
