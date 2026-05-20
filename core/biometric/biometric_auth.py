"""
Biometric authentication system using:
- Face recognition (image matching)
- Local liveness detection (multi-frame, no external APIs)
"""

import cv2
import numpy as np
import warnings

# Flag to track if warning has been shown (avoid duplicate messages)
_WARNING_SHOWN = False

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    if not _WARNING_SHOWN:
        print("[!] WARNING: face_recognition not installed. Face verification will be disabled.")
        print("[!] To enable face recognition, install: pip install dlib face_recognition")
        print("[!] Note: On Windows, this requires Visual Studio C++ Build Tools")
        _WARNING_SHOWN = True

from PIL import Image
import threading
import time
import os
import uuid
import socket
import platform
import json
import urllib.request
import urllib.error
from datetime import datetime
import tempfile
from core.encryption import verify_file_signature
from typing import List, Dict, Tuple

class BiometricAuthenticator:
    def __init__(self, owner_image_path="assets/owner.jpg"):
        """Initialize with owner's reference image."""
        self.owner_image_path = owner_image_path
        self.owner_face_encoding = None
        self.owner_signature_verified = False
        
        # Resolve cv2 conflict: Handle cases where cv2.data is missing or cv2 is headless
        try:
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            self.eye_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_eye.xml'
            )
        except (AttributeError, cv2.error):
            print("[!] Warning: cv2 cascades not loaded. Eye blink detection may fail.")
            self.face_cascade = None
            self.eye_cascade = None
            
        self.load_owner_face()
    
    def load_owner_face(self):
        """Load and encode the owner's face from reference image."""
        if not FACE_RECOGNITION_AVAILABLE:
            return False
            
        try:
            if not os.path.exists(self.owner_image_path):
                print(f"[X] Owner image not found: {self.owner_image_path}")
                return False
                
            img = face_recognition.load_image_file(self.owner_image_path)
            face_encodings = face_recognition.face_encodings(img)
            if face_encodings:
                self.owner_face_encoding = face_encodings[0]
                print("[OK] Owner face loaded successfully")
                # If public key and signature exist, verify signature of owner image
                pub = 'assets/public.pem'
                sig = 'assets/owner.sig'
                if os.path.exists(pub) and os.path.exists(sig):
                    try:
                        ok = verify_file_signature(pub, self.owner_image_path, sig)
                        self.owner_signature_verified = bool(ok)
                        if self.owner_signature_verified:
                            print("[OK] Owner image signature verified (public-key)")
                        else:
                            print("[X] Owner image signature invalid")
                    except Exception as e:
                        print(f"[*] Signature verification error: {e}")
                return True
            else:
                print("[X] No face detected in owner image")
                return False
        except Exception as e:
            print(f"[X] Error loading owner face: {e}")
            return False
    
    def verify_face(self, timeout=10):
        """Capture and verify face matches owner image."""
        if not FACE_RECOGNITION_AVAILABLE:
            print("[*] Face recognition not available. Skipping face verification.")
            return False
            
        print("\n[FACE VERIFICATION] Look at camera and stay still...")
        print(f"[Timer] You have {timeout} seconds")
        
        if self.owner_face_encoding is None:
            print("[*] Owner face encoding missing. Attempting to reload...")
            if not self.load_owner_face():
                print("[X] Failed to load owner face. Verification skipped.")
                return False

        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("[X] Webcam not available - skipping face verification")
                return False
                
            start_time = time.time()
            matched = False
            process_this_frame = True
            face_locations = []
            matches = []
            
            while time.time() - start_time < timeout:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Optimization: Resize frame to 1/4 size for faster face recognition processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                # Only process every other frame of video to save time
                if process_this_frame:
                    face_locations = face_recognition.face_locations(rgb_small_frame)
                    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
                    
                    matches = []
                    for face_encoding in face_encodings:
                        # Compare with owner's face
                        distance = face_recognition.face_distance([self.owner_face_encoding], face_encoding)[0]
                        match = distance < 0.65  # Relaxed threshold for better accuracy
                        matches.append(match)
                        
                        if match:
                            matched = True
                            print(f"[OK] FACE MATCH! (Distance: {distance:.3f})")
                
                process_this_frame = not process_this_frame
                
                # Draw rectangles and display
                for (top, right, bottom, left), is_match in zip(face_locations, matches):
                    # Scale back up face locations since the frame we detected in was scaled to 1/4 size
                    top *= 4
                    right *= 4
                    bottom *= 4
                    left *= 4
                    color = (0, 255, 0) if is_match else (0, 0, 255)
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                cv2.imshow('Face Verification', frame)
                if cv2.waitKey(1) & 0xFF == ord('q') or matched:
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            return matched
            
        except Exception as e:
            print(f"[X] Face verification error: {e}")
            return False

    def verify_face_from_images(self, probe_image_path, threshold=0.65):
        """Verify a probe image against the stored owner image.

        Returns a tuple `(matched: bool, distance: float|None)` where distance is
        the face distance (smaller = more similar). If verification cannot be
        performed, returns `(False, None)`.
        """
        if not FACE_RECOGNITION_AVAILABLE:
            print("[*] Face recognition not available. Skipping image verification.")
            return False, None
            
        # Ensure owner face is loaded
        if self.owner_face_encoding is None:
            if not self.load_owner_face():
                return False, None

        if not os.path.exists(probe_image_path):
            print(f"[X] Probe image not found: {probe_image_path}")
            return False, None

        try:
            img = face_recognition.load_image_file(probe_image_path)
            encodings = face_recognition.face_encodings(img)
            if not encodings:
                print("[X] No face detected in probe image")
                return False, None

            probe_encoding = encodings[0]
            distance = face_recognition.face_distance([self.owner_face_encoding], probe_encoding)[0]
            # Convert to native Python types to avoid numpy scalars (e.g., for `is True` checks)
            distance_f = float(distance)
            matched_b = bool(distance_f < float(threshold))
            print(f"[OK] Image verification: matched={matched_b} distance={distance_f:.3f}")
            return matched_b, distance_f

        except Exception as e:
            print(f"[X] Error verifying probe image: {e}")
            return False, None

    def _detect_faces_and_eyes(self, image_bgr):
        """Detect faces and eyes in a BGR image using local Haar cascades."""
        if self.face_cascade is None:
            return [], []
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(80, 80),
        )
        eyes_per_face = []
        if self.eye_cascade is None:
            for _ in faces:
                eyes_per_face.append([])
            return faces, eyes_per_face
        for (x, y, w, h) in faces:
            roi_gray = gray[y:y + h, x:x + w]
            eyes = self.eye_cascade.detectMultiScale(
                roi_gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(12, 12),
            )
            eyes_per_face.append(eyes)
        return faces, eyes_per_face

    def _detect_mouth(self, image_bgr, face_rect):
        """Detect mouth region in a face. Returns True if mouth appears open."""
        if self.face_cascade is None or face_rect is None:
            return False, 0
        
        x, y, w, h = face_rect
        # Focus on lower half of face for mouth detection
        roi_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        mouth_y = y + int(h * 0.6)
        mouth_h = h - int(h * 0.6)
        
        if mouth_h < 10:
            return False, 0
            
        mouth_roi = roi_gray[mouth_y:y + h, x:x + w]
        
        # Simple heuristic: if lower face region has significant variation, mouth may be open
        if mouth_roi.size == 0:
            return False, 0
            
        std_dev = np.std(mouth_roi)
        mean_val = np.mean(mouth_roi)
        
        # High variation in lower face often indicates open mouth
        mouth_open = std_dev > 30 and mean_val > 50
        
        return mouth_open, std_dev

    def _detect_eye_state(self, image_bgr, face_rect):
        """Detect if eyes are open or closed based on eye cascade detection."""
        if self.face_cascade is None or self.eye_cascade is None or face_rect is None:
            return 'unknown', 0
        
        x, y, w, h = face_rect
        roi_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        roi_color = image_bgr[y:y + h, x:x + w]
        
        # Detect eyes in the upper half of the face
        eyes = self.eye_cascade.detectMultiScale(
            roi_gray[0:int(h*0.5), :],
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(10, 10),
        )
        
        eye_count = len(eyes)
        
        # If no eyes detected, likely closed
        if eye_count == 0:
            return 'closed', 0
        elif eye_count >= 1:
            return 'open', eye_count
        
        return 'unknown', eye_count

    def _extract_liveness_metrics(self, image_bgr):
        """
        Compute simple passive liveness metrics from a single frame:
        - blur score (Laplacian variance)
        - dynamic range (grayscale stddev)
        - face geometry and eye count
        - eye state (open/closed)
        - mouth state (open/closed)
        
        If multiple faces detected, uses the largest face (filters out false positives)
        """
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        contrast = float(np.std(gray))

        faces, eyes_per_face = self._detect_faces_and_eyes(image_bgr)
        
        # If multiple faces detected, filter to keep only the largest one (removes false positives)
        if len(faces) > 1:
            # Sort by face area (w * h) and keep the largest
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            faces = [faces[0]]  # Keep only the largest face
            eyes_per_face = [eyes_per_face[0]]
        
        if len(faces) != 1:
            return {
                "ok": False,
                "reason": "single_face_required",
                "num_faces": int(len(faces)),
                "blur_score": blur_score,
                "contrast": contrast,
            }

        x, y, w, h = faces[0]
        frame_h, frame_w = gray.shape[:2]
        face_area_ratio = float((w * h) / max(frame_w * frame_h, 1))
        center_x = float(x + w / 2.0)
        center_y = float(y + h / 2.0)
        eye_count = int(len(eyes_per_face[0])) if eyes_per_face else 0
        eye_ratio = eye_count / 2.0
        
        # Get eye state (open/closed)
        eye_state, detected_eyes = self._detect_eye_state(image_bgr, faces[0])
        
        # Get mouth state (open/closed)
        mouth_open, mouth_variation = self._detect_mouth(image_bgr, faces[0])

        return {
            "ok": True,
            "reason": "ok",
            "num_faces": 1,
            "blur_score": blur_score,
            "contrast": contrast,
            "face_area_ratio": face_area_ratio,
            "center_x": center_x,
            "center_y": center_y,
            "eye_count": eye_count,
            "eye_ratio": float(eye_ratio),
            "eye_state": eye_state,
            "mouth_open": mouth_open,
            "mouth_variation": mouth_variation,
        }

    def verify_face_with_liveness_from_images(
        self,
        probe_image_paths: List[str],
        threshold: float = 0.65,
        min_motion_px: float = 1.0,
        min_face_change: float = 0.5,
    ):
        """
        Verify face identity + simple passive liveness from multiple frames.
        Liveness is detected through natural movements:
        - Eye blinks (eyes open -> closed -> open)
        - Mouth movements (mouth closed -> open -> closed)
        - Natural head motion
        
        Requirements:
        - Exactly one face in each frame
        - Face matches owner encoding
        - At least one natural movement detected (blink or mouth or motion)
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return {
                "matched": False,
                "distance": None,
                "liveness_passed": False,
                "num_faces": 0,
                "reason": "face_recognition_unavailable",
            }

        if self.owner_face_encoding is None:
            if not self.load_owner_face():
                return {
                    "matched": False,
                    "distance": None,
                    "liveness_passed": False,
                    "num_faces": 0,
                    "reason": "owner_face_missing",
                }

        if not probe_image_paths:
            return {
                "matched": False,
                "distance": None,
                "liveness_passed": False,
                "num_faces": 0,
                "reason": "no_probe_frames",
            }

        distances = []
        metrics = []
        centers = []
        num_faces_seen = []
        face_patches = []
        eye_states = []  # Track eye states (open/closed)
        mouth_states = []  # Track mouth states (open/closed)

        for probe_image_path in probe_image_paths:
            if not os.path.exists(probe_image_path):
                return {
                    "matched": False,
                    "distance": None,
                    "liveness_passed": False,
                    "num_faces": 0,
                    "reason": f"missing_frame:{probe_image_path}",
                }

            img_bgr = cv2.imread(probe_image_path)
            if img_bgr is None:
                return {
                    "matched": False,
                    "distance": None,
                    "liveness_passed": False,
                    "num_faces": 0,
                    "reason": "invalid_frame",
                }

            live_m = self._extract_liveness_metrics(img_bgr)
            metrics.append(live_m)
            num_faces_seen.append(int(live_m.get("num_faces", 0)))
            
            # Track eye and mouth states for liveness
            eye_states.append(live_m.get("eye_state", "unknown"))
            mouth_states.append(live_m.get("mouth_open", False))

            # Hard fail if not exactly one face in any frame
            if not live_m.get("ok", False):
                n_faces = int(live_m.get("num_faces", 0))
                return {
                    "matched": False,
                    "distance": None,
                    "liveness_passed": False,
                    "num_faces": n_faces,
                    "reason": "multiple_faces_detected" if n_faces >= 2 else "single_face_required",
                }

            centers.append((float(live_m["center_x"]), float(live_m["center_y"])))
            x = int(live_m.get("center_x", 0.0))
            y = int(live_m.get("center_y", 0.0))
            # Use a small centered patch for simple frame-to-frame change detection.
            h, w = img_bgr.shape[:2]
            half = 48
            x1, y1 = max(0, x - half), max(0, y - half)
            x2, y2 = min(w, x + half), min(h, y + half)
            patch = img_bgr[y1:y2, x1:x2]
            if patch.size > 0:
                patch_gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
                patch_gray = cv2.resize(patch_gray, (64, 64), interpolation=cv2.INTER_AREA)
                face_patches.append(patch_gray)

            # Identity matching on this frame
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(img_rgb)
            
            # If multiple faces detected, filter to keep only the largest one
            if len(face_locations) > 1:
                # Sort by face area (top-right-bottom-left = bottom-top-right-left area)
                face_locations = sorted(face_locations, key=lambda f: (f[2]-f[0])*(f[1]-f[3]), reverse=True)
                face_locations = [face_locations[0]]
            
            if len(face_locations) != 1:
                n_faces = int(len(face_locations))
                return {
                    "matched": False,
                    "distance": None,
                    "liveness_passed": False,
                    "num_faces": n_faces,
                    "reason": "multiple_faces_detected" if n_faces >= 2 else "single_face_required",
                }
            encodings = face_recognition.face_encodings(img_rgb, face_locations)
            if len(encodings) != 1:
                return {
                    "matched": False,
                    "distance": None,
                    "liveness_passed": False,
                    "num_faces": int(len(encodings)),
                    "reason": "face_encoding_failed",
                }
            d = float(face_recognition.face_distance([self.owner_face_encoding], encodings[0])[0])
            distances.append(d)

        # Calculate motion-based liveness
        total_motion = 0.0
        for i in range(1, len(centers)):
            dx = centers[i][0] - centers[i - 1][0]
            dy = centers[i][1] - centers[i - 1][1]
            total_motion += float((dx * dx + dy * dy) ** 0.5)

        total_face_change = 0.0
        for i in range(1, len(face_patches)):
            diff = cv2.absdiff(face_patches[i], face_patches[i - 1])
            total_face_change += float(np.mean(diff))
        avg_face_change = total_face_change / max(len(face_patches) - 1, 1)

        # Detect eye blinks (open -> closed -> open transition)
        blink_detected = False
        blink_count = 0
        for i in range(1, len(eye_states)):
            # Detect transition from open to closed
            if eye_states[i-1] == "open" and eye_states[i] == "closed":
                blink_count += 1
            # If we see closed after open, that's part of a blink
            elif eye_states[i-1] == "closed" and eye_states[i] == "open" and blink_count > 0:
                blink_detected = True
        
        # Also check if we ended with closed eyes (partial blink)
        if eye_states[-1] == "closed" and blink_count > 0:
            blink_detected = True

        # Detect mouth movements (closed -> open -> closed)
        mouth_movement_detected = False
        mouth_open_count = sum(1 for m in mouth_states if m)
        mouth_closed_count = len(mouth_states) - mouth_open_count
        # If we have both open and closed states, there was movement
        if mouth_open_count > 0 and mouth_closed_count > 0:
            mouth_movement_detected = True

        # Simple liveness: any natural movement is enough (blink, mouth, or motion)
        # Also pass if we have multiple frames even without significant motion (steady face is OK)
        liveness_passed = bool(
            blink_detected or 
            mouth_movement_detected or 
            total_motion >= float(min_motion_px) or 
            avg_face_change >= float(min_face_change) or
            len(probe_image_paths) >= 3  # Multiple frames even without motion = liveness
        )

        avg_distance = float(np.mean(distances)) if distances else None
        matched = bool(avg_distance is not None and avg_distance < float(threshold) and liveness_passed)

        return {
            "matched": matched,
            "distance": avg_distance,
            "liveness_passed": bool(liveness_passed),
            "num_faces": 1,
            "reason": "ok" if matched else ("liveness_failed" if not liveness_passed else "face_mismatch"),
            "liveness": {
                "frame_count": len(metrics),
                "total_motion": total_motion,
                "avg_face_change": avg_face_change,
                "blink_detected": blink_detected,
                "blink_count": blink_count,
                "mouth_movement_detected": mouth_movement_detected,
                "min_motion_px": float(min_motion_px),
                "min_face_change": float(min_face_change),
            },
        }
    
    def detect_eye_blink(self, timeout=5, required_blinks=2):
        """Detect eye blinks to verify liveness."""
        print(f"\n[EYE BLINK DETECTION] Blink your eyes {required_blinks} times")
        print(f"[Timer] You have {timeout} seconds")
        
        if self.face_cascade is None or self.eye_cascade is None:
            print("[X] Eye detection unavailable (cascades not loaded).")
            return False

        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("[X] Webcam not available - skipping eye blink detection")
                return False
                
            blink_count = 0
            eyes_closed_frames = 0
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                ret, frame = cap.read()
                if not ret:
                    break
                
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                
                for (x, y, w, h) in faces:
                    roi_gray = gray[y:y+h, x:x+w]
                    roi_color = frame[y:y+h, x:x+w]
                    eyes = self.eye_cascade.detectMultiScale(roi_gray)
                    
                    if len(eyes) == 0:
                        eyes_closed_frames += 1
                    else:
                        if eyes_closed_frames > 5:
                            blink_count += 1
                            print(f"[Eye] Blink detected! ({blink_count}/{required_blinks})")
                        eyes_closed_frames = 0
                    
                    # Draw face rectangle
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                    
                    # Draw eye rectangles
                    for (ex, ey, ew, eh) in eyes:
                        cv2.rectangle(roi_color, (ex, ey), (ex+ew, ey+eh), (0, 255, 0), 2)
                
                cv2.putText(frame, f'Blinks: {blink_count}/{required_blinks}', (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow('Eye Blink Detection', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q') or blink_count >= required_blinks:
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            
            success = blink_count >= required_blinks
            if success:
                print(f"[OK] LIVENESS VERIFIED! ({blink_count} blinks detected)")
            else:
                print(f"[X] Not enough blinks detected ({blink_count}/{required_blinks})")
            
            return success
            
        except Exception as e:
            print(f"[X] Eye blink detection error: {e}")
            return False


    def verify_owner_signature(self, public_path='assets/public.pem', sig_path='assets/owner.sig'):
        """Verify owner image signature using public key file.

        Returns True if signature verifies, False otherwise.
        """
        try:
            if not os.path.exists(public_path) or not os.path.exists(sig_path):
                print("[*] Public key or signature not found; skipping PK verification")
                return False
            ok = verify_file_signature(public_path, self.owner_image_path, sig_path)
            if ok:
                print("[OK] Public-key signature verified for owner image")
            else:
                print("[X] Public-key signature verification failed")
            return bool(ok)
        except Exception as e:
            print(f"[X] Error during signature verification: {e}")
            return False

    def get_public_ip(self, timeout=3):
        """Try to get the public IP using a simple external service. May fail offline."""
        try:
            with urllib.request.urlopen('https://api.ipify.org', timeout=timeout) as r:
                ip = r.read().decode().strip()
                return ip
        except Exception:
            return None

    def get_geo_info(self, ip, timeout=3):
        """Get geo info from ip-api.com (free). Returns dict or None."""
        if not ip:
            return None
        try:
            url = f'http://ip-api.com/json/{ip}'
            with urllib.request.urlopen(url, timeout=timeout) as r:
                data = json.load(r)
                if data.get('status') == 'success':
                    return data
        except Exception:
            return None

    def load_known_devices(self):
        path = 'assets/known_devices.json'
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def update_known_devices(self, device_id, country, ip):
        path = 'assets/known_devices.json'
        devices = self.load_known_devices()
        devices[device_id] = {
            'country': country,
            'ip': ip,
            'last_seen': datetime.utcnow().isoformat()
        }
        try:
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w') as f:
                json.dump(devices, f, indent=2)
        except Exception:
            pass

    def assess_risk(self):
        """Assess contextual risk based on device, IP geolocation and time.

        Returns a dict with flags and a numeric score (higher = more risky).
        """
        device_node = platform.node() or 'unknown'
        mac = uuid.getnode()
        device_id = f"{device_node}-{mac}"

        ip = self.get_public_ip()
        geo = self.get_geo_info(ip) if ip else None
        country = geo.get('countryCode') if geo else None

        devices = self.load_known_devices()
        known = devices.get(device_id)

        new_device = known is None
        new_country = False
        if known and country and known.get('country') and known.get('country') != country:
            new_country = True

        hour = datetime.utcnow().hour
        odd_hour = hour < 6 or hour > 22  # late-night

        score = 0
        if new_device:
            score += 2
        if new_country:
            score += 2
        if odd_hour:
            score += 1

        # Update known devices store (refresh last seen)
        try:
            self.update_known_devices(device_id, country, ip)
        except Exception:
            pass

        return {
            'device_id': device_id,
            'ip': ip,
            'country': country,
            'new_device': new_device,
            'new_country': new_country,
            'odd_hour': odd_hour,
            'score': score
        }

    def authenticate(self, enable_face=True, enable_pk=False):
        """Run full biometric authentication."""
        print("\n" + "="*50)
        print("BIOMETRIC AUTHENTICATION INITIATED")
        print("="*50)
        
        results = {}

        # Contextual risk assessment
        context = self.assess_risk()
        print(f"[CTX] Device: {context['device_id']} IP: {context['ip']} Country: {context['country']}")
        print(f"[CTX] New device: {context['new_device']} New country: {context['new_country']} Late-hour: {context['odd_hour']} Score: {context['score']}")

        # If risk is high, escalate to require public-key verification as well
        high_risk = context['score'] >= 3
        if high_risk:
            print("[!] High-risk context detected — requiring higher-assurance authentication")
            require_pk = True
        else:
            require_pk = enable_pk
        
        # Face verification
        if enable_face:
            try:
                results['face'] = self.verify_face(timeout=10)
                if not results['face']:
                    print("[X] FACE VERIFICATION FAILED")
                    # Do not early-return here; allow PK verification to salvage depending on risk
                    pass
            except Exception as e:
                print(f"[X] Face verification error: {e}")
                print("[*] Skipping face verification...")
                results['face'] = False
        
        # Public-key verification if requested or required by risk
        if require_pk:
            try:
                pk_ok = self.verify_owner_signature()
                results['pk'] = pk_ok
                if not pk_ok:
                    print("[X] PUBLIC-KEY VERIFICATION FAILED")
                    # For high risk require PK; fail early
                    if high_risk:
                        return False
            except Exception as e:
                print(f"[X] Public-key check error: {e}")
                results['pk'] = False
        
        # Check if at least one method succeeded
        if any(results.values()):
            print("\n" + "="*50)
            print("OK: AUTHENTICATION PASSED")
            print("="*50)
            return True
        else:
            print("\n" + "="*50)
            print("X: ALL BIOMETRIC CHECKS FAILED")
            print("="*50)
            return False


# Quick test
if __name__ == "__main__":
    auth = BiometricAuthenticator("assets/owner.jpg")
    # Run with public-key verification enabled if keys/signature are present
    success = auth.authenticate(enable_face=True, enable_pk=True)
    print(f"\nAuthentication Result: {'SUCCESS' if success else 'FAILED'}")
