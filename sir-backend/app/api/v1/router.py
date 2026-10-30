from fastapi import APIRouter

from app.api.v1.auth.router import router as auth_router
from app.api.v1.admin.router import router as admin_router
from app.api.v1.geo.router import router as geo_router
from app.api.v1.referentiel.router import router as referentiel_router
from app.api.v1.reseau.router import router as reseau_router
from app.api.v1.interruptions.distribution.router import router as distrib_router
from app.api.v1.interruptions.transport.router import router as transport_router
from app.api.v1.indicateurs.router import router as indicateurs_router
from app.api.v1.rapports.router import router as rapports_router
from app.api.v1.napt.router import router as napt_router
from app.api.v1.notifications.router import router as notifications_router
from app.api.v1.assistant.router import router as assistant_router
from app.api.v1.clients.router import router as clients_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(geo_router, prefix="/geo", tags=["geo"])
api_router.include_router(referentiel_router, prefix="/referentiel", tags=["referentiel"])
api_router.include_router(reseau_router, prefix="/reseau", tags=["reseau"])
api_router.include_router(distrib_router, prefix="/interruptions/distribution", tags=["interruptions-distribution"])
api_router.include_router(transport_router, prefix="/interruptions/transport", tags=["interruptions-transport"])
api_router.include_router(indicateurs_router, prefix="/indicateurs", tags=["indicateurs"])
api_router.include_router(rapports_router, prefix="/rapports", tags=["rapports"])
api_router.include_router(napt_router, prefix="/napt", tags=["napt"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(assistant_router, prefix="/assistant", tags=["assistant"])
api_router.include_router(clients_router, prefix="/clients", tags=["base-clients"])
