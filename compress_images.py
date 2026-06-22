import os
from PIL import Image

def optimize_image(filepath, max_dimension=800):
    try:
        if not os.path.exists(filepath):
            print(f"Not found: {filepath}")
            return
            
        print(f"Optimizing {filepath}...")
        img = Image.open(filepath)
        
        # Calculate new size maintaining aspect ratio
        ratio = min(max_dimension / img.width, max_dimension / img.height)
        
        if ratio < 1.0:
            new_size = (int(img.width * ratio), int(img.height * ratio))
            print(f"Resizing from {img.size} to {new_size}")
            # Use LANCZOS (or ANTIALIAS in older Pillow)
            resample_filter = getattr(Image, 'Resampling', Image).LANCZOS
            img = img.resize(new_size, resample_filter)
            
        # Save compressed
        img.save(filepath, optimize=True, quality=85)
        print(f"Done optimizing {filepath}. New size: {os.path.getsize(filepath)} bytes")
        
    except Exception as e:
        print(f"Failed to optimize {filepath}: {e}")

if __name__ == "__main__":
    base_dir = r"c:\Users\Mark Anthony Alegre\Documents\BrgyManagementSystem\static\images"
    optimize_image(os.path.join(base_dir, "bagong_pilipinas.png"))
    optimize_image(os.path.join(base_dir, "gigaquit_logo.png"))
    optimize_image(os.path.join(base_dir, "logo.png"))
    optimize_image(os.path.join(base_dir, "sico_sico_logo.png"))
