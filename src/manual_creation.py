import os
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple
import time
import sys
import shutil
from screeninfo import get_monitors

import cv2
import numpy as np

from PyQt5.QtWidgets import (
    QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QMessageBox, QStackedWidget, QListWidget, QLineEdit, \
    QGraphicsView, QGraphicsScene, QProgressBar, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsLineItem, QDialog
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QBrush, QPen
from PyQt5.QtCore import Qt, QTimer

# Local imports
from .visualization import draw_axes, draw_tag_border_and_id
from .projection import project_image
from .utils import open_image_in_paint
from .image_processing import cam_2D_to_tag_3D
from .camera import Camera

class DescriptionDialog(QDialog):
    def __init__(self, parent=None):
        """
        Initialize the DescriptionDialog object.
        """
        super().__init__(parent)
        self.setWindowTitle("Enter Description")
        self.setFixedSize(400, 200)
        self.setModal(True)  # Blocks the parent window until this dialog is closed

        # Layout
        layout = QVBoxLayout()

        # Label for the description input
        self.label = QLabel("Please enter a description:")
        self.label.setFont(QFont("Arial", 14))
        layout.addWidget(self.label)

        # Input field for the description
        self.description_input = QLineEdit()
        self.description_input.setFont(QFont("Arial", 12))
        layout.addWidget(self.description_input)

        # OK-Button
        self.ok_button = QPushButton("OK")
        self.ok_button.setFont(QFont("Arial", 12))
        self.ok_button.clicked.connect(self.validate_input)

        layout.addWidget(self.ok_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

    def validate_input(self):
        """
        Validate the input in the description input field.
        """
        # Check if the description is empty
        if not self.description_input.text().strip():
            QMessageBox.warning(self, "Input Error", "Description cannot be empty. Please enter a description.")
        else:
            self.accept()

    def closeEvent(self, event):
        """
        Override the closeEvent method to prevent closing the window with 'X' if the description is empty.
        """
        # Check if the description is empty and prevent closing the window with 'X'
        if not self.description_input.text().strip():
            QMessageBox.warning(self, "Input Error", "You cannot close this window without entering a description.")
            event.ignore()  # Prevents the window from closing
        else:
            event.accept()  # Accept the event and close the window

    def get_description(self):
        """
        Get the description entered by the user.
        """
        return self.description_input.text().strip()

class ManualCreator(QMainWindow):
    def __init__(self, camera=None, apriltag_detector=None, cam_K=None, cam_kc=None, projector_window_name=None, projector_width=None, projector_height=None, \
                 proj_image=None, R_proj=None, T_proj=None, proj_K=None, proj_kc=None, base_manuals_dir="data/manuals", raw_images_dir="raw_images", instructions_dir="instructions") -> None:
        """
        Initialize the ManualCreator object.

        :param camera: The camera object.
        :param apriltag_detector: The AprilTag detector object.
        :param cam_K: The camera matrix.
        :param cam_kc: The distortion coefficients.
        :param projector_window_name: The name of the projector window.
        :param projector_width: The width of the projector window.
        :param projector_height: The height of the projector window.
        :param proj_image: The projected image.
        :param R_proj: The rotation matrix of the projector.
        :param T_proj: The translation vector of the projector.
        :param proj_K: The projector matrix.
        :param proj_kc: The projector distortion coefficients.
        :param base_manuals_dir: The base directory for the manuals.
        :param raw_images_dir: The directory for the raw images.
        :param instructions_dir: The directory for the instructions.
        """
        # Initialize the parent class and the UI
        super().__init__()

        # Initialize the main window
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Initialize the pages
        self.init_start_page()
        self.init_manual_creation_page()
        self.init_manual_loading_page()
        self.init_manual_execution_page()

        # Set the first page to the start page
        self.stacked_widget.setCurrentIndex(0)

        # Initialize the camera properties
        self.camera = camera
        self.camera_running = False
        self.cam_K = cam_K
        self.cam_kc = cam_kc

        # Initialize the AprilTag properties
        self.apriltag_detector = apriltag_detector
        self.tag_axis_length = self.apriltag_detector.tag_size
        self.min_distance_to_tag = 0.15

        # Initialize the projector properties
        self.projector_window_name = projector_window_name
        self.projector_width = projector_width
        self.projector_height = projector_height

        # Initialize the timer for the live feed
        self.timer = QTimer()
        self.last_time = time.time()
        self.second_screen = None

        # Initialize the loop variables
        self.results = None
        self.color_image = None
        self.depth_image = None
        self.apriltag_pose = None
        self.image_with_drawings_path = None
        self.proj_image = proj_image
        self.points_3D_tag = None
        self.valid_colors = None
        self.R_proj = R_proj
        self.T_proj = T_proj
        self.proj_K = proj_K
        self.proj_kc = proj_kc
        self.last_raw_image_path = None
        self.manual_saved = False
        self.manual_count = 0
        self.tag_id = None
        self.step_number = 1
        self.current_execution_step_index = 0
        self.steps = []
        self.execution_steps = []
        self.step_saved = False
        self.step_description = None
        self.extracted_3D_pixels = False

        # Initialize the directories
        self.base_manuals_dir = Path(base_manuals_dir)
        self.current_manual_dir = self.base_manuals_dir / f"manual_{self.manual_count}"
        self.raw_images_dir = self.current_manual_dir / raw_images_dir
        self.instructions_dir = self.current_manual_dir / instructions_dir

    def init_start_page(self):
        """
        Initialize the start page of the application.
        """
        # Create the start page and the layout
        start_page = QWidget()
        layout = QVBoxLayout()

        # Title
        label = QLabel("Projection-Based Augmented Reality Assembly Working Station")
        label.setFont(QFont("Arial", 28))
        label.setAlignment(Qt.AlignCenter)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(20)

        # Button to get to the manual creation page
        create_manual_button = QPushButton("Create Manual")
        create_manual_button.setFont(QFont("Arial", 18))
        create_manual_button.setFixedSize(250, 100)
        create_manual_button.clicked.connect(self.create_manual_button_clicked)

        # Button to get to the manual loading page
        load_manual_button = QPushButton("Load Manual")
        load_manual_button.setFont(QFont("Arial", 18))
        load_manual_button.setFixedSize(250, 100)
        load_manual_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))

        # Button to quit the application
        quit_button = QPushButton("Quit")
        quit_button.setFont(QFont("Arial", 18))
        quit_button.setFixedSize(250, 100)
        quit_button.clicked.connect(self.close)

        button_layout.addWidget(create_manual_button)
        button_layout.addWidget(load_manual_button)
        button_layout.addWidget(quit_button)

        button_layout.setAlignment(Qt.AlignCenter)

        layout.addWidget(label)
        layout.addLayout(button_layout)
        start_page.setLayout(layout)

        self.stacked_widget.addWidget(start_page)

    def init_manual_creation_page(self):
        """
        Initialize the manual creation page of the application.
        """
        manual_creation_page = QWidget()

        self.setWindowTitle("Manual Creator")
        self.setGeometry(100, 100, 1920, 1080)  # Set the window size to 1920x1080

        # Main container for the window
        manual_creation_page_layout = QVBoxLayout()
        manual_creation_page_layout.setSpacing(20)  # Space between elements

        # Status label
        self.status_label = QLabel("Status: Ready")
        self.status_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.status_label.setAlignment(Qt.AlignLeft)
        self.status_label.setFixedHeight(50)
        self.status_label.setFont(QFont("Arial", 16))  # Bigger font for status label

        # Layout for the live image
        image_layout = QHBoxLayout()
        image_layout.setSpacing(10)
        
        instruction_text_left = (
            "<b>How to create a Manual:</b><br><br>"
            "<b>1.</b> Start the camera live feed by clicking the 'Start Live Feed' button.<br>"
            "<b>2.</b> Place the object with the AprilTag in the projected red outline (working area).<br>"
            "<b>3.</b> Ensure that the AprilTag is detected (its coordinate system should be visible). "
            "Make sure the camera has a clear view of the working area, the object, and the AprilTag.<br>"
            "<b>4.</b> Capture a photo by clicking the 'Capture Photo' button.<br>"
            "<b>5.</b> Wait until Paint has automatically created two layers.<br>"
            "<b>6.</b> Select the first layer (above the original background layer), "
            "fill it completely black, and deactivate it.<br>"
            "<b>7.</b> Select the second layer and draw the instruction in the working area.<br>"
            "<b>8.</b> Activate the first layer again so that only the instructions are visible on a black background.<br>"
        )

        instruction_text_right = (
            "<br><br><b>9.</b> Save the image as a PNG in the 'instructions' folder. "
            "Ensure you are in the correct manual folder.<br>"
            "<b>10.</b> Close Paint.<br>"
            "<b>11.</b> The instructions should now be projected into the real world "
            "and will dynamically adjust to the AprilTag’s position.<br>"
            "<b>12.</b> If satisfied, click 'Save Step' to store this instruction and enter an description.<br>"
            "<b>13.</b> If you want to redo the last step, click 'Undo Step'. "
            "Then repeat steps 2-13 to create a new instruction.<br>"
            "<b>14.</b> Repeat steps 2-14 until you have enough instruction steps.<br>"
            "<b>15.</b> Click 'Save Manual' to save the complete manual.<br>"
            "<b>16.</b> When prompted, choose 'Yes' to create another manual, or 'No' to return to the main page."
        )

        self.instruction_label_left = QLabel(instruction_text_left)
        self.instruction_label_left.setFixedSize(300, 720)
        # self.instruction_label_left.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.instruction_label_left.setAlignment(Qt.AlignLeft)
        self.instruction_label_left.setFont(QFont("Arial", 12))
        self.instruction_label_left.setWordWrap(True)
        self.instruction_label_left.setTextFormat(Qt.RichText)  # Important for HTML

        self.instruction_label_right = QLabel(instruction_text_right)
        self.instruction_label_right.setFixedSize(300, 720)
        # self.instruction_label_right.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.instruction_label_right.setAlignment(Qt.AlignLeft)
        self.instruction_label_right.setFont(QFont("Arial", 12))
        self.instruction_label_right.setWordWrap(True)
        self.instruction_label_right.setTextFormat(Qt.RichText)  # Important for HTML

        # Live Camera Feed (1280x720)
        self.live_image_label = QLabel("Live Camera Feed")
        self.live_image_label.setFixedSize(1280, 720)
        self.live_image_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.live_image_label.setAlignment(Qt.AlignCenter)

        image_layout.addWidget(self.instruction_label_left)
        image_layout.addWidget(self.live_image_label)
        image_layout.addWidget(self.instruction_label_right)

        # Button-Layout (horizontal)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(30)  # Enough space between buttons

        button_font = QFont("Arial", 18)  # Bigger font for buttons

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
        self.quit_button.clicked.connect(self.quit_button_manual_creation_page_clicked)

        # Add the buttons to the button layout
        button_layout.addWidget(self.start_live_button)
        button_layout.addWidget(self.stop_live_button)
        button_layout.addWidget(self.capture_button)
        button_layout.addWidget(self.save_step_button)
        button_layout.addWidget(self.undo_step_button)
        button_layout.addWidget(self.save_manual_button)
        button_layout.addWidget(self.quit_button)

        # Add the status label, image layout, and button layout to the main layout
        manual_creation_page_layout.addWidget(self.status_label)
        manual_creation_page_layout.addLayout(image_layout)
        manual_creation_page_layout.addLayout(button_layout)

        # Set the main layout as the central widget
        manual_creation_page.setLayout(manual_creation_page_layout)

        self.stacked_widget.addWidget(manual_creation_page)

    def init_manual_loading_page(self):
        """
        Initialize the manual loading page of the application.
        """
        manual_loading_page = QWidget()

        self.setWindowTitle("Manual Loader")
        self.setGeometry(100, 100, 1920, 1080)  # Set the window size to 1920x1080

        # Main container for the window
        manual_loading_page_layout = QVBoxLayout()

        top_bar_layout = QHBoxLayout()

        self.tag_id_input_label = QLabel("Enter the AprilTag ID:")
        self.tag_id_input_label.setFont(QFont("Arial", 24))

        self.tag_id_input_field = QLineEdit()
        self.tag_id_input_field.setFont(QFont("Arial", 24))
        self.tag_id_input_field.setFixedWidth(200)

        self.search_button = QPushButton("Search")
        self.search_button.setFont(QFont("Arial", 18))
        self.search_button.setFixedSize(250, 100)
        self.search_button.clicked.connect(self.show_manuals_in_list)
        
        top_bar_layout.addWidget(self.tag_id_input_label)
        top_bar_layout.addWidget(self.tag_id_input_field)
        top_bar_layout.addWidget(self.search_button)

        self.manuals_list = QListWidget()
        self.manuals_list.setFont(QFont("Arial", 24))
        self.manuals_list.itemClicked.connect(self.load_manual)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(30)  # Enough space between buttons

        self.quit_button = QPushButton("Quit")
        self.quit_button.setFont(QFont("Arial", 18))
        self.quit_button.setFixedSize(250, 100)
        self.quit_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))

        button_layout.addWidget(self.quit_button)

        # Add the quit button to the layout
        manual_loading_page_layout.addLayout(top_bar_layout)
        manual_loading_page_layout.addWidget(self.manuals_list)
        manual_loading_page_layout.addLayout(button_layout)
        # manual_using_page_layout.setAlignment(Qt.AlignCenter)
        manual_loading_page.setLayout(manual_loading_page_layout)

        self.stacked_widget.addWidget(manual_loading_page)

    def init_manual_execution_page(self):
        """
        Initialize the manual execution page of the application.
        """
        manual_execution_page = QWidget()

        manual_execution_page_layout = QVBoxLayout()
        manual_execution_page_layout.setSpacing(20)

        # Status label
        self.execution_status_label = QLabel("Status: Ready")
        self.execution_status_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.execution_status_label.setAlignment(Qt.AlignLeft)
        self.execution_status_label.setFixedHeight(50)
        self.execution_status_label.setFont(QFont("Arial", 16))  # Bigger font for status label
        manual_execution_page_layout.addWidget(self.execution_status_label)

        start_stop_button_layout = QHBoxLayout()
        start_stop_button_layout.setSpacing(30)  # Enough space between buttons

        button_font = QFont("Arial", 16)  # Bigger font for buttons

        self.execution_start_live_button = QPushButton("Start Live Feed")
        self.execution_start_live_button.setFont(button_font)
        self.execution_start_live_button.setFixedSize(200, 60)
        self.execution_start_live_button.clicked.connect(self.start_live_feed_button_pressed)
        start_stop_button_layout.addWidget(self.execution_start_live_button)

        self.execution_stop_live_button = QPushButton("Stop Live Feed")
        self.execution_stop_live_button.setFont(button_font)
        self.execution_stop_live_button.setFixedSize(200, 60)
        self.execution_stop_live_button.clicked.connect(self.stop_live_feed_button_pressed)
        start_stop_button_layout.addWidget(self.execution_stop_live_button)

        manual_execution_page_layout.addLayout(start_stop_button_layout)

        image_layout = QHBoxLayout()
        
        # Live Camera Feed (640x480)
        self.execution_live_image_label = QLabel("Live Camera Feed")
        self.execution_live_image_label.setFixedSize(1280, 720)
        self.execution_live_image_label.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.execution_live_image_label.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.execution_live_image_label)
        manual_execution_page_layout.addLayout(image_layout)

        self.start_execution_button = QPushButton("Start Execution")
        self.start_execution_button.setFont(QFont("Arial", 16))
        self.start_execution_button.setFixedSize(200, 60)
        self.start_execution_button.clicked.connect(self.start_execution_button_pressed)
        manual_execution_page_layout.addWidget(self.start_execution_button, alignment=Qt.AlignCenter)

        # Text label for the step description
        self.step_instruction_label = QLabel()
        self.step_instruction_label.setFont(QFont("Arial", 16))
        self.step_instruction_label.setAlignment(Qt.AlignCenter)
        manual_execution_page_layout.addWidget(self.step_instruction_label)

        # Activity Diagram View
        self.activity_diagram_view = QGraphicsView()
        self.activity_diagram_scene = QGraphicsScene()
        self.activity_diagram_view.setScene(self.activity_diagram_scene)
        self.activity_diagram_view.setFixedHeight(150)
        manual_execution_page_layout.addWidget(self.activity_diagram_view)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #4CAF50;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
            }
        """)
        manual_execution_page_layout.addWidget(self.progress_bar)

        # Buttons for manual execution
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        self.previous_step_button = QPushButton("Previous Step")
        self.previous_step_button.setFont(QFont("Arial", 14))
        self.previous_step_button.setFixedSize(150, 50)
        self.previous_step_button.clicked.connect(self.previous_step)

        self.next_step_button = QPushButton("Next Step")
        self.next_step_button.setFont(QFont("Arial", 14))
        self.next_step_button.setFixedSize(150, 50)
        self.next_step_button.clicked.connect(self.next_step)

        self.finish_button = QPushButton("Finish")
        self.finish_button.setFont(QFont("Arial", 14))
        self.finish_button.setFixedSize(150, 50)
        self.finish_button.clicked.connect(self.finish_manual)

        self.quit_manual_execution_button = QPushButton("Quit")
        self.quit_manual_execution_button.setFont(QFont("Arial", 14))
        self.quit_manual_execution_button.setFixedSize(150, 50)
        self.quit_manual_execution_button.clicked.connect(self.quit_button_manual_execution_page_clicked)

        button_layout.addStretch()
        button_layout.addWidget(self.previous_step_button)
        button_layout.addWidget(self.next_step_button)
        button_layout.addWidget(self.finish_button)
        button_layout.addStretch()
        button_layout.addWidget(self.quit_manual_execution_button)

        manual_execution_page_layout.addLayout(button_layout)

        manual_execution_page.setLayout(manual_execution_page_layout)

        self.stacked_widget.addWidget(manual_execution_page)

    def start_execution_button_pressed(self):
        """
        Start the execution of the manual.
        """
        if self.camera_running:
            self.display_current_step()
        else:
            self.show_message("Please start the live feed first.", title="Error", message_type="error")

    def open_window(self):
        """
        Open the main window.
        """
        # Get the second screen (projector)
        monitors = get_monitors()
        if len(monitors) < 2:
            print("Error: No second screen found. Please connect a second screen and try again.")
            sys.exit()

        # Move the window to the second screen and show it full screen
        second_screen = monitors[1]
        self.second_screen = second_screen
        self.move(second_screen.x, second_screen.y)
        self.showFullScreen()

    def start_live_feed_button_pressed(self):
        """
        Start the live feed of the camera.
        """    
        if not self.camera:
            self.camera = Camera()
        try:
            self.timer.timeout.disconnect(self.update_frame)
        except TypeError:
            pass  # Connection does not exist, nothing to disconnect

        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)  # Refresh every 30ms (~30fps)

        # Update the status label depending on the current page
        if self.stacked_widget.currentIndex() == 1:
            self.status_label.setText("Status: Live Feed Running")
        elif self.stacked_widget.currentIndex() == 3:
            self.step_saved = False
            self.execution_status_label.setText("Status: Live Feed Running")

        self.camera_running = True

    def stop_live_feed_button_pressed(self):
        """
        Stop the live feed of the camera.
        """
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
            self.camera_running = False

    def update_frame(self):
        """
        Update the frame of the camera and display it in the GUI.
        """
        # Calculate the FPS
        current_time = time.time()
        fps = 1 / (current_time - self.last_time)
        self.last_time = current_time

        # Get the frames from the camera
        success, color_image, _, depth_image, depth_frame = self.camera.get_frames()
        if not success:
            self.status_label.setText("Status: Error - Cannot read frame")
            self.camera_running = False
            return

        self.color_image = color_image
        self.depth_image = depth_image

        # print("Color Image Shape: ", color_image.shape)

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

        # Display the QImage in the label depending on the current page
        if self.stacked_widget.currentIndex() == 1:
            # Display the QImage in the label
            self.live_image_label.setPixmap(QPixmap.fromImage(q_image))

            # Update the status label with the FPS in real-time
            self.status_label.setText(f"Status: Live Feed Running | FPS: {fps:.2f}")
        elif self.stacked_widget.currentIndex() == 3:
            # Display the QImage in the label
            self.execution_live_image_label.setPixmap(QPixmap.fromImage(q_image))

            # Update the status label with the FPS in real-time
            self.execution_status_label.setText(f"Status: Live Feed Running | FPS: {fps:.2f}")

        ### End show the color image in the GUI ###

        if self.proj_image is not None and self.proj_image.shape[1] > 0 and self.proj_image.shape[0] > 0:
            cv2.imshow(self.projector_window_name, self.proj_image)
        else:
            print("Warning: proj_image has invalid dimensions, skipping display.")

    def save_photo(self, img) -> Tuple[str, str]:
        """
        Save the photo to the raw images directory.

        :param img: The image to save.
        :return: The path to the saved image and the filename.
        """
        filename = f"raw_image_{self.tag_id}_step_{self.step_number:03}.png"
        photo_path = self.raw_images_dir / filename

        cv2.imwrite(str(photo_path), img)
        self.show_message(f"Image saved at: {photo_path}", title="Information", message_type="info")

        return str(photo_path), filename

    def capture_photo_button_pressed(self):
        """
        Capture a photo and save it to the raw images directory.
        """
        if self.results:
            self.tag_id = self.results[0].tag_id

            self.show_message(f"Creating step {self.step_number} for AprilTag ID: {self.tag_id}", title="Information", message_type="info")

            self.step_saved = False
                
            # 1. Capture the photo
            self.last_raw_image_path, _ = self.save_photo(self.color_image)

            # 2. Open the image in Paint
            open_image_in_paint(self.last_raw_image_path, self.second_screen)

            # 3. Get the path to the image with the drawings
            instructions = [self.instructions_dir / datei for datei in os.listdir(self.instructions_dir) if datei.lower().endswith(".png")]
            if not instructions:
                self.show_message("No images with drawings found. Please draw on the image and save it.", title="Warning", message_type="warning")
                return
            else:
                # Get the newest instruction
                newest_instruction = max(instructions, key=lambda p: p.stat().st_mtime)     

                # Prepare the new path
                new_name = f"instruction_{self.tag_id}_step_{self.step_number:03}.png"
                self.image_with_drawings_path = self.instructions_dir / new_name

                # FIXME: Find a better way to handle this
                if self.image_with_drawings_path.exists():
                    self.image_with_drawings_path.unlink()
                    Path(self.last_raw_image_path).unlink()
                
                # Rename the image
                newest_instruction.rename(self.image_with_drawings_path)
                self.show_message(f"The image with the drawings has been renamed to: {self.image_with_drawings_path}", title="Information", message_type="info")

            # Calculate the 3D points relative to the AprilTag and the corresponding colors
            self.points_3D_tag, _, self.valid_colors = cam_2D_to_tag_3D(self.image_with_drawings_path, self.depth_image, self.camera.depth_scale, self.cam_K, self.apriltag_pose)

            if self.points_3D_tag is not None and self.valid_colors is not None:
                self.extracted_3D_pixels = True
                self.show_message(f"3D points extracted successfully. Number of Points: {len(self.points_3D_tag)}", title="Information", message_type="info")
            else:
                self.show_message("Error in 3D point extraction. Please check the image and parameters.", title="Error", message_type="error")
                return
        else:
            self.show_message("No AprilTag detected, please try again.", title="Warning", message_type="warning")

    def reset_projection_border_color(self, color):
        """
        Reset the color of the projection border.

        :param color: The color to set the border to.
        """
        self.proj_image = np.zeros((self.projector_height, self.projector_width, 3), dtype=np.uint8)
        if color == "red":
            self.proj_image = cv2.rectangle(self.proj_image, (0, 0), (self.projector_width - 1, self.projector_height - 1), (0, 0, 255), 10)
        elif color == "green":
            self.proj_image = cv2.rectangle(self.proj_image, (0, 0), (self.projector_width - 1, self.projector_height - 1), (0, 255, 0), 10)
    
    def save_step_button_pressed(self):
        """
        Save the current step with the image with drawings and the description.
        """
        if self.tag_id is None:
            self.show_message("No AprilTag ID found. Can't save step!", title="Error", message_type="error")
            return

        save_confirm = QMessageBox.question(
            self, 
            "Save Step", 
            f"Are you sure you want to save the instruction step {self.step_number:03} for the AprilTag ID {self.tag_id}?", 
            QMessageBox.Yes | QMessageBox.No
        )

        if save_confirm == QMessageBox.Yes:
            if self.image_with_drawings_path is None:
                self.show_message("No Image with drawing found. Can't save step!", title="Error", message_type="error")
                return
            
            # Open a dialog to enter the description
            dialog = DescriptionDialog(self)
            self.step_description = None

            if dialog.exec_() == QDialog.Accepted:
                self.step_description = dialog.get_description()
                
            if not self.step_description:
                self.show_message("No description entered. Step not saved.", title="Warning", message_type="warning")
                return

            self.create_step(self.image_with_drawings_path)

            self.step_saved = True
            self.step_number += 1
            
            self.reset_projection_border_color("red")
        else:
            print("Step not saved.")
            self.step_saved = False

            self.reset_projection_border_color("red")

    def undo_step_button_pressed(self):
        """
        Undo the last step.
        """
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
        """
        Save the manual.
        """
        saved = self.save_manual()

        if not saved:
            return
        
        manual_confirm = QMessageBox.question(
            self, 
            "Save Manual", 
            "Want to create another manual?", 
            QMessageBox.Yes | QMessageBox.No
        )

        if manual_confirm == QMessageBox.Yes:
            self.reset_manual_creator()
        else:
            self.status_label.setText("Creation of manuals stopped.")
            self.stop_live_feed_button_pressed()
            self.stacked_widget.setCurrentIndex(0)       

    def reset_manual_creator(self) -> None:
        """
        Reset the manual creator to create a new manual.
        """
        self.manual_saved = False
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
        self.image_with_drawings_path = None

        self.reset_projection_border_color("red")

        self.show_message(f"New manual initialized at {self.current_manual_dir}", title="Information", message_type="info")

    def create_step(self, drawing_path) -> None:
        """
        Creates a step with the drawing path.

        :param drawing_path: The path to the drawing image.
        """
        drawing_path = str(Path(drawing_path).as_posix())
        self.steps.append({
            "step": self.step_number,
            "description": self.step_description,
            "raw_image_path": str(Path(self.last_raw_image_path).as_posix()),
            "drawing_path": drawing_path,
            "3D_points_tag_shape": self.points_3D_tag.shape,
            "3D_points_tag_dtype": str(self.points_3D_tag.dtype),
            "3D_points_tag_data": self.points_3D_tag.tolist(),
            "colors_bgr_shape": self.valid_colors.shape,
            "colors_bgr_dtype": str(self.valid_colors.dtype),
            "colors_bgr_data": self.valid_colors.tolist()
        })
        # print(f"Shape of 3D Points before: {self.points_3D_tag.shape}")
        # print(f"Shape of Colors before: {self.valid_colors.shape}")
        self.show_message(f"Step {self.step_number} saved successfully!", title="Information", message_type="info")

    def undo_last_step(self):
        """
        Undo the last step.
        """
        if self.steps:
            removed_step = self.steps.pop()
            self.step_number -= 1

            drawing_path = Path(removed_step["drawing_path"])
            if drawing_path.exists():
                drawing_path.unlink()  # Delete the file
                print(f"Deleted file: {drawing_path}")

            if self.last_raw_image_path and Path(self.last_raw_image_path).exists():
                Path(self.last_raw_image_path).unlink()
                print(f"Deleted raw image file: {self.last_raw_image_path}")

            # Reset the projection image
            self.reset_projection_border_color("red")

            self.show_message(f"Step {removed_step['step']} has been removed.", title="Information", message_type="info")
        else:
            self.show_message("No steps to undo.", title="Warning", message_type="warning")

    def save_manual(self) -> bool:
        """
        Saves the manual as a JSON file
        """
        if self.tag_id is None:
            self.show_message("No tag ID found, manual not saved.", title="Warning", message_type="warning")
            return False
        
        if len(self.steps) == 0:
            self.show_message("No steps found, manual not saved.", title="Warning", message_type="warning")
            return False
        
        manual_name = f"manual_{self.manual_count}"

        manual_data = {
            "manual": manual_name,
            "tag_id": self.tag_id,
            "steps": self.steps,
            "created_at": datetime.now().isoformat()
        }
        json_path = self.current_manual_dir / f"{manual_name}.json"

        try:
            with open(json_path, "w") as file:
                json.dump(manual_data, file, indent=4)

            self.show_message(f"Manual saved at {json_path} for AprilTag ID {self.tag_id}.", title="Information", message_type="info")
            self.manual_saved = True
            return True
        except Exception as e:
            self.show_message(f"Error saving manual: {e}", title="Error", message_type="error")
            self.manual_saved = False
            return False

    def show_message(self, message, title="Message", message_type="info", duration=3000):
        """
        Show a message box with the given message.

        :param message: The message to display.
        :param title: The title of the message box.
        :param message_type: The type of the message (info, warning, error).
        :param duration: The duration to show the message in milliseconds.
        """
        msg_box = QMessageBox(self)
        
        # Set the icon based on the message type
        if message_type == "info":
            msg_box.setIcon(QMessageBox.Information)
        elif message_type == "warning":
            msg_box.setIcon(QMessageBox.Warning)
        elif message_type == "error":
            msg_box.setIcon(QMessageBox.Critical)
        else:
            msg_box.setIcon(QMessageBox.NoIcon)

        msg_box.setText(message)
        msg_box.setWindowTitle(title)
        msg_box.setStandardButtons(QMessageBox.NoButton)  # No buttons

        # Close the message box after the given duration
        QTimer.singleShot(duration, msg_box.accept)
        msg_box.show()

    def show_manuals_in_list(self):
        """
        Show the manuals with the given AprilTag ID in the list.
        """
        # Get the AprilTag ID from the input field
        search_tag_id = self.tag_id_input_field.text().strip()

        # Check if the input is valid
        if not search_tag_id:
            self.show_message("Please enter a valid AprilTag ID.", title="Warning", message_type="warning")
            return

        # Clear the list
        self.manuals_list.clear()

        manual_found = False

        # Search for the manual with the given tag ID
        for manual_dir in self.base_manuals_dir.iterdir():
            if manual_dir.is_dir():
                json_path = manual_dir / f"{manual_dir.name}.json"

                if json_path.exists():
                    try:
                        # Read the JSON file
                        with open(json_path, "r") as file:
                            manual_data = json.load(file)

                        # Check if the tag ID matches
                        if str(manual_data.get("tag_id")) == search_tag_id:
                            self.manuals_list.addItem(manual_dir.name)
                            manual_found = True

                    except Exception as e:
                        self.show_message(f"Error reading manual: {e}", title="Error", message_type="error")
        
        # if no manuals are found, show a message
        if not manual_found:
            self.show_message("No manuals found for the entered Tag ID.", title="Information", message_type="info")

        # If no manuals are created yet, show a message
        if not any(self.base_manuals_dir.iterdir()):
            self.show_message("No manuals available. Please create a manual first.", title="Information", message_type="info")

    def create_manual_button_clicked(self):
        """
        Create a new manual.
        """
        self.stacked_widget.setCurrentIndex(1)
        self.reset_manual_creator()

    def quit_button_manual_creation_page_clicked(self):
        """
        Quit the manual creation page.
        """
        if not self.manual_saved:
            quit_confirm = QMessageBox.question(
                self, 
                "Quit", 
                "Are you sure you want to quit without saving the manual?", 
                QMessageBox.Yes | QMessageBox.No
            )

            if quit_confirm == QMessageBox.Yes:
                # Delete the manual directory if it exists
                if self.current_manual_dir.exists():
                    try:
                        shutil.rmtree(self.current_manual_dir)
                        self.manual_count -= 1
                        print(f"Deleted manual directory: {self.current_manual_dir}")
                    except Exception as e:
                        self.show_message(f"Error deleting manual directory: {e}", title="Error", message_type="error")
                
                self.stop_live_feed_button_pressed()
                self.stacked_widget.setCurrentIndex(0)

        else:
            self.stop_live_feed_button_pressed()
            self.stacked_widget.setCurrentIndex(0)

    def load_manual(self, item):
        """
        Load the selected manual from the list.
        """
        manual_name = item.text()
        manual_path = self.base_manuals_dir / manual_name
        json_path = manual_path / f"{manual_name}.json"

        if json_path.exists():
            try:
                with open(json_path, "r") as file:
                    manual_data = json.load(file)

                self.execution_steps = manual_data.get("steps")
                self.tag_id = manual_data.get("tag_id")
                self.current_execution_step_index = 0
                self.extracted_3D_pixels = False

                self.show_message(f"Manual loaded: {manual_name} for AprilTag ID: {self.tag_id}", title="Information", message_type="info")

                self.stacked_widget.setCurrentIndex(3)
            except Exception as e:
                self.show_message(f"Error loading manual: {e}", title="Error", message_type="error")

    def display_current_step(self):
        """
        Display the current step of the manual.
        """
        # Show the instruction of the current step
        instruction_description = self.execution_steps[self.current_execution_step_index]["description"]
        self.step_instruction_label.setText(f"Step {self.current_execution_step_index + 1} of {len(self.execution_steps)}: {instruction_description}")

        # Update the progress bar, activity diagram, and buttons
        self.load_instruction()
        self.update_progress_bar()
        self.update_activity_diagram()
        self.update_manual_execution_buttons()

    def update_progress_bar(self):
        """
        Update the progress bar of the manual execution.
        """
        # Update the progress bar
        self.progress_bar.setMaximum(len(self.execution_steps))
        self.progress_bar.setValue(self.current_execution_step_index)

    def update_activity_diagram(self):
        """
        Update the activity diagram of the manual execution.
        """
        self.activity_diagram_scene.clear()
        total_steps = len(self.execution_steps)
        step_spacing = 100
        circle_radius = 20

        for i in range(total_steps):
            # Circle for each step
            circle = QGraphicsEllipseItem(i * step_spacing, 50, circle_radius, circle_radius)
            circle.setBrush(QBrush(Qt.gray) if i != self.current_execution_step_index else QBrush(Qt.green))
            self.activity_diagram_scene.addItem(circle)

            # Step label
            step_label = QGraphicsTextItem(f"Step {i + 1}")
            step_label.setPos(i * step_spacing, 80)
            self.activity_diagram_scene.addItem(step_label)

            # Line between circles
            if i > 0:
                line = QGraphicsLineItem((i - 1) * step_spacing + circle_radius, 60, i * step_spacing, 60)
                line.setPen(QPen(Qt.black, 2))
                self.activity_diagram_scene.addItem(line)

    def update_manual_execution_buttons(self):
        """
        Update the buttons of the manual execution page.
        """
        # Update the buttons based on the current step
        self.previous_step_button.setVisible(self.current_execution_step_index > 0)
        self.next_step_button.setVisible(self.current_execution_step_index < len(self.execution_steps) - 1)
        self.finish_button.setVisible(self.current_execution_step_index == len(self.execution_steps) - 1)

    def next_step(self):
        """
        Go to the next step of the manual.
        """
        if self.current_execution_step_index < len(self.execution_steps):
            self.current_execution_step_index += 1
            self.display_current_step()

    def previous_step(self):
        """
        Go to the previous step of the manual.
        """
        if self.current_execution_step_index > 0:
            self.current_execution_step_index -= 1
            self.display_current_step()

    def finish_manual(self):
        """
        Finish the manual execution.
        """
        self.progress_bar.setValue(len(self.execution_steps))  # Set the progress bar to 100%
        self.step_instruction_label.setText("Manual completed! 🎉")
        self.next_step_button.hide()
        self.previous_step_button.hide()
        self.finish_button.hide()

    def quit_button_manual_execution_page_clicked(self):
        """
        Quit the manual execution page.
        """
        self.points_3D_tag = None
        self.valid_colors = None
        
        self.reset_projection_border_color("red")
        self.stop_live_feed_button_pressed()
        
        self.stacked_widget.setCurrentIndex(0)

    def load_instruction(self):    
        """
        Load the instruction for the current step.
        """    
        instruction_path = self.execution_steps[self.current_execution_step_index]["drawing_path"]

        if instruction_path is None:
            self.show_message("No instruction found for this step.", title="Error", message_type="error")
            return
        
        # points_3D_tag_shape = self.execution_steps[self.current_execution_step_index]["3D_points_tag_shape"]
        points_3D_tag_dtype = self.execution_steps[self.current_execution_step_index]["3D_points_tag_dtype"]
        points_3D_tag_data = self.execution_steps[self.current_execution_step_index]["3D_points_tag_data"]

        # colors_bgr_shape = self.execution_steps[self.current_execution_step_index]["colors_bgr_shape"]
        colors_bgr_dtype = self.execution_steps[self.current_execution_step_index]["colors_bgr_dtype"]
        colors_bgr_data = self.execution_steps[self.current_execution_step_index]["colors_bgr_data"]

        # print(f"Shape of 3D Points after: {points_3D_tag_shape}")
        # print(f"Shape of Colors after: {colors_bgr_shape}")

        self.points_3D_tag = np.array(points_3D_tag_data, dtype=points_3D_tag_dtype)
        self.valid_colors = np.array(colors_bgr_data, dtype=colors_bgr_dtype)
        
        if self.points_3D_tag is not None and self.valid_colors is not None:
            self.extracted_3D_pixels = True
            self.show_message(f"3D points loaded successfully. Number of Points: {len(self.points_3D_tag)}", title="Information", message_type="info")
        else:
            self.show_message("Error in 3D point loading. Please check the image and parameters.", title="Error", message_type="error")
            return