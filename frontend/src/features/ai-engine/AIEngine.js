import React, { useEffect, useState } from 'react';
import './AIEngine.css';
import { API_BASE_URL } from '../../config';

function AIEngine() {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [providerStatus, setProviderStatus] = useState(null);
  const [provider, setProvider] = useState('auto');
  const [history, setHistory] = useState([
    { role: 'system', content: 'AI Engine connected. Submit a prompt for technical/security analysis.' },
  ]);

  const prompts = [
    'Analyze current security posture',
    'Review API auth and key handling risks',
    'Find high-priority vulnerabilities',
    'Suggest secure architecture improvements',
    'Review upload and CORS attack surface',
  ];

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const r = await fetch(`${API_BASE_URL}/api/ai/providers`);
        const d = await r.json();
        setProviderStatus(d?.providers || {});
      } catch (e) {
        setProviderStatus({ error: true });
      }
    };
    loadProviders();
  }, []);

  const handleSubmit = async (customPrompt = null) => {
    const prompt = (customPrompt || input || '').trim();
    if (!prompt) return;

    setIsLoading(true);
    const newHistory = [...history, { role: 'user', content: prompt }];
    setHistory(newHistory);
    setInput('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/ai/assist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          provider,
          max_tokens: 700,
        }),
      });
      const data = await response.json();

      if (!response.ok || data?.status !== 'success') {
        throw new Error(data?.detail || 'Advisor request failed');
      }

      const reply = `Provider: ${data.provider || 'unknown'}\n\n${data.text || 'No response'}`;

      setHistory([...newHistory, { role: 'assistant', content: reply }]);
    } catch (err) {
      setHistory([...newHistory, { role: 'assistant', content: `Request failed: ${err.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClear = () => {
    setHistory([{ role: 'system', content: 'AI Engine connected. Submit a prompt for technical/security analysis.' }]);
  };

  const providerText = providerStatus?.error
    ? 'Provider status unavailable'
    : providerStatus
      ? `Groq: ${providerStatus.groq ? 'ON' : 'OFF'} | OpenRouter: ${providerStatus.openrouter ? 'ON' : 'OFF'} | Puter: ${providerStatus.puter ? 'ON' : 'OFF'} | OpenAI: ${providerStatus.openai ? 'ON' : 'OFF'} | Raphael: ${providerStatus.raphael ? 'ON' : 'OFF'}`
      : 'Loading provider status...';

  return (
    <div className="ai-engine-page">
      <div className="page-header">
        <h1>AI Engine</h1>
        <p>Live technical and security vulnerability analysis</p>
      </div>

      <div className="ai-content">
        <div className="ai-main">
          <div className="ai-chat">
            <div className="chat-history">
              {history.map((message, index) => (
                <div key={index} className={`chat-message ${message.role}`}>
                  <div className="message-avatar">
                    {message.role === 'system' && '⚙'}
                    {message.role === 'user' && '👤'}
                    {message.role === 'assistant' && '❈'}
                  </div>
                  <div className="message-content">{message.content}</div>
                </div>
              ))}
              {isLoading && (
                <div className="chat-message assistant">
                  <div className="message-avatar">❈</div>
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="chat-input">
              <select
                className="input-field"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                style={{ marginBottom: '8px' }}
              >
                <option value="auto">Auto</option>
                <option value="groq">Groq</option>
                <option value="openrouter">OpenRouter</option>
                <option value="openai">OpenAI</option>
              </select>
              <input
                type="text"
                className="input-field"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask for vulnerability analysis, threat modeling, or remediation..."
                onKeyPress={(e) => e.key === 'Enter' && handleSubmit()}
              />
              <button className="btn btn-primary" onClick={() => handleSubmit()} disabled={isLoading || !input.trim()}>
                Send
              </button>
            </div>
          </div>
        </div>

        <div className="ai-sidebar">
          <div className="quick-prompts">
            <h3>Quick Prompts</h3>
            {prompts.map((prompt, index) => (
              <button key={index} className="prompt-btn" onClick={() => handleSubmit(prompt)} disabled={isLoading}>
                {prompt}
              </button>
            ))}
          </div>

          <div className="ai-stats">
            <h3>Provider Status</h3>
            <div className="stat-item">
              <span>{providerText}</span>
            </div>
            <div className="stat-item">
              <span>Endpoint</span>
              <span className="stat-value">/api/ai/assist</span>
            </div>
          </div>

          <div className="ai-actions">
            <button className="btn btn-secondary" onClick={handleClear} disabled={isLoading}>
              Clear History
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AIEngine;
