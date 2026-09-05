# model_manager.py - Working GLB loader

import numpy as np
from typing import List, Tuple, Optional
import os
import struct
from dataclasses import dataclass

try:
    from pygltflib import GLTF2
    PYGLTF_AVAILABLE = True
except ImportError:
    PYGLTF_AVAILABLE = False
    print("⚠️ pygltflib not installed. Install with: pip install pygltflib")

@dataclass
class Vertex3D:
    x: float
    y: float
    z: float

@dataclass
class Face3D:
    vertices: List[int]
    normal: Optional[Tuple[float, float, float]] = None

class Model3D:
    def __init__(self, name: str = "model"):
        self.name = name
        self.vertices: List[Vertex3D] = []
        self.faces: List[Face3D] = []
        self.position = (0.0, 0.0, 0.0)
        self.rotation = (0.0, 0.0, 0.0)
        self.scale = 1.0
        self.is_selected = False
        self.color = (100, 150, 200)
        self.selected_color = (0, 255, 0)
        self.original_vertex_count = 0
        
    def add_vertex(self, x: float, y: float, z: float) -> int:
        self.vertices.append(Vertex3D(x, y, z))
        return len(self.vertices) - 1
    
    def add_face(self, vertex_indices: List[int], normal: Optional[Tuple[float, float, float]] = None):
        self.faces.append(Face3D(vertex_indices, normal))
    
    def get_center(self) -> Tuple[float, float, float]:
        if not self.vertices:
            return (0, 0, 0)
        x_coords = [v.x for v in self.vertices]
        y_coords = [v.y for v in self.vertices]
        z_coords = [v.z for v in self.vertices]
        center_x = (min(x_coords) + max(x_coords)) / 2
        center_y = (min(y_coords) + max(y_coords)) / 2
        center_z = (min(z_coords) + max(z_coords)) / 2
        return (center_x, center_y, center_z)
    
    def get_bounding_box(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        if not self.vertices:
            return ((0, 0, 0), (0, 0, 0))
        min_x = min(v.x for v in self.vertices)
        max_x = max(v.x for v in self.vertices)
        min_y = min(v.y for v in self.vertices)
        max_y = max(v.y for v in self.vertices)
        min_z = min(v.z for v in self.vertices)
        max_z = max(v.z for v in self.vertices)
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))
    
    def normalize(self, target_size: float = 2.0):
        if not self.vertices:
            return
        bbox_min, bbox_max = self.get_bounding_box()
        bbox_size = [
            bbox_max[0] - bbox_min[0],
            bbox_max[1] - bbox_min[1],
            bbox_max[2] - bbox_min[2]
        ]
        max_dim = max(bbox_size)
        if max_dim > 0:
            scale_factor = target_size / max_dim
            for vertex in self.vertices:
                vertex.x *= scale_factor
                vertex.y *= scale_factor
                vertex.z *= scale_factor
            center = self.get_center()
            for vertex in self.vertices:
                vertex.x -= center[0]
                vertex.y -= center[1]
                vertex.z -= center[2]
    
    def simplify(self, target_faces: int = 5000):
        """Simplify model by reducing number of faces"""
        if len(self.faces) <= target_faces:
            return
        
        print(f"  Simplifying: {len(self.faces)} faces -> {target_faces} faces")
        
        # Simple decimation: keep every Nth face
        step = len(self.faces) // target_faces
        self.faces = self.faces[::step][:target_faces]
        
        print(f"  Simplified to: {len(self.vertices)} vertices, {len(self.faces)} faces")

class ModelLoader:
    @staticmethod
    def load_obj(filepath: str, simplify: bool = True) -> Optional[Model3D]:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return None
        
        model = Model3D(os.path.basename(filepath))
        try:
            vertices = []
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('v '):
                        parts = line.split()
                        if len(parts) >= 4:
                            x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                            vertices.append((x, y, z))
                    elif line.startswith('f '):
                        parts = line.split()
                        if len(parts) >= 4:
                            vertex_indices = []
                            for part in parts[1:]:
                                vertex_idx = int(part.split('/')[0]) - 1
                                vertex_indices.append(vertex_idx)
                            for idx in vertex_indices:
                                if idx >= len(model.vertices):
                                    v = vertices[idx]
                                    model.add_vertex(v[0], v[1], v[2])
                            model.add_face(vertex_indices)
            
            model.original_vertex_count = len(model.vertices)
            
            if simplify and len(model.faces) > 5000:
                model.simplify(target_faces=5000)
            
            model.normalize()
            print(f"✅ Loaded OBJ: {len(model.vertices)} vertices, {len(model.faces)} faces")
            return model
        except Exception as e:
            print(f"❌ Error loading OBJ: {e}")
            return None
    
    @staticmethod
    def load_glb(filepath: str, simplify: bool = True, target_faces: int = 5000) -> Optional[Model3D]:
        """Load GLB using pygltflib - COMPLETELY REWRITTEN"""
        if not PYGLTF_AVAILABLE:
            print("❌ pygltflib not installed. Install with: pip install pygltflib")
            return None
    
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return None

        try:
            # Load the GLB file
            glb = GLTF2().load(filepath)
            model = Model3D(os.path.basename(filepath))
        
            total_vertices = 0
            total_faces = 0
        
            # Process all meshes
            for mesh_idx, mesh in enumerate(glb.meshes):
                mesh_name = mesh.name if mesh.name else f"Mesh_{mesh_idx}"
                print(f"  Processing: {mesh_name}")
            
                for primitive in mesh.primitives:
                    # Get vertex positions
                    if primitive.attributes.POSITION is not None:
                        accessor_idx = primitive.attributes.POSITION
                        accessor = glb.accessors[accessor_idx]
                    
                        # Get buffer view
                        if accessor.bufferView is None:
                            print(f"    Skipping accessor without bufferView")
                            continue
                    
                        # Get the data using pygltflib's built-in method
                        try:
                            # Try to get data using pygltflib's method
                            vertices_array = glb.get_data_from_accessor(accessor_idx)
                        
                            if vertices_array is not None:
                                # Reshape and add vertices
                                for i in range(0, len(vertices_array), 3):
                                    x = float(vertices_array[i])
                                    y = float(vertices_array[i+1])
                                    z = float(vertices_array[i+2])
                                    model.add_vertex(x, y, z)
                                    total_vertices += 1
                                print(f"    Loaded {total_vertices} vertices")
                        except:
                            # Fallback: manual reading
                            buffer_view = glb.bufferViews[accessor.bufferView]
                        
                            # Get the buffer data
                            if hasattr(glb, 'binary_blob') and glb.binary_blob:
                                binary_data = glb.binary_blob
                            else:
                                # Read binary data from file
                                with open(filepath, 'rb') as f:
                                    # Find binary chunk
                                    f.seek(12)  # Skip magic and version
                                    f.read(4)  # Skip file size
                                    f.seek(20)  # Skip to after JSON chunk header
                                    json_length = struct.unpack('<I', f.read(4))[0]
                                    f.seek(20 + json_length)  # Skip JSON chunk
                                    binary_data = f.read()
                        
                            # Calculate offset
                            byte_offset = (buffer_view.byteOffset or 0) + (accessor.byteOffset or 0)
                            count = accessor.count
                        
                            # Each vertex is 3 floats (x, y, z)
                            for i in range(count):
                                offset = byte_offset + i * 12
                                if offset + 12 <= len(binary_data):
                                    x, y, z = struct.unpack('<fff', binary_data[offset:offset+12])
                                    model.add_vertex(float(x), float(y), float(z))
                                    total_vertices += 1
                            print(f"    Loaded {total_vertices} vertices (manual)")
                
                    # Get indices (faces)
                    if primitive.indices is not None:
                        accessor_idx = primitive.indices
                        accessor = glb.accessors[accessor_idx]
                    
                        if accessor.bufferView is None:
                            print(f"    Skipping indices without bufferView")
                            continue
                    
                        try:
                            # Try to get data using pygltflib's method
                            indices_array = glb.get_data_from_accessor(accessor_idx)
                        
                            if indices_array is not None:
                                # Convert to faces (triangles)
                                for i in range(0, len(indices_array), 3):
                                    if i + 2 < len(indices_array):
                                        i1 = int(indices_array[i])
                                        i2 = int(indices_array[i+1])
                                        i3 = int(indices_array[i+2])
                                        model.add_face([i1, i2, i3])
                                        total_faces += 1
                                print(f"    Loaded {total_faces} faces")
                        except:
                            # Fallback: manual reading
                            if not hasattr(glb, 'binary_blob') or not glb.binary_blob:
                                # Need binary data
                                with open(filepath, 'rb') as f:
                                    f.seek(12)
                                    f.read(4)
                                    f.seek(20)
                                    json_length = struct.unpack('<I', f.read(4))[0]
                                    f.seek(20 + json_length)
                                    binary_data = f.read()
                            else:
                                binary_data = glb.binary_blob
                        
                            buffer_view = glb.bufferViews[accessor.bufferView]
                            byte_offset = (buffer_view.byteOffset or 0) + (accessor.byteOffset or 0)
                            count = accessor.count
                        
                            # Check index type
                            if accessor.componentType == 5123:  # UNSIGNED_SHORT (2 bytes)
                                for i in range(0, count, 3):
                                    if i + 2 < count:
                                        offset = byte_offset + i * 2
                                        if offset + 6 <= len(binary_data):
                                            i1, i2, i3 = struct.unpack('<HHH', binary_data[offset:offset+6])
                                            model.add_face([int(i1), int(i2), int(i3)])
                                            total_faces += 1
                            elif accessor.componentType == 5125:  # UNSIGNED_INT (4 bytes)
                                for i in range(0, count, 3):
                                    if i + 2 < count:
                                        offset = byte_offset + i * 4
                                        if offset + 12 <= len(binary_data):
                                            i1, i2, i3 = struct.unpack('<III', binary_data[offset:offset+12])
                                            model.add_face([int(i1), int(i2), int(i3)])
                                            total_faces += 1
                            print(f"    Loaded {total_faces} faces (manual)")
        
            model.original_vertex_count = total_vertices
        
            if total_vertices == 0:
                print("❌ No vertices found in GLB file")
                return None
        
            print(f"\n📊 Original: {total_vertices:,} vertices, {total_faces:,} faces")
        
            # Simplify if too many faces
            if simplify and total_faces > target_faces:
                print(f"⚠️ Large model detected - simplifying to {target_faces} faces...")
                model.simplify(target_faces=target_faces)
        
            # Normalize the model
            model.normalize()
        
            print(f"✅ Final: {len(model.vertices):,} vertices, {len(model.faces):,} faces")
            return model
        
        except Exception as e:
            print(f"❌ Error loading GLB: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def create_cube_model(size: float = 2.0) -> Model3D:
        model = Model3D("cube")
        s = size / 2
        vertices = [
            (-s, -s, -s), ( s, -s, -s), ( s, -s,  s), (-s, -s,  s),
            (-s,  s, -s), ( s,  s, -s), ( s,  s,  s), (-s,  s,  s)
        ]
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
        faces = [
            [0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1],
            [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]
        ]
        for face in faces:
            model.add_face(face)
        return model
    
    @staticmethod
    def create_sphere_model(radius: float = 1.0) -> Model3D:
        model = Model3D("sphere")
        stacks = 15
        slices = 15
        
        for i in range(stacks + 1):
            phi = np.pi * i / stacks
            for j in range(slices + 1):
                theta = 2 * np.pi * j / slices
                x = radius * np.sin(phi) * np.cos(theta)
                y = radius * np.cos(phi)
                z = radius * np.sin(phi) * np.sin(theta)
                model.add_vertex(x, y, z)
        
        for i in range(stacks):
            for j in range(slices):
                p1 = i * (slices + 1) + j
                p2 = p1 + 1
                p3 = (i + 1) * (slices + 1) + j
                p4 = p3 + 1
                if i > 0:
                    model.add_face([p1, p2, p4])
                    model.add_face([p1, p4, p3])
                else:
                    model.add_face([p1, p2, p4])
        
        return model
    
    @staticmethod
    def load_model_auto(filepath: str, simplify: bool = True, max_faces: int = 5000) -> Optional[Model3D]:
        """Load model with automatic simplification"""
        filepath = filepath.strip().strip('"').strip("'")
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext == '.obj':
            return ModelLoader.load_obj(filepath, simplify)
        elif ext == '.glb':
            return ModelLoader.load_glb(filepath, simplify, max_faces)
        else:
            print(f"Unsupported format: {ext}")
            print("Supported: .obj, .glb")
            return None

    @staticmethod
    def create_cube(size: float = 2.0, position: Tuple[float, float, float] = (0, 0, 0)) -> Model3D:
        """Create a cube with optional position"""
        model = Model3D("cube")
        s = size / 2
    
        vertices = [
            (-s, -s, -s), ( s, -s, -s), ( s, -s,  s), (-s, -s,  s),  # Bottom
            (-s,  s, -s), ( s,  s, -s), ( s,  s,  s), (-s,  s,  s)   # Top
        ]
    
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
    
        faces = [
            [0, 1, 2, 3],  # Bottom
            [4, 7, 6, 5],  # Top
            [0, 4, 5, 1],  # Front
            [1, 5, 6, 2],  # Right
            [2, 6, 7, 3],  # Back
            [3, 7, 4, 0]   # Left
        ]
    
        for face in faces:
            model.add_face(face)
    
        model.position = position
        return model

    @staticmethod
    def create_sphere(radius: float = 1.0, segments: int = 20, position: Tuple[float, float, float] = (0, 0, 0)) -> Model3D:
        """Create a sphere with adjustable detail"""
        model = Model3D("sphere")
    
        # Generate vertices using spherical coordinates
        vertices = []
        for i in range(segments + 1):
            phi = np.pi * i / segments  # polar angle
            for j in range(segments + 1):
                theta = 2 * np.pi * j / segments  # azimuthal angle
            
                x = radius * np.sin(phi) * np.cos(theta)
                y = radius * np.cos(phi)
                z = radius * np.sin(phi) * np.sin(theta)
                vertices.append((x, y, z))
    
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
    
        # Generate faces (triangles)
        for i in range(segments):
            for j in range(segments):
                p1 = i * (segments + 1) + j
                p2 = p1 + 1
                p3 = (i + 1) * (segments + 1) + j
                p4 = p3 + 1
            
                if i > 0:
                    model.add_face([p1, p2, p4])
                    model.add_face([p1, p4, p3])
                else:
                    model.add_face([p1, p2, p4])
    
        model.position = position
        return model

    @staticmethod
    def create_cylinder(radius: float = 1.0, height: float = 2.0, segments: int = 24, position: Tuple[float, float, float] = (0, 0, 0)) -> Model3D:
        """Create a cylinder"""
        model = Model3D("cylinder")
    
        vertices = []
    
        # Bottom circle
        for i in range(segments):
            angle = 2 * np.pi * i / segments
            x = radius * np.cos(angle)
            z = radius * np.sin(angle)
            vertices.append((x, -height/2, z))
    
        # Top circle
        for i in range(segments):
            angle = 2 * np.pi * i / segments
            x = radius * np.cos(angle)
            z = radius * np.sin(angle)
            vertices.append((x, height/2, z))
    
        # Center vertices for bottom and top caps
        bottom_center_idx = len(vertices)
        vertices.append((0, -height/2, 0))
        top_center_idx = len(vertices)
        vertices.append((0, height/2, 0))
    
        # Add all vertices
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
    
        # Create faces for sides
        for i in range(segments):
            next_i = (i + 1) % segments
            bottom_i = i
            bottom_next = next_i
            top_i = segments + i
            top_next = segments + next_i
        
            model.add_face([bottom_i, top_i, top_next])
            model.add_face([bottom_i, top_next, bottom_next])
    
        # Bottom cap
        for i in range(segments):
            next_i = (i + 1) % segments
            model.add_face([bottom_center_idx, i, next_i])
    
        # Top cap
        for i in range(segments):
            next_i = (i + 1) % segments
            model.add_face([top_center_idx, segments + next_i, segments + i])
    
        model.position = position
        return model

    @staticmethod
    def create_cone(radius: float = 1.0, height: float = 2.0, segments: int = 24, position: Tuple[float, float, float] = (0, 0, 0)) -> Model3D:
        """Create a cone"""
        model = Model3D("cone")
    
        vertices = []
    
        # Bottom circle
        for i in range(segments):
            angle = 2 * np.pi * i / segments
            x = radius * np.cos(angle)
            z = radius * np.sin(angle)
            vertices.append((x, -height/2, z))
    
        # Apex
        apex_idx = len(vertices)
        vertices.append((0, height/2, 0))
    
        # Bottom center
        center_idx = len(vertices)
        vertices.append((0, -height/2, 0))
    
        # Add vertices
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
    
        # Create faces for sides
        for i in range(segments):
            next_i = (i + 1) % segments
            model.add_face([i, apex_idx, next_i])
    
        # Bottom cap
        for i in range(segments):
            next_i = (i + 1) % segments
            model.add_face([center_idx, next_i, i])
    
        model.position = position
        return model

    @staticmethod
    def create_pyramid(base_size: float = 2.0, height: float = 2.0, position: Tuple[float, float, float] = (0, 0, 0)) -> Model3D:
        """Create a square pyramid"""
        model = Model3D("pyramid")
        s = base_size / 2
    
        vertices = [
            (-s, -height/2, -s),  # 0: front-left bottom
            ( s, -height/2, -s),  # 1: front-right bottom
            ( s, -height/2,  s),  # 2: back-right bottom
            (-s, -height/2,  s),  # 3: back-left bottom
            (0,  height/2,  0)    # 4: apex
        ]
    
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
    
        faces = [
            [0, 1, 4],  # Front face
            [1, 2, 4],  # Right face
            [2, 3, 4],  # Back face
            [3, 0, 4],  # Left face
            [0, 3, 2, 1]  # Bottom face
        ]
    
        for face in faces:
            model.add_face(face)
    
        model.position = position
        return model

    @staticmethod
    def create_torus(radius: float = 1.5, tube_radius: float = 0.3, radial_segments: int = 30, tubular_segments: int = 30, position: Tuple[float, float, float] = (0, 0, 0)) -> Model3D:
        """Create a torus (donut shape)"""
        model = Model3D("torus")
    
        vertices = []
    
        for i in range(radial_segments):
            u = 2 * np.pi * i / radial_segments
            for j in range(tubular_segments):
                v = 2 * np.pi * j / tubular_segments
            
                x = (radius + tube_radius * np.cos(v)) * np.cos(u)
                y = tube_radius * np.sin(v)
                z = (radius + tube_radius * np.cos(v)) * np.sin(u)
                vertices.append((x, y, z))
    
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
    
        # Generate faces
        for i in range(radial_segments):
            for j in range(tubular_segments):
                next_i = (i + 1) % radial_segments
                next_j = (j + 1) % tubular_segments
            
                p1 = i * tubular_segments + j
                p2 = next_i * tubular_segments + j
                p3 = next_i * tubular_segments + next_j
                p4 = i * tubular_segments + next_j
            
                model.add_face([p1, p2, p3])
                model.add_face([p1, p3, p4])
    
        model.position = position
        return model

    @staticmethod
    def create_star(outer_radius: float = 1.5, inner_radius: float = 0.6, points: int = 5, height: float = 0.5, position: Tuple[float, float, float] = (0, 0, 0)) -> Model3D:
        """Create a 3D star shape"""
        model = Model3D("star")
    
        vertices = []
    
        # Generate star points
        for i in range(points * 2):
            angle = 2 * np.pi * i / (points * 2)
            radius = outer_radius if i % 2 == 0 else inner_radius
            x = radius * np.cos(angle)
            z = radius * np.sin(angle)
        
            # Bottom vertex
            vertices.append((x, -height/2, z))
            # Top vertex
            vertices.append((x, height/2, z))
    
        # Center vertices
        center_bottom = len(vertices)
        vertices.append((0, -height/2, 0))
        center_top = len(vertices)
        vertices.append((0, height/2, 0))
    
        for v in vertices:
            model.add_vertex(v[0], v[1], v[2])
    
        # Create faces (simplified - would need more complex logic for full star)
        num_verts = points * 2
        for i in range(num_verts):
            next_i = (i + 1) % num_verts
        
            # Bottom face
            model.add_face([center_bottom, i*2, next_i*2])
        
            # Top face
            model.add_face([center_top, next_i*2+1, i*2+1])
        
            # Side faces
            model.add_face([i*2, i*2+1, next_i*2+1])
            model.add_face([i*2, next_i*2+1, next_i*2])
    
        model.position = position
        return model


class ModelDeconstructor:
    def __init__(self):
        self.deconstructed_parts: List[Model3D] = []
        
    def deconstruct_by_face_groups(self, model: Model3D, group_size: int = 10) -> List[Model3D]:
        parts = []
        for i in range(0, len(model.faces), group_size):
            part = Model3D(f"{model.name}_part_{i//group_size}")
            face_group = model.faces[i:i+group_size]
            vertex_map = {}
            vertex_counter = 0
            
            for face in face_group:
                new_face_indices = []
                for v_idx in face.vertices:
                    if v_idx not in vertex_map:
                        vertex_map[v_idx] = vertex_counter
                        original_vertex = model.vertices[v_idx]
                        part.add_vertex(original_vertex.x, original_vertex.y, original_vertex.z)
                        vertex_counter += 1
                    new_face_indices.append(vertex_map[v_idx])
                part.add_face(new_face_indices, face.normal)
            
            if part.vertices:
                part.color = model.color
                parts.append(part)
        
        return parts