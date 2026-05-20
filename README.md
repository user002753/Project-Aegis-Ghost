The project is implemented as a full-stack web application with a React frontend and Python FastAPI backend. The implementation follows a modular architecture where each security feature is developed as an independent Python module. Steganography uses LSB (Least Significant Bit) and DWT (Discrete Wavelet Transform) algorithms for embedding data in images. Shamir Secret Sharing is implemented using the PyCryptodome library for splitting secrets into encrypted fragments. Biometric authentication uses dlib and face_recognition libraries for face matching with MediaPipe for liveness detection. Digital watermarking employs both visible and LSB-based invisible embedding techniques. The backend exposes REST API endpoints for all operations, while the frontend provides user-friendly interfaces for interacting with these features. The system includes security monitoring that tracks IP addresses and detects anomalies, an AI security advisor powered by Groq, and a secure messaging system with end-to-end encryption.

AI-Powered Steganography for Military-Grade Data Concealment(Project Aegis Ghost—named after the protective shield of the Greek goddess Athena. The name reflects a core principle of steganography: the message is visible but not recognized for what it truly is).

In an era where over 80% of security breaches involve compromised credentials and data interception is a constant threat, this project focuses on protecting sensitive communications for defense, intelligence, healthcare, journalism, and enterprise environments. Unlike encryption, which only scrambles data but signals communication is occurring, steganography conceals the very existence of the message.

The system integrates multiple security technologies:

1. Steganography using LSB and DWT to embed encrypted data within images.

2. Steganalysis using statistical and neural network methods to detect hidden data.

3. Russian Doll encryption with Shamir’s Secret Sharing to eliminate single points of failure.

4. Biometric authentication with face recognition and liveness detection to prevent spoofing.

5. Digital watermarking for content authenticity and deepfake prevention.

6. AI-powered security monitoring for real-time threat detection.

7. A secure messaging platform with end-to-end encryption and optional steganographic channels.

The system is built as a full-stack application using React and FastAPI, integrating tools such as dlib, face_recognition, MediaPipe, and Groq LLM.

Additional features we worked on:

●Account creation with login and OTP verification
●Strong password requirement (minimum 8 characters)
●Forgot password feature
●Profile view
●Secure access to steganalysis, secure chat, and image gallery modules using face or pattern recognition
●Security monitoring and alert system
●AI chatbot 
●Settings module
●IP detection


