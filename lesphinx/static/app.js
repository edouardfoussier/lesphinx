// === LeSphinx Frontend (Reversed Mode — Chat UI) ===

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---------------------------------------------------------------------------
//  State
// ---------------------------------------------------------------------------
let sessionId = null;
let language = 'fr';
let difficulty = 'medium';
let selectedTheme = 'all';
let micMode = 'manual';
let isListening = false;
let isPlaying = false;
let isProcessing = false;
let currentAudio = null;
let gameActive = false;
let isGuessMode = false;
let questionCount = 0;
let guessCount = 0;
let maxQuestions = 20;
let maxGuesses = 3;

const AUTO_LISTEN_DELAY_MS = 400;
const MIN_TRANSCRIPT_LEN = 2;

// ---------------------------------------------------------------------------
//  Web Speech API
// ---------------------------------------------------------------------------
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
}

// ---------------------------------------------------------------------------
//  i18n
// ---------------------------------------------------------------------------
const i18n = {
    fr: {
        title: 'Le Sphinx',
        subtitle: "Ose affronter l'enigme du Sphinx",
        tagline: 'Un personnage celebre se cache dans mon esprit. Sauras-tu le deviner ?',
        play: 'Defier le Sphinx',
        chooseDifficulty: 'Choisis ton destin',
        easy: 'Neophyte',
        easyDesc: 'Personnages tres celebres',
        medium: 'Initie',
        mediumDesc: 'Personnages connus',
        hard: 'Maitre',
        hardDesc: 'Personnages obscurs',
        back: 'Retour',
        start: 'Commencer',
        themes: 'THEMES',
        themeAll: 'Tous',
        themeScience: 'Science',
        themeLiterature: 'Littérature',
        themeMusic: 'Musique',
        themeCinema: 'Cinéma',
        themeSports: 'Sport',
        themePolitics: 'Politique',
        themeArts: 'Arts',
        themeHistory: 'Histoire',
        micLabel: 'MICROPHONE',
        askPlaceholder: 'Pose ta question au Sphinx...',
        guessToggle: 'Deviner',
        giveUp: 'Abandonner',
        guessTitle: 'Qui est-ce ?',
        guessPlaceholder: 'Nom du personnage...',
        guessConfirm: 'Deviner',
        guessCancel: 'Annuler',
        sphinxLabel: 'Le Sphinx',
        playerLabel: 'Toi',
        thinking: 'Le Sphinx medite...',
        listening: 'Parle maintenant...',
        endWin: 'Bravo ! Tu as demaske le Sphinx !',
        endLose: 'Le Sphinx triomphe... cette fois.',
        winTitle: 'Tu as gagne !',
        loseTitle: 'Le Sphinx triomphe',
        revealed: 'Le personnage etait :',
        restart: 'Rejouer',
        networkError: 'Erreur reseau, reessaye.',
        questionsAsked: 'questions posees',
        langToggle: 'EN',
    },
    en: {
        title: 'The Sphinx',
        subtitle: 'Dare to face the riddle of the Sphinx',
        tagline: 'A famous character hides within my mind. Can you guess who it is?',
        play: 'Challenge the Sphinx',
        chooseDifficulty: 'Choose your fate',
        easy: 'Neophyte',
        easyDesc: 'Very famous characters',
        medium: 'Initiate',
        mediumDesc: 'Well-known characters',
        hard: 'Master',
        hardDesc: 'Obscure characters',
        back: 'Back',
        start: 'Begin',
        themes: 'THEMES',
        themeAll: 'All',
        themeScience: 'Science',
        themeLiterature: 'Literature',
        themeMusic: 'Music',
        themeCinema: 'Cinema',
        themeSports: 'Sports',
        themePolitics: 'Politics',
        themeArts: 'Arts',
        themeHistory: 'History',
        micLabel: 'MICROPHONE',
        askPlaceholder: 'Ask the Sphinx a question...',
        guessToggle: 'Guess',
        giveUp: 'Give up',
        guessTitle: 'Who is it?',
        guessPlaceholder: 'Character name...',
        guessConfirm: 'Guess',
        guessCancel: 'Cancel',
        sphinxLabel: 'The Sphinx',
        playerLabel: 'You',
        thinking: 'The Sphinx ponders...',
        listening: 'Speak now...',
        endWin: 'Bravo! You unmasked the Sphinx!',
        endLose: 'The Sphinx triumphs... this time.',
        winTitle: 'You win!',
        loseTitle: 'The Sphinx triumphs',
        revealed: 'The character was:',
        restart: 'Play Again',
        networkError: 'Network error, please retry.',
        questionsAsked: 'questions asked',
        langToggle: 'FR',
    },
};

function t(key) {
    return i18n[language]?.[key] || i18n.en[key] || key;
}

// ---------------------------------------------------------------------------
//  Screen Management (animated transitions)
// ---------------------------------------------------------------------------
let currentScreen = 'welcome';

function showScreen(name) {
    const current = $(`#screen-${currentScreen}`);
    const next = $(`#screen-${name}`);
    if (!next || currentScreen === name) return;

    if (current) {
        current.classList.add('exiting');
        current.classList.remove('active');
        setTimeout(() => {
            current.classList.remove('exiting');
            current.style.display = 'none';
        }, 400);
    }

    next.style.display = 'flex';
    // Force reflow to trigger transition
    void next.offsetHeight;
    next.classList.add('active');

    currentScreen = name;

    if (name !== 'game') {
        stopRecognition();
        gameActive = false;
    }
}

// ---------------------------------------------------------------------------
//  Language Toggle
// ---------------------------------------------------------------------------
$('#lang-toggle').addEventListener('click', () => {
    language = language === 'fr' ? 'en' : 'fr';
    updateAllI18n();
});

// ---------------------------------------------------------------------------
//  Difficulty Selection
// ---------------------------------------------------------------------------
$$('.difficulty-card').forEach((card) => {
    card.addEventListener('click', () => {
        $$('.difficulty-card').forEach((c) => c.classList.remove('selected'));
        card.classList.add('selected');
        difficulty = card.dataset.diff;
    });
});

$$('.theme-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
        $$('.theme-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        selectedTheme = chip.dataset.theme;
    });
});

// ---------------------------------------------------------------------------
//  Mic Mode Selection
// ---------------------------------------------------------------------------
$$('.mic-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
        $$('.mic-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        micMode = btn.dataset.mic;
        updateMicUI();
    });
});

// ---------------------------------------------------------------------------
//  Navigation
// ---------------------------------------------------------------------------
$('#btn-play').addEventListener('click', () => showScreen('difficulty'));
$('#btn-back-diff').addEventListener('click', () => showScreen('welcome'));
$('#btn-start').addEventListener('click', startGame);
$('#btn-back-game').addEventListener('click', () => {
    gameActive = false;
    stopRecognition();
    showScreen('welcome');
});
$('#btn-restart').addEventListener('click', () => {
    gameActive = false;
    stopRecognition();
    showScreen('welcome');
});

// ---------------------------------------------------------------------------
//  i18n Updates
// ---------------------------------------------------------------------------
function updateAllI18n() {
    // Welcome
    $('#welcome-subtitle').textContent = t('subtitle');
    $('#welcome-tagline').textContent = t('tagline');
    $('#btn-play').textContent = t('play');
    $('#lang-toggle').textContent = t('langToggle');

    // Difficulty
    $('#diff-title').textContent = t('chooseDifficulty');
    $('#back-label').textContent = t('back');
    $('#diff-easy-name').textContent = t('easy');
    $('#diff-easy-desc').textContent = t('easyDesc');
    $('#diff-medium-name').textContent = t('medium');
    $('#diff-medium-desc').textContent = t('mediumDesc');
    $('#diff-hard-name').textContent = t('hard');
    $('#diff-hard-desc').textContent = t('hardDesc');
    $('#mic-mode-label').textContent = t('micLabel');
    $('#theme-label').textContent = t('themes');
    $('#theme-all').textContent = t('themeAll');
    $('#theme-science').textContent = t('themeScience');
    $('#theme-literature').textContent = t('themeLiterature');
    $('#theme-music').textContent = t('themeMusic');
    $('#theme-cinema').textContent = t('themeCinema');
    $('#theme-sports').textContent = t('themeSports');
    $('#theme-politics').textContent = t('themePolitics');
    $('#theme-arts').textContent = t('themeArts');
    $('#theme-history').textContent = t('themeHistory');
    $('#btn-start').textContent = t('start');

    // Game
    $('#input-question').placeholder = t('askPlaceholder');
    $('#guess-toggle-label').textContent = t('guessToggle');
    $('#give-up-label').textContent = t('giveUp');
    $('#thinking-text').textContent = t('thinking');

    // Guess modal
    $('#guess-modal-title').textContent = t('guessTitle');
    $('#input-guess').placeholder = t('guessPlaceholder');
    $('#btn-guess-confirm').textContent = t('guessConfirm');
    $('#btn-guess-cancel').textContent = t('guessCancel');

    // End
    $('#btn-restart').textContent = t('restart');
}

// ---------------------------------------------------------------------------
//  Mic UI
// ---------------------------------------------------------------------------
function updateMicUI() {
    const recordBtn = $('#btn-record');
    if (micMode === 'off' || !recognition) {
        recordBtn.classList.add('hidden');
    } else if (micMode === 'manual') {
        recordBtn.classList.remove('hidden');
    } else {
        recordBtn.classList.add('hidden');
    }
}

function showMicIndicator() {
    $('#mic-indicator').classList.remove('hidden');
}

function hideMicIndicator() {
    $('#mic-indicator').classList.add('hidden');
}

// ---------------------------------------------------------------------------
//  Start Game
// ---------------------------------------------------------------------------
async function startGame() {
    $('#btn-start').disabled = true;
    try {
        const res = await fetch('/game/new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                language,
                difficulty,
                themes: selectedTheme === 'all' ? [] : [selectedTheme],
            }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || `Error ${res.status}`);
            return;
        }
        const data = await res.json();
        sessionId = data.session_id;
        questionCount = data.question_count;
        guessCount = data.guess_count;
        maxQuestions = data.max_questions;
        maxGuesses = data.max_guesses;
        gameActive = true;
        isGuessMode = false;

        // Clear chat
        clearChat();
        updateCounters();

        showScreen('game');
        showControls();
        renderTurns(data);
    } catch (err) {
        console.error('Failed to start game:', err);
        showToast(t('networkError'));
    } finally {
        $('#btn-start').disabled = false;
    }
}

// ---------------------------------------------------------------------------
//  Chat Rendering
// ---------------------------------------------------------------------------
function clearChat() {
    const container = $('#chat-messages');
    const thinking = $('#thinking-indicator');
    const end = $('#messages-end');
    // Remove only message rows, keep thinking + end anchor
    container.querySelectorAll('.message-row:not(#thinking-indicator)').forEach((el) => el.remove());
    // Re-ensure thinking and end are present and in correct order
    if (thinking) { container.appendChild(thinking); thinking.classList.add('hidden'); }
    if (end) container.appendChild(end);
}

function addMessage(role, text, answer) {
    const container = $('#chat-messages');
    const end = $('#messages-end');

    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role === 'sphinx' ? 'sphinx-bubble' : 'player-bubble'}`;

    const label = document.createElement('span');
    label.className = 'msg-label';
    label.textContent = role === 'sphinx' ? t('sphinxLabel') : t('playerLabel');

    const msgText = document.createElement('span');
    msgText.className = 'msg-text';

    if (role === 'sphinx' && answer) {
        const dot = document.createElement('span');
        dot.className = `answer-dot ${answer}`;
        msgText.appendChild(dot);
    }

    msgText.appendChild(document.createTextNode(text));

    bubble.appendChild(label);
    bubble.appendChild(msgText);
    row.appendChild(bubble);

    container.insertBefore(row, end);
    // Delay scroll slightly to let the DOM render the new element
    requestAnimationFrame(() => {
        row.scrollIntoView({ behavior: 'smooth', block: 'end' });
    });
}

function renderTurns(data) {
    questionCount = data.question_count;
    guessCount = data.guess_count;
    updateCounters();

    const lastTurn = data.turns[data.turns.length - 1];
    if (!lastTurn) return;

    // Add sphinx message
    addMessage('sphinx', lastTurn.sphinx_utterance, lastTurn.raw_answer);

    if (lastTurn.audio_id) {
        playSphinxAudio(lastTurn.audio_id, lastTurn.raw_answer);
    } else {
        flashAvatarAnswer(lastTurn.raw_answer);
        onSphinxDoneSpeaking();
    }

    if (data.state === 'ended') {
        showEndScreen(data);
        return;
    }

    if (data.state === 'listening') {
        isProcessing = false;
        showControls();
        hideThinking();
    }
}

function updateCounters() {
    const qc = $('#question-counter');
    const gc = $('#guess-counter');
    const newQ = `${questionCount}/${maxQuestions}`;
    const newG = `${guessCount}/${maxGuesses}`;

    if (qc.textContent !== newQ) {
        qc.textContent = newQ;
        qc.classList.remove('bump');
        void qc.offsetHeight;
        qc.classList.add('bump');
    }
    if (gc.textContent !== newG) {
        gc.textContent = newG;
        gc.classList.remove('bump');
        void gc.offsetHeight;
        gc.classList.add('bump');
    }
}

function flashAvatarAnswer(answer) {
    const avatar = $('#avatar-welcome');
    if (!answer) return;
    // No game-screen avatar anymore — we use the chat bubble dot instead
}

// ---------------------------------------------------------------------------
//  Controls
// ---------------------------------------------------------------------------
function showControls() {
    $('#controls').classList.remove('hidden');
    $('#guess-modal').classList.add('hidden');
    updateMicUI();
    if (micMode === 'off' || micMode === 'handsfree' || micMode === 'continuous') {
        $('#input-question').focus();
    }
}

function hideControls() {
    const el = $('#controls');
    if (el) el.classList.add('hidden');
}

function showThinking() {
    const el = $('#thinking-indicator');
    if (el) el.classList.remove('hidden');
    const end = $('#messages-end');
    if (end) end.scrollIntoView({ behavior: 'smooth' });
}

function hideThinking() {
    const el = $('#thinking-indicator');
    if (el) el.classList.add('hidden');
}

// ---------------------------------------------------------------------------
//  Audio Playback
// ---------------------------------------------------------------------------
function playSphinxAudio(audioId, answer) {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }

    isPlaying = true;
    if (isListening && (micMode === 'continuous' || micMode === 'handsfree')) {
        stopRecognition();
    }

    currentAudio = new Audio(`/audio/${audioId}`);
    currentAudio.play().catch(() => {
        isPlaying = false;
        onSphinxDoneSpeaking();
    });

    currentAudio.addEventListener('ended', () => {
        currentAudio = null;
        isPlaying = false;
        onSphinxDoneSpeaking();
    });
    currentAudio.addEventListener('error', () => {
        currentAudio = null;
        isPlaying = false;
        onSphinxDoneSpeaking();
    });
}

function onSphinxDoneSpeaking() {
    if (!gameActive || isProcessing) return;

    if (micMode === 'handsfree') {
        setTimeout(() => {
            if (gameActive && !isPlaying && !isProcessing) startAutoRecognition();
        }, AUTO_LISTEN_DELAY_MS);
    } else if (micMode === 'continuous') {
        setTimeout(() => {
            if (gameActive && !isPlaying && !isProcessing) startContinuousRecognition();
        }, AUTO_LISTEN_DELAY_MS);
    }
}

// ---------------------------------------------------------------------------
//  Ask / Guess
// ---------------------------------------------------------------------------
$('#btn-send').addEventListener('click', submitQuestion);
$('#input-question').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitQuestion();
});

$('#btn-guess-toggle').addEventListener('click', () => {
    if (isListening) stopRecognition();
    $('#guess-modal').classList.remove('hidden');
    $('#input-guess').value = '';
    $('#input-guess').focus();
});

$('#btn-guess-cancel').addEventListener('click', () => {
    $('#guess-modal').classList.add('hidden');
    if (micMode === 'continuous') startContinuousRecognition();
});

$('#btn-guess-confirm').addEventListener('click', submitGuess);
$('#input-guess').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitGuess();
});

async function submitQuestion() {
    const input = $('#input-question');
    const text = input.value.trim();
    if (!text) return;

    // Add player message to chat
    addMessage('player', text);

    input.value = '';
    isProcessing = true;
    hideControls();
    showThinking();
    hideMicIndicator();
    if (isListening) stopRecognition();

    try {
        const res = await fetch(`/game/${sessionId}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        hideThinking();
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || `Error ${res.status}`);
            isProcessing = false;
            showControls();
            onSphinxDoneSpeaking();
            return;
        }
        const data = await res.json();
        renderTurns(data);
    } catch (err) {
        console.error('Failed to ask:', err);
        hideThinking();
        showToast(t('networkError'));
        isProcessing = false;
        showControls();
        onSphinxDoneSpeaking();
    }
}

async function submitGuess() {
    const input = $('#input-guess');
    const name = input.value.trim();
    if (!name) return;

    $('#guess-modal').classList.add('hidden');

    // Add player guess to chat
    addMessage('player', `🎯 ${name}`);

    isProcessing = true;
    hideControls();
    showThinking();
    hideMicIndicator();

    try {
        const res = await fetch(`/game/${sessionId}/guess`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        hideThinking();
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || `Error ${res.status}`);
            isProcessing = false;
            showControls();
            onSphinxDoneSpeaking();
            return;
        }
        const data = await res.json();
        renderTurns(data);
    } catch (err) {
        console.error('Failed to guess:', err);
        hideThinking();
        showToast(t('networkError'));
        isProcessing = false;
        showControls();
        onSphinxDoneSpeaking();
    }
}

// ---------------------------------------------------------------------------
//  Voice Recognition — 3 modes
// ---------------------------------------------------------------------------
function stopRecognition() {
    if (recognition && isListening) {
        try { recognition.abort(); } catch (_) {}
    }
    isListening = false;
    hideMicIndicator();
    const btn = $('#btn-record');
    if (btn) btn.classList.remove('recording');
}

// --- Manual ---
$('#btn-record').addEventListener('click', toggleManualRecognition);

function toggleManualRecognition() {
    if (!recognition || micMode !== 'manual') return;

    if (isListening) {
        stopRecognition();
        return;
    }

    recognition.continuous = false;
    recognition.lang = language === 'fr' ? 'fr-FR' : 'en-US';

    recognition.onstart = () => {
        isListening = true;
        $('#btn-record').classList.add('recording');
        showMicIndicator();
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript.trim();
        if (transcript.length >= MIN_TRANSCRIPT_LEN) {
            $('#input-question').value = transcript;
            submitQuestion();
        }
    };

    recognition.onerror = () => {
        isListening = false;
        $('#btn-record').classList.remove('recording');
        hideMicIndicator();
    };

    recognition.onend = () => {
        isListening = false;
        $('#btn-record').classList.remove('recording');
        hideMicIndicator();
    };

    recognition.start();
}

// --- Hands-free ---
function startAutoRecognition() {
    if (!recognition || micMode !== 'handsfree') return;
    if (isListening || isPlaying || isProcessing || !gameActive) return;

    recognition.continuous = false;
    recognition.lang = language === 'fr' ? 'fr-FR' : 'en-US';

    recognition.onstart = () => {
        isListening = true;
        showMicIndicator();
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript.trim();
        if (transcript.length >= MIN_TRANSCRIPT_LEN) {
            $('#input-question').value = transcript;
            submitQuestion();
        }
    };

    recognition.onerror = (event) => {
        isListening = false;
        hideMicIndicator();
        if (event.error === 'no-speech' || event.error === 'aborted') {
            setTimeout(() => {
                if (gameActive && !isPlaying && !isProcessing && micMode === 'handsfree') {
                    startAutoRecognition();
                }
            }, 1000);
        }
    };

    recognition.onend = () => {
        isListening = false;
        hideMicIndicator();
        if (gameActive && !isPlaying && !isProcessing && micMode === 'handsfree') {
            setTimeout(() => startAutoRecognition(), 500);
        }
    };

    try { recognition.start(); } catch (e) {
        console.warn('[Handsfree] Start failed:', e);
        isListening = false;
    }
}

// --- Continuous ---
function startContinuousRecognition() {
    if (!recognition || micMode !== 'continuous') return;
    if (isListening || isPlaying || isProcessing || !gameActive) return;

    recognition.continuous = true;
    recognition.lang = language === 'fr' ? 'fr-FR' : 'en-US';

    recognition.onstart = () => {
        isListening = true;
        showMicIndicator();
    };

    recognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                const transcript = event.results[i][0].transcript.trim();
                if (transcript.length >= MIN_TRANSCRIPT_LEN && !isProcessing && !isPlaying) {
                    $('#input-question').value = transcript;
                    submitQuestion();
                    return;
                }
            }
        }
    };

    recognition.onerror = (event) => {
        if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
            isListening = false;
            hideMicIndicator();
            showToast(language === 'fr' ? 'Micro non autorise' : 'Microphone not allowed');
            return;
        }
    };

    recognition.onend = () => {
        isListening = false;
        hideMicIndicator();
        if (gameActive && !isPlaying && !isProcessing && micMode === 'continuous') {
            setTimeout(() => startContinuousRecognition(), 300);
        }
    };

    try { recognition.start(); } catch (e) {
        console.warn('[Continuous] Start failed:', e);
        isListening = false;
    }
}

// ---------------------------------------------------------------------------
//  End Screen
// ---------------------------------------------------------------------------
function showEndScreen(data) {
    gameActive = false;
    stopRecognition();

    const isWin = data.result === 'win';
    $('#end-icon').textContent = isWin ? '🏆' : '𓁹';
    $('#end-title').textContent = isWin ? t('winTitle') : t('loseTitle');
    $('#end-message').textContent = isWin ? t('endWin') : t('endLose');

    if (data.revealed_character) {
        $('#end-character').textContent = `${t('revealed')} ${data.revealed_character}`;
    } else {
        $('#end-character').textContent = '';
    }

    $('#end-stats').textContent = `${questionCount} ${t('questionsAsked')}`;

    // Small delay so user sees the last sphinx message before transition
    setTimeout(() => showScreen('end'), 1200);
}

// ---------------------------------------------------------------------------
//  Toast
// ---------------------------------------------------------------------------
function showToast(message, durationMs = 4000) {
    let container = $('#toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));
    setTimeout(() => {
        toast.classList.remove('visible');
        setTimeout(() => toast.remove(), 300);
    }, durationMs);
}

// ---------------------------------------------------------------------------
//  Init
// ---------------------------------------------------------------------------
if (!recognition) {
    micMode = 'off';
    const micSelect = $('#mic-mode-select');
    if (micSelect) micSelect.style.display = 'none';
}

// Hide all screens except welcome on load
$$('.screen').forEach((s) => {
    s.style.display = 'none';
    s.classList.remove('active');
});
$('#screen-welcome').style.display = 'flex';
$('#screen-welcome').classList.add('active');

updateAllI18n();
updateMicUI();
