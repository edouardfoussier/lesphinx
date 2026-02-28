// === LeSphinx Frontend ===

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// --- State ---
let sessionId = null;
let language = 'fr';
let silentMode = false;
let isListening = false;
let currentAudio = null;

// --- Web Speech API ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
}

// --- i18n ---
const i18n = {
    fr: {
        subtitle: 'Pense a un personnage celebre... Je vais le deviner.',
        newGame: 'Nouvelle Partie',
        silentMode: 'Mode silencieux (pas de micro)',
        yes: 'Oui',
        no: 'Non',
        unknown: 'Je ne sais pas',
        guessPrompt: 'Est-ce correct ?',
        guessYes: "Oui, c'est ca !",
        guessNo: 'Non, continue',
        turnLabel: 'Tour',
        questionsLabel: 'Questions',
        endWin: 'Le Sphinx a demasque ton personnage !',
        endLose: 'Le Sphinx est vaincu... cette fois.',
        endGiveUp: 'La partie est terminee.',
        restart: 'Rejouer',
        sttFailed: 'Reconnaissance vocale echouee. Utilise les boutons.',
        listening: 'Parle maintenant...',
    },
    en: {
        subtitle: 'Think of a famous person... I will guess who it is.',
        newGame: 'New Game',
        silentMode: 'Silent mode (no microphone)',
        yes: 'Yes',
        no: 'No',
        unknown: "I don't know",
        guessPrompt: 'Is that correct?',
        guessYes: 'Yes, correct!',
        guessNo: 'No, keep going',
        turnLabel: 'Turn',
        questionsLabel: 'Questions',
        endWin: 'The Sphinx has unmasked your character!',
        endLose: 'The Sphinx is defeated... this time.',
        endGiveUp: 'Game over.',
        restart: 'Play Again',
        sttFailed: 'Speech recognition failed. Use the buttons.',
        listening: 'Speak now...',
    },
};

function t(key) {
    return i18n[language]?.[key] || i18n.en[key] || key;
}

// --- Screens ---
function showScreen(name) {
    $$('.screen').forEach((s) => s.classList.remove('active'));
    $(`#screen-${name}`).classList.add('active');
}

// --- Language ---
$$('.lang-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
        $$('.lang-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        language = btn.dataset.lang;
        updateI18n();
    });
});

function updateI18n() {
    $('#welcome-subtitle').textContent = t('subtitle');
    $('#btn-start').textContent = t('newGame');
    $('#silent-label').textContent = t('silentMode');
    $('#btn-yes').textContent = t('yes');
    $('#btn-no').textContent = t('no');
    $('#btn-unknown').textContent = t('unknown');
    $('#guess-prompt').textContent = t('guessPrompt');
    $('#btn-guess-yes').textContent = t('guessYes');
    $('#btn-guess-no').textContent = t('guessNo');
    $('#btn-restart').textContent = t('restart');
}

// --- Silent Mode ---
$('#toggle-silent').addEventListener('change', (e) => {
    silentMode = e.target.checked;
});

// --- Start Game ---
$('#btn-start').addEventListener('click', startGame);
$('#btn-restart').addEventListener('click', () => {
    showScreen('welcome');
});

async function startGame() {
    $('#btn-start').disabled = true;
    try {
        const res = await fetch('/game/new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language }),
        });
        const data = await res.json();
        sessionId = data.session_id;
        showScreen('game');
        renderGameState(data);
    } catch (err) {
        console.error('Failed to start game:', err);
    } finally {
        $('#btn-start').disabled = false;
    }
}

// --- Render Game State ---
function renderGameState(data) {
    // Header
    $('#turn-counter').textContent = `${t('turnLabel')} ${data.current_turn}`;
    $('#question-counter').textContent = `${t('questionsLabel')}: ${data.question_count}/15`;

    // Get latest turn
    const lastTurn = data.turns[data.turns.length - 1];
    if (lastTurn) {
        $('#sphinx-text').textContent = lastTurn.sphinx_utterance;

        // Play audio if available
        if (lastTurn.audio_id) {
            playSphinxAudio(lastTurn.audio_id);
        }

        // Show guess controls if it's a guess
        if (lastTurn.sphinx_action_type === 'guess') {
            showGuessControls();
            return;
        }
    }

    // Handle state
    if (data.state === 'ended') {
        showEndScreen(data);
        return;
    }

    if (data.state === 'listening') {
        showControls();
        hideThinking();
    } else if (data.state === 'thinking') {
        hideControls();
        showThinking();
    } else if (data.state === 'sphinx_speaking') {
        hideControls();
        hideThinking();
    }
}

function showControls() {
    $('#controls').classList.remove('hidden');
    $('#guess-controls').classList.add('hidden');
    if (silentMode || !recognition) {
        $('#btn-record').classList.add('hidden');
    } else {
        $('#btn-record').classList.remove('hidden');
    }
}

function hideControls() {
    $('#controls').classList.add('hidden');
    $('#guess-controls').classList.add('hidden');
}

function showGuessControls() {
    $('#controls').classList.add('hidden');
    $('#guess-controls').classList.remove('hidden');
}

function showThinking() {
    $('#thinking-indicator').classList.remove('hidden');
}

function hideThinking() {
    $('#thinking-indicator').classList.add('hidden');
}

// --- Audio Playback ---
function playSphinxAudio(audioId) {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }

    const avatar = $('#avatar-game');
    avatar.classList.add('talking');

    currentAudio = new Audio(`/audio/${audioId}`);
    currentAudio.play().catch(() => {
        avatar.classList.remove('talking');
    });

    currentAudio.addEventListener('ended', () => {
        avatar.classList.remove('talking');
        currentAudio = null;
    });

    currentAudio.addEventListener('error', () => {
        avatar.classList.remove('talking');
        currentAudio = null;
    });
}

// --- Text Answer Buttons ---
$$('.btn-answer[data-answer]').forEach((btn) => {
    btn.addEventListener('click', () => sendTextAnswer(btn.dataset.answer));
});

async function sendTextAnswer(answer) {
    hideControls();
    showThinking();

    try {
        const res = await fetch(`/game/${sessionId}/answer_text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answer }),
        });
        const data = await res.json();
        hideThinking();
        renderGameState(data);
    } catch (err) {
        console.error('Failed to send answer:', err);
        hideThinking();
        showControls();
    }
}

// --- Guess Confirmation ---
$('#btn-guess-yes').addEventListener('click', () => {
    sendTextAnswer('yes');
});

$('#btn-guess-no').addEventListener('click', () => {
    sendTextAnswer('no');
});

// --- Voice Recognition (Web Speech API) ---
const recordBtn = $('#btn-record');

recordBtn.addEventListener('click', toggleVoiceRecognition);

function toggleVoiceRecognition() {
    if (!recognition || silentMode) return;

    if (isListening) {
        recognition.stop();
        return;
    }

    // Configure language
    recognition.lang = language === 'fr' ? 'fr-FR' : 'en-US';

    recognition.onstart = () => {
        isListening = true;
        recordBtn.classList.add('recording');
        $('#sphinx-text').textContent = t('listening');
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log('Voice recognized:', transcript);

        // Normalize client-side then send as text
        const normalized = normalizeVoice(transcript);
        sendTextAnswer(normalized);
    };

    recognition.onerror = (event) => {
        console.warn('Speech recognition error:', event.error);
        isListening = false;
        recordBtn.classList.remove('recording');
        // Don't hide controls - let user use buttons
    };

    recognition.onend = () => {
        isListening = false;
        recordBtn.classList.remove('recording');
    };

    recognition.start();
}

// --- Client-side voice normalization ---
const YES_WORDS = {
    fr: ['oui', 'ouais', 'yes', 'yep', 'yeah', 'bien sur', 'tout a fait', 'absolument', 'exact', 'exactement', 'correct', 'si'],
    en: ['yes', 'yeah', 'yep', 'yup', 'sure', 'of course', 'absolutely', 'correct', 'right', 'exactly', 'indeed'],
};
const NO_WORDS = {
    fr: ['non', 'no', 'nope', 'pas du tout', 'absolument pas', 'nan', 'nah', 'jamais'],
    en: ['no', 'nope', 'nah', 'not at all', 'absolutely not', 'never', 'wrong', 'incorrect'],
};
const UNKNOWN_WORDS = {
    fr: ['je ne sais pas', 'je sais pas', 'aucune idee', 'sais pas', 'peut etre', 'pas sur', 'bof'],
    en: ["i don't know", "don't know", 'no idea', 'not sure', 'maybe', 'unknown', 'unsure'],
};

function normalizeVoice(text) {
    const cleaned = text.toLowerCase().trim().replace(/[.!?,;]+$/, '');
    const langs = [language, language === 'fr' ? 'en' : 'fr'];

    // Build candidates sorted longest-first
    const candidates = [];
    for (const lang of langs) {
        for (const kw of (NO_WORDS[lang] || [])) candidates.push([kw, 'no']);
        for (const kw of (YES_WORDS[lang] || [])) candidates.push([kw, 'yes']);
        for (const kw of (UNKNOWN_WORDS[lang] || [])) candidates.push([kw, 'unknown']);
    }
    candidates.sort((a, b) => b[0].length - a[0].length);

    for (const [kw, cat] of candidates) {
        if (cleaned.includes(kw)) return cat;
    }
    return 'unknown';
}

// --- End Screen ---
function showEndScreen(data) {
    let msg = t('endGiveUp');
    if (data.result === 'win') msg = t('endWin');
    else if (data.result === 'lose') msg = t('endLose');

    $('#end-title').textContent = data.result === 'win'
        ? (language === 'fr' ? 'Le Sphinx triomphe !' : 'The Sphinx triumphs!')
        : (language === 'fr' ? 'Le Sphinx est vaincu' : 'The Sphinx is defeated');
    $('#end-message').textContent = msg;

    showScreen('end');
}

// --- Init ---
updateI18n();
