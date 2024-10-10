import pyrealsense2 as rs
import numpy as np
import cv2
from pupil_apriltags import Detector

def draw_axes(img, rvec, tvec, camera_matrix, dist_coeffs, axis_length) -> np.ndarray:
    # Define 3D points for the axes: Origin and end points for x, y, z axes
    axis_points = np.float32([[0, 0, 0],            # Origin
                              [axis_length, 0, 0],  # x-axis
                              [0, axis_length, 0],  # y-axis
                              [0, 0, axis_length]]) # z-axis

    # Project the 3D axis points onto the 2D image
    imgpts, _ = cv2.projectPoints(axis_points, rvec, tvec, camera_matrix, dist_coeffs)

    # Convert the points into integer pixel coordinates
    imgpts = np.int32(imgpts).reshape(-1, 2)

    # Draw the axes (x=red, y=green, z=blue) with arrow tips
    origin = tuple(imgpts[0])
    img = cv2.arrowedLine(img, origin, tuple(imgpts[1]), (0, 0, 255), 2, tipLength=0.3)  # x-axis (red)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[2]), (0, 255, 0), 2, tipLength=0.3)  # y-axis (green)
    img = cv2.arrowedLine(img, origin, tuple(imgpts[3]), (255, 0, 0), 2, tipLength=0.3)  # z-axis (blue)

    return img

def draw_tag_border_and_id(frame, result) -> np.ndarray:
    corners = np.array(result.corners, dtype=np.int32).reshape((-1, 1, 2))
    
    # Draw the border of the tag
    frame = cv2.polylines(frame, [corners], isClosed=True, color=(0, 255, 0), thickness=2)

    # Label the tag with its ID
    center = tuple(corners[0][0])
    cv2.putText(frame, f"ID: {result.tag_id}", (center[0], center[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return frame

def main() -> None:
    # Initialize the RealSense pipeline
    pipeline = rs.pipeline()
    config = rs.config()

    # Choose the color stream
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    # Start the pipeline with the configuration
    profile = pipeline.start(config)

    # Get the color sensor and its intrinsics
    color_sensor = profile.get_device().first_color_sensor()
    intrinsics = color_sensor.get_stream_profiles()[0].as_video_stream_profile().get_intrinsics()

    # Get the camera parameters
    fx = intrinsics.fx  # Focal length in x-direction
    fy = intrinsics.fy  # Focal length in y-direction
    cx = intrinsics.ppx  # Principal point in x-direction
    cy = intrinsics.ppy  # Principal point in y-direction
    dist_coeffs = np.array(intrinsics.coeffs)  # Distortion coefficients

    # Set the camera matrix with the intrinsics
    camera_matrix = np.array([[fx, 0, cx],
                            [0, fy, cy],
                            [0, 0, 1]])

    # AprilTag size (edge length in meters)
    tag_size = 0.04

    # Initialize the AprilTag detector
    detector = Detector(families="tagStandard41h12")

    # Length of the axes in the visualization
    axis_length = tag_size * 2.0  # Axis length is twice the tag size

    # Z-Axis stabilization
    previous_z_direction = None

    try:
        while True:
            # Wait for the next set of frames
            frames = pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            # Convert the color frame to a numpy array for OpenCV
            frame = np.asanyarray(color_frame.get_data())

            # Convert the frame to grayscale for AprilTag detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect AprilTags in the image
            results = detector.detect(gray, estimate_tag_pose=True, camera_params=[fx, fy, cx, cy], tag_size=tag_size)

            for result in results:
                # print(f"Tag ID: {result.tag_id}")

                # Translation vector (Position relative to the camera)
                tvec = result.pose_t
                # Matrix representing the rotation (Orientation relative to the camera)
                rvec = result.pose_R

                # Stabilize the z-axis direction
                current_z_direction = np.sign(tvec[2])
                if previous_z_direction is not None and current_z_direction != previous_z_direction:
                    print("Warning: z-axis direction changed!")
                    if tvec[2] < 0:
                        tvec = -tvec  # Invert the entire translation vector if z is negative

                # Update the previous z-direction
                previous_z_direction = current_z_direction

                # Draw the coordinate axes on the image
                frame = draw_axes(frame, rvec, tvec, camera_matrix, dist_coeffs, axis_length)

                # Draw the border and ID of the tag on the image
                frame = draw_tag_border_and_id(frame, result)

            # Display the image with the AprilTag detection
            cv2.imshow('AprilTag Detection with Axes and IDs', frame)
            if cv2.waitKey(1) == ord('q'):
                break
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
