# Pupper LLM - Voice-Controlled Targeting System
### CS 123 Spring 2025 Group 4
### Vania Chow, Cayden Gu, Hongyue Li, and Benji Warburton

### [Demo Day Presentation](https://docs.google.com/presentation/d/1naUFeP-jD-U5F46eKh-vFS87Ycf5iTFu5LH2e7aRoZ8/edit?usp=sharing)
### [Demo Video](https://drive.google.com/file/d/1iBU_0Kyx-37Vr86rlRLbeELQ8y5SHvHe/view?usp=sharing)

## Project Overview
Our project explores the integration of human-robot communication and environmental interaction 
through the development of a voice-controlled targeting and shooting system using Pupper. 
Building on Optional Lab 3, we implemented a VLA (Voice-Language-Action) pipeline that 
interprets spoken human commands with Whisper API and identifies corresponding objects from the 
COCO dataset using GPT-4o. Equipped with a fisheye camera and a Hailo-8L accelerator for 
real-time object detection, Pupper locates, tracks, and "shoots" the designated target using a 
mounted plastic blaster. To activate the shooter, we designed and 3D-printed a custom mount to 
hold a servo motor capable of pulling the trigger with sufficient force. This project draws on 
the cumulative robotics skills we developed in CS 123 and also engages with ethical 
considerations, particularly the importance of maintaining meaningful human control over 
autonomous systems with kinetic capabilities.

### Key Features
- Voice command recognition using Whisper API
- Real-time object detection with Hailo-8L accelerator
- GPT-4o integration for natural language understanding
- Autonomous target tracking and shooting mechanism
- Custom 3D-printed servo mount for trigger control

### Hardware Requirements
- Pupper robot platform
- Fisheye camera
- Hailo-8L accelerator
- Servo motor for trigger mechanism
- Microphone for voice input
- 3D-printed trigger mount

## Repository Structure
The project is organized as follows:

* `pupper_llm`: Core LLM and control components
    * `karel`: Karel-style programming interface for Pupper
        - Vision-based command processing
        - Class label detection using GPT-4
        - COCO dataset integration
    * `Robot_Commands`: Voice command processing system
        - Keyword spotting and recognition
        - Microphone input handling
        - Command publishing system
    * `simple_scripts`: Utility scripts
        - Firing mechanism control
        - Whisper API integration
        - Basic robot operations
    * `vision_integration`: Vision processing components
        - Hailo-8L integration
        - Real-time object detection
        - Deepgram speech processing
* `search`: Vision and search components
    - Hailo Detection integration
    - Foxglove visualization
    - Core search functionality
* `test`: Testing utilities
    - Servo testing scripts
    - Component verification tools

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- ROS2 Humble
- OpenAI API key
- Hailo-8L SDK
- Required Python packages (see requirements.txt)

### Installation
1. Clone the repository:
```bash
git clone --branch final_project https://github.com/Caydengu/cs123.git
cd cs123
```

2. Install dependencies:
You’ll need to install the following dependencies (turn off the robot stack if it is running `sudo systemctl stop robot`):

```bash
pip install pygame
pip install simpleaudio
pip install openai
pip install openai-whisper
pip install sounddevice
pip install pyttsx3
pip install supervision
pip install loguru
cd ~/pupperv3-monorepo/ros2_ws/src/common
git clone https://github.com/ros-perception/vision_msgs.git
cd ~/pupperv3-monorepo/ros2_ws
bash build.sh
```

Next, install the following package with a sudo apt install
```bash
sudo apt-get install espeak
```

Then, navigate to the `pupper_llm/Robot_Commands/` folder and run the following command:
```bash
pip install -r requirements.txt
```

See the following CS123 lab pages for more setup information:
* [Lab 6: Seeing is Believing](https://cs123-stanford.readthedocs.io/en/latest/schedule/labs/spring-25/lab-6.html)
* [Lab 7: Do What I Say](https://cs123-stanford.readthedocs.io/en/latest/schedule/labs/spring-25/lab-7.html)
* [Optional Lab 3: Poor Man’s VLA](https://cs123-stanford.readthedocs.io/en/latest/schedule/labs/spring-25/opt-lab-3.html)

## Running the System

### 1. System Initialization
```bash
# Start vision components
python3 search/run.sh  # Starts Pupper, Foxglove, and Hailo dependencies
```

After Pupper is on, connect Foxglove to Pupper:
1. Connect the Pi to your laptop with an Ethernet cable/adapter.
2. SSH into Pupper with special options: `ssh -A -L 8765:localhost:8765 pi@pupper.local`
3. Open Foxglove, click `Open Connection`, leave the default websocket URL as is, and click `Open`
4. Visualize the “annotated_image” topic with people detections by selecting the gear icon on the top right panel that says `/camera/image_raw` to configure it. Under `General`, set the topic to `/annotated_image` and the calibration to `None`.

### 2. Voice Command Processing
```bash
# Option 1: Start command line publisher
python3 pupper_llm/Robot_Commands/command_line_publisher.py

# Option 2: Start Whisper API transcription
python3 pupper_llm/simple_scripts/whisper_ping.py
```
Note: Transcription lasts for 5 seconds. Ensure microphone is enabled.

### 3. Target Identification
```bash
# Process commands with GPT-4o
python3 pupper_llm/karel/class_label_detection.py
```
This will automatically trigger the search functionality with the identified target.

### 4. Shooting Mechanism
```bash
# Control the shooting mechanism
python3 pupper_llm/simple_scripts/fire.py
```
- Servo initial position: 90 degrees
- Firing position: 100 degrees
- Reset position: 90 degrees

## Ethical Considerations
This project emphasizes the importance of maintaining meaningful human control over autonomous systems with kinetic capabilities. The system is designed with safety measures and Meaningful Human Control (MHC) in mind through keeping the human-in-the-loop (HITL).

## Acknowledgments
- CS 123 teaching staff
- OpenAI for GPT-4o and Whisper API
- Hailo for the Hailo-8L accelerator
- The Pupper robot community
