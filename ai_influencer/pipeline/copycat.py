"""Implementation of the CopycatAI influencer analysis pipeline.

The pipeline is intentionally pragmatic: it mirrors the specification
contained in ``docs/CopycatAI.md`` while staying lightweight enough to be
executed inside the unit tests that accompany this project.  The
implementation favours deterministic heuristics over external services so
that the behaviour can be validated offline.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "Document",
    "TopicCluster",
    "StylometryMetrics",
    "EvolutionResult",
    "PersonaProfile",
    "PipelineResult",
    "CopycatAIPipeline",
    "lang_fix",
    "sponsored_detector",
    "evolution_tracker",
]

# ---------------------------------------------------------------------------
# Dataclasses used throughout the pipeline
# ---------------------------------------------------------------------------


@dataclass
class Document:
    """Input record ingested by the pipeline."""

    id: str
    url: str
    ts: datetime
    platform: str
    text: str
    kind: str = "unknown"
    meta: Dict[str, Any] = field(default_factory=dict)

    # Enriched fields populated by the pipeline
    lang: Optional[str] = None
    lang_conf: Optional[float] = None
    mixed_lang: bool = False
    slang: bool = False
    text_norm: Optional[str] = None
    sponsored_label: Optional[str] = None
    sponsored_score: Optional[float] = None
    cluster_id: Optional[int] = None


@dataclass
class TopicCluster:
    """Aggregated representation of a set of semantically related documents."""

    id: int
    size: int
    top_terms: List[str]
    exemplar_ids: List[str]
    coverage: float


@dataclass
class StylometryMetrics:
    """Stylometric descriptors calculated for a group of documents."""

    avg_sentence_len: float
    emoji_per_100w: float
    questions_rate: float
    imperative_rate: float
    tt_ratio: float


@dataclass
class EvolutionResult:
    """Stores the temporal drift indicators for the influencer."""

    evolution_score: float
    evolution_flag: str
    change_points: List[str]


@dataclass
class PersonaProfile:
    """Structured summary matching the schema defined in the spec."""

    influencer: Dict[str, Any]
    data_quality: Dict[str, Any]
    core_values: List[Dict[str, Any]]
    beliefs_positions: List[Dict[str, Any]]
    voice_style: Dict[str, Any]
    topics_distribution: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    last_updated: str


@dataclass
class PipelineResult:
    """Bundle holding the major artefacts produced by the pipeline."""

    persona_profile: PersonaProfile
    content_blueprint: Dict[str, Any]
    annotated_documents: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Language handling and normalisation helpers (Step 1)
# ---------------------------------------------------------------------------

_ITALIAN_WORDS = {
    "e",
    "che",
    "non",
    "per",
    "con",
    "sono",
    "fare",
    "allenamento",
    "ciao",
    "ragazzi",
    "consiglio",
    "evito",
    "sempre",
    "giorno",
    "grande",
    "ciao",
    "bene",
}

_ENGLISH_WORDS = {
    "and",
    "the",
    "for",
    "with",
    "are",
    "workout",
    "hello",
    "guys",
    "tip",
    "avoid",
    "always",
    "day",
    "great",
}

_SLANG_TOKENS = {
    "lol",
    "lmao",
    "haha",
    "ahah",
    "omg",
    "raga",
    "tipo",
    "yolo",
}

_EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAD6\U0001F900-\U0001F9FF\u2600-\u27BF]")
_WORD_PATTERN = re.compile(r"[\w']+")


@dataclass
class _LanguageDetectionResult:
    lang: str
    confidence: float
    secondary_share: float


def _detect_language(text: str) -> _LanguageDetectionResult:
    """A lightweight language detector using stop-word coverage heuristics."""

    tokens = [token.lower() for token in _WORD_PATTERN.findall(text)]
    total = max(len(tokens), 1)
    italian_hits = sum(1 for token in tokens if token in _ITALIAN_WORDS)
    english_hits = sum(1 for token in tokens if token in _ENGLISH_WORDS)

    if italian_hits == 0 and english_hits == 0:
        # Default to Italian with low confidence – the pipeline targets it
        return _LanguageDetectionResult("it", 0.5, 0.0)

    if italian_hits >= english_hits:
        main = "it"
        confidence = italian_hits / total
        secondary = english_hits / total
    else:
        main = "en"
        confidence = english_hits / total
        secondary = italian_hits / total

    return _LanguageDetectionResult(main, min(confidence, 1.0), secondary)


_TRANSLATION_GLOSSARY = {
    "workout": "allenamento",
    "training": "allenamento",
    "tip": "consiglio",
    "avoid": "evita",
    "healthy": "sano",
    "mindset": "mentalità",
    "focus": "focus",
}

_HASHTAG_PATTERN = re.compile(r"#[\w_]+")
_BRAND_PATTERN = re.compile(r"@[\w_]+")


def _conservative_translate(text: str, target: str) -> str:
    """Very small, rule-based translator used when normalisation is needed.

    The function intentionally keeps hashtags, mentions, and brand names
    untouched, replacing a curated subset of English keywords with their
    Italian counterparts while preserving the original casing.
    """

    if target != "it":
        return text

    def _replace(match: re.Match[str]) -> str:
        word = match.group(0)
        lower = word.lower()
        if lower in _TRANSLATION_GLOSSARY:
            translated = _TRANSLATION_GLOSSARY[lower]
            return translated.capitalize() if word[0].isupper() else translated
        return word

    # Protect hashtags and brands from translation
    protected = {}
    for pattern in (_HASHTAG_PATTERN, _BRAND_PATTERN):
        for tag in pattern.findall(text):
            placeholder = f"§{len(protected)}§"
            protected[placeholder] = tag
            text = text.replace(tag, placeholder)

    translated = re.sub(r"[A-Za-z']+", _replace, text)

    for placeholder, original in protected.items():
        translated = translated.replace(placeholder, original)

    return translated


def _detect_slang(tokens: Iterable[str], text: str) -> bool:
    if any(token in _SLANG_TOKENS for token in tokens):
        return True
    if re.search(r"(.)\1{2,}", text):
        return True
    if _EMOJI_PATTERN.search(text):
        return True
    return False


def lang_fix(doc: Document, target_lang: str = "it") -> Document:
    """Perform language detection and mixed-language normalisation."""

    detection = _detect_language(doc.text)
    tokens = [token.lower() for token in _WORD_PATTERN.findall(doc.text)]
    slang = _detect_slang(tokens, doc.text)
    mixed = detection.confidence < 0.9 or detection.secondary_share > 0.15
    normalized_text = (
        _conservative_translate(doc.text, target_lang) if mixed else doc.text
    )
    doc.lang = detection.lang
    doc.lang_conf = detection.confidence
    doc.mixed_lang = mixed
    doc.slang = slang
    doc.text_norm = normalized_text
    return doc


# ---------------------------------------------------------------------------
# Step 2 – Embeddings & clustering
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "e",
    "che",
    "con",
    "per",
    "the",
    "and",
    "con",
    "una",
    "del",
    "della",
    "di",
    "un",
    "una",
    "lo",
    "la",
    "gli",
    "le",
    "a",
    "da",
    "su",
}


def _tokenize(text: str) -> List[str]:
    return [
        token.lower()
        for token in _WORD_PATTERN.findall(text)
        if token.lower() not in _STOPWORDS and len(token) > 2
    ]


def _cluster_documents(documents: List[Document]) -> List[TopicCluster]:
    tokenised_docs: Dict[str, List[str]] = {}
    for doc in documents:
        source = doc.text_norm or doc.text
        tokenised_docs[doc.id] = _tokenize(source)

    # Group documents by their dominant token.  It is a simple but
    # surprisingly effective heuristic for short social-media snippets.
    cluster_map: Dict[str, List[Document]] = defaultdict(list)
    for doc in documents:
        tokens = tokenised_docs.get(doc.id, [])
        dominant = tokens[0] if tokens else "vario"
        cluster_map[dominant].append(doc)

    total_docs = max(len(documents), 1)
    clusters: List[TopicCluster] = []
    next_id = 1
    for key, members in cluster_map.items():
        counter: Counter[str] = Counter()
        for member in members:
            counter.update(tokenised_docs.get(member.id, []))
        top_terms = [term for term, _ in counter.most_common(6)]
        size = len(members)
        coverage = size / total_docs
        if size < 5 and coverage < 0.01:
            continue
        exemplars = sorted(members, key=lambda d: len(d.text), reverse=True)[:3]
        cluster = TopicCluster(
            id=next_id,
            size=size,
            top_terms=top_terms,
            exemplar_ids=[doc.id for doc in exemplars],
            coverage=coverage,
        )
        for member in members:
            member.cluster_id = cluster.id
        clusters.append(cluster)
        next_id += 1

    clusters.sort(key=lambda c: c.size, reverse=True)
    return clusters


# ---------------------------------------------------------------------------
# Step 3 – Claim extraction and validation
# ---------------------------------------------------------------------------

_CLAIM_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bcredo\b",
        r"\bconsiglio\b",
        r"\bevito\b",
        r"\bdevi\b",
        r"\bdovresti\b",
        r"\bmai\s+più\b",
        r"\bnon\s+fare\b",
    ]
]

_PRO_KEYWORDS = {"amo", "adoro", "ottimo", "pro", "favore", "consiglio", "vale"}
_CON_KEYWORDS = {"odio", "sconsiglio", "contro", "evito", "male", "no"}


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _extract_claim_candidates(cluster_docs: List[Document]) -> Dict[str, Dict[str, Any]]:
    claims: Dict[str, Dict[str, Any]] = {}
    for doc in cluster_docs:
        sentences = _split_sentences(doc.text)
        for sentence in sentences:
            if not any(pattern.search(sentence) for pattern in _CLAIM_PATTERNS):
                continue
            key = sentence.lower()
            entry = claims.setdefault(
                key,
                {
                    "text": sentence,
                    "support_docs": set(),
                    "evidence_ids": set(),
                    "pro": 0,
                    "contra": 0,
                },
            )
            entry["support_docs"].add(doc.id)
            entry["evidence_ids"].add(doc.id)
            tokens = _tokenize(sentence)
            if any(token in _PRO_KEYWORDS for token in tokens):
                entry["pro"] += 1
            if any(token in _CON_KEYWORDS for token in tokens):
                entry["contra"] += 1
    return claims


def _determine_stance(data: Dict[str, Any]) -> str:
    if data["pro"] > data["contra"]:
        return "pro"
    if data["contra"] > data["pro"]:
        return "contra"
    return "neutro"


def _paraphrase_claim(text: str, stance: str) -> str:
    stance_map = {
        "pro": "sostengono",
        "contra": "mettono in guardia",
        "neutro": "osservano",
    }
    prefix = stance_map.get(stance, "osservano")
    return f"Gli autori {prefix} che {text.strip()}"


def _build_claims(
    clusters: List[TopicCluster],
    documents: List[Document],
) -> Tuple[List[Dict[str, Any]], Dict[int, List[str]]]:
    by_cluster: Dict[int, List[Document]] = defaultdict(list)
    for doc in documents:
        if doc.cluster_id is not None:
            by_cluster[doc.cluster_id].append(doc)

    cluster_claims: Dict[int, List[str]] = defaultdict(list)
    final_claims: List[Dict[str, Any]] = []

    for cluster in clusters:
        docs_in_cluster = by_cluster.get(cluster.id, [])
        if not docs_in_cluster:
            continue
        candidates = _extract_claim_candidates(docs_in_cluster)
        for candidate in candidates.values():
            support_docs = candidate["support_docs"]
            coverage = len(support_docs) / max(len(docs_in_cluster), 1)
            if len(support_docs) < 2 and coverage < 0.15:
                continue
            stance = _determine_stance(candidate)
            paraphrased = _paraphrase_claim(candidate["text"], stance)
            evidence_ids = sorted(candidate["evidence_ids"])
            confidence = min(0.9, 0.5 + 0.1 * len(support_docs) + 0.3 * coverage)
            claim_entry = {
                "topic": cluster.top_terms[0] if cluster.top_terms else "vario",
                "text": paraphrased,
                "stance": stance,
                "confidence": round(confidence, 2),
                "coverage": round(coverage, 2),
                "evidence_ids": evidence_ids,
                "controversial": candidate["pro"] > 0 and candidate["contra"] > 0,
            }
            final_claims.append(claim_entry)
            cluster_claims[cluster.id].append(claim_entry["topic"])
    return final_claims, cluster_claims


# ---------------------------------------------------------------------------
# Step 4 – Stylometry
# ---------------------------------------------------------------------------


def _count_emojis(text: str) -> int:
    return len(_EMOJI_PATTERN.findall(text))


def _sentence_metrics(text: str) -> Tuple[int, int, int, int]:
    sentences = _split_sentences(text) or [text]
    total_words = 0
    questions = 0
    imperatives = 0
    for sentence in sentences:
        words = _WORD_PATTERN.findall(sentence)
        total_words += len(words)
        if sentence.endswith("?"):
            questions += 1
        if words:
            first = words[0].lower()
            if first in {"fai", "usa", "prova", "ricorda", "evita", "sii", "vai"}:
                imperatives += 1
    return len(sentences), total_words, questions, imperatives


def _compute_stylometry(documents: List[Document]) -> Tuple[StylometryMetrics, Dict[str, StylometryMetrics], Dict[str, Dict[str, float]]]:
    per_platform: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    per_doc_metrics: Dict[str, Dict[str, float]] = {}

    for doc in documents:
        sentences_count, total_words, questions, imperatives = _sentence_metrics(
            doc.text
        )
        tokens = _tokenize(doc.text)
        unique_tokens = len(set(tokens))
        emoji_count = _count_emojis(doc.text)
        doc_metrics = {
            "avg_sentence_len": total_words / max(sentences_count, 1),
            "emoji_per_100w": (emoji_count / max(total_words, 1)) * 100,
            "questions_rate": questions / max(sentences_count, 1),
            "imperative_rate": imperatives / max(sentences_count, 1),
            "tt_ratio": unique_tokens / max(len(tokens), 1),
        }
        per_doc_metrics[doc.id] = doc_metrics
        per_platform[doc.platform.lower()].append(doc_metrics)

    def _aggregate(values: List[Dict[str, float]]) -> StylometryMetrics:
        if not values:
            return StylometryMetrics(0, 0, 0, 0, 0)
        return StylometryMetrics(
            avg_sentence_len=mean(v["avg_sentence_len"] for v in values),
            emoji_per_100w=mean(v["emoji_per_100w"] for v in values),
            questions_rate=mean(v["questions_rate"] for v in values),
            imperative_rate=mean(v["imperative_rate"] for v in values),
            tt_ratio=mean(v["tt_ratio"] for v in values),
        )

    global_metrics = _aggregate(list(per_doc_metrics.values()))
    platform_metrics = {
        platform: _aggregate(values) for platform, values in per_platform.items()
    }
    return global_metrics, platform_metrics, per_doc_metrics


# ---------------------------------------------------------------------------
# Step 5 – Sponsored detector
# ---------------------------------------------------------------------------

_AD_HASHTAGS = {
    "#ad",
    "#adv",
    "#sponsored",
    "#sponsorizzato",
    "#collaborazione",
    "#partner",
}

_PAID_PARTNERSHIP_KEYWORDS = {
    "paid partnership",
    "partnership a pagamento",
    "in collaborazione con",
    "collaborazione con",
    "in partnership con",
}

_DISCOUNT_KEYWORDS = {
    "codice",
    "code",
    "sconto",
    "discount",
    "promo",
}

_AFFILIATE_DOMAINS = {
    "amzn.to",
    "bit.ly",
    "go.magik.ly",
    "shopstyle.it",
    "rstyle.me",
}

_URL_PATTERN = re.compile(r"https?://[\w./%-]+", re.IGNORECASE)


def _re_has_ad_hashtags(text: str) -> bool:
    return any(tag in text.lower() for tag in _AD_HASHTAGS)


def _has_paid_partnership_badge(meta: Dict[str, Any]) -> bool:
    partnership = meta.get("paid_partnership") or meta.get("partnership")
    if isinstance(partnership, bool):
        return partnership
    if isinstance(partnership, str):
        return partnership.lower() in {"true", "1", "yes"}
    return False


def _has_discount_code(text: str) -> bool:
    lower = text.lower()
    if any(keyword in lower for keyword in _DISCOUNT_KEYWORDS):
        return True
    return bool(re.search(r"codice\s+\w+", lower))


def _has_affiliate_url(text: str) -> bool:
    for url in _URL_PATTERN.findall(text.lower()):
        if any(domain in url for domain in _AFFILIATE_DOMAINS):
            return True
    return False


def sponsored_detector(doc: Document) -> Document:
    """Label a document as sponsored/organic/uncertain."""

    text = doc.text.lower()
    score = 0.0
    if _re_has_ad_hashtags(text):
        score += 0.6
    if _has_paid_partnership_badge(doc.meta):
        score += 0.3
    if _has_discount_code(text) or _has_affiliate_url(text):
        score += 0.2
    if any(keyword in text for keyword in _PAID_PARTNERSHIP_KEYWORDS):
        score += 0.3

    score = min(score, 1.0)
    if score >= 0.75:
        label = "sponsored"
    elif score >= 0.5:
        label = "uncertain"
    else:
        label = "organic"

    doc.sponsored_label = label
    doc.sponsored_score = round(score, 2)
    if score >= 0.75:
        doc.kind = "sponsored"
    elif 0.5 <= score < 0.75:
        doc.kind = "uncertain"
    else:
        doc.kind = "organic"
    return doc


# ---------------------------------------------------------------------------
# Step 6 – Evolution tracker
# ---------------------------------------------------------------------------


def _probabilities_from_counts(counts: Counter[str]) -> Dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {key: 0.0 for key in counts}
    return {key: value / total for key, value in counts.items()}


def _jensen_shannon(p: Dict[str, float], q: Dict[str, float]) -> float:
    keys = set(p) | set(q)
    m = {key: 0.5 * (p.get(key, 0.0) + q.get(key, 0.0)) for key in keys}

    def _kl(div_p: Dict[str, float], div_m: Dict[str, float]) -> float:
        result = 0.0
        for key in keys:
            value = div_p.get(key, 0.0)
            if value == 0:
                continue
            result += value * math.log2(value / max(div_m.get(key, 1e-12), 1e-12))
        return result

    return 0.5 * (_kl(p, m) + _kl(q, m))


def _mean_abs_z(
    past_values: List[Dict[str, float]],
    recent_values: List[Dict[str, float]],
) -> float:
    if not past_values or not recent_values:
        return 0.0

    metrics = past_values[0].keys()
    combined: Dict[str, List[float]] = {metric: [] for metric in metrics}
    for values in past_values + recent_values:
        for metric, value in values.items():
            combined[metric].append(value)

    z_past: Dict[str, float] = {}
    z_recent: Dict[str, float] = {}

    for metric in metrics:
        all_values = combined[metric]
        mu = mean(all_values)
        sigma = pstdev(all_values) if len(all_values) > 1 else 0.0
        if sigma == 0:
            z_past[metric] = 0.0
            z_recent[metric] = 0.0
            continue
        past_mean = mean(values[metric] for values in past_values)
        recent_mean = mean(values[metric] for values in recent_values)
        z_past[metric] = (past_mean - mu) / sigma
        z_recent[metric] = (recent_mean - mu) / sigma

    diffs = [abs(z_recent[m] - z_past[m]) for m in metrics]
    return sum(diffs) / len(diffs)


@dataclass
class _WindowedData:
    topics: Counter[str]
    style_metrics: List[Dict[str, float]]


def _split_by_time(documents: List[Document], *, window_days: int = 180) -> Tuple[_WindowedData, _WindowedData]:
    if not documents:
        empty = _WindowedData(Counter(), [])
        return empty, empty

    documents_sorted = sorted(documents, key=lambda d: d.ts)
    latest_ts = documents_sorted[-1].ts
    cutoff = latest_ts - timedelta(days=window_days)

    past_docs = [doc for doc in documents_sorted if doc.ts < cutoff]
    recent_docs = [doc for doc in documents_sorted if doc.ts >= cutoff]

    def _collect(docs: List[Document]) -> _WindowedData:
        topics = Counter()
        style_metrics = []
        for doc in docs:
            if doc.cluster_id is not None:
                topics[str(doc.cluster_id)] += 1

            sentences = _split_sentences(doc.text)
            sentence_count = len(sentences) if sentences else 1
            words = _WORD_PATTERN.findall(doc.text)
            word_count = len(words)
            tokens = _tokenize(doc.text)
            token_count = len(tokens) or 1
            style_metrics.append(
                {
                    "avg_sentence_len": word_count / sentence_count,
                    "emoji_per_100w": (
                        _count_emojis(doc.text) / max(word_count, 1)
                    )
                    * 100,
                    "questions_rate": 1.0
                    if doc.text.strip().endswith("?")
                    else 0.0,
                    "imperative_rate": 1.0
                    if words and words[0].lower()
                    in {"fai", "usa", "prova", "ricorda", "evita", "sii"}
                    else 0.0,
                    "tt_ratio": len(set(tokens)) / token_count,
                }
            )
        return _WindowedData(topics, style_metrics)

    return _collect(past_docs), _collect(recent_docs)


def evolution_tracker(documents: List[Document]) -> EvolutionResult:
    past, recent = _split_by_time(documents)

    past_probs = _probabilities_from_counts(past.topics)
    recent_probs = _probabilities_from_counts(recent.topics)

    if not past.topics and not recent.topics:
        return EvolutionResult(0.0, "low", [])

    jsd = _jensen_shannon(past_probs, recent_probs) if past_probs and recent_probs else 0.0
    style_delta = _mean_abs_z(past.style_metrics, recent.style_metrics)
    score = max(0.0, min((jsd * 0.5) + (style_delta * 0.5), 1.0))
    if score >= 0.65:
        flag = "high"
    elif score >= 0.35:
        flag = "moderate"
    else:
        flag = "low"

    change_points = []
    for topic, weight in recent_probs.items():
        if weight >= 0.12 and past_probs.get(topic, 0.0) < 0.05:
            change_points.append(topic)

    return EvolutionResult(round(score, 2), flag, change_points)


# ---------------------------------------------------------------------------
# Step 7 – Profile consolidation
# ---------------------------------------------------------------------------


def _build_topics_distribution(clusters: List[TopicCluster]) -> List[Dict[str, Any]]:
    total = sum(cluster.coverage for cluster in clusters) or 1.0
    distribution = [
        {
            "topic": cluster.top_terms[0] if cluster.top_terms else "vario",
            "weight": round(cluster.coverage / total, 2),
        }
        for cluster in clusters
    ]
    return distribution


def _derive_tone_labels(metrics: StylometryMetrics) -> List[str]:
    labels = []
    if metrics.questions_rate > 0.2:
        labels.append("coinvolgente")
    if metrics.emoji_per_100w > 1.0:
        labels.append("informale")
    if metrics.avg_sentence_len > 15:
        labels.append("approfondito")
    else:
        labels.append("diretto")
    if metrics.imperative_rate > 0.2:
        labels.append("motivazionale")
    return labels


def _derive_core_values(
    clusters: List[TopicCluster],
    claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    values = []
    claim_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        claim_map[claim["topic"]].append(claim)

    for cluster in clusters:
        if not cluster.top_terms:
            continue
        topic = cluster.top_terms[0]
        associated_claims = claim_map.get(topic, [])
        if cluster.coverage < 0.15 and len(associated_claims) < 1:
            continue
        confidence = mean(
            claim["confidence"] for claim in associated_claims
        ) if associated_claims else 0.6
        coverage = max(
            [claim["coverage"] for claim in associated_claims], default=cluster.coverage
        )
        evidence_ids = sorted(
            {
                evidence
                for claim in associated_claims
                for evidence in claim["evidence_ids"]
            }
        )
        values.append(
            {
                "value": topic,
                "confidence": round(confidence, 2),
                "coverage": round(coverage, 2),
                "source_ids": evidence_ids,
            }
        )
    return values


def _build_beliefs_positions(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for claim in claims:
        results.append(
            {
                "topic": claim["topic"],
                "stance": claim["stance"],
                "confidence": claim["confidence"],
                "coverage": claim["coverage"],
                "evidence_ids": claim["evidence_ids"],
                "controversial": claim["controversial"],
            }
        )
    return results


def _build_evidence(documents: List[Document]) -> List[Dict[str, Any]]:
    evidence = []
    for doc in documents:
        snippet = doc.text.strip().split("\n")[0][:140]
        evidence.append(
            {
                "id": doc.id,
                "url": doc.url,
                "snippet": snippet,
                "kind": doc.kind,
                "lang": doc.lang,
                "mixed_lang": doc.mixed_lang,
            }
        )
    return evidence


# ---------------------------------------------------------------------------
# Step 8 – Blueprint
# ---------------------------------------------------------------------------


def _sponsored_weight(documents: List[Document]) -> float:
    if not documents:
        return 0.0
    sponsored = sum(1 for doc in documents if doc.sponsored_label == "sponsored")
    return sponsored / len(documents)


def _blueprint_angles(clusters: List[TopicCluster], claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    angles = []
    claim_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        claim_map[claim["topic"]].append(claim)

    for cluster in clusters:
        if not cluster.top_terms:
            continue
        topic = cluster.top_terms[0]
        associated_claims = claim_map.get(topic, [])
        if any(claim["controversial"] for claim in associated_claims):
            # Skip controversial topics when proposing angles
            continue
        min_conf = (
            min(claim["confidence"] for claim in associated_claims)
            if associated_claims
            else 0.6
        )
        if "dati" in cluster.top_terms:
            angle_label = "data-driven"
        elif cluster.coverage < 0.2:
            angle_label = "controintuitivo"
        else:
            angle_label = "best-practice"
        angle = {
            "angle": angle_label,
            "min_conf": round(min_conf, 2),
            "from_topic": topic,
        }
        angles.append(angle)
    return angles


def _voice_guardrails(metrics: Dict[str, float]) -> Dict[str, List[str]]:
    must = []
    avoid = []
    if metrics.get("avg_sentence_len", 0.0) < 12:
        must.append("hook entro 3s")
    else:
        must.append("approfondire con esempi")
    if metrics.get("questions_rate", 0.0) > 0.3:
        avoid.append("interrogativi retorici eccessivi")
    else:
        avoid.append("claim non verificabili")
    return {"must": must, "avoid": avoid}


def _sponsored_policy(documents: List[Document]) -> Dict[str, Any]:
    share = _sponsored_weight(documents)
    use_ads = share >= 0.3
    reason = (
        "sufficiente materiale sponsorizzato" if use_ads else "training copy on organic only"
    )
    return {"use_ads_content": use_ads, "reason": reason}


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------


class CopycatAIPipeline:
    """High level orchestrator implementing the CopycatAI flow."""

    def __init__(self, *, target_language: str = "it") -> None:
        self.target_language = target_language

    def run(
        self,
        documents: Sequence[Dict[str, Any]],
        *,
        influencer_handle: str = "unknown",
        platforms: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
    ) -> PipelineResult:
        ingested = [self._ingest(doc) for doc in documents]
        for doc in ingested:
            lang_fix(doc, target_lang=self.target_language)
            sponsored_detector(doc)
        clusters = _cluster_documents(ingested)
        claims, _ = _build_claims(clusters, ingested)
        global_metrics, platform_metrics, _ = _compute_stylometry(ingested)
        evolution = evolution_tracker(ingested)

        persona_profile = self._build_persona_profile(
            ingested,
            clusters,
            claims,
            global_metrics,
            evolution,
            influencer_handle=influencer_handle,
            platforms=platforms,
            languages=languages,
        )
        blueprint = self._build_content_blueprint(
            ingested,
            clusters,
            claims,
            persona_profile,
        )
        annotated = [self._annotate_document(doc) for doc in ingested]
        return PipelineResult(persona_profile, blueprint, annotated)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ingest(self, payload: Dict[str, Any]) -> Document:
        required = {"id", "url", "ts", "platform", "text"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"Missing document fields: {sorted(missing)}")
        ts_value = payload["ts"]
        if isinstance(ts_value, str):
            ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
        elif isinstance(ts_value, datetime):
            ts = ts_value
        else:
            raise TypeError("ts must be ISO string or datetime")
        return Document(
            id=str(payload["id"]),
            url=str(payload["url"]),
            ts=ts,
            platform=str(payload["platform"]).lower(),
            text=str(payload["text"]),
            kind=str(payload.get("kind", "unknown")),
            meta=dict(payload.get("meta", {})),
        )

    def _build_persona_profile(
        self,
        documents: List[Document],
        clusters: List[TopicCluster],
        claims: List[Dict[str, Any]],
        global_metrics: StylometryMetrics,
        evolution: EvolutionResult,
        *,
        influencer_handle: str,
        platforms: Optional[List[str]],
        languages: Optional[List[str]],
    ) -> PersonaProfile:
        topics_distribution = _build_topics_distribution(clusters)
        core_values = _derive_core_values(clusters, claims)
        beliefs_positions = _build_beliefs_positions(claims)
        tone_labels = _derive_tone_labels(global_metrics)
        evidence = _build_evidence(documents)

        mixed_lang_ratio = (
            sum(1 for doc in documents if doc.mixed_lang) / max(len(documents), 1)
        )
        sponsored_share = _sponsored_weight(documents)
        last_updated = max(doc.ts for doc in documents).date().isoformat()

        persona = PersonaProfile(
            influencer={
                "handle": influencer_handle,
                "platforms": platforms or sorted({doc.platform for doc in documents}),
                "languages": languages or [self.target_language],
            },
            data_quality={
                "docs_total": len(documents),
                "mixed_lang_docs": round(mixed_lang_ratio, 2),
                "sponsored_share": round(sponsored_share, 2),
                "evolution_score": evolution.evolution_score,
                "evolution_flag": evolution.evolution_flag,
            },
            core_values=core_values,
            beliefs_positions=beliefs_positions,
            voice_style={
                "metrics": {
                    "avg_sentence_len": round(global_metrics.avg_sentence_len, 2),
                    "emoji_per_100w": round(global_metrics.emoji_per_100w, 2),
                    "questions_rate": round(global_metrics.questions_rate, 2),
                    "imperative_rate": round(global_metrics.imperative_rate, 2),
                    "tt_ratio": round(global_metrics.tt_ratio, 2),
                },
                "tone_labels": tone_labels,
                "taboos_redlines": ["no promesse miracolose"],
            },
            topics_distribution=topics_distribution,
            evidence=evidence,
            last_updated=last_updated,
        )
        return persona

    def _build_content_blueprint(
        self,
        documents: List[Document],
        clusters: List[TopicCluster],
        claims: List[Dict[str, Any]],
        persona_profile: PersonaProfile,
    ) -> Dict[str, Any]:
        sponsored_share = _sponsored_weight(documents)
        weighted_topics: List[Tuple[str, float]] = []
        for cluster in clusters:
            topic = cluster.top_terms[0] if cluster.top_terms else "vario"
            weight = cluster.coverage * (0.5 if sponsored_share > 0 and topic in {"promo", "brand"} else 1.0)
            weighted_topics.append((topic, weight))
        weighted_topics.sort(key=lambda item: item[1], reverse=True)
        pillars = [topic for topic, _ in weighted_topics[:3]]

        angles = _blueprint_angles(clusters, claims)
        guardrails = _voice_guardrails(persona_profile.voice_style["metrics"])
        policy = _sponsored_policy(documents)

        return {
            "persona_ref": {
                "handle": persona_profile.influencer["handle"],
                "version": persona_profile.last_updated,
            },
            "pillars": pillars,
            "angle_options": angles,
            "voice_guardrails": guardrails,
            "compliance": {"red_lines": ["no consigli medici"]},
            "sponsored_policy": policy,
        }

    def _annotate_document(self, doc: Document) -> Dict[str, Any]:
        return {
            "id": doc.id,
            "url": doc.url,
            "ts": doc.ts.isoformat(),
            "platform": doc.platform,
            "lang": doc.lang,
            "mixed_lang": doc.mixed_lang,
            "slang": doc.slang,
            "kind": doc.kind,
            "sponsored_label": doc.sponsored_label,
            "sponsored_score": doc.sponsored_score,
            "text": doc.text,
            "cluster_id": doc.cluster_id,
        }


