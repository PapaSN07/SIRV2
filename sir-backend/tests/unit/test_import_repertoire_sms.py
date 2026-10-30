"""Reprise du répertoire SMS SIR v1 : dédoublonnage par numéro, groupes, colonnes accentuées."""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2].parent
if str(_REPO) in sys.path:
    sys.path.remove(str(_REPO))
sys.path.insert(0, str(_REPO))
# sir-backend/scripts porte le même nom de paquet : forcer celui de la racine du dépôt
if "scripts" in sys.modules and not hasattr(sys.modules["scripts"], "migration"):
    for nom in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[nom]

from scripts.migration.import_repertoire_sms import champ, construire, normaliser_numero  # noqa: E402


def test_champ_accents_et_casse() -> None:
    assert champ({"PRÉNOMNOM": "  Awa   DIOP "}, "prénomnom") == "Awa DIOP"
    assert champ({"prenomnom": "Awa"}, "prénomnom") == "Awa"
    assert champ({"Telephone": None}, "Telephone") == ""


def test_construire_dedoublonne_et_rattache_les_groupes() -> None:
    groupes = [{"Groupe": "DR DAKAR"}, {"Groupe": "DIRECTION"}]
    destinataires = [
        {"prénomnom": "Awa DIOP", "Telephone": "77 740 82 54", "Fonctiondes": "Chef BCC", "Groupe": "DR DAKAR"},
        {"prénomnom": "Awa DIOP bis", "Telephone": "+221777408254", "Fonctiondes": "", "Groupe": "DIRECTION"},
        {"prénomnom": "Sans numéro", "Telephone": "", "Groupe": "DR DAKAR"},
        {"prénomnom": "Moussa FALL", "Telephone": "781451126", "Groupe": "NOUVEAU"},
    ]
    repertoire = [
        {"Prénom": "Awa", "Nom": "DIOP", "Telephone": "777408254", "fonctionagent": "Ingénieur"},
        {"Prénom": "Ibou", "Nom": "NDIAYE", "Telephone": "00221 76 000 00 01", "fonctionagent": "Technicien"},
    ]
    liste_groupes, contacts, rejets = construire(groupes, destinataires, repertoire)

    assert liste_groupes == ["DIRECTION", "DR DAKAR", "NOUVEAU"]
    assert set(contacts) == {"777408254", "781451126", "760000001"}
    awa = contacts["777408254"]
    assert (awa.nom, awa.fonction, awa.groupe) == ("Awa DIOP", "Chef BCC", "DR DAKAR")
    assert contacts["760000001"].nom == "Ibou NDIAYE" and contacts["760000001"].groupe == ""
    assert rejets["destinataire sans numéro valide"] == 1
    assert rejets["destinataire en double (même numéro)"] == 1


def test_normaliser_numero_identique_a_l_envoi() -> None:
    from app.services.sms_gateway import normaliser_numero as envoi

    for n in ("+221 77 740 82 54", "00221777408254", "77-740-82-54", "221777408254"):
        assert normaliser_numero(n) == envoi(n)
