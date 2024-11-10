# Setup Instructions for Projection-Based Assembly Assistance

This document provides a detailed guide to setting up and using the Projection-Based Assembly Assistance system.

## Table of Contents

- [Hardware Setup](#hardware-setup)
- [Software Setup](#software-setup)
- [Detailed Usage Guide](#detailed-usage-guide)
- [Troubleshooting and Tips](#troubleshooting-and-tips)

---

## Hardware Setup

1. **Intel RealSense D435 Camera**:
   - Connect the camera to a USB 3.2 port on your computer.
   - Position the camera at an angle where it can capture the entire assembly workspace.

2. **Samsung Freestyle Projector**:
   - Connect the projector to your computer via wireless screen mirroring or HDMI if available.
   - Ensure the projector’s resolution matches the RealSense camera’s RGB resolution for accurate alignment.
   - Position the projector to cover the workspace where the assembly instructions will be displayed.

3. **iiyama TV Monitor**:
   - Set up the monitor as an extended display for monitoring camera feeds and displaying instructions.
   - This will help in verifying if the instructions are being projected correctly.

4. **AprilTags**:
   - Print AprilTags as required and attach them to the assembly components.
   - Place tags in the camera's field of view for accurate tracking.

---

## Software Setup

1. **Clone the Repository**:

   ```bash  
   git clone https://github.com/ENKRAN/Praxisprojekt_Projection-based_Assembly.git  
   cd Praxisprojekt_Projection-based_Assembly  
   ```

2. **Install Python Dependencies**:  
   ```bash  
   pip install -r requirements.txt  
   ```

3. **Install Intel RealSense SDK**:
   - Visit the Intel RealSense [SDK Download Page](https://www.intelrealsense.com/sdk-2/) and download the latest SDK.
   - Follow the installation instructions provided on the Intel website.
   - (Optional) **On-Chip Calibration**: Use the RealSense Viewer to perform an on-chip calibration for better accuracy. This can be especially useful for high-precision assembly tasks.

---

## Detailed Usage Guide

### Step 1: Initial Setup

1. **Start the Program**:
   ```bash  
   python -m src.main  
   ```

2. **Connect Hardware**: Ensure that the RealSense D435 camera and the projector are connected and positioned correctly.

### Step 2: Creating Manuals

1. **Capture Workspace Image**:
   - Click "Take Picture" to capture the current view from the RealSense camera.
   - The captured image will open in Microsoft Paint on the monitor for custom instruction creation.

2. **Draw Instructions**:
   - Set the background layer color to black and make it invisible.
   - On the second layer, draw any assembly instructions needed.
   - Save the image as a JPEG in `data/saved_images`.
   - Make the background layer visible again and save a second version in `data/saved_images` with a black background.
   - Close Microsoft Paint.

3. **Drawing Transformation**:
   - The saved image will be analyzed by the program, extracting contours and coordinates of the drawings.
   - The drawings are adjusted to align perspectively with the AprilTag and are projected in real-time onto the workspace.

4. **Verification**:
   - Verify if the projected instructions align with the intended areas. Press "Confirm Step X" to confirm each step.

### Step 3: Using a Custom Manual

1. **Load and Start Manual**:
   - Press "Load Manuals" to view available manuals for the component based on the AprilTag ID.
   - Choose a manual and click "Start".

2. **Follow Assembly Instructions**:
   - Each manual step is displayed on the monitor, while specific guides are projected onto the workspace.
   - Follow each instruction step-by-step to assemble the component accurately.

3. **Final Verification**:
   - After completing all steps, the system verifies the assembled component to detect potential assembly errors.

---

## Troubleshooting and Tips

- **Resolution Mismatch**: Ensure both the camera and projector have the same resolution settings to maintain projection alignment.
- **Low Frame Rate**: Reducing the RealSense camera’s resolution can improve performance if you experience lag.
- **Drawing Recognition Adjustments**: If drawings are not accurately detected, modify parameters in the `find_drawings_in_img` function located in `image_processing.py`.

---

These instructions should help you set up and operate the Projection-Based Assembly Assistance system effectively. For further questions or issues, refer to the project's GitHub repository.
