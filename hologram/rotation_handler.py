# rotation_handler.py - Advanced smooth rotation system with follow-through
"""
Dedicated rotation handler for 3D model manipulation
Features:
- Smooth, continuous rotation
- Momentum/inertia (follow-through)
- Acceleration-based movement
- Configurable sensitivity
- Multiple rotation modes
- Visual feedback for rotation
"""

import math
import time
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class RotationState:
    """Current rotation state of the model"""
    pitch: float = 0.0      # X-axis rotation (up/down)
    yaw: float = 0.0        # Y-axis rotation (left/right)
    roll: float = 0.0       # Z-axis rotation (twist)

@dataclass
class RotationVelocity:
    """Velocity and momentum for smooth rotation"""
    pitch_vel: float = 0.0
    yaw_vel: float = 0.0
    roll_vel: float = 0.0

class SmoothRotationHandler:
    """
    Handles smooth 3D rotation with momentum and follow-through
    Like the keyboard controls but with hand gestures
    """
    
    def __init__(self):
        # Current rotation state
        self.current_rotation = RotationState()
        
        # Velocity for momentum
        self.velocity = RotationVelocity()
        
        # Previous hand positions for delta calculation
        self.prev_hand_pos = None
        self.prev_hand_angle = None
        self.last_update_time = time.time()
        
        # Rotation settings
        self.sensitivity = 0.08        # Base sensitivity (0.05-0.15)
        self.acceleration = 0.15        # Acceleration boost (0.1-0.3)
        self.momentum_decay = 0.92      # How fast momentum fades (0.85-0.98)
        self.max_velocity = 0.5         # Max rotation speed per frame
        self.smoothing = 0.7            # Smoothing factor (0.5-0.9)
        
        # Rotation mode
        self.rotation_mode = "free"     # free, x_axis, y_axis, z_axis
        
        # For smoothing
        self.last_delta = (0, 0, 0)
        
        # Visual feedback
        self.is_rotating = False
        self.rotation_intensity = 0.0   # 0-1 for visual feedback
        
    def update_from_hand_movement(self, hand_pos: Tuple[float, float], 
                                   hand_angle: float = None) -> Tuple[float, float, float]:
        """
        Update rotation based on hand movement
        Returns: (pitch_delta, yaw_delta, roll_delta) to apply
        """
        current_time = time.time()
        dt = min(current_time - self.last_update_time, 0.033)  # Cap at 30fps
        self.last_update_time = current_time
        
        if self.prev_hand_pos is None:
            self.prev_hand_pos = hand_pos
            self.prev_hand_angle = hand_angle
            return (0, 0, 0)
        
        # Calculate raw movement
        dx = hand_pos[0] - self.prev_hand_pos[0]
        dy = hand_pos[1] - self.prev_hand_pos[1]
        
        # Calculate velocity (speed of movement)
        velocity_x = dx / dt if dt > 0 else 0
        velocity_y = dy / dt if dt > 0 else 0
        
        # Calculate acceleration (change in velocity)
        if hasattr(self, 'last_velocity'):
            accel_x = velocity_x - self.last_velocity[0]
            accel_y = velocity_y - self.last_velocity[1]
        else:
            accel_x, accel_y = 0, 0
        
        self.last_velocity = (velocity_x, velocity_y)
        
        # Base rotation from position change
        pitch = dy * self.sensitivity
        yaw = dx * self.sensitivity
        
        # Add acceleration boost for faster movement = faster rotation
        pitch += accel_y * self.acceleration
        yaw += accel_x * self.acceleration
        
        # Roll from hand twist (if angle provided)
        roll = 0
        if hand_angle is not None and self.prev_hand_angle is not None:
            raw_roll = hand_angle - self.prev_hand_angle
            # Normalize angle difference
            if raw_roll > math.pi:
                raw_roll -= 2 * math.pi
            elif raw_roll < -math.pi:
                raw_roll += 2 * math.pi
            roll = raw_roll * 0.8  # Roll sensitivity
        
        # Apply smoothing to raw delta
        smooth_pitch = self.last_delta[0] * self.smoothing + pitch * (1 - self.smoothing)
        smooth_yaw = self.last_delta[1] * self.smoothing + yaw * (1 - self.smoothing)
        smooth_roll = self.last_delta[2] * self.smoothing + roll * (1 - self.smoothing)
        
        self.last_delta = (smooth_pitch, smooth_yaw, smooth_roll)
        
        # Update velocity for momentum
        self.velocity.pitch_vel = self.velocity.pitch_vel * self.momentum_decay + smooth_pitch * (1 - self.momentum_decay)
        self.velocity.yaw_vel = self.velocity.yaw_vel * self.momentum_decay + smooth_yaw * (1 - self.momentum_decay)
        self.velocity.roll_vel = self.velocity.roll_vel * self.momentum_decay + smooth_roll * (1 - self.momentum_decay)
        
        # Clamp velocities
        self.velocity.pitch_vel = max(-self.max_velocity, min(self.max_velocity, self.velocity.pitch_vel))
        self.velocity.yaw_vel = max(-self.max_velocity, min(self.max_velocity, self.velocity.yaw_vel))
        self.velocity.roll_vel = max(-self.max_velocity, min(self.max_velocity, self.velocity.roll_vel))
        
        # Store for next frame
        self.prev_hand_pos = hand_pos
        self.prev_hand_angle = hand_angle
        
        # Determine if actively rotating
        self.is_rotating = abs(self.velocity.pitch_vel) > 0.001 or \
                          abs(self.velocity.yaw_vel) > 0.001 or \
                          abs(self.velocity.roll_vel) > 0.001
        
        # Calculate rotation intensity for visual feedback
        self.rotation_intensity = min(1.0, 
            abs(self.velocity.pitch_vel) * 2 + 
            abs(self.velocity.yaw_vel) * 2 + 
            abs(self.velocity.roll_vel) * 1)
        
        # Apply axis locking based on mode
        if self.rotation_mode == "x_axis":
            return (self.velocity.pitch_vel, 0, 0)
        elif self.rotation_mode == "y_axis":
            return (0, self.velocity.yaw_vel, 0)
        elif self.rotation_mode == "z_axis":
            return (0, 0, self.velocity.roll_vel)
        else:  # free
            return (self.velocity.pitch_vel, self.velocity.yaw_vel, self.velocity.roll_vel)
    
    def apply_rotation(self, current_rotation: Tuple[float, float, float], 
                       delta: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Apply rotation delta to current rotation"""
        return (
            current_rotation[0] + delta[0],
            current_rotation[1] + delta[1],
            current_rotation[2] + delta[2]
        )
    
    def reset_momentum(self):
        """Reset all momentum/velocity (call when gesture ends)"""
        self.velocity = RotationVelocity()
        self.last_delta = (0, 0, 0)
        self.prev_hand_pos = None
        self.prev_hand_angle = None
        self.is_rotating = False
        self.rotation_intensity = 0.0
        print("🔄 Rotation momentum reset")
    
    def set_sensitivity(self, value: float):
        """Adjust rotation sensitivity"""
        self.sensitivity = max(0.02, min(0.2, value))
        print(f"Rotation sensitivity: {self.sensitivity:.3f}")
    
    def set_momentum_decay(self, value: float):
        """Adjust momentum decay (higher = more follow-through)"""
        self.momentum_decay = max(0.7, min(0.98, value))
        print(f"Momentum decay: {self.momentum_decay:.3f} (follow-through: {1-self.momentum_decay:.0%})")
    
    def set_rotation_mode(self, mode: str):
        """Set rotation axis lock"""
        if mode in ["free", "x_axis", "y_axis", "z_axis"]:
            self.rotation_mode = mode
            print(f"Rotation mode: {mode}")
    
    def get_visual_feedback(self) -> Tuple[str, Tuple[int, int, int]]:
        """Get visual feedback for UI"""
        if not self.is_rotating:
            return "Idle", (100, 100, 100)
        
        # Color based on rotation intensity
        intensity = min(255, int(self.rotation_intensity * 255))
        
        if abs(self.velocity.pitch_vel) > abs(self.velocity.yaw_vel):
            return "Rotating (Pitch)", (0, intensity, 255)
        elif abs(self.velocity.yaw_vel) > abs(self.velocity.pitch_vel):
            return "Rotating (Yaw)", (255, intensity, 0)
        else:
            return "Rotating", (0, 255, intensity)
    
    def create_rotation_indicator(self, frame, center_x, center_y):
        """Draw a visual rotation indicator on the frame"""
        if not self.is_rotating:
            return
        
        # Draw rotating circle based on intensity
        radius = 30 + int(self.rotation_intensity * 20)
        thickness = 2 + int(self.rotation_intensity * 3)
        
        # Color based on rotation direction
        pitch_intensity = abs(self.velocity.pitch_vel) / self.max_velocity
        yaw_intensity = abs(self.velocity.yaw_vel) / self.max_velocity
        
        if self.velocity.pitch_vel > 0:
            color = (0, 255, 0)  # Green for up
        elif self.velocity.pitch_vel < 0:
            color = (0, 100, 255)  # Orange for down
        elif self.velocity.yaw_vel > 0:
            color = (255, 100, 0)  # Blue for right
        elif self.velocity.yaw_vel < 0:
            color = (100, 100, 255)  # Purple for left
        else:
            color = (0, 255, 255)  # Yellow for twist
        
        # Draw rotating arc
        angle = (time.time() * 200) % 360
        for i in range(0, 360, 30):
            rad = math.radians(angle + i)
            x = center_x + int(radius * math.cos(rad))
            y = center_y + int(radius * math.sin(rad))
            cv2.circle(frame, (x, y), 3, color, -1)
        
        # Draw center indicator
        cv2.circle(frame, (center_x, center_y), 15, color, thickness)
        cv2.circle(frame, (center_x, center_y), 8, (255, 255, 255), -1)


class KeyboardRotationHandler:
    """
    Keyboard-based rotation (like your original code)
    For comparison and debugging
    """
    
    def __init__(self):
        self.sensitivity = 0.1
        
    def handle_key(self, key: int, current_rotation: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Handle keyboard rotation keys"""
        pitch, yaw, roll = current_rotation
        
        if key == ord('u') or key == ord('U'):
            pitch += self.sensitivity
        elif key == ord('j') or key == ord('J'):
            pitch -= self.sensitivity
        elif key == ord('h') or key == ord('H'):
            yaw -= self.sensitivity
        elif key == ord('l') or key == ord('L'):
            yaw += self.sensitivity
        elif key == ord('t') or key == ord('T'):
            # Twist left
            roll -= self.sensitivity
        elif key == ord('y') or key == ord('Y'):
            # Twist right
            roll += self.sensitivity
        elif key == ord('r') or key == ord('R'):
            # Reset rotation
            pitch, yaw, roll = 0, 0, 0
            
        return (pitch, yaw, roll)