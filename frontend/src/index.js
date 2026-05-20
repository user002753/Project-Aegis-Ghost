import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles/index.css';

// Apply saved theme on app start
const savedSettings = localStorage.getItem('aegisSettings');
if (savedSettings) {
  try {
    const settings = JSON.parse(savedSettings);
    if (settings.theme === 'light') {
      document.body.classList.add('light-theme');
    }
  } catch (e) {
    console.error('Failed to apply saved theme:', e);
  }
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
