// Vérifie que la police d'icônes réduite (src/assets/fonts/sir-icones.woff2) contient toutes les
// icônes du code. Échec → relancer : python scripts/generer-icones.py (voir ce fichier).
import { readFileSync } from 'node:fs';
import { iconesUtilisees } from './icones-utilisees.mjs';

const presentes = new Set(readFileSync('src/assets/fonts/sir-icones.txt', 'utf8').split(/\s+/).filter(Boolean));
const manquantes = iconesUtilisees().filter((n) => !presentes.has(n));
if (manquantes.length) {
  console.error(`Icônes absentes de la police réduite : ${manquantes.join(', ')}`);
  console.error('Régénérer : python scripts/generer-icones.py');
  process.exit(1);
}
console.log(`Police d'icônes à jour (${presentes.size} icônes).`);
