#!/usr/bin/env bash
set -euo pipefail

BASE_MODEL_DEFAULT="/workspace/models/base/sdxl.safetensors"
SELECTED_BASE_MODEL="${BASE_MODEL:-$BASE_MODEL_DEFAULT}"
TRAIN_DIR="/workspace/data/augment"
OUT_DIR="/workspace/models/lora"
OUT_NAME="influencer_lora"

EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-model)
      if [[ $# -lt 2 ]]; then
        echo "Errore: --base-model richiede un argomento" >&2
        exit 1
      fi
      SELECTED_BASE_MODEL="$2"
      shift 2
      ;;
    --base-model=*)
      SELECTED_BASE_MODEL="${1#*=}"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Utilizzo: train_lora.sh [--base-model <percorso_modello>] [argomenti aggiuntivi]

  --base-model PATH   Percorso del checkpoint base da usare.
                      Di default: /workspace/models/base/sdxl.safetensors

È inoltre possibile impostare la variabile d'ambiente BASE_MODEL.
Tutti gli argomenti non riconosciuti vengono inoltrati a train_network.py.
EOF
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${SELECTED_BASE_MODEL}" ]]; then
  echo "Errore: nessun modello base specificato." >&2
  exit 1
fi

echo "[train_lora] Modello base selezionato: ${SELECTED_BASE_MODEL}"

# ⬇️ usa lo script di sd-scripts
accelerate launch \
  /opt/kohya_ss/sd-scripts/train_network.py \
  --pretrained_model_name_or_path "${SELECTED_BASE_MODEL}" \
  --train_data_dir "${TRAIN_DIR}" \
  --output_dir "${OUT_DIR}" \
  --output_name "${OUT_NAME}" \
  --resolution="1024,1024" \
  --network_module "networks.lora" \
  --network_dim 32 --network_alpha 16 \
  --learning_rate 1e-4 --text_encoder_lr 5e-5 --unet_lr 1e-4 \
  --lr_scheduler "cosine" --train_batch_size 2 \
  --max_train_steps 4000 \
  --mixed_precision "fp16" \
  --save_every_n_steps 1000 \
  "${EXTRA_ARGS[@]}"
