import React, { useState, useRef, useEffect } from 'react';
import { API_BASE_URL } from '../../config';
import '../pattern-recognition/BiometricAuth.css';

function FaceAuth({ onSuccess, embedded = false }) {
  const [status, setStatus] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [result, setResult] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const framesRef = useRef([]);
  const animationRef = useRef(null);

  const startCamera = async () => {
    setStatus('Accessing camera...');
    setResult(null);
    framesRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        setStatus('Looking at camera...');
        setIsScanning(true);
      }
    } catch (error) {
      console.error('Camera error:', error);
      const errorMsg = error?.message || '';
      let msg = 'Camera access denied. ';
      if (errorMsg.includes('Permission denied') || errorMsg.includes('NotAllowedError')) {
        msg += 'Please allow camera access in your browser settings. ';
        msg += 'Look for a camera icon in the address bar and click it to grant permission.';
      } else if (errorMsg.includes('NotFoundError') || errorMsg.includes('DevicesNotFoundError')) {
        msg += 'No camera found. Please connect a camera and try again.';
      } else if (errorMsg.includes('NotReadableError') || errorMsg.includes('TrackStartError')) {
        msg += 'Camera is in use by another app. Please close other apps using the camera.';
      } else {
        msg += 'Check that your camera is connected and you have granted permission.';
      }
      setStatus(msg);
    }
  };

  const stopCamera = () => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setIsScanning(false);
  };

  // Continuously capture frames naturally (no user instructions)
  const captureFramesAutomatically = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState !== 4) {
      animationRef.current = requestAnimationFrame(captureFramesAutomatically);
      return;
    }

    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    // Capture frame every ~400ms (natural movements will happen during this time)
    const now = Date.now();
    const frames = framesRef.current;
    if (frames.length === 0 || now - frames[frames.length - 1].timestamp > 400) {
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      frames.push({ 
        timestamp: now, 
        imageData,
        blob: null // will convert to blob later
      });
    }

    // Stop after capturing 5 frames (~2 seconds of natural movement)
    if (frames.length >= 5) {
      verifyWithFrames();
      return;
    }

    animationRef.current = requestAnimationFrame(captureFramesAutomatically);
  };

  const verifyWithFrames = async () => {
    setStatus('Verifying...');
    
    try {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      const frames = framesRef.current;

      // Convert frames to blobs
      const formData = new FormData();
      for (let i = 0; i < frames.length; i++) {
        canvas.width = frames[i].imageData.width;
        canvas.height = frames[i].imageData.height;
        ctx.putImageData(frames[i].imageData, 0, 0);
        
        const blob = await new Promise(resolve => {
          canvas.toBlob(resolve, 'image/jpeg', 0.95);
        });
        formData.append('images', blob, `frame_${i}.jpg`);
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/face/verify`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || `Verification failed (${response.status})`);
      }

      const success = Boolean(data.matched && data.liveness_passed && data.num_faces === 1);
      setResult({
        success,
        message: success
          ? 'Face authentication passed.'
          : (data.reason || 'Authentication failed.'),
        distance: typeof data.distance === 'number' ? data.distance.toFixed(4) : 'N/A',
      });
      setStatus(success ? 'Authentication successful.' : 'Authentication failed.');
    } catch (error) {
      setResult({ success: false, message: error.message, distance: 'N/A' });
      setStatus('Authentication failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAuthenticate = () => {
    if (!isScanning || isSubmitting) return;
    setIsSubmitting(true);
    setResult(null);
    framesRef.current = [];
    setStatus('Verifying - just look at the camera...');
    captureFramesAutomatically();
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      stopCamera();
    };
  }, []);

  return (
    <div className="biometric-page">
      <div className="page-header">
        <h1>Face Recognition</h1>
        <p>Simple face verification with automatic liveness detection</p>
      </div>

      <div className="biometric-content">
        <div className="biometric-card">
          <div className="video-container">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={isScanning ? 'scanning' : ''}
            />
            <canvas ref={canvasRef} style={{ display: 'none' }} />
            {!isScanning && (
              <div className="video-placeholder">
                <span className="placeholder-icon">📷</span>
                <p>Camera inactive</p>
              </div>
            )}
            {isScanning && (
              <div className="face-frame">
                <div className="face-indicator"></div>
              </div>
            )}
          </div>

          <div className="biometric-controls">
            {!isScanning ? (
              <button className="btn btn-primary" onClick={startCamera}>
                Start Camera
              </button>
            ) : (
              <button className="btn btn-secondary" onClick={stopCamera}>
                Stop Camera
              </button>
            )}

            {isScanning && (
              <button
                className="btn btn-primary"
                onClick={handleAuthenticate}
                disabled={isSubmitting}
              >
                {isSubmitting ? 'Verifying...' : 'Verify Face'}
              </button>
            )}
          </div>

          {status && <div className={`biometric-status ${result?.success ? 'success' : ''}`}>{status}</div>}

          {result && (
            <div className={`biometric-result ${result.success ? 'success' : 'error'}`}>
              <div className="result-header">
                <span className="result-icon">{result.success ? '✓' : '✗'}</span>
                <span className="result-message">{result.message}</span>
              </div>
              <div className="result-details">
                <span>Face Match Score: {result.distance}</span>
              </div>
            </div>
          )}
        </div>

        <div className="biometric-info">
          <h3>How it works</h3>
          <ul>
            <li>Look at the camera naturally</li>
            <li>Blinking and natural movements are detected automatically</li>
            <li>Your registered face is verified with automatic liveness detection</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default FaceAuth;
