import React, { useState } from 'react';
import './ShamirSplit.css';
import { API_BASE_URL } from '../../config';

function ShamirSplit() {
  const [secret, setSecret] = useState('');
  const [numShares, setNumShares] = useState(5);
  const [threshold, setThreshold] = useState(3);
  const [shares, setShares] = useState([]);
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
          num_shares: Number(numShares),
          threshold: Number(threshold),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Shamir split failed');
      setShares(data.shares || []);
      setResult({ type: 'success', message: data.message || 'Secret split successfully' });
    } catch (error) {
      setResult({ type: 'error', message: error.message });
    } finally {
      setLoading(false);
    }
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
        body: JSON.stringify(shares.slice(0, threshold)),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Shamir reconstruction failed');
      setResult({
        type: 'success',
        message: `Reconstructed: "${data.secret}"`,
        secret: data.secret,
      });
    } catch (error) {
      setResult({ type: 'error', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="crypto-advanced-page">
      <div className="page-header">
        <h1>Shamir Secret Sharing</h1>
        <p>Split and reconstruct secrets as before</p>
      </div>

      <div className="crypto-content">
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

            <div className="option-row">
              <div className="option-group">
                <label>Number of Shares</label>
                <input
                  type="number"
                  value={numShares}
                  onChange={(e) => setNumShares(parseInt(e.target.value || '5', 10))}
                  min={2}
                  max={10}
                />
              </div>
              <div className="option-group">
                <label>Threshold (min to reconstruct)</label>
                <input
                  type="number"
                  value={threshold}
                  onChange={(e) => setThreshold(parseInt(e.target.value || '3', 10))}
                  min={2}
                  max={numShares}
                />
              </div>
            </div>

            <div className="button-group">
              <button className="btn btn-primary" onClick={handleSplitSecret} disabled={loading}>
                {loading ? 'Splitting...' : 'Split Secret'}
              </button>
              <button className="btn btn-secondary" onClick={handleReconstruct} disabled={loading || shares.length < threshold}>
                Reconstruct Secret
              </button>
            </div>

            {result && (
              <div className={`result-box ${result.type}`}>
                <p>{result.message}</p>
              </div>
            )}
          </div>

          {shares.length > 0 && (
            <div className="shares-display">
              <h3>Generated Shares ({shares.length})</h3>
              <p className="hint">Need {threshold} shares to reconstruct.</p>
              <div className="shares-grid">
                {shares.map((share, idx) => (
                  <div key={idx} className="share-card">
                    <strong>Share {share.share_index}</strong>
                    <code>X = {share.x}</code>
                    <div className="share-values">Y values: [{(share.y_values || []).slice(0, 5).join(', ')}...]</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ShamirSplit;
