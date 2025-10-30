Decision techniques
===================

Objectif et portee
------------------
- Construire un serveur MCP Python >= 3.10 qui expose 6 outils Web : navigate, screenshot, extract_links, fill, click, get_html.
- Reponses uniformes (`ok`, `tool`, `data` ou `error`, `meta` avec `ts`, `duration_ms`).
- Erreurs explicites + logging JSON. Script de demo : example.com -> screenshot -> liens -> 1er lien externe -> screenshot.

Choix Playwright (Python)
-------------------------
- Playwright retourne un HTML post-JS fiable via `page.content()`, ce qui couvre l'exigence "get_html apres execution JavaScript".
- Screenshots viewport et pleine page integres, indispensables pour l'outil screenshot.
- Locators moderns (visible/editable/clickable) qui simplifient fill et click, y compris les erreurs "element non visible / non editable / non clickable".
- Contexts isolables pour evolutions multi-sessions.
- Alternatives ecartees : Selenium (API plus verbeuse, waits moins confortables), Puppeteer/pyppeteer (stack JS). Playwright reduit la plomberie et securise les delais pour couvrir les 6 outils.

Transport MCP : stdio
---------------------
- L'enonce autorise stdio ou SSE : stdio est plus simple et portable pour la Partie 1, pas d'exposition reseau.
- stdout reserve aux messages MCP, stderr pour les logs (cf. section logs).
- Possibilite de passer a SSE plus tard sans changement des outils.

Cycle de vie MCP & API exposee
------------------------------
- `initialize` -> handshake + infos serveur.
- `tools/list` -> catalogue des 6 outils + schema d'entree (Pydantic -> JSON Schema).
- `tools/call` -> execution d'un outil.
- Format de reponse uniforme :
  - succes : `{ok:true, tool, session_id?, data, meta{ts,duration_ms}}`
  - erreur : `{ok:false, tool, error{code,message}, meta{ts,duration_ms}}`
- Outils couverts :
  - `navigate` : validation scheme http(s), gestion timeout/erreurs reseau.
  - `screenshot` : `mode` viewport/fullpage.
  - `extract_links` : texte + URL + filtre optionnel.
  - `fill` : selector,value + controles (existe, visible, editable).
  - `click` : selector + controles (existe, visible, enabled/clickable).
  - `get_html` : HTML rendu post-JS.

Sessions et etat
----------------
- Partie 1 : une seule session implicite geree par `BrowserManager` (un onglet courant reutilise). Suffisant pour le scenario impose.
- `BrowserManager` amortit le cout de lancement Playwright et assure un flow fluide navigate -> screenshot -> click ...
- Evolution : ajouter un `session_id` optionnel pour le multi-agent ou le parallele.

Erreur et logging
-----------------
- Codes fixes : `INVALID_URL`, `NAVIGATION_TIMEOUT`, `NETWORK_ERROR`, `ELEMENT_NOT_FOUND`, `ELEMENT_NOT_VISIBLE`, `ELEMENT_NOT_EDITABLE`, `ELEMENT_NOT_CLICKABLE`, `INTERNAL_ERROR`.
- Mapping : exceptions Playwright -> `ToolError` -> payload `ok:false` homogène.
- Logging JSON sur stderr (`logging_conf`) : `tool_success`, `tool_failure`, `duration_ms`, `url`, `error_code`.
- Separation stricte : stdout pour MCP, stderr pour observabilite.

---

# Partie 2 : Agent Intelligent de Web Scraping

Objectif et portée
------------------
- Construire un agent intelligent capable d'extraire des données structurées depuis n'importe quelle page web dynamique
- Utiliser un LLM (Claude) pour analyser le HTML et identifier automatiquement les sélecteurs CSS
- Supporter les interactions préliminaires (cookies, popups), la pagination, et générer des rapports de qualité
- Architecture : LLM + MCP tools (réutilisation complète de la Partie 1)

Choix d'architecture : LLM + MCP
---------------------------------
**Décision** : Utiliser Claude (Anthropic) comme moteur d'analyse et d'orchestration, en s'appuyant sur les outils MCP de la Partie 1.

**Rationale** :
- **Séparation des responsabilités** : Le MCP server fournit les primitives d'automatisation (navigate, click, get_html), l'agent fournit l'intelligence
- **Adaptabilité** : L'agent peut s'adapter aux changements de structure HTML sans modification de code
- **Maintenance** : Pas besoin de maintenir des sélecteurs CSS fragiles manuellement
- **Réutilisation** : Les outils MCP existants sont réutilisés tels quels, aucune modification nécessaire

**Alternatives écartées** :
- BeautifulSoup + règles fixes : Trop rigide, nécessite des sélecteurs manuels, cassant aux changements
- Framework scraping traditionnel (Scrapy) : Pas d'intelligence, requiert configuration manuelle extensive
- Vision-based extraction (screenshot → OCR/vision) : Plus coûteux, moins précis pour données structurées

Choix du LLM : Claude (Anthropic)
----------------------------------
**Décision** : Utiliser Claude 3.5 Sonnet pour l'analyse HTML et l'extraction de données.

**Rationale** :
- **Contexte large** : 200K tokens permettent d'analyser des pages HTML complètes
- **Qualité d'extraction** : Excellente compréhension de structures HTML et JSON
- **Fiabilité** : Génération de JSON structuré très cohérente
- **API mature** : SDK Python officiel avec gestion d'erreurs robuste
- **Latence acceptable** : ~2-5s par page, acceptable pour scraping batch

**Alternatives considérées** :
- GPT-4 : Qualité similaire mais plus coûteux, contexte plus limité
- Modèles open-source (Llama, Mixtral) : Qualité d'extraction inférieure, nécessite hébergement
- Modèles spécialisés scraping : N'existent pas avec cette flexibilité

Architecture de l'agent
------------------------
```
ScrapingAgent
    ↓
┌───┴──────────────────────┐
│  1. Analyse schéma       │ (Comprendre la structure cible)
│  2. Navigation & HTML    │ (Via MCP tools)
│  3. Interactions         │ (Cookies, popups via MCP)
│  4. Extraction LLM       │ (Claude analyse + extrait)
│  5. Pagination           │ (Détection auto + navigation)
│  6. Structuration        │ (Validation + typage)
│  7. Rapport qualité      │ (Métriques de complétude)
└──────────────────────────┘
```

**Principes** :
- **Stateless per page** : Chaque page est analysée indépendamment
- **Session management** : Réutilisation du `session_id` MCP pour continuité du navigateur
- **Error resilience** : Échecs d'extraction ne bloquent pas le flow complet
- **Progressive enhancement** : Fonctionne sans pagination/interactions, ajout progressif de features

Extraction LLM : Stratégie de prompting
----------------------------------------
**Décision** : Utiliser un prompt structuré avec le schéma JSON + HTML tronqué (50KB).

**Format du prompt** :
```
You are a web scraping expert.

TARGET SCHEMA: [schema JSON]
HTML CONTENT: [HTML tronqué]

INSTRUCTIONS:
1. Analyze HTML structure
2. Identify CSS selectors for each field
3. Extract ALL items matching schema
4. Convert types (string → number, boolean)
5. Return ONLY valid JSON

OUTPUT: {"items": [...]}
```

**Rationale** :
- **Clarté** : Instructions explicites réduisent les hallucinations
- **Structure** : Format de sortie fixe facilite le parsing
- **Contexte limité** : Troncature HTML à 50KB évite dépassement de contexte
- **Température 0** : Maximum de déterminisme pour extraction reproductible

**Optimisations** :
- Troncature intelligente : Garder début de HTML (structure générale)
- Pas de markdown dans réponse : Extraction JSON pure
- Validation post-extraction : Parser JSON systématiquement

Gestion de la pagination
-------------------------
**Décision** : Détection automatique via LLM + navigation MCP.

**Workflow** :
1. Agent demande à Claude : "Identifie le sélecteur du bouton 'page suivante'"
2. Claude analyse HTML et retourne le sélecteur (ou "NO_PAGINATION")
3. Agent utilise l'outil `click` MCP pour naviguer
4. Processus répété jusqu'à `max_pages` ou fin de pagination

**Rationale** :
- **Adaptabilité** : Fonctionne sur différents patterns de pagination (boutons, liens, numéros)
- **Pas de règles fixes** : Pas besoin de maintenir une liste de sélecteurs par site
- **Robustesse** : Si détection échoue, continue avec pages déjà extraites

**Limitations connues** :
- Pagination infinie (scroll) non supportée (nécessite outil scroll + monitoring)
- Sites avec pagination JS complexe peuvent échouer

Interactions préliminaires
---------------------------
**Décision** : Système d'interactions configurable exécuté avant extraction.

**Types supportés** :
- `click` : Accepter cookies, fermer popups
- `wait` : Attendre chargement dynamique
- `fill` : Remplir champs de recherche (futurs cas d'usage)
- `scroll` : Déclaré mais non implémenté (nécessite ajout d'outil MCP)

**Exécution** :
- Séquentielle (ordre défini par utilisateur)
- Échecs non bloquants : Warning loggé, extraction continue
- Utilise les outils MCP `click`, `fill` directement

**Rationale** :
- **Flexibilité** : Utilisateur définit les interactions nécessaires par site
- **Réutilisation MCP** : Aucune logique spéciale, délégation aux outils existants
- **Évolutif** : Facile d'ajouter nouveaux types d'interactions

Conversion et validation des types
-----------------------------------
**Décision** : Confier la conversion au LLM via instructions de prompt.

**Instructions LLM** :
- `"string"` → Extraire texte brut
- `"number"` → Retirer symboles (€, $), convertir en float
- `"boolean"` → Analyser présence/absence ou mots-clés (en stock, disponible)
- `"datetime"` → Format ISO 8601

**Validation post-extraction** :
- Vérifier présence des champs requis
- Détecter valeurs `null` ou manquantes
- Compter items complets vs. items avec données manquantes

**Rationale** :
- **Simplicité** : Pas de code de conversion complexe côté Python
- **Intelligence** : LLM comprend contexte (ex: "En stock" → true, "Épuisé" → false)
- **Flexibilité** : Supporte variations de format sans code supplémentaire

Rapport de qualité
-------------------
**Décision** : Générer automatiquement des métriques de complétude.

**Métriques incluses** :
- `total_items` : Nombre total d'items extraits
- `complete_items` : Items sans champs manquants
- `completion_rate` : Taux de complétude (0.0 - 1.0)
- `missing_fields` : Liste des champs manquants avec fréquence
- `errors` : Erreurs rencontrées (si applicable)

**Génération** :
- Analyse récursive des objets extraits
- Détection des valeurs `null`, `""`, champs absents
- Agrégation par chemin de champ (ex: "specifications.cpu: 2 items")

**Rationale** :
- **Transparence** : Utilisateur sait immédiatement si extraction est fiable
- **Débogage** : Identification rapide des champs problématiques
- **Amélioration** : Guide pour affiner le schéma ou ajouter interactions

Interface CLI et API Python
----------------------------
**Décision** : Fournir deux interfaces pour l'agent.

**1. API Python** :
```python
agent = ScrapingAgent(api_key, tool_service)
result = agent.scrape(config)
```
- Usage programmatique
- Intégration dans pipelines
- Contrôle fin sur configuration

**2. CLI Tool** :
```bash
mcp-scraping-agent --config config.json --output results.json
```
- Usage rapide depuis terminal
- Scripts batch
- Configuration via fichiers JSON

**Rationale** :
- **Accessibilité** : CLI pour utilisateurs non-développeurs
- **Flexibilité** : API Python pour intégration avancée
- **Standardisation** : Format JSON uniforme pour config et résultats

Gestion des erreurs et resilience
----------------------------------
**Décision** : Échecs partiels ne bloquent pas l'extraction complète.

**Stratégies** :
- **Interaction failed** : Log warning, continue extraction
- **Page extraction failed** : Retourne items des pages précédentes
- **Pagination detection failed** : Arrête pagination, retourne données acquises
- **Type conversion failed** : Champ mis à `null`, item marqué incomplet

**Format de réponse** :
- `status: "success"` si au moins une page extraite
- `status: "error"` si échec complet (navigation, etc.)
- Toujours inclure `quality_report` même en cas d'échec partiel

**Rationale** :
- **Robustesse** : Données partielles valent mieux que rien
- **Visibilité** : Quality report révèle les problèmes
- **Production-ready** : Comportement prévisible même en cas d'anomalie

Limitations et contraintes assumées
------------------------------------
1. **Contexte LLM** : HTML tronqué à 50KB (peut manquer contenu de grandes pages)
2. **Coût API** : Chaque page = 1 appel Claude (peut être coûteux pour gros volumes)
3. **Latence** : 2-5s par page (plus lent que scrapers traditionnels)
4. **Scroll infini** : Non supporté (nécessite outil MCP supplémentaire)
5. **JavaScript monitoring** : Pas de détection de chargements AJAX post-navigation

**Acceptation** :
- Ces limitations sont acceptables pour un MVP intelligent
- L'adaptabilité et la maintenabilité compensent la latence/coût
- Évolutions possibles : caching LLM, streaming, optimisation prompts

Évolutions futures possibles
-----------------------------
- **Caching LLM** : Réutiliser analyses pour pages similaires
- **Multi-LLM** : Support OpenAI, Mistral, etc.
- **Outil scroll** : Ajouter au MCP server pour pagination infinie
- **Proxy rotation** : Pour scraping à grande échelle
- **Rate limiting** : Intégré dans l'agent
- **Authentication flows** : Login automatique avant scraping
- **Monitoring & alerting** : Intégration Prometheus/Grafana

