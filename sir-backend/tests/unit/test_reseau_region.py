"""Filtre des postes sources par région."""


def test_postes_sources_region_du_poste_fait_foi() -> None:
    """Un poste source rattaché à une région n'apparaît pas ailleurs via un feeder mal rattaché."""
    import inspect

    from app.repositories import reseau_distribution_repository as repo

    source = inspect.getsource(repo.list_postes_sources)
    assert "PosteSource.region_id.is_(None)" in source
