import React, { useState } from 'react';
import './Steganalysis.css';
import { API_BASE_URL } from '../../config';

// ─── Risk badge helper ────────────────────────────────────────────────────────
function RiskBadge({ level }) {
  const map = {
    HIGH:   { label: 'HIGH RISK',  cls: 'risk-high'   },
    MEDIUM: { label: 'MEDIUM RISK',cls: 'risk-medium' },
    LOW:    { label: 'LOW RISK',   cls: 'risk-low'    },
    CLEAN:  { label: 'CLEAN',      cls: 'risk-clean'  },
  };
  const { label, cls } = map[level] || map.CLEAN;
  return <span className={`risk-badge ${cls}`}>{label}</span>;
}

// ─── Verdict icon ─────────────────────────────────────────────────────────────
function VerdictIcon({ verdict }) {
  return verdict === 'Suspicious'
    ? <span className="verdict-icon suspicious">⚠</span>
    : <span className="verdict-icon clean">✓</span>;
}

// ─── Confidence bar ───────────────────────────────────────────────────────────
function ConfidenceBar({ value, verdict }) {
  const cls = verdict === 'Suspicious' ? 'bar-suspicious' : 'bar-clean';
  return (
    <div className="conf-bar-wrap">
      <div className={`conf-bar-fill ${cls}`} style={{ width: `${Math.min(value, 100)}%` }} />
      <span className="conf-bar-label">{value.toFixed(1)}%</span>
    </div>
  );
}

// ─── Method card ──────────────────────────────────────────────────────────────
function MethodCard({ analysis }) {
  const [expanded, setExpanded] = useState(false);

  const renderChannelData = (channels) => {
    if (!channels) return null;
    return Object.entries(channels).map(([ch, data]) => (
      <div key={ch} className="channel-row">
        <span className="channel-name">{ch}</span>
        <div className="channel-metrics">
          {Object.entries(data).map(([key, val]) => {
            // Skip nested objects (bit_plane sub-planes)
            if (typeof val === 'object') return null;
            return (
              <span key={key} className="metric-chip">
                <span className="metric-key">{key.replace(/_/g, ' ')}:</span>
                <span className="metric-val">{typeof val === 'number' ? val.toFixed(4) : val}</span>
              </span>
            );
          })}
        </div>
      </div>
    ));
  };

  return (
    <div className={`method-card ${analysis.verdict === 'Suspicious' ? 'method-suspicious' : 'method-clean'}`}>
      <div className="method-header" onClick={() => setExpanded(!expanded)}>
        <div className="method-title-row">
          <VerdictIcon verdict={analysis.verdict} />
          <span className="method-name">{analysis.method}</span>
          <span className={`method-verdict ${analysis.verdict === 'Suspicious' ? 'text-suspicious' : 'text-clean'}`}>
            {analysis.verdict}
          </span>
        </div>
        <div className="method-summary">
          <ConfidenceBar value={analysis.confidence} verdict={analysis.verdict} />
          <span className="expand-toggle">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div className="method-details">
          <p className="method-description">{analysis.description}</p>

          {/* Key metric summary */}
          {analysis.overall_p_value !== undefined && (
            <div className="key-metric">
              <span>Overall p-value:</span>
              <strong>{analysis.overall_p_value}</strong>
            </div>
          )}
          {analysis.average_payload_estimate !== undefined && (
            <div className="key-metric">
              <span>Estimated payload:</span>
              <strong>{analysis.payload_percentage}%</strong>
            </div>
          )}
          {analysis.average_anomaly_score !== undefined && (
            <div className="key-metric">
              <span>Anomaly score:</span>
              <strong>{analysis.average_anomaly_score}</strong>
            </div>
          )}
          {analysis.average_noise_level !== undefined && (
            <div className="key-metric">
              <span>Avg noise level:</span>
              <strong>{analysis.average_noise_level}</strong>
            </div>
          )}
          {analysis.average_lsb_entropy !== undefined && (
            <div className="key-metric">
              <span>Avg LSB entropy:</span>
              <strong>{analysis.average_lsb_entropy}</strong>
            </div>
          )}

          {/* Per-channel breakdown */}
          {analysis.channels && (
            <div className="channels-section">
              <h4>Per-Channel Breakdown</h4>
              {renderChannelData(analysis.channels)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Steganalysis component ──────────────────────────────────────────────
function Steganalysis() {
  const [selectedImage, setSelectedImage] = useState(null);
  const [imageFile, setImageFile] = useState(null);
  const [imageFiles, setImageFiles] = useState([]);
  const [archiveFile, setArchiveFile] = useState(null);
  const [result, setResult] = useState(null);
  const [batchResult, setBatchResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [password, setPassword] = useState('');
  const [showPasswordInput, setShowPasswordInput] = useState(false);

  const handleImageSelect = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const zip = files.find((f) => f.name.toLowerCase().endsWith('.zip'));
    const imageOnly = files.filter((f) => f.type.startsWith('image/'));

    setResult(null);
    setBatchResult(null);
    setError('');

    if (zip) {
      setArchiveFile(zip);
      setImageFile(null);
      setImageFiles([]);
      setSelectedImage(null);
      return;
    }

    setArchiveFile(null);
    setImageFile(imageOnly[0] || null);
    setImageFiles(imageOnly);

    if (imageOnly[0]) {
      const reader = new FileReader();
      reader.onload = (ev) => setSelectedImage(ev.target.result);
      reader.readAsDataURL(imageOnly[0]);
    } else {
      setSelectedImage(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;

    const zip = files.find((f) => f.name.toLowerCase().endsWith('.zip'));
    const imageOnly = files.filter((f) => f.type.startsWith('image/'));

    setResult(null);
    setBatchResult(null);
    setError('');

    if (zip) {
      setArchiveFile(zip);
      setImageFile(null);
      setImageFiles([]);
      setSelectedImage(null);
      return;
    }

    if (!imageOnly.length) return;
    setArchiveFile(null);
    setImageFile(imageOnly[0] || null);
    setImageFiles(imageOnly);

    const reader = new FileReader();
    reader.onload = (ev) => setSelectedImage(ev.target.result);
    reader.readAsDataURL(imageOnly[0]);
  };

  const handleAnalyze = async () => {
    const hasBatch = archiveFile || imageFiles.length > 1;
    if (!imageFile && !archiveFile && imageFiles.length === 0) {
      setError('Please select image(s) or a ZIP archive to analyse.');
      return;
    }

    setLoading(true);
    setProgress(10);
    setError('');
    setResult(null);
    setBatchResult(null);

    // Fake progress ticks while waiting
    const ticker = setInterval(() => {
      setProgress((p) => (p < 85 ? p + 5 : p));
    }, 300);

    try {
      const formData = new FormData();
      let endpoint = '/api/stego/analyze';

      if (hasBatch) {
        endpoint = '/api/stego/analyze-batch';
        if (archiveFile) {
          formData.append('archive', archiveFile);
        } else {
          imageFiles.forEach((file) => formData.append('images', file));
        }
      } else {
        formData.append('image', imageFile || imageFiles[0]);
      }

      // Add passwords if provided
      if (password) {
        formData.append('passwords', password);
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
      });

      clearInterval(ticker);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error ${response.status}`);
      }

      const data = await response.json();
      setProgress(100);
      if (data.batch) {
        setBatchResult(data);
      } else {
        setResult(data);
      }
    } catch (err) {
      clearInterval(ticker);
      setError(`Analysis failed: ${err.message}`);
      setProgress(0);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setSelectedImage(null);
    setImageFile(null);
    setImageFiles([]);
    setArchiveFile(null);
    setResult(null);
    setBatchResult(null);
    setError('');
    setProgress(0);
  };

  const riskColors = {
    HIGH:   '#ff4444',
    MEDIUM: '#ffaa00',
    LOW:    '#ffdd00',
    CLEAN:  '#00ff88',
  };

  const hexToAscii = (hex) => {
    if (!hex || typeof hex !== 'string') return '';
    const clean = hex.replace(/[^0-9a-fA-F]/g, '');
    if (!clean || clean.length < 2) return '';
    const bytes = clean.length % 2 === 0 ? clean : clean.slice(0, -1);
    let out = '';
    for (let i = 0; i < bytes.length; i += 2) {
      const v = parseInt(bytes.slice(i, i + 2), 16);
      if (Number.isNaN(v)) continue;
      out += (v >= 32 && v <= 126) ? String.fromCharCode(v) : ' ';
    }
    return out.replace(/\s+/g, ' ').trim();
  };

  const renderDecodedPayloadContent = (payload) => {
    if (!payload) return 'No payload information returned by backend.';
    
    // Show decrypted text first if available
    if (payload.decoded_text) {
      // Check if it's our encrypted data format
      if (payload.decoded_text.startsWith('[ENCRYPTED DATA')) {
        return payload.decoded_text;
      }
      return payload.decoded_text;
    }
    if (payload.hex_preview) {
      const ascii = hexToAscii(payload.hex_preview);
      if (ascii) return `Text found: ${ascii}`;
      // Check if this looks like Russian Doll encrypted data (64 char hex = 32 bytes)
      if (payload.hex_preview.length >= 64) {
        return '🔐 RUSSIAN DOLL ENCRYPTED DATA DETECTED\n\n' +
               'This appears to be a Shamir secret share from Russian Doll encryption.\n' +
               'To decrypt this data, you need:\n' +
               '1. At least threshold images from the same batch\n' +
               '2. For older batches only: original password may be required\n\n' +
               'Please use the Steganography → Extract tab with Advanced mode,\n' +
               'or provide all images from the batch in batch analysis mode.\n\n' +
               `Hex data (first 64 chars): ${payload.hex_preview.substring(0, 64)}...`;
      }
      return `Binary payload detected (${payload.bytes_decoded || payload.hex_preview.length / 2} bytes).`;
    }

    const attempts = Array.isArray(payload.attempts) ? payload.attempts : [];
    if (!attempts.length) return 'No hidden payload found and no extraction attempts were returned.';

    const firstSignal = attempts.find((a) => a?.details?.text || a?.details?.hex_preview || a?.error);
    if (!firstSignal) return 'No hidden payload could be decoded from available extraction attempts.';

    if (firstSignal.details?.text) {
      return `Candidate from ${firstSignal.method}: ${firstSignal.details.text}`;
    }
    if (firstSignal.details?.hex_preview) {
      return `Candidate binary from ${firstSignal.method} (hex preview): ${firstSignal.details.hex_preview}`;
    }
    if (firstSignal.error) {
      return `Extraction attempt ${firstSignal.method} failed: ${firstSignal.error}`;
    }
    return 'No hidden payload could be decoded from available extraction attempts.';
  };

  return (
    <div className="steganalysis-page">
      <div className="page-header">
        <h1>🔬 Steganalysis</h1>
        <p>Detect hidden data in images using advanced statistical analysis techniques</p>
      </div>

      <div className="steganalysis-layout">
        {/* ── Left panel: upload + controls ── */}
        <div className="sa-left-panel">
          <div className="sa-card">
            <h2>Upload Image</h2>

            <div
              className={`sa-drop-zone ${selectedImage ? 'has-image' : ''}`}
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
            >
              <input
                type="file"
                accept="image/*,.zip,application/zip"
                id="sa-file-input"
                className="sa-file-input"
                multiple
                onChange={handleImageSelect}
              />
              <label htmlFor="sa-file-input" className="sa-file-label">
                {selectedImage ? (
                  <img src={selectedImage} alt="Selected" className="sa-preview" />
                ) : (
                  <div className="sa-drop-placeholder">
                    <span className="sa-drop-icon">🔍</span>
                    <span className="sa-drop-text">Drop image(s) or ZIP here or click to browse</span>
                    <span className="sa-drop-hint">PNG, JPG, BMP, TIFF, WEBP and ZIP supported</span>
                  </div>
                )}
              </label>
            </div>

            {(archiveFile || imageFile || imageFiles.length > 0) && (
              <div className="sa-file-info">
                {archiveFile ? (
                  <>
                    <span>ZIP: {archiveFile.name}</span>
                    <span>{(archiveFile.size / 1024).toFixed(1)} KB</span>
                  </>
                ) : imageFiles.length > 1 ? (
                  <>
                    <span>{imageFiles.length} images selected</span>
                    <span>{(imageFiles.reduce((acc, f) => acc + f.size, 0) / 1024).toFixed(1)} KB</span>
                  </>
                ) : imageFile ? (
                  <>
                    <span>File: {imageFile.name}</span>
                    <span>{(imageFile.size / 1024).toFixed(1)} KB</span>
                  </>
                ) : null}
              </div>
            )}

            <div className="sa-actions">
              <button className="btn btn-secondary" onClick={handleClear} disabled={loading}>
                Clear
              </button>
              <button
                className="btn btn-primary sa-analyze-btn"
                onClick={handleAnalyze}
                disabled={loading || (!archiveFile && !imageFile && imageFiles.length === 0)}
              >
                {loading ? '⏳ Analysing…' : '🔬 Run Steganalysis'}
              </button>
            </div>

            {loading && (
              <div className="sa-progress-wrap">
                <div className="sa-progress-bar">
                  <div className="sa-progress-fill" style={{ width: `${progress}%` }} />
                </div>
                <span className="sa-progress-label">Running {progress < 30 ? 'Chi-Square' : progress < 50 ? 'RS Analysis' : progress < 65 ? 'Histogram' : progress < 80 ? 'Noise & Sample Pair' : 'Bit-Plane'} analysis…</span>
              </div>
            )}

            {error && <div className="sa-error">{error}</div>}

            {/* Password input for decryption */}
            <div style={{ marginTop: '15px' }}>
              <label 
                style={{ cursor: 'pointer', color: '#4ade80', fontSize: '14px' }}
                onClick={() => setShowPasswordInput(!showPasswordInput)}
              >
                🔐 {showPasswordInput ? 'Hide' : 'Show'} Password for Decryption
              </label>
              {showPasswordInput && (
                <input
                  type="password"
                  className="input-field"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password(s) separated by comma to decrypt Russian Doll layers"
                  style={{ marginTop: '8px' }}
                />
              )}
            </div>
          </div>

          {/* ── Technique info cards ── */}
          <div className="sa-card sa-info-card">
            <h3>🧪 Analysis Techniques</h3>
            <ul className="sa-technique-list">
              <li>
                <span className="technique-icon">χ²</span>
                <div>
                  <strong>Chi-Square Attack</strong>
                  <p>Tests LSB pair frequency distribution for non-randomness</p>
                </div>
              </li>
              <li>
                <span className="technique-icon">RS</span>
                <div>
                  <strong>RS Analysis</strong>
                  <p>Estimates payload fraction via regular/singular pixel groups</p>
                </div>
              </li>
              <li>
                <span className="technique-icon">📊</span>
                <div>
                  <strong>Histogram Analysis</strong>
                  <p>Detects bin-pair equalisation caused by LSB embedding</p>
                </div>
              </li>
              <li>
                <span className="technique-icon">〰</span>
                <div>
                  <strong>Noise Estimation (DWT)</strong>
                  <p>Measures HH sub-band noise increase from embedding</p>
                </div>
              </li>
              <li>
                <span className="technique-icon">⊞</span>
                <div>
                  <strong>Sample Pair Analysis</strong>
                  <p>Analyses adjacent pixel pair ratios for embedding traces</p>
                </div>
              </li>
              <li>
                <span className="technique-icon">⬛</span>
                <div>
                  <strong>Bit-Plane Analysis</strong>
                  <p>Measures LSB plane entropy — stego images approach 1.0</p>
                </div>
              </li>
            </ul>
          </div>
        </div>

        {/* ── Right panel: results ── */}
        <div className="sa-right-panel">
          {!result && !batchResult && !loading && (
            <div className="sa-empty-state">
              <span className="sa-empty-icon">🔬</span>
              <h3>No Analysis Yet</h3>
              <p>Upload an image and click <strong>Run Steganalysis</strong> to detect hidden data.</p>
            </div>
          )}

          {batchResult && (
            <div className="sa-card">
              <h3>Batch Analysis Summary</h3>
              <div className="sa-meta-grid">
                <div className="sa-meta-item">
                  <span className="sa-meta-label">Total Images</span>
                  <span className="sa-meta-value">{batchResult.total_images}</span>
                </div>
                <div className="sa-meta-item">
                  <span className="sa-meta-label">Suspicious</span>
                  <span className="sa-meta-value">{batchResult.suspicious_images}</span>
                </div>
                <div className="sa-meta-item">
                  <span className="sa-meta-label">Clean</span>
                  <span className="sa-meta-value">{batchResult.clean_images}</span>
                </div>
              </div>
              {batchResult.decrypted_text && (
                <div
                  style={{
                    marginTop: '14px',
                    padding: '14px',
                    background: 'rgba(0, 255, 136, 0.12)',
                    border: '2px solid #00ff88',
                    borderRadius: '10px',
                    color: '#00ff88',
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'anywhere',
                    fontWeight: 'bold',
                  }}
                >
                  ✅ BATCH DECRYPTED MESSAGE:
                  <br /><br />
                  {batchResult.decrypted_text}
                </div>
              )}
              {!batchResult.decrypted_text && batchResult.decryption_status === 'failed' && (
                <div
                  style={{
                    marginTop: '14px',
                    padding: '12px',
                    background: 'rgba(255, 68, 68, 0.12)',
                    border: '1px solid #ff4444',
                    borderRadius: '10px',
                    color: '#ff6b6b',
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'anywhere',
                  }}
                >
                  Decryption failed: {batchResult.decryption_error || 'Insufficient threshold shares or invalid payload set.'}
                </div>
              )}
              <div style={{ marginTop: '12px', overflowX: 'auto' }}>
                <table className="sa-summary-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Verdict</th>
                      <th>Risk</th>
                      <th>Confidence</th>
                      <th>Hidden Data</th>
                      <th>Decrypted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(batchResult.results || []).map((r) => (
                      <tr key={r.filename} className={r.overall?.verdict === 'Suspicious' ? 'row-suspicious' : 'row-clean'}>
                        <td>{r.filename}</td>
                        <td>{r.overall?.verdict || 'Unknown'}</td>
                        <td>{r.overall?.risk_level || 'N/A'}</td>
                        <td>{typeof r.overall?.average_confidence === 'number' ? `${r.overall.average_confidence.toFixed(1)}%` : 'N/A'}</td>
                        <td style={{ maxWidth: '340px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                          {r.decoded_payload?.decoded_text
                            ? r.decoded_payload.decoded_text
                            : (r.decoded_payload?.hex_preview
                                ? (hexToAscii(r.decoded_payload.hex_preview) || 'Binary payload present (non-readable)')
                                : (r.decoded_payload?.found ? 'Hidden payload detected (non-text)' : 'No payload decoded'))}
                        </td>
                        <td style={{ maxWidth: '200px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', color: r.decrypted_text ? '#00ff88' : (r.decryption_status === 'failed' ? '#ff6b6b' : 'inherit') }}>
                          {r.decrypted_text 
                            ? r.decrypted_text 
                            : r.decryption_status === 'failed' 
                              ? (r.decryption_error || 'Decryption failed')
                              : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {result && (
            <>
              {/* Overall verdict banner */}
              <div
                className="sa-verdict-banner"
                style={{ borderColor: riskColors[result.overall.risk_level] }}
              >
                <div className="sa-verdict-left">
                  <RiskBadge level={result.overall.risk_level} />
                  <h2 className="sa-verdict-text">{result.overall.verdict}</h2>
                  <p className="sa-verdict-sub">
                    {result.overall.suspicious_methods} of {result.overall.total_methods} methods flagged suspicious
                  </p>
                </div>
                <div className="sa-verdict-right">
                  <div className="sa-confidence-circle">
                    <svg viewBox="0 0 36 36" className="sa-donut">
                      <path
                        className="sa-donut-bg"
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                      <path
                        className="sa-donut-fill"
                        strokeDasharray={`${result.overall.average_confidence}, 100`}
                        style={{ stroke: riskColors[result.overall.risk_level] }}
                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      />
                      <text x="18" y="20.35" className="sa-donut-text">
                        {result.overall.average_confidence.toFixed(0)}%
                      </text>
                    </svg>
                    <span className="sa-donut-label">Avg Confidence</span>
                  </div>
                </div>
              </div>

              {/* Image metadata */}
              <div className="sa-card sa-meta-card">
                <h3>📐 Image Information</h3>
                <div className="sa-meta-grid">
                  <div className="sa-meta-item">
                    <span className="sa-meta-label">Dimensions</span>
                    <span className="sa-meta-value">{result.image_info.width} × {result.image_info.height} px</span>
                  </div>
                  <div className="sa-meta-item">
                    <span className="sa-meta-label">Total Pixels</span>
                    <span className="sa-meta-value">{result.image_info.total_pixels.toLocaleString()}</span>
                  </div>
                  <div className="sa-meta-item">
                    <span className="sa-meta-label">Channels</span>
                    <span className="sa-meta-value">RGB (3)</span>
                  </div>
                  <div className="sa-meta-item">
                    <span className="sa-meta-label">Max Capacity</span>
                    <span className="sa-meta-value">{result.image_info.estimated_capacity_kb} KB</span>
                  </div>
                </div>
              </div>

              {result.decoded_payload && (
                <div className="sa-card">
                  <h3>Decoded Hidden Data</h3>
                  <div className="sa-meta-grid">
                    <div className="sa-meta-item">
                      <span className="sa-meta-label">Found</span>
                      <span className="sa-meta-value">{result.decoded_payload.found ? 'Yes' : 'No'}</span>
                    </div>
                    <div className="sa-meta-item">
                      <span className="sa-meta-label">Method</span>
                      <span className="sa-meta-value">{result.decoded_payload.method || 'N/A'}</span>
                    </div>
                    <div className="sa-meta-item">
                      <span className="sa-meta-label">Confidence</span>
                      <span className="sa-meta-value">
                        {typeof result.decoded_payload.confidence === 'number'
                          ? `${result.decoded_payload.confidence.toFixed(1)}%`
                          : 'N/A'}
                      </span>
                    </div>
                    <div className="sa-meta-item">
                      <span className="sa-meta-label">Encoding</span>
                      <span className="sa-meta-value">{result.decoded_payload.encoding || 'N/A'}</span>
                    </div>
                    <div className="sa-meta-item">
                      <span className="sa-meta-label">Hex Preview</span>
                      <span className="sa-meta-value">
                        {result.decoded_payload.hex_preview
                          ? `${Math.min(result.decoded_payload.hex_preview.length / 2, 64)} bytes`
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                  <div
                    className="sa-error"
                    style={{ marginTop: '10px', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
                  >
                    {renderDecodedPayloadContent(result.decoded_payload)}
                  </div>
                  
                  {/* Decryption result section */}
                  {result.decrypted_text && (
                    <div
                      style={{
                        marginTop: '15px',
                        padding: '15px',
                        background: 'rgba(0, 255, 136, 0.12)',
                        border: '2px solid #00ff88',
                        borderRadius: '10px',
                        color: '#00ff88',
                        fontSize: '16px',
                        fontWeight: 'bold',
                        whiteSpace: 'pre-wrap',
                        overflowWrap: 'anywhere',
                      }}
                    >
                      ✅ DECRYPTED MESSAGE:
                      <br/><br/>
                      {result.decrypted_text}
                    </div>
                  )}
                  
                  {result.decryption_status === 'failed' && result.decryption_error && (
                    <div
                      style={{
                        marginTop: '15px',
                        padding: '15px',
                        background: 'rgba(255, 68, 68, 0.12)',
                        border: '2px solid #ff4444',
                        borderRadius: '10px',
                        color: '#ff6b6b',
                        fontSize: '14px',
                      }}
                    >
                      ❌ Decryption Failed: {result.decryption_error}
                      <br/>
                      <span style={{ fontSize: '12px', opacity: 0.8 }}>
                        The data was found but could not be decrypted. Make sure you have the correct password(s).
                      </span>
                    </div>
                  )}
                  {result.decoded_payload.hex_preview && (
                    <div
                      style={{
                        marginTop: '10px',
                        padding: '10px',
                        background: 'rgba(0, 212, 255, 0.08)',
                        border: '1px solid rgba(0, 212, 255, 0.28)',
                        borderRadius: '8px',
                        color: '#8be9ff',
                        fontSize: '12px',
                        whiteSpace: 'pre-wrap',
                        overflowWrap: 'anywhere',
                      }}
                    >
                      ASCII from HEX: {hexToAscii(result.decoded_payload.hex_preview) || 'No readable ASCII text found'}
                    </div>
                  )}
                  <details style={{ marginTop: '10px' }}>
                    <summary style={{ cursor: 'pointer', color: '#9aa4b2' }}>Raw decoded payload (debug)</summary>
                    <pre
                      style={{
                        marginTop: '8px',
                        padding: '10px',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: '8px',
                        color: '#e6edf3',
                        fontSize: '12px',
                        whiteSpace: 'pre-wrap',
                        overflowWrap: 'anywhere',
                      }}
                    >
                      {JSON.stringify(result.decoded_payload || {}, null, 2)}
                    </pre>
                  </details>
                </div>
              )}

              {/* Method results */}
              <div className="sa-card">
                <h3>📋 Detailed Analysis Results</h3>
                <div className="sa-methods-list">
                  {Object.values(result.analyses).map((analysis) => (
                    <MethodCard key={analysis.method} analysis={analysis} />
                  ))}
                </div>
              </div>

              {/* Summary table */}
              <div className="sa-card">
                <h3>📊 Summary Table</h3>
                <table className="sa-summary-table">
                  <thead>
                    <tr>
                      <th>Method</th>
                      <th>Verdict</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.values(result.analyses).map((a) => (
                      <tr key={a.method} className={a.verdict === 'Suspicious' ? 'row-suspicious' : 'row-clean'}>
                        <td>{a.method}</td>
                        <td>
                          <VerdictIcon verdict={a.verdict} />
                          {' '}{a.verdict}
                        </td>
                        <td>
                          <ConfidenceBar value={a.confidence} verdict={a.verdict} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default Steganalysis;


