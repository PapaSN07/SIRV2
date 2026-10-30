# Raccourci docker compose du poste SENELEC (base srv-bddomtech/SIRV2, BI_ODS, passerelle SMS).
# Usage : .\dcs up -d api worker | .\dcs restart worker | .\dcs logs -f worker
docker compose --env-file .env.docker-senelec -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.senelec.yml @args
