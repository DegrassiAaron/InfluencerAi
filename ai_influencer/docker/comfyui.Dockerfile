# docker/comfyui.Dockerfile
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

RUN apt-get update && apt-get install -y \
    git python3 python3-pip python3-venv ffmpeg libgl1 \
    && rm -rf /var/lib/apt/lists/*

# ComfyUI
WORKDIR /opt
RUN git clone --depth=1 https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /opt/ComfyUI

# requisiti
RUN python3 -m pip install --upgrade pip \
 && pip install -r requirements.txt \
 && pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# porte e avvio
EXPOSE 8188
VOLUME ["/opt/ComfyUI/models", "/opt/ComfyUI/custom_nodes", "/opt/ComfyUI/output", "/data"]
CMD ["python3", "main.py", "--listen", "0.0.0.0"]
