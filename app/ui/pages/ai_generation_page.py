from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont


class AIGenerationPage(QWidget):
    """
    Page for AI-assisted object segmentation and step-by-step projection.

    Two modes share the same layout:

    INPUT MODE (before generation):
      status_label → camera_view → [prompt_input | btn_generate] → [btn_back]

    PLAYBACK MODE (after step 0 arrives):
      status_label → camera_view → description_label → [btn_prev | step_counter | btn_next]
                   → [btn_new_generation | btn_back]
    """

    generate_clicked = pyqtSignal(str)   # prompt text
    next_step_clicked = pyqtSignal()
    prev_step_clicked = pyqtSignal()
    new_generation_clicked = pyqtSignal()
    back_clicked = pyqtSignal()

    def __init__(self, camera_view, parent=None):
        super().__init__(parent)
        self.camera_view = camera_view
        self._step_num = 0
        self._initUI()
        self.showInputMode()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- Status label (always visible) ---
        self.status_label = QLabel(
            "Ready. Point the camera at the target, enter a prompt, and click Generate."
        )
        self.status_label.setFixedHeight(60)
        self.status_label.setFont(QFont("Arial", 18))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "color: white; background-color: #3b4252; padding: 10px; border-radius: 10px;"
        )
        main_layout.addWidget(self.status_label, stretch=0)

        # --- Camera view (always visible) ---
        cam_layout = QHBoxLayout()
        self.camera_view.setFixedSize(1280, 720)
        cam_layout.addWidget(self.camera_view, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addLayout(cam_layout, stretch=1)

        # ── INPUT MODE widgets ──────────────────────────────────────────

        self._input_widget = QWidget()
        input_layout = QVBoxLayout(self._input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(15)

        # Prompt row
        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(15)

        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText(
            "Describe the assembly task (e.g. 'assemble the pump step by step')"
        )
        self.prompt_input.setFont(QFont("Arial", 18))
        self.prompt_input.setMinimumHeight(60)
        self.prompt_input.setStyleSheet(
            "background-color: #434c5e; color: white;"
            " border: 2px solid #d8dee9; border-radius: 10px; padding: 5px 10px;"
        )
        self.prompt_input.returnPressed.connect(self._onGenerateClicked)

        self.btn_generate = QPushButton("Generate Manual")
        self.btn_generate.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.btn_generate.setFixedSize(280, 60)
        self.btn_generate.setStyleSheet(
            "QPushButton { background-color: #5e81ac; color: white; border: none; border-radius: 10px; }"
            "QPushButton:pressed { background-color: #4c6a8d; }"
            "QPushButton:disabled { background-color: #3b4252; color: #606672; border: none; }"
        )
        self.btn_generate.clicked.connect(self._onGenerateClicked)

        prompt_row.addWidget(self.prompt_input, stretch=1)
        prompt_row.addWidget(self.btn_generate, stretch=0)
        input_layout.addLayout(prompt_row)

        # Back button (input mode)
        input_bottom = QHBoxLayout()
        self._btn_back_input = QPushButton("Back to Start")
        self._btn_back_input.setFont(QFont("Arial", 18))
        self._btn_back_input.setMinimumHeight(60)
        self._btn_back_input.setStyleSheet(
            "QPushButton { background-color: #bf616a; color: white; border: none; border-radius: 10px; }"
            "QPushButton:pressed { background-color: #8f4b52; }"
        )
        self._btn_back_input.clicked.connect(self.back_clicked.emit)
        input_bottom.addWidget(self._btn_back_input)
        input_layout.addLayout(input_bottom)

        main_layout.addWidget(self._input_widget, stretch=0)

        # ── PLAYBACK MODE widgets ───────────────────────────────────────

        self._playback_widget = QWidget()
        playback_layout = QVBoxLayout(self._playback_widget)
        playback_layout.setContentsMargins(0, 0, 0, 0)
        playback_layout.setSpacing(15)

        # Step description
        self.description_label = QLabel("")
        self.description_label.setFont(QFont("Arial", 20))
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setStyleSheet(
            "color: white; background-color: #3b4252; padding: 12px; border-radius: 10px;"
        )
        self.description_label.setMinimumHeight(80)
        playback_layout.addWidget(self.description_label)

        # Navigation row: Prev | counter | Next
        nav_row = QHBoxLayout()
        nav_row.setSpacing(20)

        self.btn_prev = QPushButton("← Previous")
        self.btn_prev.setFont(QFont("Arial", 18))
        self.btn_prev.setMinimumHeight(60)
        self.btn_prev.setStyleSheet(
            "QPushButton { background-color: #4c566a; color: white; border: none; border-radius: 10px; }"
            "QPushButton:pressed { background-color: #3b4252; }"
            "QPushButton:disabled { background-color: #3b4252; color: #606672; border: none; }"
        )
        self.btn_prev.clicked.connect(self.prev_step_clicked.emit)

        self.step_counter_label = QLabel("Step 1")
        self.step_counter_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.step_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_counter_label.setStyleSheet("color: white;")
        self.step_counter_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.btn_next = QPushButton("Next →")
        self.btn_next.setFont(QFont("Arial", 18))
        self.btn_next.setMinimumHeight(60)
        self.btn_next.setStyleSheet(
            "QPushButton { background-color: #5e81ac; color: white; border: none; border-radius: 10px; }"
            "QPushButton:pressed { background-color: #4c6a8d; }"
            "QPushButton:disabled { background-color: #3b4252; color: #606672; border: none; }"
        )
        self.btn_next.clicked.connect(self.next_step_clicked.emit)

        nav_row.addWidget(self.btn_prev, stretch=1)
        nav_row.addWidget(self.step_counter_label, stretch=1)
        nav_row.addWidget(self.btn_next, stretch=1)
        playback_layout.addLayout(nav_row)

        # Bottom controls (playback mode)
        playback_bottom = QHBoxLayout()
        playback_bottom.setSpacing(15)

        self.btn_new_generation = QPushButton("New Generation")
        self.btn_new_generation.setFont(QFont("Arial", 18))
        self.btn_new_generation.setMinimumHeight(60)
        self.btn_new_generation.setStyleSheet(
            "QPushButton { background-color: #a3be8c; color: #2e3440; border: none; border-radius: 10px; }"
            "QPushButton:pressed { background-color: #7fa36a; }"
        )
        self.btn_new_generation.clicked.connect(self.new_generation_clicked.emit)

        self._btn_back_playback = QPushButton("Back to Start")
        self._btn_back_playback.setFont(QFont("Arial", 18))
        self._btn_back_playback.setMinimumHeight(60)
        self._btn_back_playback.setStyleSheet(
            "QPushButton { background-color: #bf616a; color: white; border: none; border-radius: 10px; }"
            "QPushButton:pressed { background-color: #8f4b52; }"
        )
        self._btn_back_playback.clicked.connect(self.back_clicked.emit)

        playback_bottom.addWidget(self.btn_new_generation)
        playback_bottom.addWidget(self._btn_back_playback)
        playback_layout.addLayout(playback_bottom)

        main_layout.addWidget(self._playback_widget, stretch=0)

    # ------------------------------------------------------------------
    # Public interface used by MainWindow
    # ------------------------------------------------------------------

    def showInputMode(self):
        """Switch to the prompt-entry view."""
        self._input_widget.setVisible(True)
        self._playback_widget.setVisible(False)
        self.updateStatus(
            "Ready. Point the camera at the target, enter a prompt, and click Generate."
        )

    def showPlaybackMode(self, description: str, step_num: int, is_last: bool):
        """Switch to the step-navigation view and display step data."""
        self._step_num = step_num
        self._input_widget.setVisible(False)
        self._playback_widget.setVisible(True)
        self._updateStepWidgets(description, step_num, is_last)

    def updateStep(self, description: str, step_num: int, is_last: bool):
        """Update step content while already in playback mode."""
        self._step_num = step_num
        self._updateStepWidgets(description, step_num, is_last)

    def updateStatus(self, message: str, color: str = "normal"):
        """Update the status label. color: 'normal' | 'warning' | 'error' | 'success'."""
        color_map = {
            "normal":  "color: white;",
            "warning": "color: #ebcb8b;",
            "error":   "color: #bf616a;",
            "success": "color: #a3be8c;",
        }
        style = color_map.get(color, color_map["normal"])
        self.status_label.setStyleSheet(
            f"{style} background-color: #3b4252; padding: 10px; border-radius: 10px;"
        )
        self.status_label.setText(message)

    def setGenerateEnabled(self, enabled: bool):
        """Disable/enable prompt + generate button during SSH call."""
        self.btn_generate.setEnabled(enabled)
        self.prompt_input.setEnabled(enabled)

    def setNavEnabled(self, enabled: bool):
        """Disable/enable Prev/Next during SSH navigation call."""
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _updateStepWidgets(self, description: str, step_num: int, is_last: bool):
        self.description_label.setText(description)
        self.step_counter_label.setText(f"Step {step_num}")
        self.btn_prev.setEnabled(step_num > 1)
        self.btn_next.setEnabled(not is_last)

    def _onGenerateClicked(self):
        prompt = self.prompt_input.text().strip()
        if not prompt:
            self.updateStatus("Please enter a prompt before clicking Generate.", "warning")
            return
        self.generate_clicked.emit(prompt)
