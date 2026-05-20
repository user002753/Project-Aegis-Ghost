import React, { useState, useEffect, useRef } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './layout/Sidebar';
import Dashboard from './features/dashboard/Dashboard';
import FaceAuth from './features/face-recognition/FaceAuth';
import PatternRecognition from './features/pattern-recognition/PatternRecognition';
import Encryption from './components/encryption/Encryption';
import Steganography from './features/steganography/Steganography';
import Steganalysis from './features/steganalysis/Steganalysis';
import Watermarking from './features/digital-watermarking/Watermarking';
import SecureChat from './features/secure-chat/SecureChat';
import AIEngine from './features/ai-engine/AIEngine';
import SecurityMonitor from './features/security-monitor/SecurityMonitor';
import Settings from './features/settings/Settings';
import Gallery from './features/image-gallery/Gallery';
import Profile from './features/profile/Profile';
import CryptoAdvanced from './components/CryptoAdvanced';
import ShamirStego from './features/shamir-stego/ShamirStego';
import Login from './features/auth/Login';
import ProtectedModule from './components/ProtectedModule';
import './styles/App.css';

// Boot Animation Component
function BootAnimation({ onComplete }) {
  const canvasRef = useRef(null);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    const phases = [
      { delay: 700, phase: 1 },
      { delay: 1500, phase: 2 },
      { delay: 2300, phase: 3 },
      { delay: 3200, phase: 4 },
    ];

    const timers = phases.map((p, i) =>
      setTimeout(() => {
        setPhase(p.phase);
        if (i === phases.length - 1) {
          setTimeout(onComplete, 550);
        }
      }, p.delay)
    );

    return () => timers.forEach(clearTimeout);
  }, [onComplete]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*<>[]{}';
    const fontSize = 14;
    let columns = 0;
    let drops = [];
    let frameId;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      columns = Math.floor(canvas.width / fontSize);
      drops = Array.from({ length: columns }, () => Math.random() * -120);
    };

    const draw = () => {
      ctx.fillStyle = 'rgba(2, 8, 18, 0.09)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = 'rgba(0, 255, 136, 0.65)';
      ctx.font = `${fontSize}px monospace`;

      for (let i = 0; i < drops.length; i += 1) {
        const text = chars.charAt(Math.floor(Math.random() * chars.length));
        const y = drops[i] * fontSize;
        ctx.fillText(text, i * fontSize, y);

        if (y > canvas.height && Math.random() > 0.975) {
          drops[i] = 0;
        } else {
          drops[i] += 1;
        }
      }

      frameId = requestAnimationFrame(draw);
    };

    resize();
    draw();
    window.addEventListener('resize', resize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <div className="boot-animation">
      <canvas ref={canvasRef} className="boot-matrix-canvas"></canvas>
      <div className="boot-overlay"></div>
      <div className="boot-content">
        <div className={`boot-triangle ${phase >= 1 ? 'active' : ''}`}>
          <svg viewBox="0 0 100 100" aria-hidden="true">
            <polygon points="50,8 92,84 8,84" />
            <polygon className="inner" points="50,30 73,72 27,72" />
          </svg>
        </div>
        <div className="boot-progress">
          <div
            className="boot-progress-bar"
            style={{ width: `${(phase / 4) * 100}%` }}
          ></div>
        </div>
        <div className="boot-phases">
          <div className={phase >= 1 ? 'active' : ''}>INITIALIZING</div>
          <div className={phase >= 2 ? 'active' : ''}>SCANNING</div>
          <div className={phase >= 3 ? 'active' : ''}>DECODING</div>
          <div className={phase >= 4 ? 'active' : ''}>READY</div>
        </div>
        <div className="boot-brand">
          <span className="boot-brand-icon">{'\u27C1'}</span>
          <span className="boot-brand-text">Aegis Ghost</span>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState({
    email: '',
    name: '',
    idNo: '',
    profilePicture: '',
  });
  const [booting, setBooting] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    const savedUser = localStorage.getItem('aegisSession');
    if (savedUser) {
      try {
        const user = JSON.parse(savedUser);
        setUser({
          email: user.email || '',
          name: user.name || '',
          idNo: user.idNo || '',
          profilePicture: user.profilePicture || '',
        });
        setIsAuthenticated(true);
      } catch (e) {
        console.error('Failed to parse session:', e);
      }
    }
  }, []);

  const handleBootComplete = () => {
    setBooting(false);
  };

  const handleLogin = (payload) => {
    const normalized = typeof payload === 'object' && payload !== null
      ? {
          email: payload.email || '',
          name: payload.name || '',
          idNo: payload.idNo || '',
          profilePicture: payload.profilePicture || '',
        }
      : {
          email: '',
          name: '',
          idNo: '',
          profilePicture: '',
        };
    setUser(normalized);
    setIsAuthenticated(true);
    // Save session
    localStorage.setItem('aegisSession', JSON.stringify(normalized));
  };

  const handleLogout = () => {
    setUser({ email: '', name: '', idNo: '', profilePicture: '' });
    setIsAuthenticated(false);
    localStorage.removeItem('aegisSession');
  };

  const handleProfileUpdate = (patch) => {
    setUser((prev) => {
      const next = {
        ...prev,
        name: patch?.name ?? prev.name,
        idNo: patch?.idNo ?? prev.idNo,
        profilePicture: patch?.profilePicture ?? prev.profilePicture,
      };
      localStorage.setItem('aegisSession', JSON.stringify(next));
      return next;
    });
  };

  if (booting) {
    return <BootAnimation onComplete={handleBootComplete} />;
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app">
      <Sidebar onLogout={handleLogout} userName={user.name} profilePicture={user.profilePicture} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/biometric/face" element={<FaceAuth user={user} />} />
          <Route path="/biometric/pattern" element={<PatternRecognition />} />
          <Route path="/encryption" element={<Encryption />} />
          <Route path="/steganography" element={<Steganography />} />
          <Route path="/steganalysis" element={<ProtectedModule moduleName="Steganalysis" authType="both"><Steganalysis /></ProtectedModule>} />
          <Route path="/watermarking" element={<Watermarking />} />
          <Route path="/secure-chat" element={<ProtectedModule moduleName="Secure Chat" authType="both"><SecureChat user={user} /></ProtectedModule>} />
          <Route path="/profile" element={<Profile user={user} onProfileUpdate={handleProfileUpdate} />} />
          <Route path="/ai-engine" element={<AIEngine />} />
          <Route path="/security" element={<SecurityMonitor />} />
          <Route path="/crypto-advanced" element={<CryptoAdvanced />} />
          <Route path="/gallery" element={<ProtectedModule moduleName="Image Gallery"><Gallery /></ProtectedModule>} />
          <Route path="/shamir-stego" element={<ShamirStego />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;

