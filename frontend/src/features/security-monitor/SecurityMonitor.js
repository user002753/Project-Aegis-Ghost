import React, { useEffect, useState } from 'react';
import './SecurityMonitor.css';
import { API_BASE_URL } from '../../config';

function SecurityMonitor() {
  const [alerts, setAlerts] = useState([]);
  const [userStatus, setUserStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('owner');
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedAlerts, setSelectedAlerts] = useState([]);
  const [deleting, setDeleting] = useState(false);
  const [allUsers, setAllUsers] = useState([]);

  const [advisorLoading, setAdvisorLoading] = useState(false);
  const [advisorError, setAdvisorError] = useState('');
  const [advisorReport, setAdvisorReport] = useState(null);
  const [advisorContext, setAdvisorContext] = useState('');
  const [maxFindings, setMaxFindings] = useState(8);
  const [includeRuntimeContext, setIncludeRuntimeContext] = useState(true);

  useEffect(() => {
    fetchAlerts();
    // Also fetch user status for the current user on mount
    const currentUser = sessionStorage.getItem('user_email') || sessionStorage.getItem('user_id') || 'owner';
    fetchUserStatus(currentUser);
  }, []);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/alerts`);
      const data = await response.json();
      setAlerts(data.alerts || []);
    } catch (error) {
      console.error('Error fetching alerts:', error);
    }
    setLoading(false);
  };

  const fetchUserStatus = async (id) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/status/${id}`);
      const data = await response.json();
      setUserStatus(data);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
    setLoading(false);
  };

  const handleCheckUser = (e) => {
    e.preventDefault();
    fetchUserStatus(userId);
  };

  const toggleAlertSelection = (index) => {
    setSelectedAlerts(prev => {
      if (prev.includes(index)) {
        return prev.filter(i => i !== index);
      } else {
        return [...prev, index];
      }
    });
  };

  const toggleSelectAll = () => {
    if (selectedAlerts.length === alerts.length) {
      setSelectedAlerts([]);
    } else {
      setSelectedAlerts(alerts.map((_, idx) => idx));
    }
  };

  const deleteSelectedAlerts = async () => {
    if (selectedAlerts.length === 0) return;
    
    setDeleting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/security/alerts`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alert_ids: selectedAlerts })
      });
      
      if (response.ok) {
        const newAlerts = alerts.filter((_, idx) => !selectedAlerts.includes(idx));
        setAlerts(newAlerts);
        setSelectedAlerts([]);
      }
    } catch (error) {
      console.error('Error deleting alerts:', error);
    }
    setDeleting(false);
  };

  const runSecurityAdvisor = async () => {
    setAdvisorLoading(true);
    setAdvisorError('');
    setAdvisorReport(null);
    try {
      const composedContext = [
        advisorContext || '',
        userStatus ? `User status snapshot: ${JSON.stringify(userStatus)}` : '',
        alerts?.length ? `Recent alerts snapshot: ${JSON.stringify(alerts.slice(0, 15))}` : '',
      ].filter(Boolean).join('\n');

      const response = await fetch(`${API_BASE_URL}/api/security/advisor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_context: composedContext,
          max_findings: Math.max(1, Math.min(20, Number(maxFindings) || 8)),
          include_runtime_context: Boolean(includeRuntimeContext),
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || 'LLM security analysis failed.');
      }
      setAdvisorReport(data?.report || null);
    } catch (error) {
      setAdvisorError(String(error?.message || 'LLM security analysis failed.'));
    } finally {
      setAdvisorLoading(false);
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return '#ff4444';
      case 'high': return '#ff8800';
      case 'medium': return '#ffaa00';
      case 'low': return '#00aa00';
      default: return '#888';
    }
  };

  const getAlertIcon = (type) => {
    switch (type) {
      case 'rapid_ip_changes': return 'IP';
      case 'impossible_travel': return 'TR';
      case 'multiple_countries': return 'CC';
      default: return 'AL';
    }
  };

  return (
    <div className="security-page">
      <div className="page-header">
        <h1>Security Monitor</h1>
        <p>Track IP changes, detect unusual behavior, and run LLM-based assessments</p>
      </div>

      <div className="security-content">
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`tab ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            User Status
          </button>
          <button
            className={`tab ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => { setActiveTab('alerts'); fetchAlerts(); }}
          >
            Alerts {alerts.length > 0 && <span className="badge">{alerts.length}</span>}
          </button>
          <button
            className={`tab ${activeTab === 'advisor' ? 'active' : ''}`}
            onClick={() => setActiveTab('advisor')}
          >
            AI Advisor
          </button>
        </div>

        {activeTab === 'overview' && (
          <div className="security-card">
            {/* User Status Summary */}
            {userStatus && (
              <div className="user-status-summary" style={{ marginBottom: '20px', padding: '15px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                  <h3 style={{ color: '#fff', margin: 0 }}>👤 Current User Status</h3>
                  <span className={`threat-badge ${userStatus.threat_level}`} style={{ padding: '4px 12px', borderRadius: '4px', fontSize: '12px' }}>
                    {userStatus.threat_level?.toUpperCase() || 'UNKNOWN'} THREAT
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', color: userStatus.status === 'active' ? '#00ff88' : '#ff8800' }}>
                      {userStatus.status === 'active' ? '✓' : '!'}
                    </div>
                    <div style={{ fontSize: '11px', color: '#888' }}>Status</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', color: '#00aaff' }}>
                      {userStatus.login_count || 0}
                    </div>
                    <div style={{ fontSize: '11px', color: '#888' }}>Logins</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '24px', color: '#ff6b6b' }}>
                      {userStatus.failed_attempts || 0}
                    </div>
                    <div style={{ fontSize: '11px', color: '#888' }}>Failed</div>
                  </div>
                </div>
              </div>
            )}

            <div className="security-stats">
              <div className="stat-card">
                <span className="stat-icon">AL</span>
                <span className="stat-value">{alerts.length}</span>
                <span className="stat-label">Total Alerts</span>
              </div>
              <div className="stat-card critical">
                <span className="stat-icon">CR</span>
                <span className="stat-value">{alerts.filter((a) => a.severity === 'critical').length}</span>
                <span className="stat-label">Critical</span>
              </div>
              <div className="stat-card warning">
                <span className="stat-icon">HI</span>
                <span className="stat-value">{alerts.filter((a) => a.severity === 'high').length}</span>
                <span className="stat-label">High Priority</span>
              </div>
              <div className="stat-card safe">
                <span className="stat-icon">OK</span>
                <span className="stat-value">{alerts.filter((a) => a.severity === 'low').length}</span>
                <span className="stat-label">Resolved</span>
              </div>
            </div>

            <div className="security-info">
              <h3>What This Monitors</h3>
              <ul>
                <li><strong>Rapid IP Changes:</strong> Detects if user IP changes too frequently.</li>
                <li><strong>Impossible Travel:</strong> Flags distant logins in short intervals.</li>
                <li><strong>Multiple Countries:</strong> Warns when user accesses from many countries in 24h.</li>
                <li><strong>Unusual Hours:</strong> Monitors access outside expected time windows.</li>
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'users' && (
          <div className="security-card">
            <div className="user-check-form">
              <form onSubmit={handleCheckUser}>
                <input
                  type="text"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="Enter user ID"
                  className="input-field"
                />
                <button type="submit" className="btn btn-primary">Check Status</button>
              </form>
            </div>

            {userStatus && (
              <div className="user-status-detail">
                <div className={`status-header ${userStatus.status}`}>
                  <h3>Status: {String(userStatus.status || '').toUpperCase()}</h3>
                  <span className={`threat-badge ${userStatus.threat_level}`}>
                    Threat Level: {userStatus.threat_level}
                  </span>
                </div>

                <div className="status-details">
                  <div className="detail-row"><span className="detail-label">User ID:</span><span className="detail-value">{userStatus.user_id}</span></div>
                  <div className="detail-row"><span className="detail-label">First Seen:</span><span className="detail-value">{userStatus.first_seen || 'Unknown'}</span></div>
                  <div className="detail-row"><span className="detail-label">Last Seen:</span><span className="detail-value">{userStatus.last_seen || 'Unknown'}</span></div>
                  <div className="detail-row"><span className="detail-label">Total Sessions:</span><span className="detail-value">{userStatus.total_sessions}</span></div>
                  <div className="detail-row"><span className="detail-label">Recent IP Changes:</span><span className="detail-value">{userStatus.recent_ip_count} (24h)</span></div>
                  <div className="detail-row"><span className="detail-label">Countries Accessed:</span><span className="detail-value">{(userStatus.recent_countries || []).join(', ') || 'Unknown'}</span></div>
                </div>

                {userStatus.alert && (
                  <div className="alert-section">
                    <h4>Detected Anomalies</h4>
                    {(userStatus.alert.alerts || []).map((alert, idx) => (
                      <div key={idx} className={`alert-item ${alert.severity}`}>
                        <span className="alert-icon">{getAlertIcon(alert.type)}</span>
                        <div className="alert-content">
                          <span className="alert-type">{String(alert.type || '').replace(/_/g, ' ')}</span>
                          <span className="alert-message">{alert.message}</span>
                        </div>
                        <span className="severity-badge" style={{ backgroundColor: getSeverityColor(alert.severity) }}>
                          {alert.severity}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'alerts' && (
          <div className="security-card">
            <div className="alerts-header">
              <h3>Security Alerts</h3>
              <div className="alerts-actions">
                {alerts.length > 0 && (
                  <button 
                    className="btn btn-secondary" 
                    onClick={toggleSelectAll}
                    style={{ marginRight: '10px' }}
                  >
                    {selectedAlerts.length === alerts.length ? 'Deselect All' : 'Select All'}
                  </button>
                )}
                <button 
                  className="btn btn-danger" 
                  onClick={deleteSelectedAlerts}
                  disabled={selectedAlerts.length === 0 || deleting}
                  style={{ marginRight: '10px', opacity: selectedAlerts.length === 0 ? 0.5 : 1 }}
                >
                  {deleting ? 'Deleting...' : `Delete Selected (${selectedAlerts.length})`}
                </button>
                <button className="btn btn-secondary" onClick={fetchAlerts}>Refresh</button>
              </div>
            </div>

            {loading ? (
              <div className="loading">Loading alerts...</div>
            ) : alerts.length === 0 ? (
              <div className="no-alerts">
                <span className="no-alerts-icon">OK</span>
                <p>No security alerts detected</p>
                <p className="no-alerts-hint">All systems normal</p>
              </div>
            ) : (
              <div className="alerts-list">
                {alerts.map((alert, idx) => (
                  <div key={idx} className={`alert-card ${alert.severity}`}>
                    <div className="alert-select" style={{ marginRight: '12px' }}>
                      <input
                        type="checkbox"
                        checked={selectedAlerts.includes(idx)}
                        onChange={() => toggleAlertSelection(idx)}
                        style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                    </div>
                    <div className="alert-content" style={{ flex: 1 }}>
                      <div className="alert-header">
                        <span className="alert-icon">{getAlertIcon(alert.type)}</span>
                        <span className="alert-type">{String(alert.type || '').replace(/_/g, ' ').toUpperCase()}</span>
                        <span className="severity-tag" style={{ backgroundColor: getSeverityColor(alert.severity) }}>
                          {alert.severity}
                        </span>
                      </div>
                      <div className="alert-body">
                        <p>{alert.message}</p>
                        <span className="alert-time">{alert.timestamp}</span>
                        <span className="alert-user">User: {alert.user_id}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'advisor' && (
          <div className="security-card">
            <div className="alerts-header">
              <h3>LLM Security Advisor</h3>
            </div>

            <div className="advisor-controls">
              <label className="advisor-label" htmlFor="advisor-context">Additional Context</label>
              <textarea
                id="advisor-context"
                className="advisor-textarea"
                rows={5}
                value={advisorContext}
                onChange={(e) => setAdvisorContext(e.target.value)}
                placeholder="Paste deployment notes, architecture snippets, or known incidents."
              />

              <div className="advisor-options">
                <div className="advisor-input-group">
                  <label htmlFor="advisor-findings">Max Findings</label>
                  <input
                    id="advisor-findings"
                    className="input-field"
                    type="number"
                    min="1"
                    max="20"
                    value={maxFindings}
                    onChange={(e) => setMaxFindings(e.target.value)}
                  />
                </div>
                <label className="advisor-checkbox">
                  <input
                    type="checkbox"
                    checked={includeRuntimeContext}
                    onChange={(e) => setIncludeRuntimeContext(e.target.checked)}
                  />
                  Include runtime context
                </label>
              </div>

              <button className="btn btn-primary" onClick={runSecurityAdvisor} disabled={advisorLoading}>
                {advisorLoading ? 'Analyzing...' : 'Run LLM Security Analysis'}
              </button>
            </div>

            {advisorError && <div className="advisor-error">{advisorError}</div>}

            {advisorReport && (
              <div className="advisor-report">
                <div className="advisor-summary">
                  <div><strong>Provider:</strong> {advisorReport.provider || 'unknown'}</div>
                  <div>
                    <strong>Overall Risk:</strong>{' '}
                    <span className={`risk-chip ${String(advisorReport.overall_risk || 'medium').toLowerCase()}`}>
                      {advisorReport.overall_risk || 'medium'}
                    </span>
                  </div>
                </div>

                <p className="advisor-summary-text">{advisorReport.summary || 'No summary provided.'}</p>

                <div className="advisor-findings">
                  {(advisorReport.findings || []).length === 0 ? (
                    <div className="loading">No findings returned.</div>
                  ) : (
                    advisorReport.findings.map((finding, idx) => (
                      <div key={`${finding.title || 'finding'}-${idx}`} className={`advisor-finding ${String(finding.severity || 'low').toLowerCase()}`}>
                        <div className="advisor-finding-head">
                          <span className="advisor-finding-title">{finding.title || 'Untitled Finding'}</span>
                          <span className="severity-tag" style={{ backgroundColor: getSeverityColor(String(finding.severity || 'low').toLowerCase()) }}>
                            {finding.severity || 'low'}
                          </span>
                        </div>
                        <p className="advisor-finding-detail">{finding.details || '-'}</p>
                        <p className="advisor-finding-remediation"><strong>Remediation:</strong> {finding.remediation || '-'}</p>
                      </div>
                    ))
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

export default SecurityMonitor;
