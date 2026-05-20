import React, { useState, useEffect } from 'react';
import PatternRecognition from '../features/pattern-recognition/PatternRecognition';
import FaceAuth from '../features/face-recognition/FaceAuth';

function ProtectedModule({ children, moduleName, authType = 'pattern' }) {
  // authType: 'pattern' | 'face' | 'both'
  const [isVerified, setIsVerified] = useState(false);
  const [showAuth, setShowAuth] = useState(true);
  const [authMode, setAuthMode] = useState(authType); // 'pattern' | 'face'
  
  // Use module-specific key for sessionStorage (check both pattern and face)
  const patternStorageKey = `patternVerified_${moduleName.replace(/\s+/g, '_').toLowerCase()}`;
  const faceStorageKey = `faceVerified_${moduleName.replace(/\s+/g, '_').toLowerCase()}`;

  useEffect(() => {
    // Check if already verified for this specific module (either pattern or face)
    const patternVerified = sessionStorage.getItem(patternStorageKey);
    const faceVerified = sessionStorage.getItem(faceStorageKey);
    
    if (patternVerified === 'true' || faceVerified === 'true') {
      setIsVerified(true);
      setShowAuth(false);
    }
  }, [patternStorageKey, faceStorageKey]);

  const handlePatternSuccess = () => {
    setIsVerified(true);
    setShowAuth(false);
    // Store module-specific verification
    sessionStorage.setItem(patternStorageKey, 'true');
  };

  const handleFaceSuccess = () => {
    setIsVerified(true);
    setShowAuth(false);
    // Store module-specific verification
    sessionStorage.setItem(faceStorageKey, 'true');
  };

  const handleTryAgain = () => {
    setShowAuth(true);
  };

  const switchAuthMode = (mode) => {
    setAuthMode(mode);
  };

  if (showAuth && !isVerified) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a0f1a 0%, #1a1f2e 100%)',
        color: '#fff',
        padding: '20px'
      }}>
        <div style={{
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          <h2 style={{ 
            fontSize: '24px', 
            marginBottom: '10px',
            color: '#00ff88' 
          }}>
            🔒 Authentication Required
          </h2>
          <p style={{ 
            color: '#8892b0',
            fontSize: '14px'
          }}>
            Complete {authType === 'both' ? 'either' : ''} verification to access {moduleName}
          </p>
        </div>
        
        {/* Auth type switcher when both are enabled */}
        {authType === 'both' && (
          <div style={{ marginBottom: '20px' }}>
            <button 
              onClick={() => switchAuthMode('pattern')}
              style={{
                padding: '8px 20px',
                marginRight: '10px',
                background: authMode === 'pattern' ? '#00ff88' : 'transparent',
                border: '1px solid #00ff88',
                color: authMode === 'pattern' ? '#000' : '#00ff88',
                borderRadius: '5px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              🔐 Pattern
            </button>
            <button 
              onClick={() => switchAuthMode('face')}
              style={{
                padding: '8px 20px',
                background: authMode === 'face' ? '#00ff88' : 'transparent',
                border: '1px solid #00ff88',
                color: authMode === 'face' ? '#000' : '#00ff88',
                borderRadius: '5px',
                cursor: 'pointer',
                fontSize: '14px'
              }}
            >
              👤 Face
            </button>
          </div>
        )}
        
        {authMode === 'pattern' ? (
          <PatternRecognition 
            onSuccess={handlePatternSuccess}
            embedded={true}
          />
        ) : (
          <FaceAuth 
            onSuccess={handleFaceSuccess}
            embedded={true}
          />
        )}
        
        <button 
          onClick={handleTryAgain}
          style={{
            marginTop: '20px',
            padding: '10px 30px',
            background: 'transparent',
            border: '1px solid #00ff88',
            color: '#00ff88',
            borderRadius: '5px',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          Try Again
        </button>
      </div>
    );
  }

  return children;
}

export default ProtectedModule;
