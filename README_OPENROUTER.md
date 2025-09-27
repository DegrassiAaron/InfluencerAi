# Catalogo alias OpenRouter

Questo documento integra la documentazione sugli script OpenRouter fornendo un riepilogo rapido degli alias supportati dalle utility CLI (`openrouter_*.py`) e dei modelli richiamati nella guida principale. La tabella seguente riporta l'ID OpenRouter, le tariffe correnti e note utili per scegliere il modello corretto.

> _Ultimo aggiornamento:_ 26 settembre 2025. Verificare periodicamente la dashboard OpenRouter per eventuali variazioni.

| Alias CLI | ID OpenRouter | Costo input (USD) | Costo output (USD) | Note |
| --- | --- | --- | --- | --- |
| `sdxl` | `stabilityai/sdxl` | N/D | N/D | Modello SDXL standard per generazione immagini. Tariffazione per immagine disponibile solo da dashboard autenticata. |
| `sdxl-turbo` | `stabilityai/sdxl-turbo` | N/D | N/D | Variante turbo di SDXL. Consultare la dashboard per il costo per immagine più recente. |
| `flux` | `black-forest-labs/flux-1.1-pro` | N/D | N/D | Modello FLUX 1.1 Pro. Le tariffe sono visibili nel pannello OpenRouter una volta effettuato l'accesso. |
| `flux-dev` | `black-forest-labs/flux-dev` | N/D | N/D | Variante di sviluppo di FLUX, ideale per test creativi. Costo per immagine da verificare manualmente. |
| `playground-v25` | `playgroundai/playground-v2.5` | N/D | N/D | Modello Playground V2.5. Prezzi disponibili nella dashboard OpenRouter. |
| `sdxl-lightning` | `luma-photon/stable-diffusion-xl-lightning` | N/D | N/D | Versione Lightning di SDXL orientata a inferenza rapida. Consultare la dashboard per il prezzo corrente. |
| — | `meta-llama/llama-3.1-70b-instruct` | 0.00000010 | 0.00000028 | Modello testuale usato negli esempi della guida (`openrouter_text.py`). Costo per 1K token input/output. |

_Per aggiornare i valori_: usare l'endpoint `/api/v1/models` di OpenRouter con autenticazione oppure annotare manualmente le tariffe riportate nella dashboard ogni volta che cambiano.

## Novità
- **Formattazione tariffe nella webapp** – l'endpoint `/api/models` sfrutta ora heuristics avanzate per scegliere automaticamente
  la metrica più significativa (es. `Output Text USD`) e normalizzare i valori monetari in dollari. I nuovi test assicurano che
  anche stringhe con spazi o alias personalizzati vengano ripuliti correttamente.
- **Conteggio token resiliente** – le utility CLI e l'API `/api/tokenize` gestiscono risposte OpenRouter incomplete
  ricostruendo il numero totale di token da campi alternativi (`input_tokens`, `tokens[]`) per garantire feedback coerente
  anche con modelli sperimentali.
