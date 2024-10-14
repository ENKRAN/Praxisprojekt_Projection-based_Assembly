import cv2
import time
import os

def save_component_img(frame, tag_id, save_dir="../data/saved_images") -> str:
    """
    Save an image of a component to disk

    :param frame: Color frame containing the component
    :param tag_id: ID of the component
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
    print(f"Image saved: {filepath}")

    return filepath
