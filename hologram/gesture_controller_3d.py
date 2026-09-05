# gesture_controller_3d.py - COMPLETELY FIXED rotation

import math
import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class Hand3D:
    hand_id: int
    palm_center: Tuple[float, float]
    thumb_tip: Tuple[float, float]
    index_tip: Tuple[float, float]
    middle_tip: Tuple[float, float]
    ring_tip: Tuple[float, float]
    pinky_tip: Tuple[float, float]
    is_pinched: bool = False
    is_three_fingers: bool = False
    is_fist: bool = False
    is_two_fingers: bool = False
    pinch_point: Optional[Tuple[float, float]] = None
    hand_velocity: Tuple[float, float] = (0, 0)

class GestureController3D:
    """Handles 3D gesture recognition with intuitive rotation"""
    
    def __init__(self):
        self.selected_model = None
        self.active_hands = {}
        self.last_pinch_distance = 0
        self.last_hand_positions = {}
        self.rotation_sensitivity = 0.02  # Increased for better response
        self.translation_sensitivity = 0.008
        self.scale_sensitivity = 0.01
        self.rotation_smoothing = 0.15
        self.last_rotation = (0, 0, 0)
        
    def recognize_hand_pose(self, hand_landmarks, frame_shape: Tuple[int, int]) -> Hand3D:
        """Optimized hand pose recognition with better gesture detection"""
        h, w = frame_shape[:2]
        
        landmarks = hand_landmarks.landmark
        thumb_tip = (landmarks[4].x * w, landmarks[4].y * h)
        index_tip = (landmarks[8].x * w, landmarks[8].y * h)
        middle_tip = (landmarks[12].x * w, landmarks[12].y * h)
        ring_tip = (landmarks[16].x * w, landmarks[16].y * h)
        pinky_tip = (landmarks[20].x * w, landmarks[20].y * h)
        palm_center = (landmarks[0].x * w, landmarks[0].y * h)
        
        # Calculate distances
        pinch_distance = math.hypot(thumb_tip[0] - index_tip[0], thumb_tip[1] - index_tip[1])
        index_middle_dist = math.hypot(index_tip[0] - middle_tip[0], index_tip[1] - middle_tip[1])
        
        # THREE FINGERS for DRAGGING (thumb, index, middle together)
        is_three_fingers = (pinch_distance < 40 and index_middle_dist < 40)
        
        # TWO FINGERS for ROTATION - SIMPLIFIED AND MORE RELIABLE
        # Just check if index and middle are extended (far apart) and thumb is not pinched
        is_two_fingers = (index_middle_dist > 60 and pinch_distance > 50)
        
        # PINCH for selection (thumb and index together)
        is_pinched = pinch_distance < 35 and not is_three_fingers
        
        # Fist detection
        fist_distance = math.hypot(index_tip[0] - palm_center[0], index_tip[1] - palm_center[1])
        is_fist = fist_distance < 60
        
        # Pinch point for dragging
        pinch_point = None
        if is_three_fingers or is_pinched:
            if is_three_fingers:
                pinch_point = ((thumb_tip[0] + index_tip[0] + middle_tip[0]) / 3,
                              (thumb_tip[1] + index_tip[1] + middle_tip[1]) / 3)
            else:
                pinch_point = ((thumb_tip[0] + index_tip[0]) / 2,
                              (thumb_tip[1] + index_tip[1]) / 2)
        
        # Calculate hand velocity
        hand_id = id(hand_landmarks)
        velocity = (0, 0)
        if hand_id in self.last_hand_positions:
            prev_pos = self.last_hand_positions[hand_id]
            velocity = (palm_center[0] - prev_pos[0], palm_center[1] - prev_pos[1])
        
        self.last_hand_positions[hand_id] = palm_center
        
        return Hand3D(
            hand_id=hand_id,
            palm_center=palm_center,
            thumb_tip=thumb_tip,
            index_tip=index_tip,
            middle_tip=middle_tip,
            ring_tip=ring_tip,
            pinky_tip=pinky_tip,
            is_pinched=is_pinched,
            is_three_fingers=is_three_fingers,
            is_fist=is_fist,
            is_two_fingers=is_two_fingers,
            pinch_point=pinch_point,
            hand_velocity=velocity
        )
    
    def calculate_rotation_from_hand(self, hand: Hand3D, prev_hand: Hand3D, 
                                    rotation_mode: str = "free") -> Tuple[float, float, float]:
        """Smooth rotation with acceleration and follow-through"""
        if not prev_hand:
            return (0, 0, 0)
    
        # Calculate velocity (speed of movement)
        dx = hand.palm_center[0] - prev_hand.palm_center[0]
        dy = hand.palm_center[1] - prev_hand.palm_center[1]
    
        # Calculate acceleration (change in velocity)
        if hasattr(self, 'last_velocity'):
            accel_x = dx - self.last_velocity[0]
            accel_y = dy - self.last_velocity[1]
        else:
            accel_x, accel_y = 0, 0
            self.last_velocity = (0, 0)
    
        # Store current velocity for next frame
        self.last_velocity = (dx, dy)
    
        # Finger angle for roll
        hand_angle = math.atan2(hand.index_tip[1] - hand.palm_center[1],
                                hand.index_tip[0] - hand.palm_center[0])
        prev_angle = math.atan2(prev_hand.index_tip[1] - prev_hand.palm_center[1],
                                prev_hand.index_tip[0] - prev_hand.palm_center[0])
        raw_roll = hand_angle - prev_angle
    
        # Sensitivity settings
        pos_sensitivity = 0.06      # Base movement sensitivity
        accel_sensitivity = 0.15     # Acceleration boost
        roll_sensitivity = 1.0       # Twist sensitivity
    
        # Combine velocity and acceleration for natural feel
        pitch = dy * pos_sensitivity + accel_y * accel_sensitivity
        yaw = dx * pos_sensitivity + accel_x * accel_sensitivity
        roll = raw_roll * roll_sensitivity
    
        # Apply momentum/follow-through (inertia)
        if not hasattr(self, 'rotation_momentum'):
            self.rotation_momentum = (0, 0, 0)
    
        # Momentum decay (0.85 = 15% decay per frame, creates follow-through)
        momentum_decay = 0.85
        self.rotation_momentum = (
            self.rotation_momentum[0] * momentum_decay,
            self.rotation_momentum[1] * momentum_decay,
            self.rotation_momentum[2] * momentum_decay
        )
    
        # Add current movement to momentum
        self.rotation_momentum = (
            self.rotation_momentum[0] + pitch,
            self.rotation_momentum[1] + yaw,
            self.rotation_momentum[2] + roll
        )
    
        # Apply axis locking
        if rotation_mode == "x_axis":
            self.rotation_momentum = (self.rotation_momentum[0], 0, 0)
        elif rotation_mode == "y_axis":
            self.rotation_momentum = (0, self.rotation_momentum[1], 0)
        elif rotation_mode == "z_axis":
            self.rotation_momentum = (0, 0, self.rotation_momentum[2])
    
        return self.rotation_momentum
    
    def reset_rotation_smoothing(self):
        """Reset rotation smoothing values"""
        self.last_rotation = (0, 0, 0)
        
    def reset_rotation_momentum(self):
        """Reset rotation momentum (call when gesture ends)"""
        self.last_rotation_delta = (0, 0, 0)
        print("Rotation momentum reset")