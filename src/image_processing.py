import cv2
import time
import os

def save_component_img(frame, tag_id, save_dir="data/saved_images") -> str:
    """
    Save the component image to disk.

    :param frame: The image to save
    :param tag_id: The tag ID
    :param save_dir: The directory to save the image to
    :return: The path to the saved image
    """    
    # Create the directory if it does not exist
    os.makedirs(save_dir, exist_ok=True)

    # Generate a filename and timestamp
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"component_{tag_id}_{timestamp}.png"

    # Full path to the file
    filepath = os.path.join(save_dir, filename)

    # Save the image to disk
    cv2.imwrite(filepath, frame)
    print(f"Image saved at: {filepath}")

    return filepath
