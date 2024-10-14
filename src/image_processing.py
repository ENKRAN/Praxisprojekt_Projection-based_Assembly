import cv2
import time

def save_component_img(frame, tag_id) -> None:
    """
    Save an image of a component to disk

    :param frame: Color frame containing the component
    :param tag_id: ID of the component
    """
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"component_{tag_id}_{timestamp}.png"
    cv2.imwrite(filename, frame)
    print(f"Image saved: {filename}")
