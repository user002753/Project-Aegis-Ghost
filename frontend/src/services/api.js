/**
 * Project Aegis Ghost - API Service
 * Endpoints aligned with current FastAPI backend.
 */
import { API_BASE_URL } from '../config';

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, options);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export const authAPI = {
  login: (credentials) =>
    request('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    }),

  register: (payload) =>
    request('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  forgotPassword: (email) =>
    request('/api/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }),

  resetPassword: (email, otp, new_password) =>
    request('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp, new_password }),
    }),

  smtpTest: (email) =>
    request('/api/auth/smtp-test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email || '' }),
    }),

  logout: () => request('/api/auth/logout', { method: 'POST' }),
};

export const encryptionAPI = {
  encrypt: (text, n_shares = 10, threshold = 6) =>
    request('/api/crypto/encrypt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, n_shares, threshold }),
    }),

  decrypt: (ciphertext, shares, nonce, tag) =>
    request('/api/crypto/decrypt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ciphertext, shares, nonce, tag }),
    }),
};

export const steganographyAPI = {
  hide: (imageFile, secretText) => {
    const form = new FormData();
    form.append('image', imageFile);
    form.append('secret_text', secretText);
    return request('/api/ai/hide', { method: 'POST', body: form });
  },

  reveal: (stegoImageFile, numBytes, password = '') => {
    const form = new FormData();
    form.append('stego_image', stegoImageFile);
    form.append('num_bytes', String(numBytes));
    if (password) {
      form.append('password', password);
    }
    return request('/api/ai/reveal', { method: 'POST', body: form });
  },

  analyze: (imageFile) => {
    const form = new FormData();
    form.append('image', imageFile);
    return request('/api/stego/analyze', { method: 'POST', body: form });
  },
};

export const aiAPI = {
  providers: () => request('/api/ai/providers'),
  capabilities: () => request('/api/ai/capabilities'),
  recommendPrompts: (theme, n_prompts = 10) =>
    request('/api/ai/recommend-prompts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme, n_prompts }),
    }),
};

export const healthCheck = () => request('/api/status');

export default {
  auth: authAPI,
  encryption: encryptionAPI,
  steganography: steganographyAPI,
  ai: aiAPI,
  health: healthCheck,
};

