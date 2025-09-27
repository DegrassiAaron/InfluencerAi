# Playbook 4 settimane – Dataset robusto per training (1.200 immagini pulite)

## Obiettivo
Raccogliere ~1.200 immagini **approvate** (post-QC) mantenendo coerenza identitaria, con copertura bilanciata di posa, luce, crop, contesto, outfit, espressione.

## Settimana 1 – Fondazioni (Master + Prima Copertura)
- Giorni 1–2: crea 60 master canonici (stesso look-base). Documenta sidecar.
- Giorni 3–4: variazioni **LUCE** (1 dim) su 30 master → 6–12 generate, conserva 2–4.
- Giorno 5: QC + dedup + face-sim; expected 120–240 utili.
- Giorno 6: variazioni **POSA** (1 dim) su altri 30 master; conserva 2–4.
- Giorno 7: QC + split provvisorio train/val/test (80/10/10).

## Settimana 2 – Distanza/Crop + Contesti
- Giorni 8–9: variazioni **CROP** (close/half/full) su 40 master.
- Giorni 10–11: variazioni **CONTESTO** (indoor minimal, cafe, outdoor urbano, parco).
- Giorno 12: QC cumulativo + bilanciamento distribuzioni (±20%).
- Giorno 13: augmentation **soft** (rotazione ±3°, jitter ±10%).
- Giorno 14: audit manifest + validazione JSON Schema.

## Settimana 3 – Outfit + Espressioni
- Giorni 15–16: **OUTFIT** (6 combinazioni) su 36 master.
- Giorni 17–18: **ESPRESSIONI** (neutra, soft smile, seria) su 36 master.
- Giorno 19: QC + dedup; aggiorna embedding prototipo con campione approvato.
- Giorno 20–21: round di recupero bucket poco rappresentati.

## Settimana 4 – Rifinitura + Bilanciamento
- Giorni 22–23: colma buchi (bucket underrepresented) mirati.
- Giorno 24: augmentation soft finale (×1.3) sui bucket scarsi.
- Giorno 25: QC finale, rimozione outlier (face_sim < 0.85).
- Giorni 26–27: freeze del **manifest v1.0** + export dataset (train/val/test).
- Giorni 28: redazione **Data Card** (README) e rilascio.

## KPI suggeriti
- Yield utile per batch (variazioni → approvate): 20–35%
- Similarità facciale media (cos-sim): ≥ 0.90 sui set approvati
- Dup ratio post-dedup: ≤ 3%
- Copertura bucket: nessun bucket < 10 immagini nel train

## Note operative
- Cambia **una sola dimensione** per lotto di variazioni.
- Mantieni **seed/look** quanto più possibile costanti nelle fasi di variazione.
- Esegui QC quotidiano per non accumulare debito tecnico nei metadata.
