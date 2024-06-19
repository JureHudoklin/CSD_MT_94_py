from csd_mt_94 import CSD_MT_94
import time

from pymodbus import (
    Framer,
)
import asyncio
import logging

logger = logging.getLogger(__name__)

async def main(comm, host, port, framer=Framer.SOCKET):
    """Run async client."""
    
    # Connect to the drive
    csd_mt_94 = CSD_MT_94(host, port)
    await csd_mt_94.start_connection()
    
    # Set the motor parameters
    await csd_mt_94.set_motor_code(0x15B1)     
    await csd_mt_94.set_following_error_reaction_code(17)   
    await csd_mt_94.set_mode_of_operation(1)
    await csd_mt_94.set_profile_velocity(3000)
    await csd_mt_94.set_profile_acceleration(100000)
    
    # Turn on the drive
    await csd_mt_94.quick_stop()
    await csd_mt_94.enable_voltage()
    await csd_mt_94.switch_on()
    await csd_mt_94.enable_operation()
    
    logger.info("------ Moving to position ------")
    await csd_mt_94.move_async(24800, cs="relative", change_setpoint_immediately=True)
    time.sleep(1)
    await csd_mt_94.rotate(-60, cs="relative", units="deg")
    
   
    position = await csd_mt_94.get_actual_position()
    target_position = await csd_mt_94.get_target_position()
    logger.info(f"Position: {position}, Target position: {target_position}")
    
    
    
if __name__ == '__main__':
    # Before running make sure you are able to ping the drive.
    
    asyncio.run(main(comm='tcp',
                     host='192.168.1.10', # IP address of the drive
                     port=502,
    ))