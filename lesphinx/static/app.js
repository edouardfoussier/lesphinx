// === LeSphinx Frontend (Reversed Mode — Dual Chat/Voice UI) ===

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
let hintsRemaining = 3;
let maxHints = 3;

const AUTO_LISTEN_DELAY_MS = 400;
const MIN_TRANSCRIPT_LEN = 2;
const VOICE_TIMER_SECONDS = 30;

// Voice mode state
let isVoiceMode = false;
let voiceTimerInterval = null;
let voiceTimerRemaining = 0;
let audioContext = null;
let analyserNode = null;
let orbAnimFrame = null;
let pendingTranscript = '';

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
    void next.offsetHeight;
    next.classList.add('active');
    staggerChildren(next);

    currentScreen = name;

    if (name !== 'game') {
        stopRecognition();
        gameActive = false;
    }
}

function staggerChildren(screen) {
    screen.querySelectorAll('.theme-card').forEach((card, i) => {
        card.classList.remove('stagger-in');
        void card.offsetHeight;
        card.style.setProperty('--delay', `${0.4 + i * 0.04}s`);
        card.classList.add('stagger-in');
    });

    const heroGif = screen.querySelector('.hero-gif');
    if (heroGif) {
        heroGif.classList.remove('float-anim');
        setTimeout(() => heroGif.classList.add('float-anim'), 800);
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

$$('.theme-card').forEach((card) => {
    card.addEventListener('click', () => {
        $$('.theme-card').forEach((c) => c.classList.remove('active'));
        card.classList.add('active');
        selectedTheme = card.dataset.theme;
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
    const themeNames = {
        all: 'themeAll', science: 'themeScience', literature: 'themeLiterature',
        music: 'themeMusic', cinema: 'themeCinema', sports: 'themeSports',
        politics: 'themePolitics', arts: 'themeArts', history: 'themeHistory',
    };
    for (const [key, i18nKey] of Object.entries(themeNames)) {
        const el = $(`#theme-${key}`);
        if (el) {
            const nameSpan = el.querySelector('.theme-card-name');
            if (nameSpan) nameSpan.textContent = t(i18nKey);
            else el.textContent = t(i18nKey);
        }
    }
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

        hintsRemaining = maxHints;
        updateHintCounters();

        clearChat();
        updateCounters();

        setupVoiceMode();
        showScreen('game');
        showControls();
        startBgMusic();
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

    if (isVoiceMode) {
        showVoiceSphinxText(lastTurn.sphinx_utterance);
        const orb = $('#voice-orb');
        if (orb) orb.classList.remove('listening');
    } else {
        addMessage('sphinx', lastTurn.sphinx_utterance, lastTurn.raw_answer);
    }

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
    // No game-screen avatar anymore — we use the chat bubble dot / voice orb
}

function updateHintCounters() {
    const badge = $('#hint-counter-badge');
    const voiceCount = $('#voice-hint-count');
    if (badge) {
        badge.textContent = hintsRemaining;
        badge.classList.toggle('depleted', hintsRemaining <= 0);
    }
    if (voiceCount) {
        voiceCount.textContent = hintsRemaining;
    }
    const hintBtn = $('#btn-hint');
    const voiceHintBtn = $('#voice-hint-btn');
    if (hintBtn) hintBtn.disabled = hintsRemaining <= 0;
    if (voiceHintBtn) voiceHintBtn.disabled = hintsRemaining <= 0;
}

async function requestHint() {
    if (hintsRemaining <= 0 || !sessionId || isProcessing) return;

    isProcessing = true;
    try {
        const res = await fetch(`/game/${sessionId}/hint`, { method: 'POST' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || `Error ${res.status}`);
            isProcessing = false;
            return;
        }
        const data = await res.json();
        hintsRemaining--;
        updateHintCounters();

        const badge = $('#hint-counter-badge');
        if (badge) {
            badge.classList.remove('bumping');
            void badge.offsetHeight;
            badge.classList.add('bumping');
        }

        playSfx('ding');

        if (data.hint_text) {
            if (isVoiceMode) {
                showVoiceSphinxText(data.hint_text);
            } else {
                addMessage('sphinx', `💡 ${data.hint_text}`);
            }
        }

        if (data.audio_id) {
            playSphinxAudio(data.audio_id);
        }
    } catch (err) {
        console.error('Hint error:', err);
        showToast(t('networkError'));
    } finally {
        isProcessing = false;
    }
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

    if (isVoiceMode) {
        initAudioContext();
        if (audioContext.state === 'suspended') audioContext.resume();
        connectAudioToAnalyser(currentAudio);
        const orb = $('#voice-orb');
        if (orb) orb.classList.add('speaking');
        startOrbAnimation();
        stopVoiceTimer();
    }

    currentAudio.play().catch(() => {
        isPlaying = false;
        if (isVoiceMode) {
            stopOrbAnimation();
            const orb = $('#voice-orb');
            if (orb) orb.classList.remove('speaking');
        }
        onSphinxDoneSpeaking();
    });

    currentAudio.addEventListener('ended', () => {
        currentAudio = null;
        isPlaying = false;
        if (isVoiceMode) {
            stopOrbAnimation();
            const orb = $('#voice-orb');
            if (orb) orb.classList.remove('speaking');
        }
        onSphinxDoneSpeaking();
    });
    currentAudio.addEventListener('error', () => {
        currentAudio = null;
        isPlaying = false;
        if (isVoiceMode) {
            stopOrbAnimation();
            const orb = $('#voice-orb');
            if (orb) orb.classList.remove('speaking');
        }
        onSphinxDoneSpeaking();
    });
}

function onSphinxDoneSpeaking() {
    if (!gameActive || isProcessing) return;

    if (isVoiceMode) {
        startVoiceTimer();
        const orb = $('#voice-orb');
        if (orb) orb.classList.add('listening');
    }

    if (micMode === 'handsfree') {
        setTimeout(() => {
            if (gameActive && !isPlaying && !isProcessing) startAutoRecognition();
        }, AUTO_LISTEN_DELAY_MS);
    } else if (micMode === 'continuous') {
        setTimeout(() => {
            if (gameActive && !isPlaying && !isProcessing) startContinuousRecognition();
        }, AUTO_LISTEN_DELAY_MS);
    } else if (micMode === 'manual' && isVoiceMode) {
        setTimeout(() => {
            if (gameActive && !isPlaying && !isProcessing) toggleManualRecognition();
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

$('#btn-hint').addEventListener('click', requestHint);

$('#btn-guess-toggle').addEventListener('click', () => {
    if (isListening) stopRecognition();
    if (isVoiceMode) stopVoiceTimer();
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

    if (isVoiceMode) {
        stopVoiceTimer();
        showVoiceSphinxText('...');
        hideVoiceTranscript();
        const orb = $('#voice-orb');
        if (orb) orb.classList.remove('listening');
    } else {
        addMessage('player', text);
    }

    input.value = '';
    pendingTranscript = '';
    isProcessing = true;
    hideControls();
    if (!isVoiceMode) showThinking();
    hideMicIndicator();
    if (isListening) stopRecognition();
    playSfx('whoosh');

    try {
        const res = await fetch(`/game/${sessionId}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        if (!isVoiceMode) hideThinking();
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
        if (!isVoiceMode) hideThinking();
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
            if (isVoiceMode) {
                pendingTranscript = transcript;
                showVoiceTranscript(transcript);
            }
            $('#input-question').value = transcript;
            if (!isVoiceMode) submitQuestion();
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
            if (isVoiceMode) {
                pendingTranscript = transcript;
                showVoiceTranscript(transcript);
            }
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
                    if (isVoiceMode) {
                        pendingTranscript = transcript;
                        showVoiceTranscript(transcript);
                    }
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
//  Voice Mode
// ---------------------------------------------------------------------------
function setupVoiceMode() {
    isVoiceMode = micMode !== 'off';

    const chatEl = $('#chat-container');
    const voiceEl = $('#voice-container');

    if (isVoiceMode) {
        chatEl.classList.add('hidden');
        voiceEl.classList.remove('hidden');
    } else {
        chatEl.classList.remove('hidden');
        voiceEl.classList.add('hidden');
    }
}

function initAudioContext() {
    if (audioContext) return;
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = 256;
    analyserNode.smoothingTimeConstant = 0.8;
}

function connectAudioToAnalyser(audioElement) {
    if (!audioContext || !analyserNode) return;
    try {
        const source = audioContext.createMediaElementSource(audioElement);
        source.connect(analyserNode);
        analyserNode.connect(audioContext.destination);
    } catch (_) { /* already connected */ }
}

function startOrbAnimation() {
    if (!analyserNode || orbAnimFrame) return;
    const canvas = $('#orb-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const bufLen = analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufLen);

    function draw() {
        orbAnimFrame = requestAnimationFrame(draw);
        analyserNode.getByteFrequencyData(dataArray);

        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h / 2;

        ctx.clearRect(0, 0, w, h);

        let avg = 0;
        for (let i = 0; i < bufLen; i++) avg += dataArray[i];
        avg = avg / bufLen / 255;

        const baseR = 60;
        const maxR = 90;
        const r = baseR + avg * (maxR - baseR);

        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        gradient.addColorStop(0, `rgba(230, 160, 0, ${0.3 + avg * 0.5})`);
        gradient.addColorStop(0.6, `rgba(230, 160, 0, ${0.1 + avg * 0.2})`);
        gradient.addColorStop(1, 'rgba(230, 160, 0, 0)');

        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        for (let i = 0; i < bufLen; i += 4) {
            const val = dataArray[i] / 255;
            const angle = (i / bufLen) * Math.PI * 2;
            const barR = baseR + val * 35;
            const x1 = cx + Math.cos(angle) * baseR * 0.8;
            const y1 = cy + Math.sin(angle) * baseR * 0.8;
            const x2 = cx + Math.cos(angle) * barR;
            const y2 = cy + Math.sin(angle) * barR;

            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = `rgba(230, 160, 0, ${0.2 + val * 0.6})`;
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }
    draw();
}

function stopOrbAnimation() {
    if (orbAnimFrame) {
        cancelAnimationFrame(orbAnimFrame);
        orbAnimFrame = null;
    }
    const canvas = $('#orb-canvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, 60);
        gradient.addColorStop(0, 'rgba(230, 160, 0, 0.15)');
        gradient.addColorStop(1, 'rgba(230, 160, 0, 0)');
        ctx.beginPath();
        ctx.arc(cx, cy, 60, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
    }
}

function startVoiceTimer() {
    voiceTimerRemaining = VOICE_TIMER_SECONDS;
    const timerText = $('#voice-timer-text');
    const timerSecs = $('#timer-seconds');
    const progress = $('#timer-progress');
    if (timerText) timerText.classList.remove('hidden', 'urgent');
    if (timerSecs) timerSecs.textContent = voiceTimerRemaining;

    const circumference = 2 * Math.PI * 90;
    if (progress) progress.style.strokeDashoffset = '0';

    voiceTimerInterval = setInterval(() => {
        voiceTimerRemaining--;
        if (timerSecs) timerSecs.textContent = voiceTimerRemaining;

        const fraction = 1 - (voiceTimerRemaining / VOICE_TIMER_SECONDS);
        if (progress) progress.style.strokeDashoffset = (fraction * circumference).toString();

        if (voiceTimerRemaining <= 5) {
            if (timerText) timerText.classList.add('urgent');
            playSfx('tick');
        }

        if (voiceTimerRemaining <= 0) {
            stopVoiceTimer();
            voiceSubmitCurrent();
        }
    }, 1000);
}

function stopVoiceTimer() {
    if (voiceTimerInterval) {
        clearInterval(voiceTimerInterval);
        voiceTimerInterval = null;
    }
    const timerText = $('#voice-timer-text');
    if (timerText) timerText.classList.add('hidden');
}

function showVoiceSphinxText(text) {
    const el = $('#voice-sphinx-text');
    if (!el) return;
    el.textContent = text;
    el.classList.remove('hidden');
    el.style.animation = 'none';
    void el.offsetHeight;
    el.style.animation = '';
}

function hideVoiceSphinxText() {
    const el = $('#voice-sphinx-text');
    if (el) el.classList.add('hidden');
}

function showVoiceTranscript(text) {
    const el = $('#voice-transcript');
    if (!el) return;
    el.textContent = text;
    el.classList.remove('hidden');
}

function hideVoiceTranscript() {
    const el = $('#voice-transcript');
    if (el) el.classList.add('hidden');
}

function voiceSubmitCurrent() {
    if (!gameActive || isProcessing) return;
    const text = pendingTranscript.trim() || $('#input-question')?.value?.trim();
    if (text && text.length >= MIN_TRANSCRIPT_LEN) {
        $('#input-question').value = text;
        pendingTranscript = '';
        hideVoiceTranscript();
        submitQuestion();
    }
}

// Voice mode event listeners
document.addEventListener('DOMContentLoaded', () => {
    const voiceSubmit = $('#voice-submit-btn');
    if (voiceSubmit) voiceSubmit.addEventListener('click', voiceSubmitCurrent);

    const voiceGuess = $('#voice-guess-btn');
    if (voiceGuess) voiceGuess.addEventListener('click', () => {
        if (isListening) stopRecognition();
        stopVoiceTimer();
        $('#guess-modal').classList.remove('hidden');
        $('#input-guess').value = '';
        $('#input-guess').focus();
    });

    const voiceHint = $('#voice-hint-btn');
    if (voiceHint) voiceHint.addEventListener('click', requestHint);
});

// ---------------------------------------------------------------------------
//  End Screen
// ---------------------------------------------------------------------------
function showEndScreen(data) {
    gameActive = false;
    stopRecognition();
    stopVoiceTimer();
    stopOrbAnimation();
    stopBgMusic();

    const isWin = data.result === 'win';
    playSfx(isWin ? 'fanfare' : 'gong');
    $('#end-icon').textContent = isWin ? '🏆' : '𓁹';
    $('#end-title').textContent = isWin ? t('winTitle') : t('loseTitle');
    $('#end-message').textContent = isWin ? t('endWin') : t('endLose');

    const reveal = $('#end-reveal');
    if (data.revealed_character) {
        reveal.classList.remove('hidden');
        $('#end-character').textContent = data.revealed_character;

        if (data.revealed_image) {
            const photo = $('#end-photo');
            photo.src = data.revealed_image;
            photo.alt = data.revealed_character;
            photo.parentElement.style.display = '';
        } else {
            $('#end-photo').parentElement.style.display = 'none';
        }

        if (data.revealed_summary) {
            $('#end-summary').textContent = data.revealed_summary;
        } else {
            $('#end-summary').textContent = '';
        }
    } else {
        reveal.classList.add('hidden');
    }

    $('#end-stats').textContent = `${questionCount} ${t('questionsAsked')}`;

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
//  Sound Manager
// ---------------------------------------------------------------------------
const SFX_PATHS = {
    tick: '/sfx/tick.wav',
    ding: '/sfx/ding.wav',
    whoosh: '/sfx/whoosh.wav',
    fanfare: '/sfx/fanfare.wav',
    gong: '/sfx/gong.wav',
};
const sfxCache = {};
let soundEnabled = true;
let bgMusic = null;

function preloadSfx() {
    for (const [name, path] of Object.entries(SFX_PATHS)) {
        const a = new Audio(path);
        a.preload = 'auto';
        a.volume = 0.4;
        sfxCache[name] = a;
    }
}

function playSfx(name) {
    if (!soundEnabled) return;
    const cached = sfxCache[name];
    if (cached) {
        const clone = cached.cloneNode();
        clone.volume = cached.volume;
        clone.play().catch(() => {});
    }
}

function startBgMusic() {
    if (!soundEnabled) return;
    if (bgMusic) { bgMusic.play().catch(() => {}); return; }
    bgMusic = new Audio('/sfx/ambient.wav');
    bgMusic.loop = true;
    bgMusic.volume = 0.12;
    bgMusic.play().catch(() => {});
}

function stopBgMusic() {
    if (bgMusic) { bgMusic.pause(); bgMusic.currentTime = 0; }
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    const btn = $('#btn-sound-toggle');
    if (btn) btn.textContent = soundEnabled ? '🔊' : '🔇';
    if (!soundEnabled) stopBgMusic();
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
const welcomeScreen = $('#screen-welcome');
welcomeScreen.style.display = 'flex';
void welcomeScreen.offsetHeight;
welcomeScreen.classList.add('active');
staggerChildren(welcomeScreen);

preloadSfx();
const soundToggle = $('#btn-sound-toggle');
if (soundToggle) soundToggle.addEventListener('click', toggleSound);

updateAllI18n();
updateMicUI();
