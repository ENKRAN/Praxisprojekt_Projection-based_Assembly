import sys
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, 
                             QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from app.ui.components.clickable_svg_widget import ClickableSvgWidget

class NodeSelectionPage(QWidget):
    """
    Displays a grid of SVG icons representing different flowchart nodes.
    Selects a node type and emits a signal.
    """
    # Signal sends the type of node selected (e.g., "operation", "decision")
    node_selected = pyqtSignal(str, QWidget)
    back_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Path configuration
        self.icon_dir = Path("app/resources/icons/flowchart_nodes") 
        self.svg_files = self.get_svg_files()

        self.initUI()

    def initUI(self):
        self.main_layout = QVBoxLayout(self)
        
        # --- Grid Layout for Icons ---
        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.setSpacing(20)

        # --- Bottom Layout for Back Button ---
        self.button_layout = QHBoxLayout()
        
        btn_back = QPushButton("Cancel")
        btn_back.setFont(QFont("Arial", 20))
        btn_back.setMinimumSize(300, 100)
        btn_back.clicked.connect(self.back_clicked.emit)

        self.button_layout.addWidget(btn_back)
        self.button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.button_layout.setContentsMargins(0, 0, 200, 100)

        self.main_layout.addLayout(self.grid_layout)
        self.main_layout.addLayout(self.button_layout)

        # Create Icons
        self.create_svg_grid()

    def get_svg_files(self):
        """Loads SVGs or creates dummies if missing (Legacy Logic)."""
        if not self.icon_dir.exists():
            self.icon_dir.mkdir(parents=True, exist_ok=True)
            self.create_dummy_svg(self.icon_dir / "operation.svg", "blue")
            self.create_dummy_svg(self.icon_dir / "decision.svg", "orange")
            self.create_dummy_svg(self.icon_dir / "io.svg", "green")
            self.create_dummy_svg(self.icon_dir / "end.svg", "red")
            self.create_dummy_svg(self.icon_dir / "subroutine.svg", "purple")

        # Get all SVGs
        svg_paths = sorted([f for f in self.icon_dir.glob("*.svg")])
        return svg_paths

    def create_dummy_svg(self, path: Path, color):
        """Creates a placeholder SVG if file is missing."""
        name = path.stem.capitalize()
        svg_content = f"""
        <svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
            <rect x="10" y="10" width="180" height="180" rx="20" ry="20" fill="{color}" stroke="white" stroke-width="4"/>
            <text x="100" y="110" font-family="Arial" font-size="24" text-anchor="middle" fill="white">{name}</text>
        </svg>
        """
        with open(path, "w") as f:
            f.write(svg_content)

    def create_svg_grid(self):
        """Populates the grid with ClickableSvgWidgets."""
        row = 0
        col = 0
        
        for svg_path in self.svg_files:
            # Legacy logic to determine type from filename (e.g. "operation_icon.svg" -> "operation")
            flowchart_node_name = svg_path.stem.split("_", 1)[0]
            
            svg_widget = ClickableSvgWidget(str(svg_path), flowchart_node_name)
            svg_widget.clicked.connect(self.onNodeClicked)
            
            self.grid_layout.addWidget(svg_widget, row, col)

            col += 1
            if col > 2: # 3 Columns (0, 1, 2)
                col = 0
                row += 1

    def onNodeClicked(self, node_type: str, node: QWidget):
        """Relays the signal from the widget to the page controller."""
        print(f"NodeSelectionPage: Clicked {node_type}")
        self.node_selected.emit(node_type, node)