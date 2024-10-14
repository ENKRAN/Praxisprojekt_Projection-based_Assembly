import numpy as np
import cv2
from camera import Camera
from apriltag_detection import AprilTagDetector
from visualization import draw_axes, draw_tag_border_and_id

def main() -> None:
    # Initialize the camera
    camera = Camera(enable_depth=False)

    # Get the color sensor and its intrinsics
    fx, fy, ppx, ppy, dist_coeffs = camera.get_color_sensor_intrinsics()

    apriltag_detector = AprilTagDetector(fx=fx, fy=fy, cx=ppx, cy=ppy)

    # Set the camera matrix with the intrinsics
    camera_matrix = np.array([[apriltag_detector.fx, 0, apriltag_detector.cx],
                            [0, apriltag_detector.fy, apriltag_detector.cy],
                            [0, 0, 1]])
    
    # Length of the axes in the visualization
    axis_length = apriltag_detector.tag_size * 2.0  # Axis length is twice the tag size

    try:
        while True:
            color_frame, _ = camera.get_frames()
            if color_frame is None:
                continue

            # Convert the frame to grayscale for AprilTag detection
            gray = cv2.cvtColor(color_frame, cv2.COLOR_BGR2GRAY)

            # Detect AprilTags in the image
            results = apriltag_detector.detect(gray)

            for result in results:
                # print(f"Tag ID: {result.tag_id}")

                # Translation vector (Position relative to the camera)
                tvec = result.pose_t

                # Rotation vector (Orientation relative to the camera)
                rvec = result.pose_R

                # TODO: Maybe implement z-axis stabilization
                
                # Draw the coordinate axes on the image
                color_frame = draw_axes(color_frame, rvec, tvec, camera_matrix, dist_coeffs, axis_length)

                # Draw the border and ID of the tag on the image
                color_frame = draw_tag_border_and_id(color_frame, result)

            # Display the image with the AprilTag detection
            cv2.imshow('AprilTag Detection with Axes and IDs', color_frame)
            if cv2.waitKey(1) == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
