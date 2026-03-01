# LeSphinx - AGENTS.md

## Vue d'ensemble

**LeSphinx** est un jeu vocal de devinettes developpe lors du Hackathon Mistral. Le Sphinx (creature mythique) pense a un personnage celebre, et le joueur pose des questions en langage naturel pour deviner qui c'est. Le Sphinx ne repond que par oui, non, ou je ne sais pas, avec une voix theatrale et mysterieuse. Le jeu est bilingue (FR/EN), dispose d'un systeme de scoring, d'un leaderboard, et d'achievements.

**Deploye sur** : [thesphinx.ai](https://thesphinx.ai)

## Stack technique

| Composant | Technologie | Role |
|-----------|-------------|------|
| Backend | FastAPI + Pydantic | API REST, game engine, orchestration |
| LLM | Mistral Large (`mistral-large-latest`) | Interpreter de questions + Voix du Sphinx + Fallback resolver |
| LLM (classif.) | Mistral Small (`mistral-small-latest`) | Intent classifier rapide (question vs guess) |
| TTS | ElevenLabs (`eleven_flash_v2_5`, streaming) | Voix grave/mysterieuse du Sphinx |
| STT | Web Speech API (navigateur) | Reconnaissance vocale cote client |
| Frontend | HTML + Vanilla JS + CSS | Zero build step, servi par FastAPI |
| Sessions | In-memory dict | Pas de base de donnees, single process |
| Persistence | JSON files | Leaderboard + stats (survit aux restarts) |
| Deploiement | Google VM + Caddy + Cloudflare | HTTPS auto, reverse proxy, DNS |

## Architecture

### Mode Hybrid (par defaut)

```
Joueur (Chrome)                              Serveur FastAPI
+---------------------------+                +---------------------------+
| index.html + app.js       |                | main.py                   |
|                           |  POST /game/new|                           |
| 1. Choix langue/diff/theme+--------------->+ api/routes.py             |
| 2. Web Speech API (STT)   |               |   -> SecretSelector       |
| 3. Question libre (voix   |  POST /ask    |   -> GameEngine           |
|    ou texte)              +--------------->+   -> SurrenderDetector    |
| 4. Recoit JSON + audio    |<---------------+   -> RuleMatcher (regex)  |
| 5. Joue audio TTS         |  GET /audio/id|   -> IntentClassifier     |
| 6. Affiche dans chat/orbe +--------------->+      (mistral-small)     |
|                           |  POST /guess   |   -> QuestionInterpreter  |
| 7. Propose un guess      +--------------->+      (mistral-large)     |
|                           |<---------------+   -> AnswerResolver      |
|                           |                |      (deterministe)      |
|                           |                |   -> LLMFallbackResolver  |
|                           |                |   -> SphinxVoice (mood)  |
|                           |                |   -> ElevenLabs TTS      |
+---------------------------+                +---------------------------+
```

### Mode Full LLM (experimental)

```
Joueur (Chrome)                              Serveur FastAPI
+---------------------------+                +---------------------------+
| index.html + app.js       |  POST /ask    |                           |
| Question libre            +--------------->+   -> SurrenderDetector    |
|                           |<---------------+   -> ServerGuessCheck     |
|                           |                |   -> FullLLMHandler       |
|                           |                |      (1 seul appel LLM)  |
|                           |                |      intent + answer +   |
|                           |                |      theatrical response  |
|                           |                |   -> NameLeakGuard       |
|                           |                |   -> UnicodeRepair       |
|                           |                |   -> ElevenLabs TTS      |
+---------------------------+                +---------------------------+
```

Le mode se switch a chaud via `POST /engine/mode {"mode": "full_llm"}` ou via la variable `GAME_ENGINE_MODE` dans `.env`.

### Pipeline de reponse — Mode Hybrid

```
Question du joueur
  -> SurrenderDetector (regex, termine la partie si abandon)
  -> RuleMatcher (regex bilingue, ~0ms, cout 0)
     |-- match   -> AnswerResolver (deterministe)
     |-- no match -> IntentClassifier (mistral-small, ~200ms)
                     |-- guess -> check_guess() (fuzzy match)
                     |-- question -> QuestionInterpreter (mistral-large)
                                     -> AnswerResolver (deterministe)
                                        |-- "unknown" -> LLMFallbackResolver
  -> SphinxVoice (templates mood-aware OU LLM theatral)
  -> ElevenLabs TTS (streaming + cache)
  -> Audio MP3 servi au frontend
```

### Pipeline de reponse — Mode Full LLM

```
Question du joueur
  -> SurrenderDetector (regex, termine la partie si abandon)
  -> FullLLMHandler (1 appel mistral-large, JSON mode)
     -> intent + answer + sphinx_response en une seule passe
  -> ServerGuessCheck (check_guess() systematique, filet de securite)
  -> NameLeakGuard (sanitize si le LLM a laisse echapper le nom)
  -> UnicodeRepair (corrige les artifacts d'encodage é→9, è→8, à→0)
  -> ElevenLabs TTS
```

### Points cruciaux

- **Verite deterministe** (hybrid) : `AnswerResolver` ne fait que comparer des attributs structures ou chercher des mots-cles dans les facts. Le LLM ne decide jamais de la verite.
- **Anti-leak** : le nom du personnage secret ne touche JAMAIS le contexte LLM (hybrid). En mode full_llm, `NameLeakGuard` sanitize la sortie.
- **Triple resolution** (hybrid) : RuleMatcher (regex) -> AnswerResolver (attributs) -> LLMFallbackResolver (facts). Reduit les "unknown".
- **Surrender** : detection regex cote serveur ("je donne ma langue au sphinx", "j'abandonne", "I give up") dans les deux modes.
- **Server-side guess check** : en mode full_llm, `check_guess()` tourne systematiquement sur le texte du joueur, meme si le LLM n'a pas detecte de guess.
- **Mood adaptatif** : le Sphinx change de ton (confiant → intrigue → nerveux → condescendant) selon la progression du joueur.

### State Machine

```
idle -> sphinx_speaking -> listening -> thinking -> sphinx_speaking -> ...
                                                  \-> ended (via loss, win, ou surrender)
```

Geree cote serveur dans `game/state.py`. Chaque transition est validee.

### Game Engine (regles cote serveur)

- Max 20 questions par partie
- Max 3 tentatives de guess
- Indice a la demande (3 par partie)
- Hard stop a 25 tours
- Surrender : termine la partie proprement avec revelation
- Scoring : `1000 - 40*questions - 100*wrong_guesses - 50*hints + difficulty_bonus`
- Sphinx confidence meter (visuel, 0-100)
- Streak counter (series de "oui" consecutifs)
- 15% de chance de "slip" (micro-indice subtil) sur reponse "oui"

## Arborescence du projet

```
lesphinx/
  main.py                    # FastAPI entry point, sert les fichiers statiques
  config/settings.py         # Pydantic BaseSettings, charge .env
  game/
    characters.py            # Character model, SecretSelector, FactStore, AnswerResolver
    engine.py                # GameEngine: regles, scoring, confidence, streak, hints, surrender
    judge.py                 # Fuzzy matching pour les guesses (exact, alias, Levenshtein)
    achievements.py          # 8 titres deblocables (Novice, Oeil d'Horus, Sphinx Slayer...)
    models.py                # GameSession, Turn, request/response models
    state.py                 # State machine enum + transitions valides
  llm/
    interpreter.py           # RuleMatcher (regex bilingue) + IntentClassifier (mistral-small) + QuestionInterpreter (mistral-large)
    full_llm_handler.py      # Mode Full LLM: single-call handler + surrender + name-leak guard + unicode repair
    fallback_resolver.py     # LLM deduction quand AnswerResolver retourne "unknown"
    voice.py                 # SphinxVoice: mood system + templates + LLM theatral
    schemas.py               # ParsedQuestion, AttributeCheck, SphinxUtterance
    client.py                # (legacy) MistralLLMClient
    prompts.py               # (legacy) prompts originaux
  tts/
    client.py                # ElevenLabsTTSClient: streaming + cache en memoire
  stt/
    client.py                # VoxtralSTTClient (non utilise, remplace par Web Speech API)
    normalizer.py            # Texte libre -> yes/no/unknown
  store/
    base.py                  # SessionStore + AudioBlobStore protocols
    memory.py                # InMemorySessionStore + InMemoryAudioBlobStore
    leaderboard.py           # LeaderboardStore + GlobalStats (persistance JSON)
  api/
    deps.py                  # Singletons: session_store, audio_store, game_engine
    routes.py                # Tous les endpoints REST + easter eggs + slip mechanic + mode switch
    rate_limit.py            # Rate limiting in-memory par IP
  static/
    index.html               # SPA: welcome, difficulty, game (chat+voice), end + OG meta tags
    app.js                   # Web Speech API, dual interface, audio viz, i18n, SFX
    style.css                # Theme egyptien (Cinzel, gold/dark, glassmorphism)
    hero-bg.jpg              # Image de fond hero section
    lesphinx-logo_white.png  # Logo white pour header/nav
    lesphinx.gif             # GIF anime du Sphinx pour ecran d'accueil
    favicon.png              # Favicon
    og-image.jpg             # Open Graph image pour partage reseaux sociaux (1200x630)
    sfx/                     # Effets sonores (tick, ding, whoosh, fanfare, gong, ambient)
    characters/              # Photos des personnages (143 JPG/PNG)
  voice_agent/               # (experimental) PersonaPlex/WebSocket voice agent
  logging.py                 # JSONL event logging
  data/
    characters.json          # 160 personnages avec attributs, facts, themes, summaries, images
    leaderboard.json         # Top 10 scores (persiste)
    stats.json               # Stats globales (persiste)

scripts/
  build_characters.py        # Genere characters.json via liste curee + Mistral enrichment
  enrich_attributes.py       # Ajoute birth_year, era, nobel, oscar, language aux personnages
  enrich_v2.py               # Ajoute hair_color, ethnicity, height_category, notable_works
  build_summaries.py         # Genere les summaries bilingues des personnages
  build_themes.py            # Assigne les themes aux personnages
  fetch_character_images.py  # Telecharge les photos des personnages
  generate_sfx.py            # Genere les effets sonores WAV

tests/
  test_characters.py         # FactStore, SecretSelector, AnswerResolver
  test_engine.py             # Regles du jeu, transitions, hints
  test_interpreter.py        # RuleMatcher patterns, edge cases bilingues
  test_judge.py              # Fuzzy matching noms, aliases, accents
  test_full_llm_handler.py   # Unicode repair, name leak, surrender detection
  test_voice.py              # SphinxVoice templates + mood
  test_leaderboard.py        # Leaderboard + stats persistence
  test_achievements.py       # Achievement conditions

deploy/
  Caddyfile                  # Reverse proxy thesphinx.ai -> localhost:8000
  lesphinx.service           # Systemd unit file
  deploy.sh                  # Script de deploiement VM
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/game/new` | Creer session. Body: `{language, difficulty, mode, themes}` |
| POST | `/game/{id}/ask` | Poser une question libre. Pipeline selon le mode (hybrid/full_llm) |
| POST | `/game/{id}/guess` | Proposer un nom. Fuzzy matching contre le secret |
| POST | `/game/{id}/hint` | Demander un indice (max 3 par partie) |
| GET | `/game/{id}/state` | Etat complet (sans le secret tant que state != ENDED) |
| GET | `/audio/{id}` | Servir blob audio TTS (MP3) |
| GET | `/leaderboard` | Top 10 + stats globales |
| POST | `/leaderboard` | Soumettre un score. Body: `{session_id, player_name}` |
| GET | `/engine/mode` | Mode moteur actuel (`hybrid` ou `full_llm`) |
| POST | `/engine/mode` | Changer de mode a chaud. Body: `{"mode": "hybrid"\|"full_llm"}` |

## Modes de jeu

### Hybrid (defaut)

Architecture multi-couche : regex -> intent classifier -> LLM interpreter -> resolver deterministe -> LLM fallback -> voice templates/LLM. Plus robuste, verite deterministe, latence variable.

### Full LLM (experimental)

Un seul appel Mistral Large par tour. Le LLM recoit le profil complet du personnage dans le system prompt et gere tout : intent, answer, theatralite. Plus naturel et conversationnel, mais necessite des garde-fous :
- `SurrenderDetector` : regex cote serveur avant l'appel LLM
- `ServerGuessCheck` : `check_guess()` toujours execute sur le texte brut
- `NameLeakGuard` : supprime le nom du personnage de la reponse LLM
- `UnicodeRepair` : corrige les artefacts d'encodage (accents → chiffres)

## Personnages (160 personnages cures)

Chaque personnage dans `characters.json` possede :

```json
{
  "id": "albert_einstein",
  "name": "Albert Einstein",
  "aliases": ["Einstein"],
  "difficulty": "easy",
  "themes": ["science"],
  "attributes": {
    "gender": "male",
    "alive": false,
    "nationality": "german",
    "field": "science",
    "subfield": "physics",
    "continent": "europe",
    "born_before_1900": true,
    "born_before_1950": true,
    "birth_year": 1879,
    "death_year": 1955,
    "era": "modern",
    "has_nobel_prize": true,
    "has_oscar": false,
    "primary_language": "german",
    "fictional": false,
    "hair_color": "white",
    "ethnicity": "caucasian",
    "height_category": "average",
    "notable_works": ["Theory of Relativity", "Photoelectric Effect"]
  },
  "facts": ["Won the Nobel Prize in Physics in 1921", "..."],
  "image": {"local_path": "/characters/albert_einstein.jpg"},
  "summary": {
    "fr": "Albert Einstein, ne en 1879 a Ulm...",
    "en": "Albert Einstein, born in 1879 in Ulm..."
  }
}
```

Repartition : 50 easy / 60 medium / 50 hard.
Themes : activism, arts, business, cinema, exploration, history, literature, music, philosophy, politics, religion, science, sports, technology.

## Systeme de Sphinx

### Mood system (`get_mood(session)`)

| Mood | Condition | Ton |
|------|-----------|-----|
| `confident` | Tours 0-5 | Moqueur, dedaigneux |
| `intrigued` | Tours 6-12, bonnes questions | Curieux, legerement inquiet |
| `nervous` | Tours 13+, beaucoup de "oui" | Anxieux, impressionne |
| `condescending` | Plusieurs mauvais guesses | Suffisant |

Le mood est injecte dans les templates et le prompt LLM Voice.

### Easter eggs

Questions speciales detectees par regex :
- "Es-tu le Sphinx ?" -> reponse humoristique
- "Tu connais la reponse ?" -> "Evidemment, mortel."
- "Donne-moi un indice" -> redirige vers le systeme d'indices
- "Tu triches ?" / "Je t'aime" -> reponses speciales

### Surrender

Detection regex bilingue avant tout traitement LLM :
- "je donne ma langue au sphinx", "j'abandonne"
- "I give up", "I surrender"
- "dis-moi la reponse", "tell me the answer"
Resultat : fin de partie propre avec revelation du personnage.

### Idle taunt

Apres 15 secondes de silence en mode `listening`, le Sphinx lance : "Tu donnes ta langue au Sphinx ?" (une fois par partie max).

### Sphinx "slip"

15% de chance sur une reponse "oui" d'ajouter un micro-indice subtil tire des attributs du personnage (continent, ere, domaine). Ne revele jamais le nom.

## Frontend

### Modes d'interface

1. **Mode Chat** (micro off) : bulles de conversation, input texte, bouton envoyer
2. **Mode Vocal** (micro manual/handsfree/continu) : orbe audio animee (Web Audio AnalyserNode), timer sablier SVG, gros bouton envoyer central

### Ecrans

1. **Welcome** : hero bg, logo, GIF anime, stats globales, leaderboard preview, choix mode solo/duel
2. **Difficulty** : 3 cartes animees (Neophyte/Initie/Maitre), grille de themes, selecteur micro
3. **Game** : header (counters, confidence meter, streak, son), chat OU voice container, controles (hint, guess, give up)
4. **End** : photo personnage, nom, summary educatif, score + achievements (meme ligne), soumission leaderboard, rejouer

### Modes micro

| Mode | Comportement |
|------|-------------|
| `off` | Pas de micro, saisie texte uniquement |
| `manual` | Cliquer pour parler, re-cliquer pour envoyer |
| `handsfree` | Ecoute auto apres chaque reponse du Sphinx |
| `continuous` | Micro toujours ouvert, auto-restart |

### Animations

- Staggered entrance (`reveal-up`, `reveal-scale`, `reveal-left`) sur tous les ecrans
- Cards pop (`cardPop`) pour les themes
- Chat messages directionnels (`fadeSlideLeft`/`fadeSlideRight`)
- Pulse glow sur boutons CTA
- Confidence fill transition
- Streak pulse
- Achievement badge pop
- Score counter

### SFX & Musique

- Ambient loop (volume adaptatif selon progression)
- Tick (timer), ding (hint/achievement), whoosh (question envoyee)
- Fanfare (victoire), gong (defaite)
- Toggle son dans le header

### SEO & Partage social

- Meta description pour SEO
- Open Graph tags (Facebook, LinkedIn, WhatsApp, Discord, Slack)
- Twitter/X summary_large_image card
- Image OG 1200x630px
- Apple touch icon

## Scoring & Gamification

### Score

```
score = max(0, 1000 - 40*questions - 100*wrong_guesses - 50*hints + difficulty_bonus)
```

Bonus : easy=0, medium=+200, hard=+500.

### Achievements (8 titres)

| ID | Icone | Titre FR | Condition |
|----|-------|----------|-----------|
| novice | 𓂀 | Novice du Desert | Premiere victoire |
| eye_of_horus | 𓁹 | Oeil d'Horus | Win < 10 questions |
| sphinx_slayer | ⚔ | Tueur de Sphinx | Win < 5 questions |
| nightmare | 𓆣 | Cauchemar du Sphinx | Win en Maitre |
| omniscient | 𓋹 | Omniscient | Win sans indice ni erreur |
| persistent | 𓃀 | Persistant | Win apres 2+ mauvais guesses |
| scholar | 𓏛 | Erudit | Win avec 15+ questions |
| speed_demon | ⚡ | Eclair du Desert | Score > 900 |

### Leaderboard

Top 10, persistance JSON. Soumission de nom si score qualifie.

### Stats globales

Total parties, total victoires, taux de victoire, questions moyennes pour gagner.

## Configuration

Copier `.env.example` vers `.env` et remplir :

```bash
MISTRAL_API_KEY=xxx              # Required - cle API Mistral
MISTRAL_MODEL=mistral-large-latest
INTENT_CLASSIFIER_MODEL=mistral-small-latest
ELEVENLABS_API_KEY=xxx           # Required - cle API ElevenLabs
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
ELEVENLABS_MODEL=eleven_flash_v2_5
GAME_ENGINE_MODE=hybrid          # "hybrid" (default) ou "full_llm"
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

## Deploiement (thesphinx.ai)

```bash
# Sur la VM Google Cloud :
bash deploy/deploy.sh
# Caddy gere le HTTPS automatique via Let's Encrypt
# Cloudflare DNS : A record vers l'IP de la VM
```

## Branches

| Branche | Etat | Description |
|---------|------|-------------|
| `main` | Deploye | Version principale avec hybrid + full_llm modes |
| `multiplayer` | Pret (non merge) | Mode duel 2 joueurs tour a tour |
| `personaplex` | Experimental | Integration PersonaPlex (fal.ai) voice agent |
| `frontend-react` | Prototype | Migration React + Vite du frontend |
