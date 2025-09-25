# Security Policy

- Non committare credenziali: usa `.env` e secret di GitHub Actions.
- Ruota le chiavi in caso di sospetto leak (OpenRouter, ecc.).
- Segnala vulnerabilità aprendo una Issue con tag `security` (senza chiavi).
- I container non espongono porte oltre quelle necessarie (ComfyUI: 8188).
