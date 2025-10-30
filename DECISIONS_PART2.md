# Décisions Techniques - Partie 2 : Agent Intelligent de Scraping

## Objectif et portée

Développer un agent intelligent capable d'extraire des données structurées depuis n'importe quelle page web dynamique, en s'appuyant sur un schéma JSON fourni par l'utilisateur. L'agent doit être adaptable, intelligent, et capable de gérer des interactions complexes, la pagination, et produire des rapports de qualité.

---

## 1. Architecture : Hybride Python-MCP (Appels directs)

### Décision architecturale

**L'agent appelle directement les outils MCP via `ToolService.call()` en Python, sans passer par le protocole MCP complet (stdio/SSE).**

```python
# Architecture implémentée
ScrapingAgent (Python)
    ↓ appel direct Python
ToolService.call(tool_name, args)
    ↓
MCP Tools (navigate, click, get_html, etc.)
    ↓
Playwright
```

### Pourquoi ne pas utiliser le protocole MCP complet ?

Le test technique demande de "s'appuyer sur le serveur MCP créé dans la Partie 1", ce qui pourrait suggérer une communication via stdio/SSE. Cependant, nous avons choisi une **intégration directe en Python** pour les raisons suivantes :

#### ✅ Avantages de l'approche directe

1. **Simplicité de développement**
   - Pas de gestion de processus séparés
   - Pas de sérialisation/désérialisation JSON RPC
   - Debugging facilité (stack traces unifiées)
   - Code plus lisible et maintenable

2. **Performance**
   - Pas d'overhead de communication inter-processus
   - Pas de latence réseau (même minime)
   - Partage direct de l'état (session_id, browser context)
   - Appels synchrones rapides

3. **Gestion d'état simplifiée**
   - Session partagée entre agent et outils dans le même processus
   - Pas de synchronisation complexe
   - BrowserManager singleton accessible directement

4. **Évolutivité facilitée**
   - Facile de migrer vers MCP complet si besoin futur
   - Les structures MCP (format de réponse, erreurs) sont conservées
   - API `ToolService` reste inchangée

#### 🔄 Quand utiliser MCP complet vs. appels directs ?

| Critère | MCP Complet (stdio/SSE) | Appels Directs (notre choix) |
|---------|------------------------|------------------------------|
| **Agents externes** | ✅ Nécessaire | ❌ Non supporté |
| **Multi-langage** | ✅ Agent Python/JS/Go | ❌ Python uniquement |
| **Isolation processus** | ✅ Crash-proof | ❌ Crash agent = crash tools |
| **Performance** | ⚠️ Overhead I/O | ✅ Appels directs |
| **Développement** | ⚠️ Plus complexe | ✅ Simplifié |
| **Même codebase** | ❌ Non pertinent | ✅ Optimal |

**Conclusion** : Pour un agent Python utilisant des outils Python dans le même projet, l'approche directe est **optimale**. MCP complet serait surdimensionné ici.

---

## 2. Réutilisation des structures MCP

Bien que nous n'utilisions pas le protocole complet, **nous conservons les structures et conventions MCP** pour garantir la cohérence et faciliter une migration future :

### Format de réponse uniforme

```python
# Succès
{
    "ok": True,
    "tool": "navigate",
    "session_id": "sess_abc123",
    "data": {"current_url": "...", "status": 200},
    "meta": {"ts": "2025-10-30T...", "duration_ms": 342}
}

# Erreur
{
    "ok": False,
    "tool": "click",
    "error": {"code": "ELEMENT_NOT_VISIBLE", "message": "..."},
    "meta": {"ts": "2025-10-30T...", "duration_ms": 5072}
}
```

### Gestion d'erreurs cohérente

```python
# L'agent utilise les mêmes ErrorCode que MCP
from src.errors import ToolError, ErrorCode

try:
    session_id, data = self._call_tool("click", {...})
except ToolError as e:
    if e.code == ErrorCode.ELEMENT_NOT_VISIBLE:
        # Gestion spécifique
```

### Avantages de cette cohérence

- **Logs uniformes** : Même format JSON que la Partie 1
- **Migration facilitée** : Si besoin de passer à MCP complet, l'agent ne change presque pas
- **Maintenabilité** : Une seule convention de gestion d'erreurs dans tout le projet

---

## 3. Choix du LLM : OpenAI GPT-4o

### Décision

Utiliser **GPT-4o** (via l'API OpenAI) pour l'analyse HTML et l'extraction de données.

### Rationale

1. **Contexte suffisant**
   - 128K tokens permettent d'analyser des pages HTML complètes
   - Stratégie de troncature à 50KB pour rester confortable

2. **Qualité d'extraction**
   - Excellente compréhension de structures HTML et JSON
   - Génération de JSON structuré cohérente
   - Bonne performance sur identification de sélecteurs CSS

3. **API mature et fiable**
   - SDK Python officiel (`openai`)
   - Gestion d'erreurs robuste
   - Latence acceptable (~2-3s par page)

4. **Coût raisonnable**
   - GPT-4o moins cher que GPT-4
   - Pour un MVP/test technique, le coût est acceptable
   - Production : possibilité de caching ou batching

### Alternatives considérées

| Modèle | Avantages | Inconvénients | Décision |
|--------|-----------|---------------|----------|
| **Claude 3.5 Sonnet** | Contexte 200K, excellente qualité | API Anthropic moins familière | ⚠️ Viable |
| **GPT-4 Turbo** | Qualité maximale | Plus cher, latence plus élevée | ❌ |
| **GPT-3.5 Turbo** | Moins cher, rapide | Qualité d'extraction inférieure | ❌ |
| **Modèles open-source** | Gratuit, auto-hébergeable | Qualité variable, setup complexe | ❌ |

---

## 4. Stratégie d'extraction : Prompting structuré

### Approche choisie

L'agent utilise un **prompt structuré** pour chaque page, avec le schéma JSON cible et le HTML tronqué.

### Format du prompt

```python
prompt = f"""You are a web scraping expert. Extract structured data from HTML.

TARGET SCHEMA:
{json.dumps(schema, indent=2)}

HTML CONTENT (truncated to 50KB):
{html_content[:50000]}

INSTRUCTIONS:
1. Analyze the HTML structure carefully
2. Identify CSS selectors for each field in the schema
3. Extract ALL items matching the schema structure
4. Convert types according to schema (string → number, boolean, etc.)
5. Handle missing data gracefully (use null)
6. Return ONLY valid JSON, no markdown, no explanations

OUTPUT FORMAT:
{{"items": [...]}}
"""
```

### Rationale

1. **Clarté des instructions**
   - Réduit les hallucinations du LLM
   - Format de sortie explicite (JSON pur)
   - Gestion des types demandée explicitement

2. **Contexte limité**
   - Troncature à 50KB évite dépassement de limite
   - Garde le début du HTML (structure générale + premiers items)

3. **Température 0**
   - Maximum de déterminisme
   - Extraction reproductible

4. **Validation post-extraction**
   - Parsing JSON systématique
   - Détection des erreurs de format
   - Retry possible si échec

---

## 5. Gestion de la pagination

### Décision : Détection automatique via LLM

Au lieu de maintenir des règles fixes pour la pagination, l'agent **demande au LLM** d'identifier le sélecteur du bouton "page suivante".

### Workflow

```python
# 1. Demander au LLM le sélecteur de pagination
prompt = """Analyze this HTML and identify the CSS selector for the "next page" button.

INSTRUCTIONS:
- The button MUST be active (not disabled)
- Avoid disabled elements (check for "disabled" class, aria-disabled)
- Prefer specific selectors (e.g., li.next:not(.disabled) a)
- Return ONLY the selector or "NO_PAGINATION"
"""

selector = llm.generate(prompt)

# 2. Si sélecteur trouvé, cliquer via MCP
if selector != "NO_PAGINATION":
    self._call_tool("click", {"selector": selector})
```

### Avantages

1. **Adaptabilité** : Fonctionne sur différents patterns (boutons, liens, numéros de page)
2. **Pas de règles fixes** : Pas de maintenance de liste de sélecteurs par site
3. **Intelligence contextuelle** : Le LLM comprend "disabled", "current", "active"

### Améliorations apportées

Lors du développement, nous avons identifié et corrigé plusieurs problèmes :

1. **Nettoyage du sélecteur**
   - Le LLM retournait parfois `` `.next` `` (avec backticks)
   - Solution : Strip des backticks inline et blocs markdown

2. **Détection de fin de pagination**
   - Le sélecteur `.next` peut exister mais être désactivé sur la dernière page
   - Solution : Prompt amélioré demandant explicitement d'éviter les éléments désactivés

3. **Scroll automatique**
   - Ajout de `scroll_into_view_if_needed()` dans l'outil `click`
   - Résout les cas où le bouton est hors viewport

---

## 6. Rapport de qualité

### Décision : Métriques automatiques de complétude

Chaque extraction génère un **rapport de qualité** automatique pour évaluer la fiabilité des données extraites.

### Métriques incluses

```json
{
    "quality_report": {
        "total_items": 24,
        "complete_items": 22,
        "completion_rate": 0.917,
        "missing_fields": [
            "specifications.cpu: 2 items"
        ],
        "errors": []
    }
}
```

### Génération

```python
def _check_completeness(self, item: dict, missing_fields: dict) -> bool:
    """Recursively check if item has all fields populated."""
    is_complete = True

    for key, value in item.items():
        if value is None or value == "":
            is_complete = False
            missing_fields[key] = missing_fields.get(key, 0) + 1
        elif isinstance(value, dict):
            # Recurse into nested objects
            is_complete &= self._check_completeness(value, missing_fields)
```

### Rationale

1. **Transparence** : L'utilisateur sait immédiatement si l'extraction est fiable
2. **Débogage** : Identification rapide des champs problématiques
3. **Amélioration** : Guide pour affiner le schéma ou ajouter des interactions

---

## 7. Gestion des erreurs : Résilience maximale

### Principe : Échecs partiels ne bloquent pas l'extraction

L'agent est conçu pour **continuer même en cas d'erreurs partielles**.

### Stratégies de résilience

| Situation | Comportement | Rationale |
|-----------|--------------|-----------|
| **Navigation échoue** | Erreur fatale, status="error" | Pas de HTML = pas d'extraction |
| **Interaction échoue** | Warning log, continue | Cookies/popups optionnels |
| **Extraction page 1 OK, page 2 KO** | Retourne page 1, rapport partiel | Données partielles > rien |
| **Pagination non détectée** | Arrête pagination, retourne données | Normal sur dernière page |
| **Conversion type échoue** | Champ à `null`, item incomplet | Signalé dans quality_report |

### Format de réponse

```python
# Succès (même partiel)
{
    "status": "success",
    "data": {...},          # Données extraites (même partielles)
    "quality_report": {...} # Indique la complétude
}

# Erreur fatale uniquement
{
    "status": "error",
    "error": "Navigation timeout",
    "data": None,
    "quality_report": None
}
```

### Avantages

- **Robustesse** : Production-ready, comportement prévisible
- **Visibilité** : Le quality_report révèle les problèmes
- **Valeur maximale** : Données partielles valent mieux que rien

---

## 8. Interactions préliminaires

### Décision : Système configurable par l'utilisateur

L'utilisateur peut définir des **interactions préliminaires** à exécuter avant l'extraction (accepter cookies, fermer popups, etc.).

### Configuration

```json
{
    "interactions": [
        {"type": "click", "selector": "#accept-cookies"},
        {"type": "wait", "duration": 2000},
        {"type": "scroll", "direction": "bottom"}
    ]
}
```

### Implémentation

```python
for interaction in config.interactions:
    if interaction["type"] == "click":
        self._call_tool("click", {"selector": interaction["selector"]})
    elif interaction["type"] == "wait":
        time.sleep(interaction["duration"] / 1000)
    # scroll non implémenté (nécessite ajout outil MCP)
```

### Rationale

1. **Flexibilité** : Chaque site a ses propres popups/cookies
2. **Réutilisation MCP** : Délégation aux outils existants
3. **Non-bloquant** : Échec d'interaction = warning, extraction continue

---

## 9. Limitations assumées et évolutions futures

### Limitations connues

1. **Contexte LLM** : HTML tronqué à 50KB (peut manquer contenu de grandes pages)
2. **Coût API** : Chaque page = 1 appel LLM (peut être coûteux pour gros volumes)
3. **Latence** : 2-5s par page (plus lent que scrapers traditionnels)
4. **Pagination scroll infini** : Non supportée (nécessite outil `scroll` MCP)
5. **Sites avec anti-bot** : Amazon, Cloudflare challenge peuvent bloquer

### Acceptation de ces limitations

Ces limitations sont **acceptables pour un MVP intelligent** :
- L'adaptabilité et la maintenabilité compensent la latence/coût
- Pour un test technique, la solution démontre l'intelligence et la flexibilité
- En production, des optimisations sont possibles (voir ci-dessous)

### Évolutions futures possibles

1. **Caching LLM** : Réutiliser analyses pour pages similaires
2. **Multi-LLM** : Support Claude, Mistral, modèles locaux
3. **Outil scroll** : Ajouter au MCP server pour pagination infinie
4. **Stealth mode** : User-agent, proxies, delays anti-détection
5. **Authentication flows** : Login automatique avant scraping
6. **Rate limiting** : Intégré dans l'agent (respect robots.txt)
7. **Monitoring** : Intégration Prometheus/Grafana pour métriques
8. **Batching** : Grouper plusieurs pages dans un seul appel LLM

---

## 10. Comparaison avec approche traditionnelle

### Scraper traditionnel (BeautifulSoup/Scrapy)

```python
# Approche traditionnelle : sélecteurs fixes
products = soup.select(".product-card")
for product in products:
    title = product.select_one(".title").text
    price = float(product.select_one(".price").text.replace("€", ""))
```

**Problèmes** :
- ❌ Cassant aux changements HTML
- ❌ Maintenance coûteuse (un scraper par site)
- ❌ Pas d'intelligence (ne s'adapte pas)

### Notre approche (LLM + MCP)

```python
# Approche intelligente : agent adaptatif
agent = ScrapingAgent(api_key, tool_service)
result = agent.scrape(config)  # Le LLM trouve les sélecteurs
```

**Avantages** :
- ✅ S'adapte aux changements HTML
- ✅ Un seul agent pour tous les sites
- ✅ Maintenance minimale (pas de sélecteurs en dur)
- ✅ Quality report automatique

**Trade-offs** :
- ⚠️ Plus lent (2-5s/page vs. 0.1s/page)
- ⚠️ Coût API (LLM)
- ⚠️ Dépendance externe (API OpenAI)

**Conclusion** : Pour des sites changeants, à faible volume, ou nécessitant de l'adaptabilité, notre approche est **supérieure**. Pour du scraping massif et stable, l'approche traditionnelle reste pertinente.

---

## Conclusion

L'architecture hybride choisie (appels directs Python-MCP) offre le meilleur compromis entre **simplicité, performance, et maintenabilité** pour ce projet. Elle :

- ✅ Réutilise les outils MCP de la Partie 1
- ✅ Conserve les conventions MCP (formats, erreurs)
- ✅ Permet une migration future vers MCP complet si besoin
- ✅ Offre une solution production-ready avec résilience et qualité

L'utilisation d'un **LLM pour l'analyse et l'extraction** apporte une **intelligence et adaptabilité** impossibles avec des approches traditionnelles, au prix d'une latence et d'un coût acceptables pour ce cas d'usage.
