import cv2

# Global variables for drawing
drawing = False  # True if the mouse is pressed
mode = 'circle'  # Default mode is to draw circles
ix, iy = -1, -1  # Initial mouse position
temp_img = None  # Temporary image for drawing

def draw(event, x, y, flags, param) -> None:
    """
    Mouse callback function to handle drawing on the image.

    :param event: The mouse event (e.g., left button down, move, up)
    :param x: X-coordinate of the mouse position
    :param y: Y-coordinate of the mouse position
    :param flags: Any flags passed by OpenCV
    :param param: The original image being drawn on (passed as parameter)
    """
    global ix, iy, drawing, mode, temp_img

    # Left mouse button pressed - set the initial point
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        temp_img = param.copy()  # Make a copy to preserve the original image

    # Mouse moved - draw based on the current mode (circle or line)
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            # Restore the original image to avoid "trails"
            param[:] = temp_img.copy()
            if mode == 'circle':
                # Draw a circle as a preview
                cv2.circle(param, (ix, iy), int(((x-ix)**2 + (y-iy)**2)**0.5), (0, 255, 0), 2)
            elif mode == 'line':
                # Draw a line as a preview
                cv2.line(param, (ix, iy), (x, y), (255, 0, 0), 2)

    # Left mouse button released - finalize the drawing
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        if mode == 'circle':
            # Finalize the circle on the original image
            cv2.circle(param, (ix, iy), int(((x-ix)**2 + (y-iy)**2)**0.5), (0, 255, 0), 2)
            print(f"Circle drawn at: ({ix}, {iy}) with radius: {int(((x-ix)**2 + (y-iy)**2)**0.5)}")
        elif mode == 'line':
            # Finalize the line on the original image
            cv2.line(param, (ix, iy), (x, y), (255, 0, 0), 2)
            print(f"Line drawn from: ({ix}, {iy}) to ({x}, {y})")

def edit_saved_image(image_path: str) -> None:
    """
    Opens a saved image and allows the user to draw on it.

    :param image_path: Path to the saved image to be edited
    """
    global temp_img

    # Load the saved image
    img = cv2.imread(image_path)
    if img is None:
        print(f"Image not found: {image_path}")
        return

    temp_img = img.copy()  # Temporary image for drawing

    cv2.namedWindow('Editing')
    cv2.setMouseCallback('Editing', draw, img)

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
            cv2.imwrite('../data/saved_images/edited_image.png', img)
            print("Edited image saved at: ../data/saved_images/edited_image.png")

        # Quit the editing with 'q'
        if key == ord('q'):
            break

    cv2.destroyAllWindows()
