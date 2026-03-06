#!/usr/bin/env python
"""
Network Server Launcher for Project Aegis Ghost
Run this to share the app on your local network
"""
import uvicorn
from server import app

if __name__ == "__main__":
    print("Starting Project Aegis Ghost on network...")
    print("Others can access via: http://YOUR_IP_ADDRESS:8000")
    print("To find your IP: ipconfig (Windows) / ifconfig (Mac/Linux)")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000)
