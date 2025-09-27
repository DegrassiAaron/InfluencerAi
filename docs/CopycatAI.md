1) Pipeline step-by-step (con le 3 aggiunte)
Step 0 — Ingest & Normalizzazione

Raccogli 50–200 testi pubblici → docs[] = {id,url,ts,platform,text,kind}.

kind: organic|sponsored|unknown (inizialmente unknown).

Step 1 — Correzione linguaggi misti (lang_fix)

Rileva lingua per doc (es. langid/fasttext).

Se lang_conf < 0.90 o 2+ lingue con share>0.15 → mixed_lang=true.

Normalizza in lingua target (es. it) con traduzione conservativa:

Non tradurre citazioni/brand/hashtag.

Mantieni emoji ed espressioni gergali marcate (slang=true).

Aggiungi a doc: {lang, mixed_lang, slang}.

Step 2 — Embeddings & Clustering (temi)

Embeddings (multilingua).

UMAP → HDBSCAN (fallback k-means k=5 se dataset piccolo).

topic_clusters = [{id, size, top_terms[], exemplar_ids[]}].

Soglia tema: size ≥ 5 o p(cluster) ≥ 0.01.

Step 3 — Stance/idee (statistica → LLM)

Da ciascun cluster estrai candidate claims (n-gram, TF-IDF, pattern “credo/consiglio/evito”).

Classifica stance (pro/contra/neutro) con un classificatore leggero.

Passa a LLM solo i claims con support_docs ≥ 2 o coverage ≥ 0.15.

LLM produce parafrasi con evidence_ids (obbligatori).

Validator scarta claims senza 2+ evidenze o confidence < 0.6.

Step 4 — Stylometry

Metriche misurabili: avg_sentence_len, emoji_per_100w, questions_rate, imperative_rate, tt_ratio.

Calcola per piattaforma e media ponderata.

Step 5 — Sponsored detector (sponsored_detector)

Regole ibride (precisione > recall):

Pattern testuale: #ad, #sponsored, paid partnership, “in collaborazione con”, “codice sconto”, “use my code”, “link in bio” con sconto.

Segnali visivi/meta: presenza di “Paid partnership” (se disponibile nei metadati o HTML).

Heuristica URL: domini di affiliazione (bit.ly not alone, serve contesto) + keyword sconto.

Assegna:

sponsored_label ∈ {sponsored, organic, uncertain}

sponsored_score ∈ [0,1] (media pesata pattern forti/deboli).

Imposta doc.kind = sponsored se score ≥ 0.75; uncertain se 0.5–0.75.

Step 6 — Evolution tracker (evolution_tracker)

Finestra temporale scorrevole (es. 180 giorni, step 30).

Confronta distribuzioni tema (topics_distribution) e metriche stile:

Δtopics = 0.5 * JS_divergence(past_topics, recent_topics)

Δstyle = 0.5 * mean(|z_recent - z_past|)

evolution_score = clamp(Δtopics + Δstyle, 0..1)

Soglie:

evolution_flag = "high" se evolution_score ≥ 0.65

"moderate" 0.35–0.65, "low" < 0.35.

Registra change_points quando cluster nuovi superano coverage ≥ 0.12.

Step 7 — Consolidamento profilo

Una credenza/valore entra se supportata da ≥2 cluster o 1 cluster con confidence ≥ 0.75.

Conflitti → controversial=true.

Campi non supportati → omessi (no riempitivi).

Step 8 — Blueprint & Generazione controllata

pillars: top-3 temi per coverage (sponsored pesati 0.5).

angle_options: derivati dai temi stabili; vieta angle basati su controversial=true.

Generazione contenuti: LLM vincolato al blueprint; output solo JSON.

2) Schemi JSON aggiornati (con flag e score)
PersonaProfile.json
{
  "influencer": {"handle":"...", "platforms":["instagram","youtube"], "languages":["it","en"]},
  "data_quality": {
    "docs_total": 128,
    "mixed_lang_docs": 0.19,
    "sponsored_share": 0.21,
    "evolution_score": 0.68,
    "evolution_flag": "high"
  },
  "core_values": [
    {"value":"disciplina","confidence":0.74,"coverage":0.31,"source_ids":["ig_14","yt_7"]}
  ],
  "beliefs_positions": [
    {"topic":"HIIT","stance":"pro","confidence":0.78,"coverage":0.26,
     "evidence_ids":["yt_7","yt_12","ig_19"],"controversial":false}
  ],
  "voice_style": {
    "metrics": {
      "avg_sentence_len": 12.4,
      "emoji_per_100w": 1.8,
      "questions_rate": 0.12,
      "imperative_rate": 0.27,
      "tt_ratio": 0.49
    },
    "tone_labels": ["diretto","ironico"],
    "taboos_redlines": ["no promesse miracolose"]
  },
  "topics_distribution": [
    {"topic":"allenamento","weight":0.48},
    {"topic":"alimentazione","weight":0.30},
    {"topic":"mindset","weight":0.22}
  ],
  "evidence": [{"id":"yt_7","url":"https://...","snippet":"..."}],
  "last_updated":"2025-09-27"
}

Annotazione documenti (interno, per audit)
{
  "id":"ig_141",
  "url":"https://instagram.com/p/...",
  "ts":"2025-08-13T11:24:00Z",
  "platform":"instagram",
  "lang":"it",
  "mixed_lang": false,
  "slang": true,
  "kind":"sponsored",
  "sponsored_label":"sponsored",
  "sponsored_score":0.86,
  "text":"In collaborazione con ... usa il codice ...",
  "cluster_id": 3
}

ContentBlueprint.json
{
  "persona_ref":{"handle":"...", "version":"2025-09-27"},
  "pillars":["allenamento","alimentazione","mindset"],
  "angle_options":[
    {"angle":"controintuitivo","min_conf":0.6,"from_topic":"allenamento"},
    {"angle":"data-driven","min_conf":0.7,"from_topic":"alimentazione"}
  ],
  "voice_guardrails":{"must":["hook entro 3s"],"avoid":["claim non verificabili"]},
  "compliance":{"red_lines":["no consigli medici"]},
  "sponsored_policy":{"use_ads_content": false, "reason":"training copy on organic only"}
}

3) Prompt robusti (estrazione e generazione)

Estrattore (con evidenze + rispetto sponsored & mixed_lang)

SYSTEM
Sei un extractor conservativo. Usa SOLO i dati forniti. Se non ci sono prove, lascia il campo vuoto.
Rispondi SOLO con JSON valido PersonaProfile_parziale.

USER
Dati:
1) CLUSTERS: [{id, top_terms, exemplar_ids}]
2) CLAIMS: [{text, support_docs, coverage, evidence_ids}]
3) EVIDENCE: [{id, url, snippet, kind, lang, mixed_lang}]
4) STYLE_METRICS: {...}
5) EVOLUTION: {evolution_score, flag}
Istruzioni:
- Includi solo claims con support_docs≥2 o coverage≥0.15.
- Escludi o marca `controversial` claims con evidenze in disaccordo.
- Riporta `data_quality` con mixed_lang ratio, sponsored_share, evolution_score/flag.
- Output SOLO JSON valido.


Generatore (tema → ContentPlan controllato)

SYSTEM
Genera un ContentPlan rispettando PersonaProfile e ContentBlueprint. Vietato introdurre posizioni non supportate.
Se evolution_flag = "high", preferisci angle coerenti con i temi RECENTI.

USER
PersonaProfile: {{...}}
ContentBlueprint: {{...}}
Tema: "{{tema}}"
Vincoli:
- Escludi contenuti marcati `sponsored` se sponsored_policy.use_ads_content=false.
- Cita in trace.used_sources gli evidence_ids utilizzati.
Output: JSON valido ContentPlan.

4) Collaudo & metriche

Unit test

lang_fix: rilevazione mixed_lang e traduzione conservativa (non toccare hashtag/brand).

sponsored_detector: pattern forti correttamente classificati; deboli → uncertain.

evolution_tracker: JS-divergence e z-score calcolati correttamente, soglie rispettate.

Integration test

Corpus sintetico con blocchi “old” vs “recent”: verifica evolution_flag.

Pipeline completa → PersonaProfile/Blueprint: schema valido, topics_distribution ~ somma 1, data_quality coerente.

Generazione: ContentPlan coerente con sponsored_policy.

Quality KPI (minimi)

Hallucination rate < 5% (claims senza 2 evidenze).

Sponsored mislabel rate < 10% (richiede set annotato).

Evolution responsiveness: se Δtopics≥0.2 in 60 gg → evolution_flag non deve restare “low”.

5) Pseudocodice essenziale (plug-in nei tuoi moduli)
def lang_fix(doc):
    lang, conf = detect_lang(doc.text)
    parts = detect_mixed(doc.text)  # es. segmenti EN in testo IT
    mixed = parts.share > 0.15 or conf < 0.90
    norm_text = conservative_translate(doc.text, target="it") if mixed else doc.text
    return doc | {"lang": lang, "mixed_lang": mixed, "text_norm": norm_text}

def sponsored_detector(doc):
    score = 0.0
    score += 0.6 if re_has_ad_hashtags(doc.text) else 0
    score += 0.3 if has_paid_partnership_badge(doc.meta) else 0
    score += 0.2 if has_discount_code(doc.text) else 0
    label = "sponsored" if score>=0.75 else ("uncertain" if score>=0.5 else "organic")
    return doc | {"sponsored_label": label, "sponsored_score": round(min(score,1.0),2)}

def evolution_tracker(history_profiles):
    past, recent = split_by_time(history_profiles, window_days=180)
    jsd = jensen_shannon(past.topics_distribution, recent.topics_distribution) * 0.5
    style_delta = mean_abs_z(recent.style_metrics, past.style_metrics) * 0.5
    score = clamp(jsd + style_delta, 0, 1)
    flag = "high" if score>=0.65 else ("moderate" if score>=0.35 else "low")
    return {"evolution_score": score, "evolution_flag": flag}

6) Perché funziona / rischi residui

Funziona perché: statistiche prima (riducono bias/allucinazioni), LLM dopo (coerenza e sintesi), validazione con evidenze e KPI.

Rischi: falsi positivi sponsorizzati (ambasciatore di brand non dichiarato), errori su slang/ironia (stance rumorosa), topic-shift dovuto a stagionalità. Mitigazioni incluse (uncertain, pesi, finestre temporali).