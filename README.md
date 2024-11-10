# Projection-Based Assembly Assistance

This project is a projection-based assembly assistance system that leverages computer vision and projection technology to streamline assembly processes. Using an Intel RealSense D435 camera, the system detects AprilTags, saving assembly instructions relative to their frames and projecting them directly onto the assembly surface.

## Table of Contents

- [Project Description](#project-description)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Installation](#quick-installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Known Issues](#known-issues)
- [License](#license)

---

## Project Description

The goal of this project is to simplify the assembly process by projecting step-by-step instructions directly onto the workspace. By using AprilTags, the system can track the position and orientation of an object in real-time, aligning the projection dynamically with the tag's frame.

## Features

- **AprilTag Detection:** Detects AprilTags and calculates pose using the RealSense camera's depth sensor.
- **Drawing Recognition:** Detects and analyzes drawings in images for contours and positioning.
- **Real-Time Capability:** Optimized for real-time responsiveness.

## Prerequisites

- **Operating System:** Windows 10 or higher
- **Python:** Version 3.11.0
- **Hardware:**
  - Intel RealSense D435 camera
  - Samsung Freestyle 2nd Gen Projector
  - iiyama TV Monitor
  - AprilTags (printed)

Refer to `setup_instructions.md` for specific hardware setup and dependency installation.

## Quick Installation

1. **Clone the Repository**:

   ```bash  
   git clone https://github.com/ENKRAN/Praxisprojekt_Projection-based_Assembly.git  
   cd Praxisprojekt_Projection-based_Assembly  
   ```

2. **Install Dependencies**:  
   ```bash  
   pip install -r requirements.txt  
   ```

3. **Install Intel RealSense SDK**: Follow the detailed guide in `setup_instructions.md` to complete the RealSense SDK installation and optional calibration steps.

## Quick Start

1. **Set Up Hardware**: Connect the Intel RealSense D435 camera and projector as detailed in `setup_instructions.md`.
2. **Run the Program**:  
   ```bash  
   python -m src.main  
   ```

For full usage instructions, including creating manuals and using custom instructions, see `setup_instructions.md`.

## Project Structure

   ```plaintext  
   .  
   ├── data  
   │   └── saved_images  
   ├── docs  
   │   └── setup_instructions.md  
   ├── src  
   │   ├── apriltag_detection.py  
   │   ├── camera.py  
   │   ├── image_processing.py  
   │   ├── main.py  
   └── tests  
   ```

## Known Issues

- **Resolution Mismatch**: Ensure that the camera matrix matches the projector’s resolution for accurate alignment.
- **Performance**: High camera resolutions may impact frame rate.
- **Drawing Recognition**: Adjust parameters in `find_drawings_in_img` if drawings are not detected correctly.

## License

This project is licensed under the MIT License.
