# Déploiement – Architecture & Exploitation

L’objectif est d’avoir une plateforme **rapide (< 2 s pour l’ACK)**, **scalable (500–1000 utilisateurs)**, **fiable (≈99,9 %)** et **conforme (RGPD/ISO)**.

## 1) Briques de l’architecture

### 1. Entrée & sécurité (porte d’accès)
- **Front Door + WAF** : protège l’API d’internet (anti‑bot, limitation de débit) et permet une bascule automatique si une région tombe.  
- **API Management (APIM)** : gère l’authentification (Azure AD), les quotas et les versions d’API.  
- **HTTPS partout** (TLS 1.2/1.3).

### 2. API (point de contact)
- **API stateless** (App Service ou AKS).  
- Reçoit `POST /job`, vérifie le schéma, place la demande en **file d’attente** et répond aussitôt avec un `job_id` (**< 2 s**).  
- Expose un **webhook** pour prévenir le client à la fin du traitement.

### 3. File d’attente (tampon anti‑pics)
- **Azure Service Bus (Premium)** : file fiable qui stocke chaque job.  
- En cas d’échec, le message part en **DLQ** (file d’erreur) pour être rejoué plus tard.

### 4. Workers
- **AKS (Kubernetes)** lance des **pods** qui consomment la file et traitent les jobs.  
- Chaque pod exécute l'**orchestrateur IA** + le **serveur MCP (Playwright)**.  
- **Autoscaling (KEDA)** : plus il y a de messages en attente, plus on lance de pods ; on réduit quand la charge baisse.

### 5. Sortie vers le web (respect des sites)
- Les requêtes sortent via une **NAT Gateway** avec **plusieurs adresses IP** (rotation simple).  
- Un « **Crawl Controller** » côté pods :  
  - lit et respecte **`robots.txt`** (y compris `crawl-delay`),  
  - applique un **quota par domaine** commun à tous les pods pour empécher un dépassement.

### 6. Données, sécurité et suivi
- **Base d’état (Cosmos DB)** pour suivre les jobs : en file, en cours, terminé, erreurs.  
- **Stockage des résultats (Blob Storage)** pour les fichiers **JSON** ; partage via **URL signées temporaires**.  
- **Clés & secrets** dans **Key Vault** (chiffrement au repos, rotation automatique).  
- **Logs & métriques centralisés** (Log Analytics / Application Insights) avec un **`job_id`** comme identifiant de corrélation pour suivre tout le parcours.  
- **Tableau de bord + alertes** (latence d’ACK, taux d’erreurs, quotas).  
- **Réseau isolé** : **VNet** avec sous‑réseaux séparés (entrée, workers, données) et **Private Endpoints**.  
- **Haute disponibilité** : services déployés sur **plusieurs zones** d’une même région ; option de **bascule automatique** vers une **2ᵉ région** via Front Door pour les pannes majeures.

## 2) Paramètres par défaut 

- **API** : timeout de requête **2 s** pour l’ACK ; validation du schéma en entrée.  
- **File d’attente** : **3 tentatives** de reprise par job, **backoff exponentiel**.  
- **Autoscaling** : déclenchement si **file > 10 messages/pod** création de nouveaux pods pour tenir la charge.  
- **Rétention** : résultats JSON **30–90 jours** (RGPD) ; logs **180 jours** (audit).  
- **Sécurité** : **TLS partout**.  
- **Haute disponibilité** : **multi‑zones** (et option **multi‑région**) pour viser **~99,9 %**.  
- **Chiffrement & secrets** : chiffrement au repos + **Key Vault** pour la gestion des clés.  
- **Réseau cloisonné** : **VNet**, sous‑réseaux dédiés, **NSG** et **Private Endpoints**.  
- **Traçabilité / Audit** : logs centralisés, **`job_id`** partout, **rapport mensuel automatisé**.
