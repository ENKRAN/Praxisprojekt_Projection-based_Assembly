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
import open3d as o3d

def update_windows() -> None:
    while True:
        if cv2.getWindowProperty('Test photo', cv2.WND_PROP_VISIBLE) < 1 and \
           cv2.getWindowProperty(projector_window_name, cv2.WND_PROP_VISIBLE) < 1:
             break
        cv2.waitKey(1)
        time.sleep(0.01)

def main() -> None:
    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, camera_matrix, color_intrinsics, _ = initialize_system()

    # Setup the projector window
    global projector_window_name
    projector_window_name, projector_width, projector_height = setup_projector_window()
    proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)

    # Start the thread to update the windows
    window_thread = threading.Thread(target=update_windows)
    window_thread.start()

    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    
    calibration_data_path = 'C:\\Users\\cenko\\Desktop\\Studium\\FH Aachen\\7. Semester\\Bachelor\\Projektor_Kamera_Kalibrierung\\calibration.yml'

    # Laden der Kalibrierungsdaten
    cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

    count = 0
    try:
        while True:
            color_image, depth_image, depth_frame, depth_scale, _ = camera.get_frames()
            if color_image is None or depth_image is None or depth_frame is None:
                continue

            cv2.imshow("Test photo", color_image)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                """# 1. Take a photo of the camera image
                image_name = os.path.join("data/calibration_images", f"drawing_test_img_{count + 1}.jpg")
                cv2.imwrite(image_name, color_image)
                count += 1
                
                # 2. Open the image in Paint, draw something and save the image with the drawings and a black background
                open_image_in_paint(image_name)

                # 3. Load the image with the drawings
                image_with_drawings = cv2.imread("data/saved_images/test_drawing.jpg")
                if image_with_drawings is None:
                    print("No image found.")
                    continue
                    
                # 4. Extract all non-black pixels
                non_black_mask = np.any(image_with_drawings != [0, 0, 0], axis=-1)                
                
                # Get the coordinates and colors of the non-black pixels
                non_black_coords = np.column_stack(np.nonzero(non_black_mask))
                non_black_colors = image_with_drawings[non_black_mask]
                
                # 5. Scale the depth_image and extract the depth values of the non-black pixels
                depth_image = depth_image * depth_scale
                depth_values = depth_image[non_black_coords[:, 0], non_black_coords[:, 1]]

                # 6. Filter out the invalid depth values and save the valid coordinates, colors and depths
                valid_depth_mask = (depth_values > 0) & (~np.isnan(depth_values))
                valid_coords = non_black_coords[valid_depth_mask]
                valid_colors = non_black_colors[valid_depth_mask]
                valid_depths = depth_values[valid_depth_mask]

                # 7. Get the valid 2D camera image points and undistort them
                image_points = valid_coords[:, [1, 0]].astype(np.float32).reshape(-1, 1, 2)  # (u, v)
                undistorted_points = cv2.undistortPoints(image_points, cam_K, cam_kc)

                x_c = undistorted_points[:, 0, 0]
                y_c = undistorted_points[:, 0, 1]
                Z_c = valid_depths  # Depth values in meters

                # 8. Transform the 2D camera image points to 3D camera coordinates
                X_c = x_c * Z_c
                Y_c = y_c * Z_c
                points_cam_3D = np.vstack((X_c, Y_c, Z_c)).T  # Form: (N, 3)

                # 9. Prepare the rotation matrix and translation vector for the projection
                rvec, _ = cv2.Rodrigues(R)
                T = T.reshape(3, 1) / 1000 # Convert to meters

                # 10. Project the 3D camera coordinates to the 2D projector image
                object_points = points_cam_3D.reshape(-1, 1, 3) # Form: (N, 1, 3)
                image_points_proj, _ = cv2.projectPoints(object_points, rvec, T, proj_K, proj_kc)

                # 11. Filter out the projected points that are outside the projector image
                projected_points = image_points_proj.reshape(-1, 2)

                valid_proj_mask = (projected_points[:, 0] >= 0) & (projected_points[:, 0] < projector_width) & \
                                    (projected_points[:, 1] >= 0) & (projected_points[:, 1] < projector_height)
                valid_projected_points = projected_points[valid_proj_mask]
                valid_projected_colors = valid_colors[valid_proj_mask]

                # 12. Convert the projected points to integer values
                u_p = valid_projected_points[:, 0].astype(int)
                v_p = valid_projected_points[:, 1].astype(int)

                # 13. Create the projector image and display it
                proj_image[v_p, u_p] = valid_projected_colors

                cv2.imshow(projector_window_name, proj_image)"""

                """### 1. Take a photo of the camera image ###
                image_name = os.path.join("data/calibration_images", f"drawing_test_img_{count + 1}.jpg")
                cv2.imwrite(image_name, color_image)
                count += 1
                
                ### 2. Open the image in Paint, draw something and save the image with the drawings and a black background ###
                open_image_in_paint(image_name)

                ### 3. Load the image with the drawings ###
                image_with_drawings = cv2.imread("data/saved_images/test_drawing.jpg")
                if image_with_drawings is None:
                    print("No image found.")
                    continue

                ### 4. Create a point cloud and a mesh ###
                # Get the depth values and the corresponding image coordinates
                height, width = depth_image.shape
                u_coords, v_coords = np.meshgrid(np.arange(width), np.arange(height))
                u_coords = u_coords.flatten()
                v_coords = v_coords.flatten()
                depth_values = depth_image.flatten()

                # Filter out the invalid depth values 
                valid_mask = depth_values > min_distance
                u_coords = u_coords[valid_mask]
                v_coords = v_coords[valid_mask]
                depth_values = depth_values[valid_mask]

                # Undistort the image points and calculate the 3D camera coordinates for the point cloud
                image_points = np.vstack((u_coords, v_coords)).T.astype(np.float32)
                undistorted_points = cv2.undistortPoints(image_points.reshape(-1, 1, 2), cam_K, cam_kc)
                x_c = undistorted_points[:, 0, 0]
                y_c = undistorted_points[:, 0, 1]
                Z_c = depth_values

                X_c = x_c * Z_c
                Y_c = y_c * Z_c
                point_cloud_cam = np.vstack((X_c, Y_c, Z_c)).T  # Form: (N, 3)

                # Create a Open3D point cloud object
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(point_cloud_cam)

                # Estimate the normals for the point cloud (optional, but may be needed for some algorithms)
                pcd.estimate_normals()

                # Create a mesh from the point cloud (Poisson reconstruction)
                mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=8)

                ### 5. Mapping the drawing to the mesh ###
                # Extract the vertices
                vertices = np.asarray(mesh.vertices)
                points_3D = vertices.reshape(-1, 3)

                # Project the 3D vertices points to the 2D camera image
                image_points, _ = cv2.projectPoints(points_3D, np.zeros(3), np.zeros(3), cam_K, cam_kc)
                image_points = image_points.reshape(-1, 2)

                # Normalize the image points to convert them to texture coordinates
                u = image_points[:, 0] / image_with_drawings.shape[1]
                v = image_points[:, 1] / image_with_drawings.shape[0]

                # Assign the texture to the mesh
                mesh.textures = [o3d.geometry.Image(cv2.cvtColor(image_with_drawings, cv2.COLOR_BGR2RGB))]
                mesh.triangle_uvs = o3d.utility.Vector2dVector(np.vstack((u, v)).T)
                mesh.triangle_material_ids = np.zeros(len(mesh.triangles))

                ### 6. Render from the projector's perspective ###
                # Get the intrinsic parameters of the projector
                fx_p, fy_p = proj_K[0, 0], proj_K[1, 1]
                cx_p, cy_p = proj_K[0, 2], proj_K[1, 2]
                width_p, height_p = projector_width, projector_height

                # Create a PinholeCameraIntrinsic object for the projector
                projector_intrinsic = o3d.camera.PinholeCameraIntrinsic(width_p, height_p, fx_p, fy_p, cx_p, cy_p)

                # Extrinsische Parameter (Transformation von der Kamera zum Projektor)
                # R_inv = R.T
                # T_inv = -R_inv @ T.reshape(3, 1)

                # Extrinsic parameters (Transformation from the camera to the projector)
                extrinsic = np.eye(4)
                extrinsic[:3, :3] = R
                extrinsic[:3, 3] = T.flatten()

                # Create an OffscreenRenderer object
                render = o3d.visualization.rendering.OffscreenRenderer(width_p, height_p)
                render.scene.set_background([0, 0, 0, 1])  # Set the background color to black

                # Add the mesh to the scene
                material = o3d.visualization.rendering.MaterialRecord()
                material.shader = "defaultLit"
                render.scene.add_geometry("mesh", mesh, material)

                # Setup the camera (projector) for rendering
                render.setup_camera(projector_intrinsic, extrinsic)

                # Render the scene and get the image
                proj_image = render.render_to_image()
                proj_image = np.asarray(proj_image)

                ### 7. Display the image on the projector ###
                cv2.imshow(projector_window_name, proj_image)"""

            elif key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

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
