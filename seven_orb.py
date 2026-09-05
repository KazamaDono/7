"""
seven_orb.py - Reactive GIF display for Seven AI
Reacts to voice by controlling playback speed and frame position.
"""

import pygame
import time
import json
import os
import sys
import math
from pathlib import Path
from PIL import Image, ImageSequence

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    IDLE_GIF = "bs.gif"
    ACTIVE_GIF = "ws.gif"
    STATE_FILE = "seven_state.json"
    DEFAULT_WIDTH = 800
    DEFAULT_HEIGHT = 800
    FPS = 60

# ============================================================================
# REACTIVE GIF PLAYER
# ============================================================================

class ReactiveGIFPlayer:
    """GIF player that reacts to audio by controlling playback"""
    
    def __init__(self, gif_path: str):
        self.path = gif_path
        self.frames = []
        self.durations = []
        self.current_frame = 0
        self.last_update = 0
        self.is_loaded = False
        self.width = 0
        self.height = 0
        
        # Reactive properties
        self.base_speed = 1.0
        self.speed_multiplier = 1.0
        self.pulse_intensity = 0.0
        self.shake_intensity = 0.0
        
    def load(self) -> bool:
        """Load GIF and extract frames"""
        try:
            if not os.path.exists(self.path):
                print(f"[!] GIF not found: {self.path}")
                return False
            
            gif = Image.open(self.path)
            
            for frame in ImageSequence.Iterator(gif):
                frame_rgba = frame.convert("RGBA")
                
                if self.width == 0:
                    self.width = frame_rgba.width
                    self.height = frame_rgba.height
                
                mode = frame_rgba.mode
                size = frame_rgba.size
                data = frame_rgba.tobytes()
                
                pygame_image = pygame.image.fromstring(data, size, mode)
                self.frames.append(pygame_image)
                
                duration = frame.info.get('duration', 100)
                self.durations.append(duration)
            
            self.is_loaded = True
            print(f"[✓] Loaded {len(self.frames)} frames from {self.path}")
            return True
            
        except Exception as e:
            print(f"[!] Error loading GIF {self.path}: {e}")
            return False
    
    def set_audio_level(self, level: float):
        """React to audio level (0.0 to 1.0)"""
        # Map audio level to speed (1.0 to 3.0)
        self.speed_multiplier = 1.0 + level * 1.5
        
        # Map audio level to pulse intensity
        self.pulse_intensity = level * 0.3
        
        # Map audio to shake (subtle)
        self.shake_intensity = level * 2
    
    def set_state(self, state: str):
        """Adjust base speed based on state"""
        if state == "speaking":
            self.base_speed = 1.2
        elif state == "listening":
            self.base_speed = 1.1
        elif state == "processing":
            self.base_speed = 1.3
        else:
            self.base_speed = 1.0
    
    def get_current_frame(self) -> pygame.Surface:
        """Get current frame with reactive timing"""
        if not self.is_loaded or not self.frames:
            return None
        
        current_time = time.time() * 1000
        
        # Calculate dynamic frame duration
        base_duration = self.durations[self.current_frame]
        
        # Speed affects duration (faster speed = shorter duration)
        total_speed = self.base_speed * self.speed_multiplier
        dynamic_duration = base_duration / total_speed
        
        if current_time - self.last_update >= dynamic_duration:
            # Jump frames based on audio intensity (skip frames when loud)
            jump = 1
            if self.pulse_intensity > 0.7:
                jump = 2  # Skip frames for more energetic feel
            elif self.pulse_intensity > 0.4:
                jump = 1
            
            self.current_frame = (self.current_frame + jump) % len(self.frames)
            self.last_update = current_time
        
        return self.frames[self.current_frame]
    
    def get_frame_count(self) -> int:
        return len(self.frames)
    
    def get_current_frame_index(self) -> int:
        return self.current_frame
    
    def get_size(self) -> tuple:
        return (self.width, self.height)
    
    def get_shake_offset(self) -> tuple:
        """Get screen shake offset based on audio"""
        if self.shake_intensity > 0.1:
            import random
            random.seed(time.time())
            x = random.randint(-int(self.shake_intensity), int(self.shake_intensity))
            y = random.randint(-int(self.shake_intensity), int(self.shake_intensity))
            return (x, y)
        return (0, 0)
    
    def get_pulse_scale(self) -> float:
        """Get scale factor for pulsing effect"""
        return 1.0 + self.pulse_intensity * 0.05

# ============================================================================
# ORB WINDOW
# ============================================================================

class OrbWindow:
    """Window that displays reactive GIF"""
    
    def __init__(self):
        import signal
        def ignore_sigquit(signum, frame):
            pass  # Do nothing - orb stays alive
    
        signal.signal(signal.SIGQUIT, ignore_sigquit)
        
        pygame.init()
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
        pygame.display.set_caption("SEVEN")
        self.config = Config()
        
        # Load GIFs
        print("[*] Loading GIFs...")
        self.idle_gif = ReactiveGIFPlayer(self.config.IDLE_GIF)
        self.active_gif = ReactiveGIFPlayer(self.config.ACTIVE_GIF)
        
        self.idle_loaded = self.idle_gif.load()
        self.active_loaded = self.active_gif.load()
        
        if not self.idle_loaded and not self.active_loaded:
            print("[!] No GIFs loaded. Exiting.")
            sys.exit(1)
        
        # Determine window size
        if self.idle_loaded:
            self.width, self.height = self.idle_gif.get_size()
        elif self.active_loaded:
            self.width, self.height = self.active_gif.get_size()
        else:
            self.width = self.config.DEFAULT_WIDTH
            self.height = self.config.DEFAULT_HEIGHT
        
        # Create window
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
        pygame.display.set_caption("SEVEN")
        
        self.clock = pygame.time.Clock()
        self.running = True
        
        # State
        self.current_state = "idle"
        self.audio_level = 0.0
        self.state_file = Path(self.config.STATE_FILE)
        
        # Smooth audio transitions
        self.smooth_audio = 0.0
        
        print(f"[*] Window created: {self.width}x{self.height}")
        print(f"[*] State file: {self.state_file.absolute()}")
        print("[*] Running...")
    
    def _read_state_file(self):
        """Read state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    if "state" in data:
                        self.current_state = data["state"]
                    if "audio_level" in data:
                        self.audio_level = data["audio_level"]
        except Exception:
            pass
    
    def update(self):
        """Handle events and update state"""
        self._read_state_file()
        
        # Smooth audio transitions
        self.smooth_audio += (self.audio_level - self.smooth_audio) * 0.3
        
        # Update GIF players with reactive properties
        self.idle_gif.set_state(self.current_state)
        self.idle_gif.set_audio_level(self.smooth_audio)
        
        self.active_gif.set_state(self.current_state)
        self.active_gif.set_audio_level(self.smooth_audio)
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()
            elif event.type == pygame.VIDEORESIZE:
                self.width = event.w
                self.height = event.h
                self.screen = pygame.display.set_mode((self.width, self.height), pygame.RESIZABLE)
    
    def draw(self):
        """Draw current GIF frame with effects"""
        self.screen.fill((0, 0, 0))
        
        # Choose GIF based on state
        if self.current_state in ["speaking", "listening", "processing"] and self.active_loaded:
            player = self.active_gif
        elif self.idle_loaded:
            player = self.idle_gif
        else:
            return
        
        frame = player.get_current_frame()
        
        if frame:
            # Apply pulse scale
            scale = player.get_pulse_scale()
            scaled_width = int(self.width * scale)
            scaled_height = int(self.height * scale)
            
            # Apply shake
            shake_x, shake_y = player.get_shake_offset()
            
            # Center the scaled image
            x = (self.width - scaled_width) // 2 + shake_x
            y = (self.height - scaled_height) // 2 + shake_y
            
            # Scale and draw
            scaled = pygame.transform.scale(frame, (scaled_width, scaled_height))
            self.screen.blit(scaled, (x, y))
        
        pygame.display.flip()
    
    def run(self):
        """Main loop"""
        # Force set the window title again
        pygame.display.set_caption("SEVEN")
    
        print("\n" + "="*60)
        print("SEVEN ORB // REACTIVE GIF DISPLAY")
        print("="*60)
        print("Controls:")
        print("  F - Toggle Fullscreen")
        print("  ESC - Exit")
        print("="*60 + "\n")
    
        while self.running:
            self.update()
            self.draw()
            self.clock.tick(self.config.FPS)
    
        pygame.quit()


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*60)
    print("SEVEN ORB // REACTIVE GIF DISPLAY")
    print("="*60)
    print("Controls:")
    print("  F - Toggle Fullscreen")
    print("  ESC - Exit")
    print("="*60 + "\n")
    
    orb = OrbWindow()
    orb.run()


if __name__ == "__main__":
    main()