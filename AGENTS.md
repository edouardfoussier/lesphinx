# LeSphinx - AGENTS.md

## Vue d'ensemble

**LeSphinx** est un jeu vocal style Akinator developpe lors du Hackathon Mistral. Le joueur pense a un personnage celebre, et le Sphinx (une creature mythique) pose des questions oui/non pour deviner qui c'est. Le jeu est bilingue (FR/EN) et utilise la synthese vocale pour une experience immersive.

## Stack technique

| Composant | Technologie | Role |
|-----------|-------------|------|
| Backend | FastAPI + Pydantic | API REST, game engine, orchestration |
| LLM | Mistral Large (`mistral-large-latest`) | Generer les questions/devinettes du Sphinx |
| TTS | ElevenLabs (`eleven_flash_v2_5`) | Voix grave/mysterieuse du Sphinx |
| STT | Web Speech API (navigateur) | Reconnaissance vocale cote client |
| Frontend | HTML + Vanilla JS + CSS | Zero build step, servi par FastAPI |
| Sessions | In-memory dict | Pas de base de donnees, single process |

## Architecture

```
Navigateur (Chrome)                          Serveur FastAPI
+---------------------------+                +---------------------------+
| index.html + app.js       |                | main.py                   |
|                           |  POST /game/new|                           |
| 1. Choix langue (fr/en)  +--------------->+ api/routes.py             |
| 2. Web Speech API (STT)  |                |   -> game/engine.py       |
| 3. Normalise oui/non/??  |  POST          |   -> llm/client.py        |
| 4. Envoie via /answer_text+--------------->+      (Mistral Large)      |
| 5. Recoit reponse JSON   |<---------------+   -> tts/client.py        |
| 6. Joue audio TTS        |  GET /audio/id |      (ElevenLabs)         |
| 7. Affiche texte bulle   +--------------->+   -> store/memory.py      |
+---------------------------+                +---------------------------+
```

### Communication : REST + texte

Le jeu est turn-based. Le frontend est un client muet : il envoie `yes`/`no`/`unknown` en texte, le backend fait tout (LLM, TTS, regles du jeu). Pas de WebSocket, pas de SSE -- du REST simple.

### State Machine

```
idle -> sphinx_speaking -> listening -> thinking -> sphinx_speaking -> ...
                                                  \-> ended
```

Geree cote serveur dans `game/state.py`. Chaque transition est validee.

### Game Engine (regles cote serveur)

Le LLM propose des actions, le `GameEngine` les valide et override si necessaire :

- Min 5 questions avant un guess
- Max 15 questions
- Max 2 tentatives de guess
- Auto-guess si confidence >= 0.85
- Hard stop a 20 tours
- Clamp confidence [0.0, 1.0]
- Si le LLM veut guess trop tot -> force question
- Si max questions atteint -> force guess ou end

### LLM Structured Output

Le LLM repond en JSON avec ce schema (`SphinxAction`) :

```json
{
  "type": "question|guess|clarify|end",
  "utterance": "La phrase du Sphinx",
  "confidence": 0.45,
  "top_candidates": ["Einstein", "Newton"],
  "reasoning_brief": "Scientifique homme europeen..."
}
```

On utilise `response_format={"type": "json_object"}` avec le format decrit dans le system prompt.

## Arborescence du projet

```
lesphinx/
  main.py                    # FastAPI entry point, sert les fichiers statiques
  config/settings.py         # Pydantic BaseSettings, charge .env
  game/
    engine.py                # GameEngine: regles, transitions, validation, overrides LLM
    models.py                # GameSession, Turn, request/response models
    state.py                 # State machine enum + transitions valides
  llm/
    client.py                # MistralLLMClient: chat.complete_async() + json_object
    prompts.py               # System prompt bilingue FR/EN + instructions JSON
    schemas.py               # SphinxAction Pydantic model
  stt/
    client.py                # VoxtralSTTClient (non utilise -- voir bugs)
    normalizer.py            # Texte libre -> yes/no/unknown (keywords FR+EN)
  tts/
    client.py                # ElevenLabsTTSClient: synthese vocale async
  store/
    base.py                  # SessionStore + AudioBlobStore protocols
    memory.py                # InMemorySessionStore + InMemoryAudioBlobStore
  api/
    deps.py                  # Singletons: session_store, audio_store, game_engine
    routes.py                # Tous les endpoints REST
  static/
    index.html               # SPA: ecran welcome, game, end
    app.js                   # Web Speech API, polling, audio playback, i18n
    style.css                # Theme egyptien/sphinx (Cinzel font, gold accents)
  logging.py                 # JSONL event logging
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/game/new` | Creer session. Body: `{"language": "fr"\|"en"}`. Retourne state + intro audio |
| GET | `/game/{id}/state` | Etat complet de la session |
| POST | `/game/{id}/answer_text` | Soumettre reponse texte (`yes`/`no`/`unknown`) -> LLM -> TTS |
| POST | `/game/{id}/answer` | Soumettre audio (multipart) -> STT -> normalize -> LLM -> TTS |
| GET | `/audio/{audio_id}` | Servir blob audio TTS (MP3) |

## Phases d'implementation

### Phase 1 : Squelette + Game Logic
- Settings Pydantic avec `.env`
- Modeles de donnees (GameSession, Turn)
- State machine avec transitions validees
- GameEngine avec toutes les regles du jeu
- Session store in-memory
- FastAPI skeleton + routes stub

### Phase 2 : LLM Integration
- Schema SphinxAction (question/guess/clarify/end)
- System prompt bilingue avec instructions JSON
- Client Mistral avec structured output
- Wire dans les routes `/answer_text`

### Phase 3 : TTS
- Client ElevenLabs async (eleven_flash_v2_5)
- Audio blob store en memoire
- Endpoint `/audio/{id}` pour servir les blobs

### Phase 4 : STT
- Client Voxtral (finalement remplace par Web Speech API)
- Normalisation texte -> yes/no/unknown (keywords FR+EN, longest-match)

### Phase 5 : Frontend
- HTML/CSS theme egyptien avec avatar Sphinx anime
- Web Speech API pour la reconnaissance vocale
- Boutons fallback oui/non/je ne sais pas
- Mode silencieux (pas de micro)
- i18n FR/EN complet

### Phase 6 : Polish
- JSONL logging des evenements de jeu
- Logs de debug dans les routes ([LLM OK], [LLM ERROR], [STT ERROR])
- README.md

## Bugs rencontres et corriges

### Bug 1 : Normalisation "absolument pas" -> "yes"

**Symptome** : Repondre "absolument pas" (non) etait detecte comme "yes" parce que "absolument" (keyword YES) matchait avant "absolument pas" (keyword NO).

**Cause** : L'iterateur parcourait les keywords YES avant NO, sans tenir compte de la longueur.

**Fix** : Tri de tous les keywords par longueur decroissante (longest-first) avant le matching. Ainsi "absolument pas" (13 chars) matche NO avant "absolument" (10 chars) matche YES. Corrige dans `stt/normalizer.py` et duplique dans `app.js` cote client.

### Bug 2 : STT Mistral (Voxtral) retourne 401 Unauthorized

**Symptome** : Le endpoint `/answer` (audio) retournait toujours 422. Les logs montraient `Status 401 Unauthorized` de l'API Mistral.

**Cause** : Double probleme. D'abord le modele STT etait `mistral-small-latest` au lieu de `voxtral-mini-latest`. Ensuite, meme avec le bon modele, la cle API Mistral n'avait pas acces a l'endpoint audio/transcription (tier de plan different).

**Fix** : Remplacement complet de l'approche STT. Au lieu d'envoyer l'audio au serveur pour transcription via Mistral, on utilise la **Web Speech API** du navigateur (Chrome). La reconnaissance vocale se fait cote client, le texte est normalise en JS, et seul `yes`/`no`/`unknown` est envoye au serveur via `/answer_text`. Zero API externe pour le STT.

### Bug 3 : Enregistrements audio trop courts (clics accidentels)

**Symptome** : Des requetes audio de 110 bytes envoyees au serveur, causant des erreurs ffmpeg "End of file".

**Cause** : L'utilisateur cliquait sur le bouton micro au lieu de le maintenir. Le MediaRecorder capturait un fragment vide.

**Fix** : (Resolu en meme temps que Bug 2) Le passage a Web Speech API a elimine ce probleme. Un simple clic lance la reconnaissance, pas besoin de maintenir.

### Bug 4 : LLM retourne le schema JSON au lieu de donnees

**Symptome** : Erreur Pydantic `Field required` avec `input_value={'properties': {'type': '...'}}`  -- le LLM renvoyait la definition du schema au lieu d'une instance.

**Cause** : `response_format` avec `json_schema` et `SphinxAction.model_json_schema()` causait le LLM a generer le schema lui-meme plutot que des donnees conformes.

**Fix** : Passage a `response_format={"type": "json_object"}` (JSON mode simple) + ajout d'instructions explicites dans le system prompt avec un exemple JSON complet du format attendu. Le LLM sait maintenant exactement quoi produire.

### Bug 5 : `chat.parse_async()` crashe avec "Unexpected type: 1.0"

**Symptome** : Erreur `Unexpected type: 1.0` a chaque appel LLM.

**Cause** : Le SDK Mistral `parse_async()` ne supportait pas les contraintes Pydantic `Field(ge=0.0, le=1.0)` dans la generation du schema JSON.

**Fix** : Retrait des contraintes `ge`/`le` du champ `confidence` dans `SphinxAction` + utilisation de `chat.complete_async()` avec `json_object` mode au lieu de `parse_async()`. Le clamp de confidence est fait par le GameEngine cote serveur.

### Bug 6 : Questions en boucle (LLM repetait les memes questions)

**Symptome** : Apres 4 questions, le Sphinx reposait les memes questions en boucle.

**Cause** : Combinaison de deux facteurs : (1) les erreurs LLM silencieuses faisaient tomber sur les questions fallback hardcodees a chaque tour, et (2) l'historique des conversations n'etait pas en format JSON, donc le LLM ne "voyait" pas ses questions precedentes.

**Fix** : Correction de tous les bugs LLM ci-dessus + reformatage des messages assistant en JSON dans `build_conversation_messages()` + ajout de la regle "Ne repose JAMAIS une question deja posee" dans le prompt + upgrade du modele `mistral-small-latest` -> `mistral-large-latest` pour un meilleur raisonnement.

## Configuration

Copier `.env.example` vers `.env` et remplir :

```bash
MISTRAL_API_KEY=xxx          # Required - cle API Mistral (avec acces chat)
MISTRAL_MODEL=mistral-large-latest
ELEVENLABS_API_KEY=xxx       # Required - cle API ElevenLabs (acces Text to Speech)
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB   # "Adam" voix grave
ELEVENLABS_MODEL=eleven_flash_v2_5
```

## Lancement

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # remplir les cles
uvicorn lesphinx.main:app --reload
# Ouvrir http://localhost:8000 dans Chrome
```
