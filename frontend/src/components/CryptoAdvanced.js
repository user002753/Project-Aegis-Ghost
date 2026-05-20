import React, { useState } from 'react';
import './CryptoAdvanced.css';
import { API_BASE_URL } from '../config';

function CryptoAdvanced() {
  const [activeTab, setActiveTab] = useState('shamir');
  const [secret, setSecret] = useState('');
  const [numShares, setNumShares] = useState(5);
  const [threshold, setThreshold] = useState(3);
  const [shares, setShares] = useState([]);
  const [passwords, setPasswords] = useState([]);
  const [layers, setLayers] = useState([]);
  const [decryptPasswords, setDecryptPasswords] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const handleSplitSecret = async () => {
    if (!secret) {
      alert('Please enter a secret');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/shamir/split`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          secret,
          num_shares: numShares,
          threshold
        })
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        setShares(data.shares);
        setResult({ type: 'success', message: data.message });
      } else {
        setResult({ type: 'error', message: data.detail });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message });
    }
    setLoading(false);
  };

  const handleReconstruct = async () => {
    if (shares.length < threshold) {
      alert(`Need at least ${threshold} shares to reconstruct`);
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/shamir/reconstruct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(shares.slice(0, threshold))
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        setResult({ 
          type: 'success', 
          message: `Reconstructed: "${data.secret}"`,
          secret: data.secret
        });
      } else {
        setResult({ type: 'error', message: data.detail });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message });
    }
    setLoading(false);
  };

  const handleRussianEncrypt = async () => {
    if (!secret || !passwords.length) {
      alert('Please enter a secret and at least one password');
      return;
    }
    
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/russian-doll/encrypt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          secret,
          passwords: passwords.filter(p => p.trim())
        })
      });
      
      const data = await response.json();
      if (data.status === 'success') {
        setLayers(data.layers);
        setResult({ type: 'success', message: data.message });
      } else {
        setResult({ type: 'error', message: data.detail });
      }
    } catch (error) {
      setResult({ type: 'error', message: error.message });
    }
    setLoading(false);
  };

  const addPassword = () => {
    setPasswords([...passwords, '']);
  };

  const updatePassword = (index, value) => {
    const newPasswords = [...passwords];
    newPasswords[index] = value;
    setPasswords(newPasswords);
  };

  return (
    <div className="crypto-advanced-page">
      <div className="page-header">
        <h1>🔐 Advanced Cryptography</h1>
        <p>Shamir's Secret Sharing & Russian Doll Encryption</p>
      </div>

      <div className="crypto-content">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'shamir' ? 'active' : ''}`}
            onClick={() => setActiveTab('shamir')}
          >
            🔑 Shamir's Secret Sharing
          </button>
          <button 
            className={`tab ${activeTab === 'russian' ? 'active' : ''}`}
            onClick={() => setActiveTab('russian')}
          >
            🪆 Russian Doll Encryption
          </button>
        </div>

        <div className="crypto-card">
          <div className="input-section">
            <div className="option-group">
              <label>Secret Data</label>
              <textarea
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder="Enter your secret data..."
                rows={3}
              />
            </div>

            {activeTab === 'shamir' && (
              <>
                <div className="option-row">
                  <div className="option-group">
                    <label>Number of Shares</label>
                    <input
                      type="number"
                      value={numShares}
                      onChange={(e) => setNumShares(parseInt(e.target.value))}
                      min={2}
                      max={10}
                    />
                  </div>
                  <div className="option-group">
                    <label>Threshold (min to reconstruct)</label>
                    <input
                      type="number"
                      value={threshold}
                      onChange={(e) => setThreshold(parseInt(e.target.value))}
                      min={2}
                      max={numShares}
                    />
                  </div>
                </div>

                <div className="button-group">
                  <button 
                    className="btn btn-primary"
                    onClick={handleSplitSecret}
                    disabled={loading}
                  >
                    {loading ? 'Splitting...' : '🔐 Split Secret'}
                  </button>
                  <button 
                    className="btn btn-secondary"
                    onClick={handleReconstruct}
                    disabled={loading || shares.length < threshold}
                  >
                    🔓 Reconstruct Secret
                  </button>
                </div>
              </>
            )}

            {activeTab === 'russian' && (
              <>
                <div className="option-group">
                  <label>Encryption Passwords</label>
                  <p className="hint">Add passwords for each layer (outermost first)</p>
                  {passwords.map((pwd, idx) => (
                    <input
                      key={idx}
                      type="password"
                      value={pwd}
                      onChange={(e) => updatePassword(idx, e.target.value)}
                      placeholder={`Password for layer ${idx + 1}`}
                      className="password-input"
                    />
                  ))}
                  <button className="btn btn-small" onClick={addPassword}>
                    ➕ Add Password
                  </button>
                </div>

                <div className="button-group">
                  <button 
                    className="btn btn-primary"
                    onClick={handleRussianEncrypt}
                    disabled={loading || passwords.length === 0}
                  >
                    {loading ? 'Encrypting...' : '🪆 Create Russian Doll'}
                  </button>
                </div>
              </>
            )}

            {result && (
              <div className={`result-box ${result.type}`}>
                <p>{result.message}</p>
                {result.secret && <strong>{result.secret}</strong>}
              </div>
            )}
          </div>

          {activeTab === 'shamir' && shares.length > 0 && (
            <div className="shares-display">
              <h3>Generated Shares ({shares.length})</h3>
              <p className="hint">Share these with trusted parties. Need {threshold} to reconstruct.</p>
              <div className="shares-grid">
                {shares.map((share, idx) => (
                  <div key={idx} className="share-card">
                    <strong>Share {share.share_index}</strong>
                    <code>X = {share.x}</code>
                    <div className="share-values">
                      Y values: [{share.y_values.slice(0, 5).join(', ')}...]
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'russian' && layers.length > 0 && (
            <div className="layers-display">
              <h3>Encryption Layers Created ({layers.length})</h3>
              <p className="hint">To decrypt, provide passwords in reverse order.</p>
              <div className="layers-visual">
                {layers.map((layer, idx) => (
                  <div key={idx} className="layer-card">
                    <div className="layer-label">
                      {idx === 0 ? '🔒 Outer' : idx === layers.length - 1 ? '💎 Core' : 'Layer'}
                    </div>
                    <div className="layer-info">
                      Cipher: {layer.ciphertext.slice(0, 20)}...
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="info-cards">
            <div className="info-card">
              <h3>🔑 Shamir's Secret Sharing</h3>
              <p>
                Splits a secret into multiple shares. Only a threshold number of shares 
                can reconstruct the original secret. Perfect for distributed trust.
              </p>
              <ul>
                <li><strong>Share</strong>: Each piece of the secret</li>
                <li><strong>Threshold</strong>: Minimum shares needed</li>
                <li><strong>Secure</strong>: No single point of failure</li>
              </ul>
            </div>

            <div className="info-card">
              <h3>🪆 Russian Doll Encryption</h3>
              <p>
                Nested encryption layers like matryoshka dolls. Each layer requires 
                a password to unlock the next. Maximum security through depth.
              </p>
              <ul>
                <li><strong>Layer 1</strong>: Outermost protection</li>
                <li><strong>Layer N</strong>: Core secret</li>
                <li><strong>Order matters</strong>: Decrypt in reverse</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CryptoAdvanced;
