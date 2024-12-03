import numpy as np
import cv2
import threading
from .image_processing import save_component_img, cam_2D_to_tag_3D
from .setup import initialize_system, get_calibration_data, update_windows
from .projection import setup_projector_window, project_image
from .utils import open_image_in_paint, show_depth_image
from .visualization import draw_axes, draw_tag_border_and_id


def main() -> None:
    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, camera_matrix, color_intrinsics, _ = initialize_system()

    # Setup the projector window
    global projector_window_name
    projector_window_name, projector_width, projector_height = setup_projector_window()

    # draw a red rectangle on the edges of the projector image
    proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
    proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 0, 255), 10)

    # Start the thread to update the windows
    window_thread = threading.Thread(
        target=update_windows,
        args=(projector_window_name)
    )
    window_thread.start()

    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    
    calibration_data_path = 'C:\\Users\\cenko\\Desktop\\Studium\\FH Aachen\\7. Semester\\Bachelor\\Projektor_Kamera_Kalibrierung\\calibration.yml'
    cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

    extracted_3D_pixels = False

    try:
        while True:
            success, color_image, _, depth_image, depth_frame, depth_scale = camera.get_frames()
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
                    
                    # If the user has drawn on the image, transform the 2D image points to 3D tag coordinates and project them
                    if extracted_3D_pixels:
                        proj_image = project_image(
                            proj_image, 
                            points_3D_tag,
                            valid_colors, 
                            R, 
                            T, 
                            R_ct, 
                            tvec_opencv, 
                            proj_K, 
                            proj_kc,
                            projector_width,
                            projector_height
                        )

                else:
                    cv2.putText(color_image, "Too close!, please move away a few cm.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # Always draw the tag border and ID
                color_image = draw_tag_border_and_id(color_image, result)
            
            # Display the depth image (optional, for debugging)
            # show_depth_image(depth_image)

            # Display the images
            cv2.imshow("AprilTag Projection Mapping", color_image)
            cv2.imshow(projector_window_name, proj_image)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                if results:
                    # Switch border color to green if a tag was detected
                    # proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 255, 0), 10)
                     
                    # save the image
                    image_path, _ = save_component_img(color_image)

                    # open the image in MS Paint
                    open_image_in_paint(image_path)

                    # path to the image with drawings
                    image_with_drawings_path = "data/saved_images/drawing.jpg"

                    # Calculate the 3D points relative to the AprilTag and the corresponding colors
                    points_3D_tag, valid_colors = cam_2D_to_tag_3D(image_with_drawings_path, depth_image, depth_scale, cam_K, cam_kc, (R_ct, tvec_opencv))

                    if points_3D_tag is not None and valid_colors is not None:
                        extracted_3D_pixels = True
                        print(f"3D Points relative to the AprilTag: {len(points_3D_tag)}")
                    else:
                        print("No 3D points found")
                else:
                    print("No AprilTag detected, please try again.")

            if key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
