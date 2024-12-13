import os
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple
import time
import sys
from screeninfo import get_monitors

import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QMessageBox
)
from PyQt5.QtGui import QPixmap, QImage, QFont
from PyQt5.QtCore import Qt, QTimer

# Local imports
from .visualization import draw_axes, draw_tag_border_and_id
from .projection import project_image
from .utils import open_image_in_paint
from .image_processing import cam_2D_to_tag_3D
from .camera import Camera

class ManualCreator(QMainWindow):
    def __init__(self, camera=None, apriltag_detector=None, cam_K=None, cam_kc=None, projector_window_name=None, projector_width=None, projector_height=None, \
                 proj_image=None, R_proj=None, T_proj=None, proj_K=None, proj_kc=None, base_manuals_dir="data/manuals", raw_images_dir="raw_images", instructions_dir="instructions") -> None:
        """
        Initializes the ManualCreator object.

        :param base_manuals_dir: The base directory where the manuals will be saved.
        :param raw_images_dir: The directory where the raw images will be saved.
        :param instructions_dir: The directory where the instructions will be saved.
        """
        # Initialize the parent class and the UI
        super().__init__()
        self.init_ui()
        self.camera = camera
        self.cam_K = cam_K
        self.cam_kc = cam_kc
        self.apriltag_detector = apriltag_detector
        self.tag_axis_length = self.apriltag_detector.tag_size
        self.min_distance_to_tag = 0.15
        self.projector_window_name = projector_window_name
        self.projector_width = projector_width
        self.projector_height = projector_height
        self.timer = QTimer()
        self.last_time = time.time()

        self.results = None
        self.color_image = None
        self.depth_image = None
        self.depth_scale = None
        self.apriltag_pose = None
        self.image_with_drawings_path = None
        self.proj_image = proj_image
        self.points_3D_tag = None
        self.valid_colors = None
        self.R_proj = R_proj
        self.T_proj = T_proj
        self.proj_K = proj_K
        self.proj_kc = proj_kc

        # Initialize the manual creator
        self.manual_count = 0
        self.tag_id = None
        self.step_number = 1
        self.steps = []
        self.step_saved = False
        self.extracted_3D_pixels = False
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

    def init_ui(self):
        self.setWindowTitle("Manual Creator")
        self.setGeometry(100, 100, 1920, 1080)  # Fenstergröße auf 1920x1080 setzen

        # Hauptlayout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)  # Abstände zwischen Elementen

        # Statusbereich
        self.status_label = QLabel("Status: Ready")
        self.status_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.status_label.setAlignment(Qt.AlignLeft)
        self.status_label.setFixedHeight(50)
        self.status_label.setFont(QFont("Arial", 16))  # Größere Schrift für bessere Lesbarkeit

        # Bildanzeigebereich (640x480)
        self.live_image_label = QLabel("Live Camera Feed")
        self.live_image_label.setFixedSize(640, 480)
        self.live_image_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.live_image_label.setAlignment(Qt.AlignCenter)

        # Layout für den Bildanzeigebereich
        image_layout = QHBoxLayout()
        image_layout.addWidget(self.live_image_label)

        # Button-Bereich (horizontal)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(30)  # Mehr Abstand zwischen Buttons

        button_font = QFont("Arial", 18)  # Größere Schrift für Buttons

        self.start_live_button = QPushButton("Start Live Feed")
        self.start_live_button.setFont(button_font)
        self.start_live_button.setFixedSize(250, 100)
        self.start_live_button.clicked.connect(self.start_live_feed_button_pressed)

        self.stop_live_button = QPushButton("Stop Live Feed")
        self.stop_live_button.setFont(button_font)
        self.stop_live_button.setFixedSize(250, 100)
        self.stop_live_button.clicked.connect(self.stop_live_feed_button_pressed)

        self.capture_button = QPushButton("Capture Photo")
        self.capture_button.setFont(button_font)
        self.capture_button.setFixedSize(250, 100)
        self.capture_button.clicked.connect(self.capture_photo_button_pressed)

        self.save_step_button = QPushButton("Save Step")
        self.save_step_button.setFont(button_font)
        self.save_step_button.setFixedSize(250, 100)
        self.save_step_button.clicked.connect(self.save_step_button_pressed)

        self.undo_step_button = QPushButton("Undo Step")
        self.undo_step_button.setFont(button_font)
        self.undo_step_button.setFixedSize(250, 100)
        self.undo_step_button.clicked.connect(self.undo_step_button_pressed)

        self.save_manual_button = QPushButton("Save Manual")
        self.save_manual_button.setFont(button_font)
        self.save_manual_button.setFixedSize(250, 100)
        self.save_manual_button.clicked.connect(self.save_manual_button_pressed)

        self.quit_button = QPushButton("Quit")
        self.quit_button.setFont(button_font)
        self.quit_button.setFixedSize(250, 100)
        self.quit_button.clicked.connect(self.close)

        # Buttons zum Layout hinzufügen
        button_layout.addWidget(self.start_live_button)
        button_layout.addWidget(self.stop_live_button)
        button_layout.addWidget(self.capture_button)
        button_layout.addWidget(self.save_step_button)
        button_layout.addWidget(self.undo_step_button)
        button_layout.addWidget(self.save_manual_button)
        button_layout.addWidget(self.quit_button)

        # Elemente zum Hauptlayout hinzufügen
        main_layout.addWidget(self.status_label)
        main_layout.addLayout(image_layout)
        main_layout.addLayout(button_layout)

        # Zentrales Widget setzen
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def open_window(self):
        # Get the second screen (projector)
        monitors = get_monitors()
        if len(monitors) < 2:
            print("Error: No second screen found. Please connect a second screen and try again.")
            sys.exit()

        # Move the window to the second screen and show it full screen
        second_screen = monitors[1]
        self.move(second_screen.x, second_screen.y)
        self.showFullScreen()

    def start_live_feed_button_pressed(self):    
        if not self.camera:
            self.camera = Camera(color_width=640, color_height=480, depth_width=640, depth_height=480, fps=60)
        try:
            self.timer.timeout.disconnect(self.update_frame)
        except TypeError:
            pass  # Connection does not exist, nothing to disconnect

        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  # Refresh every 16ms (~60fps)

        self.status_label.setText("Status: Live Feed Running")

    def stop_live_feed_button_pressed(self):
        # Stop the camera and the timer
        if self.camera:
            self.timer.stop()
            try:
                self.timer.timeout.disconnect(self.update_frame)
            except TypeError:
                pass  # Connection does not exist, nothing to disconnect
            self.camera.stop()
            self.camera = None
            self.live_image_label.clear()
            self.live_image_label.setText("Live Camera Feed")
            self.status_label.setText("Status: Live Feed Stopped")

    def update_frame(self):
        # Calculate the FPS
        current_time = time.time()
        fps = 1 / (current_time - self.last_time)
        self.last_time = current_time

        # Get the frames from the camera
        success, color_image, _, depth_image, depth_frame, depth_scale = self.camera.get_frames()
        if not success:
            self.status_label.setText("Status: Error - Cannot read frame")

        self.color_image = color_image
        self.depth_image = depth_image
        self.depth_scale = depth_scale

        ### AprilTag Detection Logic ###

        gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)
        results = self.apriltag_detector.detect(gray)

        if results:
            self.results = results

        for result in results:
            # Get the distance to the center of the AprilTag
            u_center_of_tag, v_center_of_tag = int(result.center[0]), int(result.center[1])
            depth_to_tag = depth_frame.get_distance(u_center_of_tag, v_center_of_tag)
            # print(f"Depth to AprilTag: {depth_to_tag}m")

            # Rotation vector (Orientation relative to the camera)
            R_tag = result.pose_R

            # Check if camera is too close to the tag
            if depth_to_tag > self.min_distance_to_tag:
                # Translation vector (Position relative to the camera) -> calculated with the opencv and the calibration data from
                # the camera-projector calibration
                # tvec_realsense = camera.get_3D_camera_coords(u_center_of_tag, v_center_of_tag, depth_to_tag, color_intrinsics["intrinsics_raw"])
                tvec_tag_opencv = self.camera.get_3D_camera_coords_opencv(u_center_of_tag, v_center_of_tag, self.cam_K, self.cam_kc, depth_frame)

                self.apriltag_pose = (R_tag, tvec_tag_opencv)

                # Draw the axes and tag border with ID
                color_image = draw_axes(color_image, R_tag, tvec_tag_opencv, self.cam_K, self.cam_kc, self.tag_axis_length)
                
                # If the user has drawn on the image, transform the 2D image points to 3D tag coordinates and project them
                if self.extracted_3D_pixels and not self.step_saved:
                    self.proj_image = project_image(
                        self.proj_image, 
                        self.points_3D_tag,
                        self.valid_colors, 
                        self.R_proj, 
                        self.T_proj, 
                        R_tag, 
                        tvec_tag_opencv, 
                        self.proj_K, 
                        self.proj_kc,
                        self.projector_width,
                        self.projector_height
                    )
            else:
                cv2.putText(color_image, "Too close!, please move away a few cm.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # Always draw the tag border and ID
            color_image = draw_tag_border_and_id(color_image, result)

        ### Begin show the color image in the GUI ###

        # Convert the color image from BGR to RGB
        frame = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)

        # Convert the image to a QImage
        height, width, channel = frame.shape
        q_image = QImage(frame.data, width, height, channel * width, QImage.Format_RGB888)

        # Display the QImage in the label
        self.live_image_label.setPixmap(QPixmap.fromImage(q_image))

        # Update the status label with the FPS in real-time
        self.status_label.setText(f"Status: Live Feed Running | FPS: {fps:.2f}")

        ### End show the color image in the GUI ###

        cv2.imshow(self.projector_window_name, self.proj_image)

    def save_photo(self, img) -> Tuple[str, str]:
        """
        Captures a photo and saves it in the raw images directory.

        :param img: The image to save.
        :return: The path to the saved image and the filename
        """
        filename = f"raw_image_{self.tag_id}_step_{self.step_number:03}.png"
        photo_path = self.raw_images_dir / filename
        cv2.imwrite(str(photo_path), img)
        self.status_label.setText(f"Image saved at: {photo_path}")

        return str(photo_path), filename

    def capture_photo_button_pressed(self):
        if self.results:
            self.tag_id = self.results[0].tag_id

            self.status_label.setText(f"Creating step {self.step_number} for AprilTag ID {self.tag_id}.")

            self.step_saved = False
                
            # 1. Capture the photo
            image_path, _ = self.save_photo(self.color_image)

            # 2. Open the image in Paint
            open_image_in_paint(image_path)

            # 3. Get the path to the image with the drawings
            instructions = [self.instructions_dir / datei for datei in os.listdir(self.instructions_dir) if datei.lower().endswith(".png")]
            if not instructions:
                self.status_label.setText("No images with drawings found.")
            else:
                # Get the newest instruction
                newest_instruction = max(instructions, key=lambda p: p.stat().st_mtime)     

                # Prepare the new path
                new_name = f"instruction_{self.tag_id}_step_{self.step_number:03}.png"
                self.image_with_drawings_path = self.instructions_dir / new_name
                
                # Rename the image
                newest_instruction.rename(self.image_with_drawings_path)
                self.status_label.setText(f"The image with the drawings has been renamed to: {self.image_with_drawings_path}")

            # Calculate the 3D points relative to the AprilTag and the corresponding colors
            self.points_3D_tag, _, self.valid_colors = cam_2D_to_tag_3D(self.image_with_drawings_path, self.depth_image, self.depth_scale, self.cam_K, self.apriltag_pose)

            if self.points_3D_tag is not None and self.valid_colors is not None:
                self.extracted_3D_pixels = True
                self.status_label.setText(f"3D Points relative to the AprilTag: {len(self.points_3D_tag)}")
            else:
                self.status_label.setText("Error in 3D point extraction. Please check the image and parameters.")
                return
        else:
            self.status_label.setText("No AprilTag detected, please try again.")

    def reset_projection_border_color(self, color):
        self.proj_image = np.zeros((self.projector_height, self.projector_width, 3), dtype=np.uint8)
        if color == "red":
            self.proj_image = cv2.rectangle(self.proj_image, (0, 0), (self.projector_width - 1, self.projector_height - 1), (0, 0, 255), 10)
        elif color == "green":
            self.proj_image = cv2.rectangle(self.proj_image, (0, 0), (self.projector_width - 1, self.projector_height - 1), (0, 255, 0), 10)
    
    def save_step_button_pressed(self):
        save_confirm = QMessageBox.question(
            self, 
            "Save Step", 
            f"Are you sure you want to save the instruction step {self.step_number:03} for the AprilTag ID {self.tag_id}?", 
            QMessageBox.Yes | QMessageBox.No
        )

        if save_confirm == QMessageBox.Yes:
            self.step_saved = True

            self.create_step(self.image_with_drawings_path)
            self.step_number += 1
            
            self.proj_image = self.reset_projection_border_color("red")
        else:
            print("Step not saved.")
            self.step_saved = False

            self.proj_image = self.reset_projection_border_color("red")

    def undo_step_button_pressed(self):
        undo_confirm = QMessageBox.question(
            self, 
            "Undo Step", 
            "Are you sure you want to undo the last step?", 
            QMessageBox.Yes | QMessageBox.No
        )

        if undo_confirm == QMessageBox.Yes:
            self.undo_last_step()
        else:
            self.status_label.setText("Undo cancelled.")

    def save_manual_button_pressed(self):
        self.save_manual()
        manual_confirm = QMessageBox.question(
            self, 
            "Save Manual", 
            "Want to create another manual?", 
            QMessageBox.Yes | QMessageBox.No
        )

        if manual_confirm == QMessageBox.Yes:
            self.reset_manual_creator(self.projector_width, self.projector_height)
        else:
            self.status_label.setText("Creation of manuals stopped.")
            # TODO: Get back to main screen       

    def reset_manual_creator(self) -> None:
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

        self.proj_image = self.reset_projection_border_color("red")

        self.status_label.setText("Everything has been reset.")

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
        self.status_label.setText(f"Step {self.step_number} saved.")

    def undo_last_step(self):
        if self.steps:
            removed_step = self.steps.pop()
            self.step_number -= 1
            self.status_label.setText(f"Removed step {removed_step['step']}.")
        else:
            self.status_label.setText("No steps to undo.")

    def save_manual(self) -> None:
        """
        Saves the manual as a JSON file
        """
        if self.tag_id is None:
            self.status_label.setText("No tag ID found, manual not saved.")
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
            self.status_label.setText(f"Manual saved at {json_path} for AprilTag ID {self.tag_id}.")
        except Exception as e:
            self.status_label.setText(f"Error saving manual: {e}")