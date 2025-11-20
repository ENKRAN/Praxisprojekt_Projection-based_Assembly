import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QTimer
import math
from src.setup import get_calibration_data

# OpenGL Imports
from OpenGL.GL import *
# Importiere die Nvidia Extension Funktionen
from OpenGL.GL.NV.path_rendering import *

from src.setup import get_calibration_data

class PathRenderingWidget(QOpenGLWidget):
    def initializeGL(self):
        """Hier wird alles einmalig initialisiert."""
        calibration_data_path = 'data/projector_camera_calibration/calibration.yml'
        cam_K, cam_kc, proj_K, proj_kc, R, T = get_calibration_data(calibration_data_path)

        print(f"Camera Intrinsics (Shape: {cam_K.shape}):\n{cam_K}")
        print(f"Camera Distortion Coefficients (Shape: {cam_kc.shape}):\n{cam_kc}")
        print(f"Projector Intrinsics (Shape: {proj_K.shape}):\n{proj_K}")
        print(f"Projector Distortion Coefficients (Shape: {proj_kc.shape}):\n{proj_kc}")
        print(f"Rotation Matrix (Shape: {R.shape}):\n{R}")
        print(f"Translation Vector (Shape: {T.shape}):\n{T}")
    
        # Teste erst mal, was wir überhaupt für einen Context haben
        version = glGetString(GL_VERSION)
        vendor = glGetString(GL_VENDOR)
        renderer = glGetString(GL_RENDERER)
        print(f"OpenGL Version: {version}")
        print(f"Vendor: {vendor}") # Sollte "NVIDIA Corporation" sein
        print(f"Renderer: {renderer}")

        # Prüfen, ob die Extension geladen wurde
        num_extensions = glGetIntegerv(GL_NUM_EXTENSIONS)
        has_nv_path = False
        
        # Wir suchen manuell in der Liste (moderner Weg)
        for i in range(num_extensions):
            ext_name = glGetStringi(GL_EXTENSIONS, i)
            if ext_name == b"GL_NV_path_rendering":
                has_nv_path = True
                break
                
        if not has_nv_path:
            print("FEHLER: GL_NV_path_rendering wird von diesem Treiber/Context nicht unterstützt!")
            return # Abbruch, sonst crash
        
        # Hintergrundfarbe (dunkelgrau)
        glClearColor(0.2, 0.2, 0.2, 1.0)

        glEnable(GL_MULTISAMPLE)
        
        # 1. Pfad-Objekt erstellen (Wir nutzen hier eine generierte ID statt 42)
        self.pathObj = glGenPathsNV(1)
        
        # SVG Daten aus deinem PDF-Beispiel (Herz)
        # "M300 300 C 100 400,100 200,300 100,500 200,500 400,300 300Z"
        svgPathString = b"M300 300 C 100 400,100 200,300 100,500 200,500 400,300 300Z"
        
        # Pfad an die GPU senden
        glPathStringNV(self.pathObj, GL_PATH_FORMAT_SVG_NV, len(svgPathString), svgPathString)

        # Timer für Animation (damit wir die 3D Drehung sehen)
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update) # Ruft paintGL auf
        self.timer.start(16) # ca. 60 FPS

    def paintGL(self):
        """Hier wird bei jedem Frame gezeichnet."""
        # WICHTIG: Stencil Buffer muss auch gecleart werden 
        glClear(GL_COLOR_BUFFER_BIT | GL_STENCIL_BUFFER_BIT)
        
        # --- PROJEKTIONSMATRIX BASIEREND AUF WINKEL ---
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        
        # 1. Parameter definieren (wie in der Vorlesung)
        fov_degrees = 65.5  # Dein Öffnungswinkel (phi)
        z_near = 1.0        # n
        z_far = 1000.0      # f
        
        # Aspect Ratio berechnen (w / h)
        w = self.width()
        h = self.height()
        if h == 0: h = 1
        aspect_ratio = w / h
        
        # 2. Die Formel aus DEINEM BILD anwenden!
        # t = n * tan(phi / 2)
        # Wichtig: Python math.tan erwartet Bogenmaß (Radians), nicht Grad!
        fov_radians = math.radians(fov_degrees)
        t = z_near * math.tan(fov_radians / 2)
        
        # b = -t (Symmetrie, wie im Bild b = -n * tan(...))
        b = -t
        
        # 3. Breite berechnen (basierend auf Aspect Ratio)
        r = t * aspect_ratio
        l = -r
        
        # 4. Matrix erstellen (Das füllt die Matrix im Bild aus)
        # Parameter: left, right, bottom, top, near, far
        glFrustum(l, r, b, t, z_near, z_far)
        
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        # Kamera etwas zurückziehen
        glTranslatef(0, 0, -800)
        
        # Das Objekt im 3D Raum drehen (Hier passiert die Magie)
        glRotatef(self.angle, 0, 1, 0) # Drehung um Y-Achse
        glRotatef(15, 1, 0, 0)         # Leicht nach hinten kippen
        
        # Den Pfad so verschieben, dass er mittig rotiert (er ist im SVG bei 300,300 definiert)
        glTranslatef(-300, -300, 0)

        # --- RENDERING SCHRITTE (Stencil then Cover) ---
        
        # Schritt A: Stencil (Schablone erstellen)
        # Zählt hoch im Stencil Buffer, analog zum PDF [cite: 89]
        glStencilFillPathNV(self.pathObj, GL_COUNT_UP_NV, 0x1F)
        
        # Schritt B: Cover (Farbe auftragen)
        # Wir aktivieren den Stencil Test
        glEnable(GL_STENCIL_TEST)
        glStencilFunc(GL_NOTEQUAL, 0, 0x1F)
        glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO)
        
        # Farbe setzen (Gelb wie im PDF Beispiel)
        glColor3f(1, 1, 0)
        
        # Zeichnen! "Cover" füllt alles, wo der Stencil != 0 ist
        glCoverFillPathNV(self.pathObj, GL_BOUNDING_BOX_NV)

        glCoverFillPathNV(self.pathObj, GL_BOUNDING_BOX_NV)

        # --- NEU: STROKE (UMRANDUNG) ---
        
        # 1. Einstellungen für den Pinsel setzen
        # Breite des Strichs (in Koordinaten-Einheiten)
        glPathParameterfNV(self.pathObj, GL_PATH_STROKE_WIDTH_NV, 5.0)
        # Runde Ecken bei Linienverbindungen (sieht bei Herz besser aus)
        glPathParameteriNV(self.pathObj, GL_PATH_JOIN_STYLE_NV, GL_ROUND_NV)

        # 2. Stencil für den Stroke berechnen
        # Wir nutzen wieder den Stencil Buffer, setzen das Referenz-Bit auf 1
        # 0x1 = Maske, ~0 = Maske für Invertierung (alle Bits an)
        glStencilStrokePathNV(self.pathObj, 0x1, ~0)

        # 3. Cover Stroke (Die Farbe zeichnen)
        glColor3f(1.0, 1.0, 1.0) # Weiß
        # Wir zeichnen nur dort, wo der Stencil-Wert durch Schritt 2 gesetzt wurde
        glStencilFunc(GL_EQUAL, 0x1, 0x1)
        glStencilOp(GL_KEEP, GL_KEEP, GL_ZERO) # Danach wieder aufräumen
        
        glCoverStrokePathNV(self.pathObj, GL_CONVEX_HULL_NV)
        
        glDisable(GL_STENCIL_TEST)
        
        # Animation weiterdrehen
        self.angle += 1

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

# Standard PyQt Boilerplate
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    from PyQt6.QtGui import QSurfaceFormat
    fmt = QSurfaceFormat()
    
    # 1. Stencil Buffer (Wichtig für die Pfad-Berechnung)
    fmt.setStencilBufferSize(8)
    
    # 2. Compatibility Profile (Damit NV-Funktionen da sind)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)

    # --- NEU: SAMPLES SETZEN ---
    # 4 ist Standard, 8 ist sehr gut, 16 ist Maximum (kein Problem für deine RTX 4070)
    fmt.setSamples(16) 
    # ---------------------------
    
    QSurfaceFormat.setDefaultFormat(fmt)
    
    window = QMainWindow()
    widget = PathRenderingWidget()
    window.setCentralWidget(widget)
    window.resize(800, 600)
    window.show()
    
    sys.exit(app.exec())