import numpy as np
import cv2

def test_tvec_difference(results, depth_to_tag, camera, color_intrinsics, tvec_realsense, saved_image_path, apriltag_detector):
    """
    Test the difference between the original translation vector and the new translation vector.

    :param results: List of AprilTag detection results
    :param depth_to_tag: Depth to the AprilTag in meters
    :param camera: Camera object
    :param u_center_of_tag: x-coordinate of the center of the AprilTag
    :param v_center_of_tag: y-coordinate of the center of the AprilTag
    :param color_intrinsics: Intrinsics of the color sensor
    :param tvec_manual: Manual calculation of the translation vector
    :param saved_image_path: Path to the saved image
    :param apriltag_detector: AprilTagDetector object
    """
    print("-----------------------------------------------------------------")

    print(f"{len(results)} Apriltags detected.")
    print(f"Center of AprilTag in pixel coordinates: {results[0].center}")
    print(f"Depth to AprilTag: {depth_to_tag}m")


    print(f"Rotation matrix: {results[0].pose_R}")
    print("-----------------------------------------------------------------")
    print(f"Oringinal estimated translation vector: {results[0].pose_t}")
    print("-----------------------------------------------------------------")  
    print(f"New translation vector (RealSense Method): {tvec_realsense}")
    print("-----------------------------------------------------------------")

    # Calculate the difference between the original translation vector and the new translation vector
    delta_t = results[0].pose_t - tvec_realsense
    
    # Calculate the euclidean distance between the original translation vector and the new translation vector
    euclidean_distance = np.linalg.norm(delta_t)
    
    print(f"Differential translation vector from original tvec and new tvec: {delta_t}")
    print(f"Euclidean distance between the two translation vectors: {euclidean_distance:.6f} meters")

    # Transform the 3D coordinates of the original translation vector to pixel coordinates
    pose_pixel = camera.get_2D_pixel_coords(color_intrinsics["intrinsics_raw"], results[0].pose_t)

    # Transform the 3D coordinates of the new translation vector to pixel coordinates
    depth_pixel = camera.get_2D_pixel_coords(color_intrinsics["intrinsics_raw"], tvec_realsense)

    print(f"Path to saved image: '{saved_image_path}'")  

    image = cv2.imread(saved_image_path)

    # Draw the pixel coordinate of estimated tvec of the AprilTag (yellow)
    cv2.circle(image, pose_pixel, 5, (0, 255, 255), -1)  
    cv2.circle(image, pose_pixel, 7, (0, 0, 0), 2)
    cv2.putText(image, f"Original tvec: (x: {pose_pixel[0]}px, y: {pose_pixel[1]}px)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)


    # Draw the pixel coordinate of calculated tvec of the AprilTag (magenta)
    cv2.circle(image, depth_pixel, 5, (255, 0, 255), -1)
    cv2.circle(image, depth_pixel, 7, (0, 0, 0), 2) 
    cv2.putText(image, f"New tvec: (x: {depth_pixel[0]}px, y: {depth_pixel[1]}px)", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)

    # Calculate the pixel distance between the original and the new translation vector
    pixel_distance = np.sqrt((depth_pixel[0] - pose_pixel[0]) ** 2 + (depth_pixel[1] - pose_pixel[1]) ** 2)

    # Draw a line between the original and the new translation vector
    cv2.line(image, pose_pixel, depth_pixel, (255, 255, 0), 2)
    center_line = ((pose_pixel[0] + depth_pixel[0]) // 2, (pose_pixel[1] + depth_pixel[1]) // 2)
    cv2.putText(image, f"{pixel_distance:.2f} px", center_line, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Show the image with the pixel coordinates of the original and the new translation vector
    apriltag_detector.show_tvec_comparison_image(image)