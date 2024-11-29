import numpy as np
import cv2
import time
import threading
from .image_processing import save_component_img
from .setup import initialize_system, get_calibration_data
from .projection import setup_projector_window
from .utils import open_image_in_paint, show_img
from .visualization import draw_axes, draw_tag_border_and_id
import os

def update_windows() -> None:
    while True:
        if cv2.getWindowProperty('AprilTag Projection Mapping', cv2.WND_PROP_VISIBLE) < 1 and \
           cv2.getWindowProperty(projector_window_name, cv2.WND_PROP_VISIBLE) < 1:
             break
        cv2.waitKey(1)
        time.sleep(0.01)

def extract_valid_image_points(image_with_drawings, depth_image, depth_scale):
    """
    Extracts the valid image points (2D), depth values (meters) and colors (RGB) from the image with drawings using the depth image.

    :param image_with_drawings: The image with the drawings (RGB)
    :param depth_image: The depth image (millimeters)
    :param depth_scale: The depth scale of the depth sensor
    :return: The valid image points, depth values and colors
    """
    # Extract all non-black pixels
    non_black_mask = np.any(image_with_drawings != [0, 0, 0], axis=-1)                
    
    # Get the coordinates and colors of the non-black pixels
    non_black_coords = np.column_stack(np.nonzero(non_black_mask))
    non_black_colors = image_with_drawings[non_black_mask]

    # Scale the depth_image to meters and get the depth values of the non-black pixels
    depth_image = depth_image * depth_scale
    depth_values = depth_image[non_black_coords[:, 0], non_black_coords[:, 1]]

    # Filter out the invalid depth values
    valid_depth_mask = (depth_values > 0) & (~np.isnan(depth_values))

    # Save the valid coordinates, colors and depth values
    valid_coords = non_black_coords[valid_depth_mask]
    valid_colors = non_black_colors[valid_depth_mask]
    valid_depths = depth_values[valid_depth_mask]

    # Store the valid image points in the format (u, v)
    image_points = valid_coords[:, [1, 0]].astype(np.float32).reshape(-1, 1, 2)  # (u, v)

    return image_points, valid_depths, valid_colors

def cam_2D_to_cam_3D(image_with_drawings, depth_image, depth_scale, cam_K, cam_kc):
    """
    Transform the 2D camera image points to 3D camera coordinates.

    :param image_with_drawings: The image with the drawings (RGB)
    :param depth_image: The depth image (millimeters)
    :param depth_scale: The depth scale of the depth sensor
    :param cam_K: The camera matrix (3x3)
    :param cam_kc: The distortion coefficients (5x1)
    :return: The 3D camera coordinates
    """
    # Extract the valid image point coords, depth values and colors
    cam_image_points, valid_depths, valid_colors = extract_valid_image_points(image_with_drawings, depth_image, depth_scale)

    # Undistort the image points
    undistorted_points = cv2.undistortPoints(cam_image_points, cam_K, cam_kc)

    # Calculate the 3D camera coordinates
    x_c = undistorted_points[:, 0, 0]
    y_c = undistorted_points[:, 0, 1]
    Z_c = valid_depths  # Depth values in meters

    X_c = x_c * Z_c
    Y_c = y_c * Z_c

    # Store each 3D point in the format (X, Y, Z) in a vertical stack by transposing the matrix
    points_cam_3D = np.vstack((X_c, Y_c, Z_c)).T  # (N, 3)

    print(f"3D Camera Points: {points_cam_3D}")
    print(f"Number of 3D Camera Points: {len(points_cam_3D)}")

    return points_cam_3D, valid_colors

def cam_3D_to_tag_3D(points_cam_3D, R_tag, tvec_tag):
    """
    Transform the 3D camera coordinates to the 3D AprilTag coordinates.

    :param points_cam_3D: The 3D camera coordinates
    :param R_ct: The rotation matrix of the AprilTag (3x3)
    :param tvec: The translation vector of the AprilTag (3x1)
    :return: The 3D AprilTag coordinates
    """
    # Convert the 3D camera coordinates from normal cartesian to homogeneous coordinates for the transformation
    points_homogeneous = np.hstack((points_cam_3D, np.ones((points_cam_3D.shape[0], 1))))

    T_cam_to_tag = np.eye(4)
    T_cam_to_tag[:3, :3] = R_tag
    T_cam_to_tag[:3, 3] = tvec_tag.flatten()

    T_tag_to_cam = np.linalg.inv(T_cam_to_tag)

    points_tag_homogeneous = (T_tag_to_cam @ points_homogeneous.T).T

    # (Optional) If needed, convert the homogeneous coordinates back to cartesian coordinates
    points_tag_cartesian = points_tag_homogeneous[:, :3] 

    return points_tag_homogeneous, points_tag_cartesian, T_cam_to_tag

def tag_3D_to_cam_3D(points_tag_3D, T_cam_to_tag):
    """
    Transform the 3D AprilTag coordinates back to 3D camera coordinates.

    :param points_tag_3D: The 3D AprilTag coordinates
    :param T_cam_to_tag: The transformation matrix from the camera to the AprilTag (4x4)
    :return: The 3D camera coordinates
    """
    # Convert the 3D AprilTag coordinates back to 3D camera coordinates (homogeneous)
    points_cam_homogeneous = (T_cam_to_tag @ points_tag_3D.T).T

    # (Optional) If needed, convert the homogeneous coordinates back to cartesian coordinates
    points_cam_cartesian = points_cam_homogeneous[:, :3]

    return points_cam_homogeneous, points_cam_cartesian

def cam_3D_to_proj_3D(points_cam_homogeneous, R_proj, tvec_proj):
    """
    Transform the 3D camera coordinates to the 3D projector coordinates.

    :param points_cam_homogeneous: The 3D camera coordinates (homogeneous)
    :param R_proj: The rotation matrix of the projector (3x3)
    :param tvec_proj: The translation vector of the projector (3x1)
    :return: The 3D projector coordinates
    """
    tvec_proj = tvec_proj.reshape(3, 1) / 1000 # Convert to meters

    # Create the tranformation matrix from the projector to the camera
    T_proj_to_cam = np.eye(4)
    T_proj_to_cam[:3, :3] = R_proj
    T_proj_to_cam[:3, 3] = tvec_proj.flatten()

    # Invert the transformation matrix to get the transformation from the camera to the projector
    T_cam_to_proj = np.linalg.inv(T_proj_to_cam)

    # Convert the 3D camera coordinates to 3D projector coordinates (homogeneous)
    points_proj_homogeneous = (T_cam_to_proj @ points_cam_homogeneous.T).T

    # (Optional) If needed, convert the homogeneous coordinates back to cartesian coordinates
    points_proj_cartesian = points_proj_homogeneous[:, :3]

    return points_proj_homogeneous, points_proj_cartesian, T_cam_to_proj

def proj_3D_to_proj_2D(points_proj_cartesian, proj_K, proj_kc):
    """
    Project the 3D projector coordinates to 2D projector image points.

    :param points_proj_homogeneous: The 3D projector coordinates (homogeneous)
    :param proj_K: The projector matrix (3x3)
    :param proj_kc: The distortion coefficients of the projector (5x1)
    :return: The 2D projector image points
    """
    # Reshape the 3D projector coordinates to (N, 1, 3) for the projection
    points_proj_homogeneous_reshaped = points_proj_cartesian.reshape(-1, 1, 3)

    # Project the 3D projector coordinates to 2D projector image points
    proj_image_points, _ = cv2.projectPoints(points_proj_homogeneous_reshaped, np.zeros((3,)), np.zeros((3,)), proj_K, proj_kc)

    projected_points = proj_image_points.reshape(-1, 2) # (N, 2)

    return projected_points

def filter_valid_proj_image_points(proj_image_points, valid_colors, projector_width, projector_height):
    valid_proj_mask = (proj_image_points[:, 0] >= 0) & (proj_image_points[:, 0] < projector_width) & \
          (proj_image_points[:, 1] >= 0) & (proj_image_points[:, 1] < projector_height)
                
    valid_projected_points = proj_image_points[valid_proj_mask]
    valid_projected_colors = valid_colors[valid_proj_mask]

    u_p = valid_projected_points[:, 0].astype(int)
    v_p = valid_projected_points[:, 1].astype(int)

    return u_p, v_p, valid_projected_colors
    

def main() -> None:
    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, camera_matrix, color_intrinsics, _ = initialize_system()

    # Setup the projector window
    global projector_window_name
    projector_window_name, projector_width, projector_height = setup_projector_window()
    proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
    # draw a red rectangle on the edges of the projector image
    proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 0, 255), 10)

    # Start the thread to update the windows
    window_thread = threading.Thread(target=update_windows)
    window_thread.start()

    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    
    image_with_drawings_path = None
    count = 0
    calibration_data_path = 'C:\\Users\\cenko\\Desktop\\Studium\\FH Aachen\\7. Semester\\Bachelor\\Projektor_Kamera_Kalibrierung\\calibration.yml'

    cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

    print(f"Projector Intrinsics (proj_K):\n{proj_K}")

    try:
        while True:
            success, color_image, color_frame, depth_image, depth_frame, depth_scale = camera.get_frames()
            if not success:
                continue

            gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
            results = apriltag_detector.detect(gray)


            for result in results:
                # Get the distance to the center of the AprilTag
                u_center_of_tag, v_center_of_tag = int(result.center[0]), int(result.center[1])
                depth_to_tag = depth_frame.get_distance(u_center_of_tag, v_center_of_tag)
                # print(f"Depth to AprilTag: {depth_to_tag}m")

                # Rotation vector (Orientation relative to the camera)
                R_ct = result.pose_R

                # Check if camera is too close to the tag
                if depth_to_tag > min_distance:
                    # axis_length = depth_to_tag / 4.0  # May be used to scale the axes according to the distance to the tag

                    # Translation vector (Position relative to the camera) -> calculated with the opencv and the calibration data from
                    # the camera-projector calibration
                    # tvec_realsense = camera.get_3D_camera_coords(u_center_of_tag, v_center_of_tag, depth_to_tag, color_intrinsics["intrinsics_raw"])
                    tvec_opencv = camera.get_3D_camera_coords_opencv(u_center_of_tag, v_center_of_tag, cam_K, cam_kc, depth_frame)

                    # Draw the axes and tag border with ID
                    color_image = draw_axes(color_image, R_ct, tvec_opencv, cam_K, cam_kc, axis_length)

                    if image_with_drawings_path is not None:
                        # Create a new projector image
                        proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)

                        # Load the image with the drawings
                        image_with_drawings = cv2.imread(image_with_drawings_path)

                        ### 1. Transform the 2D camera image points to 3D camera coordinates ###
                        points_cam_3D, valid_colors = cam_2D_to_cam_3D(image_with_drawings, depth_image, depth_scale, cam_K, cam_kc)

                        ### 2. Transform the 3D camera coordinates to the 3D AprilTag coordinates ###
                        points_tag_homogeneous, _, T_cam_to_tag = cam_3D_to_tag_3D(points_cam_3D, R_ct, tvec_opencv)

                        ### 3. Transform the 3D AprilTag coordinates back to 3D camera coordinates ###
                        points_cam_homogeneous, _ = tag_3D_to_cam_3D(points_tag_homogeneous, T_cam_to_tag)
                        
                        ### 4. Transform the 3D camera coordinates to the 3D projector coordinates ###
                        _, points_proj_cartesian, _ = cam_3D_to_proj_3D(points_cam_homogeneous, R, T)

                        ### 5. Project the 3D projector coordinates to 2D projector image points ###
                        proj_image_points = proj_3D_to_proj_2D(points_proj_cartesian, proj_K, proj_kc)

                        print(f"Proj Image Points: {proj_image_points}")
                        print(f"Number of Proj Image Points: {len(proj_image_points)}")


                        ### 6. Filter the valid projected image points ###
                        u_p, v_p, valid_projected_colors = filter_valid_proj_image_points(proj_image_points, valid_colors, projector_width, projector_height)

                        # Draw the transformed image pixels on the projector image
                        proj_image[v_p, u_p] = valid_projected_colors

                else:
                    cv2.putText(color_image, "Too close!, please move away a few cm.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Always draw the tag border and ID
                color_image = draw_tag_border_and_id(color_image, result)
            
            # Display the depth image (optional, for debugging)
            """depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)
            cv2.imshow('Depth Image', depth_colormap)

            smoothed_depth = cv2.GaussianBlur(depth_image, (5, 5), 0)
            depth_colormap_smoothed = cv2.applyColorMap(cv2.convertScaleAbs(smoothed_depth, alpha=0.03), cv2.COLORMAP_JET)
            cv2.imshow('Depth Image smoothed', depth_colormap_smoothed)

            valid_depth = np.where(smoothed_depth > 0, smoothed_depth, 0)
            depth_colormap_valid = cv2.applyColorMap(cv2.convertScaleAbs(valid_depth, alpha=0.03), cv2.COLORMAP_JET)
            cv2.imshow('Depth Image valid', depth_colormap_valid)"""
            

            cv2.imshow("AprilTag Projection Mapping", color_image)
            cv2.imshow(projector_window_name, proj_image)


            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                if results:
                    # Switch border color to green if a tag was detected
                    proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 255, 0), 10)
                     
                    # save the image
                    image_name = os.path.join("data/calibration_images", f"drawing_test_img_{count + 1}.jpg")
                    cv2.imwrite(image_name, color_image)
                    count += 1

                    open_image_in_paint(image_name)

                    image_with_drawings_path = "data/saved_images/test_drawing.jpg"
                else:
                    print("No AprilTag detected, please try again.")

            if key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
