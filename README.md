# Project Aegis Ghost - React Frontend

This is the React frontend for Project Aegis Ghost, a secure biometric authentication and steganography platform.

## Features

- **Modern UI** - Dark theme with neon accents and smooth animations
- **Biometric Authentication** - Face, Voice, and Gesture recognition interfaces
- **Encryption Tool** - AES-256 encryption/decryption functionality
- **Steganography** - Hide secret messages within images
- **AI Engine** - Security analysis chatbot
- **Settings** - Comprehensive configuration options

## Tech Stack

- React 18
- React Router 6
- Axios for API calls
- CSS3 with CSS Variables
- Custom animations

## Getting Started

### Prerequisites

- Node.js 16+ 
- npm or yarn

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

The app will be available at `http://localhost:3000`

### Build for Production

```bash
npm run build
```

The built files will be in the `build/` directory.

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── biometric/
│   │   │   ├── FaceAuth.js
│   │   │   ├── VoiceAuth.js
│   │   │   └── GestureAuth.js
│   │   ├── encryption/
│   │   │   └── Encryption.js
│   │   ├── steganography/
│   │   │   └── Steganography.js
│   │   ├── AIEngine.js
│   │   ├── Dashboard.js
│   │   ├── Login.js
│   │   ├── Settings.js
│   │   └── Sidebar.js
│   ├── services/
│   │   └── api.js
│   ├── styles/
│   │   ├── index.css
│   │   └── App.css
│   ├── App.js
│   └── index.js
├── package.json
└── README.md
```

## API Integration

The frontend communicates with the backend API. Configure the API URL using environment variables:

```env
REACT_APP_API_URL=http://localhost:5000
```

## Customization

### Theme Colors

Edit CSS variables in `src/styles/index.css`:

```css
:root {
  --primary-color: #00ff88;
  --secondary-color: #00d4ff;
  --background-dark: #0a0a0f;
  /* ... */
}
```

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## License

MIT License
