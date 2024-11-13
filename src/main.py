import numpy as np
import cv2
import time
import threading
from .image_processing import save_component_img
from .image_processing import transform_bounding_boxes_to_3D
from .setup import initialize_system
from .projection import setup_projector_window, calibrate_projector_camera
from .utils import open_image_in_paint, show_img
from .visualization import draw_axes, draw_tag_border_and_id, draw_bounding_box_and_drawing

def update_windows() -> None:
    while True:
        if cv2.getWindowProperty('AprilTag Detection', cv2.WND_PROP_VISIBLE) < 1 and \
           cv2.getWindowProperty(projector_window_name, cv2.WND_PROP_VISIBLE) < 1:
            break
        cv2.waitKey(1)
        time.sleep(0.01)

def main() -> None:
    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, camera_matrix, color_intrinsics, _ = initialize_system()

    """
    FIXME: Change to sth else to calibrate the projector-camera setup for the projector parameters
    try:
        H_proj = np.load('data/homography/homography_proj_cam.npy')
        print("Homography-matrix loaded.")
    except FileNotFoundError:
        user_input = input("Homographie-matrix not found. Do you want to calibrate the projector-camera setup? (j/n): ")
        if user_input.lower() == 'j':
            H_proj = calibrate_projector_camera(0.06, camera_matrix, color_intrinsics["dist_coeffs"])
            time.sleep(2)
        else:
            print("Exiting the program.")
            return"""

    # Setup the projector window
    global projector_window_name
    projector_window_name, projector_width, projector_height = setup_projector_window()

    # Start the thread to update the windows
    window_thread = threading.Thread(target=update_windows)
    window_thread.start()

    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    """drawings_3D = None 
    drawing_path = None"""

    """chess_board_pattern_path = "data/saved_images/pattern.png"
    chessboard_pattern = cv2.imread(chess_board_pattern_path)
    chessboard_pattern_resized = cv2.resize(chessboard_pattern, (projector_width, projector_height), interpolation=cv2.INTER_AREA)
    count = 0"""

    try:
        while True:
            # Get the frames from the camera
            color_image, depth_image, depth_frame, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue

            # Create an image for the projector
            projector_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)

            gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
            results = apriltag_detector.detect(gray)

            for result in results:
                # Get the distance to the center of the AprilTag
                u_center_of_tag, v_center_of_tag = int(result.center[0]), int(result.center[1])
                depth_to_tag = depth_frame.get_distance(u_center_of_tag, v_center_of_tag)
                print(f"Depth to AprilTag: {depth_to_tag}m")

                # Rotation vector (Orientation relative to the camera)
                R_ct = result.pose_R

                # Check if camera is too close to the tag
                if depth_to_tag > min_distance:
                    # axis_length = depth_to_tag / 4.0  # May be used to scale the axes according to the distance to the tag

                    # Translation vector (Position relative to the camera) -> calculated with the RealSense camera
                    tvec_realsense = camera.get_3D_camera_coords(u_center_of_tag, v_center_of_tag, depth_to_tag, color_intrinsics["intrinsics_raw"])

                    # Draw the axes and tag border with ID
                    color_image = draw_axes(color_image, R_ct, tvec_realsense, camera_matrix, color_intrinsics["dist_coeffs"], axis_length)

                    # Visualize the 3D bounding boxes if things were drawn on the image (to check if the 3D coordinates are correct)
                    """
                    FIXME: Don't know if this is still needed or if it should be removed
                    if drawings_3D is not None:
                        if drawing_path is not None:
                            drawing_img = cv2.imread(drawing_path)

                            for drawing in drawings_3D:
                                projector_image = draw_bounding_box_and_drawing(
                                img=projector_image,
                                drawing_img=drawing_img,
                                drawing=drawing,
                                R_ct=R_ct,
                                tvec=tvec_realsense,
                                camera_matrix=camera_matrix,
                                dist_coeffs=color_intrinsics["dist_coeffs"]
                            )
                        else:
                            print("No drawing path provided. Please provide a path to the drawing image.")
                    else:
                        print("No 3D drawings found.")"""
                else:
                    cv2.putText(color_image, "Too close!, please move away a few cm.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Always draw the tag border and ID
                # color_image = draw_tag_border_and_id(color_image, result)

            # Display on the projector
            cv2.imshow(projector_window_name, projector_image)

            # Display the image with the AprilTag detection
            cv2.imshow('AprilTag Detection', color_image)

            # Wait for a key press
            key = cv2.waitKey(1) & 0xFF

            # Save the image of the component if a tag was detected and open it for editing
            if key == ord(' '):
                """saved_image_path, saved_filename = save_component_img(color_image, count)
                count += 1"""

                if results:
                    # Save the image of the component and open it for editing
                    saved_image_path, saved_filename = save_component_img(color_image, results[0].tag_id)
                    open_image_in_paint(saved_image_path)


                    # FIXME: Paths for the edited image and the drawing (currently "hard coded")
                    edited_img_path = "data/saved_images/edited_" + saved_filename
                    drawing_path = "data/saved_images/drawing_edited_" + saved_filename

                    # Open the edited image in a window
                    show_img(edited_img_path)

                    # Get the drawings and transform the 2D bounding boxes to 3D
                    # drawings_3D = transform_bounding_boxes_to_3D(drawing_path, depth_frame, color_intrinsics, (R_ct, tvec_realsense))

            # Close the window if the 'q' key is pressed
            if key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
