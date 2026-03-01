# LeSphinx - AGENTS.md

## Vue d'ensemble

**LeSphinx** est un jeu vocal de devinettes developpe lors du Hackathon Mistral. Le Sphinx (creature mythique) pense a un personnage celebre, et le joueur pose des questions en langage naturel pour deviner qui c'est. Le Sphinx ne repond que par oui, non, ou je ne sais pas, avec une voix theatrale et mysterieuse. Le jeu est bilingue (FR/EN), dispose d'un systeme de scoring, d'un leaderboard, et d'achievements.

## Stack technique

| Composant | Technologie | Role |
|-----------|-------------|------|
| Backend | FastAPI + Pydantic | API REST, game engine, orchestration |
| LLM | Mistral Large (`mistral-large-latest`) | Interpreter de questions + Voix du Sphinx + Fallback resolver |
| TTS | ElevenLabs (`eleven_flash_v2_5`, streaming) | Voix grave/mysterieuse du Sphinx |
| STT | Web Speech API (navigateur) | Reconnaissance vocale cote client |
| Frontend | HTML + Vanilla JS + CSS | Zero build step, servi par FastAPI |
| Sessions | In-memory dict | Pas de base de donnees, single process |
| Persistence | JSON files | Leaderboard + stats (survit aux restarts) |

## Architecture

```
Joueur (Chrome)                              Serveur FastAPI
+---------------------------+                +---------------------------+
| index.html + app.js       |                | main.py                   |
|                           |  POST /game/new|                           |
| 1. Choix langue/diff/theme+--------------->+ api/routes.py             |
| 2. Web Speech API (STT)   |               |   -> SecretSelector       |
| 3. Question libre (voix   |  POST /ask    |   -> GameEngine           |
|    ou texte)              +--------------->+   -> RuleMatcher (regex)  |
| 4. Recoit JSON + audio    |<---------------+   -> QuestionInterpreter  |
| 5. Joue audio TTS         |  GET /audio/id|      (LLM fallback)      |
| 6. Affiche dans chat/orbe +--------------->+   -> AnswerResolver      |
|                           |  POST /guess   |      (deterministe)      |
| 7. Propose un guess      +--------------->+   -> LLMFallbackResolver  |
|                           |<---------------+   -> SphinxVoice (mood)  |
|                           |                |   -> ElevenLabs TTS      |
+---------------------------+                +---------------------------+
```

### Pipeline de reponse (data flow)

```
Question du joueur
  -> RuleMatcher (regex bilingue, ~0ms, cout 0)
     |-- match   -> AnswerResolver (deterministe)
     |-- no match -> QuestionInterpreter (LLM, json_object mode)
                     -> AnswerResolver (deterministe)
                        |-- "unknown" -> LLMFallbackResolver (deduit depuis les facts)
  -> SphinxVoice (templates mood-aware OU LLM theatral)
  -> ElevenLabs TTS (streaming + cache)
  -> Audio MP3 servi au frontend
```

### Points cruciaux

- **Verite deterministe** : `AnswerResolver` ne fait que comparer des attributs structures ou chercher des mots-cles dans les facts. Le LLM ne decide jamais de la verite.
- **Anti-leak** : le nom du personnage secret ne touche JAMAIS le contexte LLM. L'Interpreter ne voit que la question brute. Le SphinxVoice ne recoit que yes/no/unknown + un fait filtre.
- **Triple resolution** : RuleMatcher (regex) -> AnswerResolver (attributs) -> LLMFallbackResolver (facts). Reduit dramatiquement les reponses "unknown".
- **Mood adaptatif** : le Sphinx change de ton (confiant -> intrigue -> nerveux -> condescendant) selon la progression du joueur.

### State Machine

```
idle -> sphinx_speaking -> listening -> thinking -> sphinx_speaking -> ...
                                                  \-> ended
```

Geree cote serveur dans `game/state.py`. Chaque transition est validee.

### Game Engine (regles cote serveur)

- Max 20 questions par partie
- Max 3 tentatives de guess
- Indice a la demande (3 par partie)
- Hard stop a 25 tours
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
    engine.py                # GameEngine: regles, scoring, confidence, streak, hints
    judge.py                 # Fuzzy matching pour les guesses (exact, alias, Levenshtein)
    achievements.py          # 8 titres deblocables (Novice, Oeil d'Horus, Sphinx Slayer...)
    models.py                # GameSession, Turn, request/response models
    state.py                 # State machine enum + transitions valides
  llm/
    interpreter.py           # RuleMatcher (regex bilingue) + QuestionInterpreter (LLM fallback)
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
    routes.py                # Tous les endpoints REST + easter eggs + slip mechanic
    rate_limit.py            # Rate limiting in-memory par IP
  static/
    index.html               # SPA: welcome, difficulty, game (chat+voice), end
    app.js                   # Web Speech API, dual interface, audio viz, i18n, SFX
    style.css                # Theme egyptien (Cinzel, gold/dark, glassmorphism)
    hero-bg.jpg              # Image de fond hero section
    lesphinx-logo_white.png  # Logo white pour header/nav
    lesphinx.gif             # GIF anime du Sphinx pour ecran d'accueil
    favicon.png              # Favicon
    sfx/                     # Effets sonores (tick, ding, whoosh, fanfare, gong, ambient)
    characters/              # Photos des personnages (JPG/PNG)
  voice_agent/               # (experimental) PersonaPlex/WebSocket voice agent
  logging.py                 # JSONL event logging
  data/
    characters.json          # 160 personnages avec attributs, facts, themes, summaries
    leaderboard.json         # Top 10 scores (persiste)
    stats.json               # Stats globales (persiste)

scripts/
  build_characters.py        # Genere characters.json via liste curee + Mistral enrichment
  enrich_attributes.py       # Ajoute birth_year, era, nobel, oscar, language aux personnages
  build_summaries.py         # Genere les summaries bilingues des personnages
  build_themes.py            # Assigne les themes aux personnages
  fetch_character_images.py  # Telecharge les photos des personnages
  generate_sfx.py            # Genere les effets sonores WAV

tests/
  test_characters.py         # FactStore, SecretSelector, AnswerResolver
  test_engine.py             # Regles du jeu, transitions, hints
  test_interpreter.py        # RuleMatcher patterns, edge cases bilingues
  test_judge.py              # Fuzzy matching noms, aliases, accents

deploy/
  Caddyfile                  # Reverse proxy thesphinx.ai -> localhost:8000
  lesphinx.service           # Systemd unit file
  deploy.sh                  # Script de deploiement VM
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/game/new` | Creer session. Body: `{language, difficulty, mode, themes}` |
| POST | `/game/{id}/ask` | Poser une question libre. Pipeline: RuleMatcher -> Resolver -> Voice -> TTS |
| POST | `/game/{id}/guess` | Proposer un nom. Fuzzy matching contre le secret |
| POST | `/game/{id}/hint` | Demander un indice (max 3 par partie) |
| GET | `/game/{id}/state` | Etat complet (sans le secret tant que state != ENDED) |
| GET | `/audio/{id}` | Servir blob audio TTS (MP3) |
| GET | `/leaderboard` | Top 10 + stats globales |
| POST | `/leaderboard` | Soumettre un score. Body: `{session_id, player_name}` |

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
    "fictional": false
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
4. **End** : photo personnage, nom, summary educatif, score, achievements, soumission leaderboard, rejouer

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
ELEVENLABS_API_KEY=xxx           # Required - cle API ElevenLabs
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
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

## Deploiement (thesphinx.ai)

```bash
# Sur la VM Google Cloud :
bash deploy/deploy.sh
# Caddy gere le HTTPS automatique via Let's Encrypt
# Cloudflare DNS : A record vers l'IP de la VM
```
