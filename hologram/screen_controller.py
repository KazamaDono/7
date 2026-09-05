# screen_controller.py - Fixed with coordinate transformation

import cv2
import numpy as np
import math
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class Viewport:
    """Viewport settings for rendering"""
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    rotation: float = 0.0

class ScreenController:
    """Handles screen scaling, zooming, and viewport control with coordinate transformation"""
    
    def __init__(self, initial_width: int = 1280, initial_height: int = 720):
        self.base_width = initial_width
        self.base_height = initial_height
        self.current_width = initial_width
        self.current_height = initial_height
        
        # Zoom settings (applies to footage)
        self.zoom = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 4.0
        self.zoom_step = 0.1
        
        # Pan settings
        self.pan_x = 0.0
        self.pan_y = 0.0
        
        # Fullscreen window state
        self.is_fullscreen = False
        self.window_name = "Gesture Control"
        
        # Smooth zoom animation
        self.target_zoom = 1.0
        self.current_zoom = 1.0
        self.zoom_speed = 0.15
        
        # Mouse drag for pan
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_start_pan_x = 0
        self.drag_start_pan_y = 0
        
        # Fill mode
        self.fill_mode = "crop"
        
        # Store transformation parameters for coordinate conversion
        self.last_transform = {
            'scale_x': 1.0,
            'scale_y': 1.0,
            'offset_x': 0,
            'offset_y': 0,
            'crop_x': 0,
            'crop_y': 0,
            'zoom_w': 0,
            'zoom_h': 0
        }
        
    def update_animation(self):
        """Smooth zoom animation"""
        diff = self.target_zoom - self.current_zoom
        if abs(diff) < 0.01:
            self.current_zoom = self.target_zoom
        else:
            self.current_zoom += diff * self.zoom_speed
        self.zoom = self.current_zoom
    
    def zoom_in(self, amount: float = None):
        if amount is None:
            amount = self.zoom_step
        self.target_zoom = min(self.max_zoom, self.target_zoom + amount)
        print(f"🔍 Zoom: {self.target_zoom:.2f}x")
    
    def zoom_out(self, amount: float = None):
        if amount is None:
            amount = self.zoom_step
        self.target_zoom = max(self.min_zoom, self.target_zoom - amount)
        print(f"🔍 Zoom: {self.target_zoom:.2f}x")
    
    def reset_zoom(self):
        self.target_zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        print("🔄 Zoom reset to 1.0x")
    
    def set_zoom(self, zoom: float):
        self.target_zoom = max(self.min_zoom, min(self.max_zoom, zoom))
        print(f"🔍 Zoom set to: {self.target_zoom:.2f}x")
    
    def start_pan(self, x: int, y: int):
        self.dragging = True
        self.drag_start_x = x
        self.drag_start_y = y
        self.drag_start_pan_x = self.pan_x
        self.drag_start_pan_y = self.pan_y
    
    def update_pan(self, x: int, y: int):
        if not self.dragging:
            return
        dx = (x - self.drag_start_x) / self.current_width
        dy = (y - self.drag_start_y) / self.current_height
        self.pan_x = self.drag_start_pan_x + dx * 2
        self.pan_y = self.drag_start_pan_y + dy * 2
        
        max_pan = (self.zoom - 0.5) * 0.8
        self.pan_x = max(-max_pan, min(max_pan, self.pan_x))
        self.pan_y = max(-max_pan, min(max_pan, self.pan_y))
    
    def end_pan(self):
        self.dragging = False
    
    def reset_pan(self):
        self.pan_x = 0.0
        self.pan_y = 0.0
        print("📍 Pan reset to center")
    
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        print(f"🖥️ Fullscreen window: {'ON' if self.is_fullscreen else 'OFF'}")
    
    def set_fill_mode(self, mode: str):
        if mode in ["crop", "fit", "stretch"]:
            self.fill_mode = mode
            print(f"📐 Fill mode: {mode}")
    
    def apply_fill_transform(self, frame: np.ndarray) -> np.ndarray:
        """Apply fill transformation and store transform parameters"""
        if frame is None:
            return frame
        
        h, w = frame.shape[:2]
        screen_h, screen_w = self.current_height, self.current_width
        
        # Reset transform tracking
        self.last_transform = {
            'scale_x': 1.0,
            'scale_y': 1.0,
            'offset_x': 0,
            'offset_y': 0,
            'crop_x': 0,
            'crop_y': 0,
            'zoom_w': w,
            'zoom_h': h,
            'original_w': w,
            'original_h': h
        }
        
        # Apply zoom first
        if self.zoom != 1.0:
            zoom_w = int(w * self.zoom)
            zoom_h = int(h * self.zoom)
            frame = cv2.resize(frame, (zoom_w, zoom_h))
            self.last_transform['zoom_w'] = zoom_w
            self.last_transform['zoom_h'] = zoom_h
            h, w = zoom_w, zoom_h
        
        # Apply fill mode
        if self.fill_mode == "stretch":
            scale_x = screen_w / w
            scale_y = screen_h / h
            frame = cv2.resize(frame, (screen_w, screen_h))
            self.last_transform['scale_x'] = scale_x
            self.last_transform['scale_y'] = scale_y
            
        elif self.fill_mode == "fit":
            scale = min(screen_w / w, screen_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h))
            
            canvas = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
            x_offset = (screen_w - new_w) // 2
            y_offset = (screen_h - new_h) // 2
            canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = frame
            frame = canvas
            
            self.last_transform['scale_x'] = scale
            self.last_transform['scale_y'] = scale
            self.last_transform['offset_x'] = x_offset
            self.last_transform['offset_y'] = y_offset
            
        elif self.fill_mode == "crop":
            scale = max(screen_w / w, screen_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            frame = cv2.resize(frame, (new_w, new_h))
            
            x_start = (new_w - screen_w) // 2
            y_start = (new_h - screen_h) // 2
            
            self.last_transform['crop_x'] = x_start
            self.last_transform['crop_y'] = y_start
            self.last_transform['scale_x'] = scale
            self.last_transform['scale_y'] = scale
            
            frame = frame[y_start:y_start+screen_h, x_start:x_start+screen_w]
        
        # Apply pan offset
        if self.pan_x != 0 or self.pan_y != 0:
            h, w = frame.shape[:2]
            pan_px_x = int(self.pan_x * w * 0.3)
            pan_px_y = int(self.pan_y * h * 0.3)
            
            self.last_transform['pan_x'] = pan_px_x
            self.last_transform['pan_y'] = pan_px_y
            
            canvas = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
            x_start = max(0, min(w - screen_w, pan_px_x))
            y_start = max(0, min(h - screen_h, pan_px_y))
            src_region = frame[y_start:y_start+screen_h, x_start:x_start+screen_w]
            
            if src_region.shape[0] == screen_h and src_region.shape[1] == screen_w:
                frame = src_region
            else:
                canvas[0:src_region.shape[0], 0:src_region.shape[1]] = src_region
                frame = canvas
        
        return frame
    
    def transform_hand_coordinates(self, x: float, y: float) -> Tuple[float, float]:
        """
        Transform hand coordinates from original frame space to displayed frame space
        This is critical for proper hand tracking when zoom/pan is active
        """
        # Start with original coordinates
        tx, ty = x, y
        
        # Apply zoom scaling
        if self.zoom != 1.0:
            zoom_w = self.last_transform.get('zoom_w', 1)
            zoom_h = self.last_transform.get('zoom_h', 1)
            orig_w = self.last_transform.get('original_w', 640)
            orig_h = self.last_transform.get('original_h', 480)
            
            # Scale coordinates to zoomed space
            tx = tx * (zoom_w / orig_w)
            ty = ty * (zoom_h / orig_h)
        
        # Apply fill mode transformations
        if self.fill_mode == "fit":
            scale = self.last_transform.get('scale_x', 1.0)
            offset_x = self.last_transform.get('offset_x', 0)
            offset_y = self.last_transform.get('offset_y', 0)
            tx = tx * scale + offset_x
            ty = ty * scale + offset_y
            
        elif self.fill_mode == "crop":
            scale = self.last_transform.get('scale_x', 1.0)
            crop_x = self.last_transform.get('crop_x', 0)
            crop_y = self.last_transform.get('crop_y', 0)
            tx = tx * scale - crop_x
            ty = ty * scale - crop_y
            
        elif self.fill_mode == "stretch":
            scale_x = self.last_transform.get('scale_x', 1.0)
            scale_y = self.last_transform.get('scale_y', 1.0)
            tx = tx * scale_x
            ty = ty * scale_y
        
        # Apply pan
        pan_x = self.last_transform.get('pan_x', 0)
        pan_y = self.last_transform.get('pan_y', 0)
        tx = tx - pan_x
        ty = ty - pan_y
        
        # Clamp to screen bounds
        tx = max(0, min(self.current_width, tx))
        ty = max(0, min(self.current_height, ty))
        
        return (tx, ty)
    
    def draw_controls_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Draw on-screen controls overlay"""
        h, w = frame.shape[:2]
        
        # Semi-transparent overlay at bottom
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 80), (350, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        
        # Zoom indicator
        cv2.putText(frame, f"ZOOM: {self.zoom:.1f}x", (10, h - 55),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # Zoom bar
        bar_width = 100
        filled = int(bar_width * (self.zoom - self.min_zoom) / (self.max_zoom - self.min_zoom))
        cv2.rectangle(frame, (120, h - 62), (120 + bar_width, h - 52), (50, 50, 50), -1)
        cv2.rectangle(frame, (120, h - 62), (120 + filled, h - 52), (0, 255, 255), -1)
        
        # Fill mode indicator
        mode_colors = {"crop": (0, 255, 0), "fit": (255, 255, 0), "stretch": (255, 165, 0)}
        cv2.putText(frame, f"MODE: {self.fill_mode.upper()}", (10, h - 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, mode_colors.get(self.fill_mode, (150, 150, 150)), 1)
        
        # Controls hint
        cv2.putText(frame, "Wheel:Zoom | MMB+Move:Pan | Z:Reset | F:Fullscreen | C:Cycle Mode", 
                   (w - 450, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1)
        
        return frame
    
    def handle_mouse(self, event: int, x: int, y: int, flags: int) -> bool:
        """Handle mouse events for zoom/pan"""
        if event == cv2.EVENT_MOUSEWHEEL:
            if flags > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return True
        elif event == cv2.EVENT_MBUTTONDOWN:
            self.start_pan(x, y)
            return True
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.dragging:
                self.update_pan(x, y)
            return True
        elif event == cv2.EVENT_MBUTTONUP:
            self.end_pan()
            return True
        return False
    
    def handle_keyboard(self, key: int) -> bool:
        """Handle keyboard shortcuts for screen control"""
        if key == ord('=') or key == ord('+'):
            self.zoom_in()
            return True
        elif key == ord('-') or key == ord('_'):
            self.zoom_out()
            return True
        elif key == ord('0') or key == ord(')'):
            self.reset_zoom()
            return True
        elif key == ord('z') or key == ord('Z'):
            self.reset_zoom()
            return True
        elif key == ord('p') or key == ord('P'):
            self.reset_pan()
            return True
        elif key == ord('f') or key == ord('F'):
            self.toggle_fullscreen()
            return True
        elif key == ord('c') or key == ord('C'):
            modes = ["crop", "fit", "stretch"]
            current_idx = modes.index(self.fill_mode)
            next_idx = (current_idx + 1) % len(modes)
            self.set_fill_mode(modes[next_idx])
            return True
        return False


class GestureScreenController:
    """Screen controller with gesture support - FIXED coordinate transformation"""
    
    def __init__(self, screen_controller: ScreenController):
        self.screen = screen_controller
        
        # Gesture tracking
        self.pinch_active = False
        self.initial_pinch_distance = 0
        self.initial_zoom = 1.0
        
        # Two-finger pan
        self.pan_active = False
        self.initial_pan_point = None
        
        # Store transformed points for consistent tracking
        self.last_transformed_finger1 = None
        self.last_transformed_finger2 = None
        
    def _transform_point(self, point: Tuple[float, float]) -> Tuple[float, float]:
        """Transform a single point using screen controller"""
        if point is None:
            return None
        return self.screen.transform_hand_coordinates(point[0], point[1])
    
    def _transform_points(self, finger1: Tuple[float, float], finger2: Tuple[float, float]):
        """Transform both finger points"""
        t1 = self._transform_point(finger1)
        t2 = self._transform_point(finger2)
        return t1, t2
    
    def handle_pinch_start(self, finger1: Tuple[float, float], finger2: Tuple[float, float]):
        """Start pinch gesture - transform coordinates first"""
        t1, t2 = self._transform_points(finger1, finger2)
        if t1 is None or t2 is None:
            return
            
        self.pinch_active = True
        dx = t1[0] - t2[0]
        dy = t1[1] - t2[1]
        self.initial_pinch_distance = math.hypot(dx, dy)
        self.initial_zoom = self.screen.zoom
        self.last_transformed_finger1 = t1
        self.last_transformed_finger2 = t2
    
    def handle_pinch_update(self, finger1: Tuple[float, float], finger2: Tuple[float, float]):
        """Update pinch gesture - transform coordinates first"""
        if not self.pinch_active:
            return
        
        t1, t2 = self._transform_points(finger1, finger2)
        if t1 is None or t2 is None:
            return
        
        dx = t1[0] - t2[0]
        dy = t1[1] - t2[1]
        current_distance = math.hypot(dx, dy)
        
        if self.initial_pinch_distance > 0:
            scale = current_distance / self.initial_pinch_distance
            new_zoom = self.initial_zoom * scale
            self.screen.set_zoom(new_zoom)
        
        self.last_transformed_finger1 = t1
        self.last_transformed_finger2 = t2
    
    def handle_pinch_end(self):
        """End pinch gesture"""
        self.pinch_active = False
        self.last_transformed_finger1 = None
        self.last_transformed_finger2 = None
    
    def handle_two_finger_pan_start(self, point: Tuple[float, float]):
        """Start two-finger pan - transform coordinate first"""
        t_point = self._transform_point(point)
        if t_point is None:
            return
            
        self.pan_active = True
        self.initial_pan_point = t_point
    
    def handle_two_finger_pan_update(self, point: Tuple[float, float]):
        """Update two-finger pan - transform coordinate first"""
        if not self.pan_active or self.initial_pan_point is None:
            return
        
        t_point = self._transform_point(point)
        if t_point is None:
            return
        
        dx = t_point[0] - self.initial_pan_point[0]
        dy = t_point[1] - self.initial_pan_point[1]
        
        # Convert screen delta to pan delta
        pan_dx = dx / self.screen.current_width
        pan_dy = dy / self.screen.current_height
        
        self.screen.pan_x += pan_dx
        self.screen.pan_y += pan_dy
        
        # Clamp
        max_pan = (self.screen.zoom - 0.5) * 0.8
        self.screen.pan_x = max(-max_pan, min(max_pan, self.screen.pan_x))
        self.screen.pan_y = max(-max_pan, min(max_pan, self.screen.pan_y))
        
        # Update initial point for smooth continuous pan
        self.initial_pan_point = t_point
    
    def handle_two_finger_pan_end(self):
        """End two-finger pan"""
        self.pan_active = False
        self.initial_pan_point = None
    
    def reset(self):
        """Reset all gesture transformations"""
        self.screen.reset_zoom()
        self.screen.reset_pan()
        self.pinch_active = False
        self.pan_active = False
        self.last_transformed_finger1 = None
        self.last_transformed_finger2 = None