-- Script généré par WEBDEV le 12/06/2026 11:26:20
-- Tables de l'analyse SIR.wda
-- pour SQL Server

-- Création de la table Agences
CREATE TABLE [Agences] (
    [Codeagence] INTEGER  NOT NULL  UNIQUE  DEFAULT 0,
    [Agence] VARCHAR(50)  UNIQUE ,
    [Adresse] VARCHAR(50) ,
    [Region] VARCHAR(50) ,
    [IDAgence] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_Agences_Region] ON [Agences] ([Region]);
CREATE INDEX [WDIDX_Agences_IDDelegation] ON [Agences] ([IDDelegation]);

-- Création de la table Agences_Postes
CREATE TABLE [Agences_Postes] (
    [IDPostes] NUMERIC(19,0)  NOT NULL ,
    [IDAgence] NUMERIC(19,0)  NOT NULL );
CREATE INDEX [WDIDX_Agences_Postes_IDPostes] ON [Agences_Postes] ([IDPostes]);
CREATE INDEX [WDIDX_Agences_Postes_IDAgence] ON [Agences_Postes] ([IDAgence]);
CREATE UNIQUE INDEX [WDIDX_Agences_Postes_IDAgence_IDPostes] ON [Agences_Postes] ([IDAgence],[IDPostes]);

-- Création de la table BoiteEnvoi
CREATE TABLE [BoiteEnvoi] (
    [IDBoiteEnvoi] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [EMAIL] VARCHAR(50) ,
    [date] DATETIME ,
    [messageenvoye] TEXT ,
    [Matricule] INTEGER ,
    [Telephone] VARCHAR(50) );
CREATE INDEX [WDIDX_BoiteEnvoi_EMAIL] ON [BoiteEnvoi] ([EMAIL]);
CREATE INDEX [WDIDX_BoiteEnvoi_Matricule] ON [BoiteEnvoi] ([Matricule]);
CREATE INDEX [WDIDX_BoiteEnvoi_Telephone] ON [BoiteEnvoi] ([Telephone]);

-- Création de la table Causes
CREATE TABLE [Causes] (
    [IDCauses] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [cause] VARCHAR(255)  UNIQUE ,
    [Coupure] BIT DEFAULT 0,
    [Délestage] BIT DEFAULT 0,
    [Fugitif] BIT DEFAULT 0,
    [Permanent] BIT DEFAULT 0,
    [Semi_permanent] BIT DEFAULT 0,
    [definition] TEXT ,
    [Remarque] TEXT ,
    [Dispatching] BIT DEFAULT 0,
    [CauseReseauHTB] BIT DEFAULT 0,
    [FacteursExogenes] BIT DEFAULT 0,
    [Projet] BIT DEFAULT 0);
CREATE INDEX [WDIDX_Causes_Coupure] ON [Causes] ([Coupure]);
CREATE INDEX [WDIDX_Causes_Délestage] ON [Causes] ([Délestage]);
CREATE INDEX [WDIDX_Causes_Fugitif] ON [Causes] ([Fugitif]);
CREATE INDEX [WDIDX_Causes_Permanent] ON [Causes] ([Permanent]);
CREATE INDEX [WDIDX_Causes_Semi_permanent] ON [Causes] ([Semi_permanent]);
CREATE INDEX [WDIDX_Causes_Dispatching] ON [Causes] ([Dispatching]);
CREATE INDEX [WDIDX_Causes_CauseReseauHTB] ON [Causes] ([CauseReseauHTB]);
CREATE INDEX [WDIDX_Causes_FacteursExogenes] ON [Causes] ([FacteursExogenes]);
CREATE INDEX [WDIDX_Causes_Projet] ON [Causes] ([Projet]);

-- Création de la table CausesTransport
CREATE TABLE [CausesTransport] (
    [IDCausesTrans] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [cause] VARCHAR(255)  UNIQUE ,
    [Coupure] BIT DEFAULT 0,
    [Délestage] BIT DEFAULT 0,
    [Fugitif] BIT DEFAULT 0,
    [Permanent] BIT DEFAULT 0,
    [Semi_permanent] BIT DEFAULT 0,
    [definition] TEXT ,
    [Remarque] TEXT ,
    [Dispatching] BIT DEFAULT 0,
    [effacement] BIT DEFAULT 0,
    [NePasPrendreCpteInter] BIT DEFAULT 0);
CREATE INDEX [WDIDX_CausesTransport_Coupure] ON [CausesTransport] ([Coupure]);
CREATE INDEX [WDIDX_CausesTransport_Délestage] ON [CausesTransport] ([Délestage]);
CREATE INDEX [WDIDX_CausesTransport_Fugitif] ON [CausesTransport] ([Fugitif]);
CREATE INDEX [WDIDX_CausesTransport_Permanent] ON [CausesTransport] ([Permanent]);
CREATE INDEX [WDIDX_CausesTransport_Semi_permanent] ON [CausesTransport] ([Semi_permanent]);
CREATE INDEX [WDIDX_CausesTransport_Dispatching] ON [CausesTransport] ([Dispatching]);
CREATE INDEX [WDIDX_CausesTransport_effacement] ON [CausesTransport] ([effacement]);
CREATE INDEX [WDIDX_CausesTransport_NePasPrendreCpteInter] ON [CausesTransport] ([NePasPrendreCpteInter]);

-- Création de la table Centrale
CREATE TABLE [dbo.Centrale] (
    [IDCentrale] NUMERIC(19,0)  NOT NULL  UNIQUE  DEFAULT 0,
    [NomCentrale] VARCHAR(50) DEFAULT NULL,
    [IDTypeCentrale] NUMERIC(19,0) DEFAULT NULL,
    [IDCentraleMere] NUMERIC(19,0) DEFAULT NULL,
    [SenelecFournitCombLub] BIT DEFAULT NULL,
    [CentraleDeclassee] BIT DEFAULT NULL,
    [IDTypeReseauProducteur] NUMERIC(19,0) DEFAULT NULL,
    [IDLieu] NUMERIC(19,0) DEFAULT NULL,
    [IDParc] NUMERIC(19,0) DEFAULT NULL,
    [IDTypeCentraleIPP] NUMERIC(19,0) DEFAULT NULL);

-- Création de la table Charge_Consignation
CREATE TABLE [Charge_Consignation] (
    [IDCharge_Consignation] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Unite] VARCHAR(50) ,
    [Prenom_Nom] VARCHAR(255) ,
    [Adresse] NVARCHAR(255) ,
    [fonction_Charge] VARCHAR(50) );

-- Création de la table ChargerTravaux
CREATE TABLE [ChargerTravaux] (
    [IDChargerTravaux] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [prenom_charge_travaux] VARCHAR(50)  NOT NULL  UNIQUE ,
    [fonction_chargertravaux] VARCHAR(50) ,
    [adressechargetravaux] VARCHAR(50) ,
    [Telephone] VARCHAR(50) ,
    [Email] VARCHAR(50) );

-- Création de la table ClassementEND
CREATE TABLE [ClassementEND] (
    [IDClassementEND] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Type_END] VARCHAR(50) ,
    [Nature] VARCHAR(50) ,
    [Code_Cause] VARCHAR(50) ,
    [Service] VARCHAR(255) ,
    [Cause] VARCHAR(255) ,
    [Descript_cause] TEXT ,
    [IDCausesTrans] NUMERIC(19,0) ,
    [IDCauses] NUMERIC(19,0) ,
    [IDNature] NUMERIC(19,0) );
CREATE INDEX [WDIDX_ClassementEND_Type_END] ON [ClassementEND] ([Type_END]);
CREATE INDEX [WDIDX_ClassementEND_Nature] ON [ClassementEND] ([Nature]);
CREATE INDEX [WDIDX_ClassementEND_Code_Cause] ON [ClassementEND] ([Code_Cause]);
CREATE INDEX [WDIDX_ClassementEND_Service] ON [ClassementEND] ([Service]);
CREATE INDEX [WDIDX_ClassementEND_Cause] ON [ClassementEND] ([Cause]);
CREATE INDEX [WDIDX_ClassementEND_IDCausesTrans] ON [ClassementEND] ([IDCausesTrans]);
CREATE INDEX [WDIDX_ClassementEND_IDCauses] ON [ClassementEND] ([IDCauses]);
CREATE INDEX [WDIDX_ClassementEND_IDNature] ON [ClassementEND] ([IDNature]);

-- Création de la table Client_H2MC
CREATE TABLE [Client_H2MC] (
    [IDH2MC] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Numéro_Compteur] VARCHAR(255)  UNIQUE  DEFAULT '0',
    [UR] VARCHAR(50) ,
    [Type_Compteur] VARCHAR(50) ,
    [Nom_Client] VARCHAR(50) ,
    [Reference] VARCHAR(255) DEFAULT '0',
    [Adresse] VARCHAR(50) ,
    [Agence] VARCHAR(50) ,
    [Numero_Serie] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_Client_H2MC_UR] ON [Client_H2MC] ([UR]);
CREATE INDEX [WDIDX_Client_H2MC_Type_Compteur] ON [Client_H2MC] ([Type_Compteur]);
CREATE INDEX [WDIDX_Client_H2MC_Nom_Client] ON [Client_H2MC] ([Nom_Client]);
CREATE INDEX [WDIDX_Client_H2MC_Reference] ON [Client_H2MC] ([Reference]);
CREATE INDEX [WDIDX_Client_H2MC_Adresse] ON [Client_H2MC] ([Adresse]);
CREATE INDEX [WDIDX_Client_H2MC_Agence] ON [Client_H2MC] ([Agence]);
CREATE INDEX [WDIDX_Client_H2MC_Numero_Serie] ON [Client_H2MC] ([Numero_Serie]);

-- Création de la table consignation
CREATE TABLE [consignation] (
    [IDconsignation] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [source] VARCHAR(255) ,
    [Feeder] VARCHAR(255) ,
    [NoeudAmont] VARCHAR(255) ,
    [NoeudAval] VARCHAR(255) ,
    [TypeConsignation] BIT DEFAULT 0,
    [troncon] VARCHAR(500) ,
    [Observation] TEXT ,
    [Installation_a_consigner] VARCHAR(1000) ,
    [consistanceconsignation] VARCHAR(1000) ,
    [Num] NUMERIC(19,0) DEFAULT 0,
    [pointconsignation] VARCHAR(1000) );
CREATE INDEX [WDIDX_consignation_Feeder] ON [consignation] ([Feeder]);
CREATE INDEX [WDIDX_consignation_Observation] ON [consignation] ([Observation]);
CREATE INDEX [WDIDX_consignation_Num] ON [consignation] ([Num]);

-- Création de la table Controleur
CREATE TABLE [Controleur] (
    [IDControleur] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Prenom_Nom_controleur] VARCHAR(255)  NOT NULL  UNIQUE ,
    [Matricule] INTEGER DEFAULT 0,
    [Adresse] VARCHAR(50) ,
    [Telephone] VARCHAR(50) ,
    [Email] VARCHAR(50) ,
    [Login] VARCHAR(255) ,
    [motpasse] VARCHAR(50) ,
    [controleur] VARCHAR(255) );
CREATE INDEX [WDIDX_Controleur_Matricule] ON [Controleur] ([Matricule]);
CREATE INDEX [WDIDX_Controleur_Login] ON [Controleur] ([Login]);
CREATE INDEX [WDIDX_Controleur_controleur] ON [Controleur] ([controleur]);

-- Création de la table CopieSMS
CREATE TABLE [CopieSMS] (
    [IDCopieSMS] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [EMAIL] VARCHAR(50) ,
    [date] DATETIME ,
    [messageenvoye] TEXT ,
    [Matricule] INTEGER ,
    [Telephone] VARCHAR(50) );
CREATE INDEX [WDIDX_CopieSMS_EMAIL] ON [CopieSMS] ([EMAIL]);
CREATE INDEX [WDIDX_CopieSMS_Matricule] ON [CopieSMS] ([Matricule]);
CREATE INDEX [WDIDX_CopieSMS_Telephone] ON [CopieSMS] ([Telephone]);

-- Création de la table Delegation
CREATE TABLE [Delegation] (
    [IDDelegation] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [AbregeDelegation] VARCHAR(10) ,
    [LibelleDelegation] VARCHAR(50) ,
    [IDRegions] NUMERIC(19,0) DEFAULT 0,
    [CodeDelegation] INTEGER DEFAULT 0);
CREATE INDEX [WDIDX_Delegation_IDRegions] ON [Delegation] ([IDRegions]);
CREATE INDEX [WDIDX_Delegation_CodeDelegation] ON [Delegation] ([CodeDelegation]);

-- Création de la table Demandeurs
CREATE TABLE [Demandeurs] (
    [IDDemandeurs] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Prenom_nom_demandeur] VARCHAR(50)  NOT NULL  UNIQUE ,
    [Adresse] VARCHAR(50) ,
    [Telephone] VARCHAR(50) ,
    [Email] VARCHAR(50) ,
    [Entreprise] VARCHAR(50) DEFAULT 'Senelec',
    [Login] VARCHAR(255) ,
    [motpasse] VARCHAR(50) ,
    [Demandeur] VARCHAR(255) ,
    [Unite] VARCHAR(255) );
CREATE INDEX [WDIDX_Demandeurs_Login] ON [Demandeurs] ([Login]);
CREATE INDEX [WDIDX_Demandeurs_Demandeur] ON [Demandeurs] ([Demandeur]);
CREATE INDEX [WDIDX_Demandeurs_Unite] ON [Demandeurs] ([Unite]);

-- Création de la table Destinataire
CREATE TABLE [Destinataire] (
    [IDDestinataires] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Telephone] VARCHAR(50) ,
    [prénomnom] VARCHAR(500) ,
    [Matricule] VARCHAR(50) ,
    [Fonctiondes] VARCHAR(50) ,
    [exploitation] VARCHAR(50) ,
    [Service] VARCHAR(255) ,
    [Groupe] VARCHAR(255) );
CREATE INDEX [WDIDX_Destinataire_Telephone] ON [Destinataire] ([Telephone]);
CREATE INDEX [WDIDX_Destinataire_prénomnom] ON [Destinataire] ([prénomnom]);
CREATE INDEX [WDIDX_Destinataire_Matricule] ON [Destinataire] ([Matricule]);
CREATE INDEX [WDIDX_Destinataire_Fonctiondes] ON [Destinataire] ([Fonctiondes]);
CREATE INDEX [WDIDX_Destinataire_exploitation] ON [Destinataire] ([exploitation]);
CREATE INDEX [WDIDX_Destinataire_Service] ON [Destinataire] ([Service]);
CREATE INDEX [WDIDX_Destinataire_Groupe] ON [Destinataire] ([Groupe]);

-- Création de la table document
CREATE TABLE [document] (
    [IDdocument] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [nomdudocument] VARCHAR(500) ,
    [datecreation] DATETIME ,
    [chemin] VARCHAR(500) );
CREATE INDEX [WDIDX_document_nomdudocument] ON [document] ([nomdudocument]);

-- Création de la table EnergieND
CREATE TABLE [EnergieND] (
    [IDEnergieND] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Date] DATETIME ,
    [IDTypeEND] NUMERIC(19,0) ,
    [Directionimputable] VARCHAR(50) ,
    [TensionPrimaire] REAL DEFAULT 0,
    [ENDD] FLOAT ,
    [Duree] REAL DEFAULT 0,
    [Nombre] INTEGER DEFAULT 0,
    [Region] VARCHAR(50) ,
    [IDNature] NUMERIC(19,0) DEFAULT 0,
    [Nature] VARCHAR(50) ,
    [IDCausesTransport] INTEGER DEFAULT 0,
    [CauseTransport] VARCHAR(50) ,
    [IDCauseDistribution] INTEGER DEFAULT 0,
    [CauseDistribution] VARCHAR(50) ,
    [Service] VARCHAR(255) );
CREATE INDEX [WDIDX_EnergieND_Date] ON [EnergieND] ([Date]);
CREATE INDEX [WDIDX_EnergieND_IDTypeEND] ON [EnergieND] ([IDTypeEND]);
CREATE INDEX [WDIDX_EnergieND_Directionimputable] ON [EnergieND] ([Directionimputable]);
CREATE INDEX [WDIDX_EnergieND_TensionPrimaire] ON [EnergieND] ([TensionPrimaire]);
CREATE INDEX [WDIDX_EnergieND_ENDD] ON [EnergieND] ([ENDD]);
CREATE INDEX [WDIDX_EnergieND_Region] ON [EnergieND] ([Region]);
CREATE INDEX [WDIDX_EnergieND_IDNature] ON [EnergieND] ([IDNature]);
CREATE INDEX [WDIDX_EnergieND_Nature] ON [EnergieND] ([Nature]);
CREATE INDEX [WDIDX_EnergieND_Service] ON [EnergieND] ([Service]);
CREATE INDEX [WDIDX_EnergieND_DateIDTypeENDDirectionimputableTensionPrimaire] ON [EnergieND] ([Date],[IDTypeEND],[Directionimputable],[TensionPrimaire]);

-- Création de la table Entreprise
CREATE TABLE [Entreprise] (
    [IDEntreprise] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [NomEntreprise] VARCHAR(50) );
CREATE INDEX [WDIDX_Entreprise_NomEntreprise] ON [Entreprise] ([NomEntreprise]);

-- Création de la table EquipementsTransport
CREATE TABLE [EquipementsTransport] (
    [IDEquipements] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Tension] REAL DEFAULT 0,
    [nomequipement] VARCHAR(50) ,
    [IDSourceEquipement] NUMERIC(19,0) DEFAULT 0,
    [IDSieges] NUMERIC(19,0) DEFAULT 0,
    [Lieu] VARCHAR(50) ,
    [IDPropriétaire] INTEGER DEFAULT 0,
    [IDTypeEquipement] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_EquipementsTransport_Tension] ON [EquipementsTransport] ([Tension]);
CREATE INDEX [WDIDX_EquipementsTransport_nomequipement] ON [EquipementsTransport] ([nomequipement]);
CREATE INDEX [WDIDX_EquipementsTransport_IDSourceEquipement] ON [EquipementsTransport] ([IDSourceEquipement]);
CREATE INDEX [WDIDX_EquipementsTransport_IDSieges] ON [EquipementsTransport] ([IDSieges]);
CREATE INDEX [WDIDX_EquipementsTransport_Lieu] ON [EquipementsTransport] ([Lieu]);
CREATE INDEX [WDIDX_EquipementsTransport_IDPropriétaire] ON [EquipementsTransport] ([IDPropriétaire]);
CREATE INDEX [WDIDX_EquipementsTransport_IDTypeEquipement] ON [EquipementsTransport] ([IDTypeEquipement]);

-- Création de la table Exploitation
CREATE TABLE [Exploitation] (
    [IDExploitation] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [exploitation] VARCHAR(50)  NOT NULL  UNIQUE );

-- Création de la table Famille
CREATE TABLE [Famille] (
    [IDFamille] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL ,
    [NomFamille] VARCHAR(50) );

-- Création de la table Feeders
CREATE TABLE [Feeders] (
    [Feeder] VARCHAR(255)  NOT NULL  UNIQUE ,
    [PosteSOurce] VARCHAR(255) ,
    [TensionPrimaire] REAL DEFAULT 0,
    [Nature] VARCHAR(50) DEFAULT '0',
    [Activite] VARCHAR(1000) ,
    [Region] VARCHAR(50) ,
    [HorsDelestage] BIT DEFAULT 0,
    [PMin] REAL DEFAULT 0,
    [PMax] REAL DEFAULT 0,
    [PMoyenne] REAL DEFAULT 0,
    [Tranche] VARCHAR(50) ,
    [Courant_admissible] FLOAT DEFAULT 0,
    [NatureSectionDomi] VARCHAR(50) ,
    [observation] TEXT ,
    [PointOuvertureActuel] VARCHAR(50) ,
    [PointOuverturenormal] VARCHAR(50) ,
    [SectionDominanteactuel] VARCHAR(50) ,
    [SectionDominanteNormale] VARCHAR(50) ,
    [TypeProtection] VARCHAR(50) ,
    [CentreResponsabilite] INTEGER DEFAULT 0,
    [Service] VARCHAR(255) ,
    [IDFeeder] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDTypeEquipement] NUMERIC(19,0) DEFAULT 0,
    [exploitation] VARCHAR(50) ,
    [source] VARCHAR(255) ,
    [IDService] NUMERIC(19,0) ,
    [NomFeederSIG] VARCHAR(50) ,
    [NombreKm] INTEGER DEFAULT 0,
    [lignePrivée] BIT DEFAULT 0,
    [IDPropritetaire_Ligne] NUMERIC(19,0) ,
    [IDFEEDERS_SIG] INTEGER ,
    [IDPosteSource] NUMERIC(19,0) DEFAULT 0,
    [IMATFEEDER] VARCHAR(50) DEFAULT '0');
CREATE INDEX [WDIDX_Feeders_PosteSOurce] ON [Feeders] ([PosteSOurce]);
CREATE INDEX [WDIDX_Feeders_TensionPrimaire] ON [Feeders] ([TensionPrimaire]);
CREATE INDEX [WDIDX_Feeders_Nature] ON [Feeders] ([Nature]);
CREATE INDEX [WDIDX_Feeders_Activite] ON [Feeders] ([Activite]);
CREATE INDEX [WDIDX_Feeders_Region] ON [Feeders] ([Region]);
CREATE INDEX [WDIDX_Feeders_HorsDelestage] ON [Feeders] ([HorsDelestage]);
CREATE INDEX [WDIDX_Feeders_PMin] ON [Feeders] ([PMin]);
CREATE INDEX [WDIDX_Feeders_PMax] ON [Feeders] ([PMax]);
CREATE INDEX [WDIDX_Feeders_PMoyenne] ON [Feeders] ([PMoyenne]);
CREATE INDEX [WDIDX_Feeders_Tranche] ON [Feeders] ([Tranche]);
CREATE INDEX [WDIDX_Feeders_Courant_admissible] ON [Feeders] ([Courant_admissible]);
CREATE INDEX [WDIDX_Feeders_NatureSectionDomi] ON [Feeders] ([NatureSectionDomi]);
CREATE INDEX [WDIDX_Feeders_observation] ON [Feeders] ([observation]);
CREATE INDEX [WDIDX_Feeders_PointOuvertureActuel] ON [Feeders] ([PointOuvertureActuel]);
CREATE INDEX [WDIDX_Feeders_PointOuverturenormal] ON [Feeders] ([PointOuverturenormal]);
CREATE INDEX [WDIDX_Feeders_SectionDominanteactuel] ON [Feeders] ([SectionDominanteactuel]);
CREATE INDEX [WDIDX_Feeders_SectionDominanteNormale] ON [Feeders] ([SectionDominanteNormale]);
CREATE INDEX [WDIDX_Feeders_TypeProtection] ON [Feeders] ([TypeProtection]);
CREATE INDEX [WDIDX_Feeders_Service] ON [Feeders] ([Service]);
CREATE INDEX [WDIDX_Feeders_IDTypeEquipement] ON [Feeders] ([IDTypeEquipement]);
CREATE INDEX [WDIDX_Feeders_exploitation] ON [Feeders] ([exploitation]);
CREATE INDEX [WDIDX_Feeders_source] ON [Feeders] ([source]);
CREATE INDEX [WDIDX_Feeders_IDService] ON [Feeders] ([IDService]);
CREATE INDEX [WDIDX_Feeders_NomFeederSIG] ON [Feeders] ([NomFeederSIG]);
CREATE INDEX [WDIDX_Feeders_NombreKm] ON [Feeders] ([NombreKm]);
CREATE INDEX [WDIDX_Feeders_lignePrivée] ON [Feeders] ([lignePrivée]);
CREATE INDEX [WDIDX_Feeders_IDPropritetaire_Ligne] ON [Feeders] ([IDPropritetaire_Ligne]);
CREATE INDEX [WDIDX_Feeders_IDFEEDERS_SIG] ON [Feeders] ([IDFEEDERS_SIG]);
CREATE INDEX [WDIDX_Feeders_IDPosteSource] ON [Feeders] ([IDPosteSource]);
CREATE INDEX [WDIDX_Feeders_IMATFEEDER] ON [Feeders] ([IMATFEEDER]);
CREATE INDEX [WDIDX_Feeders_FeederSousStation] ON [Feeders] ([Feeder],[PosteSOurce]);

-- Création de la table FEEDERS_SIG
CREATE TABLE [FEEDERS_SIG] (
    [FID] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL ,
    [NOMFEEDER] VARCHAR(255) DEFAULT NULL,
    [IMATFEEDER] VARCHAR(255)  UNIQUE  DEFAULT NULL,
    [POSTESOURCE] VARCHAR(255) DEFAULT NULL,
    [CATEGORIES] VARCHAR(255) DEFAULT NULL,
    [IDPropritetaire_Ligne] NUMERIC(19,0) ,
    [Date_mise_en_service] DATETIME ,
    [Nombre_KM] INTEGER DEFAULT 0);
CREATE INDEX [WDIDX_FEEDERS_SIG_NOMFEEDER] ON [FEEDERS_SIG] ([NOMFEEDER]);
CREATE INDEX [WDIDX_FEEDERS_SIG_POSTESOURCE] ON [FEEDERS_SIG] ([POSTESOURCE]);
CREATE INDEX [WDIDX_FEEDERS_SIG_CATEGORIES] ON [FEEDERS_SIG] ([CATEGORIES]);
CREATE INDEX [WDIDX_FEEDERS_SIG_IDPropritetaire_Ligne] ON [FEEDERS_SIG] ([IDPropritetaire_Ligne]);
CREATE INDEX [WDIDX_FEEDERS_SIG_Date_mise_en_service] ON [FEEDERS_SIG] ([Date_mise_en_service]);
CREATE INDEX [WDIDX_FEEDERS_SIG_Nombre_KM] ON [FEEDERS_SIG] ([Nombre_KM]);

-- Création de la table FeuilleConduite
CREATE TABLE [FeuilleConduite] (
    [IDFeuilleConduite] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Observation] TEXT ,
    [Date] VARCHAR(50) ,
    [heure] VARCHAR(50) ,
    [Matricule] INTEGER DEFAULT 0,
    [destinataire] VARCHAR(50) ,
    [copie] VARCHAR(50) ,
    [dateEnvoi] DATETIME ,
    [typemessage] VARCHAR(50) );
CREATE INDEX [WDIDX_FeuilleConduite_Observation] ON [FeuilleConduite] ([Observation]);
CREATE INDEX [WDIDX_FeuilleConduite_Matricule] ON [FeuilleConduite] ([Matricule]);
CREATE INDEX [WDIDX_FeuilleConduite_destinataire] ON [FeuilleConduite] ([destinataire]);

-- Création de la table GroupeEnvoi
CREATE TABLE [GroupeEnvoi] (
    [IDGroupeEnvoi] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Groupe] VARCHAR(255)  NOT NULL  UNIQUE ,
    [exploitation] VARCHAR(50) );
CREATE INDEX [WDIDX_GroupeEnvoi_exploitation] ON [GroupeEnvoi] ([exploitation]);

-- Création de la table GROUPESTRAVAIL
CREATE TABLE [GROUPESTRAVAIL] (
    [Groupe] NVARCHAR(255) DEFAULT NULL,
    [Agence] NVARCHAR(255) DEFAULT NULL);
CREATE INDEX [WDIDX_GROUPESTRAVAIL_Groupe] ON [GROUPESTRAVAIL] ([Groupe]);
CREATE INDEX [WDIDX_GROUPESTRAVAIL_Agence] ON [GROUPESTRAVAIL] ([Agence]);

-- Création de la table H2MC
CREATE TABLE [H2MC] (
    [IDH2MC] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [EtablPssement] VARCHAR(50) ,
    [Agence] VARCHAR(50) ,
    [Groupe] VARCHAR(255) ,
    [bordereau] VARCHAR(50) ,
    [ParPté] VARCHAR(50) ,
    [LPB_QUARTPER_VPLLAGE_HAMEAU] VARCHAR(50) ,
    [COD_QUARTPER_VPLLAGE_HAMEAU] VARCHAR(50) ,
    [CACRV] VARCHAR(50) ,
    [UNPTE_TECHNPQUE] VARCHAR(50) ,
    [TYPE_AGENCE] VARCHAR(50) ,
    [PNDPCE_NSPC] VARCHAR(50) ,
    [UR] VARCHAR(50) );
CREATE INDEX [WDIDX_H2MC_Agence] ON [H2MC] ([Agence]);
CREATE INDEX [WDIDX_H2MC_Groupe] ON [H2MC] ([Groupe]);
CREATE INDEX [WDIDX_H2MC_bordereau] ON [H2MC] ([bordereau]);
CREATE INDEX [WDIDX_H2MC_UR] ON [H2MC] ([UR]);

-- Création de la table Histo_Troncons
CREATE TABLE [Histo_Troncons] (
    [IDHisto_Troncons] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [DatDebut] DATETIME ,
    [DateFin] DATETIME );
CREATE INDEX [WDIDX_Histo_Troncons_DatDebut] ON [Histo_Troncons] ([DatDebut]);
CREATE INDEX [WDIDX_Histo_Troncons_DateFin] ON [Histo_Troncons] ([DateFin]);

-- Création de la table Historique
CREATE TABLE [Historique] (
    [IDHistorique] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Login] VARCHAR(255) ,
    [Date] DATETIME ,
    [Region] VARCHAR(50) );
CREATE INDEX [WDIDX_Historique_Login] ON [Historique] ([Login]);
CREATE INDEX [WDIDX_Historique_Region] ON [Historique] ([Region]);

-- Création de la table IACM
CREATE TABLE [IACM] (
    [IDIACM] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IACM] VARCHAR(255)  UNIQUE );

-- Création de la table InterruptionGroupée
CREATE TABLE [InterruptionGroupée] (
    [IDInterruptionGroupée] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDEquipements] NUMERIC(19,0) DEFAULT 0,
    [NInterruption] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_InterruptionGroupée_IDEquipements] ON [InterruptionGroupée] ([IDEquipements]);
CREATE INDEX [WDIDX_InterruptionGroupée_NInterruption] ON [InterruptionGroupée] ([NInterruption]);
CREATE UNIQUE INDEX [WDIDX_InterruptionGroupée_IDEquipementsNInterruption] ON [InterruptionGroupée] ([IDEquipements],[NInterruption]);

-- Création de la table Interruptions
CREATE TABLE [Interruptions] (
    [IDTronçons] NUMERIC(19,0) DEFAULT 0,
    [IDTypePermanent] NUMERIC(19,0) DEFAULT 0,
    [IDSieges] NUMERIC(19,0) DEFAULT 0,
    [IDCauses] NUMERIC(19,0) DEFAULT 0,
    [IDSignalisation] NUMERIC(19,0) DEFAULT 0,
    [Num] NUMERIC(19,0) DEFAULT 0,
    [IDNature] NUMERIC(19,0) DEFAULT 0,
    [NInterruption] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [DateApparition] DATETIME ,
    [PuissanceCoupee] INTEGER DEFAULT 0,
    [ENDD] FLOAT DEFAULT 0,
    [Observation] TEXT ,
    [Unite] VARCHAR(255) ,
    [Ouvertures] BIT DEFAULT 0,
    [DebutTronconn] DATETIME ,
    [DateFInTronconnement] DATETIME ,
    [DureeTronconn] NUMERIC(19,0) ,
    [DateDebutLocal] DATETIME ,
    [FinLocal] DATETIME ,
    [Regions] VARCHAR(50) DEFAULT '0',
    [DureeLocal] NUMERIC(19,0) ,
    [DebutRepartion] DATETIME ,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [DareFinRepartion] DATETIME ,
    [DureeReparation] NUMERIC(19,0) ,
    [DateRemise] DATETIME ,
    [DebutRemise] DATETIME ,
    [DateFinRemise] DATETIME ,
    [DureeRemise] NUMERIC(19,0) ,
    [DureeTotalIncident] NUMERIC(19,0) ,
    [EtatTraitement] VARCHAR(255) ,
    [DureeInterruption] NUMERIC(19,0) ,
    [DateSaisie] DATETIME ,
    [DateDebutDeclenchement] DATETIME ,
    [Indisponibilité] BIT DEFAULT 0,
    [IncidentEnInstance] VARCHAR(50) ,
    [HeureFinDeclanchem] DATETIME ,
    [Matricule] INTEGER DEFAULT 0,
    [MontantMainOeuvre] INTEGER DEFAULT 0,
    [MontantMateriel] INTEGER DEFAULT 0,
    [MontantLogistique] INTEGER DEFAULT 0,
    [MontantPrestationService] INTEGER DEFAULT 0,
    [AutresFrais] INTEGER DEFAULT 0,
    [CoutIncident] INTEGER DEFAULT 0,
    [MontantEND] INTEGER DEFAULT 0,
    [Service] VARCHAR(255) ,
    [Login] VARCHAR(255) ,
    [CoutTotalIncident] INTEGER DEFAULT 0,
    [PrixEnd] FLOAT DEFAULT 118.72,
    [DistancePrelocalisee] VARCHAR(50) ,
    [PinstTi] REAL DEFAULT 0,
    [PM] REAL DEFAULT 0,
    [Kum] FLOAT DEFAULT 0,
    [Pinstf] FLOAT DEFAULT 0,
    [Annee] INTEGER DEFAULT 0,
    [MoisLettre] VARCHAR(50) ,
    [Semaine] INTEGER DEFAULT 0,
    [Cause] VARCHAR(255) ,
    [Sieges] VARCHAR(50) ,
    [heureApparition] DATETIME ,
    [heureremise] DATETIME ,
    [heuredebutTronco] DATETIME ,
    [HeureFinTronc] DATETIME ,
    [HeureDebutRemise] DATETIME ,
    [HeureFinRemise] DATETIME ,
    [DateFinDeclenchement] DATETIME ,
    [HeuredebutDeclenchement] DATETIME ,
    [HeureDebutReparation] DATETIME ,
    [HeureFinreparation] DATETIME ,
    [durredeclenchement] NUMERIC(19,0) ,
    [heuredeLocalisation] DATETIME ,
    [HeureFinLocal] DATETIME ,
    [Creation] DATETIME ,
    [CreePar] INTEGER DEFAULT 0,
    [Modification] DATETIME ,
    [ModifierPar] INTEGER DEFAULT 0,
    [PosteSource] VARCHAR(255) ,
    [Feeder1] VARCHAR(255) ,
    [Feeder2] VARCHAR(255) ,
    [NoeudAmont] VARCHAR(255) ,
    [NoeudAval] VARCHAR(255) ,
    [Nature] VARCHAR(50) ,
    [CausePresumees] VARCHAR(50) ,
    [SiegePresumee] VARCHAR(50) ,
    [Signalisation] VARCHAR(50) ,
    [TensionPrimaire] REAL DEFAULT 0,
    [source] VARCHAR(255) ,
    [Feeder] VARCHAR(255) ,
    [NomTroncon] VARCHAR(255) ,
    [causeEffective] NUMERIC(19,0) DEFAULT 0,
    [SignalisationEffective] NUMERIC(19,0) DEFAULT 0,
    [siegeEffective] NUMERIC(19,0) DEFAULT 0,
    [codeinterruption] INTEGER DEFAULT 0,
    [dureeHeure] FLOAT DEFAULT 0,
    [Nombreclientimpacte] INTEGER DEFAULT 0,
    [Duree_Jrs] FLOAT DEFAULT 0,
    [casforcemajeur] BIT DEFAULT 0,
    [Directionimputable] VARCHAR(50) ,
    [IDTypeEND] NUMERIC(19,0) ,
    [NumeroInterruption] NUMERIC(19,0)  UNIQUE  DEFAULT 0,
    [Validation] BIT DEFAULT 0,
    [Amodifier] BIT DEFAULT 0,
    [IDTroncon] NUMERIC(19,0) ,
    [ObservationSAQS] VARCHAR(50) ,
    [IDCentrale] NUMERIC(19,0) DEFAULT 0,
    [IDService] NUMERIC(19,0) DEFAULT 0,
    [IDTronconSIG] INTEGER DEFAULT 0,
    [ID_Troncon_SIG] INTEGER ,
    [IDEntreprise] NUMERIC(19,0) ,
    [IDPrestataire] NUMERIC(19,0) ,
    [DateInterpellationPDM] DATETIME ,
    [HeureInterpellationPDM] DATETIME ,
    [DateArriveePDM] DATETIME ,
    [HeureArriveePDM] DATETIME ,
    [IDSousFeeder] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_Interruptions_IDTronçons] ON [Interruptions] ([IDTronçons]);
CREATE INDEX [WDIDX_Interruptions_IDTypePermanent] ON [Interruptions] ([IDTypePermanent]);
CREATE INDEX [WDIDX_Interruptions_IDSieges] ON [Interruptions] ([IDSieges]);
CREATE INDEX [WDIDX_Interruptions_IDCauses] ON [Interruptions] ([IDCauses]);
CREATE INDEX [WDIDX_Interruptions_IDSignalisation] ON [Interruptions] ([IDSignalisation]);
CREATE INDEX [WDIDX_Interruptions_Num] ON [Interruptions] ([Num]);
CREATE INDEX [WDIDX_Interruptions_IDNature] ON [Interruptions] ([IDNature]);
CREATE INDEX [WDIDX_Interruptions_DateApparition] ON [Interruptions] ([DateApparition]);
CREATE INDEX [WDIDX_Interruptions_PuissanceCoupee] ON [Interruptions] ([PuissanceCoupee]);
CREATE INDEX [WDIDX_Interruptions_ENDD] ON [Interruptions] ([ENDD]);
CREATE INDEX [WDIDX_Interruptions_Observation] ON [Interruptions] ([Observation]);
CREATE INDEX [WDIDX_Interruptions_Unite] ON [Interruptions] ([Unite]);
CREATE INDEX [WDIDX_Interruptions_Ouvertures] ON [Interruptions] ([Ouvertures]);
CREATE INDEX [WDIDX_Interruptions_DebutTronconn] ON [Interruptions] ([DebutTronconn]);
CREATE INDEX [WDIDX_Interruptions_DateFInTronconnement] ON [Interruptions] ([DateFInTronconnement]);
CREATE INDEX [WDIDX_Interruptions_DureeTronconn] ON [Interruptions] ([DureeTronconn]);
CREATE INDEX [WDIDX_Interruptions_DateDebutLocal] ON [Interruptions] ([DateDebutLocal]);
CREATE INDEX [WDIDX_Interruptions_FinLocal] ON [Interruptions] ([FinLocal]);
CREATE INDEX [WDIDX_Interruptions_Regions] ON [Interruptions] ([Regions]);
CREATE INDEX [WDIDX_Interruptions_DureeLocal] ON [Interruptions] ([DureeLocal]);
CREATE INDEX [WDIDX_Interruptions_DebutRepartion] ON [Interruptions] ([DebutRepartion]);
CREATE INDEX [WDIDX_Interruptions_IDFeeder] ON [Interruptions] ([IDFeeder]);
CREATE INDEX [WDIDX_Interruptions_DareFinRepartion] ON [Interruptions] ([DareFinRepartion]);
CREATE INDEX [WDIDX_Interruptions_DureeReparation] ON [Interruptions] ([DureeReparation]);
CREATE INDEX [WDIDX_Interruptions_DateRemise] ON [Interruptions] ([DateRemise]);
CREATE INDEX [WDIDX_Interruptions_DebutRemise] ON [Interruptions] ([DebutRemise]);
CREATE INDEX [WDIDX_Interruptions_DateFinRemise] ON [Interruptions] ([DateFinRemise]);
CREATE INDEX [WDIDX_Interruptions_DureeRemise] ON [Interruptions] ([DureeRemise]);
CREATE INDEX [WDIDX_Interruptions_DureeTotalIncident] ON [Interruptions] ([DureeTotalIncident]);
CREATE INDEX [WDIDX_Interruptions_EtatTraitement] ON [Interruptions] ([EtatTraitement]);
CREATE INDEX [WDIDX_Interruptions_DureeInterruption] ON [Interruptions] ([DureeInterruption]);
CREATE INDEX [WDIDX_Interruptions_DateSaisie] ON [Interruptions] ([DateSaisie]);
CREATE INDEX [WDIDX_Interruptions_DateDebutDeclenchement] ON [Interruptions] ([DateDebutDeclenchement]);
CREATE INDEX [WDIDX_Interruptions_Indisponibilité] ON [Interruptions] ([Indisponibilité]);
CREATE INDEX [WDIDX_Interruptions_IncidentEnInstance] ON [Interruptions] ([IncidentEnInstance]);
CREATE INDEX [WDIDX_Interruptions_HeureFinDeclanchem] ON [Interruptions] ([HeureFinDeclanchem]);
CREATE INDEX [WDIDX_Interruptions_Matricule] ON [Interruptions] ([Matricule]);
CREATE INDEX [WDIDX_Interruptions_MontantMainOeuvre] ON [Interruptions] ([MontantMainOeuvre]);
CREATE INDEX [WDIDX_Interruptions_MontantMateriel] ON [Interruptions] ([MontantMateriel]);
CREATE INDEX [WDIDX_Interruptions_MontantLogistique] ON [Interruptions] ([MontantLogistique]);
CREATE INDEX [WDIDX_Interruptions_MontantPrestationService] ON [Interruptions] ([MontantPrestationService]);
CREATE INDEX [WDIDX_Interruptions_AutresFrais] ON [Interruptions] ([AutresFrais]);
CREATE INDEX [WDIDX_Interruptions_CoutIncident] ON [Interruptions] ([CoutIncident]);
CREATE INDEX [WDIDX_Interruptions_MontantEND] ON [Interruptions] ([MontantEND]);
CREATE INDEX [WDIDX_Interruptions_Service] ON [Interruptions] ([Service]);
CREATE INDEX [WDIDX_Interruptions_Login] ON [Interruptions] ([Login]);
CREATE INDEX [WDIDX_Interruptions_CoutTotalIncident] ON [Interruptions] ([CoutTotalIncident]);
CREATE INDEX [WDIDX_Interruptions_PrixEnd] ON [Interruptions] ([PrixEnd]);
CREATE INDEX [WDIDX_Interruptions_DistancePrelocalisee] ON [Interruptions] ([DistancePrelocalisee]);
CREATE INDEX [WDIDX_Interruptions_PinstTi] ON [Interruptions] ([PinstTi]);
CREATE INDEX [WDIDX_Interruptions_PM] ON [Interruptions] ([PM]);
CREATE INDEX [WDIDX_Interruptions_Kum] ON [Interruptions] ([Kum]);
CREATE INDEX [WDIDX_Interruptions_Pinstf] ON [Interruptions] ([Pinstf]);
CREATE INDEX [WDIDX_Interruptions_Annee] ON [Interruptions] ([Annee]);
CREATE INDEX [WDIDX_Interruptions_MoisLettre] ON [Interruptions] ([MoisLettre]);
CREATE INDEX [WDIDX_Interruptions_Semaine] ON [Interruptions] ([Semaine]);
CREATE INDEX [WDIDX_Interruptions_Cause] ON [Interruptions] ([Cause]);
CREATE INDEX [WDIDX_Interruptions_Sieges] ON [Interruptions] ([Sieges]);
CREATE INDEX [WDIDX_Interruptions_heureApparition] ON [Interruptions] ([heureApparition]);
CREATE INDEX [WDIDX_Interruptions_PosteSource] ON [Interruptions] ([PosteSource]);
CREATE INDEX [WDIDX_Interruptions_Nature] ON [Interruptions] ([Nature]);
CREATE INDEX [WDIDX_Interruptions_Signalisation] ON [Interruptions] ([Signalisation]);
CREATE INDEX [WDIDX_Interruptions_TensionPrimaire] ON [Interruptions] ([TensionPrimaire]);
CREATE INDEX [WDIDX_Interruptions_Feeder] ON [Interruptions] ([Feeder]);
CREATE INDEX [WDIDX_Interruptions_codeinterruption] ON [Interruptions] ([codeinterruption]);
CREATE INDEX [WDIDX_Interruptions_Directionimputable] ON [Interruptions] ([Directionimputable]);
CREATE INDEX [WDIDX_Interruptions_IDTypeEND] ON [Interruptions] ([IDTypeEND]);
CREATE INDEX [WDIDX_Interruptions_Validation] ON [Interruptions] ([Validation]);
CREATE INDEX [WDIDX_Interruptions_IDTroncon] ON [Interruptions] ([IDTroncon]);
CREATE INDEX [WDIDX_Interruptions_IDCentrale] ON [Interruptions] ([IDCentrale]);
CREATE INDEX [WDIDX_Interruptions_IDService] ON [Interruptions] ([IDService]);
CREATE INDEX [WDIDX_Interruptions_IDTronconSIG] ON [Interruptions] ([IDTronconSIG]);
CREATE INDEX [WDIDX_Interruptions_ID_Troncon_SIG] ON [Interruptions] ([ID_Troncon_SIG]);
CREATE INDEX [WDIDX_Interruptions_IDEntreprise] ON [Interruptions] ([IDEntreprise]);
CREATE INDEX [WDIDX_Interruptions_IDPrestataire] ON [Interruptions] ([IDPrestataire]);
CREATE INDEX [WDIDX_Interruptions_IDSousFeeder] ON [Interruptions] ([IDSousFeeder]);
CREATE UNIQUE INDEX [WDIDX_Interruptions_FeederDateApparition] ON [Interruptions] ([IDFeeder],[DateApparition],[heureApparition]);
CREATE INDEX [WDIDX_Interruptions_date_heure] ON [Interruptions] ([DateApparition],[heureApparition]);

-- Création de la table Interruptions_Histo
CREATE TABLE [Interruptions_Histo] (
    [IDTronçons] NUMERIC(19,0) DEFAULT 0,
    [IDTypePermanent] NUMERIC(19,0) DEFAULT 0,
    [IDSieges] NUMERIC(19,0) DEFAULT 0,
    [IDCauses] NUMERIC(19,0) DEFAULT 0,
    [IDSignalisation] NUMERIC(19,0) DEFAULT 0,
    [Num] NUMERIC(19,0) DEFAULT 0,
    [IDNature] NUMERIC(19,0) DEFAULT 0,
    [NInterruption] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [DateApparition] DATETIME ,
    [PuissanceCoupee] INTEGER DEFAULT 0,
    [ENDD] FLOAT DEFAULT 0,
    [Observation] TEXT ,
    [Unite] VARCHAR(255) ,
    [Ouvertures] BIT DEFAULT 0,
    [DebutTronconn] DATETIME ,
    [DateFInTronconnement] DATETIME ,
    [DureeTronconn] NUMERIC(19,0) ,
    [DateDebutLocal] DATETIME ,
    [FinLocal] DATETIME ,
    [Regions] VARCHAR(50) DEFAULT '0',
    [DureeLocal] NUMERIC(19,0) ,
    [DebutRepartion] DATETIME ,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [DareFinRepartion] DATETIME ,
    [DureeReparation] NUMERIC(19,0) ,
    [DateRemise] DATETIME ,
    [DebutRemise] DATETIME ,
    [DateFinRemise] DATETIME ,
    [DureeRemise] NUMERIC(19,0) ,
    [DureeTotalIncident] NUMERIC(19,0) ,
    [EtatTraitement] VARCHAR(255) ,
    [DureeInterruption] NUMERIC(19,0) ,
    [DateSaisie] DATETIME ,
    [DateDebutDeclenchement] DATETIME ,
    [Indisponibilité] BIT DEFAULT 0,
    [IncidentEnInstance] VARCHAR(50) ,
    [HeureFinDeclanchem] DATETIME ,
    [Matricule] INTEGER DEFAULT 0,
    [MontantMainOeuvre] INTEGER DEFAULT 0,
    [MontantMateriel] INTEGER DEFAULT 0,
    [MontantLogistique] INTEGER DEFAULT 0,
    [MontantPrestationService] INTEGER DEFAULT 0,
    [AutresFrais] INTEGER DEFAULT 0,
    [CoutIncident] INTEGER DEFAULT 0,
    [MontantEND] INTEGER DEFAULT 0,
    [Service] VARCHAR(255) ,
    [Login] VARCHAR(255) ,
    [CoutTotalIncident] INTEGER DEFAULT 0,
    [PrixEnd] FLOAT DEFAULT 118.72,
    [DistancePrelocalisee] VARCHAR(50) ,
    [PinstTi] REAL DEFAULT 0,
    [PM] REAL DEFAULT 0,
    [Kum] FLOAT DEFAULT 0,
    [Pinstf] FLOAT DEFAULT 0,
    [Annee] INTEGER DEFAULT 0,
    [MoisLettre] VARCHAR(50) ,
    [Semaine] INTEGER DEFAULT 0,
    [Cause] VARCHAR(255) ,
    [Sieges] VARCHAR(50) ,
    [heureApparition] DATETIME ,
    [heureremise] DATETIME ,
    [heuredebutTronco] DATETIME ,
    [HeureFinTronc] DATETIME ,
    [HeureDebutRemise] DATETIME ,
    [HeureFinRemise] DATETIME ,
    [DateFinDeclenchement] DATETIME ,
    [HeuredebutDeclenchement] DATETIME ,
    [HeureDebutReparation] DATETIME ,
    [HeureFinreparation] DATETIME ,
    [durredeclenchement] NUMERIC(19,0) ,
    [heuredeLocalisation] DATETIME ,
    [HeureFinLocal] DATETIME ,
    [Creation] DATETIME ,
    [CreePar] INTEGER DEFAULT 0,
    [Modification] DATETIME ,
    [ModifierPar] INTEGER DEFAULT 0,
    [PosteSource] VARCHAR(255) ,
    [Feeder1] VARCHAR(255) ,
    [Feeder2] VARCHAR(255) ,
    [NoeudAmont] VARCHAR(255) ,
    [NoeudAval] VARCHAR(255) ,
    [Nature] VARCHAR(50) ,
    [CausePresumees] VARCHAR(50) ,
    [SiegePresumee] VARCHAR(50) ,
    [Signalisation] VARCHAR(50) ,
    [TensionPrimaire] REAL DEFAULT 0,
    [source] VARCHAR(255) ,
    [Feeder] VARCHAR(255) ,
    [NomTroncon] VARCHAR(255) ,
    [causeEffective] NUMERIC(19,0) DEFAULT 0,
    [SignalisationEffective] NUMERIC(19,0) DEFAULT 0,
    [siegeEffective] NUMERIC(19,0) DEFAULT 0,
    [codeinterruption] INTEGER DEFAULT 0,
    [dureeHeure] FLOAT DEFAULT 0,
    [Nombreclientimpacte] INTEGER DEFAULT 0,
    [Duree_Jrs] FLOAT DEFAULT 0,
    [casforcemajeur] BIT DEFAULT 0,
    [Directionimputable] VARCHAR(50) ,
    [IDTypeEND] NUMERIC(19,0) ,
    [NumeroInterruption] NUMERIC(19,0)  UNIQUE  DEFAULT 0,
    [Validation] BIT DEFAULT 0,
    [Amodifier] BIT DEFAULT 0,
    [IDTroncon] NUMERIC(19,0) ,
    [ObservationSAQS] VARCHAR(50) ,
    [IDCentrale] NUMERIC(19,0) DEFAULT 0,
    [IDService] NUMERIC(19,0) DEFAULT 0,
    [IDTronconSIG] INTEGER DEFAULT 0,
    [ID_Troncon_SIG] INTEGER ,
    [Agression] BIT DEFAULT 0);
CREATE INDEX [WDIDX_Interruptions_Histo_IDTronçons] ON [Interruptions_Histo] ([IDTronçons]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDTypePermanent] ON [Interruptions_Histo] ([IDTypePermanent]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDSieges] ON [Interruptions_Histo] ([IDSieges]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDCauses] ON [Interruptions_Histo] ([IDCauses]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDSignalisation] ON [Interruptions_Histo] ([IDSignalisation]);
CREATE INDEX [WDIDX_Interruptions_Histo_Num] ON [Interruptions_Histo] ([Num]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDNature] ON [Interruptions_Histo] ([IDNature]);
CREATE INDEX [WDIDX_Interruptions_Histo_DateApparition] ON [Interruptions_Histo] ([DateApparition]);
CREATE INDEX [WDIDX_Interruptions_Histo_PuissanceCoupee] ON [Interruptions_Histo] ([PuissanceCoupee]);
CREATE INDEX [WDIDX_Interruptions_Histo_ENDD] ON [Interruptions_Histo] ([ENDD]);
CREATE INDEX [WDIDX_Interruptions_Histo_Observation] ON [Interruptions_Histo] ([Observation]);
CREATE INDEX [WDIDX_Interruptions_Histo_Unite] ON [Interruptions_Histo] ([Unite]);
CREATE INDEX [WDIDX_Interruptions_Histo_Ouvertures] ON [Interruptions_Histo] ([Ouvertures]);
CREATE INDEX [WDIDX_Interruptions_Histo_DebutTronconn] ON [Interruptions_Histo] ([DebutTronconn]);
CREATE INDEX [WDIDX_Interruptions_Histo_DateFInTronconnement] ON [Interruptions_Histo] ([DateFInTronconnement]);
CREATE INDEX [WDIDX_Interruptions_Histo_DureeTronconn] ON [Interruptions_Histo] ([DureeTronconn]);
CREATE INDEX [WDIDX_Interruptions_Histo_DateDebutLocal] ON [Interruptions_Histo] ([DateDebutLocal]);
CREATE INDEX [WDIDX_Interruptions_Histo_FinLocal] ON [Interruptions_Histo] ([FinLocal]);
CREATE INDEX [WDIDX_Interruptions_Histo_Regions] ON [Interruptions_Histo] ([Regions]);
CREATE INDEX [WDIDX_Interruptions_Histo_DureeLocal] ON [Interruptions_Histo] ([DureeLocal]);
CREATE INDEX [WDIDX_Interruptions_Histo_DebutRepartion] ON [Interruptions_Histo] ([DebutRepartion]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDFeeder] ON [Interruptions_Histo] ([IDFeeder]);
CREATE INDEX [WDIDX_Interruptions_Histo_DareFinRepartion] ON [Interruptions_Histo] ([DareFinRepartion]);
CREATE INDEX [WDIDX_Interruptions_Histo_DureeReparation] ON [Interruptions_Histo] ([DureeReparation]);
CREATE INDEX [WDIDX_Interruptions_Histo_DateRemise] ON [Interruptions_Histo] ([DateRemise]);
CREATE INDEX [WDIDX_Interruptions_Histo_DebutRemise] ON [Interruptions_Histo] ([DebutRemise]);
CREATE INDEX [WDIDX_Interruptions_Histo_DateFinRemise] ON [Interruptions_Histo] ([DateFinRemise]);
CREATE INDEX [WDIDX_Interruptions_Histo_DureeRemise] ON [Interruptions_Histo] ([DureeRemise]);
CREATE INDEX [WDIDX_Interruptions_Histo_DureeTotalIncident] ON [Interruptions_Histo] ([DureeTotalIncident]);
CREATE INDEX [WDIDX_Interruptions_Histo_EtatTraitement] ON [Interruptions_Histo] ([EtatTraitement]);
CREATE INDEX [WDIDX_Interruptions_Histo_DureeInterruption] ON [Interruptions_Histo] ([DureeInterruption]);
CREATE INDEX [WDIDX_Interruptions_Histo_DateSaisie] ON [Interruptions_Histo] ([DateSaisie]);
CREATE INDEX [WDIDX_Interruptions_Histo_DateDebutDeclenchement] ON [Interruptions_Histo] ([DateDebutDeclenchement]);
CREATE INDEX [WDIDX_Interruptions_Histo_Indisponibilité] ON [Interruptions_Histo] ([Indisponibilité]);
CREATE INDEX [WDIDX_Interruptions_Histo_IncidentEnInstance] ON [Interruptions_Histo] ([IncidentEnInstance]);
CREATE INDEX [WDIDX_Interruptions_Histo_HeureFinDeclanchem] ON [Interruptions_Histo] ([HeureFinDeclanchem]);
CREATE INDEX [WDIDX_Interruptions_Histo_Matricule] ON [Interruptions_Histo] ([Matricule]);
CREATE INDEX [WDIDX_Interruptions_Histo_MontantMainOeuvre] ON [Interruptions_Histo] ([MontantMainOeuvre]);
CREATE INDEX [WDIDX_Interruptions_Histo_MontantMateriel] ON [Interruptions_Histo] ([MontantMateriel]);
CREATE INDEX [WDIDX_Interruptions_Histo_MontantLogistique] ON [Interruptions_Histo] ([MontantLogistique]);
CREATE INDEX [WDIDX_Interruptions_Histo_MontantPrestationService] ON [Interruptions_Histo] ([MontantPrestationService]);
CREATE INDEX [WDIDX_Interruptions_Histo_AutresFrais] ON [Interruptions_Histo] ([AutresFrais]);
CREATE INDEX [WDIDX_Interruptions_Histo_CoutIncident] ON [Interruptions_Histo] ([CoutIncident]);
CREATE INDEX [WDIDX_Interruptions_Histo_MontantEND] ON [Interruptions_Histo] ([MontantEND]);
CREATE INDEX [WDIDX_Interruptions_Histo_Service] ON [Interruptions_Histo] ([Service]);
CREATE INDEX [WDIDX_Interruptions_Histo_Login] ON [Interruptions_Histo] ([Login]);
CREATE INDEX [WDIDX_Interruptions_Histo_CoutTotalIncident] ON [Interruptions_Histo] ([CoutTotalIncident]);
CREATE INDEX [WDIDX_Interruptions_Histo_PrixEnd] ON [Interruptions_Histo] ([PrixEnd]);
CREATE INDEX [WDIDX_Interruptions_Histo_DistancePrelocalisee] ON [Interruptions_Histo] ([DistancePrelocalisee]);
CREATE INDEX [WDIDX_Interruptions_Histo_PinstTi] ON [Interruptions_Histo] ([PinstTi]);
CREATE INDEX [WDIDX_Interruptions_Histo_PM] ON [Interruptions_Histo] ([PM]);
CREATE INDEX [WDIDX_Interruptions_Histo_Kum] ON [Interruptions_Histo] ([Kum]);
CREATE INDEX [WDIDX_Interruptions_Histo_Pinstf] ON [Interruptions_Histo] ([Pinstf]);
CREATE INDEX [WDIDX_Interruptions_Histo_Annee] ON [Interruptions_Histo] ([Annee]);
CREATE INDEX [WDIDX_Interruptions_Histo_MoisLettre] ON [Interruptions_Histo] ([MoisLettre]);
CREATE INDEX [WDIDX_Interruptions_Histo_Semaine] ON [Interruptions_Histo] ([Semaine]);
CREATE INDEX [WDIDX_Interruptions_Histo_Cause] ON [Interruptions_Histo] ([Cause]);
CREATE INDEX [WDIDX_Interruptions_Histo_Sieges] ON [Interruptions_Histo] ([Sieges]);
CREATE INDEX [WDIDX_Interruptions_Histo_heureApparition] ON [Interruptions_Histo] ([heureApparition]);
CREATE INDEX [WDIDX_Interruptions_Histo_PosteSource] ON [Interruptions_Histo] ([PosteSource]);
CREATE INDEX [WDIDX_Interruptions_Histo_Nature] ON [Interruptions_Histo] ([Nature]);
CREATE INDEX [WDIDX_Interruptions_Histo_Signalisation] ON [Interruptions_Histo] ([Signalisation]);
CREATE INDEX [WDIDX_Interruptions_Histo_TensionPrimaire] ON [Interruptions_Histo] ([TensionPrimaire]);
CREATE INDEX [WDIDX_Interruptions_Histo_Feeder] ON [Interruptions_Histo] ([Feeder]);
CREATE INDEX [WDIDX_Interruptions_Histo_codeinterruption] ON [Interruptions_Histo] ([codeinterruption]);
CREATE INDEX [WDIDX_Interruptions_Histo_Directionimputable] ON [Interruptions_Histo] ([Directionimputable]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDTypeEND] ON [Interruptions_Histo] ([IDTypeEND]);
CREATE INDEX [WDIDX_Interruptions_Histo_Validation] ON [Interruptions_Histo] ([Validation]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDTroncon] ON [Interruptions_Histo] ([IDTroncon]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDCentrale] ON [Interruptions_Histo] ([IDCentrale]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDService] ON [Interruptions_Histo] ([IDService]);
CREATE INDEX [WDIDX_Interruptions_Histo_IDTronconSIG] ON [Interruptions_Histo] ([IDTronconSIG]);
CREATE INDEX [WDIDX_Interruptions_Histo_ID_Troncon_SIG] ON [Interruptions_Histo] ([ID_Troncon_SIG]);
CREATE UNIQUE INDEX [WDIDX_Interruptions_Histo_FeederDateApparition] ON [Interruptions_Histo] ([IDFeeder],[DateApparition],[heureApparition]);
CREATE INDEX [WDIDX_Interruptions_Histo_date_heure] ON [Interruptions_Histo] ([DateApparition],[heureApparition]);

-- Création de la table Interruptions_OMVG
CREATE TABLE [Interruptions_OMVG] (
    [IDTronçons] NUMERIC(19,0) DEFAULT 0,
    [IDTypePermanent] NUMERIC(19,0) DEFAULT 0,
    [IDSieges] NUMERIC(19,0) DEFAULT 0,
    [IDCauses] NUMERIC(19,0) DEFAULT 0,
    [IDSignalisation] NUMERIC(19,0) DEFAULT 0,
    [Num] NUMERIC(19,0) DEFAULT 0,
    [IDNature] NUMERIC(19,0) DEFAULT 0,
    [NInterruption] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [DateApparition] DATETIME ,
    [PuissanceCoupee] INTEGER DEFAULT 0,
    [ENDD] FLOAT DEFAULT 0,
    [Observation] TEXT ,
    [Unite] VARCHAR(255) ,
    [Ouvertures] BIT DEFAULT 0,
    [DebutTronconn] DATETIME ,
    [DateFInTronconnement] DATETIME ,
    [DureeTronconn] NUMERIC(19,0) ,
    [DateDebutLocal] DATETIME ,
    [FinLocal] DATETIME ,
    [Regions] VARCHAR(50) DEFAULT '0',
    [DureeLocal] NUMERIC(19,0) ,
    [DebutRepartion] DATETIME ,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [DareFinRepartion] DATETIME ,
    [DureeReparation] NUMERIC(19,0) ,
    [DateRemise] DATETIME ,
    [DebutRemise] DATETIME ,
    [DateFinRemise] DATETIME ,
    [DureeRemise] NUMERIC(19,0) ,
    [DureeTotalIncident] NUMERIC(19,0) ,
    [EtatTraitement] VARCHAR(255) ,
    [DureeInterruption] NUMERIC(19,0) ,
    [DateSaisie] DATETIME ,
    [DateDebutDeclenchement] DATETIME ,
    [Indisponibilité] BIT DEFAULT 0,
    [IncidentEnInstance] VARCHAR(50) ,
    [HeureFinDeclanchem] DATETIME ,
    [Matricule] INTEGER DEFAULT 0,
    [MontantMainOeuvre] INTEGER DEFAULT 0,
    [MontantMateriel] INTEGER DEFAULT 0,
    [MontantLogistique] INTEGER DEFAULT 0,
    [MontantPrestationService] INTEGER DEFAULT 0,
    [AutresFrais] INTEGER DEFAULT 0,
    [CoutIncident] INTEGER DEFAULT 0,
    [MontantEND] INTEGER DEFAULT 0,
    [Service] VARCHAR(255) ,
    [Login] VARCHAR(255) ,
    [CoutTotalIncident] INTEGER DEFAULT 0,
    [PrixEnd] FLOAT DEFAULT 118.72,
    [DistancePrelocalisee] VARCHAR(50) ,
    [PinstTi] REAL DEFAULT 0,
    [PM] REAL DEFAULT 0,
    [Kum] FLOAT DEFAULT 0,
    [Pinstf] FLOAT DEFAULT 0,
    [Annee] INTEGER DEFAULT 0,
    [MoisLettre] VARCHAR(50) ,
    [Semaine] INTEGER DEFAULT 0,
    [Cause] VARCHAR(255) ,
    [Sieges] VARCHAR(50) ,
    [heureApparition] DATETIME ,
    [heureremise] DATETIME ,
    [heuredebutTronco] DATETIME ,
    [HeureFinTronc] DATETIME ,
    [HeureDebutRemise] DATETIME ,
    [HeureFinRemise] DATETIME ,
    [DateFinDeclenchement] DATETIME ,
    [HeuredebutDeclenchement] DATETIME ,
    [HeureDebutReparation] DATETIME ,
    [HeureFinreparation] DATETIME ,
    [durredeclenchement] NUMERIC(19,0) ,
    [heuredeLocalisation] DATETIME ,
    [HeureFinLocal] DATETIME ,
    [Creation] DATETIME ,
    [CreePar] INTEGER DEFAULT 0,
    [Modification] DATETIME ,
    [ModifierPar] INTEGER DEFAULT 0,
    [PosteSource] VARCHAR(255) ,
    [Feeder1] VARCHAR(255) ,
    [Feeder2] VARCHAR(255) ,
    [NoeudAmont] VARCHAR(255) ,
    [NoeudAval] VARCHAR(255) ,
    [Nature] VARCHAR(50) ,
    [CausePresumees] VARCHAR(50) ,
    [SiegePresumee] VARCHAR(50) ,
    [Signalisation] VARCHAR(50) ,
    [TensionPrimaire] REAL DEFAULT 0,
    [source] VARCHAR(255) ,
    [Feeder] VARCHAR(255) ,
    [NomTroncon] VARCHAR(255) ,
    [causeEffective] NUMERIC(19,0) DEFAULT 0,
    [SignalisationEffective] NUMERIC(19,0) DEFAULT 0,
    [siegeEffective] NUMERIC(19,0) DEFAULT 0,
    [codeinterruption] INTEGER DEFAULT 0,
    [dureeHeure] FLOAT DEFAULT 0,
    [Nombreclientimpacte] INTEGER DEFAULT 0,
    [Duree_Jrs] FLOAT DEFAULT 0,
    [casforcemajeur] BIT DEFAULT 0,
    [Directionimputable] VARCHAR(50) ,
    [IDTypeEND] NUMERIC(19,0) ,
    [NumeroInterruption] NUMERIC(19,0)  UNIQUE  DEFAULT 0,
    [Validation] BIT DEFAULT 0,
    [Amodifier] BIT DEFAULT 0,
    [IDTroncon] NUMERIC(19,0) ,
    [ObservationSAQS] VARCHAR(50) ,
    [IDCentrale] NUMERIC(19,0) DEFAULT 0,
    [IDService] NUMERIC(19,0) DEFAULT 0,
    [IDTronconSIG] INTEGER DEFAULT 0,
    [ID_Troncon_SIG] INTEGER );
CREATE INDEX [WDIDX_Interruptions_OMVG_IDTronçons] ON [Interruptions_OMVG] ([IDTronçons]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDTypePermanent] ON [Interruptions_OMVG] ([IDTypePermanent]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDSieges] ON [Interruptions_OMVG] ([IDSieges]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDCauses] ON [Interruptions_OMVG] ([IDCauses]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDSignalisation] ON [Interruptions_OMVG] ([IDSignalisation]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Num] ON [Interruptions_OMVG] ([Num]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDNature] ON [Interruptions_OMVG] ([IDNature]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DateApparition] ON [Interruptions_OMVG] ([DateApparition]);
CREATE INDEX [WDIDX_Interruptions_OMVG_PuissanceCoupee] ON [Interruptions_OMVG] ([PuissanceCoupee]);
CREATE INDEX [WDIDX_Interruptions_OMVG_ENDD] ON [Interruptions_OMVG] ([ENDD]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Observation] ON [Interruptions_OMVG] ([Observation]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Unite] ON [Interruptions_OMVG] ([Unite]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Ouvertures] ON [Interruptions_OMVG] ([Ouvertures]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DebutTronconn] ON [Interruptions_OMVG] ([DebutTronconn]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DateFInTronconnement] ON [Interruptions_OMVG] ([DateFInTronconnement]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DureeTronconn] ON [Interruptions_OMVG] ([DureeTronconn]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DateDebutLocal] ON [Interruptions_OMVG] ([DateDebutLocal]);
CREATE INDEX [WDIDX_Interruptions_OMVG_FinLocal] ON [Interruptions_OMVG] ([FinLocal]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Regions] ON [Interruptions_OMVG] ([Regions]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DureeLocal] ON [Interruptions_OMVG] ([DureeLocal]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DebutRepartion] ON [Interruptions_OMVG] ([DebutRepartion]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDFeeder] ON [Interruptions_OMVG] ([IDFeeder]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DareFinRepartion] ON [Interruptions_OMVG] ([DareFinRepartion]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DureeReparation] ON [Interruptions_OMVG] ([DureeReparation]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DateRemise] ON [Interruptions_OMVG] ([DateRemise]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DebutRemise] ON [Interruptions_OMVG] ([DebutRemise]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DateFinRemise] ON [Interruptions_OMVG] ([DateFinRemise]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DureeRemise] ON [Interruptions_OMVG] ([DureeRemise]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DureeTotalIncident] ON [Interruptions_OMVG] ([DureeTotalIncident]);
CREATE INDEX [WDIDX_Interruptions_OMVG_EtatTraitement] ON [Interruptions_OMVG] ([EtatTraitement]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DureeInterruption] ON [Interruptions_OMVG] ([DureeInterruption]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DateSaisie] ON [Interruptions_OMVG] ([DateSaisie]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DateDebutDeclenchement] ON [Interruptions_OMVG] ([DateDebutDeclenchement]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Indisponibilité] ON [Interruptions_OMVG] ([Indisponibilité]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IncidentEnInstance] ON [Interruptions_OMVG] ([IncidentEnInstance]);
CREATE INDEX [WDIDX_Interruptions_OMVG_HeureFinDeclanchem] ON [Interruptions_OMVG] ([HeureFinDeclanchem]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Matricule] ON [Interruptions_OMVG] ([Matricule]);
CREATE INDEX [WDIDX_Interruptions_OMVG_MontantMainOeuvre] ON [Interruptions_OMVG] ([MontantMainOeuvre]);
CREATE INDEX [WDIDX_Interruptions_OMVG_MontantMateriel] ON [Interruptions_OMVG] ([MontantMateriel]);
CREATE INDEX [WDIDX_Interruptions_OMVG_MontantLogistique] ON [Interruptions_OMVG] ([MontantLogistique]);
CREATE INDEX [WDIDX_Interruptions_OMVG_MontantPrestationService] ON [Interruptions_OMVG] ([MontantPrestationService]);
CREATE INDEX [WDIDX_Interruptions_OMVG_AutresFrais] ON [Interruptions_OMVG] ([AutresFrais]);
CREATE INDEX [WDIDX_Interruptions_OMVG_CoutIncident] ON [Interruptions_OMVG] ([CoutIncident]);
CREATE INDEX [WDIDX_Interruptions_OMVG_MontantEND] ON [Interruptions_OMVG] ([MontantEND]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Service] ON [Interruptions_OMVG] ([Service]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Login] ON [Interruptions_OMVG] ([Login]);
CREATE INDEX [WDIDX_Interruptions_OMVG_CoutTotalIncident] ON [Interruptions_OMVG] ([CoutTotalIncident]);
CREATE INDEX [WDIDX_Interruptions_OMVG_PrixEnd] ON [Interruptions_OMVG] ([PrixEnd]);
CREATE INDEX [WDIDX_Interruptions_OMVG_DistancePrelocalisee] ON [Interruptions_OMVG] ([DistancePrelocalisee]);
CREATE INDEX [WDIDX_Interruptions_OMVG_PinstTi] ON [Interruptions_OMVG] ([PinstTi]);
CREATE INDEX [WDIDX_Interruptions_OMVG_PM] ON [Interruptions_OMVG] ([PM]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Kum] ON [Interruptions_OMVG] ([Kum]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Pinstf] ON [Interruptions_OMVG] ([Pinstf]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Annee] ON [Interruptions_OMVG] ([Annee]);
CREATE INDEX [WDIDX_Interruptions_OMVG_MoisLettre] ON [Interruptions_OMVG] ([MoisLettre]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Semaine] ON [Interruptions_OMVG] ([Semaine]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Cause] ON [Interruptions_OMVG] ([Cause]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Sieges] ON [Interruptions_OMVG] ([Sieges]);
CREATE INDEX [WDIDX_Interruptions_OMVG_heureApparition] ON [Interruptions_OMVG] ([heureApparition]);
CREATE INDEX [WDIDX_Interruptions_OMVG_PosteSource] ON [Interruptions_OMVG] ([PosteSource]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Nature] ON [Interruptions_OMVG] ([Nature]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Signalisation] ON [Interruptions_OMVG] ([Signalisation]);
CREATE INDEX [WDIDX_Interruptions_OMVG_TensionPrimaire] ON [Interruptions_OMVG] ([TensionPrimaire]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Feeder] ON [Interruptions_OMVG] ([Feeder]);
CREATE INDEX [WDIDX_Interruptions_OMVG_codeinterruption] ON [Interruptions_OMVG] ([codeinterruption]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Directionimputable] ON [Interruptions_OMVG] ([Directionimputable]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDTypeEND] ON [Interruptions_OMVG] ([IDTypeEND]);
CREATE INDEX [WDIDX_Interruptions_OMVG_Validation] ON [Interruptions_OMVG] ([Validation]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDTroncon] ON [Interruptions_OMVG] ([IDTroncon]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDCentrale] ON [Interruptions_OMVG] ([IDCentrale]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDService] ON [Interruptions_OMVG] ([IDService]);
CREATE INDEX [WDIDX_Interruptions_OMVG_IDTronconSIG] ON [Interruptions_OMVG] ([IDTronconSIG]);
CREATE INDEX [WDIDX_Interruptions_OMVG_ID_Troncon_SIG] ON [Interruptions_OMVG] ([ID_Troncon_SIG]);
CREATE UNIQUE INDEX [WDIDX_Interruptions_OMVG_FeederDateApparition] ON [Interruptions_OMVG] ([IDFeeder],[DateApparition],[heureApparition]);
CREATE INDEX [WDIDX_Interruptions_OMVG_date_heure] ON [Interruptions_OMVG] ([DateApparition],[heureApparition]);

-- Création de la table InterruptionsTransport
CREATE TABLE [InterruptionsTransport] (
    [IDTronçons] NUMERIC(19,0) DEFAULT 0,
    [IDTypePermanent] NUMERIC(19,0) DEFAULT 0,
    [IDSieges] NUMERIC(19,0) DEFAULT 0,
    [IDCauses] NUMERIC(19,0) DEFAULT 0,
    [IDSignalisation] NUMERIC(19,0) DEFAULT 0,
    [Num] NUMERIC(19,0) DEFAULT 0,
    [IDNature] NUMERIC(19,0) DEFAULT 0,
    [NInterruption] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [DateApparition] DATETIME ,
    [PuissanceCoupee] INTEGER DEFAULT 0,
    [ENDD] FLOAT DEFAULT 0,
    [Observation] TEXT ,
    [Unite] VARCHAR(255) ,
    [Ouvertures] BIT DEFAULT 0,
    [DebutTronconn] DATETIME ,
    [DateFInTronconnement] DATETIME ,
    [DureeTronconn] NUMERIC(19,0) ,
    [DateDebutLocal] DATETIME ,
    [FinLocal] DATETIME ,
    [Regions] VARCHAR(50) DEFAULT 'Transport',
    [DureeLocal] NUMERIC(19,0) ,
    [DebutRepartion] DATETIME ,
    [DareFinRepartion] DATETIME ,
    [DureeReparation] NUMERIC(19,0) ,
    [DateRemise] DATETIME ,
    [DebutRemise] DATETIME ,
    [DateFinRemise] DATETIME ,
    [DureeRemise] NUMERIC(19,0) ,
    [DureeTotalIncident] NUMERIC(19,0) ,
    [EtatTraitement] VARCHAR(255) ,
    [DureeInterruption] NUMERIC(19,0) ,
    [DateSaisie] DATETIME ,
    [DateDebutDeclenchement] DATETIME ,
    [Indisponibilité] BIT DEFAULT 0,
    [IncidentEnInstance] VARCHAR(50) ,
    [HeureFinDeclanchem] DATETIME ,
    [Matricule] INTEGER DEFAULT 0,
    [MontantMainOeuvre] INTEGER DEFAULT 0,
    [MontantMateriel] INTEGER DEFAULT 0,
    [MontantLogistique] INTEGER DEFAULT 0,
    [MontantPrestationService] INTEGER DEFAULT 0,
    [AutresFrais] INTEGER DEFAULT 0,
    [CoutIncident] INTEGER DEFAULT 0,
    [MontantEND] INTEGER DEFAULT 0,
    [Service] VARCHAR(255) ,
    [Login] VARCHAR(255) ,
    [CoutTotalIncident] INTEGER DEFAULT 0,
    [PrixEnd] FLOAT DEFAULT 118.72,
    [DistancePrelocalisee] VARCHAR(50) ,
    [PinstTi] REAL DEFAULT 0,
    [PM] REAL DEFAULT 0,
    [Kum] FLOAT DEFAULT 0,
    [Pinstf] FLOAT DEFAULT 0,
    [Annee] INTEGER DEFAULT 0,
    [MoisLettre] VARCHAR(50) ,
    [Semaine] INTEGER DEFAULT 0,
    [Cause] VARCHAR(255) ,
    [Sieges] VARCHAR(50) ,
    [heureApparition] DATETIME ,
    [heureremise] DATETIME ,
    [heuredebutTronco] DATETIME ,
    [HeureFinTronc] DATETIME ,
    [HeureDebutRemise] DATETIME ,
    [HeureFinRemise] DATETIME ,
    [DateFinDeclenchement] DATETIME ,
    [HeuredebutDeclenchement] DATETIME ,
    [HeureDebutReparation] DATETIME ,
    [HeureFinreparation] DATETIME ,
    [durredeclenchement] NUMERIC(19,0) ,
    [heuredeLocalisation] DATETIME ,
    [HeureFinLocal] DATETIME ,
    [Creation] DATETIME ,
    [CreePar] INTEGER DEFAULT 0,
    [Modification] DATETIME ,
    [ModifierPar] INTEGER DEFAULT 0,
    [PosteSource] VARCHAR(255) ,
    [Feeder1] VARCHAR(255) ,
    [Feeder2] VARCHAR(255) ,
    [NoeudAmont] VARCHAR(255) ,
    [NoeudAval] VARCHAR(255) ,
    [Nature] VARCHAR(50) ,
    [CausePresumees] VARCHAR(50) ,
    [SiegePresumee] VARCHAR(50) ,
    [Signalisation] VARCHAR(50) ,
    [TensionPrimaire] REAL DEFAULT 0,
    [source] VARCHAR(255) ,
    [Feeder] VARCHAR(255) ,
    [NomTroncon] VARCHAR(255) ,
    [causeEffective] NUMERIC(19,0) DEFAULT 0,
    [SignalisationEffective] NUMERIC(19,0) DEFAULT 0,
    [siegeEffective] NUMERIC(19,0) DEFAULT 0,
    [codeinterruption] INTEGER DEFAULT 0,
    [dureeHeure] FLOAT DEFAULT 0,
    [Nombreclientimpacte] INTEGER DEFAULT 0,
    [Duree_Jrs] FLOAT DEFAULT 0,
    [casforcemajeur] BIT DEFAULT 0,
    [Directionimputable] VARCHAR(50) ,
    [IDEquipements] NUMERIC(19,0) DEFAULT 0,
    [IDSourceEquipement] NUMERIC(19,0) DEFAULT 0,
    [IDPosteLigne] NUMERIC(19,0) DEFAULT 0,
    [Tension] REAL DEFAULT 0,
    [validationchefunite] BIT DEFAULT 0,
    [datevalidationchefunite] DATETIME ,
    [indicateurvalidation] VARCHAR(50) DEFAULT '\nok.png',
    [choix] TINYINT DEFAULT 1,
    [supprimer] BIT DEFAULT 0,
    [IDTypeEND] NUMERIC(19,0) ,
    [IDCentrale] NUMERIC(19,0) DEFAULT 0,
    [DefautLigne] BIT DEFAULT 0,
    [NePasPrendreEnCompteDefautLigne] BIT DEFAULT 0);
CREATE INDEX [WDIDX_InterruptionsTransport_IDTronçons] ON [InterruptionsTransport] ([IDTronçons]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDTypePermanent] ON [InterruptionsTransport] ([IDTypePermanent]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDSieges] ON [InterruptionsTransport] ([IDSieges]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDCauses] ON [InterruptionsTransport] ([IDCauses]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDSignalisation] ON [InterruptionsTransport] ([IDSignalisation]);
CREATE INDEX [WDIDX_InterruptionsTransport_Num] ON [InterruptionsTransport] ([Num]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDNature] ON [InterruptionsTransport] ([IDNature]);
CREATE INDEX [WDIDX_InterruptionsTransport_DateApparition] ON [InterruptionsTransport] ([DateApparition]);
CREATE INDEX [WDIDX_InterruptionsTransport_PuissanceCoupee] ON [InterruptionsTransport] ([PuissanceCoupee]);
CREATE INDEX [WDIDX_InterruptionsTransport_ENDD] ON [InterruptionsTransport] ([ENDD]);
CREATE INDEX [WDIDX_InterruptionsTransport_Observation] ON [InterruptionsTransport] ([Observation]);
CREATE INDEX [WDIDX_InterruptionsTransport_Unite] ON [InterruptionsTransport] ([Unite]);
CREATE INDEX [WDIDX_InterruptionsTransport_Ouvertures] ON [InterruptionsTransport] ([Ouvertures]);
CREATE INDEX [WDIDX_InterruptionsTransport_DebutTronconn] ON [InterruptionsTransport] ([DebutTronconn]);
CREATE INDEX [WDIDX_InterruptionsTransport_DateFInTronconnement] ON [InterruptionsTransport] ([DateFInTronconnement]);
CREATE INDEX [WDIDX_InterruptionsTransport_DureeTronconn] ON [InterruptionsTransport] ([DureeTronconn]);
CREATE INDEX [WDIDX_InterruptionsTransport_DateDebutLocal] ON [InterruptionsTransport] ([DateDebutLocal]);
CREATE INDEX [WDIDX_InterruptionsTransport_FinLocal] ON [InterruptionsTransport] ([FinLocal]);
CREATE INDEX [WDIDX_InterruptionsTransport_Regions] ON [InterruptionsTransport] ([Regions]);
CREATE INDEX [WDIDX_InterruptionsTransport_DureeLocal] ON [InterruptionsTransport] ([DureeLocal]);
CREATE INDEX [WDIDX_InterruptionsTransport_DebutRepartion] ON [InterruptionsTransport] ([DebutRepartion]);
CREATE INDEX [WDIDX_InterruptionsTransport_DareFinRepartion] ON [InterruptionsTransport] ([DareFinRepartion]);
CREATE INDEX [WDIDX_InterruptionsTransport_DureeReparation] ON [InterruptionsTransport] ([DureeReparation]);
CREATE INDEX [WDIDX_InterruptionsTransport_DateRemise] ON [InterruptionsTransport] ([DateRemise]);
CREATE INDEX [WDIDX_InterruptionsTransport_DebutRemise] ON [InterruptionsTransport] ([DebutRemise]);
CREATE INDEX [WDIDX_InterruptionsTransport_DateFinRemise] ON [InterruptionsTransport] ([DateFinRemise]);
CREATE INDEX [WDIDX_InterruptionsTransport_DureeRemise] ON [InterruptionsTransport] ([DureeRemise]);
CREATE INDEX [WDIDX_InterruptionsTransport_DureeTotalIncident] ON [InterruptionsTransport] ([DureeTotalIncident]);
CREATE INDEX [WDIDX_InterruptionsTransport_EtatTraitement] ON [InterruptionsTransport] ([EtatTraitement]);
CREATE INDEX [WDIDX_InterruptionsTransport_DureeInterruption] ON [InterruptionsTransport] ([DureeInterruption]);
CREATE INDEX [WDIDX_InterruptionsTransport_DateSaisie] ON [InterruptionsTransport] ([DateSaisie]);
CREATE INDEX [WDIDX_InterruptionsTransport_DateDebutDeclenchement] ON [InterruptionsTransport] ([DateDebutDeclenchement]);
CREATE INDEX [WDIDX_InterruptionsTransport_Indisponibilité] ON [InterruptionsTransport] ([Indisponibilité]);
CREATE INDEX [WDIDX_InterruptionsTransport_IncidentEnInstance] ON [InterruptionsTransport] ([IncidentEnInstance]);
CREATE INDEX [WDIDX_InterruptionsTransport_HeureFinDeclanchem] ON [InterruptionsTransport] ([HeureFinDeclanchem]);
CREATE INDEX [WDIDX_InterruptionsTransport_Matricule] ON [InterruptionsTransport] ([Matricule]);
CREATE INDEX [WDIDX_InterruptionsTransport_MontantMainOeuvre] ON [InterruptionsTransport] ([MontantMainOeuvre]);
CREATE INDEX [WDIDX_InterruptionsTransport_MontantMateriel] ON [InterruptionsTransport] ([MontantMateriel]);
CREATE INDEX [WDIDX_InterruptionsTransport_MontantLogistique] ON [InterruptionsTransport] ([MontantLogistique]);
CREATE INDEX [WDIDX_InterruptionsTransport_MontantPrestationService] ON [InterruptionsTransport] ([MontantPrestationService]);
CREATE INDEX [WDIDX_InterruptionsTransport_AutresFrais] ON [InterruptionsTransport] ([AutresFrais]);
CREATE INDEX [WDIDX_InterruptionsTransport_CoutIncident] ON [InterruptionsTransport] ([CoutIncident]);
CREATE INDEX [WDIDX_InterruptionsTransport_MontantEND] ON [InterruptionsTransport] ([MontantEND]);
CREATE INDEX [WDIDX_InterruptionsTransport_Service] ON [InterruptionsTransport] ([Service]);
CREATE INDEX [WDIDX_InterruptionsTransport_Login] ON [InterruptionsTransport] ([Login]);
CREATE INDEX [WDIDX_InterruptionsTransport_CoutTotalIncident] ON [InterruptionsTransport] ([CoutTotalIncident]);
CREATE INDEX [WDIDX_InterruptionsTransport_PrixEnd] ON [InterruptionsTransport] ([PrixEnd]);
CREATE INDEX [WDIDX_InterruptionsTransport_DistancePrelocalisee] ON [InterruptionsTransport] ([DistancePrelocalisee]);
CREATE INDEX [WDIDX_InterruptionsTransport_PinstTi] ON [InterruptionsTransport] ([PinstTi]);
CREATE INDEX [WDIDX_InterruptionsTransport_PM] ON [InterruptionsTransport] ([PM]);
CREATE INDEX [WDIDX_InterruptionsTransport_Kum] ON [InterruptionsTransport] ([Kum]);
CREATE INDEX [WDIDX_InterruptionsTransport_Pinstf] ON [InterruptionsTransport] ([Pinstf]);
CREATE INDEX [WDIDX_InterruptionsTransport_Annee] ON [InterruptionsTransport] ([Annee]);
CREATE INDEX [WDIDX_InterruptionsTransport_MoisLettre] ON [InterruptionsTransport] ([MoisLettre]);
CREATE INDEX [WDIDX_InterruptionsTransport_Semaine] ON [InterruptionsTransport] ([Semaine]);
CREATE INDEX [WDIDX_InterruptionsTransport_Cause] ON [InterruptionsTransport] ([Cause]);
CREATE INDEX [WDIDX_InterruptionsTransport_Sieges] ON [InterruptionsTransport] ([Sieges]);
CREATE INDEX [WDIDX_InterruptionsTransport_PosteSource] ON [InterruptionsTransport] ([PosteSource]);
CREATE INDEX [WDIDX_InterruptionsTransport_Nature] ON [InterruptionsTransport] ([Nature]);
CREATE INDEX [WDIDX_InterruptionsTransport_Signalisation] ON [InterruptionsTransport] ([Signalisation]);
CREATE INDEX [WDIDX_InterruptionsTransport_TensionPrimaire] ON [InterruptionsTransport] ([TensionPrimaire]);
CREATE INDEX [WDIDX_InterruptionsTransport_Feeder] ON [InterruptionsTransport] ([Feeder]);
CREATE INDEX [WDIDX_InterruptionsTransport_codeinterruption] ON [InterruptionsTransport] ([codeinterruption]);
CREATE INDEX [WDIDX_InterruptionsTransport_Directionimputable] ON [InterruptionsTransport] ([Directionimputable]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDEquipements] ON [InterruptionsTransport] ([IDEquipements]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDSourceEquipement] ON [InterruptionsTransport] ([IDSourceEquipement]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDPosteLigne] ON [InterruptionsTransport] ([IDPosteLigne]);
CREATE INDEX [WDIDX_InterruptionsTransport_Tension] ON [InterruptionsTransport] ([Tension]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDTypeEND] ON [InterruptionsTransport] ([IDTypeEND]);
CREATE INDEX [WDIDX_InterruptionsTransport_IDCentrale] ON [InterruptionsTransport] ([IDCentrale]);
CREATE INDEX [WDIDX_InterruptionsTransport_FeederDateApparition] ON [InterruptionsTransport] ([DateApparition],[heureApparition]);

-- Création de la table Lieux
CREATE TABLE [Lieux] (
    [IDLieux] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Lieu] VARCHAR(50)  NOT NULL  UNIQUE );

-- Création de la table localite_senegal
CREATE TABLE [dbo.localite_senegal] (
    [identification] NVARCHAR(100) DEFAULT NULL,
    [region] NVARCHAR(100) DEFAULT NULL,
    [departement] NVARCHAR(100) DEFAULT NULL,
    [ville_commune] NVARCHAR(100) DEFAULT NULL,
    [commune] NVARCHAR(100) DEFAULT NULL,
    [quartier] NVARCHAR(200) DEFAULT NULL,
    [concession] INTEGER DEFAULT NULL,
    [population] INTEGER DEFAULT NULL,
    [longitude] NUMERIC(10,8) DEFAULT NULL,
    [latitude] NUMERIC(10,8) DEFAULT NULL,
    [id] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL );

-- Création de la table localite_senegal_Postes
CREATE TABLE [localite_senegal_Postes] (
    [IDPostes] NUMERIC(19,0) ,
    [Id] INTEGER );
CREATE INDEX [WDIDX_localite_senegal_Postes_IDPostes] ON [localite_senegal_Postes] ([IDPostes]);
CREATE INDEX [WDIDX_localite_senegal_Postes_Id] ON [localite_senegal_Postes] ([Id]);
CREATE UNIQUE INDEX [WDIDX_localite_senegal_Postes_Id_IDPostes] ON [localite_senegal_Postes] ([Id],[IDPostes]);

-- Création de la table Longueur_Reseau_SIG
CREATE TABLE [Longueur_Reseau_SIG] (
    [IDLongueur_Reseau_SIG] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Feeder] VARCHAR(50) ,
    [DateDebut] DATETIME ,
    [Longueur] INTEGER DEFAULT 0,
    [IDFeeder] NUMERIC(19,0) ,
    [DateFin] DATETIME );
CREATE INDEX [WDIDX_Longueur_Reseau_SIG_IDFeeder] ON [Longueur_Reseau_SIG] ([IDFeeder]);

-- Création de la table LongueurReseau
CREATE TABLE [LongueurReseau] (
    [IDLongueurReseau] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [longueurReseau] INTEGER DEFAULT 0,
    [DateDebut] DATETIME ,
    [DateFin] DATETIME ,
    [IDResponsable] NUMERIC(19,0) );
CREATE INDEX [WDIDX_LongueurReseau_DateDebut] ON [LongueurReseau] ([DateDebut]);
CREATE INDEX [WDIDX_LongueurReseau_DateFin] ON [LongueurReseau] ([DateFin]);
CREATE INDEX [WDIDX_LongueurReseau_IDResponsable] ON [LongueurReseau] ([IDResponsable]);

-- Création de la table NAPT
CREATE TABLE [NAPT] (
    [Num] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [NAPT] VARCHAR(50) DEFAULT '0',
    [Debut_tvx] DATETIME ,
    [Duree_Jrs] INTEGER DEFAULT 0,
    [Consistance_des_travaux] NVARCHAR(1000) ,
    [Observations] VARCHAR(1000) ,
    [Fin_napt] DATETIME ,
    [Indications_charge_consignation] VARCHAR(1000) ,
    [Heure_debut] DATETIME ,
    [Heure_fin] DATETIME ,
    [Heure_Remise_Exploitation] DATETIME ,
    [Delai_maxi_restitution] VARCHAR(50) DEFAULT '0',
    [Heure_retrait_exploitation] DATETIME ,
    [Prenom_Nom_Redacteur] VARCHAR(255) ,
    [Fonction_redacteur] VARCHAR(255) ,
    [Prenom_Nom_controleur] VARCHAR(255) ,
    [Fonction_Controleur] VARCHAR(50) ,
    [Prenom_Nom_Valideur] VARCHAR(50) ,
    [Fonction_Valideur] VARCHAR(50) ,
    [Prenom_Nom_Charge_Travaux] VARCHAR(50) ,
    [Adresse_Charge_Travaux] VARCHAR(1000) ,
    [fonction_Charge] VARCHAR(50) ,
    [Poste_source_a_consigner] VARCHAR(255) ,
    [Feeder_a_consigner] VARCHAR(50) ,
    [troncon_a_consigner] TEXT ,
    [Prenom_nom_demandeur] VARCHAR(50) ,
    [Prenom_nom_charge_consignation] VARCHAR(50) ,
    [Fonction_charge_consignation] VARCHAR(50) ,
    [Adresse_charge_consignation] VARCHAR(1000) ,
    [Adresse_demandeur] VARCHAR(50) ,
    [Unite_demandeur] VARCHAR(50) ,
    [Installation_a_consigner] VARCHAR(1000) ,
    [Tel_charge_Consignation] VARCHAR(50) ,
    [Tel_charge_Travaux] VARCHAR(50) ,
    [CODE] VARCHAR(50) ,
    [PosteSource] VARCHAR(255) ,
    [Feeder] VARCHAR(255) ,
    [NoeudAmont] VARCHAR(255) ,
    [NoeudAval] VARCHAR(255) ,
    [TypeConsignation] BIT DEFAULT 0,
    [Prenom_charge_travaux] VARCHAR(50) ,
    [exploitation] VARCHAR(50) ,
    [Feeder1] VARCHAR(255) ,
    [Feeder2] VARCHAR(255) ,
    [enregistrement] DATETIME ,
    [Modification] DATETIME ,
    [SaisiePar] VARCHAR(50) ,
    [ModifierPar] INTEGER DEFAULT 0,
    [shema] VARCHAR(255) );
CREATE INDEX [WDIDX_NAPT_NAPT] ON [NAPT] ([NAPT]);
CREATE INDEX [WDIDX_NAPT_Debut_tvx] ON [NAPT] ([Debut_tvx]);
CREATE INDEX [WDIDX_NAPT_Observations] ON [NAPT] ([Observations]);
CREATE INDEX [WDIDX_NAPT_Fin_napt] ON [NAPT] ([Fin_napt]);
CREATE INDEX [WDIDX_NAPT_Heure_debut] ON [NAPT] ([Heure_debut]);
CREATE INDEX [WDIDX_NAPT_Heure_fin] ON [NAPT] ([Heure_fin]);
CREATE INDEX [WDIDX_NAPT_Prenom_Nom_Redacteur] ON [NAPT] ([Prenom_Nom_Redacteur]);
CREATE INDEX [WDIDX_NAPT_Prenom_Nom_controleur] ON [NAPT] ([Prenom_Nom_controleur]);
CREATE INDEX [WDIDX_NAPT_Prenom_Nom_Valideur] ON [NAPT] ([Prenom_Nom_Valideur]);
CREATE INDEX [WDIDX_NAPT_Prenom_nom_demandeur] ON [NAPT] ([Prenom_nom_demandeur]);
CREATE INDEX [WDIDX_NAPT_Prenom_nom_charge_consignation] ON [NAPT] ([Prenom_nom_charge_consignation]);
CREATE INDEX [WDIDX_NAPT_Adresse_charge_consignation] ON [NAPT] ([Adresse_charge_consignation]);
CREATE INDEX [WDIDX_NAPT_Adresse_demandeur] ON [NAPT] ([Adresse_demandeur]);
CREATE INDEX [WDIDX_NAPT_Unite_demandeur] ON [NAPT] ([Unite_demandeur]);
CREATE INDEX [WDIDX_NAPT_CODE] ON [NAPT] ([CODE]);
CREATE INDEX [WDIDX_NAPT_PosteSource] ON [NAPT] ([PosteSource]);
CREATE INDEX [WDIDX_NAPT_Feeder] ON [NAPT] ([Feeder]);
CREATE INDEX [WDIDX_NAPT_NoeudAmont] ON [NAPT] ([NoeudAmont]);
CREATE INDEX [WDIDX_NAPT_NoeudAval] ON [NAPT] ([NoeudAval]);
CREATE INDEX [WDIDX_NAPT_Prenom_charge_travaux] ON [NAPT] ([Prenom_charge_travaux]);
CREATE INDEX [WDIDX_NAPT_exploitation] ON [NAPT] ([exploitation]);

-- Création de la table Natures
CREATE TABLE [Natures] (
    [NaturePresumee] VARCHAR(255)  UNIQUE ,
    [IDNature] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Transport] BIT DEFAULT 0);
CREATE INDEX [WDIDX_Natures_Transport] ON [Natures] ([Transport]);

-- Création de la table Noeud_SIG
CREATE TABLE [Noeud_SIG] (
    [IDNoeud_SIG] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL ,
    [NOM] VARCHAR(255) DEFAULT NULL,
    [NOMFEEDER] VARCHAR(255) DEFAULT NULL,
    [SSTATION] VARCHAR(255) DEFAULT NULL,
    [DELEGATION] VARCHAR(255) DEFAULT NULL,
    [REGION] VARCHAR(255) DEFAULT NULL,
    [CORX] FLOAT DEFAULT NULL,
    [CORY] FLOAT DEFAULT NULL,
    [CATEGORIE] VARCHAR(255) DEFAULT NULL,
    [PUISSANCE_] FLOAT DEFAULT NULL,
    [FAMILLE_PO] VARCHAR(255) DEFAULT NULL,
    [CELLULE] VARCHAR(255) DEFAULT NULL,
    [IDTypeNoeud_SIG] NUMERIC(19,0) DEFAULT 0,
    [FID] INTEGER  NOT NULL  UNIQUE  DEFAULT 0);
CREATE INDEX [WDIDX_Noeud_SIG_NOM] ON [Noeud_SIG] ([NOM]);
CREATE INDEX [WDIDX_Noeud_SIG_NOMFEEDER] ON [Noeud_SIG] ([NOMFEEDER]);
CREATE INDEX [WDIDX_Noeud_SIG_SSTATION] ON [Noeud_SIG] ([SSTATION]);
CREATE INDEX [WDIDX_Noeud_SIG_DELEGATION] ON [Noeud_SIG] ([DELEGATION]);
CREATE INDEX [WDIDX_Noeud_SIG_REGION] ON [Noeud_SIG] ([REGION]);
CREATE INDEX [WDIDX_Noeud_SIG_CORX] ON [Noeud_SIG] ([CORX]);
CREATE INDEX [WDIDX_Noeud_SIG_CORY] ON [Noeud_SIG] ([CORY]);
CREATE INDEX [WDIDX_Noeud_SIG_CATEGORIE] ON [Noeud_SIG] ([CATEGORIE]);
CREATE INDEX [WDIDX_Noeud_SIG_PUISSANCE_] ON [Noeud_SIG] ([PUISSANCE_]);
CREATE INDEX [WDIDX_Noeud_SIG_FAMILLE_PO] ON [Noeud_SIG] ([FAMILLE_PO]);
CREATE INDEX [WDIDX_Noeud_SIG_CELLULE] ON [Noeud_SIG] ([CELLULE]);
CREATE INDEX [WDIDX_Noeud_SIG_IDTypeNoeud_SIG] ON [Noeud_SIG] ([IDTypeNoeud_SIG]);

-- Création de la table Noeuds
CREATE TABLE [Noeuds] (
    [IDNoeuds] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Noeuds] VARCHAR(50) ,
    [IDPostes] NUMERIC(19,0) ,
    [IDAAT] NUMERIC(19,0) ,
    [IDPosteSource] NUMERIC(19,0) );
CREATE INDEX [WDIDX_Noeuds_IDPostes] ON [Noeuds] ([IDPostes]);
CREATE INDEX [WDIDX_Noeuds_IDAAT] ON [Noeuds] ([IDAAT]);
CREATE INDEX [WDIDX_Noeuds_IDPosteSource] ON [Noeuds] ([IDPosteSource]);
CREATE UNIQUE INDEX [WDIDX_Noeuds_IDPostesIDAAT] ON [Noeuds] ([IDPostes],[IDAAT],[IDPosteSource]);

-- Création de la table NombreClientMois
CREATE TABLE [NombreClientMois] (
    [IDClientAnnee] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Annee] INTEGER DEFAULT 0,
    [Nombreclient] INTEGER DEFAULT 0,
    [SAIFI] FLOAT DEFAULT 0,
    [SAIDI] FLOAT DEFAULT 0,
    [MoisNumerique] VARCHAR(50) DEFAULT '0',
    [MoisLettre] VARCHAR(50) ,
    [ID_Service] NUMERIC(19,0) DEFAULT 0,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0,
    [IDRegions] NUMERIC(19,0) DEFAULT 0,
    [IDAgence] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_NombreClientMois_Annee] ON [NombreClientMois] ([Annee]);
CREATE INDEX [WDIDX_NombreClientMois_MoisNumerique] ON [NombreClientMois] ([MoisNumerique]);
CREATE INDEX [WDIDX_NombreClientMois_MoisLettre] ON [NombreClientMois] ([MoisLettre]);
CREATE INDEX [WDIDX_NombreClientMois_ID_Service] ON [NombreClientMois] ([ID_Service]);
CREATE INDEX [WDIDX_NombreClientMois_IDDelegation] ON [NombreClientMois] ([IDDelegation]);
CREATE INDEX [WDIDX_NombreClientMois_IDRegions] ON [NombreClientMois] ([IDRegions]);
CREATE INDEX [WDIDX_NombreClientMois_IDAgence] ON [NombreClientMois] ([IDAgence]);
CREATE UNIQUE INDEX [WDIDX_NombreClientMois_MoisNumeriqueAnneeIDDelegationIDRegionsIDAgence] ON [NombreClientMois] ([MoisNumerique],[Annee],[IDDelegation],[IDRegions],[IDAgence]);

-- Création de la table O_M
CREATE TABLE [O_M] (
    [IDO_M] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Nom_O_M] VARCHAR(50) );

-- Création de la table POSTEAJOUR$
CREATE TABLE [POSTEAJOUR$] (
    [IDPostes] FLOAT  UNIQUE  DEFAULT NULL,
    [Poste] NVARCHAR(255) DEFAULT NULL,
    [Feeder] NVARCHAR(255) DEFAULT NULL,
    [IDFeeder] FLOAT DEFAULT NULL,
    [Service] NVARCHAR(255) DEFAULT NULL,
    [ID_Service] FLOAT DEFAULT NULL,
    [Observation] NVARCHAR(255) DEFAULT NULL);
CREATE INDEX [WDIDX_POSTEAJOUR$_IDFeeder] ON [POSTEAJOUR$] ([IDFeeder]);
CREATE INDEX [WDIDX_POSTEAJOUR$_ID_Service] ON [POSTEAJOUR$] ([ID_Service]);

-- Création de la table PosteClient
CREATE TABLE [PosteClient] (
    [IDPosteClient] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [groupesecteur] VARCHAR(50) ,
    [IDPostes] NUMERIC(19,0) DEFAULT 0,
    [Codereference] VARCHAR(50) ,
    [Nombreclient] INTEGER DEFAULT 0,
    [bordereau] VARCHAR(50) ,
    [Poste] VARCHAR(255) ,
    [Agence] VARCHAR(50) ,
    [Codeagence] INTEGER ,
    [UR] VARCHAR(50) ,
    [PNDPCE_NSPC] VARCHAR(50) ,
    [Agent_Modif] VARCHAR(50) DEFAULT '0',
    [Agent_Valide] VARCHAR(50) );
CREATE INDEX [WDIDX_PosteClient_groupesecteur] ON [PosteClient] ([groupesecteur]);
CREATE INDEX [WDIDX_PosteClient_IDPostes] ON [PosteClient] ([IDPostes]);
CREATE INDEX [WDIDX_PosteClient_Codereference] ON [PosteClient] ([Codereference]);
CREATE INDEX [WDIDX_PosteClient_bordereau] ON [PosteClient] ([bordereau]);
CREATE INDEX [WDIDX_PosteClient_Poste] ON [PosteClient] ([Poste]);
CREATE INDEX [WDIDX_PosteClient_Agence] ON [PosteClient] ([Agence]);
CREATE INDEX [WDIDX_PosteClient_Codeagence] ON [PosteClient] ([Codeagence]);
CREATE INDEX [WDIDX_PosteClient_UR] ON [PosteClient] ([UR]);

-- Création de la table PosteClient_Avalider
CREATE TABLE [PosteClient1] (
    [IDPosteClient] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [groupesecteur] VARCHAR(50) ,
    [IDPostes] NUMERIC(19,0) DEFAULT 0,
    [Codereference] VARCHAR(50) ,
    [Nombreclient] INTEGER DEFAULT 0,
    [bordereau] VARCHAR(50) ,
    [Poste] VARCHAR(255) ,
    [Agence] VARCHAR(50) ,
    [Codeagence] INTEGER ,
    [UR] VARCHAR(50) ,
    [PNDPCE_NSPC] VARCHAR(50) ,
    [Agent_Modif] VARCHAR(50) DEFAULT '0',
    [Agent_Valide] VARCHAR(50) ,
    [etat_modification] VARCHAR(50) ,
    [Date_de_Modification] DATETIME );
CREATE INDEX [WDIDX_PosteClient_Avalider_groupesecteur] ON [PosteClient1] ([groupesecteur]);
CREATE INDEX [WDIDX_PosteClient_Avalider_IDPostes] ON [PosteClient1] ([IDPostes]);
CREATE INDEX [WDIDX_PosteClient_Avalider_Codereference] ON [PosteClient1] ([Codereference]);
CREATE INDEX [WDIDX_PosteClient_Avalider_bordereau] ON [PosteClient1] ([bordereau]);
CREATE INDEX [WDIDX_PosteClient_Avalider_Poste] ON [PosteClient1] ([Poste]);
CREATE INDEX [WDIDX_PosteClient_Avalider_Agence] ON [PosteClient1] ([Agence]);
CREATE INDEX [WDIDX_PosteClient_Avalider_Codeagence] ON [PosteClient1] ([Codeagence]);
CREATE INDEX [WDIDX_PosteClient_Avalider_UR] ON [PosteClient1] ([UR]);

-- Création de la table PosteInterruption
CREATE TABLE [PosteInterruption] (
    [IDPosteInterruption] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDPostes] NUMERIC(19,0) DEFAULT 0,
    [SAIFI] FLOAT DEFAULT 0,
    [SAIDI] FLOAT DEFAULT 0,
    [NInterruption] NUMERIC(19,0) DEFAULT 0,
    [Posteconcerne] VARCHAR(255) ,
    [Feederconcerne] VARCHAR(255) ,
    [NInterruption_saisi] NUMERIC(20,0) DEFAULT 0,
    [nombreclientposteEstime] INTEGER DEFAULT 0,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [UR] VARCHAR(50) ,
    [IDAgences] NUMERIC(19,0) DEFAULT 0,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0,
    [ID_Service] NUMERIC(19,0) DEFAULT 0,
    [IDRegions] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_PosteInterruption_IDPostes] ON [PosteInterruption] ([IDPostes]);
CREATE INDEX [WDIDX_PosteInterruption_NInterruption] ON [PosteInterruption] ([NInterruption]);
CREATE INDEX [WDIDX_PosteInterruption_Posteconcerne] ON [PosteInterruption] ([Posteconcerne]);
CREATE INDEX [WDIDX_PosteInterruption_Feederconcerne] ON [PosteInterruption] ([Feederconcerne]);
CREATE INDEX [WDIDX_PosteInterruption_NInterruption_saisi] ON [PosteInterruption] ([NInterruption_saisi]);
CREATE INDEX [WDIDX_PosteInterruption_IDFeeder] ON [PosteInterruption] ([IDFeeder]);
CREATE INDEX [WDIDX_PosteInterruption_UR] ON [PosteInterruption] ([UR]);
CREATE INDEX [WDIDX_PosteInterruption_IDAgences] ON [PosteInterruption] ([IDAgences]);
CREATE INDEX [WDIDX_PosteInterruption_IDDelegation] ON [PosteInterruption] ([IDDelegation]);
CREATE INDEX [WDIDX_PosteInterruption_ID_Service] ON [PosteInterruption] ([ID_Service]);
CREATE INDEX [WDIDX_PosteInterruption_IDRegions] ON [PosteInterruption] ([IDRegions]);
CREATE UNIQUE INDEX [WDIDX_PosteInterruption_NInterruptionIDPostesUR] ON [PosteInterruption] ([NInterruption],[IDPostes],[UR]);

-- Création de la table PosteInterruption_Histo
CREATE TABLE [PosteInterruption_Histo] (
    [IDPosteInterruption] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDPostes] NUMERIC(19,0) DEFAULT 0,
    [SAIFI] FLOAT DEFAULT 0,
    [SAIDI] FLOAT DEFAULT 0,
    [NInterruption] NUMERIC(19,0) DEFAULT 0,
    [Posteconcerne] VARCHAR(255) ,
    [Feederconcerne] VARCHAR(255) ,
    [NInterruption_saisi] NUMERIC(20,0) DEFAULT 0,
    [nombreclientposteEstime] INTEGER DEFAULT 0,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [UR] VARCHAR(50) ,
    [IDAgences] NUMERIC(19,0) DEFAULT 0,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0,
    [ID_Service] NUMERIC(19,0) DEFAULT 0,
    [IDRegions] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_PosteInterruption_Histo_IDPostes] ON [PosteInterruption_Histo] ([IDPostes]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_NInterruption] ON [PosteInterruption_Histo] ([NInterruption]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_Posteconcerne] ON [PosteInterruption_Histo] ([Posteconcerne]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_Feederconcerne] ON [PosteInterruption_Histo] ([Feederconcerne]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_NInterruption_saisi] ON [PosteInterruption_Histo] ([NInterruption_saisi]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_IDFeeder] ON [PosteInterruption_Histo] ([IDFeeder]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_UR] ON [PosteInterruption_Histo] ([UR]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_IDAgences] ON [PosteInterruption_Histo] ([IDAgences]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_IDDelegation] ON [PosteInterruption_Histo] ([IDDelegation]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_ID_Service] ON [PosteInterruption_Histo] ([ID_Service]);
CREATE INDEX [WDIDX_PosteInterruption_Histo_IDRegions] ON [PosteInterruption_Histo] ([IDRegions]);
CREATE UNIQUE INDEX [WDIDX_PosteInterruption_Histo_NInterruptionIDPostesUR] ON [PosteInterruption_Histo] ([NInterruption],[IDPostes],[UR]);

-- Création de la table PosteLigne
CREATE TABLE [PosteLigne] (
    [IDPosteLigne] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [PosteLigne] VARCHAR(50)  UNIQUE );

-- Création de la table PosteNonTrouvee
CREATE TABLE [Agence_A_Charger1] (
    [NOM] VARCHAR(255) DEFAULT NULL,
    [IMATNOEU] VARCHAR(255) DEFAULT NULL,
    [NOMFEEDER] VARCHAR(255) DEFAULT NULL,
    [IMATFEEDER] VARCHAR(255) DEFAULT NULL,
    [SSTATION] VARCHAR(255) DEFAULT NULL,
    [DELEGATION] VARCHAR(255) DEFAULT NULL,
    [REGION] VARCHAR(255) DEFAULT NULL,
    [DEPARTEM] VARCHAR(255) DEFAULT NULL,
    [ARRONDIS] VARCHAR(255) DEFAULT NULL,
    [COMMUNE] VARCHAR(255) DEFAULT NULL,
    [NTENSION] FLOAT DEFAULT NULL,
    [CATEGORIE] VARCHAR(255) DEFAULT NULL,
    [PUISSANCE_] FLOAT DEFAULT NULL,
    [FAMILLE_PO] VARCHAR(255) DEFAULT NULL,
    [AP] VARCHAR(255) DEFAULT NULL);

-- Création de la table Postes
CREATE TABLE [Postes] (
    [IDPostes] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Poste] VARCHAR(255) ,
    [typeposte] VARCHAR(50) ,
    [natureposte] VARCHAR(50) ,
    [puissanceTransfo] INTEGER DEFAULT 0,
    [typereseau] VARCHAR(50) ,
    [secteurconducteur] VARCHAR(50) ,
    [Feeder] VARCHAR(255) ,
    [longitude] NUMERIC(10,8) DEFAULT 0,
    [latitude] NUMERIC(10,8) ,
    [PosteSource] VARCHAR(255) ,
    [Observation] TEXT ,
    [Region] VARCHAR(50) ,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [TensionPrimaire] REAL DEFAULT 0,
    [doublon] BIT DEFAULT 0,
    [UR] VARCHAR(50) ,
    [PNDPCE_NSPC] VARCHAR(50) ,
    [ID_Service] NUMERIC(19,0) DEFAULT 0,
    [IDType_Cellule] NUMERIC(19,0) DEFAULT 0,
    [FID] INTEGER );
CREATE INDEX [WDIDX_Postes_Poste] ON [Postes] ([Poste]);
CREATE INDEX [WDIDX_Postes_typeposte] ON [Postes] ([typeposte]);
CREATE INDEX [WDIDX_Postes_natureposte] ON [Postes] ([natureposte]);
CREATE INDEX [WDIDX_Postes_typereseau] ON [Postes] ([typereseau]);
CREATE INDEX [WDIDX_Postes_secteurconducteur] ON [Postes] ([secteurconducteur]);
CREATE INDEX [WDIDX_Postes_Feeder] ON [Postes] ([Feeder]);
CREATE INDEX [WDIDX_Postes_PosteSource] ON [Postes] ([PosteSource]);
CREATE INDEX [WDIDX_Postes_Observation] ON [Postes] ([Observation]);
CREATE INDEX [WDIDX_Postes_Region] ON [Postes] ([Region]);
CREATE INDEX [WDIDX_Postes_IDFeeder] ON [Postes] ([IDFeeder]);
CREATE INDEX [WDIDX_Postes_TensionPrimaire] ON [Postes] ([TensionPrimaire]);
CREATE INDEX [WDIDX_Postes_doublon] ON [Postes] ([doublon]);
CREATE INDEX [WDIDX_Postes_UR] ON [Postes] ([UR]);
CREATE INDEX [WDIDX_Postes_ID_Service] ON [Postes] ([ID_Service]);
CREATE INDEX [WDIDX_Postes_IDType_Cellule] ON [Postes] ([IDType_Cellule]);
CREATE INDEX [WDIDX_Postes_FID] ON [Postes] ([FID]);

-- Création de la table POSTES_ET_PIQUAGES_DAKAR$
CREATE TABLE ['POSTES ET PIQUAGES DAKAR$'] (
    [FID] FLOAT DEFAULT NULL,
    [NOM] VARCHAR(255) DEFAULT NULL,
    [NOMFEEDER] VARCHAR(255) DEFAULT NULL,
    [SSTATION] VARCHAR(255) DEFAULT NULL,
    [DELEGATION] VARCHAR(255) DEFAULT NULL,
    [REGION] VARCHAR(255) DEFAULT NULL,
    [CORX] FLOAT DEFAULT NULL,
    [CORY] FLOAT DEFAULT NULL,
    [CATEGORIE] VARCHAR(255) DEFAULT NULL,
    [PUISSANCE_] FLOAT DEFAULT NULL,
    [FAMILLE_PO] VARCHAR(255) DEFAULT NULL,
    [CELLULE] VARCHAR(255) DEFAULT NULL,
    [IDPoste_et_Piques_Dakar] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL ,
    [IDTypeNoeud_SIG] NUMERIC(19,0) );
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_FID] ON ['POSTES ET PIQUAGES DAKAR$'] ([FID]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_NOM] ON ['POSTES ET PIQUAGES DAKAR$'] ([NOM]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_NOMFEEDER] ON ['POSTES ET PIQUAGES DAKAR$'] ([NOMFEEDER]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_SSTATION] ON ['POSTES ET PIQUAGES DAKAR$'] ([SSTATION]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_DELEGATION] ON ['POSTES ET PIQUAGES DAKAR$'] ([DELEGATION]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_REGION] ON ['POSTES ET PIQUAGES DAKAR$'] ([REGION]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_CORX] ON ['POSTES ET PIQUAGES DAKAR$'] ([CORX]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_CORY] ON ['POSTES ET PIQUAGES DAKAR$'] ([CORY]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_CATEGORIE] ON ['POSTES ET PIQUAGES DAKAR$'] ([CATEGORIE]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_PUISSANCE_] ON ['POSTES ET PIQUAGES DAKAR$'] ([PUISSANCE_]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_FAMILLE_PO] ON ['POSTES ET PIQUAGES DAKAR$'] ([FAMILLE_PO]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_CELLULE] ON ['POSTES ET PIQUAGES DAKAR$'] ([CELLULE]);
CREATE INDEX [WDIDX_POSTES_ET_PIQUAGES_DAKAR$_IDTypeNoeud_SIG] ON ['POSTES ET PIQUAGES DAKAR$'] ([IDTypeNoeud_SIG]);

-- Création de la table Postes_Troncon
CREATE TABLE [Postes_Troncon] (
    [IDPostes] NUMERIC(19,0)  NOT NULL ,
    [IDTroncon] NUMERIC(19,0)  NOT NULL );
CREATE INDEX [WDIDX_Postes_Troncon_IDPostes] ON [Postes_Troncon] ([IDPostes]);
CREATE INDEX [WDIDX_Postes_Troncon_IDTroncon] ON [Postes_Troncon] ([IDTroncon]);
CREATE UNIQUE INDEX [WDIDX_Postes_Troncon_IDTroncon_IDPostes] ON [Postes_Troncon] ([IDTroncon],[IDPostes]);

-- Création de la table POSTESANSNOEUD$
CREATE TABLE [POSTESANSNOEUD$] (
    [IDPostes] FLOAT  UNIQUE  DEFAULT NULL,
    [Poste] NVARCHAR(255) DEFAULT NULL,
    [typeposte] NVARCHAR(255) DEFAULT NULL,
    [natureposte] NVARCHAR(255) DEFAULT NULL,
    [puissanceTransfo] FLOAT DEFAULT NULL,
    [typereseau] NVARCHAR(255) DEFAULT NULL,
    [secteurconducteur] NVARCHAR(255) DEFAULT NULL,
    [Feeder] NVARCHAR(255) DEFAULT NULL,
    [PosteSource] NVARCHAR(255) DEFAULT NULL,
    [Observation] NVARCHAR(255) DEFAULT NULL,
    [Region] NVARCHAR(255) DEFAULT NULL,
    [IDFeeder] FLOAT DEFAULT NULL,
    [TensionPrimaire] FLOAT DEFAULT NULL,
    [doublon] FLOAT DEFAULT NULL,
    [UR] NVARCHAR(255) DEFAULT NULL,
    [PNDPCE_NSPC] NVARCHAR(255) DEFAULT NULL,
    [ID_Service] FLOAT DEFAULT NULL,
    [IDType_Cellule] FLOAT DEFAULT NULL);
CREATE INDEX [WDIDX_POSTESANSNOEUD$_IDFeeder] ON [POSTESANSNOEUD$] ([IDFeeder]);
CREATE INDEX [WDIDX_POSTESANSNOEUD$_ID_Service] ON [POSTESANSNOEUD$] ([ID_Service]);

-- Création de la table PosteSource_SIG
CREATE TABLE [PosteSource_SIG] (
    [FID] FLOAT  NOT NULL  UNIQUE  DEFAULT NULL,
    [PosteSource] VARCHAR(255) DEFAULT NULL,
    [IDPosteSource_SIG] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL );
CREATE INDEX [WDIDX_PosteSource_SIG_PosteSource] ON [PosteSource_SIG] ([PosteSource]);

-- Création de la table PostesSources
CREATE TABLE [PostesSources] (
    [PosteSource] VARCHAR(255)  NOT NULL  UNIQUE ,
    [Service] VARCHAR(255) ,
    [CR] INTEGER DEFAULT 0,
    [TensionPrimaire] REAL DEFAULT 0,
    [TypeSource] VARCHAR(50) ,
    [CoordoX_GPRS] VARCHAR(50) ,
    [CoordoY_GPRS] VARCHAR(50) ,
    [DateMiseService] DATETIME ,
    [Jeubarre] VARCHAR(50) ,
    [NombrecellulesHTA] TINYINT DEFAULT 0,
    [NombreTransfo] TINYINT DEFAULT 0,
    [observation] TEXT ,
    [TensionSecondaire] VARCHAR(50) ,
    [Region] VARCHAR(50) ,
    [IDTypeEquipement] NUMERIC(19,0) DEFAULT 0,
    [IDPosteSource] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [FID] FLOAT ,
    [IDO_M] NUMERIC(19,0) );
CREATE INDEX [WDIDX_PostesSources_Service] ON [PostesSources] ([Service]);
CREATE INDEX [WDIDX_PostesSources_CR] ON [PostesSources] ([CR]);
CREATE INDEX [WDIDX_PostesSources_TypeSource] ON [PostesSources] ([TypeSource]);
CREATE INDEX [WDIDX_PostesSources_CoordoX_GPRS] ON [PostesSources] ([CoordoX_GPRS]);
CREATE INDEX [WDIDX_PostesSources_CoordoY_GPRS] ON [PostesSources] ([CoordoY_GPRS]);
CREATE INDEX [WDIDX_PostesSources_Jeubarre] ON [PostesSources] ([Jeubarre]);
CREATE INDEX [WDIDX_PostesSources_observation] ON [PostesSources] ([observation]);
CREATE INDEX [WDIDX_PostesSources_TensionSecondaire] ON [PostesSources] ([TensionSecondaire]);
CREATE INDEX [WDIDX_PostesSources_Region] ON [PostesSources] ([Region]);
CREATE INDEX [WDIDX_PostesSources_IDTypeEquipement] ON [PostesSources] ([IDTypeEquipement]);
CREATE INDEX [WDIDX_PostesSources_FID] ON [PostesSources] ([FID]);
CREATE INDEX [WDIDX_PostesSources_IDO_M] ON [PostesSources] ([IDO_M]);

-- Création de la table Prestataire
CREATE TABLE [Prestataire] (
    [IDPrestataire] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [NomPrestataire] VARCHAR(50) );
CREATE INDEX [WDIDX_Prestataire_NomPrestataire] ON [Prestataire] ([NomPrestataire]);

-- Création de la table Propriétaire
CREATE TABLE [Propriétaire] (
    [IDPropriétaire] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL ,
    [NomProprietaire] VARCHAR(50) );

-- Création de la table Propritetaire_Ligne
CREATE TABLE [Propritetaire_Ligne] (
    [IDPropritetaire_Ligne] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Libelle_Proprietaire] VARCHAR(50) ,
    [Abrege_Proprietaire] VARCHAR(50) );
CREATE INDEX [WDIDX_Propritetaire_Ligne_Libelle_Proprietaire] ON [Propritetaire_Ligne] ([Libelle_Proprietaire]);
CREATE INDEX [WDIDX_Propritetaire_Ligne_Abrege_Proprietaire] ON [Propritetaire_Ligne] ([Abrege_Proprietaire]);

-- Création de la table Rapport
CREATE TABLE [Rapport] (
    [IDRapport] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Date] DATETIME ,
    [NInterruption] NUMERIC(19,0) DEFAULT 0,
    [Heuredebut] DATETIME ,
    [HeureFin] DATETIME ,
    [PuissanceCoupee] INTEGER DEFAULT 0,
    [ENDD] FLOAT DEFAULT 0,
    [dureeHeure] FLOAT DEFAULT 0,
    [Duree_Jrs] FLOAT DEFAULT 0,
    [Dureemn] NUMERIC(18,5) DEFAULT 0,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [TensionRegion] VARCHAR(50) ,
    [Cause] VARCHAR(255) DEFAULT '0',
    [Siege] VARCHAR(50) ,
    [Nature] VARCHAR(50) ,
    [DateApparition] DATETIME ,
    [DuréeSAIDI] FLOAT DEFAULT 0);
CREATE INDEX [WDIDX_Rapport_Date] ON [Rapport] ([Date]);
CREATE INDEX [WDIDX_Rapport_NInterruption] ON [Rapport] ([NInterruption]);
CREATE INDEX [WDIDX_Rapport_Heuredebut] ON [Rapport] ([Heuredebut]);
CREATE INDEX [WDIDX_Rapport_HeureFin] ON [Rapport] ([HeureFin]);
CREATE INDEX [WDIDX_Rapport_PuissanceCoupee] ON [Rapport] ([PuissanceCoupee]);
CREATE INDEX [WDIDX_Rapport_ENDD] ON [Rapport] ([ENDD]);
CREATE INDEX [WDIDX_Rapport_dureeHeure] ON [Rapport] ([dureeHeure]);
CREATE INDEX [WDIDX_Rapport_Duree_Jrs] ON [Rapport] ([Duree_Jrs]);
CREATE INDEX [WDIDX_Rapport_Dureemn] ON [Rapport] ([Dureemn]);
CREATE INDEX [WDIDX_Rapport_IDFeeder] ON [Rapport] ([IDFeeder]);
CREATE INDEX [WDIDX_Rapport_TensionRegion] ON [Rapport] ([TensionRegion]);
CREATE INDEX [WDIDX_Rapport_Cause] ON [Rapport] ([Cause]);
CREATE INDEX [WDIDX_Rapport_Siege] ON [Rapport] ([Siege]);
CREATE INDEX [WDIDX_Rapport_Nature] ON [Rapport] ([Nature]);
CREATE INDEX [WDIDX_Rapport_DateApparition] ON [Rapport] ([DateApparition]);
CREATE INDEX [WDIDX_Rapport_DuréeSAIDI] ON [Rapport] ([DuréeSAIDI]);

-- Création de la table RapportSAIFI
CREATE TABLE [RapportSAIFI] (
    [IDRapport] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Date] DATETIME ,
    [NInterruption] NUMERIC(19,0) DEFAULT 0,
    [IDRegions] NUMERIC(19,0) DEFAULT 0,
    [Heuredebut] DATETIME ,
    [HeureFin] DATETIME ,
    [PuissanceCoupee] INTEGER DEFAULT 0,
    [ENDD] FLOAT DEFAULT 0,
    [dureeHeure] FLOAT DEFAULT 0,
    [Duree_Jrs] FLOAT DEFAULT 0,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [TensionRegion] VARCHAR(50) ,
    [Cause] VARCHAR(255) DEFAULT '0',
    [Siege] VARCHAR(50) ,
    [Nature] VARCHAR(50) ,
    [DateApparition] DATETIME ,
    [DuréeSAIDI] FLOAT DEFAULT 0,
    [DateDebutTronc] DATETIME ,
    [DateFinTronc] DATETIME ,
    [HeuredebutTronc] DATETIME ,
    [HeureFinTronc] DATETIME ,
    [TypeClient] VARCHAR(50) ,
    [USAGE] VARCHAR(3) ,
    [STATUT] VARCHAR(1) ,
    [Agence] VARCHAR(50) ,
    [Groupe] VARCHAR(255) ,
    [bordereau] VARCHAR(50) ,
    [nombreclients] INTEGER DEFAULT 0,
    [Nombreclientimpacte] INTEGER DEFAULT 0,
    [SAIFI] FLOAT DEFAULT 0,
    [SAIDI] FLOAT DEFAULT 0,
    [Service] VARCHAR(255) ,
    [ID_Service] NUMERIC(19,0) DEFAULT 0,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_RapportSAIFI_Date] ON [RapportSAIFI] ([Date]);
CREATE INDEX [WDIDX_RapportSAIFI_NInterruption] ON [RapportSAIFI] ([NInterruption]);
CREATE INDEX [WDIDX_RapportSAIFI_IDRegions] ON [RapportSAIFI] ([IDRegions]);
CREATE INDEX [WDIDX_RapportSAIFI_Heuredebut] ON [RapportSAIFI] ([Heuredebut]);
CREATE INDEX [WDIDX_RapportSAIFI_HeureFin] ON [RapportSAIFI] ([HeureFin]);
CREATE INDEX [WDIDX_RapportSAIFI_PuissanceCoupee] ON [RapportSAIFI] ([PuissanceCoupee]);
CREATE INDEX [WDIDX_RapportSAIFI_ENDD] ON [RapportSAIFI] ([ENDD]);
CREATE INDEX [WDIDX_RapportSAIFI_dureeHeure] ON [RapportSAIFI] ([dureeHeure]);
CREATE INDEX [WDIDX_RapportSAIFI_Duree_Jrs] ON [RapportSAIFI] ([Duree_Jrs]);
CREATE INDEX [WDIDX_RapportSAIFI_IDFeeder] ON [RapportSAIFI] ([IDFeeder]);
CREATE INDEX [WDIDX_RapportSAIFI_TensionRegion] ON [RapportSAIFI] ([TensionRegion]);
CREATE INDEX [WDIDX_RapportSAIFI_Cause] ON [RapportSAIFI] ([Cause]);
CREATE INDEX [WDIDX_RapportSAIFI_Siege] ON [RapportSAIFI] ([Siege]);
CREATE INDEX [WDIDX_RapportSAIFI_Nature] ON [RapportSAIFI] ([Nature]);
CREATE INDEX [WDIDX_RapportSAIFI_DateApparition] ON [RapportSAIFI] ([DateApparition]);
CREATE INDEX [WDIDX_RapportSAIFI_DuréeSAIDI] ON [RapportSAIFI] ([DuréeSAIDI]);
CREATE INDEX [WDIDX_RapportSAIFI_TypeClient] ON [RapportSAIFI] ([TypeClient]);
CREATE INDEX [WDIDX_RapportSAIFI_Agence] ON [RapportSAIFI] ([Agence]);
CREATE INDEX [WDIDX_RapportSAIFI_Groupe] ON [RapportSAIFI] ([Groupe]);
CREATE INDEX [WDIDX_RapportSAIFI_bordereau] ON [RapportSAIFI] ([bordereau]);
CREATE INDEX [WDIDX_RapportSAIFI_Service] ON [RapportSAIFI] ([Service]);
CREATE INDEX [WDIDX_RapportSAIFI_ID_Service] ON [RapportSAIFI] ([ID_Service]);
CREATE INDEX [WDIDX_RapportSAIFI_IDDelegation] ON [RapportSAIFI] ([IDDelegation]);

-- Création de la table Redacteur
CREATE TABLE [Redacteur] (
    [IDRedacteur] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Prenom_Nom] VARCHAR(255) ,
    [Fonction_redacteur] VARCHAR(50) );

-- Création de la table Rédacteurs
CREATE TABLE [Rédacteurs] (
    [IDRédacteurs] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Prenom_Nom_Redacteur] VARCHAR(255)  NOT NULL  UNIQUE ,
    [Matricule] INTEGER DEFAULT 0,
    [Adresse] VARCHAR(50) ,
    [Telephone] VARCHAR(50) ,
    [Email] VARCHAR(50) ,
    [Login] VARCHAR(255) ,
    [motpasse] VARCHAR(50) ,
    [redacteur] VARCHAR(255)  UNIQUE ,
    [exploitation] VARCHAR(50) );
CREATE INDEX [WDIDX_Rédacteurs_Matricule] ON [Rédacteurs] ([Matricule]);
CREATE INDEX [WDIDX_Rédacteurs_Login] ON [Rédacteurs] ([Login]);
CREATE INDEX [WDIDX_Rédacteurs_exploitation] ON [Rédacteurs] ([exploitation]);

-- Création de la table ReferenceClient
CREATE TABLE [ReferenceClient] (
    [bordereau] VARCHAR(50) ,
    [groupesecteur] VARCHAR(50) ,
    [Nombreclient] INTEGER DEFAULT 0,
    [Codeagence] INTEGER ,
    [codereference] VARCHAR(50)  NOT NULL  UNIQUE ,
    [Agence] VARCHAR(50) ,
    [TypeClient] VARCHAR(50) ,
    [USAGE] VARCHAR(3) ,
    [STATUT] VARCHAR(1) ,
    [TYPE_CLIENT] VARCHAR(1) ,
    [UR] VARCHAR(50) ,
    [PNDPCE_NSPC] VARCHAR(50) ,
    [IDAgences] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL );
CREATE INDEX [WDIDX_ReferenceClient_bordereau] ON [ReferenceClient] ([bordereau]);
CREATE INDEX [WDIDX_ReferenceClient_groupesecteur] ON [ReferenceClient] ([groupesecteur]);
CREATE INDEX [WDIDX_ReferenceClient_Codeagence] ON [ReferenceClient] ([Codeagence]);
CREATE INDEX [WDIDX_ReferenceClient_Agence] ON [ReferenceClient] ([Agence]);
CREATE INDEX [WDIDX_ReferenceClient_TypeClient] ON [ReferenceClient] ([TypeClient]);
CREATE INDEX [WDIDX_ReferenceClient_UR] ON [ReferenceClient] ([UR]);

-- Création de la table ReferenceH2MC
CREATE TABLE [ReferenceClient1] (
    [Nombreclient] INTEGER DEFAULT 0,
    [TypeClient] VARCHAR(50) ,
    [USAGE] VARCHAR(3) ,
    [STATUT] VARCHAR(1) ,
    [Agence] VARCHAR(50) ,
    [TYPE_CLIENT] VARCHAR(1) ,
    [UR] VARCHAR(50) ,
    [IDAgence] NUMERIC(19,0) DEFAULT 0,
    [IDReferenceH2MC] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Description_UR] VARCHAR(100) ,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0,
    [IDRegions] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_ReferenceH2MC_TypeClient] ON [ReferenceClient1] ([TypeClient]);
CREATE INDEX [WDIDX_ReferenceH2MC_Agence] ON [ReferenceClient1] ([Agence]);
CREATE INDEX [WDIDX_ReferenceH2MC_UR] ON [ReferenceClient1] ([UR]);
CREATE INDEX [WDIDX_ReferenceH2MC_IDAgence] ON [ReferenceClient1] ([IDAgence]);
CREATE INDEX [WDIDX_ReferenceH2MC_IDDelegation] ON [ReferenceClient1] ([IDDelegation]);
CREATE INDEX [WDIDX_ReferenceH2MC_IDRegions] ON [ReferenceClient1] ([IDRegions]);

-- Création de la table Regions
CREATE TABLE [Regions] (
    [IDRegions] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Region] VARCHAR(50)  UNIQUE );

-- Création de la table ReglesEND
CREATE TABLE [ReglesEND] (
    [IDReglesEND] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDTypeEND] NUMERIC(19,0) ,
    [IDCauses] NUMERIC(19,0) ,
    [IDNature] NUMERIC(19,0) ,
    [IDCausesTrans] NUMERIC(19,0) ,
    [Natureseulement] BIT DEFAULT 0,
    [Causeseulement] BIT DEFAULT 0,
    [incoherent] BIT DEFAULT 0);
CREATE INDEX [WDIDX_ReglesEND_IDTypeEND] ON [ReglesEND] ([IDTypeEND]);
CREATE INDEX [WDIDX_ReglesEND_IDCauses] ON [ReglesEND] ([IDCauses]);
CREATE INDEX [WDIDX_ReglesEND_IDNature] ON [ReglesEND] ([IDNature]);
CREATE INDEX [WDIDX_ReglesEND_IDCausesTrans] ON [ReglesEND] ([IDCausesTrans]);
CREATE INDEX [WDIDX_ReglesEND_incoherent] ON [ReglesEND] ([incoherent]);
CREATE UNIQUE INDEX [WDIDX_ReglesEND_IDNatureIDCauses] ON [ReglesEND] ([IDNature],[IDCauses],[IDCausesTrans]);

-- Création de la table Repertoire
CREATE TABLE [Repertoire] (
    [IDRepertoire] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Matricule] INTEGER DEFAULT 0,
    [Prénom] VARCHAR(255) ,
    [Nom] VARCHAR(255) ,
    [fonctionagent] VARCHAR(50) ,
    [Telephone] VARCHAR(50)  NOT NULL  UNIQUE ,
    [Service] VARCHAR(255) ,
    [Direction] VARCHAR(255) );
CREATE INDEX [WDIDX_Repertoire_Matricule] ON [Repertoire] ([Matricule]);
CREATE INDEX [WDIDX_Repertoire_Prénom] ON [Repertoire] ([Prénom]);
CREATE INDEX [WDIDX_Repertoire_Nom] ON [Repertoire] ([Nom]);
CREATE INDEX [WDIDX_Repertoire_Service] ON [Repertoire] ([Service]);
CREATE INDEX [WDIDX_Repertoire_Direction] ON [Repertoire] ([Direction]);

-- Création de la table Responsable
CREATE TABLE [Responsable] (
    [IDResponsable] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Directionimputable] VARCHAR(50)  NOT NULL  UNIQUE );

-- Création de la table SAIFISAIDI
CREATE TABLE [SAIFISAIDI] (
    [IDSAIFISAIDI] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Date] DATETIME ,
    [SAIFI] FLOAT DEFAULT 0,
    [SAIDI] FLOAT DEFAULT 0,
    [Annee] INTEGER DEFAULT 0,
    [Nature] VARCHAR(50) ,
    [MoisLettre] VARCHAR(50) ,
    [INDEX] VARCHAR(50)  UNIQUE );
CREATE INDEX [WDIDX_SAIFISAIDI_Date] ON [SAIFISAIDI] ([Date]);
CREATE INDEX [WDIDX_SAIFISAIDI_Annee] ON [SAIFISAIDI] ([Annee]);
CREATE INDEX [WDIDX_SAIFISAIDI_Nature] ON [SAIFISAIDI] ([Nature]);
CREATE INDEX [WDIDX_SAIFISAIDI_MoisLettre] ON [SAIFISAIDI] ([MoisLettre]);

-- Création de la table Services
CREATE TABLE [Services] (
    [Service] VARCHAR(255)  NOT NULL  UNIQUE ,
    [Direction] VARCHAR(255) ,
    [STE] VARCHAR(255) ,
    [FIL] VARCHAR(255) ,
    [CPTE] VARCHAR(255) ,
    [S_CPTE] VARCHAR(255) ,
    [CResp] VARCHAR(50) ,
    [NAT] VARCHAR(255) ,
    [LOC] VARCHAR(255) ,
    [Region] VARCHAR(50) ,
    [IDAUTO] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_Services_Direction] ON [Services] ([Direction]);
CREATE INDEX [WDIDX_Services_CResp] ON [Services] ([CResp]);
CREATE INDEX [WDIDX_Services_Region] ON [Services] ([Region]);
CREATE INDEX [WDIDX_Services_IDDelegation] ON [Services] ([IDDelegation]);

-- Création de la table Sieges
CREATE TABLE [Sieges] (
    [IDSieges] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Sieges] VARCHAR(50)  UNIQUE ,
    [sigles] VARCHAR(50) ,
    [Regroupement] VARCHAR(50) ,
    [Typepanne] VARCHAR(50) ,
    [Coupure] BIT DEFAULT 0,
    [Délestage] BIT DEFAULT 0,
    [Fugitif] BIT DEFAULT 0,
    [Permanent] BIT DEFAULT 0,
    [Semi_permanent] BIT DEFAULT 0,
    [Dispatching] BIT DEFAULT 0,
    [IDTypeReseau] NUMERIC(19,0) );
CREATE INDEX [WDIDX_Sieges_sigles] ON [Sieges] ([sigles]);
CREATE INDEX [WDIDX_Sieges_Regroupement] ON [Sieges] ([Regroupement]);
CREATE INDEX [WDIDX_Sieges_Coupure] ON [Sieges] ([Coupure]);
CREATE INDEX [WDIDX_Sieges_Délestage] ON [Sieges] ([Délestage]);
CREATE INDEX [WDIDX_Sieges_Fugitif] ON [Sieges] ([Fugitif]);
CREATE INDEX [WDIDX_Sieges_Permanent] ON [Sieges] ([Permanent]);
CREATE INDEX [WDIDX_Sieges_Semi_permanent] ON [Sieges] ([Semi_permanent]);
CREATE INDEX [WDIDX_Sieges_Dispatching] ON [Sieges] ([Dispatching]);
CREATE INDEX [WDIDX_Sieges_IDTypeReseau] ON [Sieges] ([IDTypeReseau]);

-- Création de la table SiegesTransport
CREATE TABLE [SiegesTransport] (
    [IDSieges] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Sieges] VARCHAR(50)  UNIQUE ,
    [sigles] VARCHAR(50) ,
    [Regroupement] VARCHAR(50) ,
    [Typepanne] VARCHAR(50) ,
    [Coupure] BIT DEFAULT 0,
    [Délestage] BIT DEFAULT 0,
    [Fugitif] BIT DEFAULT 0,
    [Permanent] BIT DEFAULT 0,
    [Semi_permanent] BIT DEFAULT 0,
    [Dispatching] BIT DEFAULT 0,
    [effacement] BIT DEFAULT 0,
    [IDTypeReseau] NUMERIC(19,0) );
CREATE INDEX [WDIDX_SiegesTransport_sigles] ON [SiegesTransport] ([sigles]);
CREATE INDEX [WDIDX_SiegesTransport_Regroupement] ON [SiegesTransport] ([Regroupement]);
CREATE INDEX [WDIDX_SiegesTransport_Coupure] ON [SiegesTransport] ([Coupure]);
CREATE INDEX [WDIDX_SiegesTransport_Délestage] ON [SiegesTransport] ([Délestage]);
CREATE INDEX [WDIDX_SiegesTransport_Fugitif] ON [SiegesTransport] ([Fugitif]);
CREATE INDEX [WDIDX_SiegesTransport_Permanent] ON [SiegesTransport] ([Permanent]);
CREATE INDEX [WDIDX_SiegesTransport_Semi_permanent] ON [SiegesTransport] ([Semi_permanent]);
CREATE INDEX [WDIDX_SiegesTransport_Dispatching] ON [SiegesTransport] ([Dispatching]);
CREATE INDEX [WDIDX_SiegesTransport_effacement] ON [SiegesTransport] ([effacement]);
CREATE INDEX [WDIDX_SiegesTransport_IDTypeReseau] ON [SiegesTransport] ([IDTypeReseau]);

-- Création de la table SIG
CREATE TABLE [SIG] (
    [IDFeederSIG] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [FeederSIG] VARCHAR(50) ,
    [NombreKm] INTEGER DEFAULT 0,
    [IDPropritetaire_Ligne] NUMERIC(19,0) );
CREATE INDEX [WDIDX_SIG_FeederSIG] ON [SIG] ([FeederSIG]);
CREATE INDEX [WDIDX_SIG_NombreKm] ON [SIG] ([NombreKm]);
CREATE INDEX [WDIDX_SIG_IDPropritetaire_Ligne] ON [SIG] ([IDPropritetaire_Ligne]);

-- Création de la table SIG_FEEDERS$
CREATE TABLE [SIG_FEEDERS$] (
    [NOMFEEDER] VARCHAR(255) DEFAULT NULL,
    [IMATFEEDER] VARCHAR(255)  UNIQUE  DEFAULT NULL,
    [POSTESOURCE] VARCHAR(255) DEFAULT NULL,
    [IDSIG_FEEDERS] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL ,
    [IDPropritetaire_Ligne] NUMERIC(19,0) ,
    [Feeder_Privé] BIT DEFAULT 0,
    [Date_mise_en_service] DATETIME ,
    [Nombre_KM] INTEGER DEFAULT 0);
CREATE INDEX [WDIDX_SIG_FEEDERS$_NOMFEEDER] ON [SIG_FEEDERS$] ([NOMFEEDER]);
CREATE INDEX [WDIDX_SIG_FEEDERS$_POSTESOURCE] ON [SIG_FEEDERS$] ([POSTESOURCE]);
CREATE INDEX [WDIDX_SIG_FEEDERS$_IDPropritetaire_Ligne] ON [SIG_FEEDERS$] ([IDPropritetaire_Ligne]);
CREATE INDEX [WDIDX_SIG_FEEDERS$_Feeder_Privé] ON [SIG_FEEDERS$] ([Feeder_Privé]);
CREATE INDEX [WDIDX_SIG_FEEDERS$_Date_mise_en_service] ON [SIG_FEEDERS$] ([Date_mise_en_service]);
CREATE INDEX [WDIDX_SIG_FEEDERS$_Nombre_KM] ON [SIG_FEEDERS$] ([Nombre_KM]);

-- Création de la table Signalisations
CREATE TABLE [Signalisations] (
    [Signalisation] VARCHAR(50)  UNIQUE ,
    [IDNature] VARCHAR(255) ,
    [IDSignalisation] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Coupure] BIT DEFAULT 0,
    [Délestage] BIT DEFAULT 0,
    [Fugitif] BIT DEFAULT 0,
    [Permanent] BIT DEFAULT 0,
    [Semi_permanent] BIT DEFAULT 0,
    [Dispatching] BIT DEFAULT 0);
CREATE INDEX [WDIDX_Signalisations_IDNature] ON [Signalisations] ([IDNature]);
CREATE INDEX [WDIDX_Signalisations_Coupure] ON [Signalisations] ([Coupure]);
CREATE INDEX [WDIDX_Signalisations_Délestage] ON [Signalisations] ([Délestage]);
CREATE INDEX [WDIDX_Signalisations_Fugitif] ON [Signalisations] ([Fugitif]);
CREATE INDEX [WDIDX_Signalisations_Permanent] ON [Signalisations] ([Permanent]);
CREATE INDEX [WDIDX_Signalisations_Semi_permanent] ON [Signalisations] ([Semi_permanent]);
CREATE INDEX [WDIDX_Signalisations_Dispatching] ON [Signalisations] ([Dispatching]);

-- Création de la table SignalisationsTransport
CREATE TABLE [SignalisationsTransport] (
    [Signalisation] VARCHAR(50)  UNIQUE ,
    [IDNature] VARCHAR(255) ,
    [IDSignalisation] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Coupure] BIT DEFAULT 0,
    [Délestage] BIT DEFAULT 0,
    [Fugitif] BIT DEFAULT 0,
    [Permanent] BIT DEFAULT 0,
    [Semi_permanent] BIT DEFAULT 0,
    [Dispatching] BIT DEFAULT 0);
CREATE INDEX [WDIDX_SignalisationsTransport_IDNature] ON [SignalisationsTransport] ([IDNature]);
CREATE INDEX [WDIDX_SignalisationsTransport_Coupure] ON [SignalisationsTransport] ([Coupure]);
CREATE INDEX [WDIDX_SignalisationsTransport_Délestage] ON [SignalisationsTransport] ([Délestage]);
CREATE INDEX [WDIDX_SignalisationsTransport_Fugitif] ON [SignalisationsTransport] ([Fugitif]);
CREATE INDEX [WDIDX_SignalisationsTransport_Permanent] ON [SignalisationsTransport] ([Permanent]);
CREATE INDEX [WDIDX_SignalisationsTransport_Semi_permanent] ON [SignalisationsTransport] ([Semi_permanent]);
CREATE INDEX [WDIDX_SignalisationsTransport_Dispatching] ON [SignalisationsTransport] ([Dispatching]);

-- Création de la table smsenvoye
CREATE TABLE [smsenvoye] (
    [IDsmsenvoye] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [NInterruption] NUMERIC(19,0) DEFAULT 0,
    [dateEnvoi] DATETIME ,
    [exploitation] VARCHAR(50) ,
    [Login] VARCHAR(255) ,
    [messageenvoye] VARCHAR(500) ,
    [Telephone] VARCHAR(50) ,
    [destinataire] VARCHAR(50) ,
    [Status_Code] VARCHAR(50) ,
    [Status_Text] VARCHAR(50) ,
    [messageID] VARCHAR(50) ,
    [messageDetailID] VARCHAR(50) );
CREATE INDEX [WDIDX_smsenvoye_NInterruption] ON [smsenvoye] ([NInterruption]);
CREATE INDEX [WDIDX_smsenvoye_exploitation] ON [smsenvoye] ([exploitation]);
CREATE INDEX [WDIDX_smsenvoye_Login] ON [smsenvoye] ([Login]);
CREATE INDEX [WDIDX_smsenvoye_Telephone] ON [smsenvoye] ([Telephone]);
CREATE INDEX [WDIDX_smsenvoye_destinataire] ON [smsenvoye] ([destinataire]);

-- Création de la table SourceTransport
CREATE TABLE [SourceTransport] (
    [IDSourceEquipement] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [sourceTransport] VARCHAR(255) ,
    [codesource] VARCHAR(50) ,
    [Tension] REAL DEFAULT 0,
    [PosteLigne] VARCHAR(50) ,
    [Appartenance] VARCHAR(50) ,
    [IDO_M] NUMERIC(19,0) );
CREATE INDEX [WDIDX_SourceTransport_sourceTransport] ON [SourceTransport] ([sourceTransport]);
CREATE INDEX [WDIDX_SourceTransport_codesource] ON [SourceTransport] ([codesource]);
CREATE INDEX [WDIDX_SourceTransport_Tension] ON [SourceTransport] ([Tension]);
CREATE INDEX [WDIDX_SourceTransport_PosteLigne] ON [SourceTransport] ([PosteLigne]);
CREATE INDEX [WDIDX_SourceTransport_Appartenance] ON [SourceTransport] ([Appartenance]);
CREATE INDEX [WDIDX_SourceTransport_IDO_M] ON [SourceTransport] ([IDO_M]);

-- Création de la table SousFeeder
CREATE TABLE [SousFeeder] (
    [IDSousFeeder] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Libelle_SousFeeder] VARCHAR(50) ,
    [Libelle_Feeder_SousFeeder] VARCHAR(50) ,
    [IDFeeder] NUMERIC(19,0) );
CREATE INDEX [WDIDX_SousFeeder_IDFeeder] ON [SousFeeder] ([IDFeeder]);

-- Création de la table Sousgroupe
CREATE TABLE [Sousgroupe] (
    [IDSousGroupes] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [nomgroupe] VARCHAR(50) ,
    [Service] VARCHAR(255) ,
    [Exploitation] VARCHAR(50) );
CREATE INDEX [WDIDX_Sousgroupe_nomgroupe] ON [Sousgroupe] ([nomgroupe]);
CREATE INDEX [WDIDX_Sousgroupe_Service] ON [Sousgroupe] ([Service]);
CREATE INDEX [WDIDX_Sousgroupe_Exploitation] ON [Sousgroupe] ([Exploitation]);

-- Création de la table TelephoneMobile
CREATE TABLE [TelephoneMobile] (
    [CRESP] INTEGER DEFAULT 0,
    [Organisation] VARCHAR(50) ,
    [STE] VARCHAR(50) ,
    [Filiale] VARCHAR(50) ,
    [SousCompte] VARCHAR(50) ,
    [Compte] VARCHAR(50) ,
    [Nature] VARCHAR(50) ,
    [NumeroLigne] NUMERIC(10,0)  UNIQUE  DEFAULT 0,
    [IDAgences] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL );
CREATE INDEX [WDIDX_TelephoneMobile_CRESP] ON [TelephoneMobile] ([CRESP]);

-- Création de la table Tension
CREATE TABLE [Tension] (
    [IDTension] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Tension] REAL  NOT NULL  UNIQUE  DEFAULT 0);

-- Création de la table Troncon
CREATE TABLE [Troncon] (
    [IDTroncon] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Libelle_Troncon] VARCHAR(50) ,
    [IDNoeudAmont] NUMERIC(19,0) DEFAULT 0,
    [IDNoeudAval] NUMERIC(19,0) DEFAULT 0,
    [IDFeeder] NUMERIC(19,0) );
CREATE INDEX [WDIDX_Troncon_IDNoeudAmont] ON [Troncon] ([IDNoeudAmont]);
CREATE INDEX [WDIDX_Troncon_IDNoeudAval] ON [Troncon] ([IDNoeudAval]);
CREATE INDEX [WDIDX_Troncon_IDFeeder] ON [Troncon] ([IDFeeder]);
CREATE UNIQUE INDEX [WDIDX_Troncon_IDNoeudAmontIDNoeudAval] ON [Troncon] ([IDNoeudAmont],[IDNoeudAval]);

-- Création de la table TRONCON_POSTE$
CREATE TABLE [TRONCON_POSTE$] (
    [IDTroncon_Postes] INTEGER  UNIQUE  DEFAULT NULL,
    [Libelle_Troncon] NVARCHAR(255) DEFAULT NULL,
    [IDTroncon] FLOAT DEFAULT NULL,
    [Poste] NVARCHAR(255) DEFAULT NULL,
    [IDPoste] FLOAT DEFAULT NULL,
    [Feeder] NVARCHAR(255) DEFAULT NULL);
CREATE INDEX [WDIDX_TRONCON_POSTE$_IDTroncon] ON [TRONCON_POSTE$] ([IDTroncon]);
CREATE INDEX [WDIDX_TRONCON_POSTE$_IDPoste] ON [TRONCON_POSTE$] ([IDPoste]);
CREATE INDEX [WDIDX_TRONCON_POSTE$_IDTronconIDPoste] ON [TRONCON_POSTE$] ([IDTroncon],[IDPoste]);

-- Création de la table Troncon_SIG
CREATE TABLE [Troncon_SIG] (
    [FID] INTEGER DEFAULT 0,
    [OBJECTID] FLOAT DEFAULT NULL,
    [NTROCON] FLOAT DEFAULT NULL,
    [NOMFEEDER] VARCHAR(255) DEFAULT NULL,
    [IMATFEEDER] VARCHAR(255) DEFAULT NULL,
    [NTENSION] FLOAT DEFAULT NULL,
    [SECTIONS] FLOAT DEFAULT NULL,
    [NOMNAMONT] VARCHAR(255) DEFAULT NULL,
    [CODAMONT] VARCHAR(255) DEFAULT NULL,
    [NOMNAVAL] VARCHAR(255) DEFAULT NULL,
    [CODAVAL] VARCHAR(255) DEFAULT NULL,
    [ss] VARCHAR(255) DEFAULT NULL,
    [Date_d_Acq] DATETIME DEFAULT NULL,
    [Date_de_Mi] DATETIME DEFAULT NULL,
    [Shape_Leng] FLOAT DEFAULT NULL,
    [TYPE_CONDU] FLOAT DEFAULT NULL,
    [Projet] VARCHAR(255) DEFAULT NULL,
    [DATE_MAJ] DATETIME DEFAULT NULL,
    [DELEGATION] VARCHAR(255) DEFAULT NULL,
    [Date_Chargement] DATETIME ,
    [NomTroncon] VARCHAR(255) ,
    [ID_Troncon_SIG] INTEGER  IDENTITY   PRIMARY KEY  NOT NULL );
CREATE INDEX [WDIDX_Troncon_SIG_FID] ON [Troncon_SIG] ([FID]);
CREATE INDEX [WDIDX_Troncon_SIG_OBJECTID] ON [Troncon_SIG] ([OBJECTID]);
CREATE INDEX [WDIDX_Troncon_SIG_NTROCON] ON [Troncon_SIG] ([NTROCON]);
CREATE INDEX [WDIDX_Troncon_SIG_NOMFEEDER] ON [Troncon_SIG] ([NOMFEEDER]);
CREATE INDEX [WDIDX_Troncon_SIG_IMATFEEDER] ON [Troncon_SIG] ([IMATFEEDER]);
CREATE INDEX [WDIDX_Troncon_SIG_NTENSION] ON [Troncon_SIG] ([NTENSION]);
CREATE INDEX [WDIDX_Troncon_SIG_SECTIONS] ON [Troncon_SIG] ([SECTIONS]);
CREATE INDEX [WDIDX_Troncon_SIG_NOMNAMONT] ON [Troncon_SIG] ([NOMNAMONT]);
CREATE INDEX [WDIDX_Troncon_SIG_CODAMONT] ON [Troncon_SIG] ([CODAMONT]);
CREATE INDEX [WDIDX_Troncon_SIG_NOMNAVAL] ON [Troncon_SIG] ([NOMNAVAL]);
CREATE INDEX [WDIDX_Troncon_SIG_CODAVAL] ON [Troncon_SIG] ([CODAVAL]);
CREATE INDEX [WDIDX_Troncon_SIG_ss] ON [Troncon_SIG] ([ss]);
CREATE INDEX [WDIDX_Troncon_SIG_Date_d_Acq] ON [Troncon_SIG] ([Date_d_Acq]);
CREATE INDEX [WDIDX_Troncon_SIG_Date_de_Mi] ON [Troncon_SIG] ([Date_de_Mi]);
CREATE INDEX [WDIDX_Troncon_SIG_Shape_Leng] ON [Troncon_SIG] ([Shape_Leng]);
CREATE INDEX [WDIDX_Troncon_SIG_TYPE_CONDU] ON [Troncon_SIG] ([TYPE_CONDU]);
CREATE INDEX [WDIDX_Troncon_SIG_Projet] ON [Troncon_SIG] ([Projet]);
CREATE INDEX [WDIDX_Troncon_SIG_DATE_MAJ] ON [Troncon_SIG] ([DATE_MAJ]);
CREATE INDEX [WDIDX_Troncon_SIG_DELEGATION] ON [Troncon_SIG] ([DELEGATION]);
CREATE INDEX [WDIDX_Troncon_SIG_Date_Chargement] ON [Troncon_SIG] ([Date_Chargement]);
CREATE INDEX [WDIDX_Troncon_SIG_NomTroncon] ON [Troncon_SIG] ([NomTroncon]);
CREATE UNIQUE INDEX [WDIDX_Troncon_SIG_FIDDate_Chargement] ON [Troncon_SIG] ([FID],[Date_Chargement]);

-- Création de la table Tronçons
CREATE TABLE [Tronçons] (
    [IDTronçons] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [IDFeeder] NUMERIC(19,0) DEFAULT 0,
    [Feeder] VARCHAR(255) );
CREATE INDEX [WDIDX_Tronçons_IDFeeder] ON [Tronçons] ([IDFeeder]);
CREATE INDEX [WDIDX_Tronçons_Feeder] ON [Tronçons] ([Feeder]);

-- Création de la table Troncons_SIG_Ancien
CREATE TABLE [Troncons_SIG_Ancien] (
    [IDTroncons_SIG] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [NomAmont] VARCHAR(255) ,
    [NomAval] VARCHAR(255) ,
    [Longueur] INTEGER DEFAULT 0,
    [IDFeederSIG] NUMERIC(19,0)  UNIQUE  DEFAULT 0,
    [NTension] INTEGER DEFAULT 0,
    [NomTroncon] VARCHAR(50) ,
    [Natcond] VARCHAR(50) ,
    [TypeConduc] FLOAT DEFAULT 0,
    [Sections] VARCHAR(50) ,
    [SStation] VARCHAR(50) ,
    [DareFin] DATETIME );
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_NomAmont] ON [Troncons_SIG_Ancien] ([NomAmont]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_NomAval] ON [Troncons_SIG_Ancien] ([NomAval]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_Longueur] ON [Troncons_SIG_Ancien] ([Longueur]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_NTension] ON [Troncons_SIG_Ancien] ([NTension]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_NomTroncon] ON [Troncons_SIG_Ancien] ([NomTroncon]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_Natcond] ON [Troncons_SIG_Ancien] ([Natcond]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_TypeConduc] ON [Troncons_SIG_Ancien] ([TypeConduc]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_Sections] ON [Troncons_SIG_Ancien] ([Sections]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_SStation] ON [Troncons_SIG_Ancien] ([SStation]);
CREATE INDEX [WDIDX_Troncons_SIG_Ancien_DareFin] ON [Troncons_SIG_Ancien] ([DareFin]);

-- Création de la table Type_Cellule
CREATE TABLE [Type_Cellule] (
    [IDType_Cellule] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Libelle_Cellule] VARCHAR(50) );

-- Création de la table TypeAAT
CREATE TABLE [TypeAAT] (
    [IDTypeAAT] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Libelle_TypeAAT] VARCHAR(50) );

-- Création de la table TypeEND
CREATE TABLE [TypeEND] (
    [IDTypeEND] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [TypeEND] VARCHAR(50) ,
    [IDResponsable] NUMERIC(19,0) DEFAULT 0);
CREATE INDEX [WDIDX_TypeEND_TypeEND] ON [TypeEND] ([TypeEND]);
CREATE INDEX [WDIDX_TypeEND_IDResponsable] ON [TypeEND] ([IDResponsable]);

-- Création de la table TypeEquipement
CREATE TABLE [TypeEquipement] (
    [IDTypeEquipement] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [typeequipement] VARCHAR(50)  UNIQUE );

-- Création de la table TypeNoeud_SIG
CREATE TABLE [TypeNoeud_SIG] (
    [IDTypeNoeud_SIG] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Libelle_TYpeNoeud_SIG] VARCHAR(50) ,
    [Abrege_TupeNoeud_SIG] VARCHAR(50) );

-- Création de la table TypePermanent
CREATE TABLE [TypePermanent] (
    [IDTypePermanent] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [TypePermanent] VARCHAR(255)  UNIQUE );

-- Création de la table TypeReseau
CREATE TABLE [TypeReseau] (
    [IDTypeReseau] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [typereseau] VARCHAR(50) );
CREATE INDEX [WDIDX_TypeReseau_typereseau] ON [TypeReseau] ([typereseau]);

-- Création de la table TypeUtilisateur
CREATE TABLE [TypeUtilisateur] (
    [IDTypeUtilisateur] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [typeuser] VARCHAR(50)  NOT NULL  UNIQUE );

-- Création de la table Unites
CREATE TABLE [Unites] (
    [Unite] VARCHAR(255)  UNIQUE ,
    [Service] VARCHAR(255) ,
    [CR] INTEGER DEFAULT 0,
    [Departement] VARCHAR(255) ,
    [Chefunite] VARCHAR(1000) ,
    [description] VARCHAR(255) ,
    [DescriptionDepartement] VARCHAR(1000) ,
    [DescriptionService] VARCHAR(1000) ,
    [Region] VARCHAR(50) ,
    [IDAgences] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL );
CREATE INDEX [WDIDX_Unites_Service] ON [Unites] ([Service]);
CREATE INDEX [WDIDX_Unites_CR] ON [Unites] ([CR]);
CREATE INDEX [WDIDX_Unites_Departement] ON [Unites] ([Departement]);
CREATE INDEX [WDIDX_Unites_Chefunite] ON [Unites] ([Chefunite]);
CREATE INDEX [WDIDX_Unites_description] ON [Unites] ([description]);
CREATE INDEX [WDIDX_Unites_DescriptionDepartement] ON [Unites] ([DescriptionDepartement]);
CREATE INDEX [WDIDX_Unites_DescriptionService] ON [Unites] ([DescriptionService]);
CREATE INDEX [WDIDX_Unites_Region] ON [Unites] ([Region]);

-- Création de la table UR
CREATE TABLE [UR] (
    [UR] VARCHAR(50)  UNIQUE ,
    [Description_UR] VARCHAR(100) );

-- Création de la table UR_Fictif
CREATE TABLE [ReferenceClient2] (
    [Nombreclient] INTEGER DEFAULT 0,
    [TypeClient] VARCHAR(50) ,
    [USAGE] VARCHAR(3) ,
    [STATUT] VARCHAR(1) ,
    [Agence] VARCHAR(50) ,
    [TYPE_CLIENT] VARCHAR(1) ,
    [UR] VARCHAR(50) ,
    [IDAgence] NUMERIC(19,0) DEFAULT 0,
    [IDReferenceH2MC] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Description_UR] VARCHAR(100) ,
    [IDDelegation] NUMERIC(19,0) DEFAULT 0,
    [IDRegions] NUMERIC(19,0) DEFAULT 0,
    [Status_UR] VARCHAR(50) );
CREATE INDEX [WDIDX_UR_Fictif_TypeClient] ON [ReferenceClient2] ([TypeClient]);
CREATE INDEX [WDIDX_UR_Fictif_Agence] ON [ReferenceClient2] ([Agence]);
CREATE INDEX [WDIDX_UR_Fictif_UR] ON [ReferenceClient2] ([UR]);
CREATE INDEX [WDIDX_UR_Fictif_IDAgence] ON [ReferenceClient2] ([IDAgence]);
CREATE INDEX [WDIDX_UR_Fictif_IDDelegation] ON [ReferenceClient2] ([IDDelegation]);
CREATE INDEX [WDIDX_UR_Fictif_IDRegions] ON [ReferenceClient2] ([IDRegions]);

-- Création de la table Utilisateurs
CREATE TABLE [Utilisateurs] (
    [Matricule] INTEGER  NOT NULL  UNIQUE  DEFAULT 0,
    [Login] VARCHAR(255)  NOT NULL  UNIQUE ,
    [Prénom] VARCHAR(255)  NOT NULL ,
    [Groupe] VARCHAR(255)  NOT NULL ,
    [Nom] VARCHAR(255)  NOT NULL ,
    [Unite] VARCHAR(255)  NOT NULL ,
    [Regions] VARCHAR(50)  NOT NULL ,
    [IDUser] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [superviseur] BIT  NOT NULL  DEFAULT 0,
    [mdp] VARCHAR(50)  NOT NULL ,
    [typeuser] VARCHAR(50)  NOT NULL ,
    [exploitation] VARCHAR(50)  NOT NULL ,
    [AdminSCR] BIT  NOT NULL  DEFAULT 0,
    [AdminDitpatching] BIT  NOT NULL  DEFAULT 0,
    [premiereconnexion] BIT  NOT NULL  DEFAULT 0,
    [Email] VARCHAR(50)  NOT NULL ,
    [AdminSAQS] BIT  NOT NULL  DEFAULT 0,
    [disparcheur] BIT  NOT NULL  DEFAULT 0,
    [Service] VARCHAR(255)  NOT NULL );
CREATE INDEX [WDIDX_Utilisateurs_Prénom] ON [Utilisateurs] ([Prénom]);
CREATE INDEX [WDIDX_Utilisateurs_Groupe] ON [Utilisateurs] ([Groupe]);
CREATE INDEX [WDIDX_Utilisateurs_Nom] ON [Utilisateurs] ([Nom]);
CREATE INDEX [WDIDX_Utilisateurs_Unite] ON [Utilisateurs] ([Unite]);
CREATE INDEX [WDIDX_Utilisateurs_Regions] ON [Utilisateurs] ([Regions]);
CREATE INDEX [WDIDX_Utilisateurs_mdp] ON [Utilisateurs] ([mdp]);
CREATE INDEX [WDIDX_Utilisateurs_typeuser] ON [Utilisateurs] ([typeuser]);
CREATE INDEX [WDIDX_Utilisateurs_exploitation] ON [Utilisateurs] ([exploitation]);
CREATE INDEX [WDIDX_Utilisateurs_Email] ON [Utilisateurs] ([Email]);
CREATE INDEX [WDIDX_Utilisateurs_AdminSAQS] ON [Utilisateurs] ([AdminSAQS]);
CREATE INDEX [WDIDX_Utilisateurs_Service] ON [Utilisateurs] ([Service]);

-- Création de la table Validateur
CREATE TABLE [Validateur] (
    [IDValidateur] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Prenom_Nom_Valideur] VARCHAR(50)  NOT NULL  UNIQUE ,
    [Adresse] VARCHAR(50) ,
    [fonctionvalidateur] VARCHAR(50) ,
    [Email] VARCHAR(50) ,
    [Login] VARCHAR(255) ,
    [motpasse] VARCHAR(50) ,
    [Matricule] INTEGER DEFAULT 0,
    [validateur] VARCHAR(255)  UNIQUE );
CREATE INDEX [WDIDX_Validateur_Login] ON [Validateur] ([Login]);
CREATE INDEX [WDIDX_Validateur_Matricule] ON [Validateur] ([Matricule]);

-- Création de la table Valideur
CREATE TABLE [Valideur] (
    [IDValideur] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL ,
    [Prenom_Nom] VARCHAR(255) ,
    [Fonction_Valideur] VARCHAR(50) );

-- Création de la table vw_ABONNES_ALL
CREATE TABLE [dbo.vw_ABONNES_ALL] (
    [CODETABL] VARCHAR(3) DEFAULT NULL,
    [CODETABL2] VARCHAR(3) DEFAULT NULL,
    [POLICE] VARCHAR(10) DEFAULT NULL,
    [NUMCOMPTEUR] VARCHAR(8) DEFAULT NULL,
    [CODGEST] VARCHAR(2) DEFAULT NULL,
    [CODSUIV] VARCHAR(2) DEFAULT NULL,
    [NOM] VARCHAR(25) DEFAULT NULL,
    [PRENOM] VARCHAR(25) DEFAULT NULL,
    [ADRLIVR] VARCHAR(100) DEFAULT NULL,
    [ADRPRES] VARCHAR(100) DEFAULT NULL,
    [TELEPH1] VARCHAR(8) DEFAULT NULL,
    [CODBANQ] VARCHAR(2) DEFAULT NULL,
    [GRP-SECT] VARCHAR(3) DEFAULT NULL,
    [BORDERO] VARCHAR(4) DEFAULT NULL,
    [REFERE] VARCHAR(10) DEFAULT NULL,
    [CODUSAG] VARCHAR(3) DEFAULT NULL,
    [CODTARIF] VARCHAR(2) DEFAULT NULL,
    [COTE] VARCHAR(5) DEFAULT NULL,
    [TYPCLI] VARCHAR(1) DEFAULT NULL,
    [CODACTIV] VARCHAR(1) DEFAULT NULL,
    [STATUT] VARCHAR(1) DEFAULT NULL,
    [datchargement] DATETIME DEFAULT NULL,
    [CODE_NATIONALITE] VARCHAR(2) DEFAULT NULL,
    [CODE_PROFESSION] VARCHAR(2) DEFAULT NULL,
    [TYPE_IDENTITE] VARCHAR(1) DEFAULT NULL,
    [TYPE_INSCRIPTION] VARCHAR(1) DEFAULT NULL,
    [TYPE_LOCAL] VARCHAR(1) DEFAULT NULL,
    [CODE_PRESENTATION] VARCHAR(1) DEFAULT NULL,
    [PRELEVEMENT] VARCHAR(3) DEFAULT NULL,
    [DATE_PRELEVEMENT] DATETIME DEFAULT NULL,
    [NUMERO_COMPTE] VARCHAR(12) DEFAULT NULL,
    [DATE_CREATION] DATETIME DEFAULT NULL,
    [DATE_SOUSCRIPTION] DATETIME DEFAULT NULL,
    [TELEPHONE2] VARCHAR(8) DEFAULT NULL,
    [NUMERO_PIECE] VARCHAR(11) DEFAULT NULL,
    [DATE_NAISSANCE] DATETIME DEFAULT NULL,
    [NUMERO_INSCRIPTION] VARCHAR(8) DEFAULT NULL,
    [BOITE_POSTALE] VARCHAR(5) DEFAULT NULL,
    [TYPE_CONVENTION] VARCHAR(1) DEFAULT NULL,
    [QUALITE_PAYEUR] VARCHAR(2) DEFAULT NULL,
    [RECLASSEMENT] VARCHAR(3) DEFAULT NULL,
    [DATE_RECLASSEMENT] DATETIME DEFAULT NULL,
    [TIMBRE] VARCHAR(3) DEFAULT NULL,
    [TCO] VARCHAR(3) DEFAULT NULL,
    [TVA] VARCHAR(3) DEFAULT NULL,
    [TV] VARCHAR(3) DEFAULT NULL,
    [AUT] VARCHAR(3) DEFAULT NULL,
    [EXT] VARCHAR(3) DEFAULT NULL,
    [PARTICIPATION] VARCHAR(3) DEFAULT NULL,
    [NB_INC_CHEQUE] SMALLINT DEFAULT NULL,
    [DATE_INC_CHEQUE] DATETIME DEFAULT NULL,
    [DATE_INC_PRELEVEMENT] DATETIME DEFAULT NULL,
    [DATE_COUPURE] DATETIME DEFAULT NULL,
    [SECT_BRANCH] SMALLINT DEFAULT NULL,
    [TYPDEM_ENCOURS] VARCHAR(2) DEFAULT NULL,
    [NUMDEM_ENCOURS] VARCHAR(10) DEFAULT NULL,
    [TENSION] VARCHAR(10) DEFAULT NULL,
    [REDEVANCE] INTEGER DEFAULT NULL,
    [NOMBRE_MORATOIRE] INTEGER DEFAULT NULL,
    [NOMBRE_DELAI] INTEGER DEFAULT NULL,
    [PHASE] VARCHAR(4) DEFAULT NULL,
    [INTENSITE] VARCHAR(3) DEFAULT NULL,
    [PUISSANCE] NUMERIC(19,0) DEFAULT NULL,
    [PUISSANCE_KW] FLOAT DEFAULT NULL,
    [ANCIEN_INDEX] VARCHAR(6) DEFAULT NULL,
    [DATE_AI] DATETIME DEFAULT NULL,
    [NOUVEL_INDEX] VARCHAR(6) DEFAULT NULL,
    [DATE_NI] DATETIME DEFAULT NULL,
    [INDEX_RESILIATION] VARCHAR(11) DEFAULT NULL,
    [INDEX_RESILIATION2] VARCHAR(11) DEFAULT NULL,
    [DATE_RESILIATION] DATETIME DEFAULT NULL,
    [INDEX_POSE] VARCHAR(6) DEFAULT NULL,
    [DATE_POSE] DATETIME DEFAULT NULL,
    [NOMBRE_FOYER] SMALLINT DEFAULT NULL,
    [PUISSANCE_FOYER] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_FRIGO] SMALLINT DEFAULT NULL,
    [PUISSANCE_FRIGO] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_TELE] SMALLINT DEFAULT NULL,
    [PUISSANCE_TELE] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_CONGELATEUR] SMALLINT DEFAULT NULL,
    [PUISSANCE_CONGELATEUR] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_CHAUFFEAU] SMALLINT DEFAULT NULL,
    [PUISSANCE_CHAUFFEAU] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_VENTILO] SMALLINT DEFAULT NULL,
    [PUISSANCE_VENTILO] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_CLIM] SMALLINT DEFAULT NULL,
    [PUISSANCE_CLIM] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_HIFI] SMALLINT DEFAULT NULL,
    [PUISSANCE_HIFI] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_FER] SMALLINT DEFAULT NULL,
    [PUISSANCE_FER] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_MACHALAVER] SMALLINT DEFAULT NULL,
    [PUISSANCE_MACHALAVER] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_MOTEUR] SMALLINT DEFAULT NULL,
    [PUISSANCE_MOTEUR] NUMERIC(19,0) DEFAULT NULL,
    [NOMBRE_ORDINATEUR] SMALLINT DEFAULT NULL,
    [PUISSANCE_ORDINATEUR] NUMERIC(19,0) DEFAULT NULL,
    [ANC_REFERENCE] VARCHAR(10) DEFAULT NULL,
    [RESILIE_BR] VARCHAR(7) DEFAULT NULL,
    [NB_COUPURE] INTEGER DEFAULT NULL,
    [MAT_AGENT_COUP] VARCHAR(4) DEFAULT NULL,
    [NBRE_FILS] TINYINT DEFAULT NULL,
    [NB_FRAUDE] SMALLINT DEFAULT NULL,
    [NB_INCHQ] SMALLINT DEFAULT NULL,
    [NB_INCPREL] SMALLINT DEFAULT NULL,
    [NUMFACT_ANCIENNE] VARCHAR(7) DEFAULT NULL,
    [DATFACT_ANCIENNE] DATETIME DEFAULT NULL,
    [NUMFACT_DERNIERE] VARCHAR(7) DEFAULT NULL,
    [DATFACT_DERNIERE] DATETIME DEFAULT NULL,
    [MAX_APPL] VARCHAR(6) DEFAULT NULL,
    [DERN_MAX_REL] NUMERIC(19,0) DEFAULT NULL,
    [MOY_MAX_REL] NUMERIC(19,0) DEFAULT NULL,
    [TYPE_COMPTAGE] VARCHAR(1) DEFAULT NULL,
    [NUMCOMPT_ACTIF2] VARCHAR(8) DEFAULT NULL,
    [NUMCOMPT_REACTIF] VARCHAR(8) DEFAULT NULL,
    [HORLOGE] VARCHAR(8) DEFAULT NULL,
    [MONO1] VARCHAR(8) DEFAULT NULL,
    [MONO2] VARCHAR(8) DEFAULT NULL,
    [MONO3] VARCHAR(8) DEFAULT NULL,
    [HORAIRE1] VARCHAR(8) DEFAULT NULL,
    [HORAIRE1B] VARCHAR(8) DEFAULT NULL,
    [HORAIRE2] VARCHAR(8) DEFAULT NULL,
    [PSTRANSF1] NUMERIC(19,0) DEFAULT NULL,
    [RPTRANSF1] VARCHAR(10) DEFAULT NULL,
    [PSTRANSF2] NUMERIC(19,0) DEFAULT NULL,
    [RPTRANSF2] VARCHAR(10) DEFAULT NULL,
    [PSTRANSF3] NUMERIC(19,0) DEFAULT NULL,
    [RPTRANSF3] VARCHAR(10) DEFAULT NULL,
    [PSTRANSF4] NUMERIC(19,0) DEFAULT NULL,
    [RPTRANSF4] VARCHAR(10) DEFAULT NULL,
    [PSCONDEN] NUMERIC(19,0) DEFAULT NULL,
    [PSDISJONCTEUR] INTEGER DEFAULT NULL,
    [RAPPTI] VARCHAR(15) DEFAULT NULL,
    [PS_TI] NUMERIC(19,0) DEFAULT NULL,
    [RAPPTP] VARCHAR(15) DEFAULT NULL,
    [PS_TP] NUMERIC(19,0) DEFAULT NULL,
    [CODACTSECT] VARCHAR(3) DEFAULT NULL,
    [CODE_ALIMENTATION] VARCHAR(1) DEFAULT NULL,
    [NOM_POSTE] VARCHAR(20) DEFAULT NULL,
    [NOM_FEEDER] VARCHAR(20) DEFAULT NULL,
    [SECTION_FEEDER] VARCHAR(40) DEFAULT NULL,
    [LIBELLE_STATUT] VARCHAR(33) DEFAULT NULL,
    [LIBELLE_ACTIVITE] VARCHAR(34) DEFAULT NULL,
    [LIBELLE_NATIONALITE] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_TYPELOCAL] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_PROFESSION] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_TARIF] VARCHAR(30) DEFAULT NULL,
    [TAUX_PF] NUMERIC(12,0) DEFAULT NULL,
    [LIBELLE_COUPURE] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_ACTIVECO] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_CONVENTION] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_PRESFACTURE] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_IDENTITE] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_TYPECLIENT] VARCHAR(33) DEFAULT NULL,
    [LIBELLE_CODGESTION] VARCHAR(40) DEFAULT NULL,
    [LIBELLE_BANQUE] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_SUIVI] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_TYPECOMPTAGE] VARCHAR(30) DEFAULT NULL,
    [LIBELLE_ALIMENTATION] VARCHAR(30) DEFAULT NULL,
    [DATE_RELEVE] DATETIME DEFAULT NULL,
    [IDAgences] NUMERIC(19,0)  IDENTITY  PRIMARY KEY  NOT NULL );
-- Contraintes d'intégrité
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDNature]) REFERENCES [Natures] ([IDNature]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDCauses]) REFERENCES [Causes] ([IDCauses]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDSieges]) REFERENCES [Sieges] ([IDSieges]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDSignalisation]) REFERENCES [Signalisations] ([IDSignalisation]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE [Feeders] ADD FOREIGN KEY ([PosteSOurce]) REFERENCES [PostesSources] ([PosteSource]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([Login]) REFERENCES [Utilisateurs] ([Login]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDTypePermanent]) REFERENCES [TypePermanent] ([IDTypePermanent]);
ALTER TABLE [Postes] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE [Postes] ADD FOREIGN KEY ([PosteSource]) REFERENCES [PostesSources] ([PosteSource]);
ALTER TABLE [FeuilleConduite] ADD FOREIGN KEY ([Matricule]) REFERENCES [Utilisateurs] ([Matricule]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [Unites] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [Feeders] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [PostesSources] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([PosteSource]) REFERENCES [PostesSources] ([PosteSource]);
ALTER TABLE [NAPT] ADD FOREIGN KEY ([Prenom_Nom_Valideur]) REFERENCES [Validateur] ([Prenom_Nom_Valideur]);
ALTER TABLE [NAPT] ADD FOREIGN KEY ([Prenom_Nom_Redacteur]) REFERENCES [Rédacteurs] ([Prenom_Nom_Redacteur]);
ALTER TABLE [NAPT] ADD FOREIGN KEY ([Prenom_nom_demandeur]) REFERENCES [Demandeurs] ([Prenom_nom_demandeur]);
ALTER TABLE [NAPT] ADD FOREIGN KEY ([PosteSource]) REFERENCES [PostesSources] ([PosteSource]);
ALTER TABLE [NAPT] ADD FOREIGN KEY ([Feeder]) REFERENCES [Feeders] ([Feeder]);
ALTER TABLE [NAPT] ADD FOREIGN KEY ([Prenom_charge_travaux]) REFERENCES [ChargerTravaux] ([prenom_charge_travaux]);
ALTER TABLE [NAPT] ADD FOREIGN KEY ([Prenom_Nom_controleur]) REFERENCES [Controleur] ([Prenom_Nom_controleur]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([Num]) REFERENCES [NAPT] ([Num]);
ALTER TABLE [consignation] ADD FOREIGN KEY ([Num]) REFERENCES [NAPT] ([Num]);
ALTER TABLE [Utilisateurs] ADD FOREIGN KEY ([typeuser]) REFERENCES [TypeUtilisateur] ([typeuser]);
ALTER TABLE [Tronçons] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDTronçons]) REFERENCES [Tronçons] ([IDTronçons]);
ALTER TABLE [PostesSources] ADD FOREIGN KEY ([IDTypeEquipement]) REFERENCES [TypeEquipement] ([IDTypeEquipement]);
ALTER TABLE [ReferenceClient] ADD FOREIGN KEY ([Codeagence]) REFERENCES [Agences] ([Codeagence]);
ALTER TABLE [PosteInterruption] ADD FOREIGN KEY ([NInterruption]) REFERENCES [Interruptions] ([NInterruption]);
ALTER TABLE [PosteClient] ADD FOREIGN KEY ([IDPostes]) REFERENCES [Postes] ([IDPostes]);
ALTER TABLE [PosteClient] ADD FOREIGN KEY ([Codereference]) REFERENCES [ReferenceClient] ([codereference]);
ALTER TABLE [Rapport] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE [Rapport] ADD FOREIGN KEY ([NInterruption]) REFERENCES [Interruptions] ([NInterruption]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDEquipements]) REFERENCES [EquipementsTransport] ([IDEquipements]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDSourceEquipement]) REFERENCES [SourceTransport] ([IDSourceEquipement]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDNature]) REFERENCES [Natures] ([IDNature]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDCauses]) REFERENCES [CausesTransport] ([IDCausesTrans]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDSieges]) REFERENCES [SiegesTransport] ([IDSieges]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([Matricule]) REFERENCES [Utilisateurs] ([Matricule]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDPosteLigne]) REFERENCES [PosteLigne] ([IDPosteLigne]);
ALTER TABLE [EquipementsTransport] ADD FOREIGN KEY ([IDSourceEquipement]) REFERENCES [SourceTransport] ([IDSourceEquipement]);
ALTER TABLE [EquipementsTransport] ADD FOREIGN KEY ([IDSieges]) REFERENCES [SiegesTransport] ([IDSieges]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDSignalisation]) REFERENCES [SignalisationsTransport] ([IDSignalisation]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([Directionimputable]) REFERENCES [Responsable] ([Directionimputable]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([Directionimputable]) REFERENCES [Responsable] ([Directionimputable]);
ALTER TABLE [EquipementsTransport] ADD FOREIGN KEY ([Tension]) REFERENCES [Tension] ([Tension]);
ALTER TABLE [EquipementsTransport] ADD FOREIGN KEY ([Lieu]) REFERENCES [Lieux] ([Lieu]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDTypeEND]) REFERENCES [TypeEND] ([IDTypeEND]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDTypeEND]) REFERENCES [TypeEND] ([IDTypeEND]);
ALTER TABLE [ReglesEND] ADD FOREIGN KEY ([IDTypeEND]) REFERENCES [TypeEND] ([IDTypeEND]);
ALTER TABLE [ReglesEND] ADD FOREIGN KEY ([IDCauses]) REFERENCES [Causes] ([IDCauses]);
ALTER TABLE [ReglesEND] ADD FOREIGN KEY ([IDNature]) REFERENCES [Natures] ([IDNature]);
ALTER TABLE [ReglesEND] ADD FOREIGN KEY ([IDCausesTrans]) REFERENCES [CausesTransport] ([IDCausesTrans]);
ALTER TABLE [EnergieND] ADD FOREIGN KEY ([IDTypeEND]) REFERENCES [TypeEND] ([IDTypeEND]);
ALTER TABLE [EnergieND] ADD FOREIGN KEY ([Directionimputable]) REFERENCES [Responsable] ([Directionimputable]);
ALTER TABLE [PosteInterruption] ADD FOREIGN KEY ([IDPostes]) REFERENCES [Postes] ([IDPostes]);
ALTER TABLE [Sieges] ADD FOREIGN KEY ([IDTypeReseau]) REFERENCES [TypeReseau] ([IDTypeReseau]);
ALTER TABLE [SiegesTransport] ADD FOREIGN KEY ([IDTypeReseau]) REFERENCES [TypeReseau] ([IDTypeReseau]);
ALTER TABLE [ClassementEND] ADD FOREIGN KEY ([IDCausesTrans]) REFERENCES [CausesTransport] ([IDCausesTrans]);
ALTER TABLE [ClassementEND] ADD FOREIGN KEY ([IDCauses]) REFERENCES [Causes] ([IDCauses]);
ALTER TABLE [ClassementEND] ADD FOREIGN KEY ([IDNature]) REFERENCES [Natures] ([IDNature]);
ALTER TABLE [ClassementEND] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [CopieSMS] ADD FOREIGN KEY ([Telephone]) REFERENCES [Repertoire] ([Telephone]);
ALTER TABLE [Sousgroupe] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [BoiteEnvoi] ADD FOREIGN KEY ([Telephone]) REFERENCES [Repertoire] ([Telephone]);
ALTER TABLE [Destinataire] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [Utilisateurs] ADD FOREIGN KEY ([Service]) REFERENCES [Services] ([Service]);
ALTER TABLE [Destinataire] ADD FOREIGN KEY ([exploitation]) REFERENCES [Exploitation] ([exploitation]);
ALTER TABLE [Destinataire] ADD FOREIGN KEY ([Groupe]) REFERENCES [GroupeEnvoi] ([Groupe]);
ALTER TABLE [LongueurReseau] ADD FOREIGN KEY ([IDResponsable]) REFERENCES [Responsable] ([IDResponsable]);
ALTER TABLE [ReferenceClient1] ADD FOREIGN KEY ([IDDelegation]) REFERENCES [Delegation] ([IDDelegation]);
ALTER TABLE [Delegation] ADD FOREIGN KEY ([IDRegions]) REFERENCES [Regions] ([IDRegions]);
ALTER TABLE [Services] ADD FOREIGN KEY ([IDDelegation]) REFERENCES [Delegation] ([IDDelegation]);
ALTER TABLE [Postes] ADD FOREIGN KEY ([ID_Service]) REFERENCES [Services] ([IDAUTO]);
ALTER TABLE [NombreClientMois] ADD FOREIGN KEY ([ID_Service]) REFERENCES [Services] ([IDAUTO]);
ALTER TABLE [NombreClientMois] ADD FOREIGN KEY ([IDDelegation]) REFERENCES [Delegation] ([IDDelegation]);
ALTER TABLE [ReferenceClient1] ADD FOREIGN KEY ([IDAgence]) REFERENCES [Agences] ([IDAgence]);
ALTER TABLE [Postes_Troncon] ADD FOREIGN KEY ([IDTroncon]) REFERENCES [Troncon] ([IDTroncon]);
ALTER TABLE [Postes_Troncon] ADD FOREIGN KEY ([IDPostes]) REFERENCES [Postes] ([IDPostes]);
ALTER TABLE [Noeuds] ADD FOREIGN KEY ([IDPostes]) REFERENCES [Postes] ([IDPostes]);
ALTER TABLE [Troncon] ADD FOREIGN KEY ([IDNoeudAmont]) REFERENCES [Noeuds] ([IDNoeuds]);
ALTER TABLE [Troncon] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDTroncon]) REFERENCES [Troncon] ([IDTroncon]);
ALTER TABLE [Troncon] ADD FOREIGN KEY ([IDNoeudAval]) REFERENCES [Noeuds] ([IDNoeuds]);
ALTER TABLE [Postes] ADD FOREIGN KEY ([IDType_Cellule]) REFERENCES [Type_Cellule] ([IDType_Cellule]);
ALTER TABLE [Noeuds] ADD FOREIGN KEY ([IDPosteSource]) REFERENCES [PostesSources] ([IDPosteSource]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDCentrale]) REFERENCES [dbo.Centrale] ([IDCentrale]);
ALTER TABLE [InterruptionsTransport] ADD FOREIGN KEY ([IDCentrale]) REFERENCES [dbo.Centrale] ([IDCentrale]);
ALTER TABLE [Agences_Postes] ADD FOREIGN KEY ([IDAgence]) REFERENCES [Agences] ([IDAgence]);
ALTER TABLE [Agences_Postes] ADD FOREIGN KEY ([IDPostes]) REFERENCES [Postes] ([IDPostes]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDService]) REFERENCES [Services] ([IDAUTO]);
ALTER TABLE [Feeders] ADD FOREIGN KEY ([IDService]) REFERENCES [Services] ([IDAUTO]);
ALTER TABLE [Feeders] ADD FOREIGN KEY ([IDPropritetaire_Ligne]) REFERENCES [Propritetaire_Ligne] ([IDPropritetaire_Ligne]);
ALTER TABLE [Longueur_Reseau_SIG] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE ['POSTES ET PIQUAGES DAKAR$'] ADD FOREIGN KEY ([IDTypeNoeud_SIG]) REFERENCES [TypeNoeud_SIG] ([IDTypeNoeud_SIG]);
ALTER TABLE [SIG] ADD FOREIGN KEY ([IDPropritetaire_Ligne]) REFERENCES [Propritetaire_Ligne] ([IDPropritetaire_Ligne]);
ALTER TABLE [Noeud_SIG] ADD FOREIGN KEY ([IDTypeNoeud_SIG]) REFERENCES [TypeNoeud_SIG] ([IDTypeNoeud_SIG]);
ALTER TABLE [Postes] ADD FOREIGN KEY ([FID]) REFERENCES [Noeud_SIG] ([FID]);
ALTER TABLE [SIG_FEEDERS$] ADD FOREIGN KEY ([IDPropritetaire_Ligne]) REFERENCES [Propritetaire_Ligne] ([IDPropritetaire_Ligne]);
ALTER TABLE [FEEDERS_SIG] ADD FOREIGN KEY ([IDPropritetaire_Ligne]) REFERENCES [Propritetaire_Ligne] ([IDPropritetaire_Ligne]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([ID_Troncon_SIG]) REFERENCES [Troncon_SIG] ([ID_Troncon_SIG]);
ALTER TABLE [PostesSources] ADD FOREIGN KEY ([FID]) REFERENCES [PosteSource_SIG] ([FID]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDService]) REFERENCES [Services] ([IDAUTO]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([ID_Troncon_SIG]) REFERENCES [Troncon_SIG] ([ID_Troncon_SIG]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([Num]) REFERENCES [NAPT] ([Num]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDCentrale]) REFERENCES [dbo.Centrale] ([IDCentrale]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDCauses]) REFERENCES [Causes] ([IDCauses]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDNature]) REFERENCES [Natures] ([IDNature]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDSieges]) REFERENCES [Sieges] ([IDSieges]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDSignalisation]) REFERENCES [Signalisations] ([IDSignalisation]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDTypePermanent]) REFERENCES [TypePermanent] ([IDTypePermanent]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([IDTypeEND]) REFERENCES [TypeEND] ([IDTypeEND]);
ALTER TABLE [Interruptions_OMVG] ADD FOREIGN KEY ([PosteSource]) REFERENCES [PostesSources] ([PosteSource]);
ALTER TABLE [PostesSources] ADD FOREIGN KEY ([IDO_M]) REFERENCES [O_M] ([IDO_M]);
ALTER TABLE [SourceTransport] ADD FOREIGN KEY ([IDO_M]) REFERENCES [O_M] ([IDO_M]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDEntreprise]) REFERENCES [Entreprise] ([IDEntreprise]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDPrestataire]) REFERENCES [Prestataire] ([IDPrestataire]);
ALTER TABLE [EquipementsTransport] ADD FOREIGN KEY ([IDPropriétaire]) REFERENCES [Propriétaire] ([IDPropriétaire]);
ALTER TABLE [EquipementsTransport] ADD FOREIGN KEY ([IDTypeEquipement]) REFERENCES [TypeEquipement] ([IDTypeEquipement]);
ALTER TABLE [TypeEND] ADD FOREIGN KEY ([IDResponsable]) REFERENCES [Responsable] ([IDResponsable]);
ALTER TABLE [SousFeeder] ADD FOREIGN KEY ([IDFeeder]) REFERENCES [Feeders] ([IDFeeder]);
ALTER TABLE [Interruptions] ADD FOREIGN KEY ([IDSousFeeder]) REFERENCES [SousFeeder] ([IDSousFeeder]);
ALTER TABLE [localite_senegal_Postes] ADD FOREIGN KEY ([Id]) REFERENCES [dbo.localite_senegal] ([id]);
ALTER TABLE [localite_senegal_Postes] ADD FOREIGN KEY ([IDPostes]) REFERENCES [Postes] ([IDPostes]);
