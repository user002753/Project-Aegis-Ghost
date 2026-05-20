import React from 'react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';
import { API_BASE_URL } from '../config';

function Sidebar({ onLogout, userName, profilePicture }) {
  const menuItems = [
    { path: '/dashboard', icon: '◈', label: 'Dashboard' },
    { path: '/biometric/face', icon: '◉', label: 'Face Recognition' },
    { path: '/biometric/pattern', icon: '◇', label: 'Pattern Recognition' },
    { path: '/encryption', icon: '⚿', label: 'Encryption' },
    { path: '/steganography', icon: '✧', label: 'Steganography' },
    { path: '/steganalysis', icon: '🔬', label: 'Steganalysis' },
    { path: '/watermarking', icon: '⌘', label: 'Digital Watermarking' },
    { path: '/gallery', icon: '🖼', label: 'Image Gallery' },
    { path: '/shamir-stego', icon: '🔐', label: 'Shamir-Stego' },
    { path: '/profile', icon: '👤', label: 'Profile' },
    { path: '/secure-chat', icon: '✉', label: 'Secure Chat' },
    { path: '/ai-engine', icon: '❈', label: 'AI Engine' },
    { path: '/crypto-advanced', icon: '🔑', label: 'Crypto Advanced' },
    { path: '/security', icon: '🛡', label: 'Security Monitor' },
    { path: '/settings', icon: '⚙', label: 'Settings' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <span className="logo-icon">⟁</span>
          <span className="logo-text">Aegis Ghost</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">
            {profilePicture ? (
              <img
                src={`${API_BASE_URL}/${String(profilePicture).replace(/^\/+/, '')}`}
                alt="Profile"
                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }}
              />
            ) : '👤'}
          </div>
          <div className="user-details">
            <span className="user-name">{userName || 'Agent'}</span>
            <span className="user-role">Active Operative</span>
          </div>
        </div>
        <button className="logout-btn" onClick={onLogout}>
          <span>←</span> Logout
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
