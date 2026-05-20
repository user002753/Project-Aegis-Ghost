import React, { useState, useEffect, useCallback } from 'react';
import './Settings.css';
import ipDetectionService from '../security-monitor/services/ipDetection';


function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const [settings, setSettings] = useState(() => {
    const saved = localStorage.getItem('aegisSettings');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error('Failed to parse settings:', e);
      }
    }
    return {
      language: 'en',
      theme: 'dark',
      autoLock: true,
      autoLockTimeout: 5,
      twoFactorAuth: true,
      biometricFallback: true,
      encryptionLevel: '256',
      logActivity: true,
      ipChangeDetection: true,
      ipAlertThreshold: 3,
      trustedIps: [],
      emailNotifications: false,
      pushNotifications: true,
      securityAlerts: true,
      anonymizeData: false,
      shareAnalytics: false
    };
  });

  // IP Detection state
  const [ipStatus, setIpStatus] = useState({
    currentIP: 'Detecting...',
    location: { country: 'Unknown', region: 'Unknown' },
    timestamp: null,
    isMonitoring: false,
    ipHistory: [],
    alertCount: 0
  });
  const [isCheckingIP, setIsCheckingIP] = useState(false);
  const [alertMessage, setAlertMessage] = useState(null);

  // Email test state
  const [testEmail, setTestEmail] = useState('');
  const [testingEmail, setTestingEmail] = useState(false);
  const [emailStatus, setEmailStatus] = useState(null);

  // Handle SMTP test
  const handleSmtpTest = async () => {
    setTestingEmail(true);
    setEmailStatus(null);
    try {
      const response = await fetch('/api/auth/smtp-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: testEmail || null })
      });
      const data = await response.json();
      setEmailStatus(data.message || 'Test email sent!');
    } catch (err) {
      setEmailStatus('Failed to send test email: ' + err.message);
    } finally {
      setTestingEmail(false);
    }
  };

  // Apply theme on mount and when it changes
  useEffect(() => {
    const body = document.body;
    if (settings.theme === 'light') {
      body.classList.add('light-theme');
    } else {
      body.classList.remove('light-theme');
    }
    localStorage.setItem('aegisSettings', JSON.stringify(settings));
  }, [settings.theme]);

  // Initialize IP detection
  useEffect(() => {
    if (settings.ipChangeDetection) {
      ipDetectionService.startMonitoring(5);

      const unsubscribe = ipDetectionService.addListener((event) => {
        if (event.type === 'IP_CHANGED') {
          setAlertMessage({
            type: event.isSuspicious ? 'warning' : 'info',
            message: event.isSuspicious 
              ? `⚠️ Suspicious IP change detected! Previous: ${event.previousIP}, Current: ${event.currentIP}`
              : `📍 IP address changed from ${event.previousIP} to ${event.currentIP}`
          });
          refreshIPStatus();
        }
      });

      refreshIPStatus();

      return () => {
        unsubscribe();
        if (activeTab !== 'ip-detection') {
          ipDetectionService.stopMonitoring();
        }
      };
    }
  }, [settings.ipChangeDetection]);

  const refreshIPStatus = useCallback(async () => {
    setIsCheckingIP(true);
    try {
      const result = await ipDetectionService.checkIPChange();
      if (result.ip) {
        setIpStatus({
          currentIP: result.ip,
          location: result.location,
          timestamp: result.timestamp,
          isMonitoring: ipDetectionService.isMonitoring,
          ipHistory: result.history || ipDetectionService.getHistory(),
          alertCount: ipStatus.alertCount + (result.changed ? 1 : 0)
        });
      }
    } catch (error) {
      console.error('Failed to check IP:', error);
    }
    setIsCheckingIP(false);
  }, [ipStatus.alertCount]);

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    const event = new CustomEvent('settingsSaved', { detail: settings });
    window.dispatchEvent(event);
    alert('Settings saved successfully!');
  };

  const handleReset = () => {
    if (window.confirm('Are you sure you want to reset all settings to defaults?')) {
      setSettings({
        language: 'en',
        theme: 'dark',
        autoLock: true,
        autoLockTimeout: 5,
        twoFactorAuth: true,
        biometricFallback: true,
        encryptionLevel: '256',
        logActivity: true,
        ipChangeDetection: true,
        ipAlertThreshold: 3,
        trustedIps: [],
        emailNotifications: false,
        pushNotifications: true,
        securityAlerts: true,
        anonymizeData: false,
        shareAnalytics: false
      });
    }
  };

  const clearAlert = () => {
    setAlertMessage(null);
  };

  const formatTimestamp = (ts) => {
    if (!ts) return 'Never';
    const date = new Date(ts);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} minutes ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="settings-page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Configure your security preferences and system options</p>
      </div>

      {/* Alert Banner */}
      {alertMessage && (
        <div className={`alert-banner ${alertMessage.type}`}>
          <span>{alertMessage.message}</span>
          <button onClick={clearAlert} className="alert-dismiss">×</button>
        </div>
      )}

      <div className="settings-container">
        <div className="settings-tabs">
          <button 
            className={`settings-tab ${activeTab === 'general' ? 'active' : ''}`}
            onClick={() => setActiveTab('general')}
          >
            ⚙ General
          </button>
          <button 
            className={`settings-tab ${activeTab === 'security' ? 'active' : ''}`}
            onClick={() => setActiveTab('security')}
          >
            🛡 Security
          </button>
          <button 
            className={`settings-tab ${activeTab === 'notifications' ? 'active' : ''}`}
            onClick={() => setActiveTab('notifications')}
          >
            🔔 Notifications
          </button>
          <button 
            className={`settings-tab ${activeTab === 'privacy' ? 'active' : ''}`}
            onClick={() => setActiveTab('privacy')}
          >
            👁 Privacy
          </button>
          <button 
            className={`settings-tab ${activeTab === 'ip-detection' ? 'active' : ''}`}
            onClick={() => setActiveTab('ip-detection')}
          >
            🌐 IP Detection
          </button>
          <button 
            className={`settings-tab ${activeTab === 'email' ? 'active' : ''}`}
            onClick={() => setActiveTab('email')}
          >
            📧 Email
          </button>
        </div>

        <div className="settings-content">
          {activeTab === 'general' && (
            <div className="settings-section">
              <h2>General Settings</h2>
              
              <div className="setting-item">
                <div className="setting-info">
                  <label>Language</label>
                  <p>Select your preferred language</p>
                </div>
                <select 
                  value={settings.language}
                  onChange={(e) => handleChange('language', e.target.value)}
                  className="setting-select"
                >
                  <option value="en">English</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                  <option value="de">Deutsch</option>
                  <option value="zh">中文</option>
                </select>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Theme</label>
                  <p>Choose your preferred color theme</p>
                </div>
                <select 
                  value={settings.theme}
                  onChange={(e) => handleChange('theme', e.target.value)}
                  className="setting-select"
                >
                  <option value="dark">Dark (Default)</option>
                  <option value="light">Light</option>
                  <option value="system">System</option>
                </select>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Auto-Lock</label>
                  <p>Automatically lock session after inactivity</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.autoLock}
                    onChange={(e) => handleChange('autoLock', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              {settings.autoLock && (
                <div className="setting-item">
                  <div className="setting-info">
                    <label>Auto-Lock Timeout</label>
                    <p>Minutes of inactivity before locking</p>
                  </div>
                  <select 
                    value={settings.autoLockTimeout}
                    onChange={(e) => handleChange('autoLockTimeout', parseInt(e.target.value))}
                    className="setting-select"
                  >
                    <option value="1">1 minute</option>
                    <option value="5">5 minutes</option>
                    <option value="10">10 minutes</option>
                    <option value="15">15 minutes</option>
                    <option value="30">30 minutes</option>
                  </select>
                </div>
              )}
            </div>
          )}

          {activeTab === 'security' && (
            <div className="settings-section">
              <h2>Security Settings</h2>
              
              <div className="setting-item">
                <div className="setting-info">
                  <label>Two-Factor Authentication</label>
                  <p>Add an extra layer of security</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.twoFactorAuth}
                    onChange={(e) => handleChange('twoFactorAuth', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Biometric Fallback</label>
                  <p>Allow password login if biometrics fail</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.biometricFallback}
                    onChange={(e) => handleChange('biometricFallback', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Encryption Level</label>
                  <p>Default encryption strength</p>
                </div>
                <select 
                  value={settings.encryptionLevel}
                  onChange={(e) => handleChange('encryptionLevel', e.target.value)}
                  className="setting-select"
                >
                  <option value="128">128-bit</option>
                  <option value="256">256-bit (Recommended)</option>
                  <option value="512">512-bit</option>
                </select>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Activity Logging</label>
                  <p>Record all authentication attempts</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.logActivity}
                    onChange={(e) => handleChange('logActivity', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="settings-section">
              <h2>Notification Preferences</h2>
              
              <div className="setting-item">
                <div className="setting-info">
                  <label>Email Notifications</label>
                  <p>Receive alerts via email</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.emailNotifications}
                    onChange={(e) => handleChange('emailNotifications', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Push Notifications</label>
                  <p>Receive browser push notifications</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.pushNotifications}
                    onChange={(e) => handleChange('pushNotifications', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Security Alerts</label>
                  <p>Immediate alerts for security events</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.securityAlerts}
                    onChange={(e) => handleChange('securityAlerts', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'privacy' && (
            <div className="settings-section">
              <h2>Privacy Settings</h2>
              
              <div className="setting-item">
                <div className="setting-info">
                  <label>Anonymize Data</label>
                  <p>Store biometric data in anonymized form</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.anonymizeData}
                    onChange={(e) => handleChange('anonymizeData', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              <div className="setting-item">
                <div className="setting-info">
                  <label>Share Analytics</label>
                  <p>Help improve the system with anonymous data</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.shareAnalytics}
                    onChange={(e) => handleChange('shareAnalytics', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'ip-detection' && (
            <div className="settings-section">
              <h2>🌐 IP Address Change Detection</h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Monitor for unusual IP address changes that may indicate unauthorized access.
                The system tracks your IP address and alerts you when changes are detected.
              </p>
              
              {/* Alert Configuration */}
              <div className="setting-item">
                <div className="setting-info">
                  <label>Enable IP Change Detection</label>
                  <p>Alert when IP address changes unexpectedly</p>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={settings.ipChangeDetection}
                    onChange={(e) => handleChange('ipChangeDetection', e.target.checked)}
                  />
                  <span className="toggle-slider"></span>
                </label>
              </div>

              {settings.ipChangeDetection && (
                <>
                  {/* Alert Threshold */}
                  <div className="setting-item">
                    <div className="setting-info">
                      <label>Alert Threshold</label>
                      <p>Number of IP changes before triggering alert</p>
                    </div>
                    <select 
                      value={settings.ipAlertThreshold}
                      onChange={(e) => handleChange('ipAlertThreshold', parseInt(e.target.value))}
                      className="setting-select"
                    >
                      <option value="1">1 change</option>
                      <option value="2">2 changes</option>
                      <option value="3">3 changes</option>
                      <option value="5">5 changes</option>
                    </select>
                  </div>

                  {/* Current IP Status with Map */}
                  <div className="ip-status-card">
                    <div className="ip-status-header">
                      <span className="ip-icon">📡</span>
                      <span>Current Session Location</span>
                    </div>
                    
                    {/* Embedded Live Map */}
                    <div style={{ marginBottom: '20px', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(0, 255, 136, 0.3)', height: '280px', background: '#0a0f1a', position: 'relative' }}>
                      {ipStatus.location.latitude && ipStatus.location.longitude ? (
                        <>
                          <iframe 
                            title="IP Location Map"
                            width="100%" 
                            height="100%" 
                            style={{ 
                              border: 0, 
                              filter: settings.theme === 'dark' ? 'invert(100%) hue-rotate(180deg) contrast(110%) brightness(80%) grayscale(20%)' : 'none' 
                            }} 
                            loading="lazy" 
                            allowFullScreen 
                            referrerPolicy="no-referrer-when-downgrade" 
                            src={`https://maps.google.com/maps?q=${ipStatus.location.latitude},${ipStatus.location.longitude}&z=13&output=embed`}
                          ></iframe>
                          {/* Overlay label */}
                          <div style={{ position: 'absolute', bottom: 10, left: 10, background: 'rgba(10, 15, 26, 0.85)', backdropFilter: 'blur(4px)', padding: '6px 12px', borderRadius: '8px', border: '1px solid rgba(0,255,136,0.2)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', background: '#00ff88', boxShadow: '0 0 8px #00ff88' }}></span>
                            <span style={{ color: '#00ff88', fontSize: '13px', fontWeight: 600 }}>Live View</span>
                          </div>
                        </>
                      ) : (
                        <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                          Retrieving grid coordinates...
                        </div>
                      )}
                    </div>
                    
                    <div className="ip-status-content">
                      <div className="ip-main-info-enhanced">
                        <div className="ip-address-box">
                          <span className="ip-label">Current IP</span>
                          <span className="ip-address">{ipStatus.currentIP}</span>
                        </div>
                        <span className={`ip-badge ${ipStatus.isMonitoring ? 'monitoring' : 'paused'}`}>
                          {ipStatus.isMonitoring ? '🟢 Monitoring' : '🔴 Paused'}
                        </span>
                      </div>
                      
                      <div className="ip-metric-grid">
                        <div className="ip-metric-card">
                          <div className="metric-icon">📍</div>
                          <div className="metric-details">
                            <span className="metric-label">Location</span>
                            <span className="metric-value">{ipStatus.location.city || ipStatus.location.region}, {ipStatus.location.country}</span>
                          </div>
                        </div>
                        
                        {ipStatus.location.isp && (
                          <div className="ip-metric-card">
                            <div className="metric-icon">🌐</div>
                            <div className="metric-details">
                              <span className="metric-label">ISP Network</span>
                              <span className="metric-value">{ipStatus.location.isp}</span>
                            </div>
                          </div>
                        )}
                        
                        {ipStatus.location.timezone && (
                          <div className="ip-metric-card">
                            <div className="metric-icon">🕐</div>
                            <div className="metric-details">
                              <span className="metric-label">Timezone</span>
                              <span className="metric-value">{ipStatus.location.timezone}</span>
                            </div>
                          </div>
                        )}
                        
                        <div className="ip-metric-card">
                          <div className="metric-icon">⏱️</div>
                          <div className="metric-details">
                            <span className="metric-label">Last Checked</span>
                            <span className="metric-value">{formatTimestamp(ipStatus.timestamp)}</span>
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                        <button 
                          className="btn btn-refresh"
                          onClick={refreshIPStatus}
                          disabled={isCheckingIP}
                        >
                          {isCheckingIP ? 'Checking...' : '🔄 Refresh IP'}
                        </button>
                        <button 
                          className="btn btn-secondary"
                          onClick={() => {
                            if (navigator.geolocation) {
                              navigator.geolocation.getCurrentPosition(
                                (position) => {
                                  setIpStatus(prev => ({
                                    ...prev,
                                    location: {
                                      ...prev.location,
                                      latitude: position.coords.latitude,
                                      longitude: position.coords.longitude,
                                      city: 'Precise GPS',
                                      region: 'Verified'
                                    }
                                  }));
                                },
                                (err) => alert('Location access denied: ' + err.message)
                              );
                            } else {
                              alert('Geolocation not supported by your browser');
                            }
                          }}
                          style={{ padding: '10px 20px', background: 'rgba(0, 255, 136, 0.1)', border: '1px solid rgba(0, 255, 136, 0.3)', borderRadius: '8px', color: '#00ff88', cursor: 'pointer' }}
                        >
                          🎯 Get Precise Location
                        </button>
                        <button 
                          className="btn btn-primary"
                          onClick={() => {
                            if (navigator.geolocation) {
                              navigator.geolocation.getCurrentPosition(
                                (position) => {
                                  const lat = position.coords.latitude;
                                  const lon = position.coords.longitude;
                                  window.open(`https://earth.google.com/web/@${lat},${lon},500m`, '_blank');
                                },
                                (err) => alert('Could not get location: ' + err.message)
                              );
                            } else {
                              alert('Geolocation not supported');
                            }
                          }}
                          style={{ padding: '10px 20px' }}
                        >
                          🌍 Open Google Earth
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* IP History */}
                  <div className="ip-history-card">
                    <div className="ip-history-header">
                      <span className="history-icon">📋</span>
                      <span>Recent IP Addresses</span>
                    </div>
                    <div className="ip-history-list">
                      {ipStatus.ipHistory.length === 0 ? (
                        <div className="ip-history-empty">
                          <span>No IP history yet. Your IP will be recorded when detection is active.</span>
                        </div>
                      ) : (
                        ipStatus.ipHistory.map((entry, index) => (
                          <div key={index} className="ip-history-item">
                            <div className="ip-info">
                              <span className="ip">{entry.ip}</span>
                              <span className="location">{entry.location.region}, {entry.location.country}</span>
                            </div>
                            <div className="ip-meta">
                              <span className="timestamp">{formatTimestamp(entry.timestamp)}</span>
                              <span className="badge">{index === 0 ? 'Current' : 'Previous'}</span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    {ipStatus.ipHistory.length > 0 && (
                      <div className="ip-history-actions">
                        <button 
                          className="btn btn-clear"
                          onClick={() => {
                            ipDetectionService.clearHistory();
                            setIpStatus(prev => ({ ...prev, ipHistory: [], alertCount: 0 }));
                          }}
                        >
                          Clear History
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Security Tips */}
                  <div className="ip-tips">
                    <h4>💡 Security Tips</h4>
                    <ul>
                      <li>Enable IP detection to receive alerts about suspicious login locations</li>
                      <li>VPN or proxy usage may cause frequent IP changes</li>
                      <li>Your IP address is never shared with third parties</li>
                      <li>Detection runs automatically in the background when enabled</li>
                    </ul>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'email' && (
            <div className="settings-section">
              <h2>📧 Email / SMTP Configuration</h2>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Test your SMTP configuration for the forgot password feature. 
                Currently running in <strong>MOCK mode</strong> - emails are printed to the server console.
              </p>
              
              <div className="setting-item">
                <div className="setting-info">
                  <label>Test Recipient Email</label>
                  <p>Email address to receive the test message</p>
                </div>
                <input
                  type="email"
                  className="setting-input"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="your@email.com"
                  style={{ width: '200px', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                />
              </div>

              <div className="setting-item">
                <button 
                  className="btn btn-primary"
                  onClick={handleSmtpTest}
                  disabled={testingEmail}
                  style={{ marginTop: '10px' }}
                >
                  {testingEmail ? '⏳ Sending...' : '📤 Send Test Email'}
                </button>
              </div>

              {emailStatus && (
                <div className={`status-message ${emailStatus.includes('success') || emailStatus.includes('sent') || emailStatus.includes('Mock') || emailStatus.includes('console') ? 'success' : 'error'}`} style={{ 
                  padding: '12px', 
                  borderRadius: '6px', 
                  marginTop: '15px',
                  background: emailStatus.includes('success') || emailStatus.includes('sent') || emailStatus.includes('Mock') || emailStatus.includes('console') ? 'rgba(0,255,136,0.1)' : 'rgba(255,0,0,0.1)',
                  border: `1px solid ${emailStatus.includes('success') || emailStatus.includes('sent') || emailStatus.includes('Mock') || emailStatus.includes('console') ? 'rgba(0,255,136,0.3)' : 'rgba(255,0,0,0.3)'}`,
                  color: emailStatus.includes('success') || emailStatus.includes('sent') || emailStatus.includes('Mock') || emailStatus.includes('console') ? '#00ff88' : '#ff4444'
                }}>
                  {emailStatus}
                </div>
              )}

              <div className="ip-tips" style={{ marginTop: '30px' }}>
                <h4>💡 Current Mode: MOCK</h4>
                <ul>
                  <li>Emails are printed to the server console (terminal)</li>
                  <li>No external service or API key required</li>
                  <li>To use real email, update .env with SMTP credentials</li>
                  <li>For Mailtrap: create free account at mailtrap.io</li>
                  <li>For Gmail: use App Password (16 characters)</li>
                </ul>
              </div>
            </div>
          )}

          <div className="settings-actions">
            <button className="btn btn-secondary" onClick={handleReset}>
              Reset to Defaults
            </button>
            <button className="btn btn-primary" onClick={handleSave}>
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Settings;
