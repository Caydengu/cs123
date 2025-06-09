from gpiozero import Servo
from time import sleep

def angle_to_value(angle):
    # Clamp angle to 0-180
    angle = max(0, min(180, angle))
    # Map 0-180 to -1 to +1
    return (angle / 90.0) - 1

# Initialize servos on GPIO 26
servo = Servo(26, min_pulse_width=0.0005, max_pulse_width=0.0025)

print(f"Initial value {servo.value}")
try:
    while True:
        # Get target angle from user
        angle = float(input("Enter servo angle (0-180): "))

        # Convert angle to value
        value = angle_to_value(angle)

        # Set servo value
        servo.value = value
        print(f"Servo to {angle}° ({value:.2f})")
        sleep(0.5)
        
except KeyboardInterrupt:
    print("\nExiting and releasing servos...")
    servo.detach()
