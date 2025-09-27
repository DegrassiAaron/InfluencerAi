from datetime import datetime, timedelta

import pytest

from ai_influencer.pipeline import (
    CopycatAIPipeline,
    Document,
    evolution_tracker,
    lang_fix,
    sponsored_detector,
)


def _build_doc(**kwargs):
    payload = {
        "id": kwargs.get("id", "doc"),
        "url": "https://example.com",
        "ts": kwargs.get("ts", datetime.now().isoformat()),
        "platform": kwargs.get("platform", "instagram"),
        "text": kwargs.get("text", ""),
        "kind": kwargs.get("kind", "unknown"),
    }
    if "meta" in kwargs:
        payload["meta"] = kwargs["meta"]
    return payload


def test_lang_fix_detects_mixed_language_and_preserves_hashtags():
    raw = _build_doc(
        id="mix1",
        text="Workout time ragazzi! #StayFit",
    )
    doc = CopycatAIPipeline()._ingest(raw)
    lang_fix(doc)
    assert doc.mixed_lang is True
    assert doc.lang == "it"
    assert "#StayFit" in doc.text_norm
    assert "allenamento" in doc.text_norm.lower()


def test_sponsored_detector_assigns_labels():
    raw = _build_doc(
        id="s1",
        text="In collaborazione con BrandX, usa il codice SCONTO10! #ad",
        meta={"paid_partnership": True},
    )
    doc = CopycatAIPipeline()._ingest(raw)
    result = sponsored_detector(doc)
    assert result.sponsored_label == "sponsored"
    assert result.sponsored_score >= 0.75
    assert result.kind == "sponsored"


def test_evolution_tracker_high_flag_on_topic_shift():
    now = datetime.now()
    past_docs = [
        Document(
            id=f"old{i}",
            url="https://example.com",
            ts=now - timedelta(days=200 + i),
            platform="instagram",
            text="Parlo di allenamento ogni giorno",
            kind="organic",
            cluster_id=1,
        )
        for i in range(3)
    ]
    recent_docs = [
        Document(
            id=f"new{i}",
            url="https://example.com",
            ts=now - timedelta(days=10 - i),
            platform="instagram",
            text="Nuovo tema sulla nutrizione completa",
            kind="organic",
            cluster_id=2,
        )
        for i in range(3)
    ]
    result = evolution_tracker(past_docs + recent_docs)
    assert result.evolution_flag == "high"
    assert result.evolution_score >= 0.65


def test_pipeline_run_produces_profile_and_blueprint():
    now = datetime.now()
    docs = []
    for i in range(6):
        docs.append(
            {
                "id": f"ig_{i}",
                "url": "https://instagram.com/p/abc",
                "ts": (now - timedelta(days=30 - i)).isoformat(),
                "platform": "instagram",
                "text": "Credo nel workout HIIT, ragazzi!",  # triggers claim
            }
        )
    for i in range(5):
        docs.append(
            {
                "id": f"yt_{i}",
                "url": "https://youtube.com/watch?v=xyz",
                "ts": (now - timedelta(days=i)).isoformat(),
                "platform": "youtube",
                "text": "Consiglio una dieta bilanciata con esempi pratici.",
            }
        )

    pipeline = CopycatAIPipeline()
    result = pipeline.run(docs, influencer_handle="@tester")

    profile = result.persona_profile
    assert profile.influencer["handle"] == "@tester"
    assert profile.data_quality["docs_total"] == len(docs)
    assert profile.topics_distribution
    assert result.content_blueprint["pillars"]
    assert result.annotated_documents

