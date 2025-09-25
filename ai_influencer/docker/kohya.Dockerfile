# docker/kohya.Dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    git python3 python3-pip python3-venv ffmpeg libgl1 git-lfs \
 && rm -rf /var/lib/apt/lists/*

# Torch CUDA 12.1
RUN python3 -m pip install --upgrade pip \
 && pip install --extra-index-url https://download.pytorch.org/whl/cu121 \
        torch==2.3.1 torchvision==0.18.1

# xFormers opzionale (se fallisce, non bloccare)
RUN pip install xformers==0.0.26.post1 --extra-index-url https://download.pytorch.org/whl/cu121 || true

# Clona kohya_ss + submodules
WORKDIR /opt
RUN git clone --depth=1 https://github.com/bmaltais/kohya_ss.git \
 && cd kohya_ss && git submodule update --init --recursive

WORKDIR /opt/kohya_ss

# 1) pulizia requirements kohya
RUN grep -v -E "file:///opt/kohya_ss/sd-scripts|-e sd-scripts|^-e \.|kohya_ss" requirements.txt > /tmp/req.kohya.txt \
 && pip install -r /tmp/req.kohya.txt

# 2) pulizia requirements sd-scripts
RUN awk '!/^(-e|#)/ && $0 !~ /file:|kohya_ss|sd-scripts/' sd-scripts/requirements.txt > /tmp/req.sd.txt \
 && pip install -r /tmp/req.sd.txt

# 3) extra utili per LoRA SDXL
RUN pip install \
    accelerate==0.33.0 safetensors==0.4.3 bitsandbytes==0.43.1 \
    transformers==4.42.3 datasets==2.19.1 peft==0.11.1 sentencepiece==0.2.0 \
    einops==0.8.0

# Rende importabili i moduli
ENV PYTHONPATH="/opt/kohya_ss:/opt/kohya_ss/sd-scripts:${PYTHONPATH}"

CMD ["bash","-lc","tail -f /dev/null"]
