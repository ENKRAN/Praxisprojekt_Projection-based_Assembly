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
        if cv2.getWindowProperty('Test photo', cv2.WND_PROP_VISIBLE) < 1 and \
           cv2.getWindowProperty(projector_window_name, cv2.WND_PROP_VISIBLE) < 1:
             break
        cv2.waitKey(1)
        time.sleep(0.01)

def select_point(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        param['point'] = (x, y)
        cv2.destroyWindow('drawing_test')

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
    
    # Laden der Kalibrierungsdaten
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

    count = 0
    try:
        while True:
            color_image, depth_image, depth_frame, depth_scale, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue

            proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)

            cv2.imshow("Test photo", color_image)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                # Compare intrinsics
                print("Camera intrinsics (RealSense): ", color_intrinsics['intrinsics_raw'])
                print("Camera distortion coefficients (RealSense): ", color_intrinsics['dist_coeffs'])
                print("Camera intrinsics (Calibration): ", cam_K)
                print("Camera distortion coefficients (Calibration): ", cam_kc)

                # save the image
                image_name = os.path.join("data/calibration_images", f"drawing_test_img_{count + 1}.jpg")
                cv2.imwrite(image_name, color_image)
                count += 1

                open_image_in_paint(image_name)

                image_with_drawings = cv2.imread("data/saved_images/test_drawing.jpg")

                if image_with_drawings is None:
                    print("No image found.")
                    continue
                    
                # Extract all non-black pixels
                non_black_mask = np.any(image_with_drawings != [0, 0, 0], axis=-1)                
                
                # Get the coordinates and colors of the non-black pixels
                non_black_coords = np.column_stack(np.nonzero(non_black_mask))
                non_black_colors = image_with_drawings[non_black_mask]

                depth_image = depth_image * depth_scale

                # Get the depth values of the non-black pixels
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

                rvec, _ = cv2.Rodrigues(R)
                T = T.reshape(3, 1) / 1000  # Umrechnung in Meter, falls erforderlich

                object_points = point_cam_3D.reshape(-1, 1, 3)

                image_points_proj, _ = cv2.projectPoints(object_points, rvec, T, proj_K, proj_kc)

                projected_points = image_points_proj.reshape(-1, 2)

                valid_proj_mask = (projected_points[:, 0] >= 0) & (projected_points[:, 0] < projector_width) & (projected_points[:, 1] >= 0) & (projected_points[:, 1] < projector_height)
                
                valid_projected_points = projected_points[valid_proj_mask]
                valid_projected_colors = valid_colors[valid_proj_mask]

                u_p = valid_projected_points[:, 0].astype(int)
                v_p = valid_projected_points[:, 1].astype(int)

                within_bounds_mask = (u_p >= 0) & (u_p < projector_width) & (v_p >= 0) & (v_p < projector_height)
                u_p = u_p[within_bounds_mask]
                v_p = v_p[within_bounds_mask]
                valid_projected_colors = valid_projected_colors[within_bounds_mask]

                proj_image[v_p, u_p] = valid_projected_colors

                cv2.imshow(projector_window_name, proj_image)

                """drawing_img = cv2.imread(image_name)
                params = {}
                cv2.namedWindow('drawing_test')
                cv2.setMouseCallback('drawing_test', select_point, params)
                cv2.imshow('drawing_test', drawing_img)
                
                while True:
                    cv2.waitKey(1)
                    if 'point' in params:
                        break
                    
                if 'point' not in params:
                    print("No point selected.")
                    exit()

                u = params['point'][0]
                v = params['point'][1]
                cv2.circle(color_image, (u, v), 5, (0, 0, 255), -1)
                print("Selected point: ", u, v)

                Z_c = depth_frame.get_distance(u, v)
                print("Image point z: ", Z_c)

                # Prepare R and T for the projection
                rvec, _ = cv2.Rodrigues(R)
                T = T.reshape(3, 1) / 1000


                print("Translation vector (meter): ", T)


                image_point = np.array([[u, v]], dtype=np.float32)
                undistorted = cv2.undistortPoints(image_point, cam_K, cam_kc)
                x_c = undistorted[0][0][0]
                y_c = undistorted[0][0][1]

                print("undistorted image point in camera coordinates (pixels): ", x_c, y_c)

                X_c = x_c * Z_c
                Y_c = y_c * Z_c
                Z_c = Z_c
                point_cam_3D = np.array([[X_c], [Y_c], [Z_c]])
                print("Image point in camera coordinates (meters): ", point_cam_3D)
                
                # Vorbereitung für die Projektion
                object_points = point_cam_3D.T  # Form (1, 3)
                object_points = object_points.reshape(-1, 1, 3)  # Form (N, 1, 3)

                # Projektion auf die Projektorbildebene
                image_points, _ = cv2.projectPoints(object_points, rvec, T, proj_K, proj_kc)

                # scale_x = projector_width / 1920
                # scale_y = projector_height / 1080

                u_p = image_points[0][0][0]
                v_p = image_points[0][0][1]

                # u_p = u_p * scale_x
                # v_p = v_p * scale_y

                point_proj_2D = (int(u_p), int(v_p))
                print("Image point in projector coordinates (2D): ", point_proj_2D)

                cv2.circle(proj_image, point_proj_2D, 5, (0, 0, 255), -1)

                cv2.imshow(projector_window_name, proj_image)"""

            elif key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
    
    """print("Camera matrix: ", cam_K)
    print("Camera distortion coefficients: ", cam_kc)
    print("Projector matrix: ", proj_K)
    print("Projector distortion coefficients: ", proj_kc)
    print("Rotation matrix: ", R)
    print("Translation matrix: ", T)"""

    """try:
        while True:
            # Get the frames from the camera
            color_image, depth_image, depth_frame, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue

            # Display on the projector
            cv2.imshow(projector_window_name, chessboard_img)

            # Display the image with the AprilTag detection
            cv2.imshow('AprilTag Detection', color_image)
            
            obj_points, img_points, proj_img_points = analyze_chessboard_pattern(0.05, 80, color_image, color_intrinsics['intrinsics_raw'], depth_frame)

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
                        print("No 3D drawings found.")
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
        cv2.destroyAllWindows()"""

if __name__ == "__main__":
    main() 
