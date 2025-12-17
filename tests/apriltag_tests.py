import cv2
from src.apriltag_detection import AprilTagDetector
import numpy as np
from src.visualization import draw_axes, draw_tag_border_and_id
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

class WebcamThread(QThread):
    pose_update_signal = pyqtSignal(np.ndarray, np.ndarray)
    image_update_signal = pyqtSignal(QImage)

    def __init__(self, camera_id=0, width=1280, height=720, apriltag_detector=None, camera_intrinsics=None, dist_coeffs=None):
        """
        Initialisiert die Kamera-Einstellungen.
        """
        super().__init__()
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.cap = None
        self.is_running = False

        if apriltag_detector is None:
            raise ValueError("Ein AprilTag-Detektor muss übergeben werden.")
        self.apriltag_detector = apriltag_detector
        self.camera_intrinsics = camera_intrinsics
        self.dist_coeffs = dist_coeffs

    def start_camera(self):
        """Öffnet die Verbindung zur Kamera."""
        self.cap = cv2.VideoCapture(self.camera_id)
        
        # Auflösung setzen
        self.cap.set(3, self.width)
        self.cap.set(4, self.height)

        if not self.cap.isOpened():
            raise IOError("Kamera konnte nicht geöffnet werden.")
        
        print(f"Kamera gestartet. Auflösung: {self.width}x{self.height}")

    def process_snapshot(self, frame):
        """
        Diese Methode wird aufgerufen, wenn die Leertaste gedrückt wird.
        Hier kommt deine spezielle Foto-Logik rein.
        """
        print("Foto aufgenommen!")
        
        cv2.imwrite("detected_apriltag.jpg", frame)

        snapshot = frame.copy()

        print(f"Rotationsmatrix:\n{self.R_ct}")
        print(f"Translationsvektor:\n{self.tvec}")
        
        cv2.imshow('Geschossenes Foto', snapshot)

    def run(self):
        """Startet den Haupt-Loop (Video-Anzeige)."""
        if not self.cap:
            self.start_camera()

        self.is_running = True
        print("Drücke 'LEERTASTE' für Foto, 'q' zum Beenden.")

        while self.is_running:
            ret, frame = self.cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            results = self.apriltag_detector.detect(gray)

            for result in results:
                # Zeichnen für Debug-Ansicht (optional, cv2.imshow im Thread ist manchmal buggy, aber meist okay)
                frame = draw_tag_border_and_id(frame, result)
                
                R_ct = result.pose_R
                tvec = result.pose_t
                
                frame = draw_axes(frame, R_ct, tvec, 
                                  self.camera_intrinsics, 
                                  self.dist_coeffs, 
                                  axis_length=0.05)
                
                # WICHTIG: Statt direktem Aufruf senden wir ein Signal!
                self.pose_update_signal.emit(R_ct, tvec)

            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()
            
            self.image_update_signal.emit(qt_image)
            
            # Ein kurzes Sleep ist wichtig, damit der Thread nicht 100% CPU frisst
            # und das Event-Handling von cv2 funktioniert
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.is_running = False

        self.cap.release()
        cv2.destroyAllWindows()

    def stop(self):
        self.is_running = False
        self.wait()

if __name__ == "__main__":

    fx, fy = 800, 800  # Brennweite
    cx, cy = 640, 360  # Bildmitte
    camera_matrix = np.array([[fx, 0, cx], 
                            [0, fy, cy], 
                            [0, 0, 1]], dtype=np.float32)
    
    dist_coeffs = np.zeros(5)

    apriltag_detector = AprilTagDetector(camera_intrinsics=camera_matrix)
    app = WebcamApp(apriltag_detector=apriltag_detector, camera_intrinsics=camera_matrix, dist_coeffs=dist_coeffs)
    app.run()
