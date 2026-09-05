# ui_controller.py - Holographic Shelf System with Gesture Scrolling
"""
Iron Man-style Holographic UI with shelf-based navigation
Features:
- Left-side stacked shelf panels
- Expand/collapse with pinch
- Gesture scrolling through files (two-finger drag)
- Holographic glass effect
- Proper hand layering
"""

import cv2
import numpy as np
import os
import math
import time
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum

@dataclass
class ShelfItem:
    """Item in a shelf panel"""
    id: str
    name: str
    icon: str  # Now using text icons instead of emojis
    type: str  # 'file', 'folder', 'shape', 'action'
    data: any = None
    color: Tuple[int, int, int] = (100, 150, 200)

class ShelfPanel:
    """Individual shelf panel on the left side"""
    
    def __init__(self, id: str, title: str, icon: str, y_position: int, x: int = 10):
        self.id = id
        self.title = title
        self.icon = icon
        self.x = x
        self.y = y_position
        self.width = 60
        self.height = 60
        self.is_expanded = False
        self.expand_progress = 0.0
        self.items: List[ShelfItem] = []
        self.scroll_offset = 0
        self.target_scroll = 0
        self.item_height = 55  # Increased for easier pinching
        self.visible_items = 0
        self.hovered_item = -1
        
    def update_animation(self):
        """Smooth expand/collapse animation"""
        target = 1.0 if self.is_expanded else 0.0
        diff = target - self.expand_progress
        if abs(diff) < 0.02:
            self.expand_progress = target
        else:
            self.expand_progress += diff * 0.2
        
        # Smooth scroll
        scroll_diff = self.target_scroll - self.scroll_offset
        if abs(scroll_diff) < 0.5:
            self.scroll_offset = self.target_scroll
        else:
            self.scroll_offset += scroll_diff * 0.15
    
    def get_expanded_width(self) -> int:
        """Get width when expanded"""
        return 300 if self.expand_progress > 0 else self.width
    
    def get_content_y(self) -> int:
        """Get content area Y position"""
        return self.y + self.height + 5
    
    def get_content_height(self) -> int:
        """Get content area height based on expansion"""
        if self.expand_progress <= 0:
            return 0
        return int(350 * self.expand_progress)
    
    def scroll(self, delta: int):
        """Scroll through items"""
        max_scroll = max(0, len(self.items) * self.item_height - self.get_content_height())
        # Scroll faster for better response
        self.target_scroll = max(0, min(max_scroll, self.target_scroll + delta * 40))
    
    def draw(self, frame: np.ndarray, is_hovered: bool = False) -> np.ndarray:
        """Draw the shelf panel with holographic effect"""
        h, w = frame.shape[:2]
        
        # Calculate positions
        panel_x = self.x
        panel_y = self.y
        panel_w = self.get_expanded_width()
        
        # Draw collapsed shelf button
        if self.expand_progress < 0.95:
            # Holographic glass effect for collapsed button
            overlay = frame.copy()
            cv2.rectangle(overlay, 
                         (panel_x, panel_y), 
                         (panel_x + self.width, panel_y + self.height), 
                         (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            
            # Border with glow effect
            border_color = (0, 200, 255) if is_hovered else (60, 80, 100)
            cv2.rectangle(frame, 
                         (panel_x, panel_y), 
                         (panel_x + self.width, panel_y + self.height), 
                         border_color, 2)
            
            # Icon (text-based, no emojis)
            cv2.putText(frame, self.icon, 
                       (panel_x + 18, panel_y + 42),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                       (0, 200, 255) if is_hovered else (150, 180, 220), 2)
        
        # Draw expanded content
        if self.expand_progress > 0.05:
            content_x = panel_x + self.width
            content_w = panel_w - self.width
            content_y = self.get_content_y()
            content_h = self.get_content_height()
            
            if content_h > 0:
                # Semi-transparent background (black)
                overlay = frame.copy()
                cv2.rectangle(overlay, 
                             (content_x, content_y), 
                             (content_x + content_w, content_y + content_h), 
                             (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
                
                # Border with cyan glow
                cv2.rectangle(frame, 
                             (content_x, content_y), 
                             (content_x + content_w, content_y + content_h), 
                             (0, 180, 220), 1)
                
                # Title header
                header_color = (30, 30, 50)
                cv2.rectangle(frame, 
                             (content_x, content_y), 
                             (content_x + content_w, content_y + 40), 
                             header_color, -1)
                cv2.putText(frame, f"{self.icon} {self.title}", 
                           (content_x + 10, content_y + 28),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
                
                # Draw items with clipping
                start_idx = max(0, int(self.scroll_offset / self.item_height))
                end_idx = min(len(self.items), start_idx + int(content_h / self.item_height) + 1)
                
                for i in range(start_idx, end_idx):
                    item = self.items[i]
                    item_y = content_y + 45 + (i * self.item_height) - self.scroll_offset
                    
                    if item_y + self.item_height > content_y + content_h:
                        continue
                    if item_y < content_y:
                        continue
                    
                    # Item background (highlight on hover)
                    if i == self.hovered_item:
                        cv2.rectangle(frame, 
                                     (content_x + 5, int(item_y)), 
                                     (content_x + content_w - 5, int(item_y + self.item_height - 5)), 
                                     (50, 70, 90), -1)
                    
                    # Item icon (text-based)
                    cv2.putText(frame, item.icon, 
                               (content_x + 15, int(item_y + 35)),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 255), 1)
                    
                    # Item name (truncated)
                    name = item.name[:28] + ".." if len(item.name) > 30 else item.name
                    cv2.putText(frame, name, 
                               (content_x + 50, int(item_y + 35)),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 240), 1)
                    
                    # Separator line
                    cv2.line(frame, 
                            (content_x + 10, int(item_y + self.item_height - 5)), 
                            (content_x + content_w - 10, int(item_y + self.item_height - 5)), 
                            (40, 50, 70), 1)
                
                # Scroll indicator
                total_height = len(self.items) * self.item_height
                if total_height > content_h:
                    bar_height = max(25, int(content_h * (content_h / total_height)))
                    bar_y = content_y + (self.scroll_offset / total_height) * content_h
                    cv2.rectangle(frame, 
                                 (content_x + content_w - 8, content_y + 5), 
                                 (content_x + content_w - 3, content_y + content_h - 5), 
                                 (30, 40, 60), -1)
                    cv2.rectangle(frame, 
                                 (content_x + content_w - 8, int(bar_y)), 
                                 (content_x + content_w - 3, int(bar_y + bar_height)), 
                                 (0, 180, 220), -1)
        
        return frame
    
    def get_item_at(self, x: float, y: float) -> Tuple[int, ShelfItem]:
        """Get item at screen position"""
        if not self.is_expanded or self.expand_progress < 0.5:
            return -1, None
        
        content_x = self.x + self.width
        content_w = self.get_expanded_width() - self.width
        content_y = self.get_content_y()
        content_h = self.get_content_height()
        
        if not (content_x <= x <= content_x + content_w and content_y <= y <= content_y + content_h):
            return -1, None
        
        # Calculate which item
        relative_y = y - content_y - 45 + self.scroll_offset
        idx = int(relative_y / self.item_height)
        
        if 0 <= idx < len(self.items):
            return idx, self.items[idx]
        
        return -1, None
    
    def is_collapsed_button_hit(self, x: float, y: float) -> bool:
        """Check if collapsed button was hit"""
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + self.height)

class HolographicUI:
    """Main UI Controller with shelf-based navigation"""
    
    def __init__(self, screen_width: int = 640, screen_height: int = 480):
        self.width = screen_width
        self.height = screen_height
        
        # Shelf panels (stacked on left)
        self.panels: List[ShelfPanel] = []
        self.active_panel = None
        self.hovered_panel = None
        self.hovered_item = None
        
        # Scroll gesture tracking
        self.scroll_gesture_active = False
        self.last_scroll_y = 0
        
        # File browser state
        self.current_directory = os.getcwd()
        self.directory_history = []
        
        # Callbacks
        self.on_file_select = None
        self.on_shape_select = None
        self.on_intrusion_toggle = None
        
        # Intrusion mode
        self.intrusion_mode = False
        
        self._init_panels()
        self.refresh_file_browser()
    
    def _init_panels(self):
        """Initialize shelf panels (stacked vertically)"""
        start_y = 100
        panel_spacing = 70
        
        # Files Panel
        self.files_panel = ShelfPanel("files", "FILES", "[F]", start_y)
        self.panels.append(self.files_panel)
        
        # Shapes Panel
        self.shapes_panel = ShelfPanel("shapes", "SHAPES", "[S]", start_y + panel_spacing)
        self._populate_shapes()
        self.panels.append(self.shapes_panel)
        
        # Security Panel
        self.security_panel = ShelfPanel("security", "SECURITY", "[!]", start_y + panel_spacing * 2)
        self._populate_security()
        self.panels.append(self.security_panel)
        
        # Settings Panel
        self.settings_panel = ShelfPanel("settings", "SETTINGS", "[=]", start_y + panel_spacing * 3)
        self._populate_settings()
        self.panels.append(self.settings_panel)
    
    def _populate_shapes(self):
        """Populate shapes panel"""
        shapes = [
            ShelfItem("cube", "Cube", "[#]", "shape", "cube"),
            ShelfItem("sphere", "Sphere", "( )", "shape", "sphere"),
            ShelfItem("cylinder", "Cylinder", "||", "shape", "cylinder"),
            ShelfItem("cone", "Cone", "/\\", "shape", "cone"),
            ShelfItem("pyramid", "Pyramid", "/^\\", "shape", "pyramid"),
            ShelfItem("torus", "Torus", "O", "shape", "torus"),
            ShelfItem("star", "Star", "*", "shape", "star"),
        ]
        self.shapes_panel.items = shapes
    
    def _populate_security(self):
        """Populate security panel"""
        items = [
            ShelfItem("id_toggle", "ID Mode", "[S]", "toggle", "intrusion"),
        ]
        self.security_panel.items = items
    
    def _populate_settings(self):
        """Populate settings panel"""
        items = [
            ShelfItem("reset_ui", "Reset UI", "[R]", "action", "reset"),
            ShelfItem("help", "Help", "[?]", "action", "help"),
        ]
        self.settings_panel.items = items
    
    def refresh_file_browser(self):
        """Refresh file browser with current directory - ONLY GLB and OBJ files"""
        items = []
        
        # Parent directory (if not at root)
        if self.current_directory != "/" and self.current_directory != "C:\\":
            items.append(ShelfItem("parent", "..", "[..]", "folder", "parent"))
        
        try:
            # Get directories and model files
            dirs = []
            files = []
            for item in os.listdir(self.current_directory):
                item_path = os.path.join(self.current_directory, item)
                if os.path.isdir(item_path):
                    dirs.append(item)
                elif item.lower().endswith(('.glb', '.obj')):
                    files.append(item)
            
            # Add directories first
            for dir_name in sorted(dirs)[:20]:
                items.append(ShelfItem(f"dir_{dir_name}", dir_name, "[D]", "folder", dir_name))
            
            # Add GLB/OBJ files
            for file_name in sorted(files)[:30]:
                ext = os.path.splitext(file_name)[1].upper().replace('.', '')
                icon = "[G]" if ext == "GLB" else "[O]"
                items.append(ShelfItem(f"file_{file_name}", file_name, icon, "file", file_name))
                
        except Exception as e:
            print(f"Error reading directory: {e}")
        
        self.files_panel.items = items
        
        # Reset scroll when refreshing
        self.files_panel.scroll_offset = 0
        self.files_panel.target_scroll = 0
    
    def navigate_to(self, path: str):
        """Navigate to directory"""
        if path == "parent":
            self.current_directory = os.path.dirname(self.current_directory)
        else:
            new_path = os.path.join(self.current_directory, path)
            if os.path.isdir(new_path):
                self.current_directory = new_path
        self.refresh_file_browser()
        print(f"📁 Current directory: {self.current_directory}")
    
    def update(self, pinch_point: Optional[Tuple[float, float]] = None, 
               two_finger_points: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None):
        """Update UI state"""
        self.hovered_panel = None
        self.hovered_item = None
        
        # Reset hover states
        for panel in self.panels:
            panel.hovered_item = -1
        
        # Update animations
        for panel in self.panels:
            panel.update_animation()
        
        # Check hover
        if pinch_point:
            x, y = pinch_point
            for panel in self.panels:
                # Check expanded content first
                idx, item = panel.get_item_at(x, y)
                if idx >= 0:
                    self.hovered_panel = panel
                    self.hovered_item = idx
                    panel.hovered_item = idx
                    break
                
                # Check collapsed button
                if panel.is_collapsed_button_hit(x, y):
                    self.hovered_panel = panel
                    break
        
        # Handle two-finger scroll
        if two_finger_points:
            p1, p2 = two_finger_points
            center_y = (p1[1] + p2[1]) / 2
            
            if not self.scroll_gesture_active:
                self.scroll_gesture_active = True
                self.last_scroll_y = center_y
            else:
                delta_y = self.last_scroll_y - center_y
                if abs(delta_y) > 8 and self.hovered_panel and self.hovered_panel.is_expanded:
                    self.hovered_panel.scroll(int(delta_y / 2))
                self.last_scroll_y = center_y
        else:
            self.scroll_gesture_active = False
    
    def handle_pinch(self, pinch_point: Tuple[float, float]) -> bool:
        """Handle pinch gesture on UI"""
        x, y = pinch_point
        
        # Check all panels
        for panel in self.panels:
            # Check expanded content
            idx, item = panel.get_item_at(x, y)
            if idx >= 0:
                return self._handle_item_click(panel, idx, item)
            
            # Check collapsed button
            if panel.is_collapsed_button_hit(x, y):
                # Toggle expansion
                panel.is_expanded = not panel.is_expanded
                if panel.is_expanded:
                    # Close other panels
                    for p in self.panels:
                        if p != panel and p.is_expanded:
                            p.is_expanded = False
                    print(f"📂 Opened: {panel.title}")
                else:
                    print(f"📁 Closed: {panel.title}")
                return True
        
        return False
    
    def _handle_item_click(self, panel: ShelfPanel, idx: int, item: ShelfItem) -> bool:
        """Handle item click based on type"""
        if panel.id == "files":
            if item.type == "folder":
                self.navigate_to(item.data)
                return True
            elif item.type == "file":
                file_path = os.path.join(self.current_directory, item.data)
                print(f"📄 Selected file: {item.data}")
                if self.on_file_select:
                    self.on_file_select(file_path)
                # Auto-close after selection
                panel.is_expanded = False
                return True
        
        elif panel.id == "shapes":
            print(f"🔷 Creating shape: {item.data}")
            if self.on_shape_select:
                self.on_shape_select(item.data)
            panel.is_expanded = False
            return True
        
        elif panel.id == "security":
            if item.type == "toggle":
                self.intrusion_mode = not self.intrusion_mode
                if self.on_intrusion_toggle:
                    self.on_intrusion_toggle(self.intrusion_mode)
                # Update icon
                if self.intrusion_mode:
                    item.icon = "[!]"
                    item.name = "ID ACTIVE"
                else:
                    item.icon = "[S]"
                    item.name = "ID Mode"
                print(f"🛡️ Intrusion mode: {'ON' if self.intrusion_mode else 'OFF'}")
                return True
        
        elif panel.id == "settings":
            if item.data == "reset":
                for p in self.panels:
                    p.is_expanded = False
                    p.scroll_offset = 0
                    p.target_scroll = 0
                print("🔄 UI reset to default")
            elif item.data == "help":
                print("\n" + "=" * 50)
                print("HELP - Gesture Controls")
                print("=" * 50)
                print("• Pinch on a shelf icon → Expand panel")
                print("• Pinch on an item → Select it")
                print("• Two-finger scroll (peace sign) → Scroll through lists")
                print("• Pinch on expanded header → Collapse panel")
                print("=" * 50)
            return True
        
        return False
    
    def draw(self, frame: np.ndarray, hands: List = None) -> np.ndarray:
        """Draw all UI elements with proper layering"""
        # Draw panels (they handle their own transparency)
        for panel in self.panels:
            is_hovered = (self.hovered_panel == panel)
            frame = panel.draw(frame, is_hovered)
        
        # Draw intrusion indicator (bottom right)
        if self.intrusion_mode:
            # Glowing red dot
            cv2.circle(frame, (self.width - 20, self.height - 20), 10, (0, 0, 100), -1)
            cv2.circle(frame, (self.width - 20, self.height - 20), 10, (0, 0, 255), 2)
            cv2.putText(frame, "SECURE", (self.width - 75, self.height - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        
        # Draw current directory path if files panel expanded
        if self.files_panel.is_expanded and self.files_panel.expand_progress > 0.5:
            # Truncate long paths
            path = self.current_directory
            if len(path) > 45:
                path = "..." + path[-42:]
            cv2.putText(frame, path, (self.files_panel.x + 75, self.files_panel.y + 100),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 180, 220), 1)
        
        return frame
    
    def set_mouse_scale(self, delta: float):
        """Scale UI with mouse wheel"""
        # Future implementation
        pass
    
    def get_ui_transform(self):
        """Get UI transformation"""
        return 1.0, 0, 0