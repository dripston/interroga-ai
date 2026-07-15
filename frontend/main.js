// ===== AI Detective — Main Game Logic =====

const CHARACTER_POOL = [
  { id: 'street-boy', name: 'Viktor "Knuckles" Petrov', type: 'young-male' },
  { id: 'scared-boy', name: 'Eddie Marsh', type: 'young-male' },
  { id: 'bald-uncle', name: 'Don Enzo Moretti', type: 'old-male' },
  { id: 'calm-uncle', name: 'Richard Ashford III', type: 'old-male' },
  { id: 'modern-girl', name: 'Scarlett Dubois', type: 'young-female' },
  { id: 'athletic-girl', name: 'Maya "Ace" Torres', type: 'young-female' },
  { id: 'old-aunty', name: 'Beatrice Harmon', type: 'old-female' },
  { id: 'modern-aunty', name: 'Vivienne LaRoux', type: 'old-female' },
];

function pickSuspects(count = 5) {
  const shuffled = [...CHARACTER_POOL].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
}

const state = {
  suspects: [], activeSuspect: null, isTalking: false, talkInterval: null,
  timerInterval: null, elapsedSeconds: 0, introTyping: null, introSkipped: false,
  micMuted: false,
};

const $landing = document.getElementById('landing');
const $landingCta = document.getElementById('landing-cta');
const $modeSelect = document.getElementById('mode-select');
const $modeText = document.getElementById('mode-text');
const $modeVoice = document.getElementById('mode-voice');
const $langSelect = document.getElementById('lang-select');
const $langGrid = document.getElementById('lang-grid');
const $langBack = document.getElementById('lang-back');
const $diffSelect = document.getElementById('diff-select');
const $diffBack = document.getElementById('diff-back');
const $diffStep = document.getElementById('diff-step');
const $textModeNotice = document.getElementById('text-mode-notice');
const $gameIntro = document.getElementById('game-intro');
const $introStamp = document.getElementById('intro-stamp');
const $introCaseNumber = document.getElementById('intro-case-number');
const $introDate = document.getElementById('intro-date');
const $introText = document.getElementById('intro-text');
const $introProgressBar = document.getElementById('intro-progress-bar');
const $beginBtn = document.getElementById('begin-btn');
const $skipBtn = document.getElementById('skip-btn');
const $introCursor = document.querySelector('.intro-cursor');
const $redacted1 = document.getElementById('redacted-1');
const $redactedText1 = document.getElementById('redacted-text-1');
const $gameScene = document.getElementById('game-scene');
const $suspectsLineup = document.getElementById('suspects-lineup');
const $hudTimer = document.getElementById('hud-timer');
const $hudSuspects = document.getElementById('hud-suspects');
const $hudCase = document.getElementById('hud-case');
const $interrogationOverlay = document.getElementById('interrogation-overlay');
const $suspectCloseup = document.getElementById('suspect-closeup');
const $suspectNameTag = document.getElementById('suspect-name-tag');
const $backBtn = document.getElementById('back-btn');
const $dialogueText = document.getElementById('dialogue-text');
const $micBtn = document.getElementById('mic-btn');
const $micMuteBtn = document.getElementById('mic-mute-btn');
const $textInputContainer = document.getElementById('text-input-container');
const $qLeftVal = document.getElementById('q-left-val');
const $interrogationTextInput = document.getElementById('interrogation-text-input');
const $sendBtn = document.getElementById('send-btn');
const $partnerTextContainer = document.getElementById('partner-text-container');
const $partnerTextInput = document.getElementById('partner-text-input');
const $partnerSendBtn = document.getElementById('partner-send-btn');
const $screenFlash = document.getElementById('screen-flash');
const $globalMuteBtn = document.getElementById('global-mute-btn');

// AUDIO
const audioCtx = {
  landing: { play: () => Promise.resolve(), pause: () => {}, loop: false, volume: 0, currentTime: 0 },
  bgm: new Audio('./assets/audio/bgm.mp3'),
  clock: new Audio('./assets/audio/clock.mp3'),
  outro: { play: () => Promise.resolve(), pause: () => {}, loop: false, volume: 0, currentTime: 0 },
  click: new Audio('./assets/audio/click.mp3'),
  muted: false,
};
audioCtx.bgm.loop = true;
audioCtx.clock.loop = true;
audioCtx.bgm.volume = 0.5;
audioCtx.clock.volume = 0.15;
let landingMusicStarted = false;

function playClick() { if (audioCtx.muted) return; audioCtx.click.currentTime = 0; audioCtx.click.play().catch(() => { }); }
document.addEventListener('click', (e) => {
  if (e.target.closest('button') || e.target.closest('.btn') || e.target.closest('.neon-btn') || e.target.closest('.suspect-slot') || e.target.closest('.lang-card') || e.target.closest('.diff-card') || e.target.closest('#mode-text') || e.target.closest('#mode-voice')) playClick();
});
if ($globalMuteBtn) {
  $globalMuteBtn.addEventListener('click', (e) => {
    e.stopPropagation(); audioCtx.muted = !audioCtx.muted;
    $globalMuteBtn.textContent = audioCtx.muted ? '🔇' : '🔊';
    if (audioCtx.muted) {
      audioCtx.bgm.pause();
      audioCtx.clock.pause();
      stopBriefingAudio();
      audioQueue.stop();
    }
    else {
      if (!$gameScene.classList.contains('screen-hidden')) {
        audioCtx.bgm.play().catch(() => { });
        audioCtx.clock.play().catch(() => { });
      }
    }
  });
}

function switchScreen(hideEl, showEl) { flashTransition(); setTimeout(() => { hideEl.classList.add('screen-hidden'); showEl.classList.remove('screen-hidden'); }, 150); }
function flashTransition() { return new Promise(resolve => { $screenFlash.classList.add('flash-active'); setTimeout(() => { $screenFlash.classList.remove('flash-active'); resolve(); }, 600); }); }
function getFormattedTime() { const m = String(Math.floor(state.elapsedSeconds / 60)).padStart(2, '0'); const s = String(state.elapsedSeconds % 60).padStart(2, '0'); return `${m}:${s}`; }

function handleLandingStart() { switchScreen($landing, $modeSelect); }
$landingCta.addEventListener('click', handleLandingStart);
document.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !$landing.classList.contains('screen-hidden')) handleLandingStart(); });

$modeText.addEventListener('click', () => { state.gameMode = 'text'; state.language = 'en'; $diffStep.innerHTML = 'STEP 02 <span class="step-divider">/</span> 02'; $textModeNotice.style.display = 'flex'; switchScreen($modeSelect, $diffSelect); });
$modeVoice.addEventListener('click', () => { state.gameMode = 'voice'; switchScreen($modeSelect, $langSelect); });

$langGrid.addEventListener('click', (e) => { const card = e.target.closest('.lang-card'); if (!card) return; state.language = card.dataset.lang; $langGrid.querySelectorAll('.lang-card').forEach(c => c.classList.remove('selected')); card.classList.add('selected'); setTimeout(() => { $diffStep.innerHTML = 'STEP 03 <span class="step-divider">/</span> 03'; $textModeNotice.style.display = 'none'; switchScreen($langSelect, $diffSelect); }, 300); });
$langBack.addEventListener('click', () => switchScreen($langSelect, $modeSelect));

document.querySelectorAll('.diff-card').forEach(card => { card.addEventListener('click', () => { state.difficulty = card.dataset.diff; switchScreen($diffSelect, $gameIntro); setTimeout(() => startGameIntro(), 200); }); });
$diffBack.addEventListener('click', () => { if (state.gameMode === 'text') switchScreen($diffSelect, $modeSelect); else switchScreen($diffSelect, $langSelect); });

const API_BASE = '';
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

// ===== BRIEFING AUDIO =====
let currentBriefingAudio = null;
let briefingAudioQueue = [];
let isBriefingPlaying = false;
let briefingFetchIndex = 0;

async function fetchAllBriefingSentences(sentences) {
  for (let i = 0; i < sentences.length; i++) {
    if (state.briefingCancelled || audioCtx.muted) break;
    const s = sentences[i].trim();
    if (!s) { briefingFetchIndex++; continue; }
    console.log(`[Sarvam TTS] Requesting audio for sentence ${i + 1}/${sentences.length}: "${s}"`);
    try {
      const res = await fetch("https://api.sarvam.ai/text-to-speech", {
        method: "POST",
        headers: { "api-subscription-key": "sk_x4jwxt2b_jW4NsA1QR7b9a5tFPqbIaDd9", "Content-Type": "application/json" },
        body: JSON.stringify({ text: s, target_language_code: "en-IN", speaker: "varun", pace: 1.0, speech_sample_rate: 16000, model: "bulbul:v3" })
      });
      if (state.briefingCancelled) break;
      if (res.ok) {
        const data = await res.json();
        const b64 = data.audios[0];
        console.log(`[Sarvam TTS] Received base64 audio response for sentence ${i + 1}. Data length: ${b64.length}`);
        const binary = atob(b64);
        const bytes = new Uint8Array(binary.length);
        for (let j = 0; j < binary.length; j++) bytes[j] = binary.charCodeAt(j);
        const blob = new Blob([bytes], { type: 'audio/wav' });
        const url = URL.createObjectURL(blob);
        console.log(`[Sarvam TTS] Generated blob for sentence ${i + 1}. ${blob.size} bytes.`);
        briefingAudioQueue.push(url);
        if (!isBriefingPlaying) playNextBriefingAudio();
      } else {
        const errText = await res.text();
        console.error(`[Sarvam TTS] API Error for sentence ${i + 1}. Status ${res.status}: ${errText}`);
      }
    } catch (err) { console.error("Sarvam TTS error:", err); }
    briefingFetchIndex++;
  }
}

function playNextBriefingAudio() {
  if (state.briefingCancelled || briefingAudioQueue.length === 0) { isBriefingPlaying = false; return; }
  isBriefingPlaying = true;
  const url = briefingAudioQueue.shift();
  currentBriefingAudio = new Audio(url);
  currentBriefingAudio.volume = 1.0;
  currentBriefingAudio.onended = () => { URL.revokeObjectURL(url); currentBriefingAudio = null; playNextBriefingAudio(); };
  currentBriefingAudio.onerror = () => { URL.revokeObjectURL(url); currentBriefingAudio = null; playNextBriefingAudio(); };
  currentBriefingAudio.play().catch(e => { console.error("Briefing audio playback error:", e, url); currentBriefingAudio = null; isBriefingPlaying = false; playNextBriefingAudio(); });
}

function stopBriefingAudio() {
  state.briefingCancelled = true;
  if (currentBriefingAudio) { currentBriefingAudio.pause(); currentBriefingAudio = null; }
  briefingAudioQueue = []; isBriefingPlaying = false;
}

async function playBriefingSequentially(text) {
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
  state._briefingTotalSentences = sentences.length;
  briefingFetchIndex = 0; briefingAudioQueue = []; isBriefingPlaying = false; state.briefingCancelled = false;
  state._originalBgmVolume = audioCtx.bgm ? audioCtx.bgm.volume : 0.5;
  if (audioCtx.bgm) audioCtx.bgm.volume = Math.max(0.05, state._originalBgmVolume - 0.4);
  fetchAllBriefingSentences(sentences);
}

async function startGameIntro() {
  audioCtx.landing.pause();
  $redactedText1.textContent = 'GENERATING NEW CASE FILE...';

  // Cycle loading messages while case is being generated (takes ~1-3 min)
  const loadingMessages = [
    'GENERATING NEW CASE FILE...',
    'CONSULTING CRIMINAL DATABASE...',
    'PROFILING SUSPECTS...',
    'ANALYZING EVIDENCE...',
    'BUILDING AGENT MEMORIES...',
    'COMPILING BRIEFING DOSSIER...',
    'ENCRYPTING CASE CHANNELS...',
  ];
  let msgIdx = 0;
  const loadingInterval = setInterval(() => {
    msgIdx = (msgIdx + 1) % loadingMessages.length;
    $redactedText1.textContent = loadingMessages[msgIdx];
  }, 8000);

  try {
    const res = await fetch(`${API_BASE}/game/create`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ difficulty: state.difficulty || 'medium', language: state.language || 'en-IN', mode: state.gameMode || 'text' })
    });
    clearInterval(loadingInterval);
    if (!res.ok) throw new Error("API Error");
    const data = await res.json();
    state.case_id = data.case_id;
    state.caseTitle = data.title || `CASE #${data.case_id.substring(0, 6).toUpperCase()}`;
    state.briefingText = data.briefing_text;
    if (!audioCtx.muted && state.briefingText) playBriefingSequentially(state.briefingText);
    let pool = [...CHARACTER_POOL];
    state.suspects = data.suspects.map(suspect => {
      const type = suspect.character_type;
      const matchIndex = pool.findIndex(c => c.type === type);
      let selectedId = 'detective';
      if (matchIndex !== -1) { selectedId = pool[matchIndex].id; pool.splice(matchIndex, 1); }
      else if (pool.length > 0) { selectedId = pool[0].id; pool.splice(0, 1); }
      return { ...suspect, id: selectedId, questions_left: 60 };
    });
    $introCaseNumber.textContent = state.caseTitle;
    $introDate.textContent = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }).toUpperCase();
    $redactedText1.textContent = 'PRIORITY: ALPHA — HOMICIDE DIVISION';
    setTimeout(() => $introStamp.classList.add('stamp-active'), 300);
    setTimeout(() => $redacted1.classList.add('revealed'), 1500);
    setTimeout(() => typewriterEffect(state.briefingText), 2500);
  } catch (err) {
    clearInterval(loadingInterval);
    console.error(err);
    state.caseTitle = "CASE ERROR";
    state.briefingText = "Failed to generate case. Check that the backend server is running (port 8000) and your .env API keys are set.";
    $introCaseNumber.textContent = state.caseTitle;
    $redactedText1.textContent = "CONNECTION FAILED";
    setTimeout(() => $redacted1.classList.add('revealed'), 100);
    setTimeout(() => typewriterEffect(state.briefingText), 1000);
  }
}

function typewriterEffect(text) {
  let i = 0; $introText.textContent = ''; state.introSkipped = false;
  state.introTyping = setInterval(() => {
    if (state.introSkipped) return;
    if (i < text.length) { $introText.textContent += text[i]; i++; $introProgressBar.style.width = `${(i / text.length) * 100}%`; }
    else { clearInterval(state.introTyping); state.introTyping = null; finishIntro(); }
  }, 65);
}

function finishIntro() {
  if ($introCursor) $introCursor.classList.add('hidden');
  $introProgressBar.style.width = '100%';
  $beginBtn.classList.remove('screen-hidden'); $beginBtn.classList.add('show');
}

function skipIntro() {
  state.introSkipped = true;
  if (state.introTyping) { clearInterval(state.introTyping); state.introTyping = null; }
  stopBriefingAudio();
  $introText.textContent = state.briefingText || "Loading...";
  $redacted1.classList.add('revealed'); $introStamp.classList.add('stamp-active');
  finishIntro();
}

$skipBtn.addEventListener('click', skipIntro);
$beginBtn.addEventListener('click', () => {
  stopBriefingAudio(); flashTransition();
  setTimeout(() => {
    $gameIntro.classList.add('screen-hidden'); $gameScene.classList.remove('screen-hidden');
    $hudCase.textContent = state.caseTitle; renderLineup(); startTimer();
    if (!audioCtx.muted) {
      audioCtx.bgm.play().catch(() => { });
      audioCtx.clock.play().catch(() => { });
    }
  }, 200);
});

function startTimer() { state.timerInterval = setInterval(() => { state.elapsedSeconds++; const m = String(Math.floor(state.elapsedSeconds / 60)).padStart(2, '0'); const s = String(state.elapsedSeconds % 60).padStart(2, '0'); $hudTimer.textContent = `⏱ ${m}:${s}`; }, 1000); }

function renderLineup() {
  $suspectsLineup.innerHTML = '';
  state.suspects.forEach((suspect, index) => {
    const slot = document.createElement('div'); slot.className = 'suspect-slot'; slot.dataset.index = index;
    const basePath = `./assets/characters/${suspect.id}`;
    slot.innerHTML = `<div class="suspect-img-wrapper"><img class="suspect-img mouth-closed" src="${basePath}/mouth_closed.png" alt="${suspect.name}" draggable="false" /><img class="suspect-img mouth-open" src="${basePath}/mouth_open.png" alt="${suspect.name} talking" draggable="false" /><div class="suspect-glow"></div></div><div class="suspect-number">${suspect.name}</div>`;
    slot.addEventListener('click', () => openInterrogation(index));
    $suspectsLineup.appendChild(slot);
  });
}

// --- AUDIO QUEUE FOR VOICE TTS ---
class AudioQueue {
  constructor() { this.queue = []; this.isPlaying = false; }
  async addChunk(base64Audio, sentence) {
    const binary = atob(base64Audio); const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const blob = new Blob([bytes], { type: 'audio/wav' });
    this.queue.push({ url: URL.createObjectURL(blob), sentence });
    this.playNext();
  }
  playNext() {
    if (this.isPlaying || this.queue.length === 0) return;
    this.isPlaying = true; startTalking();
    const item = this.queue.shift();
    if (item.sentence) {
      if (!state.currentTurnSuspectNameAdded) {
        if ($dialogueText.innerHTML.includes('<em>You:')) $dialogueText.innerHTML += `<br/><br/>`;
        else $dialogueText.innerHTML = "";
        $dialogueText.innerHTML += `<strong>${state.activeSuspect.name}:</strong> `;
        state.currentTurnSuspectNameAdded = true;
      } else {
        $dialogueText.innerHTML += ` `;
      }
      $dialogueText.classList.add('typing-cursor');
      let i = 0;
      if (window.voiceTypingInterval) clearInterval(window.voiceTypingInterval);
      window.voiceTypingInterval = setInterval(() => {
        if (!this.isPlaying) {
          clearInterval(window.voiceTypingInterval);
          return;
        }
        if (i < item.sentence.length) {
          $dialogueText.innerHTML += item.sentence[i];
          i++;
        } else {
          clearInterval(window.voiceTypingInterval);
          $dialogueText.classList.remove('typing-cursor');
        }
      }, 35);
    }
    this.currentAudio = new Audio(item.url);
    if (audioCtx.muted) this.currentAudio.muted = true;
    this.currentAudio.play().catch(() => {
      this.isPlaying = false;
      if (this.queue.length > 0) this.playNext();
      else { stopTalking(); state.isSuspectSpeaking = false; }
    });
    this.currentAudio.onended = () => {
      this.isPlaying = false;
      URL.revokeObjectURL(item.url);
      this.currentAudio = null;
      if (this.queue.length > 0) this.playNext();
      else { stopTalking(); state.isSuspectSpeaking = false; }
    };
  }
  stop() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio.currentTime = 0;
      this.currentAudio = null;
    }
    if (window.voiceTypingInterval) {
      clearInterval(window.voiceTypingInterval);
      window.voiceTypingInterval = null;
      $dialogueText.classList.remove('typing-cursor');
    }
    this.queue = [];
    this.isPlaying = false;
    stopTalking();
    state.isSuspectSpeaking = false;
  }
  clear() { this.stop(); }
}
const audioQueue = new AudioQueue();

function setupWebSocket() {
  if (state.interrogationSocket) state.interrogationSocket.close();
  const wsUrl = `${WS_BASE}/game/${state.case_id}/interrogate/voice`;
  state.interrogationSocket = new WebSocket(wsUrl);
  state.interrogationSocket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'transcript') {
      if (state.isSuspectSpeaking) {
        audioQueue.stop();
        $dialogueText.innerHTML += `<br/><br/><em>You: ${msg.text}</em>`;
      } else {
        $dialogueText.innerHTML = `<em>You: ${msg.text}</em>`;
      }
      state.isSuspectSpeaking = true;
      state.currentTurnSuspectNameAdded = false;
    }
    else if (msg.type === 'audio_chunk') {
      audioQueue.addChunk(msg.data, msg.sentence);
      state.isSuspectSpeaking = true;
    }
    else if (msg.type === 'response_complete') {
      if (typeof msg.questions_remaining === 'number') {
        state.suspects[state.activeSuspect.index].questions_left = msg.questions_remaining;
        $qLeftVal.textContent = msg.questions_remaining;
      }
    }
    else if (msg.type === 'error') {
      if (!state.isSuspectSpeaking) {
        const lower = msg.message ? msg.message.toLowerCase() : "";
        if (!lower.includes('empty') && !lower.includes('no speech') && !lower.includes('no audio')) {
          const langElt = document.querySelector(`.lang-card[data-lang="${state.language || 'en'}"] .lang-label`);
          const langName = langElt ? langElt.textContent : 'English';
          $dialogueText.innerHTML = `<em>[Could you repeat yourself in ${langName}?]</em>`;
        } else {
          $dialogueText.innerHTML = 'Listening... Speak naturally.';
        }
      }
    }
  };
}

function openInterrogation(index) {
  stopBriefingAudio();
  const suspect = state.suspects[index]; state.activeSuspect = { ...suspect, index };
  const basePath = `./assets/characters/${suspect.id}`;
  $suspectCloseup.src = `${basePath}/mouth_closed.png`; $suspectCloseup.dataset.charId = suspect.id;
  $suspectNameTag.textContent = suspect.name;
  $dialogueText.classList.remove('typing-cursor'); $interrogationOverlay.classList.remove('screen-hidden');
  $detectiveAvatar.classList.add('screen-hidden');
  const $spPanel = document.getElementById('suspect-profile-panel');
  if ($spPanel) $spPanel.classList.add('screen-hidden');
  $qLeftVal.textContent = suspect.questions_left !== undefined ? suspect.questions_left : '--';
  if (state.gameMode === 'text') {
    $textInputContainer.classList.remove('screen-hidden'); $micBtn.classList.add('screen-hidden');
    $dialogueText.textContent = 'Type your question...';
  } else {
    $textInputContainer.classList.add('screen-hidden'); $micBtn.classList.add('screen-hidden');
    $dialogueText.textContent = 'Listening... Speak naturally.';
    setupWebSocket(); startContinuousRecording();
  }
}

function closeInterrogation() {
  stopTalking(); state.activeSuspect = null;
  $interrogationOverlay.classList.add('screen-hidden'); $detectiveAvatar.classList.remove('screen-hidden');
  if (state.interrogationSocket) { state.interrogationSocket.close(); state.interrogationSocket = null; }
  audioQueue.clear(); stopContinuousRecording();
}
$backBtn.addEventListener('click', closeInterrogation);

function startTalking() {
  if (state.isTalking) return; state.isTalking = true;
  const basePath = `./assets/characters/${$suspectCloseup.dataset.charId}`;
  state.talkInterval = setInterval(() => { const o = Math.random() > 0.4; $suspectCloseup.src = o ? `${basePath}/mouth_open.png` : `${basePath}/mouth_closed.png`; }, 120 + Math.random() * 80);
  document.getElementById('interrogation-suspect').classList.add('talking');
}

function stopTalking() {
  state.isTalking = false;
  if (state.talkInterval) { clearInterval(state.talkInterval); state.talkInterval = null; }
  if (state.activeSuspect) $suspectCloseup.src = `./assets/characters/${state.activeSuspect.id}/mouth_closed.png`;
  document.getElementById('interrogation-suspect').classList.remove('talking');
}

let interrogationTypingInterval = null;

async function submitTextInterrogation(message) {
  $dialogueText.textContent = ''; $dialogueText.classList.add('typing-cursor');
  $sendBtn.disabled = true; $interrogationTextInput.disabled = true;
  if (state.talkInterval) stopTalking();
  if (interrogationTypingInterval) { clearInterval(interrogationTypingInterval); interrogationTypingInterval = null; }
  try {
    const res = await fetch(`${API_BASE}/game/${state.case_id}/interrogate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ suspect_name: state.activeSuspect.name, message: message })
    });
    if (!res.ok) throw new Error("API Error");
    const data = await res.json();
    $dialogueText.textContent = '';
    const textToType = data.response || "No response.";
    let i = 0; startTalking();
    interrogationTypingInterval = setInterval(() => {
      if (i < textToType.length) { $dialogueText.textContent += textToType[i]; i++; }
      else {
        clearInterval(interrogationTypingInterval); interrogationTypingInterval = null;
        stopTalking(); $dialogueText.classList.remove('typing-cursor');
        $sendBtn.disabled = false; $interrogationTextInput.disabled = false; $interrogationTextInput.focus();
      }
    }, 30);
    if (typeof data.questions_remaining === 'number') { state.suspects[state.activeSuspect.index].questions_left = data.questions_remaining; $qLeftVal.textContent = data.questions_remaining; }
  } catch (err) {
    console.error("Text Interrogation Error:", err); stopTalking();
    $dialogueText.textContent = "Connection dropped. The line went dead.";
    $dialogueText.classList.remove('typing-cursor'); $sendBtn.disabled = false; $interrogationTextInput.disabled = false; $interrogationTextInput.focus();
  }
}

$sendBtn.addEventListener('click', () => {
  const text = $interrogationTextInput.value.trim();
  if (!text || state.isTalking || !state.activeSuspect) return;
  $interrogationTextInput.value = ''; submitTextInterrogation(text);
});
$interrogationTextInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') $sendBtn.click(); });

// ===== VAD / VOICE RECORDING =====
let continuousStream = null, vadAudioContext = null, vadAnalyser = null, vadMicrophone = null, vadScriptProcessor = null;
let isSpeaking = false, silenceStart = 0, maxDurationTimer = null, pcmChunks = [], preRoll = [], vadRafId = null;

function float32ToWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
  writeStr(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); writeStr(8, 'WAVE'); writeStr(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); writeStr(36, 'data');
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++) { const s = Math.max(-1, Math.min(1, samples[i])); view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true); offset += 2; }
  return new Uint8Array(buffer);
}

async function startContinuousRecording() {
  if (continuousStream) return;
  try {
    continuousStream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
    vadAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    vadAnalyser = vadAudioContext.createAnalyser(); vadAnalyser.fftSize = 512;
    vadMicrophone = vadAudioContext.createMediaStreamSource(continuousStream);
    vadMicrophone.connect(vadAnalyser);
    vadScriptProcessor = vadAudioContext.createScriptProcessor(4096, 1, 1);
    vadMicrophone.connect(vadScriptProcessor); vadScriptProcessor.connect(vadAudioContext.destination);
    pcmChunks = []; preRoll = [];
    vadScriptProcessor.onaudioprocess = (e) => {
      const chunk = new Float32Array(e.inputBuffer.getChannelData(0));
      if (!isSpeaking) { preRoll.push(chunk); if (preRoll.length > 5) preRoll.shift(); }
      else pcmChunks.push(chunk);
    };
    function sendUtterance() {
      if (pcmChunks.length === 0) return;
      if (!state.interrogationSocket || state.interrogationSocket.readyState !== WebSocket.OPEN) { pcmChunks = []; return; }
      const totalLen = pcmChunks.reduce((sum, c) => sum + c.length, 0);
      const merged = new Float32Array(totalLen); let off = 0;
      for (const chunk of pcmChunks) { merged.set(chunk, off); off += chunk.length; }
      pcmChunks = [];
      const wavBytes = float32ToWav(merged, vadAudioContext.sampleRate);
      let binary = '';
      for (let i = 0; i < wavBytes.length; i++) binary += String.fromCharCode(wavBytes[i]);
      state.interrogationSocket.send(JSON.stringify({ type: "audio", suspect_name: state.activeSuspect?.name, data: btoa(binary) }));
    }
    if (!audioCtx.muted && audioCtx.bgm) { audioCtx.bgm.volume = 0.1; audioCtx.clock.volume = 0.02; }
    const MIN_DECIBELS = -45; isSpeaking = false;
    function checkVAD() {
      if (!continuousStream) return;
      const dataArray = new Float32Array(vadAnalyser.fftSize);
      vadAnalyser.getFloatTimeDomainData(dataArray);
      let sumSq = 0;
      for (let i = 0; i < dataArray.length; i++) sumSq += dataArray[i] * dataArray[i];
      const rms = Math.sqrt(sumSq / dataArray.length);
      const decibels = rms > 0 ? 20 * Math.log10(rms) : -100;

      // Do not trigger "Hearing you" or process speech if the suspect is currently speaking
      // Wait, we DO want to trigger it if we want barge-in!
      if (decibels > MIN_DECIBELS && !state.micMuted) {
        if (!isSpeaking) {
          isSpeaking = true; pcmChunks = [...preRoll]; preRoll = [];
          if (!state.isSuspectSpeaking) {
            $dialogueText.innerHTML = '🗣️ Hearing you...';
          }
          if (maxDurationTimer) clearTimeout(maxDurationTimer);
          maxDurationTimer = setTimeout(() => {
            if (isSpeaking) {
              isSpeaking = false;
              if (!state.isSuspectSpeaking) $dialogueText.innerHTML = 'Processing your question...';
              sendUtterance();
            }
          }, 15000);
        }
        silenceStart = Date.now();
      } else {
        if (isSpeaking && Date.now() - silenceStart > 700) {
          isSpeaking = false;
          if (maxDurationTimer) clearTimeout(maxDurationTimer);
          if (!state.isSuspectSpeaking) $dialogueText.innerHTML = 'Processing your question...';
          sendUtterance();
        }
      }
      vadRafId = requestAnimationFrame(checkVAD);
    }
    checkVAD();
  } catch (e) { console.error("Mic access denied", e); $dialogueText.textContent = "Microphone access denied."; }
}

function stopContinuousRecording() {
  if (vadRafId) cancelAnimationFrame(vadRafId); vadRafId = null;
  if (maxDurationTimer) clearTimeout(maxDurationTimer); maxDurationTimer = null;
  isSpeaking = false; pcmChunks = []; preRoll = [];
  if (vadScriptProcessor) { vadScriptProcessor.disconnect(); vadScriptProcessor = null; }
  if (vadMicrophone) { vadMicrophone.disconnect(); vadMicrophone = null; }
  if (vadAnalyser) { vadAnalyser.disconnect(); vadAnalyser = null; }
  if (vadAudioContext) { vadAudioContext.close().catch(() => { }); vadAudioContext = null; }
  if (continuousStream) { continuousStream.getTracks().forEach(t => t.stop()); continuousStream = null; }
  if (!audioCtx.muted && audioCtx.bgm) { audioCtx.bgm.volume = 0.5; audioCtx.clock.volume = 0.15; }
  if (typeof $dialogueText !== 'undefined' && state.gameMode === 'voice') $dialogueText.textContent = 'Listening... Speak naturally.';
}

const $punchBtn = document.getElementById('punch-btn');
$punchBtn.addEventListener('click', async () => {
  if (!state.activeSuspect || state.isTalking) return;
  $punchBtn.style.transform = 'scale(0.9)'; setTimeout(() => $punchBtn.style.transform = 'none', 100);
  try {
    const res = await fetch(`${API_BASE}/game/${state.case_id}/punch`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ suspect_name: state.activeSuspect.name, action: 'slaps the suspect directly' })
    });
    if (res.ok) {
      $interrogationOverlay.classList.add('shake'); setTimeout(() => $interrogationOverlay.classList.remove('shake'), 400);
      const data = await res.json();
      if (interrogationTypingInterval) { clearInterval(interrogationTypingInterval); interrogationTypingInterval = null; }
      $dialogueText.textContent = ''; $dialogueText.classList.add('typing-cursor');
      $sendBtn.disabled = true; $interrogationTextInput.disabled = true;
      const textToType = data.reaction ? `[${data.reaction}]` : `[You push the suspect physically]`;
      let i = 0; startTalking();
      interrogationTypingInterval = setInterval(() => {
        if (i < textToType.length) { $dialogueText.textContent += textToType[i]; i++; }
        else { clearInterval(interrogationTypingInterval); interrogationTypingInterval = null; stopTalking(); $dialogueText.classList.remove('typing-cursor'); $sendBtn.disabled = false; $interrogationTextInput.disabled = false; }
      }, 30);
    }
  } catch (e) { console.error("Punch interaction failed", e); }
});

$micMuteBtn.addEventListener('click', () => {
  state.micMuted = !state.micMuted;
  $micMuteBtn.classList.toggle('muted', state.micMuted);
  if (state.micMuted) {
    // If they were already "speaking" when muting, cancel it
    if (isSpeaking) {
      isSpeaking = false;
      if (maxDurationTimer) clearTimeout(maxDurationTimer);
      if (!state.isSuspectSpeaking) $dialogueText.innerHTML = 'Microphone Muted';
      pcmChunks = [];
    }
  } else {
    if (!state.isSuspectSpeaking) $dialogueText.innerHTML = 'Listening... Speak naturally.';
  }
});

const $bookBriefingOverlay = document.getElementById('book-briefing-overlay');
const $bookBriefingText = document.getElementById('book-briefing-text');
const $closeBookBtn = document.getElementById('close-book-btn');

document.getElementById('briefing-book-btn').addEventListener('click', () => {
  if (state.briefingText) {
    $bookBriefingText.textContent = state.briefingText;
    $bookBriefingOverlay.classList.remove('screen-hidden');
  }
});

if ($closeBookBtn) {
  $closeBookBtn.addEventListener('click', () => {
    $bookBriefingOverlay.classList.add('screen-hidden');
  });
}

// ===== VERDICT / ACCUSATION SYSTEM =====
const $verdictBtn = document.getElementById('verdict-btn');
const $evidenceRecap = document.getElementById('evidence-recap');
const $recapSuspects = document.getElementById('recap-suspects');
const $recapBack = document.getElementById('recap-back');
const $recapTime = document.getElementById('recap-time');
const $proceedAccuseBtn = document.getElementById('proceed-accuse-btn');
const $accusationScreen = document.getElementById('accusation-screen');
const $accuseBack = document.getElementById('accuse-back');
const $accuseWho = document.getElementById('accuse-who');
const $accuseWhy = document.getElementById('accuse-why');
const $accuseHow = document.getElementById('accuse-how');
const $whyCharCount = document.getElementById('why-char-count');
const $howCharCount = document.getElementById('how-char-count');
const $submitVerdictBtn = document.getElementById('submit-verdict-btn');
const $submitVerdictText = document.getElementById('submit-verdict-text');
const $confirmModal = document.getElementById('confirm-modal');
const $confirmCancel = document.getElementById('confirm-cancel');
const $confirmSubmit = document.getElementById('confirm-submit');
const $verdictReveal = document.getElementById('verdict-reveal');   // judge loading screen
const $creditsReveal = document.getElementById('credits-reveal');   // cinematic split screen (NEW)
const $postgame = document.getElementById('postgame');              // judge scoring screen

$verdictBtn.addEventListener('click', () => openEvidenceRecap());

function openEvidenceRecap() {
  $recapTime.textContent = getFormattedTime(); $recapSuspects.innerHTML = '';
  state.suspects.forEach((suspect, i) => {
    const card = document.createElement('div'); card.className = 'recap-card';
    const bp = `./assets/characters/${suspect.id}`;
    card.innerHTML = `<div class="portrait-container"><img class="recap-card__img" src="${bp}/mouth_closed.png" alt="${suspect.name}" /></div><div class="recap-card__name">${suspect.name}</div><div class="recap-card__status">${(suspect.role || "").toUpperCase()}</div>`;
    $recapSuspects.appendChild(card);
  });
  $gameScene.classList.add('screen-hidden'); $evidenceRecap.classList.remove('screen-hidden');
}
$recapBack.addEventListener('click', () => { switchScreen($evidenceRecap, $gameScene); $gameScene.classList.remove('screen-hidden'); });
$proceedAccuseBtn.addEventListener('click', () => openAccusation());

function openAccusation() {
  $accuseWho.innerHTML = '<option value="" disabled selected>Select a suspect...</option>';
  state.suspects.forEach(s => { const opt = document.createElement('option'); opt.value = s.name; opt.textContent = s.name; $accuseWho.appendChild(opt); });
  $accuseWhy.value = ''; $accuseHow.value = '';
  $whyCharCount.textContent = '0'; $howCharCount.textContent = '0';
  $submitVerdictBtn.disabled = true; $submitVerdictText.textContent = 'SUBMIT ACCUSATION';
  switchScreen($evidenceRecap, $accusationScreen);
}

function validateAccusationForm() {
  $submitVerdictBtn.disabled = !($accuseWho.value !== '' && $accuseWhy.value.trim().length >= 10 && $accuseHow.value.trim().length >= 10);
}

$accuseWho.addEventListener('change', validateAccusationForm);
$accuseWhy.addEventListener('input', () => { $whyCharCount.textContent = $accuseWhy.value.trim().length; validateAccusationForm(); });
$accuseHow.addEventListener('input', () => { $howCharCount.textContent = $accuseHow.value.trim().length; validateAccusationForm(); });
$accuseBack.addEventListener('click', () => switchScreen($accusationScreen, $evidenceRecap));

$submitVerdictBtn.addEventListener('click', () => { if (!$submitVerdictBtn.disabled) $confirmModal.classList.remove('screen-hidden'); });
$confirmCancel.addEventListener('click', () => { $confirmModal.classList.add('screen-hidden'); });

$confirmSubmit.addEventListener('click', async () => {
  $confirmModal.classList.add('screen-hidden');
  const who = $accuseWho.value, why = $accuseWhy.value.trim(), how = $accuseHow.value.trim();
  const accusedIndex = state.suspects.findIndex(s => s.name === who);
  state.accusedSuspect = accusedIndex !== -1 ? { ...state.suspects[accusedIndex], index: accusedIndex } : { name: who, index: 0 };
  state.verdict = { accused: state.accusedSuspect, who, why, how, time: getFormattedTime() };
  $submitVerdictBtn.disabled = true; $submitVerdictText.textContent = 'SUBMITTING...';

  // STEP 1: Judge loading screen
  startVerdictLoading();

  try {
    const res = await fetch(`${API_BASE}/game/${state.case_id}/submit`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ who, why, how })
    });
    const data = await res.json();
    state.verdictData = data;
    // STEP 2: Cinematic credits reveal
    showCreditsReveal(data);
  } catch (err) {
    console.error(err);
    state.verdictData = { correct: false, score: 0, who_score: 0, why_score: 0, how_score: 0, summary: "Could not reach precinct database.", actual_culprit: "Unknown", motive: "Unknown", method: "Unknown", key_evidence: [], marking_schema: "", thinking_skills_report: "", analysis: "" };
    showCreditsReveal(state.verdictData);
  } finally {
    $submitVerdictBtn.disabled = false; $submitVerdictText.textContent = 'SUBMIT ACCUSATION';
  }
});

// ===== STEP 1: JUDGE LOADING =====
const JUDGE_FLAVOR_TEXTS = ["Analyzing evidence...", "Cross-referencing alibis...", "Reviewing interrogation transcripts...", "Evaluating motive plausibility...", "Checking forensic reports...", "The Judge is deliberating...", "Comparing your theory to the facts...", "Scoring your deduction..."];
let judgeLoadingInterval = null, judgeFlavorInterval = null;

function startVerdictLoading() {
  audioCtx.bgm.pause(); audioCtx.clock.pause();
  if (!audioCtx.muted) { audioCtx.outro.currentTime = 0; audioCtx.outro.play().catch(() => { }); }
  switchScreen($accusationScreen, $verdictReveal);
  const $fill = document.getElementById('judge-loading-fill');
  const $flavor = document.getElementById('judge-loading-flavor');
  let progress = 0, flavorIdx = 0;
  $fill.style.width = '0%'; $flavor.textContent = JUDGE_FLAVOR_TEXTS[0];
  judgeLoadingInterval = setInterval(() => { progress += Math.random() * 8 + 2; if (progress > 90) progress = 90; $fill.style.width = `${progress}%`; }, 500);
  judgeFlavorInterval = setInterval(() => { flavorIdx = (flavorIdx + 1) % JUDGE_FLAVOR_TEXTS.length; $flavor.textContent = JUDGE_FLAVOR_TEXTS[flavorIdx]; }, 2000);
}

function stopVerdictLoading() {
  if (judgeLoadingInterval) { clearInterval(judgeLoadingInterval); judgeLoadingInterval = null; }
  if (judgeFlavorInterval) { clearInterval(judgeFlavorInterval); judgeFlavorInterval = null; }
  document.getElementById('judge-loading-fill').style.width = '100%';
}

// ===== STEP 2: CINEMATIC CREDITS REVEAL =====
function showCreditsReveal(data) {
  stopVerdictLoading();
  if (state.timerInterval) { clearInterval(state.timerInterval); state.timerInterval = null; }

  let actualCulpritIndex = state.suspects.findIndex(s => s.name === data.actual_culprit);
  if (actualCulpritIndex === -1) actualCulpritIndex = 0;
  state.guiltyIndex = actualCulpritIndex;

  const isCorrect = data.correct !== undefined ? data.correct : (data.who_score === 25);
  const guiltyName = state.suspects[state.guiltyIndex].name;
  const accusedName = state.accusedSuspect.name;
  // Safety: if names match, always treat as correct to avoid nonsense copy
  const finalIsCorrect = (guiltyName === accusedName) ? true : isCorrect;

  switchScreen($verdictReveal, $creditsReveal);

  // Get elements inside credits-reveal
  const $stamp = document.getElementById('credits-verdict-stamp');
  const $verdictTxt = document.getElementById('credits-verdict-text');
  const $suspectReveal = document.getElementById('credits-suspect-reveal');
  const $continueBtn = document.getElementById('credits-continue-btn');
  const $cs = document.getElementById('credits-scroll');
  const $cp = document.querySelector('#credits-reveal .credits-panel');

  // Reset
  $stamp.className = 'verdict-stamp';
  $verdictTxt.textContent = '';
  $suspectReveal.innerHTML = '';
  $continueBtn.classList.add('screen-hidden');
  $continueBtn.classList.remove('show');
  $cs.classList.remove('rolling');
  $cs.innerHTML = '';

  // Stamp + text
  setTimeout(() => {
    if (finalIsCorrect) {
      $stamp.textContent = 'GUILTY'; $stamp.classList.add('guilty');
      setTimeout(() => { $verdictTxt.textContent = `Your deduction was correct, Detective. ${guiltyName} has been found guilty. Justice has been served.`; buildCreditsSuspect($suspectReveal, state.guiltyIndex, true); }, 600);
    } else {
      $stamp.textContent = 'NOT GUILTY'; $stamp.classList.add('not-guilty');
      setTimeout(() => { $verdictTxt.textContent = `You accused ${accusedName}, but the evidence points to ${guiltyName}. The real killer walks free.`; buildCreditsSuspect($suspectReveal, state.guiltyIndex, false); }, 600);
    }
    buildAndRollCredits($cs, $cp, isCorrect, guiltyName, accusedName);
    setTimeout(() => { $continueBtn.classList.remove('screen-hidden'); $continueBtn.classList.add('show'); }, 2500);
  }, 400);
}

function buildCreditsSuspect($container, index, wasCorrect) {
  const s = state.suspects[index]; const bp = `./assets/characters/${s.id}`;
  $container.innerHTML = `<div class="verdict-character-reveal"><div class="verdict-character-img-wrap ${wasCorrect ? 'convicted' : 'escaped'}"><img src="${bp}/mouth_closed.png" alt="${s.name}" class="verdict-character-img" /><div class="verdict-character-glow ${wasCorrect ? 'glow-red' : 'glow-gray'}"></div></div><div class="verdict-character-info"><div class="verdict-character-name">${s.name}</div><div class="verdict-character-status ${wasCorrect ? 'status-convicted' : 'status-escaped'}">${wasCorrect ? '✓ CONVICTED' : '✗ TRUE CULPRIT — ESCAPED'}</div></div></div>`;
}

// ===== buildAndRollCredits — FULLY RESTORED =====
function buildAndRollCredits($cs, $cp, isCorrect, guiltyName, accusedName) {
  const caseTitle = state.caseTitle || 'CASE #----';
  const items = [
    { type: 'film-title', title: 'AI DETECTIVE', subtitle: `${caseTitle} — ${isCorrect ? 'SOLVED' : 'UNSOLVED'}` },
    { type: 'block', role: 'Developed by', name: 'REHAAN', highlight: true },
    { type: 'separator' },
    { type: 'block', role: 'Written by', name: 'DEEPSEEK R1' },
    { type: 'block', role: 'Directed by', name: 'LLAMA 70B', subname: 'VERSATILE' },
    { type: 'separator' },
    { type: 'block', role: 'Cast', name: 'LLAMA 8B' },
    { type: 'block', role: 'Interrogated by', name: 'YOU' },
    { type: 'separator' },
    { type: 'block', role: 'The Accused', name: accusedName.toUpperCase() },
    { type: 'block', role: 'The Real Culprit', name: guiltyName.toUpperCase(), highlight: !isCorrect },
    { type: 'separator' },
    { type: 'block', role: 'Voice Recognition', name: 'GROQ', subname: 'WHISPER' },
    { type: 'block', role: 'Intelligence by', name: 'ANTHROPIC' },
    { type: 'separator' },
    { type: 'block', role: 'Difficulty', name: (state.difficulty || 'MEDIUM').toUpperCase() },
    { type: 'block', role: 'Time on Case', name: getFormattedTime() },
    { type: 'block', role: 'Mode', name: (state.gameMode || 'TEXT').toUpperCase() },
    { type: 'separator' },
    { type: 'end-card', lines: ['No suspects were harmed in the making of this game.', 'All characters, crimes, and cases are entirely fictional.', 'Any resemblance to actual criminals is purely coincidental.'], big: isCorrect ? 'JUSTICE HAS BEEN SERVED.' : 'BETTER LUCK NEXT TIME, DETECTIVE.' },
  ];

  let html = '';
  items.forEach(item => {
    if (item.type === 'film-title') html += `<div class="credit-film-title">${item.title}</div><div class="credit-film-subtitle">${item.subtitle}</div>`;
    else if (item.type === 'separator') html += '<div class="credit-separator"></div>';
    else if (item.type === 'block') html += `<div class="credit-block"><div class="credit-role">${item.role}</div><div class="credit-name${item.highlight ? ' highlight' : ''}">${item.name}</div>${item.subname ? `<div class="credit-subname">${item.subname}</div>` : ''}</div>`;
    else if (item.type === 'end-card') html += `<div class="credit-end-card">${item.lines.map(l => `<div class="credit-end-line">${l}</div>`).join('')}<div style="height:1rem;"></div><div class="credit-end-big">${item.big}</div></div>`;
  });
  html += '<div style="height:60vh;"></div>';
  $cs.innerHTML = html;

  requestAnimationFrame(() => {
    void $cs.offsetHeight;
    const ph = $cp.offsetHeight;
    const td = $cs.scrollHeight + ph;
    const dur = Math.max(50, Math.round(td / 28));
    $cs.style.setProperty('--roll-distance', `-${td}px`);
    $cs.style.setProperty('--roll-duration', `${dur}s`);
    setTimeout(() => $cs.classList.add('rolling'), 200);
  });
}

// ===== STEP 3: VIEW CASE REPORT BUTTON → JUDGE VERDICT =====
document.getElementById('credits-continue-btn').addEventListener('click', () => {
  showJudgeVerdict(state.verdictData);
});

function showJudgeVerdict(data) {
  switchScreen($creditsReveal, $postgame);
  const whoScore = data.who_score || 0;
  const whyScore = data.why_score || 0;
  const howScore = data.how_score || 0;
  const rawScore = typeof data.score === 'number' ? data.score : (whoScore + whyScore + howScore);
  // If backend sends 0 but subscores are non‑zero, trust the breakdown
  const safeScore = (rawScore === 0 && (whoScore > 0 || whyScore > 0 || howScore > 0))
    ? (whoScore + whyScore + howScore)
    : rawScore;
  const isCorrect = data.correct !== undefined ? data.correct : (whoScore === 25);
  renderJudgeVerdict(data, safeScore, whoScore, whyScore, howScore, isCorrect);
}

function renderJudgeVerdict(data, score, whoScore, whyScore, howScore, isCorrect) {
  const $banner = document.getElementById('jv-banner');
  const $bannerTitle = document.getElementById('jv-banner-title');
  const $bannerSubtitle = document.getElementById('jv-banner-subtitle');
  $banner.className = 'jv-banner';
  if (whoScore === 0) { $banner.classList.add('jv-theme-failed'); $bannerTitle.textContent = '❌ CASE FAILED'; $bannerSubtitle.textContent = 'You accused the wrong person.'; }
  else if (score < 50) { $banner.classList.add('jv-theme-partial'); $bannerTitle.textContent = '⚖️ JUDGE\'S VERDICT'; $bannerSubtitle.textContent = 'Partial deduction. You\'re on the right track but missed critical details.'; }
  else if (score < 80) { $banner.classList.add('jv-theme-solid'); $bannerTitle.textContent = '⚖️ JUDGE\'S VERDICT'; $bannerSubtitle.textContent = 'Solid detective work, but room for improvement.'; }
  else { $banner.classList.add('jv-theme-excellent'); $bannerTitle.textContent = '🏆 JUDGE\'S VERDICT'; $bannerSubtitle.textContent = 'Exceptional deduction! You cracked the case.'; }

  document.getElementById('jv-total-score').textContent = score;
  const $pf = document.getElementById('jv-progress-fill');
  $pf.style.width = '0%';
  if (whoScore === 0) $pf.className = 'jv-progress-bar__fill jv-bar-failed';
  else if (score < 50) $pf.className = 'jv-progress-bar__fill jv-bar-partial';
  else if (score < 80) $pf.className = 'jv-progress-bar__fill jv-bar-solid';
  else $pf.className = 'jv-progress-bar__fill jv-bar-excellent';
  setTimeout(() => { $pf.style.width = `${score}%`; }, 300);

  const $zs = document.getElementById('jv-zero-sum');
  if (whoScore === 0 && (whyScore > 0 || howScore > 0)) $zs.classList.remove('screen-hidden');
  else $zs.classList.add('screen-hidden');

  renderSubScoreCard('jv-who-card', 'jv-who-score', 'jv-who-icon', whoScore, 25);
  renderSubScoreCard('jv-why-card', 'jv-why-score', 'jv-why-icon', whyScore, 50);
  renderSubScoreCard('jv-how-card', 'jv-how-score', 'jv-how-icon', howScore, 25);

  const $marking = document.getElementById('jv-marking');
  if (data.marking_schema) {
    $marking.innerHTML = data.marking_schema.split('|').map(s => s.trim()).filter(Boolean).map(item => `<div class="jv-marking-item">${item}</div>`).join('');
  } else { $marking.innerHTML = '<div class="jv-marking-item">No marking data available.</div>'; }

  const critiqueText = data.thinking_skills_report || data.critique || data.summary || 'No investigation critique available.';
  const analysisText = data.analysis || data.full_report || data.raw_report || 'No detailed judge report available.';

  const $downloadBtn = document.getElementById('download-report-btn');
  if ($downloadBtn) {
    $downloadBtn.onclick = () => {
      generatePDFReport(critiqueText, analysisText, score, isCorrect);
    };
  }

  document.getElementById('jv-truth-culprit').textContent = data.actual_culprit || '—';
  document.getElementById('jv-truth-motive').textContent = data.motive || '—';
  document.getElementById('jv-truth-method').textContent = data.method || '—';
  const ev = data.key_evidence || [];
  document.getElementById('jv-truth-evidence').textContent = ev.length > 0 ? ev.join(', ') : '—';
  const miniMotive = document.getElementById('jv-mini-motive');
  const miniEvidence = document.getElementById('jv-mini-evidence');
  if (miniMotive) miniMotive.textContent = data.motive || '—';
  if (miniEvidence) miniEvidence.textContent = ev.length > 0 ? ev.join(' • ') : '—';
}

function renderSubScoreCard(cardId, scoreId, iconId, score, max) {
  const $card = document.getElementById(cardId);
  const $score = document.getElementById(scoreId);
  const $icon = document.getElementById(iconId);
  $score.textContent = score; $card.className = 'jv-subscore-card';
  const ratio = score / max;
  if (cardId === 'jv-who-card') {
    if (score === 25) { $icon.textContent = '✅'; $card.classList.add('jv-card-green'); }
    else { $icon.textContent = '❌'; $card.classList.add('jv-card-red'); }
  } else if (max === 50) {
    if (ratio >= 0.7) { $icon.textContent = '✅'; $card.classList.add('jv-card-green'); }
    else if (ratio >= 0.4) { $icon.textContent = '⚠️'; $card.classList.add('jv-card-yellow'); }
    else { $icon.textContent = '❌'; $card.classList.add('jv-card-red'); }
  } else {
    if (ratio >= 0.8) { $icon.textContent = '✅'; $card.classList.add('jv-card-green'); }
    else if (ratio >= 0.5) { $icon.textContent = '⚠️'; $card.classList.add('jv-card-yellow'); }
    else { $icon.textContent = '❌'; $card.classList.add('jv-card-red'); }
  }
}

function generatePDFReport(critique, analysis, score, isCorrect) {
  const container = document.createElement('div');
  container.style.padding = '40px';
  container.style.fontFamily = "'Inter', sans-serif";
  container.style.color = '#333';
  container.style.backgroundColor = '#fdfbf7';
  container.style.boxSizing = 'border-box';

  const header = document.createElement('div');
  header.style.textAlign = 'center';
  header.style.borderBottom = '3px solid #b89c62';
  header.style.paddingBottom = '20px';
  header.style.marginBottom = '30px';
  header.innerHTML = `
    <h1 style="font-family: 'Bebas Neue', sans-serif; font-size: 48px; margin: 0; color: #1a1a1a;">AI DETECTIVE</h1>
    <h2 style="font-family: 'Inter', sans-serif; font-size: 20px; font-weight: 600; color: #b89c62; letter-spacing: 4px; margin: 10px 0 0 0;">OFFICIAL CASE REPORT</h2>
    <p style="margin: 10px 0 0 0; font-family: 'JetBrains Mono', monospace; font-size: 14px; color: #666;">CASE #${state.case_id || 'UNKNOWN'} • SCORE: ${score}/100 • VERDICT: ${isCorrect ? 'GUILTY / SOLVED' : 'NOT GUILTY / FAILED'}</p>
  `;
  container.appendChild(header);

  const thinkingSection = document.createElement('div');
  thinkingSection.style.marginBottom = '30px';
  thinkingSection.innerHTML = `
    <h3 style="font-family: 'Bebas Neue', sans-serif; font-size: 28px; color: #2c3e50; border-left: 5px solid #e74c3c; padding-left: 15px; margin-bottom: 15px;">THINKING SKILLS REPORT</h3>
    <p style="font-size: 16px; line-height: 1.6; color: #444; background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; white-space: pre-wrap;">${critique}</p>
  `;
  container.appendChild(thinkingSection);

  const analysisSection = document.createElement('div');
  analysisSection.innerHTML = `
    <h3 style="font-family: 'Bebas Neue', sans-serif; font-size: 28px; color: #2c3e50; border-left: 5px solid #3498db; padding-left: 15px; margin-bottom: 15px;">DETAILED ANALYSIS</h3>
    <p style="font-size: 16px; line-height: 1.6; color: #444; background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee; white-space: pre-wrap;">${analysis}</p>
  `;
  container.appendChild(analysisSection);

  const footer = document.createElement('div');
  footer.style.marginTop = '40px';
  footer.style.textAlign = 'center';
  footer.style.borderTop = '1px solid #ccc';
  footer.style.paddingTop = '20px';
  footer.innerHTML = `
    <p style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #888;">CONFIDENTIAL — FOR INTERNAL PRECINCT USE ONLY</p>
  `;
  container.appendChild(footer);

  document.body.appendChild(container);

  const opt = {
    margin: [0.5, 0.5, 0.5, 0.5],
    filename: `Case_Report_${state.case_id || 'Unknown'}.pdf`,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true },
    jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
  };

  const btn = document.getElementById('download-report-btn');
  const originalText = btn.innerHTML;
  btn.innerHTML = '<span class="neon-btn__text">⏳ GENERATING PDF...</span><span class="neon-btn__glow"></span><span class="neon-btn__border"></span>';
  btn.style.pointerEvents = 'none';

  html2pdf().set(opt).from(container).save().then(() => {
    document.body.removeChild(container);
    btn.innerHTML = originalText;
    btn.style.pointerEvents = 'auto';
  }).catch(err => {
    console.error("PDF Generation error", err);
    document.body.removeChild(container);
    btn.innerHTML = originalText;
    btn.style.pointerEvents = 'auto';
    alert("Failed to generate PDF.");
  });
}

document.getElementById('play-again-btn').addEventListener('click', () => {
  audioCtx.outro.pause(); audioCtx.outro.currentTime = 0;
  if (landingMusicStarted && !audioCtx.muted) { audioCtx.landing.currentTime = 0; audioCtx.landing.play().catch(() => { }); }
  stopBriefingAudio();
  state.suspects = []; state.activeSuspect = null; state.accusedSuspect = null; state.guiltyIndex = null;
  state.elapsedSeconds = 0; state.introSkipped = false; state.gameMode = null; state.difficulty = null; state.language = 'en'; state.verdictData = null;
  $hudTimer.textContent = '⏱ 00:00'; $introText.textContent = ''; $introProgressBar.style.width = '0%';
  $introStamp.classList.remove('stamp-active'); $redacted1.classList.remove('revealed');
  if ($introCursor) $introCursor.classList.remove('hidden');
  $beginBtn.classList.add('screen-hidden'); $beginBtn.classList.remove('show');
  switchScreen($postgame, $landing);
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (state.activeSuspect) closeInterrogation();
    else if ($detectiveOverlay && !$detectiveOverlay.classList.contains('screen-hidden')) closeDetectiveOverlay();
    else if ($confirmModal && !$confirmModal.classList.contains('screen-hidden')) $confirmModal.classList.add('screen-hidden');
    else if (document.getElementById('suspect-profile-panel') && !document.getElementById('suspect-profile-panel').classList.contains('screen-hidden')) closeSuspectProfile();
  }
});
console.log('🕵️ AI Detective loaded. Good luck, detective.');

// ===== DETECTIVE PARTNER OVERLAY =====
const $detectiveAvatar = document.querySelector('.detective-avatar');
const $detectiveImg = document.getElementById('detective-img');
const $detectiveOverlay = document.getElementById('detective-overlay');
const $detectiveBackBtn = document.getElementById('detective-back-btn');
const $detectiveOverlayImg = document.getElementById('detective-overlay-img');
const $detectiveCharWrap = document.getElementById('detective-char-wrap');
const $detectiveHintText = document.getElementById('detective-hint-text');
const $detectiveAskBtn = document.getElementById('detective-ask-btn');
const $partnerSuspects = document.getElementById('partner-suspects');
const $partnerTime = document.getElementById('partner-time');
const $partnerDiff = document.getElementById('partner-diff');
const $partnerMode = document.getElementById('partner-mode');
let detectiveTalkInterval = null, partnerTimeInterval = null;

const PARTNER_HINTS = [
  "I've been watching them carefully. One keeps avoiding eye contact whenever the victim's name comes up.",
  "Check the timeline again — someone's alibi doesn't add up. The math isn't right.",
  "One suspect is way too calm for this situation. Guilt? Or just good nerves?",
  "Body language tells a story. Watch how they hold themselves when you press on motive.",
  "Someone here knew the hotel layout. That narrows it down more than you'd think.",
  "Liars get the big stuff right but slip on the little things. Dig into the details.",
  "The most cooperative suspect isn't always the innocent one. I've seen it before.",
  "Follow the money, Detective. Always follow the money.",
  "Someone in that lineup had access to the penthouse. That's your starting point.",
  "Trust your gut. You've been doing this long enough to know when something's off.",
];

function setDetectiveOverlaySpeaking(on) {
  if (!$detectiveCharWrap || !$detectiveOverlayImg) return;
  if (on) {
    $detectiveCharWrap.classList.add('talking');
    if (!detectiveTalkInterval) detectiveTalkInterval = setInterval(() => { $detectiveOverlayImg.src = Math.random() > 0.4 ? './assets/characters/detective/mouth_open.png' : './assets/characters/detective/mouth_closed.png'; }, 130);
  } else {
    $detectiveCharWrap.classList.remove('talking');
    if (detectiveTalkInterval) { clearInterval(detectiveTalkInterval); detectiveTalkInterval = null; }
    $detectiveOverlayImg.src = './assets/characters/detective/mouth_closed.png';
  }
}

window.setDetectiveSpeaking = function (on) {
  setDetectiveOverlaySpeaking(on);
  if (!$detectiveImg) return;
  if (on) { if (!detectiveTalkInterval) detectiveTalkInterval = setInterval(() => { $detectiveImg.src = Math.random() > 0.4 ? './assets/characters/detective/mouth_open.png' : './assets/characters/detective/mouth_closed.png'; }, 150); }
  else { if (detectiveTalkInterval) { clearInterval(detectiveTalkInterval); detectiveTalkInterval = null; } $detectiveImg.src = './assets/characters/detective/mouth_closed.png'; }
};

function typeHint(text) {
  $detectiveHintText.textContent = ''; $detectiveHintText.classList.add('typing'); setDetectiveOverlaySpeaking(true);
  let i = 0; const t = setInterval(() => { if (i < text.length) { $detectiveHintText.textContent += text[i]; i++; } else { clearInterval(t); $detectiveHintText.classList.remove('typing'); setDetectiveOverlaySpeaking(false); } }, 28);
}

function openDetectiveOverlay() {
  $partnerSuspects.textContent = state.suspects.length || '—';
  $partnerDiff.textContent = (state.difficulty || '—').toUpperCase();
  $partnerMode.textContent = (state.gameMode || '—').toUpperCase();
  $partnerTime.textContent = getFormattedTime();
  partnerTimeInterval = setInterval(() => { $partnerTime.textContent = getFormattedTime(); }, 1000);
  $detectiveHintText.textContent = 'Your partner is observing the lineup...'; $detectiveHintText.classList.remove('typing');
  setDetectiveOverlaySpeaking(false); $detectiveOverlayImg.src = './assets/characters/detective/mouth_closed.png';
  $detectiveOverlay.classList.remove('screen-hidden');
  setTimeout(() => { typeHint(PARTNER_HINTS[Math.floor(Math.random() * PARTNER_HINTS.length)]); }, 800);
}

function closeDetectiveOverlay() {
  setDetectiveOverlaySpeaking(false);
  if (partnerTimeInterval) { clearInterval(partnerTimeInterval); partnerTimeInterval = null; }
  $detectiveOverlay.classList.add('screen-hidden');
}

$detectiveAvatar.addEventListener('click', () => { if (!$detectiveOverlay.classList.contains('screen-hidden')) return; openDetectiveOverlay(); });
$detectiveBackBtn.addEventListener('click', closeDetectiveOverlay);

let partnerTypingInterval = null;
$partnerSendBtn.addEventListener('click', async () => {
  const task = $partnerTextInput.value.trim();
  if (!task || !state.case_id) return;
  $partnerTextInput.value = ''; $partnerSendBtn.disabled = true; $partnerTextInput.disabled = true;
  $detectiveHintText.textContent = ''; $detectiveHintText.classList.add('typing'); setDetectiveOverlaySpeaking(false);
  if (partnerTypingInterval) { clearInterval(partnerTypingInterval); partnerTypingInterval = null; }
  try {
    const res = await fetch(`${API_BASE}/game/${state.case_id}/task`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: task })
    });
    if (!res.ok) throw new Error("API Error");
    const data = await res.json();
    $detectiveHintText.textContent = '';
    const textToType = data.result || "No response.";
    let i = 0; setDetectiveOverlaySpeaking(true);
    partnerTypingInterval = setInterval(() => {
      if (i < textToType.length) { $detectiveHintText.textContent += textToType[i]; i++; }
      else { clearInterval(partnerTypingInterval); partnerTypingInterval = null; $detectiveHintText.classList.remove('typing'); setDetectiveOverlaySpeaking(false); $partnerSendBtn.disabled = false; $partnerTextInput.disabled = false; $partnerTextInput.focus(); }
    }, 30);
  } catch (err) {
    console.error("Partner Task Error:", err); $detectiveHintText.classList.remove('typing'); setDetectiveOverlaySpeaking(false);
    $detectiveHintText.textContent = "Connection dropped. The line went dead.";
    $partnerSendBtn.disabled = false; $partnerTextInput.disabled = false;
  }
});
$partnerTextInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') $partnerSendBtn.click(); });
$detectiveAskBtn.addEventListener('click', () => {
  $partnerTextContainer.classList.toggle('screen-hidden');
  if (!$partnerTextContainer.classList.contains('screen-hidden')) $partnerTextInput.focus();
});

// --- Intimidation Interactions ---
document.querySelectorAll('.desk-item:not(.evidence-btn)').forEach(item => {
  item.addEventListener('click', async () => {
    if (!state.activeSuspect || state.isTalking) return;
    item.style.transform = 'scale(0.9)'; setTimeout(() => item.style.transform = 'none', 100);
    try {
      const res = await fetch(`${API_BASE}/game/${state.case_id}/punch`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suspect_name: state.activeSuspect.name, action: `interacts with ${item.classList[1]}` })
      });
      if (res.ok) {
        $interrogationOverlay.classList.add('shake'); setTimeout(() => $interrogationOverlay.classList.remove('shake'), 400);
        const data = await res.json();
        $dialogueText.textContent = data.reaction ? `[${data.reaction}]` : `[You hit the desk]`;
      }
    } catch (e) { }
  });
});

// ===== SUSPECT PROFILE PANEL =====
const $suspectProfileToggle = document.getElementById('suspect-profile-toggle');
const $suspectProfilePanel = document.getElementById('suspect-profile-panel');
const $suspectProfileClose = document.getElementById('suspect-profile-close');
const $profileName = document.getElementById('profile-name');
const $profileDetails = document.getElementById('profile-details');

function openSuspectProfile() {
  if (!state.activeSuspect) return;
  const suspect = state.activeSuspect;
  $profileName.textContent = suspect.name || '—';
  let detailsHtml = '';
  [{ label: 'Age', key: 'age' }, { label: 'Role', key: 'role' }, { label: 'Occupation', key: 'occupation' }, { label: 'Relationship', key: 'relationship' }, { label: 'Background', key: 'background' }, { label: 'Personality', key: 'personality' }, { label: 'Alibi', key: 'alibi' }, { label: 'Suspicious Behaviour', key: 'suspicious_behavior' }].forEach(f => {
    const val = suspect[f.key];
    if (val) detailsHtml += `<div class="suspect-profile__field"><span class="suspect-profile__field-label">${f.label}</span><span class="suspect-profile__field-value">${val}</span></div>`;
  });
  if (!detailsHtml) detailsHtml = '<div class="suspect-profile__field"><span class="suspect-profile__field-value">No profile data available.</span></div>';
  $profileDetails.innerHTML = detailsHtml;
  $suspectProfilePanel.classList.remove('screen-hidden');
}

function closeSuspectProfile() { $suspectProfilePanel.classList.add('screen-hidden'); }
if ($suspectProfileToggle) $suspectProfileToggle.addEventListener('click', openSuspectProfile);
if ($suspectProfileClose) $suspectProfileClose.addEventListener('click', closeSuspectProfile);

// ===== DYNAMIC TEXTAREA RESIZING =====
function autoResizeTextarea(ta) { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; }
if ($interrogationTextInput) $interrogationTextInput.addEventListener('input', () => autoResizeTextarea($interrogationTextInput));
if ($partnerTextInput) $partnerTextInput.addEventListener('input', () => autoResizeTextarea($partnerTextInput));
if ($accuseWhy) $accuseWhy.addEventListener('input', () => autoResizeTextarea($accuseWhy));
if ($accuseHow) $accuseHow.addEventListener('input', () => autoResizeTextarea($accuseHow));