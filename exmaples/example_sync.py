from csd_mt_94 import CSD_MT_94
import time

# Create an instance of the CSD_MT_94 class
motor = CSD_MT_94(host='192.168.1.10', port=502)

# Use a context manager to ensure proper connection handling
with motor:
    # Get motor information
    print("Getting motor information...")
    
    # Get device info
    device_info = motor.get_device_info()
    if device_info:
        print(f"Device Info: {device_info}")
    
    # Get motor code
    motor_code = motor.get_motor_code()
    print(f"Motor Code: {motor_code}")
    
    # Get current ratio
    current_ratio = motor.get_current_ratio()
    print(f"Current Ratio: {current_ratio}%")
    
    # Get steps per revolution
    steps_per_rev = motor.get_step_revolution()
    print(f"Steps per Revolution: {steps_per_rev}")
    
    # Get actual position
    actual_position = motor.get_actual_position()
    print(f"Current Position: {actual_position} steps")
    
    # Prepare the motor for movement
    print("\nPreparing motor for movement...")
    motor.quick_stop()
    motor.enable_voltage()
    motor.switch_on()
    motor.enable_operation()
    
    # Set mode of operation to profile position mode
    motor.set_mode_of_operation(1)
    
    # Set motion parameters
    motor.set_profile_velocity(10000)
    motor.set_profile_acceleration(100000)
    
    # Rotate the motor
    print("\nRotating motor...")
    success = motor.rotate(3.14, cs="relative", units="rad", change_setpoint_immediately=True, wait_for_target_reached=True)
    
    if success:
        print("Motor rotation completed successfully.")
    else:
        print("Motor rotation failed.")
    
    # Get new position after rotation
    new_position = motor.get_actual_position()
    print(f"New Position: {new_position} steps")
    
    # Move motor to absolute position
    print("\nMoving motor to absolute position...")
    success = motor.move(10000, cs="absolute", change_setpoint_immediately=True, wait_for_target_reached=True)
    
    if success:
        print("Motor move completed successfully.")
    else:
        print("Motor move failed.")
    
    # Get final position
    final_position = motor.get_actual_position()
    print(f"Final Position: {final_position} steps")

print("\nMotor operations completed.")