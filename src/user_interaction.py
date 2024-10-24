import cv2
from .utils import pixelcoords_to_apriltagcoords

# Global variables for drawing
drawing = False  # True if the mouse is pressed
mode = 'circle'  # Default mode is to draw circles
ix, iy = -1, -1  # Initial mouse position
temp_img = None  # Temporary image for drawing

def draw(event, x, y, flags, params) -> None:
    """
    Mouse callback function to handle drawing on the image.

    :param event: The mouse event (e.g., left button down, move, up)
    :param x: X-coordinate of the mouse position
    :param y: Y-coordinate of the mouse position
    :param flags: Any flags passed by OpenCV
    :param params: Additional parameters for the callback function
    """
    global ix, iy, drawing, mode, temp_img

    # Extract the parameters from the dictionary
    rvec = params["rvec"]
    tvec = params["tvec"]
    img = params["image"]
    depth_frame = params["depth_frame"]
    depth_intrinsics = params["depth_intrinsics"]


    # Left mouse button pressed - set the initial point
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        temp_img = img.copy()  # Make a copy to preserve the original image

    # Mouse moved - draw based on the current mode (circle or line)
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            # Restore the original image to avoid "trails"
            img[:] = temp_img.copy()
            if mode == 'circle':
                # Draw a circle as a preview
                cv2.circle(img, (ix, iy), int(((x-ix)**2 + (y-iy)**2)**0.5), (255, 255, 0), 2)
            elif mode == 'line':
                # Draw a line as a preview
                cv2.line(img, (ix, iy), (x, y), (255, 0, 0), 2)

    # Left mouse button released - finalize the drawing
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False

        if mode == 'circle':
            # Finalize the circle on the original image
            cv2.circle(img, (ix, iy), int(((x-ix)**2 + (y-iy)**2)**0.5), (255, 255, 0), 2)
            cv2.putText(img, f"(x: {ix}px, y: {iy}px)", (ix, iy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            print(f"Circle drawn at: (x: {ix}px, y: {iy}px) with radius: {int(((x-ix)**2 + (y-iy)**2)**0.5)}px")
        elif mode == 'line':
            # Finalize the line on the original image
            cv2.line(img, (ix, iy), (x, y), (255, 0, 0), 2)
            print(f"Line drawn from: (x: {ix}px, y: {iy}px) to (x: {x}px, y: {y}px)")

        april_tag_pose = (rvec, tvec)

        # Calculate the 3D coordinates relative to the AprilTag by transforming the pixel coordinates
        at_coords = pixelcoords_to_apriltagcoords(ix, iy, depth_frame, depth_intrinsics, april_tag_pose)

        if at_coords is not None:
            print(f"3D-Coordinates relative to AprilTag: ({at_coords[0]}, {at_coords[1]}, {at_coords[2]})")
        else:
            print("Could not calculate 3D-Coordinates relative to AprilTag")

        # print(f"Mouse coordinates (Pixel): (x: {x}px, y: {y}px)") # Debugging

def edit_saved_image(image_path, rvec, tvec_manual, depth_frame, depth_intrinsics) -> None:    
    """
    Opens a saved image and allows the user to draw on it.

    :param image_path: The path to the saved image
    :param rvec: The rotation vector from the AprilTag detection
    :param tvec_manual: The manually calculated translation vector
    :param depth_frame: The depth frame from the RealSense camera
    :param depth_intrinsics: The depth intrinsics from the RealSense camera
    """
    global temp_img

    # Load the saved image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Image not found: {image_path}")
        return

    temp_img = img.copy()  # Temporary image for drawing

    # Pack the additional parameters into a dictionary
    params = {
        "rvec": rvec,
        "tvec": tvec_manual,
        "image": img,
        "depth_frame": depth_frame,
        "depth_intrinsics": depth_intrinsics
    }

    cv2.namedWindow('Editing')
    cv2.setMouseCallback('Editing', draw, params)

    while True:
        # Display the image with current drawings
        cv2.imshow('Editing', img)

        # Check for key presses
        key = cv2.waitKey(1) & 0xFF

        # Switch mode: 'l' for line, 'c' for circle
        if key == ord('l'):
            global mode
            mode = 'line'
            print("Drawing mode: Line")
        elif key == ord('c'):
            mode = 'circle'
            print("Drawing mode: Circle")

        # Save the edited image with 's'
        if key == ord('s'):
            cv2.imwrite('data/saved_images/edited_image.png', img)
            print("Edited image saved at: ../data/saved_images/edited_image.png")

        # Quit the editing with 'q'
        if key == ord('q'):
            break

    cv2.destroyAllWindows()
