// ---------------------------------------------------------------------------
// API-key gate: blocks the whole app behind a modal asking for the
// visitor's own Groq API key + model, so the deployed site never ships with
// a key baked into the server. Validated against /api/validate_key before
// the modal is dismissed. The key/model are kept in localStorage (this
// browser only) and read by app.js via getApiConfig() on every request.
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'genori_groq_api_key';
const STORAGE_MODEL = 'genori_groq_model';
const DEFAULT_MODEL = 'openai/gpt-oss-120b';

const appRoot = document.getElementById('appRoot');
const modal = document.getElementById('apiKeyModal');
const keyInput = document.getElementById('apiKeyInput');
const modelInput = document.getElementById('apiModelInput');
const enterBtn = document.getElementById('apiKeyEnterBtn');
const statusEl = document.getElementById('apiKeyStatus');

export function getApiConfig() {
  return {
    apiKey: localStorage.getItem(STORAGE_KEY) || '',
    model: localStorage.getItem(STORAGE_MODEL) || DEFAULT_MODEL,
  };
}

// Called by app.js if a request comes back with an auth-shaped error, so a
// revoked/typo'd key doesn't just spin forever -- it re-opens the gate.
export function invalidateApiConfig(message) {
  localStorage.removeItem(STORAGE_KEY);
  openModal(message || 'Your API key was rejected. Please re-enter it.');
}

function lockApp() {
  appRoot.classList.add('app-blurred');
  appRoot.setAttribute('aria-hidden', 'true');
}

function unlockApp() {
  appRoot.classList.remove('app-blurred');
  appRoot.removeAttribute('aria-hidden');
}

function openModal(message) {
  lockApp();
  modal.classList.add('visible');
  setStatus(message || '', message ? 'error' : '');
  setTimeout(() => keyInput.focus(), 0);
}

function closeModal() {
  modal.classList.remove('visible');
  unlockApp();
}

function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = 'api-key-status' + (kind ? ` ${kind}` : '');
}

function setBusy(busy) {
  enterBtn.disabled = busy;
  keyInput.disabled = busy;
  modelInput.disabled = busy;
  enterBtn.textContent = busy ? 'Checking...' : 'Enter';
}

async function handleEnter() {
  const apiKey = keyInput.value.trim();
  const model = modelInput.value.trim() || DEFAULT_MODEL;

  if (!apiKey) {
    setStatus('Please enter your API key.', 'error');
    keyInput.focus();
    return;
  }

  setBusy(true);
  setStatus('Validating key...', '');

  try {
    const res = await fetch('/api/validate_key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey, model }),
    });
    const data = await res.json();

    if (data.valid) {
      localStorage.setItem(STORAGE_KEY, apiKey);
      localStorage.setItem(STORAGE_MODEL, model);
      closeModal();
    } else {
      setStatus(data.error ? `Invalid key: ${data.error}` : 'That key did not work. Please check it and try again.', 'error');
    }
  } catch (err) {
    setStatus(`Could not reach the server: ${err.message}`, 'error');
  } finally {
    setBusy(false);
  }
}

enterBtn.addEventListener('click', handleEnter);
keyInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleEnter();
});
modelInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') handleEnter();
});

// ---------------------------------------------------------------------------
// Init: lock immediately, only unlock if a stored key is already present.
// (We don't re-validate a stored key on every page load -- app.js falls
// back to invalidateApiConfig() if it turns out to be stale.)
// ---------------------------------------------------------------------------
lockApp();
const existing = getApiConfig();
if (existing.apiKey) {
  modelInput.value = existing.model;
  closeModal();
} else {
  modelInput.value = DEFAULT_MODEL;
  openModal();
}
