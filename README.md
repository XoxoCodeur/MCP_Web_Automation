# MCP Web Automation - Test Technique Full Stack IA

Solution complète d'automatisation web intelligente utilisant le Model Context Protocol (MCP) et l'intelligence artificielle pour le scraping adaptatif.

## 📋 Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Partie 1 : Serveur MCP](#partie-1--serveur-mcp)
- [Partie 2 : Agent de Scraping Intelligent](#partie-2--agent-de-scraping-intelligent)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Architecture](#architecture)
- [Documentation](#documentation)

---

## 🎯 Vue d'ensemble

Ce projet implémente une solution complète d'automatisation web en deux parties :

1. **Serveur MCP** : Exposer 6 outils d'automatisation web (navigate, screenshot, extract_links, fill, click, get_html)
2. **Agent Intelligent** : Agent LLM capable d'extraire des données structurées depuis n'importe quelle page web selon un schéma JSON

### Technologies utilisées

- **Backend** : Python 3.11+
- **Automatisation** : Playwright
- **LLM** : OpenAI GPT-4o
- **Validation** : Pydantic
- **Protocole** : MCP (Model Context Protocol)

---

## 📦 Partie 1 : Serveur MCP

### Outils exposés

Le serveur MCP expose 6 outils d'automatisation web :

| Outil | Description |
|-------|-------------|
| `navigate` | Naviguer vers une URL |
| `screenshot` | Capturer l'écran (viewport ou page complète) |
| `extract_links` | Extraire tous les liens de la page |
| `fill` | Remplir un champ de formulaire |
| `click` | Cliquer sur un élément |
| `get_html` | Récupérer le HTML complet post-JavaScript |

### Format de réponse uniforme

```json
{
  "ok": true,
  "tool": "navigate",
  "session_id": "sess_abc123",
  "data": {"current_url": "https://example.com", "status": 200},
  "meta": {"ts": "2025-10-30T...", "duration_ms": 342}
}
```

### Démo Partie 1

```bash
python demo/scenario_part1.py
```

**Scénario** :
1. Naviguer vers https://example.com
2. Prendre une capture d'écran
3. Extraire tous les liens
4. Naviguer vers le premier lien externe
5. Capturer à nouveau l'écran

---

## 🤖 Partie 2 : Agent de Scraping Intelligent

### Fonctionnalités

L'agent utilise un LLM (GPT-4o) pour :
- ✅ Analyser automatiquement la structure HTML
- ✅ Identifier les sélecteurs CSS optimaux
- ✅ Extraire des données selon un schéma JSON
- ✅ Gérer la pagination automatiquement
- ✅ Convertir les types (string → number, boolean)
- ✅ Générer un rapport de qualité

### Configuration exemple

```json
{
  "url": "https://books.toscrape.com/",
  "schema": {
    "products": [
      {
        "title": "string",
        "price": "number",
        "availability": "string",
        "rating": "string"
      }
    ],
    "metadata": {
      "date_extraction": "datetime",
      "nb_resultats": "number"
    }
  },
  "options": {
    "pagination": true,
    "max_pages": 3
  }
}
```

### Démo Partie 2

```bash
python demo/scenario_part2.py
```

**Résultat** : Fichier JSON structuré avec données extraites + rapport de qualité

---

## 🚀 Installation

### Prérequis

- Python 3.10+
- pip

### Étapes

```bash
# 1. Cloner le repository
git clone https://github.com/votre-username/MCP_Web_Automation.git
cd MCP_Web_Automation

# 2. Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Installer le navigateur Playwright
playwright install chromium

# 5. Configurer l'API OpenAI (pour Partie 2)
cp .env.example .env
# Éditer .env et ajouter votre OPENAI_API_KEY
```

### Fichier .env

```bash
OPENAI_API_KEY=sk-...
```

---

## 💻 Utilisation

### Serveur MCP (Partie 1)

```python
from src.mcp_server import MCPServer

server = MCPServer()
server.run()
```

### Agent de scraping (Partie 2)

#### API Python

```python
from src.scraping_agent import ScrapingAgent, ScrapingConfig
from src.mcp_server import ToolService

agent = ScrapingAgent(
    openai_api_key="sk-...",
    tool_service=ToolService()
)

config = ScrapingConfig(
    url="https://example.com/products",
    schema={
        "products": [{"name": "string", "price": "number"}]
    },
    options={"pagination": True, "max_pages": 5}
)

result = agent.scrape(config)
print(result.data)
```

#### CLI

```bash
python src/scraping_cli.py \
  --config config.json \
  --output results.json
```

---

## 🏗️ Architecture

### Architecture globale

```
┌─────────────────────────────────────┐
│   Agent de Scraping Intelligent     │
│   (LLM + Orchestration)             │
└─────────────┬───────────────────────┘
              │ Appels directs Python
              ↓
┌─────────────────────────────────────┐
│      ToolService (MCP)              │
│  (navigate, click, get_html, etc.)  │
└─────────────┬───────────────────────┘
              │
              ↓
┌─────────────────────────────────────┐
│         Playwright                  │
│    (Chromium automation)            │
└─────────────────────────────────────┘
```

### Pourquoi pas MCP complet (stdio/SSE) ?

Pour un agent Python utilisant des outils Python dans le même projet, l'approche **appels directs** est optimale :
- ✅ Simplicité de développement
- ✅ Performance (pas d'overhead I/O)
- ✅ Gestion d'état simplifiée
- ✅ Facile à migrer vers MCP complet si besoin

Voir [DECISIONS_PART2.md](DECISIONS_PART2.md) pour les détails architecturaux.

---

## 📚 Documentation

### Fichiers de décisions techniques

- **[DECISIONS.md](DECISIONS.md)** : Décisions Partie 1 (Serveur MCP)
- **[DECISIONS_PART2.md](DECISIONS_PART2.md)** : Décisions Partie 2 (Agent intelligent)

### Structure du projet

```
MCP_Web_Automation/
├── src/
│   ├── mcp_server.py          # Serveur MCP principal
│   ├── scraping_agent.py      # Agent intelligent de scraping
│   ├── scraping_cli.py        # Interface CLI pour l'agent
│   ├── browser.py             # Gestionnaire de navigateur
│   ├── errors.py              # Gestion d'erreurs
│   ├── logging_conf.py        # Configuration logging
│   └── tools/                 # Outils MCP
│       ├── navigate.py
│       ├── screenshot.py
│       ├── extract_links.py
│       ├── fill.py
│       ├── click.py
│       └── get_html.py
├── demo/
│   ├── scenario_part1.py      # Démo Partie 1
│   └── scenario_part2.py      # Démo Partie 2
├── DECISIONS.md               # Décisions techniques Partie 1
├── DECISIONS_PART2.md         # Décisions techniques Partie 2
├── requirements.txt           # Dépendances Python
├── pyproject.toml             # Configuration projet
└── README.md                  # Ce fichier
```

---

## 🔧 Développement

### Exécuter les tests

```bash
# Partie 1
python demo/scenario_part1.py

# Partie 2
python demo/scenario_part2.py
```

### Logging

Les logs JSON sont écrits sur stderr :

```json
{"level":"INFO","message":"tool_success","tool":"navigate","duration_ms":342}
```

---

## 🚧 Limitations connues

1. **Contexte LLM** : HTML tronqué à 50KB
2. **Coût API** : Chaque page = 1 appel LLM
3. **Latence** : 2-5s par page (vs. scrapers traditionnels)
4. **Pagination scroll infini** : Non supportée
5. **Anti-bot** : Sites comme Amazon peuvent bloquer

Voir [DECISIONS_PART2.md](DECISIONS_PART2.md) section "Limitations" pour détails.

---

## 🔮 Évolutions futures

- [ ] Caching LLM pour pages similaires
- [ ] Support multi-LLM (Claude, Mistral, etc.)
- [ ] Outil `scroll` pour pagination infinie
- [ ] Stealth mode (user-agent, proxies)
- [ ] Authentication flows automatiques
- [ ] Rate limiting et respect robots.txt
- [ ] Monitoring Prometheus/Grafana

---

## 📄 Licence

Ce projet est un test technique réalisé dans le cadre d'un processus de recrutement.

---

## 👤 Auteur

**Robin** - Test Technique Full Stack IA - Octobre 2025

---

## 🙏 Remerciements

- [Playwright](https://playwright.dev/) pour l'automatisation navigateur
- [OpenAI](https://openai.com/) pour l'API GPT-4o
- [Anthropic](https://www.anthropic.com/) pour le protocole MCP
