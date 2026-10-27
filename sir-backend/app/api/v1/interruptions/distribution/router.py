from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.fis_import import FisImportResponse, FisImportStatsResponse
from app.schemas.interruption_statut import (
    ArchivageRequest,
    ArchivageResponse,
    MotifRequest,
    StatutHistoriqueResponse,
    ValidationLotRequest,
    ValidationLotResponse,
)
from app.schemas.interruption_distribution import (
    InterruptionDistributionCreate,
    InterruptionClotureRequest,
    InterruptionDistributionDetailResponse,
    InterruptionDistributionResponse,
    InterruptionDistributionStatsResponse,
    InterruptionDistributionUpdate,
    OuvertureInterruption,
    PosteImpacteBulkResponse,
    PosteImpacteFromSigRequest,
    PosteImpacteResponse,
    PosteInterruptionCreate,
    StatutInterruption,
)
from app.schemas.interruption_workflow import (
    InterruptionWorkflowResponse,
    WorkflowEtapeUpdate,
)
from app.services import fis_import_service
from app.services import interruption_distribution_service
from app.services import interruption_workflow_service

router = APIRouter()

# Un fichier FIS mensuel réel pèse moins de 2 Mo ; au-delà de 10 Mo on refuse.
_FIS_MAX_BYTES = 10 * 1024 * 1024
_FIS_EXTENSIONS = (".xlsx", ".xlsm")


def _fis_error(code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=code,
        detail={"status": "error", "data": None, "error": message},
    )


@router.post(
    "/valider-lot",
    response_model=ApiResponse[ValidationLotResponse],
    status_code=status.HTTP_200_OK,
    summary="Valider plusieurs interruptions clôturées (résultat ligne par ligne)",
)
async def valider_lot_distribution(
    body: ValidationLotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "validate")
    ),
) -> ApiResponse[ValidationLotResponse]:
    result = await interruption_distribution_service.valider_lot(db, body, current_user)
    return ApiResponse.success(result)


@router.post(
    "/archiver",
    response_model=ApiResponse[ArchivageResponse],
    status_code=status.HTTP_200_OK,
    summary="Archiver (geler) les interruptions validées d'un mois, après le rapport CRSE",
)
async def archiver_mois_distribution(
    body: ArchivageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "validate")
    ),
) -> ApiResponse[ArchivageResponse]:
    result = await interruption_distribution_service.archiver_mois(db, body, current_user)
    return ApiResponse.success(result)


@router.post(
    "/import-fis",
    response_model=ApiResponse[FisImportResponse],
    status_code=status.HTTP_200_OK,
    summary="Importer un fichier FIS (BCC ou BRC) — création groupée d'interruptions",
)
async def import_fis(
    file: UploadFile = File(..., description="Fichier Excel FIS (.xlsx)"),
    skip_existing: bool = Query(
        True,
        description="Ignorer les numéros d'interruption déjà présents en base",
    ),
    simulation: bool = Query(
        False,
        description="Contrôler le fichier sans rien enregistrer (aperçu avant import)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "create")
    ),
) -> ApiResponse[FisImportResponse]:
    """Importe un fichier FIS Excel (BCC ou BRC) et crée les interruptions
    distribution correspondantes.

    - Lignes hors du périmètre de l'utilisateur : rejetées (comptées en erreur)
    - Statut «valide» si l'utilisateur peut valider, sinon «cloture» (file de validation)

    - Lit la feuille «Détails interruptions»
    - Crée les référentiels manquants (Nature, Cause, Siège) à la volée
    - Convertit END kWh → MWh, Puissance kW → MW
    - Ignore les doublons si `skip_existing=true`

    Permissions requises : `interruptions_distribution:create`
    (rôles : BCC, ADMIN_SCR, ADMIN_SAQS)
    """
    if not (file.filename or "").lower().endswith(_FIS_EXTENSIONS):
        raise _fis_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Fichier FIS attendu au format .xlsx"
        )
    content = await file.read(_FIS_MAX_BYTES + 1)
    if len(content) > _FIS_MAX_BYTES:
        raise _fis_error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichier FIS trop volumineux (10 Mo max)"
        )
    result = await fis_import_service.import_fis_file(
        db,
        content,
        current_user=current_user,
        skip_existing=skip_existing,
    )
    if simulation:
        await db.rollback()  # aperçu : mêmes contrôles, rien n'est conservé
    else:
        await db.commit()

    response = FisImportResponse(
        simulation=simulation,
        stats=FisImportStatsResponse(
            total_lignes=result.stats.total_lignes,
            importees=result.stats.importees,
            doublons_ignores=result.stats.doublons_ignores,
            erreurs=result.stats.erreurs,
            end_total_kwh=result.stats.end_total_kwh,
            end_total_mwh=result.stats.end_total_kwh / 1000.0,
        ),
        periode_debut=result.periode_debut,
        periode_fin=result.periode_fin,
        services_touches=result.services_touches,
        erreurs_detail=result.stats.erreurs_detail[:50],
    )
    return ApiResponse.success(response)


@router.get(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Exporter la liste filtrée (Excel ou PDF, 5 000 lignes max.)",
    response_class=Response,
)
async def export_interruptions_distribution(
    format: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    region_id: int | None = Query(default=None, ge=1),
    service_id: int | None = Query(default=None, ge=1),
    feeder_id: int | None = Query(default=None, ge=1),
    nature_id: int | None = Query(default=None, ge=1),
    ouverture: OuvertureInterruption | None = Query(default=None),
    statut: StatutInterruption | None = Query(default=None),
    date_debut: datetime | None = Query(default=None),
    date_fin: datetime | None = Query(default=None),
    libelle: str = Query("Tous filtres", max_length=300, description="Filtres lisibles, repris en tête du fichier"),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> Response:
    contenu, media_type, nom = await interruption_distribution_service.exporter_liste(
        db,
        current_user,
        format=format,
        filtres_libelle=libelle,
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        ouverture=ouverture,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return Response(
        content=contenu,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[InterruptionDistributionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste paginée des interruptions distribution",
)
async def list_interruptions_distribution(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    region_id: int | None = Query(default=None, ge=1),
    service_id: int | None = Query(default=None, ge=1),
    feeder_id: int | None = Query(default=None, ge=1),
    nature_id: int | None = Query(default=None, ge=1),
    ouverture: OuvertureInterruption | None = Query(default=None),
    statut: StatutInterruption | None = Query(default=None),
    date_debut: datetime | None = Query(default=None),
    date_fin: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[PaginatedResponse[InterruptionDistributionResponse]]:
    result = await interruption_distribution_service.list_items(
        db,
        current_user,
        page=page,
        page_size=page_size,
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        ouverture=ouverture,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return ApiResponse.success(result)


@router.get(
    "/stats",
    response_model=ApiResponse[InterruptionDistributionStatsResponse],
    status_code=status.HTTP_200_OK,
    summary="Compteurs interruptions distribution (périmètre RBAC)",
)
async def stats_interruptions_distribution(
    region_id: int | None = Query(default=None, ge=1),
    service_id: int | None = Query(default=None, ge=1),
    feeder_id: int | None = Query(default=None, ge=1),
    nature_id: int | None = Query(default=None, ge=1),
    ouverture: OuvertureInterruption | None = Query(default=None),
    statut: StatutInterruption | None = Query(default=None),
    date_debut: datetime | None = Query(default=None),
    date_fin: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[InterruptionDistributionStatsResponse]:
    result = await interruption_distribution_service.get_stats(
        db,
        current_user,
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        ouverture=ouverture,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return ApiResponse.success(result)


@router.post(
    "",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer une interruption distribution",
)
async def create_interruption_distribution(
    body: InterruptionDistributionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "create")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.create(db, body, current_user)
    return ApiResponse.success(result)


@router.get(
    "/{interruption_id}/postes",
    response_model=ApiResponse[list[PosteImpacteResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste des postes impactés par une interruption",
)
async def list_postes_interruption(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[list[PosteImpacteResponse]]:
    result = await interruption_distribution_service.list_postes(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.post(
    "/{interruption_id}/postes",
    response_model=ApiResponse[PosteImpacteResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Associer un poste impacté à une interruption",
)
async def add_poste_interruption(
    interruption_id: int,
    body: PosteInterruptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[PosteImpacteResponse]:
    result = await interruption_distribution_service.add_poste(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.post(
    "/{interruption_id}/postes/from-feeder",
    response_model=ApiResponse[PosteImpacteBulkResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Associer tous les postes actifs du feeder",
)
async def add_postes_from_feeder(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[PosteImpacteBulkResponse]:
    result = await interruption_distribution_service.add_postes_from_feeder(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.post(
    "/{interruption_id}/postes/from-sig-troncon",
    response_model=ApiResponse[PosteImpacteBulkResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Associer les postes liés au tronçon SIG du workflow",
)
async def add_postes_from_sig_troncon(
    interruption_id: int,
    body: PosteImpacteFromSigRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[PosteImpacteBulkResponse]:
    result = await interruption_distribution_service.add_postes_from_sig_troncon(
        db,
        interruption_id,
        body or PosteImpacteFromSigRequest(),
        current_user,
    )
    return ApiResponse.success(result)


@router.delete(
    "/{interruption_id}/postes/{poste_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un poste impacté d'une interruption",
)
async def remove_poste_interruption(
    interruption_id: int,
    poste_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> Response:
    await interruption_distribution_service.remove_poste(
        db, interruption_id, poste_id, current_user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{interruption_id}/workflow",
    response_model=ApiResponse[InterruptionWorkflowResponse],
    status_code=status.HTTP_200_OK,
    summary="Workflow opérationnel d'une interruption distribution",
)
async def get_interruption_workflow(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[InterruptionWorkflowResponse]:
    result = await interruption_workflow_service.get_workflow(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.put(
    "/{interruption_id}/workflow/etapes/{etape_id}",
    response_model=ApiResponse[InterruptionWorkflowResponse],
    status_code=status.HTTP_200_OK,
    summary="Saisir une étape du workflow (déverrouillée par la date de fin de l'étape précédente)",
)
async def update_interruption_workflow_etape(
    interruption_id: int,
    etape_id: int,
    body: WorkflowEtapeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[InterruptionWorkflowResponse]:
    result = await interruption_workflow_service.update_etape(
        db, interruption_id, etape_id, body, current_user
    )
    return ApiResponse.success(result)


@router.put(
    "/{interruption_id}",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Modifier une interruption distribution",
)
async def update_interruption_distribution(
    interruption_id: int,
    body: InterruptionDistributionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.update(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/cloturer",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Clôturer une interruption distribution",
)
async def cloturer_interruption_distribution(
    interruption_id: int,
    body: InterruptionClotureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.cloturer(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.get(
    "/{interruption_id}/historique-statuts",
    response_model=ApiResponse[list[StatutHistoriqueResponse]],
    status_code=status.HTTP_200_OK,
    summary="Historique des statuts (saisie, clôture, validation, renvois…)",
)
async def historique_statuts_distribution(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> ApiResponse[list[StatutHistoriqueResponse]]:
    result = await interruption_distribution_service.historique_statuts(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/renvoyer",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Renvoyer en correction une interruption clôturée (Admin SCR, motif obligatoire)",
)
async def renvoyer_interruption_distribution(
    interruption_id: int,
    body: MotifRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "validate")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.renvoyer_en_correction(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/devalider",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Dévalider une interruption validée (Admin SCR, motif obligatoire)",
)
async def devalider_interruption_distribution(
    interruption_id: int,
    body: MotifRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "validate")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.devalider(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/valider",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Valider une interruption distribution clôturée",
)
async def valider_interruption_distribution(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "validate")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.valider(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.get(
    "/{interruption_id}",
    response_model=ApiResponse[InterruptionDistributionDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Détail d'une interruption distribution",
)
async def get_interruption_distribution(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[InterruptionDistributionDetailResponse]:
    result = await interruption_distribution_service.get_item(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)
