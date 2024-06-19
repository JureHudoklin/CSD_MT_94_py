from csd_mt_94 import CSD_MT_94
import time

from pymodbus import (
    ExceptionResponse,
    Framer,
    ModbusException,
    pymodbus_apply_logging_config,
)
import asyncio
import logging

logger = logging.getLogger(__name__)


async def main(comm, host, port, framer=Framer.SOCKET):
    """Run async client."""
    import time
    
    
    csd_mt_94 = CSD_MT_94(host, port)
    await csd_mt_94.start_connection()
    
    await csd_mt_94.switch_off()
    await csd_mt_94.disable_voltage()
    await csd_mt_94.disable_operation()
    await csd_mt_94.set_motor_code(0x15B1)     
    await csd_mt_94.set_following_error_reaction_code(17)   
    await csd_mt_94.set_mode_of_operation(1)
    await csd_mt_94.set_profile_velocity(50000)
    
    motor_code = await csd_mt_94.get_motor_code()
    mode_of_operation = await csd_mt_94.get_mode_of_operation()
    print({"motor_code": motor_code, "mode_of_operation": mode_of_operation})

    await csd_mt_94.quick_stop()
    await csd_mt_94.enable_voltage()
    
    await csd_mt_94.switch_on()
    await csd_mt_94.enable_operation()
    
    
    sw = await csd_mt_94.get_status_word()
    cw = await csd_mt_94.get_control_word()
    
    print("------ Move to position ------")
    await csd_mt_94.move_async(24800, cs="relative", change_setpoint_immediately=True)
    time.sleep(1)
    await csd_mt_94.move(-12800, cs="relative")
    
    
    sw = await csd_mt_94.get_status_word()
    cw = await csd_mt_94.get_control_word()
    
    position = await csd_mt_94.get_actual_position()
    target_position = await csd_mt_94.get_target_position()
    velocity = await csd_mt_94.get_profile_velocity()
    target_velocity = await csd_mt_94.get_target_velocity()
    print(f"Position: {position}, Target position: {target_position}")
    print(f"Velocity: {velocity}, Target velocity: {target_velocity}")
    
    
if __name__ == '__main__':
    asyncio.run(main(comm='tcp',
                     host='192.168.1.10',
                     port=502,
    ))