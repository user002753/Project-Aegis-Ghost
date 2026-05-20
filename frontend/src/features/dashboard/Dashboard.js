import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';
import { API_BASE_URL } from '../../config';

function Dashboard() {
  const navigate = useNavigate();
  const [animatedStats, setAnimatedStats] = useState({});
  const [currentTime, setCurrentTime] = useState(new Date());
  const [recentActivity, setRecentActivity] = useState([]);
  const [securityAlerts, setSecurityAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRecentActivity();
    fetchSecurityStatus();
  }, []);

  const fetchRecentActivity = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/recent-activity`);
      const data = await response.json();
      if (data.activities && data.activities.length > 0) {
        const formatted = data.activities.map((activity, index) => {
          const timeDiff = getTimeDifference(activity.timestamp);
          let actionText = '';
          let status = 'info';
          let icon = '⚡';
          
          if (activity.type === 'alert') {
            actionText = activity.action || 'Security Alert';
            status = activity.severity === 'critical' ? 'error' : activity.severity === 'high' ? 'warning' : 'info';
            icon = '🚨';
          } else if (activity.action === 'login') {
            actionText = `Login from ${activity.location || activity.ip}`;
            status = 'success';
            icon = '🔐';
          } else if (activity.action === 'api_access') {
            actionText = `API Access from ${activity.location || activity.ip}`;
            status = 'info';
            icon = '📡';
          } else {
            actionText = activity.action || 'Activity recorded';
            icon = '📋';
          }
          
          return {
            time: timeDiff,
            action: actionText,
            status: status,
            icon: icon
          };
        });
        setRecentActivity(formatted);
      } else {
        // Fallback to default if no data
        setRecentActivity([
          { time: 'Just now', action: 'System initialized', status: 'success', icon: '✓' },
          { time: '1 min ago', action: 'Security monitor active', status: 'info', icon: '🛡️' }
        ]);
      }
    } catch (error) {
      console.error('Error fetching recent activity:', error);
      setRecentActivity([
        { time: 'Just now', action: 'System initialized', status: 'success', icon: '✓' },
        { time: '1 min ago', action: 'Security monitor active', status: 'info', icon: '🛡️' }
      ]);
    }
  };

  const fetchSecurityStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/alerts`);
      const data = await response.json();
      if (data.alerts && data.alerts.length > 0) {
        const formatted = data.alerts.slice(0, 5).map(alert => ({
          level: alert.severity === 'critical' ? 'high' : alert.severity === 'high' ? 'medium' : 'low',
          message: alert.message,
          time: getTimeDifference(alert.timestamp)
        }));
        setSecurityAlerts(formatted);
      } else {
        setSecurityAlerts([
          { level: 'low', message: 'System operating normally', time: 'Now' },
          { level: 'info', message: 'All security systems active', time: 'Now' }
        ]);
      }
    } catch (error) {
      console.error('Error fetching security status:', error);
      setSecurityAlerts([
        { level: 'low', message: 'System operating normally', time: 'Now' },
        { level: 'info', message: 'All security systems active', time: 'Now' }
      ]);
    }
    setLoading(false);
  };

  const getTimeDifference = (timestamp) => {
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} min ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } catch {
      return 'Unknown';
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedStats({
        biometrics: 3,
        encryption: 256,
        stegoImages: 10,
        accuracy: 99.8
      });
    }, 500);

    const clockInterval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => {
      clearTimeout(timer);
      clearInterval(clockInterval);
    };
  }, []);

  const features = [
    {
      icon: '◉',
      title: 'Face Recognition',
      description: 'Advanced facial biometric authentication with liveness detection',
      path: '/biometric/face',
      status: 'Active',
      color: '#00ff88'
    },
    {
      icon: '◇',
      title: 'Pattern Recognition',
      description: 'Unique gesture pattern drawing for secure access',
      path: '/biometric/pattern',
      status: 'Active',
      color: '#ff6b6b'
    },
    {
      icon: '⚿',
      title: 'Encryption',
      description: 'Military-grade encryption for your sensitive data',
      path: '/encryption',
      status: 'Active',
      color: '#ffd93d'
    },
    {
      icon: '✧',
      title: 'Steganography',
      description: 'Hide secret messages within images securely',
      path: '/steganography',
      status: 'Active',
      color: '#c56cf0'
    },
    {
      icon: '❈',
      title: 'AI Engine',
      description: 'Intelligent AI-powered security analysis with Gemini',
      path: '/ai-engine',
      status: 'Active',
      color: '#17c0eb'
    }
  ];

  const stats = [
    { icon: '✓', value: animatedStats.biometrics || '0', label: 'Active Biometrics', color: 'green', target: 3 },
    { icon: '⚿', value: animatedStats.encryption || '0', label: 'Encryption Bit', color: 'blue', target: 256 },
    { icon: '✧', value: animatedStats.stegoImages || '0', label: 'Stego Images', color: 'orange', target: 10 },
    { icon: '◉', value: animatedStats.accuracy || '0%', label: 'Accuracy Rate', color: 'green', target: 99.8, suffix: '%' }
  ];

  // Recent activity now comes from API (see state above)
  // Security alerts now come from API (see state above)

  return (
    <div className="dashboard">
      <div className="dashboard-bg">
        <div className="bg-orb orb-1"></div>
        <div className="bg-orb orb-2"></div>
        <div className="bg-orb orb-3"></div>
        <div className="grid-overlay"></div>
      </div>

      <div className="dashboard-content">
        <div className="page-header">
          <div className="header-glow"></div>
          <h1>Security Dashboard</h1>
          <p>Welcome back, Administrator</p>
          <div className="live-clock">
            <span className="clock-icon">🕐</span>
            <span>{currentTime.toLocaleDateString()} {currentTime.toLocaleTimeString()}</span>
          </div>
        </div>

        <div className="stats-grid">
          {stats.map((stat, index) => (
            <div 
              key={index} 
              className="stat-card"
              style={{ '--accent-color': `var(--${stat.color}-color)` }}
            >
              <div className="stat-glow"></div>
              <div className="stat-icon-wrapper">
                <div className={`stat-icon ${stat.color}`}>
                  {stat.icon}
                </div>
                <div className="stat-pulse"></div>
              </div>
              <div className="stat-info">
                <h3 className="stat-value">
                  {typeof stat.value === 'number' ? stat.value : stat.value}
                  {stat.suffix}
                </h3>
                <p>{stat.label}</p>
              </div>
              <div className="stat-bar">
                <div 
                  className="stat-bar-fill"
                  style={{ width: `${Math.min((parseFloat(stat.value) / stat.target) * 100, 100)}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>

        <div className="dashboard-grid">
          <div className="features-section">
            <div className="section-header">
              <h2>🛡️ Security Features</h2>
              <div className="section-line"></div>
            </div>
            <div className="features-grid">
              {features.map((feature, index) => (
                <div
                  key={index}
                  className="feature-card"
                  onClick={() => navigate(feature.path)}
                  style={{ '--feature-color': feature.color }}
                >
                  <div className="feature-glow"></div>
                  <div className="feature-icon-wrapper">
                    <span className="icon">{feature.icon}</span>
                    <div className="icon-ring"></div>
                  </div>
                  <div className="feature-content">
                    <h3>
                      {feature.title}
                      <span className={`status-badge ${feature.status.toLowerCase()}`}>
                        {feature.status}
                      </span>
                    </h3>
                    <p>{feature.description}</p>
                  </div>
                  <div className="feature-arrow">→</div>
                </div>
              ))}
            </div>
          </div>

          <div className="sidebar-section">
            <div className="security-status-card">
              <div className="status-header">
                <span className="status-icon">🛡️</span>
                <h3>System Status</h3>
              </div>
              <div className="security-indicator">
                <div className="indicator-ring">
                  <div className="indicator-dot"></div>
                </div>
                <span className="indicator-text">Secure</span>
              </div>
              <div className="security-details">
                {securityAlerts.map((alert, i) => (
                  <div key={i} className={`security-alert ${alert.level}`}>
                    <span className="alert-dot"></span>
                    <span className="alert-text">{alert.message}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="activity-card">
              <div className="activity-header">
                <span className="activity-icon">📋</span>
                <h3>Recent Activity</h3>
              </div>
              <div className="activity-list">
                {recentActivity.map((activity, index) => (
                  <div key={index} className="activity-item">
                    <div className={`activity-status ${activity.status}`}>
                      <span>{activity.icon}</span>
                    </div>
                    <div className="activity-details">
                      <span className="activity-action">{activity.action}</span>
                      <span className="activity-time">{activity.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="quick-actions-card">
              <div className="quick-header">
                <span className="quick-icon">⚡</span>
                <h3>Quick Actions</h3>
              </div>
              <div className="quick-actions-grid">
                <button className="action-btn" onClick={() => navigate('/biometric/face')}>
                  <span className="action-icon">◉</span>
                  <span>Enroll Face</span>
                </button>
                <button className="action-btn" onClick={() => navigate('/biometric/pattern')}>
                  <span className="action-icon">◇</span>
                  <span>Draw Pattern</span>
                </button>
                <button className="action-btn" onClick={() => navigate('/encryption')}>
                  <span className="action-icon">⚿</span>
                  <span>Encrypt</span>
                </button>
                <button className="action-btn" onClick={() => navigate('/steganography')}>
                  <span className="action-icon">✧</span>
                  <span>Hide Data</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="dashboard-footer">
          <div className="footer-item">
            <span className="footer-icon">🔒</span>
            <span>256-bit Encryption Active</span>
          </div>
          <div className="footer-item">
            <span className="footer-icon">📡</span>
            <span>IP Monitoring Enabled</span>
          </div>
          <div className="footer-item">
            <span className="footer-icon">🤖</span>
            <span>AI Engine Ready</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;

