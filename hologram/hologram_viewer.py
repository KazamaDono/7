# test_backup.py (updated main application with better drag)
"""
Main application for 3D model manipulation with hand gestures
"""

import os  
import cv2
import mediapipe as mp
import numpy as np
import math
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass
from model_manager import Model3D, ModelLoader, ModelDeconstructor
from gesture_controller_3d import GestureController3D, Hand3D
from intrusion_detection import IntrusionAwareGestureSystem
from ui_controller import HolographicUI
from rotation_handler import SmoothRotationHandler, KeyboardRotationHandler

# ============================================================================
# 3D RENDERER
# ============================================================================

class Simple3DRenderer:
    """Optimized 3D renderer for wireframe models with performance mode"""
    
    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2
        self.focal_length = 500
        self.wireframe_mode = False
        self.performance_mode = True
        self.max_faces_per_frame = 3000
        self._projected_points_cache = {}
        
    def project_3d_to_2d(self, x: float, y: float, z: float, 
                         rotation: Tuple[float, float, float] = (0, 0, 0),
                         position: Tuple[float, float, float] = (0, 0, 0),
                         scale: float = 1.0) -> Tuple[int, int]:
        
        x, y, z = x * scale, y * scale, z * scale
        pitch, yaw, roll = rotation
        
        cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
        x1 = x * cos_yaw + z * sin_yaw
        y1 = y
        z1 = -x * sin_yaw + z * cos_yaw
        
        cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
        x2 = x1
        y2 = y1 * cos_pitch - z1 * sin_pitch
        z2 = y1 * sin_pitch + z1 * cos_pitch
        
        cos_roll, sin_roll = math.cos(roll), math.sin(roll)
        x3 = x2 * cos_roll - y2 * sin_roll
        y3 = x2 * sin_roll + y2 * cos_roll
        z3 = z2
        
        x3 += position[0]
        y3 += position[1]
        z3 += position[2] + 5
        
        if z3 > 0.1:
            factor = self.focal_length / (z3 + self.focal_length)
            screen_x = self.center_x + x3 * factor * 100
            screen_y = self.center_y - y3 * factor * 100
            return (int(screen_x), int(screen_y))
        return (self.center_x, self.center_y)
    
    def render_model(self, frame: np.ndarray, model: Model3D):
        if not model or not model.vertices or not model.faces:
            return
        if abs(model.position[0]) > 10 or abs(model.position[1]) > 10:
            return

        self._projected_points_cache = {}

        for idx, vertex in enumerate(model.vertices):
            point_2d = self.project_3d_to_2d(
                vertex.x, vertex.y, vertex.z,
                model.rotation, model.position, model.scale
            )
            self._projected_points_cache[idx] = point_2d

        if self.performance_mode and len(model.faces) > self.max_faces_per_frame:
            face_stride = max(1, len(model.faces) // self.max_faces_per_frame)
            faces_rendered = 0
        
            for i, face in enumerate(model.faces):
                if i % face_stride != 0:
                    continue
                if faces_rendered >= self.max_faces_per_frame:
                    break
            
                if len(face.vertices) >= 3:
                    points_2d = []
                    for v_idx in face.vertices:
                        if v_idx in self._projected_points_cache:
                            points_2d.append(self._projected_points_cache[v_idx])
                
                    if len(points_2d) >= 3:
                        self._draw_face_fast(frame, points_2d, model.is_selected, model.color)
                        faces_rendered += 1
        else:
            for face in model.faces:
                if len(face.vertices) >= 3:
                    points_2d = []
                    for v_idx in face.vertices:
                        if v_idx in self._projected_points_cache:
                            points_2d.append(self._projected_points_cache[v_idx])
                
                    if len(points_2d) >= 3:
                        self._draw_face_fast(frame, points_2d, model.is_selected, model.color)

    def _draw_face_fast(self, frame: np.ndarray, points_2d: List[Tuple[int, int]], 
                        is_selected: bool, color: Tuple[int, int, int]):
        pts = np.array(points_2d, np.int32)
        pts = pts.reshape((-1, 1, 2))
    
        if is_selected:
            line_color = (0, 255, 0)
            thickness = 2
        else:
            line_color = color
            thickness = 1
    
        cv2.polylines(frame, [pts], True, line_color, thickness)
    
    def toggle_performance_mode(self):
        self.performance_mode = not self.performance_mode
        mode_status = "ON" if self.performance_mode else "OFF"
        print(f"Performance mode: {mode_status}")
        if self.performance_mode:
            print(f"   Max faces per frame: {self.max_faces_per_frame}")
        return self.performance_mode
    
    def set_max_faces(self, max_faces: int):
        self.max_faces_per_frame = max_faces
        print(f"Max faces per frame set to: {self.max_faces_per_frame}")
        
# ============================================================================
# INTERACTION MANAGER FOR 3D
# ============================================================================
class InteractionManager3D:
    """Handles 3D model interaction with gestures"""
    
    def __init__(self):
        self.selected_model = None
        self.last_hand_position = None
        self.gesture_controller = GestureController3D()
        self.hands_history = {}
        self.deconstructor = ModelDeconstructor()
        self.deconstructed_parts = []
        self.is_deconstructed = False
        self.drag_active = False
        self.rotate_active = False
        self.scale_active = False
        self.drag_start_position = None
        self.drag_start_model_position = None
        self.rotation_mode = "free"
        self.width = 640
        self.height = 480
        self.last_pinch_distance = 0
        self.last_drag_position = None
        self.scaling_start_distance = None
        self.scaling_start_scale = None
        self.rotation_handler = SmoothRotationHandler()
        self.keyboard_rotation = KeyboardRotationHandler()
        
    def update(self, hands: List[Hand3D], models: List[Model3D], current_time: float):
        drag_hands = [h for h in hands if h.is_three_fingers or h.is_pinched]
        rotate_hands = [h for h in hands if h.is_two_fingers]
        pinched_hands = [h for h in hands if h.is_pinched]
    
        # ====================================================================
        # TWO-HAND SCALING
        # ====================================================================
        if len(pinched_hands) >= 2 and self.selected_model:
            hand1, hand2 = pinched_hands[0], pinched_hands[1]
        
            if hand1.pinch_point and hand2.pinch_point:
                current_distance = math.hypot(hand2.pinch_point[0] - hand1.pinch_point[0],
                                            hand2.pinch_point[1] - hand1.pinch_point[1])
            
                if self.scaling_start_distance is None:
                    self.scaling_start_distance = current_distance
                    self.scaling_start_scale = self.selected_model.scale
                    print(f"Scaling started! Distance: {current_distance:.0f}, Scale: {self.selected_model.scale:.2f}")
            
                if self.scaling_start_distance is not None and self.scaling_start_distance > 0:
                    scale_factor = current_distance / self.scaling_start_distance
                    new_scale = self.scaling_start_scale * scale_factor
                    self.selected_model.scale = max(0.2, min(3.0, new_scale))
                    self.scale_active = True
            
                self.last_pinch_distance = current_distance
            else:
                self.scaling_start_distance = None
                self.scaling_start_scale = None
                self.scale_active = False
            return
    
        else:
            self.scaling_start_distance = None
            self.scaling_start_scale = None
            self.scale_active = False
    
        # ====================================================================
        # SINGLE HAND - DRAG
        # ====================================================================
        if len(drag_hands) == 1 and not self.rotate_active:
            hand = drag_hands[0]
    
            if hand.pinch_point:
                pinch_x, pinch_y = hand.pinch_point
        
                if not self.drag_active:
                    for model in reversed(models):
                        if self.is_point_over_model((pinch_x, pinch_y), model):
                            if self.selected_model and self.selected_model != model:
                                self.selected_model.is_selected = False
                        
                            self.selected_model = model
                            model.is_selected = True
                            self.drag_active = True
                            self.drag_start_position = (pinch_x, pinch_y)
                            self.drag_start_model_position = model.position
                            self.last_drag_position = (pinch_x, pinch_y)
                            break
            
                elif self.drag_active and self.selected_model:
                    if self.last_drag_position:
                        dx = (pinch_x - self.last_drag_position[0]) * self.gesture_controller.translation_sensitivity
                        dy = (pinch_y - self.last_drag_position[1]) * self.gesture_controller.translation_sensitivity
                    
                        current_pos = self.selected_model.position
                        new_position = (
                            current_pos[0] + dx,
                            current_pos[1] - dy,
                            current_pos[2]
                        )
                        self.selected_model.position = new_position
                        self.last_drag_position = (pinch_x, pinch_y)
    
        # ========================================================================
        # TWO FINGERS - SMOOTH ROTATION (using rotation_handler)
        # ========================================================================
        if len(rotate_hands) == 1 and not self.drag_active and not self.scale_active:
            hand = rotate_hands[0]
    
            # If no model selected, try to select one
            if not self.selected_model:
                for model in reversed(models):
                    if self.is_point_over_model(hand.index_tip, model) or \
                    self.is_point_over_model(hand.middle_tip, model):
                        self.selected_model = model
                        model.is_selected = True
                        print(f"✅ Selected model: {model.name}")
                        break
    
            if self.selected_model:
                self.rotate_active = True
        
                # Calculate hand angle for roll (twist)
                hand_angle = math.atan2(
                    hand.index_tip[1] - hand.palm_center[1],
                    hand.index_tip[0] - hand.palm_center[0]
                )
        
                # Update rotation using smooth handler
                rotation_delta = self.rotation_handler.update_from_hand_movement(
                    hand.palm_center, hand_angle
                )
        
                # Apply rotation to model
                current_rot = self.selected_model.rotation
                new_rotation = (
                    current_rot[0] + rotation_delta[0],
                    current_rot[1] + rotation_delta[1],
                    current_rot[2] + rotation_delta[2]
                )
                self.selected_model.rotation = new_rotation
        
                # Store hand for next frame
                hand_id = hand.hand_id
                self.hands_history[hand_id] = hand

        # Reset rotation when gesture ends
        if len(rotate_hands) == 0 and self.rotate_active:
            self.rotate_active = False
            self.rotation_handler.reset_momentum()

        # ====================================================================
        # RESET STATES
        # ====================================================================
        if len(drag_hands) == 0 and len(rotate_hands) == 0 and len(pinched_hands) == 0:
            self.drag_active = False
            self.rotate_active = False
            self.scale_active = False
            self.drag_start_position = None
            self.drag_start_model_position = None
            self.last_drag_position = None
            self.last_pinch_distance = 0
    
        current_ids = {h.hand_id for h in hands}
        self.hands_history = {hid: h for hid, h in self.hands_history.items() 
                            if hid in current_ids}
    
    def is_point_over_model(self, point: Tuple[float, float], model: Model3D) -> bool:
        if not model.vertices:
            return False
            
        bbox_min, bbox_max = model.get_bounding_box()
        
        corners = [
            (bbox_min[0], bbox_min[1], bbox_min[2]),
            (bbox_max[0], bbox_min[1], bbox_min[2]),
            (bbox_min[0], bbox_max[1], bbox_min[2]),
            (bbox_max[0], bbox_max[1], bbox_min[2]),
            (bbox_min[0], bbox_min[1], bbox_max[2]),
            (bbox_max[0], bbox_min[1], bbox_max[2]),
            (bbox_min[0], bbox_max[1], bbox_max[2]),
            (bbox_max[0], bbox_max[1], bbox_max[2])
        ]
        
        renderer = Simple3DRenderer(self.width, self.height)
        screen_points = []
        for corner in corners:
            screen_point = renderer.project_3d_to_2d(
                corner[0], corner[1], corner[2],
                model.rotation, model.position, model.scale
            )
            screen_points.append(screen_point)
        
        if not screen_points:
            return False
            
        min_x = min(p[0] for p in screen_points)
        max_x = max(p[0] for p in screen_points)
        min_y = min(p[1] for p in screen_points)
        max_y = max(p[1] for p in screen_points)
        
        padding = 30
        return (min_x - padding <= point[0] <= max_x + padding and
                min_y - padding <= point[1] <= max_y + padding)
    
    def set_rotation_mode(self, mode: str):
        self.rotation_mode = mode
        print(f"Rotation mode: {mode}")
    
    def set_screen_dimensions(self, width: int, height: int):
        self.width = width
        self.height = height

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # ============================================================================
    # INITIALIZATION
    # ============================================================================
    
    # Initialize camera
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    ui_controller = HolographicUI(640, 480)

    # Set callbacks
    def on_file_select(filepath):
        print(f"Loading model: {filepath}")
        model = ModelLoader.load_model_auto(filepath)
        if model:
            model.position = (0, 0, 0)
            model.scale = 0.8
            model.color = (100, 150, 200)
            loaded_models.append(model)
            print(f"Loaded: {model.name}")

    def on_shape_select(shape_type):
        print(f"Creating shape: {shape_type}")
        if shape_type == "cube":
            model = ModelLoader.create_cube(size=1.5, position=(0, 0, 0))
            model.color = (100, 150, 200)
        elif shape_type == "sphere":
            model = ModelLoader.create_sphere(radius=1.0, segments=20, position=(0, 0, 0))
            model.color = (150, 100, 200)
        elif shape_type == "cylinder":
            model = ModelLoader.create_cylinder(radius=0.8, height=1.5, segments=24, position=(0, 0, 0))
            model.color = (100, 200, 150)
        elif shape_type == "cone":
            model = ModelLoader.create_cone(radius=0.8, height=1.5, segments=24, position=(0, 0, 0))
            model.color = (200, 150, 100)
        elif shape_type == "pyramid":
            model = ModelLoader.create_pyramid(base_size=1.2, height=1.5, position=(0, 0, 0))
            model.color = (200, 100, 150)
        elif shape_type == "torus":
            model = ModelLoader.create_torus(radius=1.2, tube_radius=0.3, position=(0, 0, 0))
            model.color = (150, 200, 100)
        elif shape_type == "star":
            model = ModelLoader.create_star(outer_radius=1.2, inner_radius=0.5, points=5, position=(0, 0, 0))
            model.color = (255, 200, 100)
        else:
            return
    
        loaded_models.append(model)

    def on_intrusion_toggle(enabled):
        if enabled:
            intrusion_system.intrusion_detector.start_monitoring()
            print("Intrusion detection ENABLED")
        else:
            intrusion_system.intrusion_detector.stop_monitoring()
            print("Intrusion detection DISABLED")

    ui_controller.on_file_select = on_file_select
    ui_controller.on_shape_select = on_shape_select
    ui_controller.on_intrusion_toggle = on_intrusion_toggle
    
    # Initialize MediaPipe for hand tracking
    mp_hands = mp.solutions.hands
    hands_detector = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    mp_draw = mp.solutions.drawing_utils
    
    # Initialize 3D components
    renderer = Simple3DRenderer(640, 480)
    interaction = InteractionManager3D()
    interaction.set_screen_dimensions(640, 480)
    
    # Initialize model management
    model_loader = ModelLoader()
    deconstructor = ModelDeconstructor()
    loaded_models = []
    
    # ============================================================================
    # CREATE A WRAPPER CLASS to make gesture system compatible
    # ============================================================================
    
    class GestureSystemWrapper:
        def __init__(self, renderer, interaction, hands_detector, mp_draw, mp_hands, loaded_models):
            self.renderer = renderer
            self.interaction = interaction
            self.hands_detector = hands_detector
            self.mp_draw = mp_draw
            self.mp_hands = mp_hands
            self.loaded_models = loaded_models
            
        def process_frame(self, frame):
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands_detector.process(rgb_frame)
            
            detected_hands = []
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    hand = self.interaction.gesture_controller.recognize_hand_pose(
                        hand_landmarks, frame.shape
                    )
                    detected_hands.append(hand)
            
            self.interaction.update(detected_hands, self.loaded_models, time.time())
            
            for model in self.loaded_models:
                self.renderer.render_model(frame, model)
            
            self._draw_ui(frame, detected_hands)
            return frame
        
        def _draw_ui(self, frame, detected_hands):
            info_y = 35
            cv2.rectangle(frame, (5, info_y - 3), (255, info_y + 70), (0, 0, 0), -1)
            cv2.rectangle(frame, (5, info_y - 3), (255, info_y + 70), (100, 100, 100), 1)
            
            cv2.putText(frame, f"✋ Hands: {len(detected_hands)}", (10, info_y + 12), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            cv2.putText(frame, f"📦 Models: {len(self.loaded_models)}", (10, info_y + 28), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            if self.interaction.selected_model:
                model = self.interaction.selected_model
                cv2.putText(frame, f"✅ Selected: {model.name[:18]}", (10, info_y + 44), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
                cv2.putText(frame, f"   Scale: {model.scale:.2f}", (10, info_y + 58), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)
            
            perf_text = "ON" if self.renderer.performance_mode else "OFF"
            perf_color = (0, 255, 0) if self.renderer.performance_mode else (255, 165, 0)
            cv2.putText(frame, f"⚡ Perf Mode: {perf_text}", (10, info_y + 72), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, perf_color, 1)
            
            for hand in detected_hands:
                if hand.is_three_fingers and hand.pinch_point:
                    px, py = int(hand.pinch_point[0]), int(hand.pinch_point[1])
                    cv2.circle(frame, (px, py), 30, (0, 255, 255), 3)
                    cv2.circle(frame, (px, py), 10, (0, 255, 255), -1)
                    cv2.putText(frame, "DRAG", (px - 25, py - 35),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                elif hand.is_pinched and hand.pinch_point:
                    px, py = int(hand.pinch_point[0]), int(hand.pinch_point[1])
                    cv2.circle(frame, (px, py), 20, (0, 0, 255), 2)
                    cv2.circle(frame, (px, py), 6, (0, 0, 255), -1)
                    cv2.putText(frame, "PINCH", (px - 25, py - 25),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                elif hand.is_two_fingers:
                    cv2.circle(frame, (int(hand.index_tip[0]), int(hand.index_tip[1])), 15, (255, 165, 0), 2)
                    cv2.circle(frame, (int(hand.middle_tip[0]), int(hand.middle_tip[1])), 15, (255, 165, 0), 2)
                    cv2.line(frame, (int(hand.index_tip[0]), int(hand.index_tip[1])), 
                            (int(hand.middle_tip[0]), int(hand.middle_tip[1])), (255, 165, 0), 2)
                    cv2.putText(frame, "ROTATE", (int(hand.index_tip[0]) - 30, int(hand.index_tip[1]) - 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1)
        
        def handle_keyboard(self, key):
            if key == ord('o') or key == ord('O'):
                print("\n" + "=" * 50)
                filepath = input("📁 Enter path to 3D model (.obj, .glb): ").strip()
                filepath = filepath.strip('"').strip("'")
                
                if not os.path.exists(filepath):
                    print(f"❌ File not found: {filepath}")
                    return
                
                print("🔄 Loading model...")
                model = ModelLoader.load_model_auto(filepath)
                
                if model:
                    cols = 3
                    row = len(self.loaded_models) // cols
                    col = len(self.loaded_models) % cols
                    offset_x = (col - 1) * 2.5
                    offset_y = (row - 1) * 2.0
                    
                    model.position = (offset_x, offset_y, 0)
                    model.scale = 0.8
                    model.color = (
                        np.random.randint(50, 200),
                        np.random.randint(50, 200),
                        np.random.randint(50, 200)
                    )
                    self.loaded_models.append(model)
                    
                    print(f"\n✅ Successfully loaded: {model.name}")
                    print(f"   📊 {len(model.vertices):,} vertices, {len(model.faces):,} faces")
                else:
                    print(f"❌ Failed to load: {filepath}")
            
            elif key == ord('d') or key == ord('D'):
                if self.interaction.selected_model:
                    name = self.interaction.selected_model.name
                    self.loaded_models.remove(self.interaction.selected_model)
                    self.interaction.selected_model = None
                    self.interaction.drag_active = False
                    print(f"🗑️ Deleted: {name}")
                else:
                    print("⚠️ No model selected. Pinch a model first.")
            
            elif key == ord('x') or key == ord('X'):
                if self.loaded_models:
                    count = len(self.loaded_models)
                    self.loaded_models.clear()
                    self.interaction.selected_model = None
                    self.interaction.drag_active = False
                    print(f"🗑️ Deleted all {count} models")
                else:
                    print("⚠️ No models to delete")
            
            elif key == ord('r') or key == ord('R'):
                if self.interaction.selected_model:
                    self.interaction.selected_model.position = (0, 0, 0)
                    self.interaction.selected_model.rotation = (0, 0, 0)
                    self.interaction.selected_model.scale = 1.0
                    print(f"🔄 Reset: {self.interaction.selected_model.name}")
                else:
                    print("⚠️ No model selected")
            
            elif key == ord('p') or key == ord('P'):
                self.renderer.toggle_performance_mode()
            
            elif key == ord('1'):
                cube = ModelLoader.create_cube(size=1.5, position=(0, 0, 0))
                cube.color = (100, 150, 200)
                self.loaded_models.append(cube)
                print("Created cube")
            
            elif key == ord('2'):
                sphere = ModelLoader.create_sphere(radius=1.0, segments=20, position=(0, 0, 0))
                sphere.color = (150, 100, 200)
                self.loaded_models.append(sphere)
                print("Created sphere")
            
            elif key == ord('3'):
                cylinder = ModelLoader.create_cylinder(radius=0.8, height=1.5, segments=24, position=(0, 0, 0))
                cylinder.color = (100, 200, 150)
                self.loaded_models.append(cylinder)
                print("Created cylinder")
            
            elif key == ord('4'):
                cone = ModelLoader.create_cone(radius=0.8, height=1.5, segments=24, position=(0, 0, 0))
                cone.color = (200, 150, 100)
                self.loaded_models.append(cone)
                print("Created cone")
            
            elif key == ord('5'):
                pyramid = ModelLoader.create_pyramid(base_size=1.2, height=1.5, position=(0, 0, 0))
                pyramid.color = (200, 100, 150)
                self.loaded_models.append(pyramid)
                print("Created pyramid")
            
            elif key == ord('6'):
                torus = ModelLoader.create_torus(radius=1.2, tube_radius=0.3, position=(0, 0, 0))
                torus.color = (150, 200, 100)
                self.loaded_models.append(torus)
                print("Created torus")
            
            elif key == ord('7'):
                star = ModelLoader.create_star(outer_radius=1.2, inner_radius=0.5, points=5, position=(0, 0, 0))
                star.color = (255, 200, 100)
                self.loaded_models.append(star)
                print("Created star")
            
            elif key == ord('=') or key == ord('+'):
                if self.renderer.performance_mode:
                    current = self.renderer.max_faces_per_frame
                    new_max = min(current + 500, 10000)
                    self.renderer.max_faces_per_frame = new_max
                    print(f"Quality increased: {current} → {new_max} faces/frame")
            
            elif key == ord('-') or key == ord('_'):
                if self.renderer.performance_mode:
                    current = self.renderer.max_faces_per_frame
                    new_max = max(current - 500, 500)
                    self.renderer.max_faces_per_frame = new_max
                    print(f"Performance increased: {current} → {new_max} faces/frame")
                    
            elif key == ord('s') or key == ord('S'):
                self.interaction.gesture_controller.reset_rotation_smoothing()
                print("Rotation smoothing reset")
            
            elif key == ord('u') or key == ord('U'):
                if self.interaction.selected_model:
                    rot = self.interaction.selected_model.rotation
                    self.interaction.selected_model.rotation = (rot[0] + 0.1, rot[1], rot[2])
                    print(f"Manual rotate - New rotation: {self.interaction.selected_model.rotation}")
        
            elif key == ord('j') or key == ord('J'):
                if self.interaction.selected_model:
                    rot = self.interaction.selected_model.rotation
                    self.interaction.selected_model.rotation = (rot[0] - 0.1, rot[1], rot[2])
                    print(f"Manual rotate - New rotation: {self.interaction.selected_model.rotation}")
        
            elif key == ord('h') or key == ord('H'):
                if self.interaction.selected_model:
                    rot = self.interaction.selected_model.rotation
                    self.interaction.selected_model.rotation = (rot[0], rot[1] - 0.1, rot[2])
                    print(f"Manual rotate - New rotation: {self.interaction.selected_model.rotation}")
        
            elif key == ord('l') or key == ord('L'):
                if self.interaction.selected_model:
                    rot = self.interaction.selected_model.rotation
                    self.interaction.selected_model.rotation = (rot[0], rot[1] + 0.1, rot[2])
                    print(f"Manual rotate - New rotation: {self.interaction.selected_model.rotation}")
    
    # ============================================================================
    # CREATE THE GESTURE SYSTEM WRAPPER
    # ============================================================================
    
    gesture_system = GestureSystemWrapper(
        renderer, interaction, hands_detector, mp_draw, mp_hands, loaded_models
    )
    
    # ============================================================================
    # WRAP WITH INTRUSION DETECTION
    # ============================================================================
    
    intrusion_system = IntrusionAwareGestureSystem(gesture_system, cap)    
    
    # ============================================================================
    # PRINT CONTROLS
    # ============================================================================
    
    print("\n" + "=" * 60)
    print("3D MODEL GESTURE CONTROL WITH INTRUSION DETECTION")
    print("=" * 60)
    print("\nGESTURE CONTROLS:")
    print("   • Pinch (thumb + index)     → Select & Drag model")
    print("   • Two-finger (peace sign)   → Rotate model")
    print("   • Two-hand pinch            → Scale model")
    print("\nINTRUSION DETECTION:")
    print("   • I - Toggle intrusion monitoring ON/OFF")
    print("   • R - Register new admin face")
    print("   • S - Show intrusion status")
    print("\nKEYBOARD CONTROLS:")
    print("   • O - Load 3D model (.obj, .glb)")
    print("   • D - Delete selected model")
    print("   • X - Delete ALL models")
    print("   • R - Reset selected model")
    print("   • P - Toggle performance mode")
    print("   • 1-7 - Create primitive shapes")
    print("   • Q - Quit application")
    print("\nTIP: Register your face first (press R) to become admin!")
    print("=" * 60 + "\n")
    
    # ============================================================================
    # MAIN LOOP
    # ============================================================================
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to grab frame")
            break
        
        frame = cv2.flip(frame, 1)
        
        # Process UI interactions
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands_detector.process(rgb_frame)
        
        pinch_point = None
        two_finger_points = None
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                index_tip = hand_landmarks.landmark[8]
                middle_tip = hand_landmarks.landmark[12]
                h, w = frame.shape[:2]
                index_x, index_y = int(index_tip.x * w), int(index_tip.y * h)
                middle_x, middle_y = int(middle_tip.x * w), int(middle_tip.y * h)
        
                distance = math.hypot(index_x - middle_x, index_y - middle_y)
                if distance < 40:
                    two_finger_points = ((index_x, index_y), (middle_x, middle_y))
                    break

        ui_controller.update(pinch_point, two_finger_points)
        
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                thumb_tip = hand_landmarks.landmark[4]
                index_tip = hand_landmarks.landmark[8]
                h, w = frame.shape[:2]
                thumb_x, thumb_y = int(thumb_tip.x * w), int(thumb_tip.y * h)
                index_x, index_y = int(index_tip.x * w), int(index_tip.y * h)
                distance = math.hypot(thumb_x - index_x, thumb_y - index_y)
                if distance < 35:
                    pinch_point = ((thumb_x + index_x) / 2, (thumb_y + index_y) / 2)
                    break
        
        ui_controller.update(pinch_point)
        
        if pinch_point:
            ui_controller.handle_pinch(pinch_point)
        
        processed_frame = intrusion_system.process_frame(frame)
        processed_frame = ui_controller.draw(processed_frame)
        
        cv2.imshow('3D Gesture Control + Intrusion Detection', processed_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q') or key == ord('Q'):
            print("\n👋 Shutting down...")
            break
        
        intrusion_system.handle_keyboard(key)
    
    cap.release()
    cv2.destroyAllWindows()
    print("Application closed")

if __name__ == "__main__":
    main()