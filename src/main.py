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
    

def main() -> None:
    # Initialize the camera and AprilTag detector
    camera, apriltag_detector, camera_matrix, color_intrinsics, _ = initialize_system()

    # Setup the projector window
    global projector_window_name
    projector_window_name, projector_width, projector_height = setup_projector_window()
    proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
    # draw a red rectangle on the edges of the projector image
    proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 0, 255), 10)
    proj_physical_width = 0.56
    proj_physical_height = 0.32
    s_x = projector_width / proj_physical_width
    s_y = projector_height / proj_physical_height

    # Start the thread to update the windows
    window_thread = threading.Thread(target=update_windows)
    window_thread.start()

    # Length of the axes in the visualization and the minimum distance to the tag in meters
    axis_length = apriltag_detector.tag_size
    min_distance = 0.15
    
    image_with_drawings_path = None
    proj_image_points = None
    valid_colors = None
    count = 0
    calibration_data_path = 'C:\\Users\\cenko\\Desktop\\Studium\\FH Aachen\\7. Semester\\Bachelor\\Projektor_Kamera_Kalibrierung\\calibration.yml'

    cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

    T = T.reshape((3, 1)) / 1000

    M = np.zeros((3, 3))
    M[0, 0] = s_x * R[0, 0]
    M[0, 1] = s_x * R[0, 1]
    M[0, 2] = T[0]
    M[1, 0] = s_y * R[1, 0]
    M[1, 1] = s_y * R[1, 1]
    M[1, 2] = T[1]
    M[2, 0] = R[2, 0]
    M[2, 1] = R[2, 1]
    M[2, 2] = 1

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
                        pass


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
                # if results:
                # Switch border color to green if a tag was detected
                proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 255, 0), 10)
                    
                # save the image
                image_name = os.path.join("data/calibration_images", f"drawing_test_img_{count + 1}.jpg")
                cv2.imwrite(image_name, color_image)
                count += 1

                open_image_in_paint(image_name)

                image_with_drawings_path = "data/saved_images/test_drawing.jpg"

                image_with_drawings = cv2.imread(image_with_drawings_path)

                # image_with_drawings_resized = cv2.resize(image_with_drawings, (projector_width, projector_height))

                proj_image = cv2.warpPerspective(image_with_drawings, M, (projector_width, projector_height))


                # else:
                    # print("No AprilTag detected, please try again.")

            if key == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 
