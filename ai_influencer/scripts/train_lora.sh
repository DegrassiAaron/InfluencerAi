#!/usr/bin/env bash
set -euo pipefail

BASE_MODEL="/workspace/models/base/sdxl.safetensors"
TRAIN_DIR="/workspace/data/augment"
OUT_DIR="/workspace/models/lora"
OUT_NAME="influencer_lora"

# ⬇️ usa lo script di sd-scripts
accelerate launch \
  /opt/kohya_ss/sd-scripts/train_network.py \
  --pretrained_model_name_or_path "${BASE_MODEL}" \
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
  --save_every_n_steps 1000
