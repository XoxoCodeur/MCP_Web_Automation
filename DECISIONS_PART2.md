# Décisions Techniques - Partie 2 : Agent Intelligent de Scraping

## Objectif et portée

Développer un agent intelligent capable d'extraire des données structurées depuis n'importe quelle page web dynamique, en s'appuyant sur un schéma JSON fourni par l'utilisateur. L'agent doit être adaptable, intelligent, et capable de gérer des interactions complexes, la pagination, et produire des rapports de qualité.

---

## 1. Architecture : Hybride Python-MCP (Appels directs)

### Décision architecturale

**L'agent appelle directement les outils MCP via `ToolService.call()` en Python, sans passer par le protocole MCP complet (stdio/SSE).**

#### ✅ Avantages de l'approche directe

1. **Simplicité de développement**
   - Pas de gestion de processus séparés
   - Debugging facilité (stack traces unifiées)
   - Code plus lisible et maintenable pour une version de dev

2. **Performance**
   - Pas de latence réseau 
   - Partage direct de l'état (session_id, browser context)
   - Appels synchrones rapides

3. **Évolutivité facilitée**
   - Facile de migrer vers MCP complet si besoin futur
   - Les structures MCP (format de réponse, erreurs) sont conservées
   - API `ToolService` reste inchangée


---

## 2. Choix du LLM : OpenAI GPT-4o

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
   - Latence acceptable 

### Alternatives considérées

| **GPT-3.5 Turbo** | Moins cher, rapide | Qualité d'extraction inférieure 
| **Modèles open-source** | Gratuit, auto-hébergeable | Qualité variable, setup plus complexe 

---


## 3. Gestion de la pagination

### Décision : Détection automatique via LLM

Au lieu de maintenir des règles fixes pour la pagination, l'agent **demande au LLM** d'identifier le sélecteur du bouton "page suivante".

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

## 4. Limitations assumées et évolutions futures

### Limitations connues

1. **Contexte LLM** : HTML tronqué à 50KB (peut manquer contenu de grandes pages)
2. **Coût API** : Chaque page = 1 appel LLM (peut être coûteux pour gros volumes)
3. **Latence** : 2-3s par page (plus lent que scrapers traditionnels)
4. **Sites avec anti-bot** : Amazon, Cloudflare challenge peuvent bloquer

### Acceptation de ces limitations

Ces limitations sont **acceptables pour un MVP intelligent** :
- L'adaptabilité et la maintenabilité compensent la latence/coût
- Pour un test technique, la solution démontre l'intelligence et la flexibilité
- En production, des optimisations sont possibles (voir ci-dessous)


---

## 5. Comparaison avec approche traditionnelle

### Scraper traditionnel (BeautifulSoup/Scrapy)

**Problèmes** :
- ❌ Cassant aux changements HTML
- ❌ Maintenance coûteuse (un scraper par site)
- ❌ Pas d'intelligence (ne s'adapte pas)

### Notre approche (LLM + MCP)

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

