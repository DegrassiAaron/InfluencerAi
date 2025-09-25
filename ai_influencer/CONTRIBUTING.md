# Contribuire al progetto

Grazie! Ecco le regole base per PR snelle e riproducibili.

## Requisiti
- Python 3.10+
- Docker + NVIDIA Container Toolkit
- PowerShell o Bash

## Setup dev
```bash
# opzionale: ambiente virtuale
python -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
```

## Stile & QA veloci
- Mantieni gli script compatibili con Linux/WSL e Windows.
- Evita dipendenze non-FOSS.
- Aggiungi commenti a intestazione script con uso e parametri.

Quick checks:
```bash
python -m compileall scripts
```

## Git Flow
- Crea branch dalla `main`: `feature/<breve-nome>`
- Commit piccoli e descrittivi.
- PR con: descrizione, test manuali fatti, output atteso, screenshot se utile.

## Dati & Modelli
- Non committare file in `data/` e `models/`. Usa release o storage esterno.
