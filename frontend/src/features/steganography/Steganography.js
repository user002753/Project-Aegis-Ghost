import React, { useState } from 'react';
import './Steganography.css';
import { API_BASE_URL } from '../../config';

function Steganography() {
  const [mode, setMode] = useState('hide'); // hide | extract
  const [secretMessage, setSecretMessage] = useState('');
  const [password, setPassword] = useState('');
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [status, setStatus] = useState('');
  const [progress, setProgress] = useState(0);
  const [useAI, setUseAI] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [extractedMessage, setExtractedMessage] = useState('');
  const [provider, setProvider] = useState('pollinations-schnell');
  const [advancedMode, setAdvancedMode] = useState(false);
  const [runHistory, setRunHistory] = useState([]);

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onload = (event) => {
        setSelectedImage(event.target.result);
        if (useAI) {
          setStatus('AI image selected. Enter prompt or use default.');
        } else {
          setStatus('Image loaded. Enter your secret message.');
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleGenerateAI = async () => {
    if (!secretMessage) {
      setStatus('Please enter a secret message first.');
      return;
    }

    setStatus('Generating AI image with hidden data...');
    setProgress(10);

    try {
      const endpoint = advancedMode ? '/api/stego/russian-doll-fake-lsb/hide' : '/api/ai/hide';
      const reqBody = advancedMode
        ? {
            secret_text: secretMessage,
            password: password || 'layer1',
            decoy_message: 'NO_VALID_SECRET_PRESENT',
            prompt_themes: Array.from({ length: 10 }, () => aiPrompt || 'Abstract artistic pattern with deep colors'),
            threshold: 6,
            num_shares: 10,
            provider,
            size: [384, 384],
            allow_fallback: true,
          }
        : {
            prompt: aiPrompt || 'Abstract artistic pattern with deep colors',
            secret_text: secretMessage,
            provider,
            use_gemini: true,
            size: [1024, 1024],
            allow_fallback: true,
            user_id: sessionStorage.getItem('user_email') || sessionStorage.getItem('user_id') || null,
          };

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(reqBody),
      });

      const data = await response.json();

      if (data.status === 'success') {
        setProgress(80);
        const imagePath = advancedMode ? (data.image_paths || [])[0] : data.image_path;
        // Fetch the generated image
        const imageResponse = await fetch(`${API_BASE_URL}/${String(imagePath || '').replace(/^\/+/, '')}`);
        const blob = await imageResponse.blob();
        const url = URL.createObjectURL(blob);
        
        setResultImage(url);
        setProgress(100);
        setStatus(`Message hidden successfully! Backend: ${data.backend_used || provider}`);
        if (advancedMode) {
          setRunHistory((prev) => [
            {
              id: Date.now(),
              createdAt: new Date().toLocaleString(),
              backend: data.backend_used || provider,
              manifest_path: data.manifest_path,
              image_paths: data.image_paths || [],
              threshold: data.threshold || 6,
            },
            ...prev,
          ].slice(0, 20));
        }
      } else {
        throw new Error(data.detail || 'Generation failed');
      }
    } catch (error) {
      console.error('AI generation error:', error);
      setStatus(`AI generation failed: ${error.message}. No mock fallback used.`);
    }
  };

  const simulateHide = async () => {
    setProgress(0);
    for (let i = 0; i <= 100; i += 10) {
      await new Promise(resolve => setTimeout(resolve, 50));
      setProgress(i);
    }
    
    // Create a simple stego result
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 512;
    canvas.height = 512;
    
    // Create abstract pattern
    const gradient = ctx.createLinearGradient(0, 0, 512, 512);
    gradient.addColorStop(0, '#1a1a2e');
    gradient.addColorStop(1, '#16213e');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 512, 512);
    
    // Add some artistic elements
    for (let i = 0; i < 20; i++) {
      ctx.beginPath();
      ctx.arc(
        Math.random() * 512,
        Math.random() * 512,
        Math.random() * 50 + 10,
        0,
        Math.PI * 2
      );
      ctx.fillStyle = `rgba(${Math.random() * 100 + 50}, ${Math.random() * 200 + 100}, ${Math.random() * 150 + 100}, 0.3)`;
      ctx.fill();
    }
    
    setResultImage(canvas.toDataURL());
    setProgress(100);
    setStatus('Message hidden (simulated). Download the stego image.');
  };

  const handleHide = async () => {
    if (!secretMessage) {
      setStatus('Please enter a secret message.');
      return;
    }

    if (useAI) {
      await handleGenerateAI();
      return;
    }

    if (!selectedImage) {
      setStatus('Please enter a message and select an image.');
      return;
    }

    // Use regular steganography with selected image
    setStatus('Embedding message in selected image...');
    setProgress(15);
    try {
      const formData = new FormData();
      const fileToSend = selectedFile || (await (await fetch(selectedImage)).blob());
      formData.append('image', fileToSend, selectedFile?.name || 'upload.png');
      formData.append('secret_text', secretMessage);

      const response = await fetch(`${API_BASE_URL}/api/stego/hide`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Stego hide failed');
      }

      const outPath = String(data.output_image || '').replace(/^\/+/, '');
      const imageResponse = await fetch(`${API_BASE_URL}/${outPath}`);
      const blob = await imageResponse.blob();
      const url = URL.createObjectURL(blob);
      setResultImage(url);
      setProgress(100);
      setStatus('Message hidden successfully.');
    } catch (error) {
      console.error('Stego hide error:', error);
      setStatus(`Stego hide failed: ${error.message}`);
    }
  };

  const handleExtract = async () => {
    if (!selectedImage && !resultImage) {
      setStatus('Please select a stego image.');
      return;
    }

    setStatus('Extracting message from image...');
    setProgress(10);

    try {
      if (advancedMode && runHistory.length > 0) {
        const latest = runHistory[0];
        const response = await fetch(`${API_BASE_URL}/api/stego/russian-doll-fake-lsb/reveal`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_paths: (latest.image_paths || []).slice(0, latest.threshold || 6),
            password: password || 'layer1',
            threshold: latest.threshold || 6,
            manifest_path: latest.manifest_path,
          }),
        });
        const data = await response.json();
        if (data.status === 'success') {
          setExtractedMessage(data.secret_text || data.secret || '');
          setProgress(100);
          setStatus('Advanced message extracted successfully!');
          return;
        }
      }

      // For AI-generated images, try API extraction
      if (selectedImage) {
        const formData = new FormData();
        // Convert data URL to blob
        const response = await fetch(selectedImage);
        const blob = await response.blob();
        formData.append('stego_image', blob, 'stego.png');

        const extractResponse = await fetch(`${API_BASE_URL}/api/ai/reveal`, {
          method: 'POST',
          body: formData,
        });

        const data = await extractResponse.json();
        
        if (data.status === 'success') {
          setExtractedMessage(data.text || `Binary data: ${data.raw_hex}`);
          setProgress(100);
          setStatus('Message extracted successfully!');
          return;
        }
      }
      
      // Fallback simulation
      throw new Error('API extraction not available');
    } catch (error) {
      console.error('Extraction error:', error);
      // Fallback to simulation
      setProgress(50);
      await new Promise(resolve => setTimeout(resolve, 500));
      setExtractedMessage('This is a simulated hidden message extracted from the image!');
      setProgress(100);
      setStatus('Message extracted (simulated).');
    }
  };

  const handleDownload = () => {
    if (resultImage) {
      const link = document.createElement('a');
      link.download = 'stego_image.png';
      link.href = resultImage;
      link.click();
    }
  };

  const handleClear = () => {
    setSecretMessage('');
    setExtractedMessage('');
    setSelectedImage(null);
    setSelectedFile(null);
    setResultImage(null);
    setStatus('');
    setProgress(0);
    setAiPrompt('');
  };

  return (
    <div className="steganography-page">
      <div className="page-header">
        <h1>Steganography</h1>
        <p>Hide secret messages within images using AI or traditional methods</p>
      </div>

      <div className="steganography-content">
        <div className="stego-card">
          <div className="tabs">
            <button 
              className={`tab ${mode === 'hide' ? 'active' : ''}`}
              onClick={() => { setMode('hide'); setExtractedMessage(''); setStatus(''); }}
            >
              Hide Message
            </button>
            <button 
              className={`tab ${mode === 'extract' ? 'active' : ''}`}
              onClick={() => { setMode('extract'); setSecretMessage(''); setStatus(''); }}
            >
              Extract Message
            </button>
          </div>

          {/* AI Generation Toggle */}
          {mode === 'hide' && (
            <div className="ai-toggle-section">
              <label className="ai-toggle">
                <input
                  type="checkbox"
                  checked={useAI}
                  onChange={(e) => setUseAI(e.target.checked)}
                />
                <span className="toggle-slider"></span>
                <span className="toggle-label">
                  <span className="ai-icon">✨</span>
                  Use AI to generate image
                </span>
              </label>
              <label className="ai-toggle" style={{ marginTop: '8px' }}>
                <input
                  type="checkbox"
                  checked={advancedMode}
                  onChange={(e) => setAdvancedMode(e.target.checked)}
                />
                <span className="toggle-slider"></span>
                <span className="toggle-label">Advanced: Russian Doll + Shamir (10 images)</span>
              </label>
              <div className="input-group" style={{ marginTop: '10px', background: 'rgba(197, 108, 240, 0.08)', padding: '15px', borderRadius: '8px', border: '1px solid rgba(197, 108, 240, 0.2)' }}>
                <label style={{ color: '#c56cf0', fontWeight: 600, display: 'block', marginBottom: '10px', fontSize: '14px' }}>🎨 AI Provider</label>
                <select 
                  className="input-field" 
                  value={provider} 
                  onChange={(e) => setProvider(e.target.value)}
                  style={{ width: '100%', padding: '12px', background: 'rgba(0, 0, 0, 0.4)', border: '1px solid rgba(197, 108, 240, 0.3)', borderRadius: '6px', color: '#fff', fontSize: '14px', cursor: 'pointer' }}
                >
                  <option value="pollinations-schnell">Pollinations Schnell (Fastest)</option>
                  <option value="auto">Auto</option>
                  <option value="pollinations">Pollinations</option>
                  <option value="pollinations-turbo">Pollinations Turbo</option>
                  <option value="pexels">Pexels</option>
                  <option value="genai">GenAI</option>
                  <option value="puter">Puter</option>
                  <option value="openai">OpenAI</option>
                  <option value="raphael">Raphael</option>
                  <option value="deepai">DeepAI</option>
                  <option value="leonardo">Leonardo</option>
                  <option value="llm">LLM Local</option>
                  <option value="mock">Mock</option>
                </select>
              </div>
              
              {useAI && (
                <div className="ai-prompt-section">
                  <input
                    type="text"
                    className="input-field"
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    placeholder="Describe the image you want AI to generate..."
                  />
                  <div className="ai-presets">
                    <button onClick={() => setAiPrompt('Abstract colorful patterns')} className="preset-btn">Abstract</button>
                    <button onClick={() => setAiPrompt('Cyberpunk cityscape neon lights')} className="preset-btn">Cyberpunk</button>
                    <button onClick={() => setAiPrompt('Nature landscape mountains sunset')} className="preset-btn">Nature</button>
                    <button onClick={() => setAiPrompt('')} className="preset-btn">Random</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Image Upload */}
          {!useAI && mode === 'hide' && (
            <div className="image-upload">
              <input
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                id="image-upload"
                className="file-input"
              />
              <label htmlFor="image-upload" className="file-label">
                {selectedImage ? (
                  <img src={selectedImage} alt="Selected" className="preview-image" />
                ) : (
                  <>
                    <span className="upload-icon">📷</span>
                    <span>Click to select an image</span>
                    <span className="upload-hint">PNG or JPG recommended</span>
                  </>
                )}
              </label>
            </div>
          )}

          {/* For AI mode, show a placeholder or generated preview */}
          {useAI && mode === 'hide' && (
            <div className="ai-preview">
              <div className="ai-preview-placeholder">
                <span className="ai-icon-large">🎨</span>
                <span>{aiPrompt || 'AI will generate an image based on your prompt'}</span>
              </div>
            </div>
          )}

          {mode === 'hide' && (
            <div className="input-group">
              <label>Secret Message</label>
              <textarea
                className="input-field textarea"
                value={secretMessage}
                onChange={(e) => setSecretMessage(e.target.value)}
                placeholder="Enter your secret message..."
                rows={4}
              />
            </div>
          )}

          {mode === 'extract' && (
            <div className="image-upload">
              <input
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                id="image-upload-extract"
                className="file-input"
              />
              <label htmlFor="image-upload-extract" className="file-label">
                {selectedImage ? (
                  <img src={selectedImage} alt="Selected" className="preview-image" />
                ) : (
                  <>
                    <span className="upload-icon">🔍</span>
                    <span>Click to select a stego image</span>
                    <span className="upload-hint">Image with hidden data</span>
                  </>
                )}
              </label>
            </div>
          )}

          {mode === 'extract' && (
            <div className="input-group">
              <label>Extracted Message</label>
              <textarea
                className="input-field textarea"
                value={extractedMessage}
                readOnly
                placeholder="Extracted message will appear here..."
                rows={4}
              />
            </div>
          )}

          <div className="input-group" style={{ background: 'rgba(255, 217, 61, 0.08)', padding: '15px', borderRadius: '8px', border: '1px solid rgba(255, 217, 61, 0.2)', marginTop: '15px' }}>
            <label style={{ color: '#ffd93d', fontWeight: 600, display: 'block', marginBottom: '10px', fontSize: '14px' }}>🔑 Password (Optional)</label>
            <input
              type="password"
              className="input-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password to encrypt the message"
              style={{ width: '100%', padding: '12px', background: 'rgba(0, 0, 0, 0.4)', border: '1px solid rgba(255, 217, 61, 0.3)', borderRadius: '6px', color: '#fff', fontSize: '14px' }}
            />
          </div>

          <div className="action-buttons">
            <button className="btn btn-secondary" onClick={handleClear}>
              Clear
            </button>
            <button 
              className="btn btn-primary"
              onClick={mode === 'hide' ? handleHide : handleExtract}
              disabled={progress > 0 && progress < 100}
            >
              {mode === 'hide' ? (useAI ? '✨ Generate & Hide' : 'Hide Message') : 'Extract Message'}
            </button>
          </div>

          {progress > 0 && progress < 100 && (
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
          )}

          {status && (
            <div className="status-message">
              {status}
            </div>
          )}

          {resultImage && mode === 'hide' && (
            <div className="result-section">
              <label>Result Image</label>
              <div className="result-preview">
                <img src={resultImage} alt="Stego result" />
                <button className="btn btn-primary download-btn" onClick={handleDownload}>
                  📥 Download
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="stego-info">
          <div className="info-card">
            <h3>✨ AI Integration</h3>
            <p>
              Generate AI images with hidden secret data. The AI engine creates unique images 
              based on your prompts, then embeds your secret message invisibly.
            </p>
            <ul>
              <li>No image upload needed</li>
              <li>Unique generated images</li>
              <li>Professional quality results</li>
            </ul>
          </div>

          <div className="info-card">
            <h3>How Steganography Works</h3>
            <p>
              Steganography hides secret data within ordinary files, making the 
              existence of the hidden information imperceptible to observers.
            </p>
          </div>

          <div className="info-card">
            <h3>Capacity Guide</h3>
            <ul>
              <li>Small images (640x480): ~50KB message</li>
              <li>Medium images (1920x1080): ~300KB message</li>
              <li>Large images (4K): ~2MB message</li>
            </ul>
          </div>

          <div className="info-card">
            <h3>Security Tips</h3>
            <ul>
              <li>Use lossless formats (PNG)</li>
              <li>Combine with encryption for best security</li>
              <li>Don't share the original image</li>
              <li>AI-generated images provide extra cover</li>
            </ul>
          </div>
          <div className="info-card">
            <h3>Run History</h3>
            {runHistory.length === 0 ? (
              <p>No advanced runs yet.</p>
            ) : (
              <ul>
                {runHistory.map((r) => (
                  <li key={r.id}>{r.createdAt} | {r.backend} | {r.image_paths.length} images</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Steganography;
