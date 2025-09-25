# AI Influencer — Hybrid Pro (Leonardo.ai + Locale)

Pipeline per generare un dataset (da 2 foto iniziali a ~100+ immagini), verificare qualità, fare augment e addestrare un LoRA SDXL.

## Requisiti
- Windows + Docker Desktop + GPU NVIDIA (es. RTX 4070)
- Account Leonardo.ai (per generazione remota) — [Unverified] verifica termini/licenza correnti.
- Modello SDXL base (metti il file in `models/base/sdxl.safetensors`).

## Setup rapido
1. Copia le tue 2 immagini in `data/input_raw/`.
2. Avvia i container:
   ```bash
   docker compose -f docker/docker-compose.yaml up -d
   ```
3. Entra nel container `tools` e lancia pulizia:
   ```bash
   docker exec -it ai_influencer_tools bash
   python3 scripts/prepare_dataset.py --in data/input_raw --out data/cleaned --do_rembg --do_facecrop
   ```
4. Leonardo batch (aggiorna endpoint/parametri nello script se servono) e esporta la chiave:
   ```bash
   export LEONARDO_API_KEY=YOUR_KEY
   python3 scripts/leonardo_batch.py --prompt_bank scripts/prompt_bank.yaml --out data/synth_leonardo
   ```
5. Controllo qualità:
   ```bash
   python3 scripts/qc_face_sim.py --ref data/cleaned --cand data/synth_leonardo --out data/qc_passed --minsim 0.34
   ```
6. Augment + caption:
   ```bash
   python3 scripts/augment_and_caption.py --in data/qc_passed --out data/augment --captions data/captions --num_aug 1 --meta data/synth_leonardo/manifest.json
   ```
7. Addestra LoRA (metti SDXL in `models/base/`):
   ```bash
   docker exec -it kohya bash -lc "bash /workspace/scripts/train_lora.sh"
   ```

## Note
- `leonardo_batch.py` è uno scheletro: aggiorna endpoint/parametri secondo la documentazione ufficiale Leonardo.ai.
- La soglia `--minsim` va calibrata osservando i falsi positivi/negativi.
- Mantieni 2–3 preset luce/scene come “firma” del brand per la coerenza.
