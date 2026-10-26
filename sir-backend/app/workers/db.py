"""Sessions base de données des tâches Celery.

Chaque tâche lance ``asyncio.run()`` : une nouvelle boucle d'événements par
exécution. Le pool de connexions de l'API (``app.core.database``) garde des
connexions liées à la boucle qui les a ouvertes ; les réutiliser depuis une
autre boucle provoque « Future attached to a different loop » ou des
connexions mortes, de façon aléatoire selon la tâche qui récupère la connexion.

Ici ``NullPool`` : chaque session ouvre sa connexion et la ferme en sortant,
dans la boucle de la tâche. Coût négligeable face à la durée d'un calcul
SAIFI/SAIDI ou d'une génération de rapport.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

worker_engine = create_async_engine(settings.database_url, poolclass=NullPool)

WorkerSessionLocal = async_sessionmaker(
    worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
