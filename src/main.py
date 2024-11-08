import numpy as np
import cv2
from .camera import Camera
from .apriltag_detection import AprilTagDetector
from .visualization import *
from .image_processing import save_component_img
from .user_interaction import edit_saved_image
from tests import test_apriltag_detection
from .utils import *
from .image_processing import transform_bounding_boxes_to_3D

def main() -> None:
    # Initialize the camera
    camera = Camera()

    # Get the intrinsics of the camera
    color_intrinsics = camera.get_color_sensor_intrinsics()
    # depth_intrinsics = camera.get_depth_sensor_intrinsics()

    # Initialize the AprilTag detector
    apriltag_detector = AprilTagDetector(fx=color_intrinsics["fx"], fy=color_intrinsics["fy"], cx=color_intrinsics["ppx"], cy=color_intrinsics["ppy"])

    # Set the camera matrix with the intrinsics
    camera_matrix = np.array([[apriltag_detector.fx, 0, apriltag_detector.cx],
                            [0, apriltag_detector.fy, apriltag_detector.cy],
                            [0, 0, 1]])
    
    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    drawings_3D = None 

    projector_width = 1920
    projector_height = 1080

    projector_window_name = 'Projector Window'
    cv2.namedWindow(projector_window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(projector_window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    projector_screen_x = 1920
    cv2.moveWindow(projector_window_name, projector_screen_x, 0)
    
    try:
        while True:
            # Get the frames from the camera
            color_image, depth_image, depth_frame, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue

            # Convert the frame to grayscale for AprilTag detection
            gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)

            # Detect AprilTags in the image
            results = apriltag_detector.detect(gray)

            # Create an image for the projector
            projector_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)

            for result in results:
                # Get the distance to the center of the AprilTag
                u_center_of_tag, v_center_of_tag = int(result.center[0]), int(result.center[1])
                depth_to_tag = depth_frame.get_distance(u_center_of_tag, v_center_of_tag)
                print(f"Depth to AprilTag: {depth_to_tag}m")

                # Rotation vector (Orientation relative to the camera)
                rvec = result.pose_R

                # Check if camera is too close to the tag
                if depth_to_tag > min_distance:
                    # axis_length = depth_to_tag / 4.0  # May be used to scale the axes according to the distance to the tag

                    # Translation vector (Position relative to the camera) -> calculated with the RealSense camera
                    tvec_realsense = camera.get_3D_camera_coords(u_center_of_tag, v_center_of_tag, depth_to_tag, color_intrinsics["intrinsics_raw"])

                    # Draw the axes and tag border with ID
                    color_image = draw_axes(color_image, rvec, tvec_realsense, camera_matrix, color_intrinsics["dist_coeffs"], axis_length)

                    # Visualize the 3D bounding boxes if things were drawn on the image (to check if the 3D coordinates are correct)
                    if drawings_3D is not None:
                        drawing_img = cv2.imread(drawing_path)

                        for drawing in drawings_3D:
                            projector_image = draw_bounding_box_and_drawing_projector(
                            img=projector_image,
                            drawing_img=drawing_img,
                            drawing=drawing,
                            R_ct=rvec,
                            tvec=tvec_realsense,
                            camera_matrix=camera_matrix,
                            dist_coeffs=np.zeros(5)
                            # Optional: pass H_proj if calibration was done 
                        )
                else:
                    cv2.putText(color_image, "Too close!, please move away a few cm.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Always draw the tag border and ID
                color_image = draw_tag_border_and_id(color_image, result)
            
            # Display on the projector
            cv2.imshow(projector_window_name, projector_image)
            cv2.waitKey(1)

            # Display the image with the AprilTag detection
            cv2.imshow('AprilTag Detection with Axes and IDs', color_image)

            # Wait for a key press
            key = cv2.waitKey(1) & 0xFF

            # Save the image of the component if a tag was detected and open it for editing
            if key == ord(' '):
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
                    drawings_3D = transform_bounding_boxes_to_3D(drawing_path, depth_frame, color_intrinsics, (rvec, tvec_realsense))

                    # Test the difference between the original estimated tvec and the manual calculation
                    # test_apriltag_detection.test_tvec_difference(results, depth_to_tag, camera, color_intrinsics, tvec_realsense, saved_image_path, apriltag_detector)

                    # edit_saved_image(saved_image_path, rvec, tvec_realsense, depth_frame, color_intrinsics)

            # Close the window if the 'q' key is pressed
            if key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
