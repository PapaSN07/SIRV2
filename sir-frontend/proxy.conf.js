// Proxy du serveur de développement Angular vers l'API FastAPI.
// - Docker Compose : API_PROXY_TARGET=http://api:8000 (nom du service, défini dans les fichiers compose)
// - ng serve lancé directement sur le poste : API locale ou conteneur publié sur le port 8000
const target = process.env.API_PROXY_TARGET || 'http://localhost:8000';

module.exports = {
  '/api': {
    target,
    secure: false,
    changeOrigin: true,
  },
};
