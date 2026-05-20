import React, { useState } from 'react';
import { API_BASE_URL } from '../../config';
import './ShamirStego.css';

function ShamirStego() {
  const [secret, setSecret] = useState('');
  const [password, setPassword] = useState('');
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [revealedSecret, setRevealedSecret] = useState('');
  const [revealLoading, setRevealLoading] = useState(false);

  const [selectedModel, setSelectedModel] = useState('openai');
  const [customPrompt, setCustomPrompt] = useState('');
  const [selectedPromptIndex, setSelectedPromptIndex] = useState(0);
  const [numShares, setNumShares] = useState(10);
  const [threshold, setThreshold] = useState(6);

  const ICONS = {
    lock: '\u{1F512}',
    closedLock: '\u{1F510}',
    key: '\u{1F511}',
    number: '\u{1F522}',
    edit: '\u270F\uFE0F',
    robot: '\u{1F916}',
    brush: '\u{1F3A8}',
    rocket: '\u{1F680}',
    warning: '\u26A0\uFE0F',
    check: '\u2705',
    cross: '\u274C',
    folder: '\u{1F5C2}\uFE0F',
    down: '\u2B07\uFE0F',
    search: '\u{1F50D}',
    bolt: '\u26A1',
  };

  const aiModels = [
    { id: 'mock', name: `${ICONS.bolt} Instant Mock`, description: 'Fast - generates placeholders instantly' },
    { id: 'pollinations', name: `${ICONS.brush} Pollinations AI (Flux)`, description: 'Free AI - default model' },
    { id: 'pollinations-schnell', name: `${ICONS.bolt} Pollinations Turbo`, description: 'Fast generation - free' },
    { id: 'pexels', name: 'Pexels', description: 'Pexels photo API - requires API key' },
    { id: 'pollinations-realism', name: '\u{1F4F7} Pollinations Realism', description: 'Realistic photos - free' },
    { id: 'puter', name: 'Puter', description: 'Puter image API - requires API key' },
    { id: 'raphael', name: 'Raphael AI', description: 'Raphael API - requires API key' },
    { id: 'leonardo', name: 'Leonardo AI', description: 'Leonardo API - requires API key' },
    { id: 'genai', name: '\u{1F539} Google GenAI', description: 'Google Gemini - requires API key' },
    { id: 'openai', name: '\u{1F4AC} OpenAI', description: 'OpenAI DALL-E - requires API key' },
    { id: 'hf', name: '\u{1F984} Hugging Face', description: 'HF Inference - requires API key' },
    { id: 'replicate', name: '\u2699\uFE0F Replicate', description: 'Replicate API - requires API key' },
  ];

  const promptOptions = [
    { id: 1, title: '\u{1F306} Cyberpunk City', prompt: 'Futuristic cityscape with neon lights, dark atmosphere, cyberpunk' },
    { id: 2, title: '\u2302 Digital Matrix', prompt: 'Digital matrix code, green and black, tech theme' },
    { id: 3, title: '\u{1F30C} Cosmic Nebula', prompt: 'Cosmic nebula with stars, purple and blue, space theme' },
    { id: 4, title: '\u{1F30A} Underwater', prompt: 'Underwater scene with coral, blue and teal colors' },
    { id: 5, title: '\u{1F3DC}\uFE0F Desert Sunset', prompt: 'Desert landscape at sunset, orange and red tones' },
    { id: 6, title: '\u2744\uFE0F Snowy Mountain', prompt: 'Snowy mountain peak, white and blue winter theme' },
    { id: 7, title: '\u{1F332} Mystical Forest', prompt: 'Forest with mystical fog, green and gray nature' },
    { id: 8, title: '\u{1F30B} Volcanic Eruption', prompt: 'Volcanic eruption, red and orange fire theme' },
    { id: 9, title: '\u{1F6D5}\uFE0F Ancient Temple', prompt: 'Ancient temple ruins, mysterious stone architecture' },
    { id: 10, title: '\u{1F4AB} Abstract Geometric', prompt: 'Abstract geometric patterns with hidden data, dark theme, cyberpunk' },
  ];

  const handleCreate = async () => {
    if (!secret.trim()) {
      setError('Please enter a secret message');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setImages([]);
    setProgress(0);

    const prompt = customPrompt.trim() || promptOptions[selectedPromptIndex].prompt;

    try {
      const progressInterval = setInterval(() => {
        setProgress((prev) => Math.min(prev + 10, 90));
      }, 200);

      const response = await fetch(`${API_BASE_URL}/api/shamir-stego/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          secret,
          password,
          num_shares: numShares,
          threshold: threshold,
          prompt,
          model: selectedModel,
        }),
      });

      clearInterval(progressInterval);
      setProgress(100);

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to create images');
      }

      setImages(data.images || []);
      setSuccess(`Created ${data.images?.length || numShares} secret images with threshold ${data.threshold || threshold}. Need ${data.threshold || threshold} shares to reconstruct.`);

      setTimeout(() => {
        const imagesSection = document.querySelector('.images-grid');
        if (imagesSection) {
          imagesSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setProgress(100);
    }
  };

  const handleReveal = async () => {
    if (images.length === 0) {
      setError('No images to reveal. Create images first.');
      return;
    }

    setRevealLoading(true);
    setError('');
    setRevealedSecret('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/shamir-stego/reveal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_paths: images,
          password,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to reveal secret');
      }

      setRevealedSecret(data.secret);
    } catch (err) {
      setError(err.message);
    } finally {
      setRevealLoading(false);
    }
  };

  const getImageUrl = (path) => {
    const cleanPath = String(path || '').replace(/^\/+/, '');
    const timestamp = new Date().getTime();
    return `${API_BASE_URL}/${cleanPath}?t=${timestamp}`;
  };

  const handleDownloadAllZip = async () => {
    if (!images.length) {
      setError('No generated images to download.');
      return;
    }

    try {
      setError('');
      const response = await fetch(`${API_BASE_URL}/api/shamir-stego/download-zip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_paths: images }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to create ZIP download');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `shamir_stego_bundle_${Date.now()}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleQuickMock = () => {
    setSecret('MySecret123');
    setPassword('password123');
    setSelectedModel('mock');
    setSelectedPromptIndex(0);
    setNumShares(10);
    setThreshold(6);
  };

  return (
    <div className="shamir-stego-page">
      <div className="page-header">
        <h1>{ICONS.lock} Shamir-Stego Encryption</h1>
        <p>Encrypt a secret, split into shares using Shamir's algorithm, embed into AI-generated images</p>
      </div>

      <div className="content">
        <div className="create-section">
          <div className="section-header">
            <h2>{ICONS.closedLock} Create Secret Shares</h2>
            <button className="btn-quick" onClick={handleQuickMock}>{ICONS.bolt} Quick Demo</button>
          </div>

          <div className="form-grid">
            <div className="form-group full-width">
              <label>{ICONS.key} Secret Message</label>
              <textarea
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder="Enter your secret message to hide..."
                rows={3}
              />
            </div>

            <div className="form-group">
              <label>{ICONS.lock} Password (optional)</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter encryption password..."
              />
            </div>

            <div className="form-group">
              <label>{ICONS.number} Number of Shares</label>
              <input
                type="number"
                value={numShares}
                onChange={(e) => setNumShares(Math.max(2, Math.min(20, parseInt(e.target.value, 10) || 10)))}
                min={2}
                max={20}
                placeholder="10"
              />
              <small className="hint">How many share images to generate (2-20)</small>
            </div>

            <div className="form-group">
              <label>{ICONS.edit} Threshold</label>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(Math.max(2, Math.min(numShares, parseInt(e.target.value, 10) || 6)))}
                min={2}
                max={numShares}
                placeholder="6"
              />
              <small className="hint">Minimum shares needed to reconstruct</small>
            </div>

            <div className="form-group">
              <label>{ICONS.robot} AI Model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="model-select"
              >
                {aiModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
              <small className="hint">
                {selectedModel === 'mock' ? `${ICONS.check} Instant - no API calls` : `${ICONS.warning} May be slow if provider is down`}
              </small>
            </div>

            <div className="form-group full-width">
              <label>{ICONS.brush} Image Theme</label>
              <div className="prompt-grid">
                {promptOptions.map((opt, index) => (
                  <button
                    key={opt.id}
                    className={`prompt-btn ${selectedPromptIndex === index ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedPromptIndex(index);
                      setCustomPrompt('');
                    }}
                  >
                    {opt.title}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group full-width">
              <label>{ICONS.edit} Custom Prompt (optional)</label>
              <input
                type="text"
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Or enter your own prompt..."
                className="custom-prompt-input"
              />
            </div>
          </div>

          <button
            className="btn btn-primary btn-large"
            onClick={handleCreate}
            disabled={loading || !secret.trim()}
          >
            {loading ? (
              <>
                <span className="spinner"></span>
                Generating Images... {progress}%
              </>
            ) : (
              `${ICONS.rocket} Create ${numShares} Secret Images`
            )}
          </button>

          {loading && (
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }}></div>
            </div>
          )}

          {error && <div className="error-message">{ICONS.cross} {error}</div>}
          {success && <div className="success-message">{ICONS.check} {success}</div>}
        </div>

        {images.length > 0 && (
          <div className="images-section">
            <div className="section-header">
              <h2>{ICONS.folder} Generated Secret Images ({images.length})</h2>
              <span className="badge">Share these securely!</span>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <button className="btn btn-primary" onClick={handleDownloadAllZip}>
                Download All as ZIP
              </button>
            </div>

            <div className="images-grid">
              {images.map((img, index) => (
                <div key={index} className="image-card">
                  <div className="image-wrapper">
                    <img
                      src={getImageUrl(img)}
                      alt={`Share ${index + 1}`}
                      onError={(e) => {
                        e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNTEyIiBoZWlnaHQ9IjUxMiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNTEyIiBoZWlnaHQ9IjUxMiIgZmlsbD0iIzMzMyIvPjx0ZXh0IHg9IjI1NiIgeT0iMjU2IiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIyNCIgZmlsbD0iI2ZmZiIgdGV4dC1hbmNob3I9Im1pZGRsZSI+SW1hZ2UgVy9TSEFNSVIgMTwvdGV4dD48L3N2Zz4=';
                      }}
                    />
                    <div className="share-badge">{index + 1}</div>
                  </div>
                  <div className="image-actions">
                    <a
                      href={getImageUrl(img)}
                      download={`secret_share_${index + 1}.png`}
                      className="btn-download"
                    >
                      {ICONS.down}
                    </a>
                  </div>
                </div>
              ))}
            </div>

            <div className="reveal-section">
              <h3>{ICONS.search} Reveal Secret</h3>
              <p className="hint">Upload at least {threshold} of the {numShares} images to reconstruct the secret</p>
              <button
                className="btn btn-success btn-large"
                onClick={handleReveal}
                disabled={revealLoading}
              >
                {revealLoading ? `${ICONS.search} Revealing...` : `${ICONS.search} Reveal Secret from Images`}
              </button>

              {revealedSecret && (
                <div className="revealed-secret">
                  <h4>{ICONS.check} Secret Revealed:</h4>
                  <div className="secret-value">{revealedSecret}</div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="info-footer">
        <div className="info-box">
          <h4>{ICONS.lock} How It Works</h4>
          <ol>
            <li>Enter your secret message</li>
            <li>Set number of shares and threshold</li>
            <li>Choose AI model (Mock is instant, network models may be slower)</li>
            <li>Select or enter a prompt</li>
            <li>Click Create to generate {numShares} images</li>
            <li>Each image contains an encrypted share</li>
            <li>Need at least {threshold} of {numShares} shares to reconstruct the secret</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

export default ShamirStego;
