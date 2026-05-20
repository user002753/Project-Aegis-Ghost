import React, { useState, useRef, useEffect, useCallback } from 'react';
import './BiometricAuth.css';
import { API_BASE_URL } from '../../config';

function PatternRecognition({ onSuccess, embedded = false }) {
  const [mode, setMode] = useState(embedded ? 'authenticate' : 'authenticate');
  const [status, setStatus] = useState('👆 Draw a pattern by connecting the dots');
  const [isDrawing, setIsDrawing] = useState(false);
  const [result, setResult] = useState(null);
  const [points, setPoints] = useState([]);
  const [enrolledPattern, setEnrolledPattern] = useState(null);
  const [serverRegistered, setServerRegistered] = useState(false);
  const [registering, setRegistering] = useState(false);
  const canvasRef = useRef(null);
  const lastPointRef = useRef(null);
  const gridSize = 3;
  const canvasSize = 360;
  const cellSize = canvasSize / gridSize;

  // Get user email from localStorage
  const getUserEmail = () => {
    try {
      const session = JSON.parse(localStorage.getItem('aegisSession') || '{}');
      return session.email || '';
    } catch {
      return '';
    }
  };

  // Initialize with saved pattern or demo
  useEffect(() => {
    const savedPattern = localStorage.getItem('aegisPattern');
    if (savedPattern) {
      setEnrolledPattern(JSON.parse(savedPattern));
    } else {
      // Demo enrolled pattern - a simple but recognizable L shape
      setEnrolledPattern([
        { x: 60, y: 60 },
        { x: 60, y: 180 },
        { x: 60, y: 300 },
        { x: 180, y: 300 },
        { x: 300, y: 300 }
      ]);
    }
  }, []);

  const getGridPoint = useCallback((x, y) => {
    // Larger snap area for easier drawing
    const snapRadius = cellSize * 0.6;
    const gridX = Math.round((x - cellSize/2) / cellSize) * cellSize + cellSize/2;
    const gridY = Math.round((y - cellSize/2) / cellSize) * cellSize + cellSize/2;
    
    // Check if within snap radius of any grid point
    for (let gx = cellSize/2; gx <= canvasSize - cellSize/2; gx += cellSize) {
      for (let gy = cellSize/2; gy <= canvasSize - cellSize/2; gy += cellSize) {
        const dist = Math.sqrt((x - gx)**2 + (y - gy)**2);
        if (dist < snapRadius) {
          return { x: gx, y: gy };
        }
      }
    }
    
    return { 
      x: Math.max(cellSize/2, Math.min(canvasSize - cellSize/2, gridX)),
      y: Math.max(cellSize/2, Math.min(canvasSize - cellSize/2, gridY))
    };
  }, [cellSize, canvasSize]);

  const drawPattern = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw gradient background
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, '#1a1a2e');
    gradient.addColorStop(1, '#0f0f1a');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw subtle grid lines
    ctx.strokeStyle = 'rgba(0, 255, 136, 0.08)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= gridSize; i++) {
      ctx.beginPath();
      ctx.moveTo(i * cellSize, 0);
      ctx.lineTo(i * cellSize, canvasSize);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * cellSize);
      ctx.lineTo(canvasSize, i * cellSize);
      ctx.stroke();
    }
    
    // Draw grid points with enhanced visibility
    for (let x = 0; x < gridSize; x++) {
      for (let y = 0; y < gridSize; y++) {
        const px = x * cellSize + cellSize/2;
        const py = y * cellSize + cellSize/2;
        
        // Outer glow ring (larger for easier visibility)
        ctx.beginPath();
        ctx.arc(px, py, 28, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 255, 136, 0.08)';
        ctx.fill();
        
        // Mid glow
        ctx.beginPath();
        ctx.arc(px, py, 20, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 255, 136, 0.15)';
        ctx.fill();
        
        // Inner dot
        ctx.beginPath();
        ctx.arc(px, py, 12, 0, Math.PI * 2);
        ctx.fillStyle = '#00ff88';
        ctx.fill();
        
        // Center highlight
        ctx.beginPath();
        ctx.arc(px, py, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
      }
    }
    
    // Draw current pattern with smooth animated line
    if (points.length > 0) {
      // Draw glow effect for the entire path
      if (points.length > 1) {
        ctx.strokeStyle = 'rgba(0, 255, 136, 0.5)';
        ctx.lineWidth = 20;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
          ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.stroke();
        
        // Draw main line
        ctx.strokeStyle = '#00ff88';
        ctx.lineWidth = 8;
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
          ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.stroke();
      }
      
      // Highlight connected points with numbers
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      for (let i = 0; i < points.length; i++) {
        const point = points[i];
        
        // Outer glow
        ctx.beginPath();
        ctx.arc(point.x, point.y, 18, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(0, 255, 136, 0.6)';
        ctx.fill();
        
        // Inner point
        ctx.beginPath();
        ctx.arc(point.x, point.y, 12, 0, Math.PI * 2);
        ctx.fillStyle = '#00ff88';
        ctx.fill();
        ctx.stroke();
        
        // Number indicator
        ctx.fillStyle = '#000000';
        ctx.font = 'bold 14px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(i + 1, point.x, point.y);
      }
    }
  }, [points, cellSize, canvasSize, gridSize]);

  useEffect(() => {
    drawPattern();
  }, [drawPattern]);

  const handleMouseDown = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    
    const gridPoint = getGridPoint(x, y);
    setIsDrawing(true);
    lastPointRef.current = gridPoint;
    setPoints([gridPoint]);
    setStatus('🔗 Keep connecting dots...');
    setResult(null);
  };

  const handleMouseMove = (e) => {
    if (!isDrawing) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    
    const gridPoint = getGridPoint(x, y);
    
    const lastPoint = lastPointRef.current;
    if (lastPoint && (gridPoint.x !== lastPoint.x || gridPoint.y !== lastPoint.y)) {
      setPoints(prev => [...prev, gridPoint]);
      lastPointRef.current = gridPoint;
      setStatus(`🔗 ${points.length + 1} dots connected`);
    }
  };

  const handleMouseUp = () => {
    if (isDrawing) {
      setIsDrawing(false);
      if (points.length < 3) {
        setStatus('⚠️ Too short! Connect at least 3 dots.');
      } else {
        setStatus(`✓ Pattern drawn with ${points.length} dots. Ready to ${mode === 'authenticate' ? 'verify' : 'enroll'}!`);
      }
    }
  };

  const handleTouchStart = (e) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches[0];
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (touch.clientX - rect.left) * scaleX;
    const y = (touch.clientY - rect.top) * scaleY;
    
    const gridPoint = getGridPoint(x, y);
    setIsDrawing(true);
    lastPointRef.current = gridPoint;
    setPoints([gridPoint]);
    setStatus('🔗 Keep connecting...');
    setResult(null);
  };

  const handleTouchMove = (e) => {
    e.preventDefault();
    if (!isDrawing) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches[0];
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (touch.clientX - rect.left) * scaleX;
    const y = (touch.clientY - rect.top) * scaleY;
    
    const gridPoint = getGridPoint(x, y);
    const lastPoint = lastPointRef.current;
    if (lastPoint && (gridPoint.x !== lastPoint.x || gridPoint.y !== lastPoint.y)) {
      setPoints(prev => [...prev, gridPoint]);
      lastPointRef.current = gridPoint;
    }
  };

  const handleTouchEnd = (e) => {
    e.preventDefault();
    setIsDrawing(false);
    if (points.length < 3) {
      setStatus('⚠️ Too short! Connect at least 3 dots.');
    } else {
      setStatus(`✓ ${points.length} dots - Ready!`);
    }
  };

  const calculateSimilarity = (p1, p2) => {
    if (p1.length !== p2.length) return 0;
    if (p1.length === 0) return 0;
    
    let totalDistance = 0;
    for (let i = 0; i < p1.length; i++) {
      const dx = p1[i].x - p2[i].x;
      const dy = p1[i].y - p2[i].y;
      totalDistance += Math.sqrt(dx * dx + dy * dy);
    }
    
    const avgDistance = totalDistance / p1.length;
    const maxDistance = canvasSize;
    const similarity = Math.max(0, 1 - avgDistance / maxDistance);
    
    return similarity;
  };

  const handleAuthenticate = async () => {
    if (points.length < 3) {
      setStatus('⚠️ Please draw a longer pattern (at least 3 dots).');
      return;
    }
    
    setStatus('🔄 Analyzing pattern...');
    
    // First verify with server
    const email = getUserEmail();
    if (email) {
      try {
        const patternString = points.map(p => `${Math.round(p.x)},${Math.round(p.y)}`).join('|');
        const response = await fetch(`${API_BASE_URL}/api/auth/pattern/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, pattern: patternString }),
        });
        const data = await response.json();
        if (data.matched) {
          setStatus('✅ Server verified - Authentication successful!');
          setResult({
            success: true,
            message: '🎉 Pattern recognized! Access granted!',
            similarity: 100,
            complexity: points.length > 8 ? 'Very High' : points.length > 5 ? 'High' : points.length > 3 ? 'Medium' : 'Basic'
          });
          if (onSuccess) {
            setTimeout(() => onSuccess(), 1000);
          }
          return;
        }
      } catch (e) {
        console.log('Server verification failed, trying local:', e);
      }
    }
    
    // Fallback to local verification if server fails or user not logged in
    await new Promise(resolve => setTimeout(resolve, 600));
    
    let success = false;
    let similarity = 0;
    
    if (enrolledPattern) {
      similarity = calculateSimilarity(points, enrolledPattern);
      success = similarity > 0.40; // Lower threshold for easier authentication
    } else {
      success = points.length >= 3;
    }
    
    const complexity = points.length > 8 ? 'Very High' : points.length > 5 ? 'High' : points.length > 3 ? 'Medium' : 'Basic';
    
    setResult({
      success,
      message: success 
        ? '🎉 Pattern recognized! Access granted!' 
        : '❌ Pattern not recognized. Try again.',
      similarity: Math.round(similarity * 100),
      complexity
    });
    
    setStatus(success ? '✅ Authentication successful!' : '❌ Authentication failed');
    
    // Call onSuccess callback if provided and authentication succeeded
    if (success && onSuccess) {
      setTimeout(() => {
        onSuccess();
      }, 1000);
    }
  };

  const handleClear = () => {
    setPoints([]);
    setStatus('👆 Draw a pattern by connecting dots');
    setResult(null);
  };

  const handleEnroll = async () => {
    if (points.length < 3) {
      setStatus('⚠️ Please draw a longer pattern (at least 3 dots).');
      return;
    }
    
    setStatus('💾 Enrolling pattern...');
    
    // Save to localStorage and state
    setEnrolledPattern([...points]);
    localStorage.setItem('aegisPattern', JSON.stringify(points));
    
    // Try to register with server
    const email = getUserEmail();
    if (email) {
      setRegistering(true);
      try {
        const patternString = points.map(p => `${Math.round(p.x)},${Math.round(p.y)}`).join('|');
        const response = await fetch(`${API_BASE_URL}/api/auth/profile/pattern/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, pattern: patternString }),
        });
        if (response.ok) {
          setServerRegistered(true);
        }
      } catch (e) {
        console.log('Server registration failed, using local only');
      }
      setRegistering(false);
    }
    
    const complexity = points.length > 8 ? 'Very High' : points.length > 5 ? 'High' : points.length > 3 ? 'Medium' : 'Basic';
    
    setResult({
      success: true,
      message: '✅ Pattern enrolled successfully!' + (serverRegistered ? ' (Server registered)' : ''),
      complexity
    });
    
    setStatus('🎉 Pattern saved! Use it to authenticate.');
  };

  const handleDemoPattern = () => {
    // Draw a recognizable demo pattern
    const demoPattern = [
      { x: 60, y: 60 },
      { x: 180, y: 60 },
      { x: 180, y: 180 },
      { x: 60, y: 180 },
      { x: 60, y: 300 },
      { x: 300, y: 300 }
    ];
    setPoints(demoPattern);
    setStatus('📋 Demo pattern loaded. Click "Verify Pattern" to test!');
  };

  const handleQuickEnroll = () => {
    // One-click enrollment with a simple but secure pattern
    const quickPattern = [
      { x: 60, y: 300 },
      { x: 60, y: 180 },
      { x: 60, y: 60 },
      { x: 180, y: 60 },
      { x: 180, y: 180 },
      { x: 180, y: 300 },
      { x: 300, y: 300 },
      { x: 300, y: 60 }
    ];
    setPoints(quickPattern);
    handleEnroll();
  };

  return (
    <div className="biometric-page">
      <div className="page-header">
        <h1>🔐 Pattern Recognition</h1>
        <p>Draw a unique pattern for secure, easy authentication</p>
      </div>

      <div className="biometric-content">
        <div className="tabs">
          <button 
            className={`tab ${mode === 'authenticate' ? 'active' : ''}`}
            onClick={() => { setMode('authenticate'); setStatus('👆 Draw your pattern to authenticate'); setResult(null); }}
          >
            🔑 Authenticate
          </button>
          <button 
            className={`tab ${mode === 'enroll' ? 'active' : ''}`}
            onClick={() => { setMode('enroll'); setStatus('👆 Draw a new pattern to enroll'); setResult(null); }}
          >
            ✏️ Enroll Pattern
          </button>
        </div>

        <div className="biometric-card">
          <div className="pattern-instructions">
            <span className="instruction-icon">{isDrawing ? '🔗' : '👆'}</span>
            <span>{status}</span>
          </div>

          <div className="pattern-canvas-container">
            <canvas
              ref={canvasRef}
              width={canvasSize}
              height={canvasSize}
              className="pattern-canvas"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onTouchStart={handleTouchStart}
              onTouchMove={handleTouchMove}
              onTouchEnd={handleTouchEnd}
            />
          </div>

          <div className="pattern-info-bar">
            <span className="point-count">🔢 {points.length} dots</span>
            {enrolledPattern && mode === 'authenticate' && (
              <span className="pattern-saved">✓ Pattern saved</span>
            )}
          </div>

          <div className="biometric-controls">
            <button className="btn btn-secondary" onClick={handleClear}>
              🗑️ Clear
            </button>
            <button 
              className="btn btn-primary"
              onClick={mode === 'authenticate' ? handleAuthenticate : handleEnroll}
              disabled={points.length < 3}
            >
              {mode === 'authenticate' ? '✅ Verify Pattern' : '💾 Enroll Pattern'}
            </button>
          </div>

          {mode === 'enroll' && !enrolledPattern && (
            <button className="btn btn-quick" onClick={handleQuickEnroll}>
              ⚡ Quick Enroll (One Click)
            </button>
          )}

          {mode === 'authenticate' && !enrolledPattern && (
            <button className="btn btn-demo" onClick={handleDemoPattern}>
              📋 Load Demo Pattern
            </button>
          )}

          {result && (
            <div className={`biometric-result ${result.success ? 'success' : 'error'}`}>
              <div className="result-header">
                <span className="result-icon">{result.success ? '✓' : '✗'}</span>
                <span className="result-message">{result.message}</span>
              </div>
              {result.success && (
                <div className="result-details">
                  <span>Pattern Complexity: {result.complexity}</span>
                  {result.similarity !== undefined && (
                    <span>Match Score: {result.similarity}%</span>
                  )}
                </div>
              )}
              {!result.success && enrolledPattern && (
                <div className="result-hint">
                  <p>💡 Tip: Draw at consistent speed and follow the same path as enrollment.</p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="biometric-info">
          <h3>💡 Creating a Strong Pattern</h3>
          <ul>
            <li>🔹 Connect at least <strong>4 dots</strong> for better security</li>
            <li>🔹 Use <strong>complex shapes</strong> with multiple turns</li>
            <li>🔹 Avoid simple shapes like squares or letters</li>
            <li>🔹 <strong>Dots snap automatically</strong> - just drag through them</li>
            <li>🔹 Draw with <strong>consistent speed</strong> for best recognition</li>
            <li>🔹 <strong>Large touch targets</strong> make it easy on mobile</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default PatternRecognition;
