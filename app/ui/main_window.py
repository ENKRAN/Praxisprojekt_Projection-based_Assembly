import sys
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QMessageBox, QDialog, 
    QToolBar, QCheckBox, 
    QWidgetAction, QPushButton, QColorDialog, QWidget,
    QVBoxLayout, QLabel, QSizePolicy, QSpinBox
)
from PyQt6.QtGui import QIcon, QColor, QFont, QAction
from PyQt6.QtCore import Qt, QSize, QTimer

# Core / Configuration
from app.core.config import Config
from app.core.flowchart_manager import FlowchartManager
from app.core.manual_manager import ManualManager

# Vision / Hardware
from app.vision.worker import VisionWorker
from app.rendering.projector_window import ProjectorWindow

# UI Components & Pages
from app.ui.components.screen_selector import ScreenSelectorDialog
from app.ui.components.dialogs import PopupDialog
from app.ui.pages.start_page import StartPage
from app.ui.pages.creation_page import CreationPage
from app.ui.pages.node_selection_page import NodeSelectionPage
from app.ui.pages.drawing_page import DrawingPage
from app.ui.components.drawing.palette import PaletteHorizontal, PALETTES, PaletteGrid
from app.ui.components.camera_view import CameraView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AR Assembly System - Control")
        
        # 1. Load Configuration
        try:
            Config.loadCalibration("data/projector_camera_calibration/calibration.yml")
        except Exception as e:
            print(f"Error loading calibration: {e}")
            # We don't exit here strictly, to allow UI testing without calib
        
        # 2. Logic Managers
        self.flowchart_manager = FlowchartManager() 
        self.manual_manager = ManualManager()
        
        # Temp Data Storage (RAM) for the current step being created
        self.current_snapshot = None     # The image (NumPy Array)
        self.current_homography = None   # The matrix
        self.current_node_type = None    # The selected node type (e.g., "operation")
        self.current_tag_id = -1         # ID of the tag in the snapshot
        self.step_counter = 1            # Counter for step IDs
        self.pending_step_data = None

        # 3. Setup Hardware & Windows
        self.vision_worker = VisionWorker()
        self.projector_window = ProjectorWindow()
        self.camera_view = CameraView()  # Shared Camera View for CreationPage
        
        # Screen Setup via Dialog
        if not self.setupScreens():
            sys.exit(0)
        
        # 5. GUI Stack Setup
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Initialize Pages
        self.initPages()
        
        # setup Vision Worker Connections (after screens are setup, before UI is created)
        self.setup_vision_worker_connections()

        # Initialize Toolbars (must happen after pages are created)
        self.createDrawingToolbars()

        # Connect Stack Change to Toolbar Visibility
        self.stack.currentChanged.connect(self.updateToolbarVisibility)
        
        # Trigger initial toolbar check
        self.updateToolbarVisibility(self.stack.currentIndex())

    def initPages(self):
        self.setGlobalStyling()

        # Page 0: Start Page
        self.start_page = StartPage()
        self.start_page.create_manual_clicked.connect(self.onRequestCreateManual)
        self.start_page.load_manual_clicked.connect(self.gotoLoadPage) # TODO: Implement Load Page and connect properly
        self.start_page.quit_clicked.connect(self.close)
        self.stack.addWidget(self.start_page)
        
        # Page 1: Creation Page (Live Camera)
        self.creation_page = CreationPage(self.camera_view)
        self.creation_page.start_live_clicked.connect(self.onStartLive)
        self.creation_page.stop_live_clicked.connect(self.onStopLive)
        self.creation_page.capture_clicked.connect(self.onCapture)
        self.creation_page.save_step_clicked.connect(self.onConfirmStep)
        self.creation_page.undo_step_clicked.connect(self.onDiscardStep)
        self.creation_page.quit_clicked.connect(self.gotoStartPage)
        self.stack.addWidget(self.creation_page)
        
        # Page 2: Node Selection Page
        self.node_selection_page = NodeSelectionPage()
        self.node_selection_page.node_selected.connect(self.onNodeSelected)
        self.node_selection_page.back_clicked.connect(self.gotoCreationPage)
        self.stack.addWidget(self.node_selection_page)
        
        # Page 3: Drawing Page
        self.drawing_page = DrawingPage()
        self.drawing_page.save_clicked.connect(self.onDrawingFinished)
        self.drawing_page.cancel_clicked.connect(self.gotoCreationPage)
        self.drawing_page.tool_selected.connect(self.onToolSelected)
        self.drawing_page.selection_changed.connect(self.onToolSelectionChanged)
        self.stack.addWidget(self.drawing_page)

    def setGlobalStyling(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2e3440;
            }
            QToolBar {
                background-color: #3b4252;
            }
            QWidget#shadow_widget {
                background-color: #3b4252;
                border-radius: 15px;
            }
            QPushButton {
                background-color: #434c5e; 
                color: white; 
                border: 2px solid #d8dee9;
                border-radius: 15px;
            }
            QPushButton:pressed {
                background-color: #2e3440;
            }
            QMessageBox {
                background-color: #2e3440; 
            }
            QMessageBox QLabel {
                color: #eceff4;
                font-size: 14px;
            }
            QMessageBox QPushButton {
                min-width: 80px;
                padding: 5px;
                border-radius: 8px;
            }
        """)

    def setup_vision_worker_connections(self):
        # 4. Connect Vision -> Projector
        self.vision_worker.pose_update_signal.connect(self.projector_window.gl_widget.updateTagPose)
        self.vision_worker.baking_update_signal.connect(self.projector_window.gl_widget.setBakingMatrix)
        
        # Connect Vision -> MainWindow (Catch Snapshot)
        self.vision_worker.baking_update_signal.connect(self.onSnapshotTaken)
        self.vision_worker.image_update_signal.connect(self.camera_view.setImage)
        self.vision_worker.status_signal.connect(self.creation_page.updateStatus)
        
        # Connect the critical error signal
        self.vision_worker.error_signal.connect(self.creation_page.onCameraError)

    def createDrawingToolbars(self):
        """
        Creates the toolbars exactly like in legacy drawing_tool.py.
        Uses icons if available, matches CSS styling.
        """
        ### --- Tools Toolbars ---

        # Toolbar for tools like brush, rectangle, circle, arrow
        self.tools_toolbar = QToolBar("Tools")

        self.tools = {
            'select': 'Select',
            'scale': 'Scale',
            'erase': 'Erase',
            'nodes': 'Nodes',
            'brush': 'Brush',
            'rectangle': 'Rectangle',
            'circle': 'Circle',
            'arrow': 'Arrow',
            'text': 'Text'
        }

        icon_path = "app/resources/icons/toolbar"

        # Actions for tool shapes
        for tool, text in self.tools.items():
            action = QAction(text, self)
            action.setCheckable(True)
            action.setIcon(QIcon(f"{icon_path}/{tool}.svg"))
            action.triggered.connect(lambda checked, t=tool: self.drawing_page.setTool(t))
            self.tools_toolbar.addAction(action)
            if tool == 'brush':
                action.setChecked(True)

        self.tools_toolbar.setIconSize(QSize(64, 64))  # Kleinere Icons

        self.text_size_spinbox = QSpinBox(self)
        self.text_size_spinbox.setRange(1, 50)
        self.text_size_spinbox.setValue(self.drawing_page.text_size)  # Default text size
        self.text_size_spinbox.setSuffix(" pt")
        self.text_size_spinbox.setStyleSheet("""
            QSpinBox {
                font-size: 24px;
                padding: 5px;
                min-height: 40px;
                border: 2px solid #4c566a;
                border-radius: 5px;
                background-color: #d8dee9;
                color: #2e3440;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 25px;
                height: 20px;
            }
        """)
        self.text_size_spinbox.valueChanged.connect(self.drawing_page.handleTextSizeChange)

        self.text_size_action = QWidgetAction(self)
        self.text_size_action.setDefaultWidget(self.text_size_spinbox)
        self.tools_toolbar.addAction(self.text_size_action)

        self.tools_toolbar.addSeparator()

        self.delete_action = QAction("Delete", self)
        self.delete_action.setIcon(QIcon(f"{icon_path}/delete.svg")) 
        self.delete_action.triggered.connect(self.drawing_page.deleteSelected)
        self.tools_toolbar.addAction(self.delete_action)
        self.delete_action.setVisible(False)

        ### --- Fill Shape Toolbar ---

        # Toolbar for Checkbox to fill shapes
        self.fill_shape_toolbar = QToolBar("Fill Shape", self)

        # Checkbox to toggle fill shape
        self.fill_shape_checkbox = QCheckBox("Fill Shape", self)
        self.fill_shape_checkbox.setStyleSheet("QCheckBox::indicator { width: 50px; height: 50px;}")
        self.fill_shape_checkbox.setChecked(self.drawing_page.fill_shape)
        self.fill_shape_checkbox.toggled.connect(self.drawing_page.toggleFillShape)
        
        self.fill_action = QWidgetAction(self)
        self.fill_action.setDefaultWidget(self.fill_shape_checkbox)
        self.fill_shape_toolbar.addAction(self.fill_action)

        ### --- End of Fill Shape Toolbar ---

        ### --- Color Selection Toolbar ---

        chosen_palette_name = 'paired12' # You can choose 'paired12', 'category10', or '17undertones' here
        if chosen_palette_name in PALETTES and PALETTES[chosen_palette_name]:
            self.drawing_page.pen_color = QColor(PALETTES[chosen_palette_name][0])
        else:
            self.drawing_page.pen_color = QColor(Qt.GlobalColor.white) # Fallback

        # Toolbar for color selection
        self.colors_toolbar = QToolBar("Colors", self)
        
        # Use a palette from palette.py, e.g., PaletteHorizontal, PaletteGrid, or PaletteVertical
        color_palette = PaletteGrid(chosen_palette_name, n_columns=5)
        # color_palette = PaletteHorizontal(chosen_palette_name) 
        color_palette.selected.connect(self.drawing_page.setPenColor)
        self.colors_toolbar.addWidget(color_palette)

        ### --- End of Color Selection Toolbar ---

        # Save button centered
        save_button = QPushButton("Save", self)
        save_button.setFont(QFont("Arial", 20))
        save_button.setMinimumSize(200, 100)
        save_button.clicked.connect(self.drawing_page.saveStep)

        save_action = QWidgetAction(self)
        save_action.setDefaultWidget(save_button)
        self.save_button_toolbar = QToolBar("Save", self)
        self.save_button_toolbar.addAction(save_action)

        merge_branch_button = QPushButton("Merge with previous branch", self)
        merge_branch_button.setFont(QFont("Arial", 20))
        merge_branch_button.setMinimumSize(200, 100)
        merge_branch_button.clicked.connect(self.onMergeButtonClicked)

        self.merge_branch_action = QWidgetAction(self)
        self.merge_branch_action.setDefaultWidget(merge_branch_button)
        self.merge_branch_action.setVisible(False) # Initially hidden
        self.save_button_toolbar.addAction(self.merge_branch_action)

        vertical_layout_widget = QWidget()
        vertical_layout = QVBoxLayout(vertical_layout_widget)

        fixed_branch_label = QLabel("Current Branch: ")
        fixed_branch_label.setStyleSheet("color: white; font-size: 42px;")  # TODO: REMEMBER TO SET BACK TO 42PX
        self.dynamic_branch_label = QLabel(self.flowchart_manager._current_branch)
        self.dynamic_branch_label.setStyleSheet("color: white; font-size: 42px; margin-right: 20px;") # TODO: REMEMBER TO SET BACK TO 42PX
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        fixed_node_label = QLabel("Current Node: ")
        fixed_node_label.setStyleSheet("color: white; font-size: 42px;")  # TODO: REMEMBER TO SET BACK TO 42PX
        self.dynamic_node_label = QLabel(self.flowchart_manager.current_node.node_name)
        self.dynamic_node_label.setStyleSheet("color: white; font-size: 42px; margin-right: 20px;") # TODO: REMEMBER TO SET_BACK TO 42PX

        vertical_layout.addWidget(fixed_branch_label)
        vertical_layout.addWidget(self.dynamic_branch_label)
        vertical_layout.addWidget(fixed_node_label)
        vertical_layout.addWidget(self.dynamic_node_label)

        self.save_button_toolbar.addWidget(spacer)
        self.save_button_toolbar.addWidget(vertical_layout_widget)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tools_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.fill_shape_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.colors_toolbar)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.save_button_toolbar)

    def updateToolbarVisibility(self, index):
        """
        Shows toolbars only if current page is DrawingPage.
        Also toggles the visibility of the Merge Branch button based on flowchart state.

        Args:
            index (int): The index of the currently visible page in the stack.
        """
        current_widget = self.stack.widget(index)
        is_drawing = (current_widget == self.drawing_page)
        self.setToolbarsVisible(is_drawing)
        self.toggleMergeButton()

    def setToolbarsVisible(self, visible: bool):
        self.tools_toolbar.setVisible(visible)
        self.fill_shape_toolbar.setVisible(visible)
        self.colors_toolbar.setVisible(visible)
        self.save_button_toolbar.setVisible(visible)

    def onToolSelected(self, tool_key):
        # Update buttons visually
        for action in self.tools_toolbar.actions():
            if not isinstance(action, QWidgetAction) and action.text() in ['Select', 'Scale', 'Erase', 'Nodes', 'Brush','Rectangle','Circle','Arrow', 'Text']: # Check if not QWidgetAction
                action.setChecked(action.text() == {'select':'Select', 'scale':'Scale', 'erase':'Erase', 'nodes':'Nodes', 'brush':'Brush', 'rectangle':'Rectangle', 'circle':'Circle', 'arrow':'Arrow', 'text':'Text'}[tool_key])

        # Enable/disable fill_action based on the selected tool
        if tool_key in ['brush', 'rectangle', 'circle']:
            self.fill_action.setEnabled(True)
        else:
            self.fill_action.setEnabled(False)
            self.fill_shape_checkbox.setChecked(False) 
            if self.drawing_page.fill_shape:  # only update if it was true
                self.drawing_page.fill_shape = False

    def onToolSelectionChanged(self, num_selected):
        """
        Updates the visibility of the delete action based on the number of selected items.
        """
        self.delete_action.setVisible(num_selected >= 1)

    def openColorDialog(self):
        """Opens color picker and updates DrawingPage + Button Style."""
        color = QColorDialog.getColor(Qt.GlobalColor.white, self, "Select Color")
        if color.isValid():
            self.drawing_page.setPenColor(color)
            # Update Button Background to show selected color
            self.btn_color_ref.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color.name()}; 
                    color: white; 
                    border: 2px solid #d8dee9;
                    border-radius: 15px;
                    font-size: 16px;
                }}
            """)

    def onRequestCreateManual(self):
        """Opens a popup to enter the manual name."""
        dialog = PopupDialog(self, 
                             dialog_type="text_input", 
                             header="Create New Manual", 
                             placeholder_text="e.g. Pump_Assembly_V1")
        
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.user_input:
            title = dialog.user_input
            try:
                # Create Manual (Tag ID is initially -1/unknown)
                self.manual_manager.createNewManual(title, tag_id=-1)
                print(f"Manual '{title}' created successfully.")
                
                # Switch to Camera
                self.gotoCreationPage()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create manual:\n{e}")

    def onSnapshotTaken(self, homography, color_img, tag_id):
        """Called when VisionWorker takes a snapshot."""
        print(f"Snapshot received for Tag {tag_id}. Storing data...")
        
        self.current_homography = homography
        self.current_snapshot = color_img.copy()
        self.current_tag_id = tag_id

        self.onStopLive()
        
        # Proceed to selection page
        self.stack.setCurrentWidget(self.node_selection_page)

    def onNodeSelected(self, node_type: str, node: QWidget):
        """
        Called when the user selects an icon on the NodeSelectionPage.
        Transitions to DrawingPage.
        """
        # Guard: Is flowchart already done?
        if self.flowchart_manager.flowchart_done:
            print("Warning: Flowchart is already done.")
            QMessageBox.critical(self, "Flowchart Completed", "The flowchart is already completed. No more nodes can be added.")
            self.gotoCreationPage()
            return
        
        print(f"Node selected: {node_type}")
        self.current_node_type = node_type
        
        if self.current_snapshot is not None:
            popup = None
            popup_io_text = None

            if node_type in ["operation", "condition", "subroutine"]:
                popup = PopupDialog(self, dialog_type="text_input", header=f"{node_type.capitalize()} Description")
                result = popup.exec()

                if not popup.isPopupResultValid(result):
                    return
                
                self.current_node_data = popup.user_input
            elif node_type == "inputoutput":
                popup = PopupDialog(self, dialog_type="buttons", header="Choose Input/Output Type", button_count=2, button_texts=["input", "output"])
                result_io = popup.exec()

                if not popup.isPopupResultValid(result_io):
                    return
                
                popup_io_text = PopupDialog(self, dialog_type="text_input", header=f"{popup.user_input.capitalize()} Text")
                result_io_text = popup_io_text.exec()

                if not popup_io_text.isPopupResultValid(result_io_text):
                    return
                
                self.current_node_data = popup_io_text.user_input            
                
            node_added_success = self.flowchart_manager.addNode(node_type, popup, popup_io_text)

            if not node_added_success:
                QMessageBox.warning(self, "Error", "Could not add node to flowchart. Please try again.")
                return

            node.playAnimation()
            
            self.flowchart_manager.updateFlowchart()

            self.drawing_page.load_svg(self.flowchart_manager.output_svg_path)

            self.dynamic_node_label.setText(self.flowchart_manager.current_node.node_name) 
                
            # 1. Load image into Drawing Page
            self.drawing_page.loadSnapshot(self.current_snapshot)
            
            # 2. Switch View (Toolbars will appear automatically via updateToolbarVisibility)
            QTimer.singleShot(1000, lambda: self.stack.setCurrentWidget(self.drawing_page))  # Slight delay to ensure snapshot is loaded first
        else:
            QMessageBox.warning(self, "Error", "No snapshot available!")
            self.gotoCreationPage()

    def onMergeButtonClicked(self):
        merge_canditates = self.flowchart_manager.getMergeCandidates()

        popup_merge = PopupDialog(self, dialog_type="buttons", header="To which Condition Node do you want to connect to? (Branches will be merged)", button_count=len(merge_canditates), button_texts=[node.node_text for node in merge_canditates])
        result_merge = popup_merge.exec()

        if not popup_merge.isPopupResultValid(result_merge):
            return
        
        selected_node = popup_merge.user_input
        print(f"User selected to merge with node: {selected_node}")

        merge_success = self.flowchart_manager.mergeWithCondition(selected_node)

        if not merge_success:
            QMessageBox.warning(self, "Merge Failed", "Could not merge branches. Please try again.")

        self.toggleMergeButton()

        self.flowchart_manager.updateFlowchart()
        self.drawing_page.load_svg(self.flowchart_manager.output_svg_path)

    def toggleMergeButton(self):
        merge_possible = self.flowchart_manager.checkMergePossibility()
        if merge_possible:
            self.merge_branch_action.setVisible(True)
        else:
            self.merge_branch_action.setVisible(False)

    def onDrawingFinished(self, temp_svg_path: str):
        """
        Called when 'Save' is clicked in DrawingPage.
        Uses ManualManager to persist data.
        """
        print("Drawing finished. Switching to Review Mode...")
        
        self.pending_step_data = {
            "temp_svg_path": temp_svg_path,
            "node_type": self.current_node_type,
            "node_data": getattr(self, 'current_node_data', None), 
            "snapshot": self.current_snapshot,
            "homography": self.current_homography,
            "tag_id": self.current_tag_id
        }

        self.projector_window.loadInstruction(temp_svg_path)

        self.creation_page.showReviewUI(True)

        self.gotoCreationPage()

    def onConfirmStep(self):
        """
        Called when user confirms the step in CreationPage after reviewing the projection.
        """
        if not self.pending_step_data:
            return

        print("Confirming Step... Saving to disk.")
        try:
            data = self.pending_step_data
            
            desc = f"Step {self.step_counter}: {data['node_type']}"
            if data.get('node_data'):
                desc = str(data['node_data'])

            self.manual_manager.saveStep(
                step_id=self.step_counter,
                node_uid=f"node_{self.step_counter}",
                node_type=data['node_type'],
                description=desc,
                snapshot_img=data['snapshot'],
                svg_source_path=data['temp_svg_path'],
                homography=data['homography'],
                tag_id=data['tag_id']
            )

            # Cleanup
            self.step_counter += 1
            self.pending_step_data = None
            
            self.creation_page.showReviewUI(False)
            
            self.projector_window.clearProjection() 

            print("Step successfully saved.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save step: {e}")

    def onDiscardStep(self):
        """
        Called when user discards the step in CreationPage after reviewing the projection.
        """
        print("Discarding current step...")
        
        # 1. Delete pending data to reset state (if user goes back to creation page without confirming, it should be like they never took a snapshot or selected a node)
        self.pending_step_data = None
        
        # 2. Reset CreationPage UI to initial state (disable buttons, reset status, etc.)
        self.creation_page.showReviewUI(False)
        
        # 3. Clear Projector (remove the rejected instruction from the projector)
        self.projector_window.clearProjection()
        
        # 4. Go back to Creation Page with live feed active, so user can try again immediately if they want
        self.onStartLive()

    def setupScreens(self):
        gui_screen, proj_screen, is_debug = ScreenSelectorDialog.get_screens()
        
        if not gui_screen or not proj_screen:
            return False

        if is_debug:
            print("Starting in DEBUG MODE (Windowed)")
            test_image = "app/resources/debug/debug_frame.png" 
            self.vision_worker.setDebugMode(True, test_image)

            self.move(gui_screen.geometry().x() + 50, gui_screen.geometry().y() + 50)
            self.resize(3840, 2160)
            self.show()
            
            self.projector_window.move(proj_screen.geometry().x() + 100, proj_screen.geometry().y() + 100)
            self.projector_window.resize(1280, 720)
            self.projector_window.show()
        else:
            print("Starting in PRODUCTION MODE (Fullscreen)")
            self.vision_worker.setDebugMode(False)
            self.setGeometry(gui_screen.geometry())
            self.showFullScreen()
            
            self.projector_window.setGeometry(proj_screen.geometry())
            self.projector_window.showFullScreen()
            
        return True

    def onStartLive(self):
        if not self.vision_worker.isRunning():
            self.creation_page.status_label.setText("Status: Starting Camera...")
            self.vision_worker.start()
            self.creation_page.status_label.setText("Status: Camera Running")
            self.creation_page.setButtonsState(running=True)
        else:
            self.creation_page.status_label.setText("Status: Camera already running")

    def onStopLive(self):
        if self.vision_worker.isRunning():
            self.creation_page.status_label.setText("Status: Stopping Camera...")
            self.vision_worker.stop()
            self.creation_page.status_label.setText("Status: Live Feed Stopped")
            self.creation_page.camera_view.clear()
            self.creation_page.setButtonsState(running=False)
        else:
            self.creation_page.status_label.setText("Status: Camera is not running")

    def onCapture(self):
        if self.vision_worker.isRunning():
            self.creation_page.status_label.setText("Status: Capturing Photo...")
            self.vision_worker.triggerSnapshot()
        else:
             self.creation_page.status_label.setText("Status: Cannot capture - Camera not running")

    def gotoCreationPage(self):
        self.stack.setCurrentWidget(self.creation_page)
        
    def gotoStartPage(self):
        self.stack.setCurrentWidget(self.start_page)

    def gotoLoadPage(self):
        print("Load Page not implemented yet.")

    def closeEvent(self, event):
        self.vision_worker.stop()
        self.projector_window.close()
        event.accept()