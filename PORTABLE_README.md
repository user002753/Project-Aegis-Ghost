# Project Aegis Ghost - Portable Distribution

## Quick Start for End Users

### Option 1: Windows (Easiest)
1. Double-click `LAUNCH_PORTABLE.bat`
2. The app will open in your browser at http://localhost:8000

### Option 2: Manual Start
```bash
# Install dependencies
pip install -r requirements.txt

# Build frontend (if not built)
cd frontend && npm install && npm run build && cd ..

# Run the server locally
python server.py

# Or run on network (for sharing)
python server.py --host 0.0.0.0 --port 8000
```

### Option 3: Docker
```bash
docker-compose up --build
```

## Features Included
- 🔐 Advanced Steganography (Russian Doll + Shamir Secret Sharing)
- 🔬 Steganalysis (Chi-Square, RS Analysis, Histogram Analysis)
- 💧 Digital Watermarking
- 🤖 AI-Powered Image Generation
- 👤 Biometric Authentication
- 💬 Secure Messaging

## Sharing on Local Network

To share with others on your local network:

1. **Find your local IP address:**
   - Windows: Open Command Prompt and run `ipconfig` - look for "IPv4 Address" (usually 192.168.x.x)
   - Mac/Linux: Open Terminal and run `ifconfig` or `ip a`

2. **Start server with network access:**
   ```bash
   python server.py --host 0.0.0.0 --port 8000
   ```

3. **Others access via:**
   ```
   http://192.168.X.X:8000
   ```
   (Replace with your actual IP address)

## Command Line Options
```
python server.py [--host HOST] [--port PORT]

  --host HOST    Host to bind to (default: 127.0.0.1)
                Use 0.0.0.0 for network access
  
  --port PORT   Port to bind to (default: 8000)
```

## System Requirements
- Python 3.9+
- 4GB RAM minimum
- Internet connection (for AI features)
- Chrome/Firefox/Edge browser
