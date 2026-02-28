# LeSphinx -- Frontend Prompt

## Le jeu

**LeSphinx** est un jeu vocal de devinettes. Un Sphinx mythique pense à un personnage célèbre. Le joueur pose des questions libres en texte ou à la voix, et le Sphinx répond par oui, non, ou je ne sais pas, avec une voix grave et théâtrale (synthèse vocale). Le joueur doit deviner le personnage en un minimum de questions.

Le jeu est bilingue français/anglais. Il y a 3 niveaux de difficulté (facile, moyen, difficile) qui déterminent si le personnage est très connu ou plus obscur.

Le backend existe déjà (FastAPI). Je veux un frontend moderne, créatif, et immersif. Libre à toi pour le design, les animations, le style visuel -- surprends-moi. L'univers est celui d'un Sphinx mystique et énigmatique.

## API Endpoints

Tous les endpoints sont sur la même origine (pas de CORS à gérer).

### POST /game/new

Crée une nouvelle partie.

Request :
```json
{"language": "fr", "difficulty": "medium"}
```
- `language` : `"fr"` ou `"en"`
- `difficulty` : `"easy"`, `"medium"`, ou `"hard"`

Response (GameStateResponse) :
```json
{
  "session_id": "abc123",
  "state": "listening",
  "language": "fr",
  "difficulty": "easy",
  "turns": [
    {
      "turn_number": 0,
      "player_text": "",
      "intent": "question",
      "raw_answer": null,
      "sphinx_utterance": "Je suis le Sphinx. Je pense à un personnage célèbre...",
      "audio_id": "f8a3b2c1d4e5"
    }
  ],
  "question_count": 0,
  "guess_count": 0,
  "max_questions": 20,
  "max_guesses": 3,
  "result": null,
  "current_turn": 1,
  "revealed_character": null
}
```

### POST /game/{session_id}/ask

Poser une question au Sphinx.

Request :
```json
{"text": "Est-ce un homme ?"}
```

Response : même shape `GameStateResponse`. Un nouveau `turn` est ajouté à `turns`. Le dernier turn contient :
- `raw_answer` : `"yes"`, `"no"`, ou `"unknown"`
- `sphinx_utterance` : la réponse théâtrale du Sphinx (texte)
- `audio_id` : ID pour récupérer l'audio TTS (peut être `null` si le TTS échoue)

### POST /game/{session_id}/guess

Soumettre une tentative de devinette.

Request :
```json
{"name": "Albert Einstein"}
```

Response : même shape. Si correct : `result` = `"win"`, `state` = `"ended"`. Si faux mais il reste des essais : la partie continue. Si max essais atteint : `result` = `"lose"`, `state` = `"ended"`.

### GET /game/{session_id}/state

Récupérer l'état courant (même shape).

### GET /audio/{audio_id}

Retourne des bytes audio MP3 (la voix du Sphinx). À jouer avec `new Audio('/audio/' + audioId)`.

## Flow de jeu

1. **Écran d'accueil** : le joueur choisit la langue, la difficulté, et le mode micro, puis lance la partie
2. **POST /game/new** → réponse avec le premier turn (intro du Sphinx) → afficher l'écran de jeu
3. **Boucle de jeu** : le joueur pose une question (texte ou voix) → **POST /ask** → afficher la réponse du Sphinx + jouer l'audio → répéter
4. Le joueur peut à tout moment tenter de deviner → **POST /guess** → afficher le résultat
5. Quand `state === "ended"` : afficher l'écran de fin avec le résultat (`win`/`lose`) et `revealed_character` (le nom du personnage secret)

## Reconnaissance vocale (Web Speech API)

Utiliser `window.SpeechRecognition || window.webkitSpeechRecognition` côté navigateur.

4 modes au choix du joueur :

| Mode | Comportement |
|------|-------------|
| **Off** | Pas de micro, texte uniquement |
| **Manuel** | Bouton micro : clic pour commencer, reclic ou fin auto pour arrêter. `continuous = false` |
| **Mains libres** | Après que l'audio du Sphinx finit (`audio.onended`), attendre 400ms puis démarrer la reconnaissance automatiquement. Résultat → auto-submit. Si erreur `no-speech` ou `onend` sans résultat : retry après 1s. `continuous = false` |
| **Continu** | `continuous = true`, micro toujours ouvert. On pause pendant que le Sphinx parle (pour éviter l'auto-capture de sa voix). `onend` → auto-restart après 300ms (Chrome coupe aléatoirement). Chaque résultat `isFinal` avec texte >= 2 caractères → auto-submit |

**Règle critique** : ne JAMAIS lancer la reconnaissance pendant que l'audio du Sphinx joue (sinon le micro capture la voix du Sphinx et l'envoie comme question).

## i18n

Tous les textes de l'interface doivent changer selon la langue choisie (français ou anglais). Voici les clés principales :

| Clé | Français | English |
|-----|----------|---------|
| subtitle | Je pense à un personnage célèbre... Sauras-tu le deviner ? | I'm thinking of a famous person... Can you guess who? |
| newGame | Nouvelle Partie | New Game |
| easy | Facile | Easy |
| medium | Moyen | Medium |
| hard | Difficile | Hard |
| askPlaceholder | Pose ta question... | Ask your question... |
| guessBtn | Je devine ! | I want to guess! |
| guessTitle | Qui est-ce ? | Who is it? |
| guessConfirm | Deviner | Guess |
| guessCancel | Annuler | Cancel |
| questionsLabel | Questions | Questions |
| guessesLabel | Essais | Guesses |
| endWin | Bravo ! Tu as démasqué le Sphinx ! | Bravo! You unmasked the Sphinx! |
| endLose | Le Sphinx triomphe... cette fois. | The Sphinx triumphs... this time. |
| restart | Rejouer | Play Again |
| listening | Parle maintenant... | Speak now... |
| revealed | Le personnage était : | The character was: |
| networkError | Erreur réseau, réessaye. | Network error, please retry. |

## Gestion d'erreurs

- Toujours vérifier `res.ok` avant de parser le JSON
- Sur erreur HTTP : afficher le `detail` du JSON d'erreur (ou le status code)
- Sur erreur réseau : afficher un message d'erreur non-bloquant (toast / notification)
- Ne jamais crasher silencieusement

## Résumé

3 écrans (accueil, jeu, fin), 5 endpoints REST, 4 modes micro, bilingue FR/EN. Le backend gère toute la logique de jeu -- le frontend est un client léger qui affiche les réponses et joue l'audio. L'univers est celui d'un Sphinx mythique et énigmatique : sois créatif sur le visuel et les animations.
