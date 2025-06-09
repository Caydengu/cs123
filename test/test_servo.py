from gpiozero import Servo
from time import sleep

def angle_to_value(angle):
    # Clamp angle to 0-180
    angle = max(0, min(180, angle))
    # Map 0-180 to -1 to +1
    return (angle / 90.0) - 1

# Initialize servos on GPIO 16 and 26
# servo_l = Servo(16, min_pulse_width=0.000500, max_pulse_width=0.002500)
servo_r = Servo(26, min_pulse_width=0.0005, max_pulse_width=0.0025)
# servo_r = Servo(26, min_pulse_width=0.001, max_pulse_width=0.005)

print(f"Initial value {servo_r.value}")
# sleep(5)
try:
    while True:
        # l_angle = float(input("Enter LEFT servo angle (0-180): "))
        r_angle = float(input("Enter RIGHT servo angle (0-180): "))
        # l_value = angle_to_value(l_angle)
        r_value = angle_to_value(r_angle)
        # servo_l.value = l_value
        servo_r.value = r_value
        print(f"RIGHT servo to {r_angle}° ({r_value:.2f})")
        sleep(0.5)
except KeyboardInterrupt:
    print("\nExiting and releasing servos...")
    # servo_l.detach()
    servo_r.detach()
