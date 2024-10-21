import numpy as np
import cv2
from camera import Camera
from apriltag_detection import AprilTagDetector
from visualization import draw_axes, draw_tag_border_and_id, visualize_depth_image
from image_processing import save_component_img
from user_interaction import edit_saved_image

def main() -> None:
    # Initialize the camera
    camera = Camera()

    # Get the color sensor and its intrinsics
    color_intrinsics = camera.get_color_sensor_intrinsics()

    depth_intrinsics = camera.get_depth_sensor_intrinsics()

    apriltag_detector = AprilTagDetector(fx=color_intrinsics["fx"], fy=color_intrinsics["fy"], cx=color_intrinsics["ppx"], cy=color_intrinsics["ppy"])

    # Set the camera matrix with the intrinsics
    camera_matrix = np.array([[apriltag_detector.fx, 0, apriltag_detector.cx],
                            [0, apriltag_detector.fy, apriltag_detector.cy],
                            [0, 0, 1]])
    
    # Length of the axes in the visualization
    axis_length = apriltag_detector.tag_size * 2.0  # Axis length is twice the tag size
    
    try:
        while True:
            color_image, depth_image, depth_frame, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue

            # Convert the frame to grayscale for AprilTag detection
            gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)

            # Detect AprilTags in the image
            results = apriltag_detector.detect(gray)

            for result in results:
                # Translation vector (Position relative to the camera)
                tvec = result.pose_t

                # Rotation vector (Orientation relative to the camera)
                rvec, _ = cv2.Rodrigues(result.pose_R)

                # TODO: Maybe implement z-axis stabilization
                
                # Draw the axes and tag border with ID
                color_image = draw_axes(color_image, rvec, tvec, camera_matrix, color_intrinsics["dist_coeffs"], axis_length)
                color_image = draw_tag_border_and_id(color_image, result)

            # Display the image with the AprilTag detection
            cv2.imshow('AprilTag Detection with Axes and IDs', color_image)

            # Wait for a key press
            key = cv2.waitKey(1) & 0xFF

            # Save the image if the space key is pressed
            if key == ord(' '):
                if results:
                    # Save the image of the component if a tag was detected and open it for editing
                    visualize_depth_image(depth_image)  # Visualisiere hier das Tiefenbild
                    saved_image_path = save_component_img(color_image, results[0].tag_id)


                    edit_saved_image(saved_image_path, results[0], camera_matrix, depth_frame, depth_intrinsics)
            # Close the window if the 'q' key is pressed
            if key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
