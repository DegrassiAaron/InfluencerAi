# QC Checklist – InfluencerAI Dataset
Data: 2025-09-27 07:20

## Gate quantitativi
- Similarità facciale (cosine) ≥ **0.85** (rispetto all'embedding prototipo)
- Dedup: distanza Hamming pHash ≤ **10** → **REJECT**
- NSFW: **false**
- Risoluzione minima: lato min ≥ **768 px**
- Rapporto d'aspetto consentiti: 1:1, 4:5, 3:4 (o documentare altrimenti)

## Coerenza identitaria
- Occhi verdi coerenti; distanza pupille stabile
- Capelli biondi; riga e texture coerenti
- Simmetria labbra/viso non eccessivamente deformata
- Assenza di artefatti su orecchie/dita/denti

## Copertura e bilanciamento
- La variazione cambia **1 sola dimensione** (pose/light/crop/context/outfit/expression)
- Distribuzione per dimensione ~ bilanciata (±20%)
- No cluster di 10+ immagini quasi identiche nello stesso bucket

## Metadati e naming
- Filename conforme allo standard
- `.json` sidecar valido contro `sidecar_schema.json`
- `manifest` aggiornato e valido contro `manifest_schema.json`

## Regressioni note
- Drift identitario in golden hour controluce → ridurre denoise/strength
- Outfit scuro in notturna urbana aumenta falsi positivi NSFW → alzare soglia illuminazione

