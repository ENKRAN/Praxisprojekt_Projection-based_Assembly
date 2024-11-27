import numpy as np
import cv2
import time
import threading
from .image_processing import save_component_img
from .setup import initialize_system
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


def cam_2D_to_cam_3D(image_with_drawings, depth_image, depth_scale, cam_K, cam_kc):
    # Extract all non-black pixels
    non_black_mask = np.any(image_with_drawings != [0, 0, 0], axis=-1)                
    
    # Get the coordinates and colors of the non-black pixels
    non_black_coords = np.column_stack(np.nonzero(non_black_mask))
    non_black_colors = image_with_drawings[non_black_mask]

    # Get the depth values of the non-black pixels
    depth_image = depth_image * depth_scale
    depth_values = depth_image[non_black_coords[:, 0], non_black_coords[:, 1]]

    # Filter out the invalid depth values
    valid_depth_mask = (depth_values > 0) & (~np.isnan(depth_values))

    # Save the valid coordinates, colors and depth values
    valid_coords = non_black_coords[valid_depth_mask]
    valid_colors = non_black_colors[valid_depth_mask]
    valid_depths = depth_values[valid_depth_mask]

    image_points = valid_coords[:, [1, 0]].astype(np.float32).reshape(-1, 1, 2)  # (u, v)

    undistorted_points = cv2.undistortPoints(image_points, cam_K, cam_kc)

    x_c = undistorted_points[:, 0, 0]
    y_c = undistorted_points[:, 0, 1]
    Z_c = valid_depths  # Tiefenwerte in Meter

    X_c = x_c * Z_c
    Y_c = y_c * Z_c
    point_cam_3D = np.vstack((X_c, Y_c, Z_c)).T  # Form: (N, 3)

    return point_cam_3D, valid_colors

def cam_3D_to_tag_3D(R_ct, tvec_realsense, R, T, point_cam_3D):
    # Transform 3D Points (cam coords) to 3D Points (Apriltag coords)
    # Inverse of the rotation matrix
    rmat_tag = np.array(R_ct)
    R_cam_to_tag = rmat_tag.T

    # Inverse of the translation vector
    tvec_tag = np.array(tvec_realsense)
    T_cam_to_tag = -R_cam_to_tag @ tvec_tag.reshape(3, 1)  # (3,1)

    # Transform the 3D points from camera to tag coordinates
    points_tag = (R_cam_to_tag @ point_cam_3D.T) + T_cam_to_tag  # (3, N)
    points_tag = points_tag.T  # (N, 3)

    return points_tag

def tag_3D_to_proj_3D(R, T, points_tag):
    # Transform 3D Points (Apriltag coords) to 3D Points (Projektor coords)
    points_proj = (R @ points_tag.T) + (T.reshape(3, 1) / 1000)  # (3, N)
    points_proj = points_proj.T  # (N, 3)

    return points_proj

def tag_3D_to_proj_2D(points_proj, proj_K, proj_kc, projector_width, projector_height, proj_image, valid_colors):                    
    # Reshape the points for the projection
    points_proj_reshaped = points_proj.reshape(-1, 1, 3)

    image_points_proj, _ = cv2.projectPoints(points_proj_reshaped, np.zeros((3, 1)), np.zeros((3, 1)), proj_K, proj_kc)

    projected_points = image_points_proj.reshape(-1, 2)

    valid_proj_mask = (projected_points[:, 0] >= 0) & (projected_points[:, 0] < projector_width) & (projected_points[:, 1] >= 0) & (projected_points[:, 1] < projector_height)
    
    valid_projected_points = projected_points[valid_proj_mask]
    valid_projected_colors = valid_colors[valid_proj_mask]

    u_p = valid_projected_points[:, 0].astype(int)
    v_p = valid_projected_points[:, 1].astype(int)

    proj_image[v_p, u_p] = valid_projected_colors

    return proj_image


def main() -> None:
    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, camera_matrix, color_intrinsics, _ = initialize_system()

    # Setup the projector window
    global projector_window_name
    projector_window_name, projector_width, projector_height = setup_projector_window()

    # Start the thread to update the windows
    # window_thread = threading.Thread(target=update_windows)
    # window_thread.start()

    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    
    """# Laden der Kalibrierungsdaten
    fs = cv2.FileStorage('C:\\Users\\cenko\\Desktop\\Studium\\FH Aachen\\7. Semester\\Bachelor\\Projektor_Kamera_Kalibrierung\\calibration.yml', cv2.FILE_STORAGE_READ)

    # Kameraparameter
    cam_K = fs.getNode('camK').mat()
    cam_kc = fs.getNode('camKc').mat()

    # Projektorparameter
    proj_K = fs.getNode('prjK').mat()
    proj_kc = fs.getNode('prjKc').mat()

    # Rotations- und Translationsvektoren
    R = fs.getNode('R').mat()
    T = fs.getNode('T').mat()

    fs.release()

    # Überprüfen, ob die Kalibrierungsdaten geladen wurden
    if cam_K is None or cam_kc is None or proj_K is None or proj_kc is None or R is None or T is None:
        print('Kalibrierungsdaten konnten nicht geladen werden.')
        exit()

    image_with_drawings_path = None
    proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
    count = 0
    try:
        while True:
            color_image, depth_image, depth_frame, depth_scale, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue


            cv2.imshow("AprilTag Projection Mapping", color_image)

            # cv2.imshow(projector_window_name, proj_image)

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

                    # Translation vector (Position relative to the camera) -> calculated with the RealSense camera
                    tvec_realsense = camera.get_3D_camera_coords(u_center_of_tag, v_center_of_tag, depth_to_tag, color_intrinsics["intrinsics_raw"])

                    # Draw the axes and tag border with ID
                    color_image = draw_axes(color_image, R_ct, tvec_realsense, camera_matrix, color_intrinsics["dist_coeffs"], axis_length)

                    if image_with_drawings_path is not None:
                        print("Drawing image found.")

                        image_with_drawings = cv2.imread(image_with_drawings_path)

                        point_cam_3D, valid_colors = cam_2D_to_cam_3D(image_with_drawings, depth_image, depth_scale, cam_K, cam_kc) 
                        
                        points_tag = cam_3D_to_tag_3D(R_ct, tvec_realsense, R, T, point_cam_3D)

                        points_proj = tag_3D_to_proj_3D(R, T, points_tag)

                        proj_image = tag_3D_to_proj_2D(points_proj, proj_K, proj_kc, projector_width, projector_height, proj_image, valid_colors)

                        cv2.imshow(projector_window_name, proj_image)
                else:
                    cv2.putText(color_image, "Too close!, please move away a few cm.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Always draw the tag border and ID
                color_image = draw_tag_border_and_id(color_image, result)


            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                # Compare intrinsics
                # print("Camera intrinsics (RealSense): ", color_intrinsics['intrinsics_raw'])
                # print("Camera distortion coefficients (RealSense): ", color_intrinsics['dist_coeffs'])
                # print("Camera intrinsics (Calibration): ", cam_K)
                # print("Camera distortion coefficients (Calibration): ", cam_kc)

                # save the image
                image_name = os.path.join("data/calibration_images", f"drawing_test_img_{count + 1}.jpg")
                cv2.imwrite(image_name, color_image)
                count += 1

                open_image_in_paint(image_name)

                image_with_drawings_path = "data/saved_images/test_drawing.jpg"

            if key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()"""

    try:
        while True:
            # Get the frames from the camera
            color_image, depth_image, depth_frame, _, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue

            # Display the image with the AprilTag detection
            cv2.imshow('AprilTag Detection', color_image)            

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

                    
                else:
                    cv2.putText(color_image, "Too close!, please move away a few cm.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Always draw the tag border and ID
                # color_image = draw_tag_border_and_id(color_image, result)


            # Wait for a key press
            key = cv2.waitKey(1) & 0xFF

            # Save the image of the component if a tag was detected and open it for editing
            if key == ord(' '):
                saved_image_path, saved_filename = save_component_img(color_image, count)
                count += 1

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
