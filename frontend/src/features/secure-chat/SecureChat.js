import React, { useState, useRef, useEffect, useCallback } from 'react';
import './SecureChat.css';
import { API_BASE_URL } from '../../config';

function SecureChat({ user }) {
  const [conversations, setConversations] = useState([]);
  const [activeConversation, setActiveConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [showNewChat, setShowNewChat] = useState(false);
  const [recipientId, setRecipientId] = useState('');
  const [chatName, setChatName] = useState('');
  const [ephemeral, setEphemeral] = useState(false);
  const [destroyTime, setDestroyTime] = useState(60);
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [chatError, setChatError] = useState('');
  const [chatStatus, setChatStatus] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedMessages, setSelectedMessages] = useState([]);
  const [selectMode, setSelectMode] = useState(false);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  const currentUser = (user?.email || user?.name || 'test').trim().toLowerCase();

  // Delete selected messages
  const deleteSelectedMessages = async () => {
    if (selectedMessages.length === 0) return;
    
    if (!window.confirm(`Delete ${selectedMessages.length} selected message(s)? This cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/messages/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_ids: selectedMessages,
          conversation_id: activeConversation?.id,
          user_id: currentUser
        })
      });
      
      if (response.ok) {
        setMessages(messages.filter(msg => !selectedMessages.includes(msg.id)));
        setSelectedMessages([]);
        setSelectMode(false);
      }
    } catch (error) {
      console.error('Error deleting messages:', error);
    }
  };

  // Toggle message selection
  const toggleMessageSelection = (msgId) => {
    if (selectedMessages.includes(msgId)) {
      setSelectedMessages(selectedMessages.filter(id => id !== msgId));
    } else {
      setSelectedMessages([...selectedMessages, msgId]);
    }
  };

  // Toggle select mode
  const toggleSelectMode = () => {
    setSelectMode(!selectMode);
    if (selectMode) {
      setSelectedMessages([]);
    }
  };

  const parseApiResponse = async (response, fallbackMessage) => {
    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    let payload = {};
    if (contentType.includes('application/json')) {
      payload = await response.json().catch(() => ({}));
    } else {
      const rawText = await response.text().catch(() => '');
      payload = { detail: rawText ? rawText.slice(0, 180) : '' };
    }

    if (!response.ok) {
      throw new Error(payload.detail || payload.error || fallbackMessage || `HTTP ${response.status}`);
    }
    if (!contentType.includes('application/json')) {
      throw new Error('Server returned non-JSON response. Restart backend and refresh.');
    }
    return payload;
  };

  const fetchConversations = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/conversations?user_id=${encodeURIComponent(currentUser)}`);
      const data = await parseApiResponse(response, 'Failed to fetch conversations');
      setConversations(data.conversations || []);
      setChatError('');
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
      setChatError(error.message || 'Failed to fetch conversations.');
    }
  }, [currentUser]);

  const fetchMessages = useCallback(async (convId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/messages/${encodeURIComponent(convId)}?user_id=${encodeURIComponent(currentUser)}`);
      const data = await parseApiResponse(response, 'Failed to fetch messages');
      setMessages(data.messages || []);
      setChatStatus(`Synced ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
      setChatError('');
      fetchConversations();
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      setChatError(error.message || 'Failed to fetch messages.');
    }
  }, [currentUser, fetchConversations]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Poll for new messages every 3 seconds while a conversation is active.
  useEffect(() => {
    if (activeConversation) {
      fetchMessages(activeConversation.id);
    }
    const interval = setInterval(() => {
      if (activeConversation) {
        fetchMessages(activeConversation.id);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [activeConversation, fetchMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const createConversation = async () => {
    if (!recipientId.trim()) {
      alert('Please enter a recipient ID');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          participants: [currentUser, recipientId.trim()],
          name: chatName || null
        }),
      });
      const data = await parseApiResponse(response, 'Failed to create conversation');
      if (data.success) {
        setShowNewChat(false);
        setRecipientId('');
        setChatName('');
        setActiveConversation(data.conversation);
        setChatError('');
        fetchConversations();
      } else {
        alert(data.detail || data.error || 'Failed to create conversation');
      }
    } catch (error) {
      const msg = error?.message || 'Connection error. Please try again.';
      setChatError(msg);
      alert(msg);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    if ((!newMessage.trim() && !selectedFile) || !activeConversation) return;

    setLoading(true);
    try {
      // If there's a file selected, send as file
      if (selectedFile) {
        const formData = new FormData();
        formData.append('conversation_id', activeConversation.id);
        formData.append('sender_id', currentUser);
        formData.append('file_name', selectedFile.name);
        formData.append('file_type', selectedFile.type.startsWith('image/') ? 'image' : 'zip');
        formData.append('ephemeral', ephemeral === true);
        formData.append('destroy_after_seconds', ephemeral ? (destroyTime || 60) : '');
        formData.append('file', selectedFile);

        const response = await fetch(`${API_BASE_URL}/api/chat/send-file`, {
          method: 'POST',
          body: formData,
        });

        const data = await parseApiResponse(response, 'Failed to send file');
        if (data.success) {
          setSelectedFile(null);
          if (fileInputRef.current) fileInputRef.current.value = '';
          setNewMessage('');
          setChatError('');
          fetchMessages(activeConversation.id);
        } else {
          alert(data.detail || data.error || 'Failed to send file');
        }
      } else {
        // Send regular text message
        const response = await fetch(`${API_BASE_URL}/api/chat/send`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            conversation_id: activeConversation.id,
            sender_id: currentUser,
            content: newMessage.trim(),
            ephemeral,
            destroy_after_seconds: ephemeral ? destroyTime : null
          }),
        });

        const data = await parseApiResponse(response, 'Failed to send message');
        if (data.success) {
          setNewMessage('');
          setChatError('');
          fetchMessages(activeConversation.id);
        } else {
          alert(data.detail || data.error || 'Failed to send message');
        }
      }
    } catch (error) {
      const msg = error?.message || 'Connection error. Please try again.';
      setChatError(msg);
      alert(msg);
    } finally {
      setLoading(false);
    }
  };

  const destroyConversation = async () => {
    if (!activeConversation) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/conversations/${activeConversation.id}`, {
        method: 'DELETE'
      });
      const data = await parseApiResponse(response, 'Failed to destroy conversation');
      if (!data.success) {
        alert(data.detail || data.error || 'Failed to destroy conversation');
        return;
      }
      setActiveConversation(null);
      setMessages([]);
      setShowSettings(false);
      fetchConversations();
    } catch (error) {
      const msg = error?.message || 'Connection error. Please try again.';
      setChatError(msg);
      alert(msg);
    }
  };

  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      const isImage = file.type.startsWith('image/');
      const isZip = file.type === 'application/zip' || file.type === 'application/x-zip-compressed';
      
      if (!isImage && !isZip) {
        alert('Please select an image or ZIP file');
        return;
      }
      
      if (file.size > 10 * 1024 * 1024) {
        alert('File size must be less than 10MB');
        return;
      }
      
      setSelectedFile(file);
    }
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getFileIcon = (fileType) => {
    if (fileType === 'image') return 'IMG';
    return 'ZIP';
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <div className="secure-chat-container">
      <div className="chat-sidebar">
        <div className="sidebar-header">
          <h2>Secure Conversations</h2>
          <button className="new-chat-btn" onClick={() => setShowNewChat(true)}>+</button>
        </div>

        <div className="conversation-list">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${activeConversation?.id === conv.id ? 'active' : ''}`}
              onClick={() => setActiveConversation(conv)}
            >
              <div className="conv-avatar">
                {conv.is_group ? (
                  <span className="avatar-icon">GRP</span>
                ) : (
                  <span className="avatar-text">{getInitials(conv.name)}</span>
                )}
              </div>
              <div className="conv-info">
                <div className="conv-name">{conv.display_name || conv.name}</div>
                <div className="conv-preview">
                  {Array.isArray(conv.participant_names) && conv.participant_names.length
                    ? conv.participant_names.join(', ')
                    : (conv.last_activity ? formatTime(conv.last_activity) : 'No messages')}
                </div>
              </div>
              {conv.unread_count > 0 && (
                <div className="unread-badge">{conv.unread_count}</div>
              )}
            </div>
          ))}

          {conversations.length === 0 && (
            <div className="empty-conversations">
              <p>No conversations yet</p>
              <p className="hint">Start a new secure chat</p>
            </div>
          )}
        </div>

        <div className="sidebar-footer">
          <div className="security-badge">
            <span className="lock-icon">LOCK</span>
            <span>End-to-End Encrypted</span>
          </div>
        </div>
      </div>

      <div className="chat-area">
        {(chatError || chatStatus) && (
          <div className="chat-runtime-banner-wrap">
            {chatError && <div className="chat-runtime-error">{chatError}</div>}
            {!chatError && chatStatus && <div className="chat-runtime-status">{chatStatus}</div>}
          </div>
        )}
        {activeConversation ? (
          <>
            <div className="chat-header">
              <div className="chat-info">
                <h3>{activeConversation.display_name || activeConversation.name}</h3>
                <span className="participant-count">
                  {Array.isArray(activeConversation.participant_names) && activeConversation.participant_names.length
                    ? activeConversation.participant_names.join(', ')
                    : `${activeConversation.participants?.length || 2} participants`}
                </span>
              </div>
              <div className="chat-actions">
                <button
                  className={`action-icon ${selectMode ? 'active' : ''}`}
                  onClick={toggleSelectMode}
                  title="Select Messages"
                >
                  {selectMode ? '✓' : '✎'}
                </button>
                <button
                  className="action-icon"
                  onClick={() => setShowSettings(!showSettings)}
                  title="Chat Settings"
                >
                  CFG
                </button>
              </div>
            </div>

            {showSettings && (
              <div className="settings-panel">
                <div className="setting-item">
                  <label>Ephemeral Messages</label>
                  <div className="toggle-wrapper">
                    <input
                      type="checkbox"
                      checked={ephemeral}
                      onChange={(e) => setEphemeral(e.target.checked)}
                    />
                    <span>Messages self-destruct after reading</span>
                  </div>
                  {ephemeral && (
                    <div className="time-selector">
                      <label>Destroy after:</label>
                      <select value={destroyTime} onChange={(e) => setDestroyTime(parseInt(e.target.value, 10))}>
                        <option value={10}>10 seconds</option>
                        <option value={30}>30 seconds</option>
                        <option value={60}>1 minute</option>
                        <option value={300}>5 minutes</option>
                        <option value={3600}>1 hour</option>
                      </select>
                    </div>
                  )}
                </div>
                <button
                  className="danger-btn"
                  onClick={() => {
                    if (window.confirm('This will permanently delete this conversation. Continue?')) {
                      destroyConversation();
                    }
                  }}
                >
                  Destroy Conversation
                </button>
              </div>
            )}

            <div className="messages-container">
              {selectMode && (
                <div className="select-mode-toolbar">
                  <button className="select-mode-btn" onClick={toggleSelectMode}>✕ Cancel</button>
                  <span>{selectedMessages.length} selected</span>
                  <button 
                    className="delete-selected-btn" 
                    onClick={deleteSelectedMessages}
                    disabled={selectedMessages.length === 0}
                  >
                    🗑️ Delete Selected
                  </button>
                </div>
              )}
              {messages.map((msg, idx) => (
                <div
                  key={msg.id || idx}
                  className={`message ${msg.sender === currentUser ? 'sent' : 'received'} ${selectedMessages.includes(msg.id) ? 'selected' : ''}`}
                  onClick={() => selectMode && toggleMessageSelection(msg.id)}
                >
                  {selectMode && (
                    <div className="message-checkbox">
                      <input 
                        type="checkbox" 
                        checked={selectedMessages.includes(msg.id)}
                        onChange={() => toggleMessageSelection(msg.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </div>
                  )}
                  <div className="message-content">
                    <div className="message-sender">{msg.sender_name || msg.sender || 'unknown'}</div>
                    {msg.content && msg.content.startsWith('[FILE:') ? (
                      <div className="message-file">
                        {(() => {
                          const fileMatch = msg.content.match(/\[FILE:([^:]+):([^:]+):([^\]]+)\]/);
                          if (fileMatch) {
                            const [, fileType, fileName, fileId] = fileMatch;
                            const fileUrl = `${API_BASE_URL}/api/chat/files/${fileId}`;
                            if (fileType === 'image') {
                              return (
                                <div className="file-attachment">
                                  <img 
                                    src={fileUrl} 
                                    alt={fileName} 
                                    className="message-image"
                                    onError={(e) => e.target.style.display = 'none'}
                                  />
                                  <span className="file-name">{fileName}</span>
                                  <a href={fileUrl} download={fileName} className="download-link">DOWNLOAD</a>
                                </div>
                              );
                            } else {
                              return (
                                <div className="file-attachment">
                                  <span className="file-icon">{getFileIcon(fileType)}</span>
                                  <span className="file-name">{fileName}</span>
                                  <a href={fileUrl} download={fileName} className="download-link">DOWNLOAD</a>
                                </div>
                              );
                            }
                          }
                          return null;
                        })()}
                      </div>
                    ) : (
                      <div className="message-text">{msg.content || msg.error || '[No content]'}</div>
                    )}
                    <div className="message-meta">
                      <span className="message-time">{msg.timestamp ? formatTime(msg.timestamp) : ''}</span>
                      {msg.ephemeral && <span className="ephemeral-badge">EPH</span>}
                      {msg.signature_valid === true && <span className="verified-badge">SIG</span>}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input">
              <div className="input-options">
                <label className="ephemeral-toggle">
                  <input
                    type="checkbox"
                    checked={ephemeral}
                    onChange={(e) => setEphemeral(e.target.checked)}
                  />
                  <span className="toggle-label">{ephemeral ? `TTL ${destroyTime}s` : 'TTL'}</span>
                </label>
                <label className="file-upload-btn" title="Send Image or ZIP">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    accept=".png,.jpg,.jpeg,.gif,.webp,.zip"
                    style={{ display: 'none' }}
                  />
                  <span className="attach-icon">ATTACH</span>
                </label>
              </div>
              {selectedFile && (
                <div className="selected-file-preview">
                  <span className="file-info">
                    {selectedFile.type.startsWith('image/') ? 'IMG' : 'ZIP'}: {selectedFile.name}
                  </span>
                  <button type="button" className="clear-file-btn" onClick={clearSelectedFile}>X</button>
                </div>
              )}
              <textarea
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type a secure message..."
                rows={1}
              />
              <button
                className="send-btn"
                onClick={sendMessage}
                disabled={loading || (!newMessage.trim() && !selectedFile)}
              >
                {loading ? '...' : 'SEND'}
              </button>
            </div>
          </>
        ) : (
          <div className="no-chat-selected">
            <div className="welcome-icon">SECURE</div>
            <h3>Secure Conversations</h3>
            <p>Select a conversation or start a new one</p>
            <p className="security-note">
              All messages are end-to-end encrypted using AES-256-GCM
            </p>
          </div>
        )}
      </div>

      {showNewChat && (
        <div className="modal-overlay" onClick={() => setShowNewChat(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>New Secure Conversation</h3>
              <button className="close-btn" onClick={() => setShowNewChat(false)}>X</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Recipient ID (Email or Username)</label>
                <input
                  type="text"
                  value={recipientId}
                  onChange={(e) => setRecipientId(e.target.value)}
                  placeholder="Enter recipient ID"
                />
              </div>
              <div className="form-group">
                <label>Chat Name (Optional)</label>
                <input
                  type="text"
                  value={chatName}
                  onChange={(e) => setChatName(e.target.value)}
                  placeholder="Give this chat a name"
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="cancel-btn" onClick={() => setShowNewChat(false)}>
                Cancel
              </button>
              <button
                className="create-btn"
                onClick={createConversation}
                disabled={loading}
              >
                {loading ? 'Creating...' : 'Create Secure Chat'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SecureChat;
