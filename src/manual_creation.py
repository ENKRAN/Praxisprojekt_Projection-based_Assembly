import os
import json
from datetime import datetime
import cv2
from .visualization import draw_axes, draw_tag_border_and_id
from .projection import project_image
from .utils import open_image_in_paint
from .image_processing import save_component_img, cam_2D_to_tag_3D
from typing import Tuple

class ManualCreater:
    def __init__(self, base_image_dir="data/saved_images/raw_images", base_instruction_dir="data/saved_images/drawings"):
        self.tag_id = None
        self.steps = []
        self.base_image_dir = base_image_dir
        self.base_instruction_dir = base_instruction_dir
        os.makedirs(self.base_image_dir, exist_ok=True)
        os.makedirs(self.base_instruction_dir, exist_ok=True)

    def capture_photo(self, img, step_number) -> Tuple[str, str]:
        """
        Capture a photo and save it to disk.

        :param img: The image to save
        :param step_number: The step number
        :return: The path to the saved image and the filename
        """    
        filename = f"raw_image_{self.tag_id}_step{step_number:03}.png"

        # Full path to the file
        photo_path = os.path.join(self.base_image_dir, filename)

        # Save the image to disk
        cv2.imwrite(photo_path, img)
        print(f"Image saved at: {photo_path}")

        return photo_path, filename

    def create_step(self, step_number, drawing_path):
        # Schritt speichern
        self.steps.append({
            "step": step_number,
            "drawing_path": drawing_path,
        })
        print(f"Step {step_number} saved.")

    def save_manual(self):
        # Schritt 5: Speichere die gesamte Anleitung
        manual_data = {
            "tag_id": self.tag_id,
            "steps": self.steps,
            "created_at": datetime.now().isoformat()
        }
        json_path = os.path.join(self.base_instruction_dir, f"instruction_{self.tag_id}.json")

        with open(json_path, "w") as file:
            json.dump(manual_data, file, indent=4)
        print(f"Anleitung für Tag-ID {self.tag_id} gespeichert: {json_path}")

    def create_manual(self, camera, apriltag_detector, min_distance, cam_K, cam_kc, axis_length, R, T, proj_K, proj_kc, projector_width, projector_height, projector_window_name, proj_image):
        print(f"Beginning manual creation for tag ID {self.tag_id}.")
        step_number = 1
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
                        self.tag_id = results[0].tag_id

                        print(f"Creating step {step_number} for AprilTag ID {self.tag_id}.")
                            
                        # 1. Capture the photo
                        image_path, _ = self.capture_photo(color_image, step_number)

                         # 2. Define the temporary path and open the image in MS Paint
                        temp_drawing_path = f"{self.base_instruction_dir}/temp_drawing.jpg"
                        os.rename(image_path, temp_drawing_path)  # Rename to a temporary name
                        open_image_in_paint(temp_drawing_path)

                        # 3. Wait for the user to save the file in Paint
                        print("Please edit and save the file in Paint. Press Enter when done.")
                        input("")

                        # path to the image with drawings
                        image_with_drawings_path = f"{self.base_instruction_dir}/instruction_{self.tag_id}_step_{step_number:03}.jpg"

                        # 5. Check if the temporary file exists and rename it
                        if not os.path.exists(temp_drawing_path):
                            print("The edited file was not saved or Paint is still open. Please save the file and try again.")
                            continue

                        try:
                            os.rename(temp_drawing_path, image_with_drawings_path)
                            print(f"File saved as {image_with_drawings_path}.")
                        except OSError as e:
                            print(f"Error renaming the file: {e}")
                            continue

                        # Calculate the 3D points relative to the AprilTag and the corresponding colors
                        points_3D_tag, valid_colors = cam_2D_to_tag_3D(image_with_drawings_path, depth_image, depth_scale, cam_K, cam_kc, (R_ct, tvec_opencv))

                        if points_3D_tag is not None and valid_colors is not None:
                            extracted_3D_pixels = True
                            print(f"3D Points relative to the AprilTag: {len(points_3D_tag)}")
                        else:
                            print("Error in 3D point extraction. Please check the image and parameters.")
                            continue
                    else:
                        print("No AprilTag detected, please try again.")
                if key == ord('s'):
                    confirm = input(f"Are you sure you want to save the instruction step {step_number:03} for the AprilTag ID {self.tag_id}? (y/n): ").lower()

                    if confirm == "y":
                        self.create_step(step_number)
                        step_number += 1
                    else:
                        print("Step not saved.")
                        continue

                if key == ord('q'):
                    break
        finally:
            self.save_manual()
            print("Manual creation finished.")

            camera.stop()
            cv2.destroyAllWindows()

