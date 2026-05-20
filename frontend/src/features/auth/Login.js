import React, { useEffect, useRef, useState } from 'react';
import './Login.css';
import { API_BASE_URL } from '../../config';

async function apiRequest(endpoint, payload) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    const backendHint = API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`;
    throw new Error(`Cannot reach backend server at ${backendHint}. Start API and try again.`);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data?.detail || data?.message || 'Request failed');
  }
  return data;
}

function Login({ onLogin }) {
  const canvasRef = useRef(null);
  const [view, setView] = useState('login');
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [name, setName] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [pendingEmail, setPendingEmail] = useState('');
  const [profileName, setProfileName] = useState('');
  const [profileIdNo, setProfileIdNo] = useState('');
  const [profilePictureFile, setProfilePictureFile] = useState(null);
  
  // Face registration state
  const [faceView, setFaceView] = useState(null); // 'register' after account creation
  const [faceCapturedImage, setFaceCapturedImage] = useState(null);
  const [faceCapturing, setFaceCapturing] = useState(false);
  const videoRef = useRef(null);
  const faceCanvasRef = useRef(null);
  const faceStreamRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const resetMessages = () => {
    setError('');
    setStatus('');
  };

  const normalizedEmail = () => email.trim().toLowerCase();
  const handleMouseMove = (e) => setMousePos({ x: e.clientX, y: e.clientY });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*<>[]{}';
    const fontSize = 14;
    const columns = Math.floor(canvas.width / fontSize);
    const drops = Array.from({ length: columns }, () => Math.random() * -100);

    let animationId;
    const draw = () => {
      ctx.fillStyle = 'rgba(6, 6, 12, 0.08)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      const gradient = ctx.createRadialGradient(mousePos.x, mousePos.y, 0, mousePos.x, mousePos.y, 200);
      gradient.addColorStop(0, 'rgba(0, 255, 136, 0.1)');
      gradient.addColorStop(1, 'transparent');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = '#00ff88';
      ctx.font = `${fontSize}px monospace`;
      for (let i = 0; i < drops.length; i += 1) {
        const text = chars.charAt(Math.floor(Math.random() * chars.length));
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);
        if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
        drops[i] += 1;
      }
      animationId = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
    };
  }, [mousePos]);

  const renderAnimatedBackground = () => (
    <>
      <canvas ref={canvasRef} className="matrix-canvas"></canvas>
      <div className="login-background">
        <div className="bg-grid"></div>
        <div className="glow-orb orb-1"></div>
        <div className="glow-orb orb-2"></div>
      </div>
      <div className="floating-particles">
        {[...Array(20)].map((_, i) => (
          <div key={i} className={`float-particle p-${i}`}></div>
        ))}
      </div>
    </>
  );

  const handleLogin = async (e) => {
    e.preventDefault();
    resetMessages();
    setLoading(true);
    try {
      const emailValue = normalizedEmail();
      const data = await apiRequest('/api/auth/login', { email: emailValue, password });
      if (data.profile_required) {
        setPendingEmail(data.email || emailValue);
        setProfileName(data.name || '');
        setProfileIdNo(data.id_no || '');
        setProfilePictureFile(null);
        setStatus('Profile setup is required before you can proceed.');
        setView('profile');
      } else {
        onLogin({
          email: data.email || emailValue,
          name: data.name || emailValue.split('@')[0],
          idNo: data.id_no || '',
          profilePicture: data.profile_picture || '',
          profileComplete: true,
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteProfile = async (e) => {
    e.preventDefault();
    resetMessages();
    if (!pendingEmail) {
      setError('Missing user context. Please sign in again.');
      setView('login');
      return;
    }
    if (!profilePictureFile) {
      setError('Profile picture is required.');
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('email', pendingEmail);
      formData.append('name', profileName.trim());
      formData.append('id_no', profileIdNo.trim());
      formData.append('profile_picture', profilePictureFile);

      const response = await fetch(`${API_BASE_URL}/api/auth/profile/complete`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Profile setup failed');
      }
      onLogin({
        email: data.email || pendingEmail,
        name: data.name || profileName.trim(),
        idNo: data.id_no || profileIdNo.trim(),
        profilePicture: data.profile_picture || '',
        profileComplete: true,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    resetMessages();
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const data = await apiRequest('/api/auth/register', { email: normalizedEmail(), password, name });
      setStatus(data.message || 'Account created successfully.');
      setPassword('');
      setConfirmPassword('');
      // After successful registration, prompt for face registration
      setPendingEmail(normalizedEmail());
      setProfileName(name);
      setFaceView('register');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    resetMessages();
    setLoading(true);
    try {
      const data = await apiRequest('/api/auth/forgot-password', { email: normalizedEmail() });
      setStatus(data.message || 'OTP sent. Check your server terminal for the code.');
      setView('verify');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSmtpTest = async () => {
    resetMessages();
    setLoading(true);
    try {
      const data = await apiRequest('/api/auth/smtp-test', { email: normalizedEmail() });
      setStatus(data.message || 'SMTP test email sent successfully.');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    resetMessages();
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      const data = await apiRequest('/api/auth/reset-password', {
        email: normalizedEmail(),
        otp: otp.trim(),
        new_password: newPassword,
      });
      setStatus(data.message || 'Password reset successfully.');
      setOtp('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setView('login'), 800);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Face registration functions
  const startFaceCapture = async () => {
    setFaceCapturing(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        faceStreamRef.current = stream;
      }
    } catch (err) {
      console.error('Camera error:', err);
      const errorMsg = err?.message || '';
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
      setError(msg);
      setFaceCapturing(false);
    }
  };

  const stopFaceCapture = () => {
    if (faceStreamRef.current) {
      faceStreamRef.current.getTracks().forEach(track => track.stop());
      faceStreamRef.current = null;
    }
    setFaceCapturing(false);
  };

  const captureFace = () => {
    const video = videoRef.current;
    const canvas = faceCanvasRef.current;
    if (!video || !canvas || video.readyState !== 4) return;
    
    const ctx = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);
    
    canvas.toBlob((blob) => {
      setFaceCapturedImage(blob);
      stopFaceCapture();
    }, 'image/jpeg', 0.95);
  };

  const retakeFace = () => {
    setFaceCapturedImage(null);
    startFaceCapture();
  };

  const handleRegisterFace = async () => {
    if (!faceCapturedImage) {
      setError('Please capture your face first.');
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('email', pendingEmail);
      formData.append('face_image', faceCapturedImage, 'face.jpg');
      
      const response = await fetch(`${API_BASE_URL}/api/auth/profile/face/register`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'Face registration failed');
      }
      
      setStatus('Face registered successfully! You can now sign in.');
      stopFaceCapture();
      setTimeout(() => {
        setFaceView(null);
        setView('login');
      }, 1500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (view === 'login') {
    return (
      <div className="login-container" onMouseMove={handleMouseMove}>
        {renderAnimatedBackground()}
        <div className="login-content">
          <div className="login-header">
            <div className="login-logo">
              <span className="logo-icon">{'\u27C1'}</span>
              <h1>Project Aegis Ghost</h1>
            </div>
            <p className="login-subtitle">Advanced Security System</p>
          </div>

          <form onSubmit={handleLogin} className="auth-form" autoComplete="on">
            <div className="input-group">
              <label>Email Address</label>
              <input type="email" name="email" autoComplete="email" className="input-field" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>

            <div className="input-group">
              <label>Password</label>
              <input type="password" name="password" autoComplete="current-password" className="input-field" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>

            {error && <div className="error-message">{error}</div>}
            {status && <div className="status-message">{status}</div>}

            <button type="submit" className="auth-btn" disabled={loading}>
              {loading ? <span className="spinner"></span> : 'Sign In'}
            </button>
          </form>

          <div className="auth-links">
            <button className="link-btn" onClick={() => { resetMessages(); setView('forgot'); }}>
              Forgot Password?
            </button>
          </div>

          <div className="auth-divider">
            <span>New to Aegis Ghost?</span>
          </div>

          <button className="secondary-btn" onClick={() => { resetMessages(); setView('register'); }}>
            Create Account
          </button>
        </div>
      </div>
    );
  }

  // Face registration view - shown after successful account creation
  if (faceView === 'register') {
    return (
      <div className="login-container" onMouseMove={handleMouseMove}>
        {renderAnimatedBackground()}
        <div className="login-content">
          <div className="login-header">
            <div className="login-logo">
              <span className="logo-icon">📷</span>
              <h1>Register Your Face</h1>
            </div>
            <p className="login-subtitle">Complete account setup by registering your biometric face</p>
          </div>

          <div className="auth-form">
            {!faceCapturedImage ? (
              <>
                <div className="face-capture-container">
                  <div className="video-container" style={{ maxWidth: '320px', margin: '0 auto' }}>
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className={faceCapturing ? 'scanning' : ''}
                    />
                    <canvas ref={faceCanvasRef} style={{ display: 'none' }} />
                    {!faceCapturing && (
                      <div className="video-placeholder">
                        <span className="placeholder-icon">📷</span>
                        <p>Camera inactive</p>
                      </div>
                    )}
                    {faceCapturing && (
                      <div className="face-frame">
                        <div className="face-indicator"></div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="biometric-controls" style={{ marginTop: '20px' }}>
                  {!faceCapturing ? (
                    <button type="button" className="btn btn-primary" onClick={startFaceCapture}>
                      Start Camera
                    </button>
                  ) : (
                    <button type="button" className="btn btn-primary" onClick={captureFace}>
                      Capture Face
                    </button>
                  )}
                  {faceCapturing && (
                    <button type="button" className="btn btn-secondary" onClick={stopFaceCapture} style={{ marginLeft: '10px' }}>
                      Cancel
                    </button>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="face-preview-container" style={{ textAlign: 'center', marginBottom: '20px' }}>
                  <p style={{ marginBottom: '10px', color: '#00ff88' }}>Face captured successfully!</p>
                  <button type="button" className="btn btn-secondary" onClick={retakeFace}>
                    Retake Photo
                  </button>
                </div>
              </>
            )}

            {error && <div className="error-message">{error}</div>}
            {status && <div className="status-message success">{status}</div>}

            <button 
              type="button" 
              className="auth-btn" 
              onClick={handleRegisterFace}
              disabled={!faceCapturedImage || loading}
            >
              {loading ? <span className="spinner"></span> : 'Complete Registration'}
            </button>

            <div className="auth-divider">
              <span>Already registered?</span>
            </div>

            <button className="secondary-btn" onClick={() => { setFaceView(null); setView('login'); }}>
              Sign In
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (view === 'register') {
    return (
      <div className="login-container" onMouseMove={handleMouseMove}>
        {renderAnimatedBackground()}
        <div className="login-content">
          <div className="login-header">
            <div className="login-logo">
              <span className="logo-icon">{'\u27C1'}</span>
              <h1>Create Account</h1>
            </div>
            <p className="login-subtitle">Join the Aegis Ghost security network</p>
          </div>

          <form onSubmit={handleRegister} className="auth-form" autoComplete="on">
            <div className="input-group">
              <label>Full Name</label>
              <input type="text" name="name" autoComplete="name" className="input-field" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>

            <div className="input-group">
              <label>Email Address</label>
              <input type="email" name="email" autoComplete="username email" className="input-field" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>

            <div className="input-group">
              <label>Password</label>
              <input type="password" name="newPassword" autoComplete="new-password" className="input-field" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>

            <div className="input-group">
              <label>Confirm Password</label>
              <input type="password" name="confirmPassword" autoComplete="new-password" className="input-field" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
            </div>

            {error && <div className="error-message">{error}</div>}
            {status && <div className="status-message success">{status}</div>}

            <button type="submit" className="auth-btn" disabled={loading}>
              {loading ? <span className="spinner"></span> : 'Create Account'}
            </button>
          </form>

          <div className="auth-divider">
            <span>Already have an account?</span>
          </div>

          <button className="secondary-btn" onClick={() => { resetMessages(); setView('login'); }}>
            Sign In
          </button>
        </div>
      </div>
    );
  }

  if (view === 'forgot') {
    return (
      <div className="login-container" onMouseMove={handleMouseMove}>
        {renderAnimatedBackground()}
        <div className="login-content">
          <div className="login-header">
            <div className="login-logo">
              <span className="logo-icon">{'\u27C1'}</span>
              <h1>Reset Password</h1>
            </div>
            <p className="login-subtitle">Enter your email to receive OTP</p>
          </div>

          <form onSubmit={handleForgotPassword} className="auth-form" autoComplete="on">
            <div className="input-group">
              <label>Email Address</label>
              <input type="email" name="email" autoComplete="username email" className="input-field" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>

            {error && <div className="error-message">{error}</div>}
            {status && <div className="status-message success">{status}</div>}

            <button type="submit" className="auth-btn" disabled={loading}>
              {loading ? <span className="spinner"></span> : 'Send OTP'}
            </button>
          </form>

          <div className="auth-links">
            <button type="button" className="link-btn" onClick={handleSmtpTest} disabled={loading}>
              Test Gmail SMTP
            </button>
          </div>

          <div className="auth-divider">
            <span>Remember your password?</span>
          </div>

          <button className="secondary-btn" onClick={() => { resetMessages(); setView('login'); }}>
            Sign In
          </button>
        </div>
      </div>
    );
  }

  if (view === 'profile') {
    return (
      <div className="login-container" onMouseMove={handleMouseMove}>
        {renderAnimatedBackground()}
        <div className="login-content">
          <div className="login-header">
            <div className="login-logo">
              <span className="logo-icon">{'\u27C1'}</span>
              <h1>Complete Profile</h1>
            </div>
            <p className="login-subtitle">Full name and profile picture are mandatory. Member ID is optional.</p>
          </div>

          <form onSubmit={handleCompleteProfile} className="auth-form" autoComplete="on">
            <div className="input-group">
              <label>Email Address</label>
              <input type="email" className="input-field" value={pendingEmail} readOnly />
            </div>

            <div className="input-group">
              <label>Full Name</label>
              <input type="text" className="input-field" value={profileName} onChange={(e) => setProfileName(e.target.value)} required />
            </div>

            <div className="input-group">
              <label>Member ID (Optional)</label>
              <input type="text" className="input-field" value={profileIdNo} onChange={(e) => setProfileIdNo(e.target.value)} />
            </div>

            <div className="input-group">
              <label>Profile Picture</label>
              <input
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/webp"
                className="input-field"
                onChange={(e) => setProfilePictureFile(e.target.files?.[0] || null)}
                required
              />
            </div>

            {error && <div className="error-message">{error}</div>}
            {status && <div className="status-message success">{status}</div>}

            <button type="submit" className="auth-btn" disabled={loading}>
              {loading ? <span className="spinner"></span> : 'Save Profile & Continue'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container" onMouseMove={handleMouseMove}>
      {renderAnimatedBackground()}
      <div className="login-content">
        <div className="login-header">
          <div className="login-logo">
            <span className="logo-icon">{'\u27C1'}</span>
            <h1>Verify OTP</h1>
          </div>
          <p className="login-subtitle">Enter the code sent to your email and set a new password</p>
        </div>

        <form onSubmit={handleResetPassword} className="auth-form" autoComplete="on">
          <div className="input-group">
            <label>Email Address</label>
            <input type="email" name="email" autoComplete="username email" className="input-field" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>

          <div className="input-group">
            <label>OTP Code</label>
            <input type="text" name="otp" autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} className="input-field" value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} required />
          </div>

          <div className="input-group">
            <label>New Password</label>
            <input type="password" name="newPassword" autoComplete="new-password" className="input-field" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
          </div>

          <div className="input-group">
            <label>Confirm New Password</label>
            <input type="password" name="confirmNewPassword" autoComplete="new-password" className="input-field" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
          </div>

          {error && <div className="error-message">{error}</div>}
          {status && <div className="status-message success">{status}</div>}

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? <span className="spinner"></span> : 'Reset Password'}
          </button>
        </form>

        <div className="auth-divider">
          <span>Need a new OTP?</span>
        </div>

        <button className="secondary-btn" onClick={() => { resetMessages(); setView('forgot'); }}>
          Resend OTP
        </button>
      </div>
    </div>
  );
}

export default Login;


