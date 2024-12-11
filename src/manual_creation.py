import os
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

# Local imports
from .visualization import draw_axes, draw_tag_border_and_id
from .projection import project_image
from .utils import open_image_in_paint
from .image_processing import cam_2D_to_tag_3D

KEY_CAPTURE = ord(' ')
KEY_SAVE_STEP = ord('s')
KEY_SAVE_MANUAL = ord('m')
KEY_UNDO_STEP = ord('u')

class ManualCreator:
    def __init__(self, base_manuals_dir="data/manuals", raw_images_dir="raw_images", instructions_dir="instructions") -> None:
        """
        Initializes the ManualCreator object.

        :param base_manuals_dir: The base directory where the manuals will be saved.
        :param raw_images_dir: The directory where the raw images will be saved.
        :param instructions_dir: The directory where the instructions will be saved.
        """
        self.manual_count = 0
        self.tag_id = None
        self.step_number = 1
        self.steps = []
        self.base_manuals_dir = Path(base_manuals_dir)
        self.current_manual_dir = self.base_manuals_dir / f"manual_{self.manual_count}"
        self.raw_images_dir = self.current_manual_dir / raw_images_dir
        self.instructions_dir = self.current_manual_dir / instructions_dir

        # Create the directories if they don't exist
        try:
            self.current_manual_dir.mkdir(parents=True, exist_ok=True)
            self.raw_images_dir.mkdir(parents=True, exist_ok=True)
            self.instructions_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating directories: {e}")
            raise

    def capture_photo(self, img) -> Tuple[str, str]:
        """
        Captures a photo and saves it in the raw images directory.

        :param img: The image to save.
        :return: The path to the saved image and the filename
        """
        filename = f"raw_image_{self.tag_id}_step_{self.step_number:03}.png"
        photo_path = self.raw_images_dir / filename
        cv2.imwrite(str(photo_path), img)
        print(f"Image saved at: {photo_path}")

        return str(photo_path), filename

    def reset_manual_creator(self, projector_width, projector_height) -> None:
        """
        Resets the manual creator by creating a new directory for the new manual.
        """
        self.manual_count += 1
        self.current_manual_dir = self.base_manuals_dir / f"manual_{self.manual_count}"
        self.raw_images_dir = self.current_manual_dir / self.raw_images_dir.name
        self.instructions_dir = self.current_manual_dir / self.instructions_dir.name

        try:
            self.current_manual_dir.mkdir(parents=True, exist_ok=True)
            self.raw_images_dir.mkdir(parents=True, exist_ok=True)
            self.instructions_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"Error creating directories: {e}")
            raise

        self.tag_id = None
        self.steps.clear()
        self.step_number = 1

        proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
        proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 0, 255), 10)

        print("Everything has been reset.")
        print(f"Current manual directory: {self.current_manual_dir}")

    def create_step(self, drawing_path) -> None:
        """
        Creates a step with the drawing path.

        :param drawing_path: The path to the drawing image.
        """
        drawing_path = str(Path(drawing_path).as_posix())
        self.steps.append({
            "step": self.step_number,
            "drawing_path": drawing_path,
        })
        print(f"Step {self.step_number} saved.")

    def undo_last_step(self):
        if self.steps:
            removed_step = self.steps.pop()
            self.step_number -= 1
            print(f"Removed step {removed_step['step']}.")
        else:
            print("No steps to undo.")

    def save_manual(self) -> None:
        """
        Saves the manual as a JSON file
        """
        if self.tag_id is None:
            print("No tag ID found, manual not saved.")
            return

        manual_data = {
            "tag_id": self.tag_id,
            "steps": self.steps,
            "created_at": datetime.now().isoformat()
        }
        json_path = self.current_manual_dir / f"manual_{self.manual_count}.json"

        try:
            with open(json_path, "w") as file:
                json.dump(manual_data, file, indent=4)
            print(f"Manual saved at {json_path} for AprilTag ID {self.tag_id}.")
        except Exception as e:
            print(f"Error saving manual: {e}")

    def create_manual(self, camera, apriltag_detector, min_distance, cam_K, cam_kc, axis_length, R, T, \
                       proj_K, proj_kc, projector_width, projector_height, projector_window_name, proj_image) -> None:
        """
        Creates a manual by capturing images, drawing on them, and saving the steps.

        :param camera: The camera object.
        :param apriltag_detector: The AprilTag detector object.
        :param min_distance: The minimum distance to the tag in meters.
        :param cam_K: The intrinsic camera matrix.
        :param cam_kc: The camera distortion coefficients.
        :param axis_length: The length of the axes in the visualization.
        :param R: The rotation matrix from the projector to the camera.
        :param T: The translation vector from the projector to the camera.
        :param proj_K: The intrinsic projector matrix.
        :param proj_kc: The projector distortion coefficients.
        :param projector_width: The width of the projector image.
        :param projector_height: The height of the projector image.
        :param projector_window_name: The name of the projector window.
        :param proj_image: The projector image.
        """
        print(f"Beginning manual creation...")
        step_saved = False
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
                        if extracted_3D_pixels and not step_saved:
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

                if key == KEY_CAPTURE:
                    if results:
                        self.tag_id = results[0].tag_id

                        print(f"Creating step {self.step_number} for AprilTag ID {self.tag_id}.")

                        step_saved = False
                            
                        # 1. Capture the photo
                        image_path, _ = self.capture_photo(color_image)

                         # 2. Open the image in Paint
                        open_image_in_paint(image_path)

                        # 3. Get the path to the image with the drawings
                        instructions = [self.instructions_dir / datei for datei in os.listdir(self.instructions_dir) if datei.lower().endswith(".png")]
                        if not instructions:
                            print("No images with drawings found.")
                        else:
                            # Get the newest instruction
                            newest_instruction = max(instructions, key=lambda p: p.stat().st_mtime)     

                            # Prepare the new path
                            new_name = f"instruction_{self.tag_id}_step_{self.step_number:03}.png"
                            image_with_drawings_path = self.instructions_dir / new_name
                            
                            # Rename the image
                            newest_instruction.rename(image_with_drawings_path)
                            print(f"The image with the drawings has been renamed to: {image_with_drawings_path}")

                        # Calculate the 3D points relative to the AprilTag and the corresponding colors
                        points_3D_tag, _, valid_colors = cam_2D_to_tag_3D(image_with_drawings_path, depth_image, depth_scale, cam_K, (R_ct, tvec_opencv))

                        if points_3D_tag is not None and valid_colors is not None:
                            extracted_3D_pixels = True
                            print(f"3D Points relative to the AprilTag: {len(points_3D_tag)}")
                        else:
                            print("Error in 3D point extraction. Please check the image and parameters.")
                            continue
                    else:
                        print("No AprilTag detected, please try again.")
                if key == KEY_SAVE_STEP:

                    confirm = input(f"Are you sure you want to save the instruction step {self.step_number:03} for the AprilTag ID {self.tag_id}? (y/n): ").lower()

                    if confirm == "y":
                        step_saved = True

                        self.create_step(image_with_drawings_path)
                        self.step_number += 1
                        
                        proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
                        proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 0, 255), 10)
                    else:
                        print("Step not saved.")
                        step_saved = False
                        proj_image = np.zeros((projector_height, projector_width, 3), dtype=np.uint8)
                        proj_image = cv2.rectangle(proj_image, (0, 0), (projector_width - 1, projector_height - 1), (0, 0, 255), 10)

                if key == KEY_UNDO_STEP:

                    confirm = input(f"Are you sure you want to undo the last step? (y/n): ").lower()

                    if confirm == "y":
                        self.undo_last_step()
                    else:
                        print("Undo cancelled.")

                if key == KEY_SAVE_MANUAL:
                    self.save_manual()

                    more_manuals = input("Want to create another manual? (y/n): ")

                    if more_manuals == "y":
                        self.reset_manual_creator(projector_width, projector_height)
                    else:
                        print("Creation of manuals stopped.")
                        break
        finally:
            camera.stop()
            cv2.destroyAllWindows()

