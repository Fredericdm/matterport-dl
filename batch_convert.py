#!/usr/bin/env python3
import os
import re
import sys
import shutil
import subprocess
from pathlib import Path

# Ensure Pillow is installed
try:
    from PIL import Image
except ImportError:
    print("Pillow not found. Installing Pillow...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image

# Ensure py360convert (and numpy) is installed
try:
    import py360convert
    import numpy as np
except ImportError:
    print("py360convert or numpy not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "py360convert"])
    import py360convert
    import numpy as np

##################################
# 1. Configuration
##################################

# Use custom downloads folder if provided; otherwise, use default:
if len(sys.argv) > 1:
    downloads_root = sys.argv[1]
else:
    downloads_root = str(Path.home() / "Desktop" / "matterport-dl-main" / "downloads")
downloads_root = os.path.abspath(downloads_root)
print(f"Using Matterport-dl downloads folder: {downloads_root}")

# Matterport main folder: where this script is located.
matterport_main = os.getcwd()

# The py360convert folder is inside the Matterport main folder.
py360_dir = os.path.join(matterport_main, "py360convert")

##################################
# Folder renaming as requested:
##################################

# Instead of "skybox", we now use "cubemaps" for the input cubemap sets.
cubemaps_root = os.path.join(py360_dir, "cubemaps")
os.makedirs(cubemaps_root, exist_ok=True)
print(f"Using cubemaps folder: {cubemaps_root}")

# The output folder (converted outputs) is now "panoramas".
panoramas_root = os.path.join(py360_dir, "panoramas")
os.makedirs(panoramas_root, exist_ok=True)
print(f"Using panoramas folder: {panoramas_root}")

# Mapping from skybox face number to direction name.
direction_mapping = {
    "0": "top",
    "1": "front",
    "2": "right",
    "3": "back",
    "4": "left",
    "5": "bottom"
}

# Regex for matching filenames like <identifier>_skybox<number>.jpg
skybox_pattern = re.compile(r"^(.*?)_skybox(\d+)\.jpg$", re.IGNORECASE)

##################################
# 2. Copy and Rename Skybox Images
##################################

def copy_and_rename_skybox_image(tour_code, identifier, face_num, src_path):
    """
    Copies a single skybox image from src_path into:
      cubemaps/<tour_code>/<identifier>/
    and renames it based on the direction mapping.
    """
    tour_folder = os.path.join(cubemaps_root, tour_code)
    identifier_folder = os.path.join(tour_folder, identifier)
    os.makedirs(identifier_folder, exist_ok=True)

    if face_num in direction_mapping:
        new_name = f"{direction_mapping[face_num]}.jpg"
    else:
        new_name = os.path.basename(src_path)

    dst_path = os.path.join(identifier_folder, new_name)
    shutil.copy2(src_path, dst_path)
    print(f"Copied '{src_path}' → '{dst_path}'")

print(f"\nSearching for tours in {downloads_root}...")

# Process each tour in the downloads folder.
for tour_code in os.listdir(downloads_root):
    tour_path = os.path.join(downloads_root, tour_code)
    if not os.path.isdir(tour_path):
        continue

    print(f"\nProcessing tour folder: {tour_code}")
    # Recursively search for skybox images in this tour folder.
    for root, dirs, files in os.walk(tour_path):
        for filename in files:
            if "skybox" in filename.lower() and filename.lower().endswith(".jpg"):
                match = skybox_pattern.match(filename)
                if match:
                    identifier = match.group(1)
                    face_num = match.group(2)
                    src_path = os.path.join(root, filename)
                    copy_and_rename_skybox_image(tour_code, identifier, face_num, src_path)

print("\nSkybox images copied and renamed into the local 'cubemaps' folder.")

##################################
# 3. Convert Each Cubemap Set to Equirectangular
##################################

# High-quality output dimensions and interpolation settings.
out_width, out_height = 4096, 2048
interp_mode = 'bicubic'

# Mapping for face filenames to py360convert keys.
face_keys = {
    "front": "F",
    "right": "R",
    "back": "B",
    "left": "L",
    "top": "U",
    "bottom": "D"
}

def convert_cubemap_folder(tour_code, identifier):
    """
    Looks in cubemaps/<tour_code>/<identifier>/ for the six face images
    (top.jpg, front.jpg, right.jpg, back.jpg, left.jpg, bottom.jpg)
    and converts them into a single equirectangular image saved in panoramas/<tour_code>/.
    If the output file already exists, the conversion is skipped.
    """
    cube_dict = {}
    folder_path = os.path.join(cubemaps_root, tour_code, identifier)

    # Construct output path
    tour_output_folder = os.path.join(panoramas_root, tour_code)
    os.makedirs(tour_output_folder, exist_ok=True)
    output_filename = f"{tour_code}_{identifier}_equirectangular.png"
    output_path = os.path.join(tour_output_folder, output_filename)

    if os.path.exists(output_path):
        print(f"Output already exists for {tour_code}/{identifier}. Skipping conversion.")
        return

    missing_face = False
    for face, key in face_keys.items():
        face_file = os.path.join(folder_path, f"{face}.jpg")
        if not os.path.exists(face_file):
            print(f"Missing '{face}.jpg' in {folder_path}. Skipping this set.")
            missing_face = True
            break
        cube_dict[key] = np.array(Image.open(face_file))

    if missing_face:
        return

    try:
        e_img = py360convert.c2e(cube_dict,
                                 h=out_height,
                                 w=out_width,
                                 cube_format='dict',
                                 mode=interp_mode)
    except Exception as e:
        print(f"Error converting {folder_path}: {e}")
        return

    Image.fromarray(e_img).save(output_path)
    print(f"Converted: {folder_path} -> {output_path}")

print("\nStarting conversion to equirectangular images...")

for tour_code in os.listdir(cubemaps_root):
    tour_folder = os.path.join(cubemaps_root, tour_code)
    if not os.path.isdir(tour_folder):
        continue

    for identifier in os.listdir(tour_folder):
        identifier_folder = os.path.join(tour_folder, identifier)
        if os.path.isdir(identifier_folder):
            convert_cubemap_folder(tour_code, identifier)

print("\nAll processes completed.")
