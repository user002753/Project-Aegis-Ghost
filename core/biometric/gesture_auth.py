"""
Gesture-based authentication using Gemini AI and Face Detection
- Generates random gestures using Gemini AI
- Detects face movements (head turns, tilts, nods)
- Real-time gesture verification
"""

import cv2
import numpy as np
import os
from typing import List, Tuple, Optional
import warnings

# Suppress future warnings for google.generativeai deprecation
warnings.filterwarnings('ignore', category=FutureWarning, module='google.generativeai')

try:
    import google.genai as genai
    GEMINI_MODULE = "google.genai"
except ImportError:
    try:
        import google.generativeai as genai
        GEMINI_MODULE = "google.generativeai"
    except ImportError:
        genai = None
        GEMINI_MODULE = None


class GestureAuthenticator:
    def __init__(self, gemini_api_key: Optional[str] = None):
        """Initialize Gesture Authenticator with Gemini AI."""
        # Load face cascade classifier
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            print(f"[!] Error: Could not load face cascade from {cascade_path}")
        
        # Initialize Gemini AI
        api_key = gemini_api_key or os.getenv('GEMINI_API_KEY')
        self.model = None
        
        if genai is None:
            print("[*] Google Gemini not available. Install: pip install google-genai")
        elif api_key:
            try:
                if GEMINI_MODULE == "google.genai":
                    genai.api_key = api_key
                else:
                    genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"[*] Gemini initialization failed: {e}")
        else:
            print("[*] Gemini API key not set. Set GEMINI_API_KEY environment variable")
        
        self.gestures = [
            "look_left",
            "look_right",
            "nod_up_down",
            "tilt_left",
            "tilt_right",
            "smile",
            "open_mouth"
        ]
        
        self.last_positions = []  # Track face positions
        self.position_history = []  # Store movement history
    
    def detect_faces(self, frame: np.ndarray) -> List[Tuple]:
        """Detect faces in frame using cascade classifier."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        return faces

    def get_head_pose(self, face: Tuple, frame_shape: Tuple) -> dict:
        """Estimate head pose based on face position in frame."""
        x, y, w, h = face
        frame_h, frame_w = frame_shape[:2]
        
        # Calculate face center
        face_cx = x + w // 2
        face_cy = y + h // 2
        
        # Frame center
        frame_cx = frame_w // 2
        frame_cy = frame_h // 2
        
        # Calculate position metrics
        yaw = (face_cx - frame_cx) / (frame_w / 2)  # -1 (left) to 1 (right)
        pitch = (face_cy - frame_cy) / (frame_h / 2)  # -1 (up) to 1 (down)
        
        return {
            'yaw': yaw,      # Left/Right rotation
            'pitch': pitch,  # Up/Down rotation
            'x': face_cx,
            'y': face_cy,
            'size': w * h
        }

    def analyze_movement(self, current_pose: dict) -> Optional[str]:
        """Analyze movement pattern to detect gestures."""
        # Need enough frames to establish baseline
        if len(self.position_history) < 8:
            return None
        
        # Calculate movement vectors from last 8-10 frames
        recent_poses = self.position_history[-8:]
        
        # Yaw movement
        yaw_values = [p['yaw'] for p in recent_poses]
        yaw_change = yaw_values[-1] - yaw_values[0]
        
        # Pitch movement
        pitch_values = [p['pitch'] for p in recent_poses]
        pitch_change = pitch_values[-1] - pitch_values[0]
        
        # Size change (zoom indication)
        sizes = [p['size'] for p in recent_poses]
        size_change = (sizes[-1] - sizes[0]) / sizes[0] if sizes[0] > 0 else 0
        
        # Detect gestures with motion purity (pure vs diagonal)
        # Pure movements: dominant in one direction with minimal cross-movement
        # Diagonal movements: significant in both directions
        
        yaw_threshold = 0.25
        pitch_threshold = 0.2
        
        # Pure horizontal (look left/right) - minimal pitch change
        if abs(pitch_change) < 0.15 and yaw_change < -yaw_threshold:
            return "look_left"
        elif abs(pitch_change) < 0.15 and yaw_change > yaw_threshold:
            return "look_right"
        
        # Pure vertical (nod) - minimal yaw change
        elif abs(yaw_change) < 0.15 and pitch_change > pitch_threshold:
            return "nod_up_down"
        elif abs(yaw_change) < 0.15 and pitch_change < -pitch_threshold:
            return "nod_up_down"
        
        # Diagonal movements (tilt) - significant in both directions
        elif abs(yaw_change) > 0.2 and abs(pitch_change) > 0.15:
            return "tilt_left" if yaw_change < 0 else "tilt_right"
        
        return None
    
    def generate_gesture_challenge(self) -> str:
        """Use Gemini AI to generate a random gesture challenge."""
        if not self.model:
            # Fallback to random gesture
            import random
            gesture = random.choice(self.gestures)
            return f"Please {gesture.replace('_', ' ')}"
        
        try:
            prompt = f"""Generate ONE random face gesture challenge for biometric authentication.
            Choose ONLY ONE from this list: {', '.join(self.gestures)}
            
            Return ONLY the gesture name in this exact format: "Gesture: [name]"
            Example: "Gesture: look_left" or "Gesture: nod_up_down"
            """
            
            response = self.model.generate_content(prompt, stream=False)
            text = response.text.strip()
            
            # Extract gesture name
            if "Gesture:" in text:
                gesture = text.split("Gesture:")[-1].strip().lower().replace(' ', '_')
                # Validate gesture
                for g in self.gestures:
                    if g in gesture or gesture in g:
                        return f"Please {g.replace('_', ' ')}"
            
            # Fallback
            import random
            return f"Please {random.choice(self.gestures).replace('_', ' ')}"
        
        except Exception as e:
            print(f"[*] Gemini generation failed: {e}, using random gesture")
            import random
            return f"Please {random.choice(self.gestures).replace('_', ' ')}"
    
    def is_gesture_detected(self, frame: np.ndarray, target_gesture: str) -> bool:
        """Detect if target gesture is performed."""
        faces = self.detect_faces(frame)
        
        if len(faces) == 0:
            return False
        
        face = faces[0]  # Use first/largest face
        pose = self.get_head_pose(face, frame.shape)
        
        # Add to history
        self.position_history.append(pose)
        if len(self.position_history) > 30:
            self.position_history.pop(0)
        
        # Analyze movement
        detected_gesture = self.analyze_movement(pose)
        
        # Normalize gesture names for comparison
        target_normalized = target_gesture.lower().replace(' ', '_')
        
        if detected_gesture and target_normalized in detected_gesture:
            return True
        
        return False
    
    def verify_gesture(self, capture_duration: int = 10) -> Tuple[bool, str]:
        """Verify gesture by detecting ANY facial movement.
        
        Simple and reliable: Just check if face region changes between frames.
        """
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return False, "Webcam not available"
            
            challenge = self.generate_gesture_challenge()
            print(f"\n[*] Gesture Challenge: {challenge}")
            print(f"[*] Move your head for {capture_duration} seconds...")
            
            # Get baseline frame with face
            baseline_frame = None
            baseline_face = None
            frame_count = 0
            
            # Capture baseline (first valid frame with face)
            print("[*] Calibrating...")
            while baseline_frame is None and frame_count < 30:
                ret, frame = cap.read()
                if not ret:
                    cap.release()
                    return False, "Cannot read from webcam"
                
                # Optimization: Resize for consistent performance
                if frame.shape[1] > 640:
                    frame = cv2.resize(frame, (640, int(frame.shape[0] * 640 / frame.shape[1])))
                
                faces = self.detect_faces(frame)
                if faces:
                    baseline_frame = frame.copy()
                    baseline_face = faces[0]
                    print(f"[OK] Baseline captured")
                    break
                
                frame_count += 1
            
            if baseline_frame is None:
                cap.release()
                return False, "No face detected in baseline"
            
            # Detection phase - look for movement
            frame_count = 0
            target_frames = capture_duration * 30
            gesture_verified = False
            consecutive_movements = 0
            
            # Parse target gesture from challenge string
            target_gesture = challenge.replace("Please ", "").replace("Gesture: ", "").strip().lower().replace(' ', '_')
            
            print("[*] Detecting movement...")
            
            while frame_count < target_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Optimization: Resize for consistent performance
                if frame.shape[1] > 640:
                    frame = cv2.resize(frame, (640, int(frame.shape[0] * 640 / frame.shape[1])))
                
                faces = self.detect_faces(frame)
                if not faces:
                    frame_count += 1
                    continue
                
                # Get current pose
                current_face = faces[0]
                pose = self.get_head_pose(current_face, frame.shape)
                
                # Add to history for pattern analysis
                self.position_history.append(pose)
                if len(self.position_history) > 30:
                    self.position_history.pop(0)
                
                # Analyze movement
                detected_gesture = self.analyze_movement(pose)
                
                if detected_gesture and target_gesture in detected_gesture:
                    gesture_verified = True
                    print(f"[OK] {detected_gesture} detected!")
                    break
                
                # Progress update
                if frame_count % 15 == 0:
                    print(f"[*] Analyzing... (Target: {target_gesture})")
                    
                frame_count += 1
            
            cap.release()
            
            if gesture_verified:
                return True, f"Gesture '{challenge.replace('Please ', '')}' verified!"
            else:
                return False, f"Gesture failed or timed out. Expected: {target_gesture}"
        
        except Exception as e:
            return False, f"Gesture verification error: {str(e)}"


# Test function
if __name__ == "__main__":
    auth = GestureAuthenticator()
    success, msg = auth.verify_gesture(capture_duration=10)
    print(f"[*] Result: {msg}")
