# SMS — reprise du processus SIR v1

Comparaison entre l'ancien SIR (WebDev : `PAGE_sms`, procédure `EnvoiSMS`, tables HFSQL) et SIRV2.

## Données

| SIR v1 | SIRV2 | Reprise |
|---|---|---|
| `GroupeEnvoi` (Groupe, exploitation) | `groupes_envoi` (libelle, exploitation BCC/BRC/DISPATCHING, is_active) | `import_repertoire_sms.py` |
| `Destinataire` (prénomnom, Telephone, Fonctiondes, Matricule, Service, Groupe) — une ligne par groupe | `destinataires` (nom, telephone, fonction, matricule) + `destinataire_groupes` (plusieurs groupes par personne) | idem, doublons de numéro fusionnés |
| `Repertoire` (annuaire : Matricule, Prénom, Nom, fonctionagent, Telephone, Service, Direction) | `destinataires` sans groupe | option `--repertoire` |
| `smsenvoye` (NInterruption, dateEnvoi, exploitation, Login, Telephone, destinataire, messageenvoye, Status_Code, Status_Text, messageID) | `sms_envoyes` (entity_type/entity_id, created_at/sent_at, envoye_par_id, destinataire_id, contenu, code_retour, erreur, message_id) | historique non repris |
| `CopieSMS`, `Sousgroupe`, `GROUPESTRAVAIL` | — | usage à confirmer |

## Écran d'envoi

| SIR v1 (`PAGE_sms`) | SIRV2 (Notifications › Envoyer SMS) |
|---|---|
| Cases « Groupe » + bouton « Sélection » : la liste montre les membres des groupes cochés | Pastilles de groupes (plusieurs à la fois) : la liste montre leurs membres |
| « Sélection TOUS » / « Désélection TOUS » | « Tout cocher » / « Tout décocher » sur la liste affichée |
| Nombre de destinataires | Compteur « Destinataires (n) » |
| ENVOYER : `sendOneSMS` par ligne, compteurs envoyés / non envoyés | File d'envoi Celery, `sendOneSignedSMS` (signature `SMS_GATEWAY_SIGNATURE`) ; statut par SMS dans « SMS envoyés » |
| Un numéro présent dans deux groupes cochés reçoit deux SMS | Un seul SMS par numéro |
| Message suffixé « ( from <exploitation> ) » | Non repris (à confirmer) |
| Bouton « Test SMS » | `python -m scripts.test_sms <numéro>` (à confirmer si un bouton est utile) |

## Gestion

Notifications › Destinataires : groupes à gauche (créer, renommer, exploitation, désactiver / réactiver),
destinataires du groupe à droite (recherche, fiche avec fonction, matricule, groupes).

Les destinataires repris n'ont pas de service : ils ne reçoivent que les envois manuels. Un destinataire
rattaché à un service reçoit aussi les SMS automatiques des interruptions de ce service.
