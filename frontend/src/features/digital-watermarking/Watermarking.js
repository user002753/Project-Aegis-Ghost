import React, { useState, useRef } from 'react';
import './Watermarking.css';
import { API_BASE_URL } from '../../config';

function Watermarking() {
  const [activeTab, setActiveTab] = useState('embed');
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [watermarkText, setWatermarkText] = useState('');
  const [position, setPosition] = useState('bottom-right');
  const [opacity, setOpacity] = useState(0.5);
  const [visible, setVisible] = useState(true);
  const [invisible, setInvisible] = useState(true);
  const [ownerId, setOwnerId] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  
  // New watermark customization options
  const [watermarkColor, setWatermarkColor] = useState('#FFFFFF');
  const [fontSize, setFontSize] = useState(24);
  const [fontFamily, setFontFamily] = useState('Arial');
  const [fontStyle, setFontStyle] = useState('normal');
  const [fontWeight, setFontWeight] = useState('normal');
  const [textShadow, setTextShadow] = useState(false);
  const [rotation, setRotation] = useState(0);
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [logoPosition, setLogoPosition] = useState('top-right');
  const [logoSize, setLogoSize] = useState(50);
  const [logoOpacity, setLogoOpacity] = useState(0.8);
  
  // Doodle/drawing options
  const [doodleMode, setDoodleMode] = useState(false);
  const [doodleColor, setDoodleColor] = useState('#FF0000');
  const [doodleWidth, setDoodleWidth] = useState(3);
  const [doodleShapes, setDoodleShapes] = useState([]);
  const [currentShape, setCurrentShape] = useState(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const canvasRef = useRef(null);
  
  const inputRef = useRef(null);

  const handleFileSelect = (file) => {
    if (file && file.type.startsWith('image/')) {
      setSelectedFile(file);
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      setResult(null);
      setVerificationResult(null);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = () => {
    setDragActive(false);
  };

  const handleEmbed = async () => {
    if (!selectedFile || !watermarkText) {
      alert('Please select an image and enter watermark text');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('image', selectedFile);
    formData.append('watermark_text', watermarkText);
    formData.append('position', position);
    formData.append('opacity', opacity.toString());
    formData.append('font_size', fontSize.toString());
    formData.append('font_family', fontFamily);
    formData.append('font_style', fontStyle);
    formData.append('font_weight', fontWeight);
    formData.append('text_shadow', textShadow.toString());
    formData.append('rotation', rotation.toString());
    formData.append('color', watermarkColor);
    formData.append('visible', visible.toString());
    formData.append('invisible', invisible.toString());
    formData.append('owner_id', ownerId || 'AEGIS-GHOST');
    formData.append('logo_position', logoPosition);
    formData.append('logo_size', logoSize.toString());
    formData.append('logo_opacity', logoOpacity.toString());
    if (logoFile) {
      formData.append('logo_image', logoFile);
    }
    if (doodleMode && canvasRef.current) {
      const doodleBlob = await new Promise((resolve) => {
        canvasRef.current.toBlob((blob) => resolve(blob), 'image/png');
      });
      if (doodleBlob) {
        formData.append('doodle_image', doodleBlob, 'doodle.png');
      }
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/watermark/embed`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      if (data.success) {
        // Download the watermarked image
        const imageUrl = data.output_path.startsWith('http')
          ? data.output_path
          : `${API_BASE_URL}${data.output_path}`;
        const imageResponse = await fetch(imageUrl);
        const blob = await imageResponse.blob();
        const url = URL.createObjectURL(blob);
        
        setResult({
          type: 'success',
          message: 'Watermark embedded successfully!',
          downloadUrl: url,
          metadata: data.metadata
        });
      } else {
        setResult({
          type: 'error',
          message: data.error || 'Failed to embed watermark'
        });
      }
    } catch (error) {
      setResult({
        type: 'error',
        message: 'Connection error. Please try again.'
      });
    }

    setLoading(false);
  };

  const handleVerify = async () => {
    if (!selectedFile) {
      alert('Please select an image to verify');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('image', selectedFile);
    formData.append('expected_owner', ownerId || '');

    try {
      const response = await fetch(`${API_BASE_URL}/api/watermark/verify`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      setVerificationResult(data);
    } catch (error) {
      setVerificationResult({
        verified: false,
        message: 'Connection error. Please try again.'
      });
    }

    setLoading(false);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      alert('Please select an image to analyze');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
      const response = await fetch(`${API_BASE_URL}/api/watermark/analyze`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      setResult({
        type: 'analysis',
        data: data
      });
    } catch (error) {
      setResult({
        type: 'error',
        message: 'Connection error. Please try again.'
      });
    }

    setLoading(false);
  };

  const downloadImage = (url, filename) => {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
  };

  return (
    <div className="watermarking-container">
      <div className="watermarking-header">
        <h1>Digital Watermarking</h1>
        <p>Protect your digital assets with military-grade invisible watermarks</p>
      </div>

      <div className="watermarking-tabs">
        <button 
          className={`tab ${activeTab === 'embed' ? 'active' : ''}`}
          onClick={() => setActiveTab('embed')}
        >
          Embed Watermark
        </button>
        <button 
          className={`tab ${activeTab === 'verify' ? 'active' : ''}`}
          onClick={() => setActiveTab('verify')}
        >
          Verify & Analyze
        </button>
      </div>

      <div className="watermarking-content">
        <div className="file-upload-section">
          <div 
            className={`drop-zone ${dragActive ? 'active' : ''}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => inputRef.current.click()}
          >
            <input 
              ref={inputRef}
              type="file" 
              accept="image/*"
              onChange={(e) => handleFileSelect(e.target.files[0])}
              style={{ display: 'none' }}
            />
            
            {previewUrl ? (
              <div className="preview-container">
                <img src={previewUrl} alt="Preview" className="preview-image" />
                <button 
                  className="remove-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                    setPreviewUrl(null);
                    setResult(null);
                  }}
                >
                  ×
                </button>
              </div>
            ) : (
              <div className="upload-placeholder">
                <span className="upload-icon">🖼️</span>
                <p>Drag & drop an image or click to browse</p>
                <span className="upload-hint">Supports PNG, JPG, JPEG</span>
              </div>
            )}
          </div>
        </div>

        {activeTab === 'embed' && (
          <div className="embed-options">
            <div className="option-group">
              <label>Watermark Text</label>
              <input
                type="text"
                value={watermarkText}
                onChange={(e) => setWatermarkText(e.target.value)}
                placeholder="Enter watermark text (e.g., CONFIDENTIAL)"
              />
            </div>

            {/* Color and Font Options */}
            <div className="option-section">
              <h4>🎨 Text Style</h4>
              <div className="option-row">
                <div className="option-group">
                  <label>Color</label>
                  <div className="color-picker-wrapper">
                    <input
                      type="color"
                      value={watermarkColor}
                      onChange={(e) => setWatermarkColor(e.target.value)}
                      className="color-picker"
                    />
                    <span className="color-value">{watermarkColor}</span>
                  </div>
                </div>

                <div className="option-group">
                  <label>Font Size: {fontSize}px</label>
                  <input
                    type="range"
                    min="8"
                    max="72"
                    value={fontSize}
                    onChange={(e) => setFontSize(parseInt(e.target.value))}
                  />
                </div>
              </div>

              <div className="option-row">
                <div className="option-group">
                  <label>Font Family</label>
                  <select value={fontFamily} onChange={(e) => setFontFamily(e.target.value)}>
                    <option value="Arial">Arial</option>
                    <option value="Helvetica">Helvetica</option>
                    <option value="Times New Roman">Times New Roman</option>
                    <option value="Georgia">Georgia</option>
                    <option value="Verdana">Verdana</option>
                    <option value="Courier New">Courier New</option>
                    <option value="Comic Sans MS">Comic Sans MS</option>
                    <option value="Impact">Impact</option>
                  </select>
                </div>

                <div className="option-group">
                  <label>Rotation: {rotation}°</label>
                  <input
                    type="range"
                    min="-180"
                    max="180"
                    value={rotation}
                    onChange={(e) => setRotation(parseInt(e.target.value))}
                  />
                </div>
              </div>

              <div className="checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={fontStyle === 'italic'}
                    onChange={(e) => setFontStyle(e.target.checked ? 'italic' : 'normal')}
                  />
                  Italic
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={fontWeight === 'bold'}
                    onChange={(e) => setFontWeight(e.target.checked ? 'bold' : 'normal')}
                  />
                  Bold
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={textShadow}
                    onChange={(e) => setTextShadow(e.target.checked)}
                  />
                  Text Shadow
                </label>
              </div>
            </div>

            {/* Logo Upload Options */}
            <div className="option-section">
              <h4>🖼️ Logo Embedding</h4>
              <div className="option-group">
                <label>Upload Logo (PNG with transparency)</label>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/jpg"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setLogoFile(e.target.files[0]);
                      setLogoPreview(URL.createObjectURL(e.target.files[0]));
                    }
                  }}
                />
                {logoPreview && (
                  <div className="logo-preview">
                    <img src={logoPreview} alt="Logo preview" />
                    <button onClick={() => { setLogoFile(null); setLogoPreview(null); }}>Remove</button>
                  </div>
                )}
              </div>
              {logoFile && (
                <>
                  <div className="option-row">
                    <div className="option-group">
                      <label>Logo Position</label>
                      <select value={logoPosition} onChange={(e) => setLogoPosition(e.target.value)}>
                        <option value="top-left">Top Left</option>
                        <option value="top-right">Top Right</option>
                        <option value="bottom-left">Bottom Left</option>
                        <option value="bottom-right">Bottom Right</option>
                        <option value="center">Center</option>
                      </select>
                    </div>
                    <div className="option-group">
                      <label>Logo Size: {logoSize}px</label>
                      <input
                        type="range"
                        min="20"
                        max="200"
                        value={logoSize}
                        onChange={(e) => setLogoSize(parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="option-group">
                    <label>Logo Opacity: {Math.round(logoOpacity * 100)}%</label>
                    <input
                      type="range"
                      min="0.1"
                      max="1"
                      step="0.1"
                      value={logoOpacity}
                      onChange={(e) => setLogoOpacity(parseFloat(e.target.value))}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Doodle/Drawing Options */}
            <div className="option-section">
              <h4>✏️ Doodle/Drawing</h4>
              <div className="checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={doodleMode}
                    onChange={(e) => setDoodleMode(e.target.checked)}
                  />
                  Enable Drawing Mode
                </label>
              </div>
              {doodleMode && (
                <>
                  <div className="option-row">
                    <div className="option-group">
                      <label>Draw Color</label>
                      <div className="color-picker-wrapper">
                        <input
                          type="color"
                          value={doodleColor}
                          onChange={(e) => setDoodleColor(e.target.value)}
                          className="color-picker"
                        />
                      </div>
                    </div>
                    <div className="option-group">
                      <label>Brush Width: {doodleWidth}px</label>
                      <input
                        type="range"
                        min="1"
                        max="20"
                        value={doodleWidth}
                        onChange={(e) => setDoodleWidth(parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="doodle-actions">
                    <button onClick={() => setDoodleShapes([])}>Clear Drawing</button>
                    <button onClick={() => {
                      const canvas = canvasRef.current;
                      if (canvas) {
                        const ctx = canvas.getContext('2d');
                        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                        setDoodleShapes([...doodleShapes, { type: 'canvas', data: imageData }]);
                      }
                    }}>Add Drawing to Watermark</button>
                  </div>
                  <canvas
                    ref={canvasRef}
                    width={400}
                    height={300}
                    className="doodle-canvas"
                    onMouseDown={(e) => {
                      setIsDrawing(true);
                      const ctx = canvasRef.current.getContext('2d');
                      const rect = canvasRef.current.getBoundingClientRect();
                      ctx.beginPath();
                      ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
                    }}
                    onMouseMove={(e) => {
                      if (isDrawing) {
                        const ctx = canvasRef.current.getContext('2d');
                        const rect = canvasRef.current.getBoundingClientRect();
                        ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
                        ctx.strokeStyle = doodleColor;
                        ctx.lineWidth = doodleWidth;
                        ctx.lineCap = 'round';
                        ctx.stroke();
                      }
                    }}
                    onMouseUp={() => setIsDrawing(false)}
                    onMouseLeave={() => setIsDrawing(false)}
                  />
                </>
              )}
            </div>

            <div className="option-group">
              <label>Owner ID (Optional)</label>
              <input
                type="text"
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value)}
                placeholder="Enter owner identifier"
              />
            </div>

            <div className="option-group">
              <label>Position</label>
              <select value={position} onChange={(e) => setPosition(e.target.value)}>
                <option value="top-left">Top Left</option>
                <option value="top-right">Top Right</option>
                <option value="bottom-left">Bottom Left</option>
                <option value="bottom-right">Bottom Right</option>
                <option value="center">Center</option>
              </select>
            </div>

            <div className="option-group">
              <label>Opacity: {Math.round(opacity * 100)}%</label>
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.1"
                value={opacity}
                onChange={(e) => setOpacity(parseFloat(e.target.value))}
              />
            </div>

            <div className="checkbox-group">
              <label>
                <input
                  type="checkbox"
                  checked={visible}
                  onChange={(e) => setVisible(e.target.checked)}
                />
                Visible Watermark
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={invisible}
                  onChange={(e) => setInvisible(e.target.checked)}
                />
                Invisible Watermark (Steganography)
              </label>
            </div>

            <button 
              className="action-btn primary" 
              onClick={handleEmbed}
              disabled={loading || !selectedFile || !watermarkText}
            >
              {loading ? 'Processing...' : 'Embed Watermark'}
            </button>

            {result && (
              <div className={`result-box ${result.type}`}>
                {result.type === 'success' && (
                  <>
                    <p className="result-message">{result.message}</p>
                    <div className="result-actions">
                      <button 
                        className="action-btn"
                        onClick={() => downloadImage(result.downloadUrl, 'watermarked_image.png')}
                      >
                        Download Watermarked Image
                      </button>
                    </div>
                    {result.metadata && (
                      <div className="metadata-info">
                        <h4>Watermark Metadata:</h4>
                        <p>Owner: {result.metadata.owner_id}</p>
                        <p>Timestamp: {result.metadata.timestamp}</p>
                      </div>
                    )}
                  </>
                )}
                {result.type === 'error' && (
                  <p className="result-message">{result.message}</p>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'verify' && (
          <div className="verify-options">
            <div className="option-group">
              <label>Expected Owner ID (Optional)</label>
              <input
                type="text"
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value)}
                placeholder="Enter expected owner for verification"
              />
            </div>

            <div className="action-buttons">
              <button 
                className="action-btn secondary"
                onClick={handleVerify}
                disabled={loading || !selectedFile}
              >
                {loading ? 'Verifying...' : 'Verify Watermark'}
              </button>
              <button 
                className="action-btn secondary"
                onClick={handleAnalyze}
                disabled={loading || !selectedFile}
              >
                {loading ? 'Analyzing...' : 'Forensic Analysis'}
              </button>
            </div>

            {verificationResult && (
              <div className={`result-box ${verificationResult.verified ? 'success' : 'error'}`}>
                <h3>Verification Result</h3>
                <p className="result-status">
                  {verificationResult.verified ? '✓ Watermark Verified' : '✗ No Valid Watermark Found'}
                </p>
                {verificationResult.owner_id && (
                  <p><strong>Owner ID:</strong> {verificationResult.owner_id}</p>
                )}
                {verificationResult.timestamp && (
                  <p><strong>Embedded:</strong> {verificationResult.timestamp}</p>
                )}
                {verificationResult.message && (
                  <p><strong>Note:</strong> {verificationResult.message}</p>
                )}
              </div>
            )}

            {result && result.type === 'analysis' && (
              <div className="result-box analysis">
                <h3>Forensic Analysis Report</h3>
                <div className="analysis-details">
                  <p><strong>Dimensions:</strong> {result.data.dimensions?.join(' × ')}</p>
                  <p><strong>Color Mode:</strong> {result.data.mode}</p>
                  <p><strong>File Hash:</strong> {result.data.file_hash}</p>
                  <p><strong>Noise Level:</strong> {result.data.noise_level?.toFixed(2)}</p>
                  <p><strong>Brightness:</strong> {result.data.brightness?.toFixed(2)}</p>
                  
                  {result.data.anomalies && result.data.anomalies.length > 0 && (
                    <div className="anomalies">
                      <h4>⚠️ Potential Anomalies:</h4>
                      <ul>
                        {result.data.anomalies.map((anomaly, idx) => (
                          <li key={idx}>{anomaly}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Watermarking;
