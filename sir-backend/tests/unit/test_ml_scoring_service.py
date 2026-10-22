"""Tests unitaires — scoring P0 Assistant ML."""

from app.services.ml_scoring_service import compute_p0_score


def test_compute_p0_score_low_when_no_incidents() -> None:
    score, factors, reco = compute_p0_score(
        {
            "nb_interruptions": 0,
            "nb_permanentes": 0,
            "duree_moyenne_minutes": 0,
            "clients_touches_total": 0,
        },
        horizon_days=90,
    )
    assert score == 0
    assert len(factors) == 4
    assert "faible" in reco.lower() or "suivre" in reco.lower()


def test_compute_p0_score_high_with_many_permanents() -> None:
    score, factors, reco = compute_p0_score(
        {
            "nb_interruptions": 20,
            "nb_permanentes": 12,
            "duree_moyenne_minutes": 240,
            "clients_touches_total": 8000,
        },
        horizon_days=90,
    )
    assert score >= 55
    assert any(f["code"] == "frequence" for f in factors)
    assert "préventif" in reco.lower() or "inspection" in reco.lower()
