// Icônes Material Symbols écrites dans le code (mots du code qui sont des noms d'icônes).
// Liste large par construction : un mot du code qui est aussi un nom d'icône est gardé.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

export function iconesUtilisees(racine = 'src/app') {
  const noms = new Set(
    [...readFileSync('node_modules/material-symbols/index.d.ts', 'utf8').matchAll(/"([a-z0-9_]+)"/g)].map((m) => m[1]),
  );
  const mots = new Set();
  const parcourir = (dossier) => {
    for (const nom of readdirSync(dossier)) {
      const chemin = join(dossier, nom);
      if (statSync(chemin).isDirectory()) parcourir(chemin);
      else if (/\.(ts|html)$/.test(nom)) {
        for (const m of readFileSync(chemin, 'utf8').matchAll(/\b[a-z0-9][a-z0-9_]{1,40}\b/g)) mots.add(m[0]);
      }
    }
  };
  parcourir(racine);
  return [...mots].filter((m) => noms.has(m)).sort();
}
