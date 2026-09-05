# intrusion_detection.py - Optimized with Windows Lock Screen
"""
Intrusion Detection System for Gesture Control
- Uses OpenCV face detection with frame skipping
- Locks Windows screen when unknown person detected
"""

import cv2
import numpy as np
import os
import time
import subprocess
import platform
import ctypes
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from collections import deque
import threading

@dataclass
class DetectedPerson:
    """Information about a detected person"""
    face_location: Tuple[int, int, int, int]
    name: str = "Unknown"
    confidence: float = 0.0
    is_admin: bool = False
    timestamp: float = 0.0

class FaceRecognitionSystem:
    """Simple face recognition using OpenCV"""
    
    def __init__(self, known_faces_dir: str = "known_faces"):
        self.known_faces_dir = known_faces_dir
        self.known_face_encodings = []
        self.known_face_names = []
        self.is_trained = False
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        if not os.path.exists(known_faces_dir):
            os.makedirs(known_faces_dir)
            print(f"📁 Created directory: {known_faces_dir}")
    
    def get_face_histogram(self, face_img):
        """Extract color histogram as a simple face signature"""
        face_img = cv2.resize(face_img, (100, 100))
        hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [30, 40], [0, 180, 0, 256])  # Reduced bins for speed
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist.flatten()
    
    def train_from_directory(self) -> bool:
        """Load and encode all known faces from directory"""
        self.known_face_encodings = []
        self.known_face_names = []
        
        for filename in os.listdir(self.known_faces_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(self.known_faces_dir, filename)
                name = os.path.splitext(filename)[0]
                
                try:
                    image = cv2.imread(filepath)
                    if image is None:
                        continue
                        
                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
                    
                    if len(faces) > 0:
                        x, y, w, h = faces[0]
                        face_img = image[y:y+h, x:x+w]
                        hist = self.get_face_histogram(face_img)
                        self.known_face_encodings.append(hist)
                        self.known_face_names.append(name)
                        print(f"  ✅ Loaded: {name}")
                        
                except Exception as e:
                    print(f"  ❌ Error loading {filename}: {e}")
        
        self.is_trained = len(self.known_face_encodings) > 0
        
        if self.is_trained:
            print(f"\n✅ Loaded {len(self.known_face_encodings)} known face(s)")
        else:
            print("\n⚠️ No known faces loaded.")
        
        return self.is_trained
    
    def add_admin_face_from_camera(self, cap) -> bool:
        """Capture and add admin face from existing camera"""
        print(f"\n📸 Capturing admin face")
        print("   Look at the camera and press SPACE to capture")
        print("   Press ESC to cancel")
        
        captured = False
        
        while not captured:
            ret, frame = cap.read()
            if not ret:
                break
            
            display = frame.copy()
            cv2.putText(display, "Register Admin Face - Press SPACE to capture", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(display, "Press ESC to cancel", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            
            for (x, y, w, h) in faces:
                cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(display, "FACE DETECTED", (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            cv2.imshow('Register Admin Face', display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # SPACE
                if len(faces) > 0:
                    x, y, w, h = faces[0]
                    face_img = frame[y:y+h, x:x+w]
                    
                    filename = f"admin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    filepath = os.path.join(self.known_faces_dir, filename)
                    cv2.imwrite(filepath, face_img)
                    
                    hist = self.get_face_histogram(face_img)
                    self.known_face_encodings.append(hist)
                    self.known_face_names.append("admin")
                    self.is_trained = True
                    
                    print(f"✅ Admin face saved: {filename}")
                    captured = True
                else:
                    print("⚠️ No face detected. Please look at the camera.")
            
            elif key == 27:  # ESC
                break
        
        cv2.destroyWindow('Register Admin Face')
        return captured
    
    def recognize_face(self, face_img) -> Tuple[str, float, bool]:
        """Recognize a face by comparing histograms"""
        if not self.is_trained or len(self.known_face_encodings) == 0:
            return "Unknown", 0.0, False
        
        hist = self.get_face_histogram(face_img)
        
        best_match = None
        best_score = 0
        
        for i, known_hist in enumerate(self.known_face_encodings):
            score = cv2.compareHist(hist, known_hist, cv2.HISTCMP_CORREL)
            
            if score > best_score:
                best_score = score
                best_match = i
        
        if best_score > 0.55:
            name = self.known_face_names[best_match]
            return name, best_score, True
        else:
            return "Unknown", best_score, False

class IntrusionDetector:
    """Main intrusion detection system - OPTIMIZED"""
    
    def __init__(self, frame_skip: int = 5):  # Increased frame skip for performance
        self.face_system = FaceRecognitionSystem()
        self.frame_skip = frame_skip  # Process every 15th frame
        self.frame_counter = 0
        self.current_persons: List[DetectedPerson] = []
        self.admin_present = False
        self.intrusion_detected = False
        self.lock_screen_callback = None
        self.intrusion_log = []
        
        # Status flags
        self.is_monitoring = False
        self.is_locked = False
        self.alert_cooldown = 0
        self.last_lock_time = 0
        self.lock_cooldown = 10  # Seconds between lock attempts
        
        # Detection history for smoothing
        self.admin_history = deque(maxlen=10)
        self.intrusion_history = deque(maxlen=10)
        
        # Face cascade for detection
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Threading for async operations
        self.lock_thread = None
        
    def initialize(self) -> bool:
        """Initialize the detection system"""
        print("\n" + "=" * 50)
        print("🔒 INTRUSION DETECTION SYSTEM")
        print("=" * 50)
        
        if self.face_system.train_from_directory():
            print("✅ Face recognition ready")
        else:
            print("\n⚠️ No admin faces found. Press 'R' to register your face")
        
        return True
    
    def set_lock_screen_callback(self, callback):
        """Set callback function for screen locking"""
        self.lock_screen_callback = callback
    
    def lock_windows_screen(self):
        """Lock Windows screen from WSL"""
        current_time = time.time()
    
        if current_time - self.last_lock_time < self.lock_cooldown:
            return
    
        self.last_lock_time = current_time
    
        print(f"\n🔒 INTRUSION DETECTED! Locking screen...")
    
        try:
            # Check if running in WSL
            is_wsl = 'microsoft' in platform.uname().release.lower()
        
            if is_wsl:
                # Method 1: Use Windows PowerShell from WSL
                powershell_cmd = [
                    'powershell.exe', 
                    '-Command', 
                    'rundll32.exe user32.dll,LockWorkStation'
                ]
                subprocess.run(powershell_cmd, capture_output=True)
                print("   ✅ Windows screen locked via PowerShell")
            
            elif platform.system() == "Windows":
                # Direct Windows lock
                ctypes.windll.user32.LockWorkStation()
                print("   ✅ Windows screen locked")
            
            elif platform.system() == "Linux":
                # Linux desktop lock
                lock_methods = [
                    ["loginctl", "lock-session"],
                    ["gnome-screensaver-command", "-l"],
                    ["xdg-screensaver", "lock"],
                    ["dm-tool", "lock"]
                ]
                for method in lock_methods:
                    try:
                        result = subprocess.run(method, capture_output=True, timeout=2)
                        if result.returncode == 0:
                            print(f"   ✅ Screen locked via {method[0]}")
                            break
                    except:
                        continue
                    
        except Exception as e:
            print(f"   ❌ Failed to lock screen: {e}")
    
        self.is_locked = True
    
        if self.lock_screen_callback:
            self.lock_screen_callback()
    
    def unlock_screen(self):
        """Note: Can't programmatically unlock Windows for security reasons"""
        if not self.is_locked:
            return
        
        print(f"\n✅ Admin detected!")
        print("   Please unlock Windows manually with your credentials")
        self.is_locked = False
        self.intrusion_detected = False
        self.alert_cooldown = 30
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process frame for face detection and recognition - OPTIMIZED"""
        if not self.is_monitoring:
            return frame
    
        # Update cooldown
        if self.alert_cooldown > 0:
            self.alert_cooldown -= 1
    
        self.frame_counter += 1
    
        # Skip frames for performance
        if self.frame_counter % self.frame_skip != 0:
            return self._draw_overlay(frame)
    
        # Downscale frame for faster face detection
        h, w = frame.shape[:2]
        scale = 0.5
        small_frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    
        # Detect faces
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 3, minSize=(50, 50))
    
        # Scale faces back
        scaled_faces = [(int(x/scale), int(y/scale), int(w/scale), int(h/scale)) 
                        for (x, y, w, h) in faces]
    
        # Process each detected face
        self.current_persons = []
        admin_detected_this_frame = False
    
        for (x, y, fw, fh) in scaled_faces:
            if fw < 50 or fh < 50:
                continue
            
            face_img = frame[y:y+fh, x:x+fw]
            name, confidence, is_admin = self.face_system.recognize_face(face_img)
        
            person = DetectedPerson(
                face_location=(x, y, fw, fh),
                name=name,
                confidence=confidence,
                is_admin=is_admin,
                timestamp=time.time()
            )
            self.current_persons.append(person)
        
            if is_admin:
                admin_detected_this_frame = True
    
        # Update history
        self.admin_history.append(admin_detected_this_frame)
        self.intrusion_history.append(len(scaled_faces) > 0 and not admin_detected_this_frame)
    
        # Determine admin presence (faster response - 3 out of 5 frames)
        if len(self.admin_history) > 0:
            self.admin_present = sum(self.admin_history) >= 3
    
        # Determine intrusion (faster response - 3 out of 5 frames)
        if len(self.intrusion_history) > 0:
            has_intrusion = sum(self.intrusion_history) >= 3
            self.intrusion_detected = has_intrusion and not self.admin_present
    
        # IMMEDIATE LOCK when intrusion detected and no admin
        if self.intrusion_detected and not self.is_locked and self.alert_cooldown == 0:
            if not self.admin_present:
                print("\n" + "!" * 50)
                print("⚠️ UNKNOWN PERSON DETECTED - LOCKING SCREEN NOW!")
                print("!" * 50)
                threading.Thread(target=self.lock_windows_screen, daemon=True).start()
                self.alert_cooldown = 20  # Prevent repeated locks for 20 frames
    
        # Handle unlock message when admin appears
        if self.admin_present and self.is_locked:
            self.unlock_screen()
    
        return self._draw_overlay(frame)
    
    def _draw_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw detection overlay on frame - OPTIMIZED (minimal drawing)"""
        h, w = frame.shape[:2]
        
        # Draw simple status bar (only changes when status changes)
        if self.is_locked:
            status_color = (0, 0, 255)
            status_text = "LOCKED - Intrusion"
        elif self.admin_present:
            status_color = (0, 255, 0)
            status_text = "Admin Present"
        elif self.intrusion_detected:
            status_color = (0, 0, 255)
            status_text = "Intrusion!"
        else:
            status_color = (255, 165, 0)
            status_text = "Monitoring"
        
        cv2.rectangle(frame, (0, 0), (w, 35), status_color, -1)
        cv2.putText(frame, status_text, (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Draw face boxes (only for admin or unknown)
        for person in self.current_persons:
            x, y, fw, fh = person.face_location
            color = (0, 255, 0) if person.is_admin else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x+fw, y+fh), color, 2)
        
        return frame
    
    def start_monitoring(self):
        """Start intrusion monitoring"""
        self.is_monitoring = True
        self.is_locked = False
        print("\nIntrusion detection ACTIVE")
        print("   - Admin present: System stays unlocked")
        print("   - Unknown person without admin: Windows locks")
    
    def stop_monitoring(self):
        """Stop intrusion monitoring"""
        self.is_monitoring = False
        print("\nIntrusion detection OFF")
    
    def toggle_monitoring(self):
        """Toggle monitoring on/off"""
        if self.is_monitoring:
            self.stop_monitoring()
        else:
            self.start_monitoring()
    
    def register_admin_face(self, cap):
        """Register a new admin face using existing camera"""
        self.face_system.add_admin_face_from_camera(cap)
        self.face_system.train_from_directory()
    
    def get_status(self) -> Dict:
        """Get current system status"""
        return {
            'monitoring': self.is_monitoring,
            'admin_present': self.admin_present,
            'intrusion_detected': self.intrusion_detected,
            'is_locked': self.is_locked,
            'faces_detected': len(self.current_persons),
            'known_faces': len(self.face_system.known_face_names)
        }

# ============================================================================
# INTEGRATION WITH MAIN GESTURE SYSTEM
# ============================================================================

class IntrusionAwareGestureSystem:
    """Wrapper that adds intrusion detection to the gesture system - Gestures NEVER disabled"""
    
    def __init__(self, gesture_system, camera):
        self.gesture_system = gesture_system
        self.camera = camera
        self.intrusion_detector = IntrusionDetector(frame_skip=15)
        self.intrusion_detector.initialize()
        self.intrusion_detector.set_lock_screen_callback(self._on_intrusion_lock)
        
    def _on_intrusion_lock(self):
        """Called when intrusion locks the screen - Just log, don't disable gestures"""
        print("\nWindows screen locked due to intrusion")
        print("   Gesture controls remain active")
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Process frame with intrusion detection - Gestures always work"""
        # Run intrusion detection (this may lock Windows)
        frame = self.intrusion_detector.process_frame(frame)
        
        # ALWAYS process gestures - never disable
        frame = self.gesture_system.process_frame(frame)
        
        return frame
    
    def handle_keyboard(self, key: int):
        """Handle keyboard input for intrusion system"""
        if key == ord('i') or key == ord('I'):
            self.intrusion_detector.toggle_monitoring()
        
        elif key == ord('r') or key == ord('R'):
            print("\nRegister new admin face...")
            self.intrusion_detector.register_admin_face(self.camera)
        
        elif key == ord('s') or key == ord('S'):
            status = self.intrusion_detector.get_status()
            print("\n" + "=" * 40)
            print("INTRUSION SYSTEM STATUS")
            print("=" * 40)
            for k, v in status.items():
                print(f"  {k}: {v}")
            print("=" * 40)
        
        # Always pass to gesture system
        self.gesture_system.handle_keyboard(key)

# ============================================================================
# STANDALONE TEST
# ============================================================================

def test_intrusion_system():
    """Test the intrusion detection system standalone"""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        return
    
    detector = IntrusionDetector(frame_skip=10)
    detector.initialize()
    detector.start_monitoring()
    
    print("\n" + "=" * 50)
    print("INTRUSION DETECTION TEST MODE")
    print("=" * 50)
    print("Controls:")
    print("  - ESC: Quit")
    print("  - SPACE: Toggle monitoring")
    print("  - R: Register new admin face")
    print("  - S: Show status")
    print("=" * 50)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame = cv2.flip(frame, 1)
        frame = detector.process_frame(frame)
        
        cv2.putText(frame, "ESC:Quit | SPACE:Toggle | R:Register | S:Status", 
                   (10, frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        cv2.imshow('Intrusion Detection Test', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        elif key == 32:
            detector.toggle_monitoring()
        elif key == ord('r') or key == ord('R'):
            detector.register_admin_face(cap)
        elif key == ord('s') or key == ord('S'):
            status = detector.get_status()
            print(f"\nStatus: {status}")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_intrusion_system()