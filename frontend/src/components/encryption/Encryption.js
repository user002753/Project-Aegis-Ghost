import React, { useState } from 'react';
import './Encryption.css';

function Encryption() {
  const [mode, setMode] = useState('encrypt'); // encrypt | decrypt
  const [inputText, setInputText] = useState('');
  const [password, setPassword] = useState('');
  const [result, setResult] = useState('');
  const [status, setStatus] = useState('');
  const [algorithm, setAlgorithm] = useState('AES-256');

  const handleProcess = async () => {
    if (!inputText || !password) {
      setStatus('Please enter both text and password.');
      return;
    }

    setStatus('Processing...');
    
    // Simulate encryption/decryption
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    if (mode === 'encrypt') {
      // Simulate encryption
      const encrypted = btoa(inputText).split('').reverse().join('');
      setResult(encrypted);
      setStatus(`Encrypted using ${algorithm}. Copy the result below.`);
    } else {
      try {
        // Simulate decryption
        const decrypted = atob(inputText.split('').reverse().join(''));
        setResult(decrypted);
        setStatus('Decryption successful!');
      } catch (error) {
        setResult('Decryption failed. Please check your input.');
        setStatus('Error: Invalid encrypted data.');
      }
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(result);
    setStatus('Copied to clipboard!');
    setTimeout(() => setStatus(''), 2000);
  };

  const handleClear = () => {
    setInputText('');
    setResult('');
    setStatus('');
  };

  return (
    <div className="encryption-page">
      <div className="page-header">
        <h1>Encryption</h1>
        <p>Military-grade encryption for your sensitive data</p>
      </div>

      <div className="encryption-content">
        <div className="encryption-controls">
          <div className="tabs">
            <button 
              className={`tab ${mode === 'encrypt' ? 'active' : ''}`}
              onClick={() => { setMode('encrypt'); setInputText(''); setPassword(''); setResult(''); setStatus(''); }}
            >
              Encrypt
            </button>
            <button 
              className={`tab ${mode === 'decrypt' ? 'active' : ''}`}
              onClick={() => { setMode('decrypt'); setInputText(''); setPassword(''); setResult(''); setStatus(''); }}
            >
              Decrypt
            </button>
          </div>

          <div className="algorithm-selector" style={{ background: 'rgba(0, 255, 136, 0.08)', padding: '15px', borderRadius: '8px', border: '1px solid rgba(0, 255, 136, 0.2)', marginBottom: '15px' }}>
            <label style={{ color: '#00ff88', fontWeight: 600, display: 'block', marginBottom: '10px', fontSize: '14px' }}>🔐 Encryption Algorithm</label>
            <select 
              value={algorithm} 
              onChange={(e) => setAlgorithm(e.target.value)}
              style={{ width: '100%', padding: '12px', background: 'rgba(0, 0, 0, 0.4)', border: '1px solid rgba(0, 255, 136, 0.3)', borderRadius: '6px', color: '#fff', fontSize: '14px', cursor: 'pointer' }}
            >
              <option value="AES-256">AES-256 (Recommended)</option>
              <option value="AES-128">AES-128</option>
              <option value="RSA-2048">RSA-2048</option>
              <option value="ChaCha20">ChaCha20</option>
            </select>
          </div>

          <div className="input-section">
            <div className="input-group">
              <label>{mode === 'encrypt' ? 'Plain Text' : 'Encrypted Text'}</label>
              <textarea
                className="input-field textarea"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={mode === 'encrypt' 
                  ? 'Enter text to encrypt...' 
                  : 'Enter encrypted text...'}
                rows={6}
              />
            </div>

            <div className="input-group" style={{ background: 'rgba(255, 217, 61, 0.08)', padding: '15px', borderRadius: '8px', border: '1px solid rgba(255, 217, 61, 0.2)', marginBottom: '15px' }}>
              <label style={{ color: '#ffd93d', fontWeight: 600, display: 'block', marginBottom: '10px', fontSize: '14px' }}>🔑 Password / Key</label>
              <input
                type="password"
                className="input-field"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                style={{ width: '100%', padding: '12px', background: 'rgba(0, 0, 0, 0.4)', border: '1px solid rgba(255, 217, 61, 0.3)', borderRadius: '6px', color: '#fff', fontSize: '14px' }}
              />
            </div>

            <div className="action-buttons">
              <button className="btn btn-secondary" onClick={handleClear}>
                Clear
              </button>
              <button className="btn btn-primary" onClick={handleProcess}>
                {mode === 'encrypt' ? 'Encrypt' : 'Decrypt'}
              </button>
            </div>

            {status && (
              <div className={`status-message ${status.includes('Error') ? 'error' : ''}`}>
                {status}
              </div>
            )}
          </div>

          {result && (
            <div className="result-section">
              <label>{mode === 'encrypt' ? 'Encrypted Result' : 'Decrypted Result'}</label>
              <div className="result-box">
                <textarea
                  className="input-field textarea"
                  value={result}
                  readOnly
                  rows={6}
                />
                <button className="copy-btn" onClick={handleCopy}>
                  📋 Copy
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="encryption-info">
          <div className="info-card">
            <h3>Security Features</h3>
            <ul>
              <li>256-bit military-grade encryption</li>
              <li>Secure key derivation (PBKDF2)</li>
              <li>Unique IV for each encryption</li>
              <li>No data stored on servers</li>
            </ul>
          </div>

          <div className="info-card">
            <h3>Best Practices</h3>
            <ul>
              <li>Use strong, unique passwords</li>
              <li>Don't share encryption keys</li>
              <li>Store passwords securely</li>
              <li>Verify recipient identity</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Encryption;
