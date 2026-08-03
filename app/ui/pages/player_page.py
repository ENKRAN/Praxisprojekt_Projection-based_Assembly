from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget
)
from PyQt6.QtCore import pyqtSignal, Qt, QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtWebEngineWidgets import QWebEngineView
from pathlib import Path

class PlayerPage(QWidget):
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    yes_clicked = pyqtSignal()
    no_clicked = pyqtSignal()
    finish_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, camera_view):
        super().__init__()
        self.camera_view = camera_view
        self.initUI()

        self.current_node_info = {}
        self.flowchart_view.loadFinished.connect(self._applyHighlight)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- HEADER ---
        self.instruction_label = QLabel("Loading Instruction...")
        self.instruction_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.instruction_label.setStyleSheet("color: #eceff4; background-color: #3b4252; padding: 20px; border-radius: 15px;")
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.instruction_label, stretch=0)

        # --- CONTENT AREA ---
        content_layout = QHBoxLayout()
        
        # 1. Left: Camera View
        self.camera_view.setFixedSize(1280, 720) 
        
        cam_container = QVBoxLayout()
        cam_container.addWidget(self.camera_view, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addLayout(cam_container, stretch=0)
        
        # 2. Right: Flowchart
        self.flowchart_view = QWebEngineView()
        self.flowchart_view.setHtml('<html><body style="background-color: #2e3440; color: white;"><h2>Loading Flowchart...</h2></body></html>')
        # self.flowchart_view.setMinimumSize(800, 600)
        content_layout.addWidget(self.flowchart_view, stretch=1)
        
        main_layout.addLayout(content_layout, stretch=1)

        # --- BOTTOM CONTROLS (Dynamic Buttons) ---
        self.control_stack = QStackedWidget()
        self.control_stack.setMaximumHeight(100)
        
        # Widget 1: Standard Navigation
        self.nav_widget = QWidget()
        nav_layout = QHBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(0,0,0,0)
        self.btn_prev = self._createBtn("<< Previous", self.prev_clicked.emit)
        self.btn_next = self._createBtn("Next Step >>", self.next_clicked.emit, color="#a3be8c")
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        
        # Widget 2: Decision Navigation
        self.decision_widget = QWidget()
        dec_layout = QHBoxLayout(self.decision_widget)
        dec_layout.setContentsMargins(0,0,0,0)
        self.btn_yes = self._createBtn("YES (Pass)", self.yes_clicked.emit, color="#a3be8c")
        self.btn_no = self._createBtn("NO (Fail)", self.no_clicked.emit, color="#bf616a")
        dec_layout.addWidget(self.btn_no)
        dec_layout.addWidget(self.btn_yes)

        # Widget 3: Finish
        self.finish_widget = QWidget()
        fin_layout = QHBoxLayout(self.finish_widget)
        fin_layout.setContentsMargins(0,0,0,0)
        self.btn_finish = self._createBtn("Finish Assembly", self.finish_clicked.emit, color="#81a1c1")
        fin_layout.addWidget(self.btn_finish)

        self.control_stack.addWidget(self.nav_widget)
        self.control_stack.addWidget(self.decision_widget)
        self.control_stack.addWidget(self.finish_widget)
        
        main_layout.addWidget(self.control_stack, stretch=0)

        # --- QUIT BUTTON ---
        self.btn_quit = QPushButton("Quit Assembly")
        self.btn_quit.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.btn_quit.setMinimumHeight(60)
        self.btn_quit.setMinimumWidth(300)
        self.btn_quit.setStyleSheet("""
            QPushButton { 
                background-color: #bf616a; 
                color: white; 
                border-radius: 10px; 
            } 
            QPushButton:pressed { background-color: #8f4b52; }
        """)
        self.btn_quit.clicked.connect(self.quit_clicked.emit)
        main_layout.addWidget(self.btn_quit, alignment=Qt.AlignmentFlag.AlignCenter)

    def _createBtn(self, text, signal, color="#434c5e"):
        btn = QPushButton(text)
        btn.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        btn.setMinimumHeight(80)
        btn.setStyleSheet(f"QPushButton {{ background-color: {color}; color: white; border-radius: 15px; }} QPushButton:pressed {{ background-color: #2e3440; }}")
        btn.clicked.connect(signal)
        return btn

    def updateUI(self, node_info: dict):
        """
        Updates the instruction text, flowchart view, and control buttons based on the current node information.
        """
        self.instruction_label.setText(node_info.get("text", "Unknown Step"))
        
        node_type = node_info.get("type", "unknown")
        
        if node_info.get("is_finished") or node_type == "end":
            self.control_stack.setCurrentWidget(self.finish_widget)
        elif node_type == "condition":
            self.control_stack.setCurrentWidget(self.decision_widget)
        else:
            self.control_stack.setCurrentWidget(self.nav_widget)

    def loadFlowchartSVG(self, svg_path: str):
        """
        Loads the SVG file and embeds it into the QWebEngineView with custom styling to match the dark theme.
        """
        abs_path = Path(svg_path).resolve()
        if abs_path.exists():
            with open(abs_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()

            html = f"""
            <html>
              <head>
                <style>
                  body {{ 
                      background-color: #2e3440; 
                      margin: 0; 
                      display: flex; 
                      justify-content: center; 
                      align-items: center; 
                      min-height: 100vh; 
                      overflow: auto;
                  }}
                  .svg-container {{
                      transform: scale(1.8);
                      transform-origin: center center;
                  }}
                </style>
              </head>
              <body>
                <div class="svg-container">
                    {svg_content}
                </div>
              </body>
            </html>
            """
            self.flowchart_view.setHtml(html, QUrl.fromLocalFile(str(abs_path.parent)))
        else:
            self.flowchart_view.setHtml('<html><body style="background-color: #2e3440; color: white;"><h2>Flowchart SVG not found.</h2></body></html>')

    def highlightNode(self, node_info: dict):
        """
        Saves the current node information and triggers the JavaScript function to highlight the corresponding SVG node.
        """
        self.current_node_info = node_info
        self._applyHighlight()

    def _applyHighlight(self):
        """
        Applies a glow effect to the current node in the SVG flowchart by executing JavaScript in the QWebEngineView.
        """
        if not self.current_node_info:
            return
            
        node_id = self.current_node_info.get("node_id", "")
        if not node_id:
            return
            
        js_code = f"""
        (function() {{
            document.querySelectorAll('rect, polygon, path').forEach(function(el) {{
                var id = el.getAttribute('id') || '';
                if (el.getAttribute('fill') !== 'none' && !id.includes('marker') && !el.closest('defs')) {{
                    el.setAttribute('fill', '#4c566a'); // Nord Dark Grey
                    el.setAttribute('stroke', '#d8dee9'); 
                    el.setAttribute('stroke-width', '2');
                    el.style.filter = 'none'; // Glow entfernen
                }}
            }});
            
            var targetId = "{node_id}";
            var mainShape = document.getElementById(targetId);
            
            if (mainShape) {{
                mainShape.setAttribute('fill', '#d08770'); 
                mainShape.setAttribute('stroke', '#ebcb8b'); 
                mainShape.setAttribute('stroke-width', '4'); // Etwas dünnerer Rand
                mainShape.style.filter = 'drop-shadow(0px 0px 5px rgba(235, 203, 139, 0.5))';
                
                var sibling = mainShape.nextElementSibling;
                while (sibling && sibling.tagName !== 'text') {{
                    if (sibling.tagName === 'rect' || sibling.tagName === 'path' || sibling.tagName === 'polygon') {{
                        sibling.setAttribute('fill', '#d08770');
                        sibling.setAttribute('stroke', '#ebcb8b');
                        sibling.setAttribute('stroke-width', '4');
                        sibling.style.filter = 'drop-shadow(0px 0px 5px rgba(235, 203, 139, 0.5))';
                    }}
                    sibling = sibling.nextElementSibling;
                }}
            }}
        }})();
        """
        self.flowchart_view.page().runJavaScript(js_code)