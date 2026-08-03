from pupil_apriltags import Detector
from typing import Any

class AprilTagDetector:
    def __init__(self, tag_family="tagStandard41h12", camera_intrinsics=None, tag_size=0.038) -> None:
        """
        Initialize the AprilTag detector

        :param tag_family: Tag family to detect
        :param fx: Focal length in x direction
        :param fy: Focal length in y direction
        :param cx: Principal point in x direction
        :param cy: Principal point in y direction
        :param tag_size: Size of the tag in meters
        """
        self.detector = Detector(families=tag_family)
        if camera_intrinsics is None:
            raise ValueError("Camera intrinsics must be provided")
        self.fx = camera_intrinsics[0, 0]
        self.fy = camera_intrinsics[1, 1]
        self.cx = camera_intrinsics[0, 2]
        self.cy = camera_intrinsics[1, 2]
        self.tag_size = tag_size

    def detect(self, gray_frame) -> Any:
        """
        Detect apriltags in a grayscale frame

        :param gray_frame: Grayscale frame to detect apriltags in
        :return: Detection object containing the detected apriltags and their properties
        """
        results = self.detector.detect(gray_frame, estimate_tag_pose=True, 
                                       camera_params=[self.fx, self.fy, self.cx, self.cy], 
                                       tag_size=self.tag_size)
        return results
    