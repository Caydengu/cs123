# 1.
cd ~/pupper_llm/pupper_llm/Robot_Commands
python3 command_line_publisher.py

# or

cd ~/pupper_llm/pupper_llm/simple_scripts
python3 whisper_ping.py

# 2. 
cd ~/pupper_llm/pupper_llm/karel
python3 class_label_detection.py



# 3.
cd ~/pupper_llm/search
./run.sh
# source ~/.bashrc
# ros2 launch lab_7.launch.py &
# ros2 launch foxglove_bridge foxglove_bridge_launch.xml &
# python hailo_detection.py

# 4.
cd ~/pupper_llm/search
python search.py