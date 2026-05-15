import sys
import json
import numpy as np
import shutil

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
from app.core.player_manager import PlayerManager
from app.core.remote_server import RemoteSVGServer

# Vision / Hardware
from app.vision.worker import VisionWorker
from app.rendering.projector_window import ProjectorWindow

# UI Components & Pages
from app.ui.pages.start_page import StartPage
from app.ui.pages.creation_page import CreationPage
from app.ui.pages.node_selection_page import NodeSelectionPage
from app.ui.pages.drawing_page import DrawingPage
from app.ui.pages.load_page import LoadPage
from app.ui.pages.player_page import PlayerPage
from app.ui.pages.remote_page import RemotePage
from app.ui.pages.ai_generation_page import AIGenerationPage
from app.core.ai_ssh_client import AIGenerationWorker, AIStepNavigationWorker
from app.ui.components.screen_selector import ScreenSelectorDialog
from app.ui.components.dialogs import PopupDialog
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
        self.player_manager = PlayerManager()

        # --- Remote Assistance Setup ---
        self.current_live_tag_id = None

        self.remote_server = RemoteSVGServer()
        self.remote_server.client_connected.connect(self.onRemoteClientConnected)
        self.remote_server.client_disconnected.connect(self.onRemoteClientDisconnected)
        self.remote_server.svg_received.connect(self.onRemoteSvgReceived)
        
        # Temp Data Storage (RAM) for the current step being created
        self.current_snapshot = None     # The image (NumPy Array)
        self.current_homography = None   # The matrix
        self.current_node_type = None    # The selected node type (e.g., "operation")
        self.current_tag_id = -1         # ID of the tag in the snapshot
        self.step_counter = 1            # Counter for step IDs
        self.pending_step_data = None
        self.confirmed_flowchart_actions = []
        self.pending_flowchart_actions = []

        # 3. Setup Hardware & Windows
        self.vision_worker = VisionWorker()
        self.projector_window = ProjectorWindow()
        self.camera_view = CameraView()  # Camera View for CreationPage
        self.player_camera_view = CameraView() # Separate Camera View for PlayerPage to avoid conflicts
        self.remote_camera_view = CameraView() # Separate Camera View for RemotePage to avoid conflicts
        self.ai_camera_view = CameraView()     # Separate Camera View for AIGenerationPage
        self.ai_worker = None           # AIGenerationWorker or AIStepNavigationWorker
        self._ai_step_num = 0           # 1-based counter displayed to the user
        self._ai_pending_action = "generate"  # "generate" | "next" | "prev"
        self._ai_is_last = False        # tracks is_last from the most recent step
        
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
        self.start_page.load_manual_clicked.connect(self.gotoLoadPage)
        self.start_page.remote_assistance_clicked.connect(self.gotoRemotePage)
        self.start_page.ai_generation_clicked.connect(self.gotoAIGenerationPage)
        self.start_page.quit_clicked.connect(self.close)
        self.stack.addWidget(self.start_page)

        # Page 1: Load Page
        self.load_page = LoadPage()
        self.load_page.back_clicked.connect(self.gotoStartPage)
        self.load_page.manual_selected.connect(self.onManualSelectedForPlayback)
        self.stack.addWidget(self.load_page)
        
        # Page 2: Creation Page (Live Camera)
        self.creation_page = CreationPage(self.camera_view)
        self.creation_page.start_live_clicked.connect(self.onStartLive)
        self.creation_page.stop_live_clicked.connect(self.onStopLive)
        self.creation_page.capture_clicked.connect(self.onCapture)
        self.creation_page.save_step_clicked.connect(self.onConfirmStep)
        self.creation_page.undo_step_clicked.connect(self.onDiscardStep)
        self.creation_page.finish_manual_clicked.connect(self.onFinishManual)
        self.creation_page.quit_clicked.connect(self.gotoStartPage)
        self.stack.addWidget(self.creation_page)
        
        # Page 3: Node Selection Page
        self.node_selection_page = NodeSelectionPage()
        self.node_selection_page.node_selected.connect(self.onNodeSelected)
        self.node_selection_page.back_clicked.connect(self.gotoCreationPage)
        self.stack.addWidget(self.node_selection_page)
        
        # Page 4: Drawing Page
        self.drawing_page = DrawingPage()
        self.drawing_page.save_clicked.connect(self.onDrawingFinished)
        self.drawing_page.cancel_clicked.connect(self.gotoCreationPage)
        self.drawing_page.tool_selected.connect(self.onToolSelected)
        self.drawing_page.selection_changed.connect(self.onToolSelectionChanged)
        self.stack.addWidget(self.drawing_page)

        # Page 5: Player Page
        self.player_page = PlayerPage(self.player_camera_view)
        self.player_page.quit_clicked.connect(self.quitPlayer)
        self.player_page.prev_clicked.connect(self.goBackPlayer)
        self.player_page.next_clicked.connect(lambda: self.advancePlayer("next"))
        self.player_page.yes_clicked.connect(lambda: self.advancePlayer("Yes"))
        self.player_page.no_clicked.connect(lambda: self.advancePlayer("No"))
        self.player_page.finish_clicked.connect(self.quitPlayer)
        self.stack.addWidget(self.player_page)

        # --- Page 6: Remote Assistance Page ---
        self.remote_page = RemotePage(self.remote_camera_view)
        self.remote_page.quit_clicked.connect(self.quitRemoteMode)
        self.remote_page.snapshot_clicked.connect(self.vision_worker.triggerSnapshot)
        self.stack.addWidget(self.remote_page)

        # --- Page 7: AI Generation Page ---
        self.ai_generation_page = AIGenerationPage(self.ai_camera_view)
        self.ai_generation_page.generate_clicked.connect(self.onAIGenerateRequested)
        self.ai_generation_page.next_step_clicked.connect(self.onAINextStep)
        self.ai_generation_page.prev_step_clicked.connect(self.onAIPrevStep)
        self.ai_generation_page.new_generation_clicked.connect(self.onAINewGeneration)
        self.ai_generation_page.back_clicked.connect(self.onAIBack)
        self.stack.addWidget(self.ai_generation_page)

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
        self.vision_worker.plane_update_signal.connect(self.projector_window.gl_widget.updateTablePlane)
        
        # Connect Vision -> MainWindow (Catch Snapshot)
        self.vision_worker.baking_update_signal.connect(self.onSnapshotTaken)
        self.vision_worker.image_update_signal.connect(self.camera_view.setImage)
        self.vision_worker.status_signal.connect(self.creation_page.updateStatus)
        
        # Connect the critical error signal
        self.vision_worker.error_signal.connect(self.creation_page.onCameraError)

        # Also connect Vision -> PlayerPage's Camera View to show live feed during playback
        self.vision_worker.image_update_signal.connect(self.camera_view.setImage)
        self.vision_worker.image_update_signal.connect(self.player_camera_view.setImage)

        # Connect Vision -> RemotePage's Camera View to show live feed during remote assistance
        self.vision_worker.image_update_signal.connect(self.remote_camera_view.setImage)
        # Connect Vision -> AIGenerationPage's Camera View
        self.vision_worker.image_update_signal.connect(self.ai_camera_view.setImage)
        self.vision_worker.pose_update_signal.connect(self.updateLiveTagId)

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
        """Asks the user whether to create a new manual or resume a draft."""
        dialog = PopupDialog(self, dialog_type="buttons", header="What do you want to do?", 
                             button_count=2, button_texts=["Start New Manual", "Resume Draft"])
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.user_input == "Start New Manual":
                self.startNewManualFlow()
            elif dialog.user_input == "Resume Draft":
                self.resumeDraftFlow()

    def startNewManualFlow(self):
        dialog = PopupDialog(self, dialog_type="text_input", header="Create New Manual", placeholder_text="e.g. Pump_Assembly_V1")
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.user_input:
            title = dialog.user_input
            try:
                self.manual_manager.createNewManual(title, tag_id=-1)
                
                # IMPORTANT: Reset flowchart manager and action logs when starting a new manual
                self.confirmed_flowchart_actions = []
                self.pending_flowchart_actions = []
                self.flowchart_manager = FlowchartManager()
                self.step_counter = 1
                
                self.gotoCreationPage()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create manual:\n{e}")

    def resumeDraftFlow(self):
        # 1. List available drafts
        drafts = self.manual_manager.listManuals(status_filter="draft")
        if not drafts:
            QMessageBox.information(self, "No Drafts", "There are currently no unfinished drafts.")
            return
        
        # 2. Show selection dialog
        titles = [d[1] for d in drafts]
        dialog = PopupDialog(self, dialog_type="buttons", header="Select Draft to Resume", 
                             button_count=len(titles), button_texts=titles)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_title = dialog.user_input
            selected_id = next(d[0] for d in drafts if d[1] == selected_title)
            self.loadDraftIntoWorkspace(selected_id)

    def loadDraftIntoWorkspace(self, manual_id):
        """Loads a draft and replays the flowchart actions."""
        if not self.manual_manager.loadManualForEditing(manual_id):
            QMessageBox.critical(self, "Error", "Could not load draft files.")
            return

        self.confirmed_flowchart_actions = []
        self.pending_flowchart_actions = []
        self.flowchart_manager = FlowchartManager()

        # Load action-log and replay actions to reconstruct flowchart state
        flowchart_json_path = self.manual_manager.current_manual_dir / "flowchart.json"
        if flowchart_json_path.exists():
            try:
                with open(flowchart_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    actions = data.get("actions", [])
                
                # START TIMERAVEL REPLAY
                for action in actions:
                    if action[0] == "add":
                        self.flowchart_manager.addNode(action[1], action[2], action[3], action[4], action[5])
                    elif action[0] == "merge":
                        self.flowchart_manager.mergeWithCondition(action[1])
                
                self.confirmed_flowchart_actions = actions
                self.flowchart_manager.updateFlowchart()
            except Exception as e:
                print(f"Error replaying actions: {e}")

        # Set step counter to the next step after the last one in the loaded manual
        self.step_counter = len(self.manual_manager.current_manual.steps) + 1
        
        print(f"Draft loaded! Resuming at step {self.step_counter}")
        self.gotoCreationPage()

    def onSnapshotTaken(self, homography, color_img, tag_id):
        """Called when VisionWorker takes a snapshot."""
        print(f"Snapshot received for Tag {tag_id}. Storing data...")
        
        self.current_homography = homography
        self.current_snapshot = color_img.copy()
        self.current_tag_id = tag_id

        # Only navigate to NodeSelectionPage when triggered from the CreationPage.
        # On RemotePage the snapshot is used for projection baking only — no page switch.
        if self.stack.currentWidget() == self.remote_page:
            print("[Snapshot] Remote mode — skipping navigation to NodeSelectionPage.")
            return

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
                
            # 1. Extract text from popups
            text1 = popup.user_input if popup else ""
            text2 = popup_io_text.user_input if popup_io_text else ""
            if node_type in ["start", "end"]:
                text1 = ""

            node_uid = f"node_{self.step_counter}"
            step_folder = f"step_{self.step_counter:03d}"

            # 2. Add node to flowchart manager and get success status
            node_added_success = self.flowchart_manager.addNode(node_type, text1, text2, node_uid, step_folder)

            if not node_added_success:
                QMessageBox.warning(self, "Error", "Could not add node to flowchart.")
                return
            
            # 3. Store the action for later confirmation when user confirms the step in CreationPage (if they discard, we will revert this action in the flowchart manager)
            self.pending_flowchart_actions.append(("add", node_type, text1, text2, node_uid, step_folder))

            node.playAnimation()
            
            self.flowchart_manager.updateFlowchart()

            self.drawing_page.load_svg(self.flowchart_manager.output_svg_path)

            self.dynamic_node_label.setText(self.flowchart_manager.current_node.node_name) 
                
            # 1. Load image into Drawing Page, with tag boundary overlay so user knows where to draw
            import cv2
            snapshot_display = self.current_snapshot.copy()
            if self.current_homography is not None:
                H = self.current_homography
                corners_ideal = np.array([[1,1,1],[1,-1,1],[-1,-1,1],[-1,1,1]], dtype=np.float64).T
                corners_h = H @ corners_ideal
                corners_px = (corners_h[:2] / corners_h[2]).T.astype(np.int32)
                cv2.polylines(snapshot_display, [corners_px], True, (0, 255, 0), 3)
                center_h = H @ np.array([0.0, 0.0, 1.0])
                cx, cy = int(center_h[0]/center_h[2]), int(center_h[1]/center_h[2])
                cv2.drawMarker(snapshot_display, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 20, 3)
            self.drawing_page.loadSnapshot(snapshot_display)
            
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
            return
        
        self.pending_flowchart_actions.append(("merge", selected_node, "", ""))

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
        
        # Resume live tracking so the projection updates dynamically on the tag
        self.onStartLive()

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

            self.confirmed_flowchart_actions.extend(self.pending_flowchart_actions)
            self.pending_flowchart_actions.clear()

            self.manual_manager.saveFlowchartData(self.flowchart_manager.graph_data, self.confirmed_flowchart_actions)

            # Cleanup
            self.step_counter += 1
            self.pending_step_data = None
            
            self.creation_page.showReviewUI(False)
            
            self.projector_window.clearProjection() 

            print("Step successfully saved.")

            self.onStartLive()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save step: {e}")

    def onDiscardStep(self):
        """
        Called when user discards the step in CreationPage after reviewing the projection.
        """
        print("Discarding current step...")
        
        # Delete pending data to reset state (if user goes back to creation page without confirming, it should be like they never took a snapshot or selected a node)
        self.pending_step_data = None

        self.pending_flowchart_actions.clear()
        
        # Restart the flowchart manager to the last confirmed state (before the pending actions)
        self.flowchart_manager = FlowchartManager()
        for action in self.confirmed_flowchart_actions:
            if action[0] == "add":
                # action[1]=type, action[2]=text1, action[3]=text2, action[4]=uid, action[5]=folder
                self.flowchart_manager.addNode(action[1], action[2], action[3], action[4], action[5])
            elif action[0] == "merge":
                self.flowchart_manager.mergeWithCondition(action[1])

        # Reset the flowchart to its last confirmed state (before pending changes) and update the SVG        
        self.flowchart_manager.updateFlowchart()
        
        # Reset CreationPage UI to initial state (disable buttons, reset status, etc.)
        self.creation_page.showReviewUI(False)
        
        # Clear Projector (remove the rejected instruction from the projector)
        self.projector_window.clearProjection()
        
        # Go back to Creation Page with live feed active, so user can try again immediately if they want
        self.onStartLive()

    def onFinishManual(self):
        """
        Called when user wants to completely finish the manual.
        """
        if not self.flowchart_manager.flowchart_done:
            QMessageBox.warning(self, "Incomplete", "The flowchart is not finished yet!\nPlease add an 'End' node to the main branch (leftmost) before saving the manual.")
            return

        src_svg = self.flowchart_manager.output_svg_path
        dest_svg = self.manual_manager.current_manual_dir / "flowchart.svg"
        if src_svg.exists():
            shutil.copy(src_svg, dest_svg)
        
        # Final save of flowchart data to ensure everything is up to date before we generate the final manual files.
        self.manual_manager.updateFlowchartDSL(self.flowchart_manager.getDSL())

        # Set status of manual to published
        self.manual_manager.finalizeManual()
        
        QMessageBox.information(self, "Success", "Manual has been successfully saved and published!")
        
        # Zurück zur Startseite und Kamera stoppen
        self.onStopLive()
        self.gotoStartPage()

    def setupScreens(self):
        gui_screen, proj_screen, is_debug = ScreenSelectorDialog.get_screens()
        
        if not gui_screen or not proj_screen:
            return False

        if is_debug:
            print("Starting in DEBUG MODE (Windowed)")
            test_image = "image.png"
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
        """Switches to LoadPage and populates the list of manuals with published manuals from ManualManager."""
        # Load published manuals from ManualManager
        published_manuals = self.manual_manager.listManuals(status_filter="published")
        
        self.load_page.populateList(published_manuals)
        self.stack.setCurrentWidget(self.load_page)

    def onManualSelectedForPlayback(self, manual_id: str):
        """
        Called when user selects a manual from the LoadPage to start playback in PlayerPage.
        """
        if not self.player_manager.loadManual(manual_id):
            QMessageBox.critical(self, "Error", "Could not load manual files.")
            return
            
        # 1. Switch to Player Page
        self.stack.setCurrentWidget(self.player_page)
        
        # 2. Show flowchart SVG in QWebEngineView on the PlayerPage (if exists)
        flowchart_svg_path = self.player_manager.manual_dir / "flowchart.svg"
        self.player_page.loadFlowchartSVG(str(flowchart_svg_path))
        
        # 3. Start live feed and load the first instruction in the projector
        self.onStartLive()
        self.loadCurrentPlayerNode()

    def advancePlayer(self, choice: str):
        """
        Called when user clicks 'Next', 'Yes', or 'No' in PlayerPage to advance to the next step based on the choice.
        """
        if self.player_manager.advance(choice):
            self.loadCurrentPlayerNode()
        else:
            QMessageBox.warning(self, "End of Path", "No further steps found for this path.")

    def goBackPlayer(self):
        """
        Called when user clicks 'Previous' in PlayerPage to go back to the previous step.
        """
        if self.player_manager.goBack():
            self.loadCurrentPlayerNode()
        else:
            QMessageBox.information(self, "Start of Assembly", "You are already at the very first step.")

    def loadCurrentPlayerNode(self):
        """
        Loads the current node's instruction into the projector and updates the PlayerPage UI with node info.
        """
        node_info = self.player_manager.getCurrentNodeInfo()
        self.player_page.updateUI(node_info)

        self.player_page.highlightNode(node_info)
        
        if node_info.get("is_finished"):
            self.projector_window.clearProjection()
            return
            
        _, svg_path = self.player_manager.getPaths()
        
        # Update projector with the current instruction's SVG (if exists)
        if svg_path:
            self.projector_window.loadInstruction(svg_path)
            
            tracking_data = node_info.get("tracking_data", {})
            matrix_list = tracking_data.get("homography_matrix")
            tag_id = tracking_data.get("tag_id", 0)
            
            if matrix_list:
                homography = np.array(matrix_list, dtype=np.float32)
                self.projector_window.gl_widget.setBakingMatrix(homography, None, tag_id)
            else:
                self.projector_window.clearProjection()
        else:
            self.projector_window.clearProjection()

    def quitPlayer(self):
        """
        Called when user wants to quit the PlayerPage and return to the StartPage.
        """
        self.onStopLive()
        self.projector_window.clearProjection()
        self.gotoStartPage()

    def closeEvent(self, event):
        self.vision_worker.stop()
        self.projector_window.close()
        event.accept()

    # --- Remote Assistance Page Methods ---

    def updateLiveTagId(self, r_matrix, t_vector, tag_id: int):
        """
        Called whenever VisionWorker detects a tag pose update during live feed.

        Args:
            r_matrix (np.ndarray): The rotation matrix of the detected tag.
            t_vector (np.ndarray): The translation vector of the detected tag.
            tag_id (int): The ID of the detected tag.
        """
        self.current_live_tag_id = tag_id

    def gotoRemotePage(self):
        """
        Called when user wants to enter Remote Assistance Mode from the StartPage.
        """
        self.stack.setCurrentWidget(self.remote_page)
        self.onStartLive()
        self.remote_server.startServer(port=9001, host_ip="127.0.0.1")
        print("[MainWindow] Entered Remote Assistance Mode.")

    def quitRemoteMode(self):
        """Exits the Remote Mode, stops camera and server."""
        self.onStopLive()
        self.remote_server.stopServer()
        
        # Clean up the projector
        self.projector_window.clearProjection() 
        self.projector_window.gl_widget.is_baked = False # Reset the baking matrix
        
        self.gotoStartPage()

    def onRemoteClientConnected(self):
        """
        Updates the UI to show that a remote client has connected and can start sending SVG instructions.
        """
        self.remote_page.setConnectionStatus(True)

    def onRemoteClientDisconnected(self):
        """
        Updates the UI to show that the remote client has disconnected and no SVG instructions can be received until a new client connects.
        """
        self.remote_page.setConnectionStatus(False)

    def onRemoteSvgReceived(self, svg_string: str):
        """Processes the incoming SVG from the tablet."""
        
        # 1. Safety check: Has the user taken a snapshot yet?
        if not self.projector_window.gl_widget.is_baked:
            print("[Remote] Warning: Tag is not baked yet! Please take a snapshot first.")
            return # <--- The crucial fix: We stop execution right here!

        print(f"[Remote] SVG received: {svg_string} \n -----------------------------")    
        
        # 2. Load the string directly into the GPU VRAM via our new function
        self.projector_window.loadInstructionFromString(svg_string)
        
        print(f"[Remote] SVG ({len(svg_string)} bytes) sent to projector.")

    # --- AI Generation Page Methods ---

    def gotoAIGenerationPage(self):
        if not self.vision_worker.isRunning():
            self.vision_worker.start()
        self.ai_generation_page.showInputMode()
        self.stack.setCurrentWidget(self.ai_generation_page)

    def _aiWorkerRunning(self) -> bool:
        return self.ai_worker is not None and self.ai_worker.isRunning()

    def _startAIWorker(self, worker):
        """Wire common signals and start any AI worker."""
        self.ai_worker = worker
        worker.status_update.connect(
            lambda msg: self.ai_generation_page.updateStatus(msg, "normal")
        )
        worker.step_ready.connect(self.onAIStepReady)
        worker.error_occurred.connect(self.onAIError)
        worker.start()

    def onAIGenerateRequested(self, prompt: str):
        if self._aiWorkerRunning():
            self.ai_generation_page.updateStatus(
                "Generation already in progress. Please wait.", "warning"
            )
            return

        frame = self.vision_worker.get_latest_frame()
        if frame is None:
            self.ai_generation_page.updateStatus(
                "No camera frame yet. Wait for the live feed to start.", "error"
            )
            return

        self._ai_step_num = 0
        self._ai_pending_action = "generate"
        self.ai_generation_page.setGenerateEnabled(False)
        worker = AIGenerationWorker(frame=frame, prompt=prompt)
        worker.finished.connect(lambda: self.ai_generation_page.setGenerateEnabled(True))
        self._startAIWorker(worker)

    def onAINextStep(self):
        if self._aiWorkerRunning():
            return
        frame = self.vision_worker.get_latest_frame()
        if frame is None:
            self.ai_generation_page.updateStatus("No camera frame available.", "error")
            return
        self._ai_pending_action = "next"
        self.ai_generation_page.setNavEnabled(False)
        worker = AIStepNavigationWorker(action="next", frame=frame)
        worker.finished.connect(self._onAINavFinished)
        self._startAIWorker(worker)

    def onAIPrevStep(self):
        if self._aiWorkerRunning():
            return
        frame = self.vision_worker.get_latest_frame()
        if frame is None:
            self.ai_generation_page.updateStatus("No camera frame available.", "error")
            return
        self._ai_pending_action = "prev"
        self.ai_generation_page.setNavEnabled(False)
        worker = AIStepNavigationWorker(action="prev", frame=frame)
        worker.finished.connect(self._onAINavFinished)
        self._startAIWorker(worker)

    def _onAINavFinished(self):
        """Re-enable nav buttons after a navigation worker finishes, respecting is_last."""
        self.ai_generation_page.btn_prev.setEnabled(self._ai_step_num > 1)
        self.ai_generation_page.btn_next.setEnabled(not self._ai_is_last)

    def onAIStepReady(self, step_data: dict):
        if self._ai_pending_action == "next":
            self._ai_step_num += 1
        elif self._ai_pending_action == "prev":
            self._ai_step_num = max(1, self._ai_step_num - 1)
        else:  # "generate"
            self._ai_step_num = 1
        description = step_data["description"]
        svg_string = step_data["svg"]
        is_last = step_data.get("is_last", False)
        self._ai_is_last = is_last

        # Save SVG to disk for inspection
        try:
            import pathlib
            svg_path = pathlib.Path("data/debug_last_svg.svg")
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            svg_path.write_text(svg_string, encoding="utf-8")
            print(f"[AI] SVG saved to {svg_path} for inspection.")
        except Exception as exc:
            print(f"[AI] Could not save SVG debug file: {exc}")

        print(f"[AI] Step {self._ai_step_num} received ({len(svg_string)} chars), is_last={is_last}.")
        self.projector_window.loadInstructionWithoutTag(svg_string)
        self.ai_generation_page.showPlaybackMode(description, self._ai_step_num, is_last)
        self.ai_generation_page.updateStatus(
            f"Step {self._ai_step_num} projected.", "success"
        )

    def onAIError(self, error_message: str):
        print(f"[AI] Error: {error_message}")
        self.ai_generation_page.updateStatus(f"Error: {error_message}", "error")

    def onAINewGeneration(self):
        """Reset to input mode and clear the projector."""
        self._ai_step_num = 0
        self.projector_window.clearProjection()
        self.projector_window.gl_widget.setNoTagMode(False)
        self.ai_generation_page.showInputMode()

    def onAIBack(self):
        """Leave AI page, clear projection, return to start."""
        self.projector_window.clearProjection()
        self.projector_window.gl_widget.setNoTagMode(False)
        self.gotoStartPage()