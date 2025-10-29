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
- Mapping : exceptions Playwright -> `ToolError` -> payload `ok:false` homog?ne.
- Logging JSON sur stderr (`logging_conf`) : `tool_success`, `tool_failure`, `duration_ms`, `url`, `error_code`.
- Separation stricte : stdout pour MCP, stderr pour observabilite.

