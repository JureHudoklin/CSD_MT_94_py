from typing import Any, Dict, List, Tuple, Literal, Union
import time

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.client import ModbusTcpClient
from pymodbus import (
    ExceptionResponse,
    Framer,
    ModbusException,
    pymodbus_apply_logging_config,
)
import asyncio
import logging
from .utils import merge_registers, to_bits_list, int32_to_uint16
from .definitions import *

logger = logging.getLogger(__name__)


class CSD_MT_94:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        # self.client = AsyncModbusTcpClient(
        #     host,
        #     port=port,
        #     framer=Framer.SOCKET,
        # )
        self.client_sync = ModbusTcpClient(
            host,
            port=port,
            framer=Framer.SOCKET,
        )    
        
    async def start_connection(self):
        await self.client.connect()
        self.client_sync.connect()
        
    def __del__(self):
        print("Deleting")
        self.switch_off()
        self.client.close()
        self.client_sync.close()
    
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self.client.is_active()
   
    async def move_async(self,
                   position: int,
                   cs: Literal["absolute", "relative"] = "relative",
                   change_setpoint_immediately: bool = False,
                   wait_for_target_reached: bool = False,
                   timeout: float = 10,
        ):
        """ Move to a specific position. The function will block until the target position is reached or the timeout is reached.

        Parameters
        ----------
        position : int
            The target position in [steps].
        cs : Literal["absolute", "relative"]
            The coordinate system in which the position is defined, by default "relative"
        timeout : float, optional
            The timeout in seconds, by default 10
        change_setpoint_immediately : bool, optional
            If True, the current setpoint can be overwritten by sending a new movement command, by default False
        """
        await self.set_control_word_bits_async({4: False, 5: change_setpoint_immediately, 6: cs == "relative"})
        await self.set_target_position_async(position)
        await self.set_control_word_bit_async(4, True)
        
        if wait_for_target_reached:
            target_reached = False
            timeout = time.time() + timeout
            while not target_reached:
                sw = await self.get_status_word_async()
                target_reached = sw[1].target_reached
                if time.time() > timeout:
                    return     
    def move(self,
            position: int,
            cs: Literal["absolute", "relative"] = "relative",
            change_setpoint_immediately: bool = False,
            wait_for_target_reached: bool = False,
            timeout: float = 10,
        ):
        """ Move to a specific position asynchronously. The function will return immediately after the movement is started.

        Parameters
        ----------
        position : int
            The target position in [steps].
        cs : Literal[&quot;absolute&quot;, &quot;relative&quot;], optional
            The coordinate system in which the position is defined, by default "relative"
        change_setpoint_immediately : bool, optional
            If True, the current setpoint can be overwritten by sending a new movement command, by default True
        """
        self.set_control_word_bits({4: False, 5: change_setpoint_immediately, 6: cs == "relative"})
        self.set_target_position(position)        
        self.set_control_word_bit(4, True)
        
        if wait_for_target_reached:
            target_reached = False
            timeout = time.time() + timeout
            while not target_reached:
                sw = self.get_status_word()
                target_reached = sw[1].target_reached
                if time.time() > timeout:
                    return
        
        return
   
    def halt(self):
        """ Toggles the halt bit in the control word. Does not permanently stop the drive."""
        self.set_control_word_bit(8, True)
        self.set_control_word_bit(8, False)    
    async def halt_async(self):
        """ Toggles the halt bit in the control word. Does not permanently stop the drive."""
        await self.set_control_word_bit_async(8, True)
        await self.set_control_word_bit_async(8, False)
        
    def rotate(self,
                     angle: float,
                     cs: Literal["absolute", "relative"] = "relative",
                     units: Literal["deg", "rad"] = "rad",
                     change_setpoint_immediately: bool = False,
                     wait_for_target_reached: bool = False,
                     timeout: float = 10,
                     ) -> bool:
        """ Rotate the motor by a specific angle.

        Parameters
        ----------
        angle : float
            The angle in degrees.
        cs : Literal["absolute", "relative"], optional
            The coordinate system in which the angle is defined, by default "relative"
        units : Literal["deg", "rad"], optional
            The units of the angle, by default "rad"
        change_setpoint_immediately : bool, optional
            If True, the current setpoint can be overwritten by sending a new movement command, by default False
        timeout : float, optional
            The timeout in seconds, by default 10
        """
        if units == "deg":
            angle = angle * 3.14159 / 180
            
        steps_per_revolution = self.get_step_revolution()
        if cs == "relative":
            target_position = angle * steps_per_revolution / (2 * 3.14159)
            target_position = int(target_position)
        else:
            current_position = self.get_actual_position()
            target_position = current_position + angle * steps_per_revolution / (2 * 3.14159)
            target_position = int(target_position)
            
        self.set_control_word_bits({4: False, 5: change_setpoint_immediately, 6: cs == "relative"})
        self.set_target_position(target_position)
        self.set_control_word_bit(4, True)
        
        if wait_for_target_reached:
            target_reached = False
            timeout = time.time() + timeout
            while not target_reached:
                sw = self.get_status_word()
                target_reached = sw[1].target_reached
                if time.time() > timeout:
                    return False
               
        return True 
                
    async def rotate_async(self,
                            angle: float,
                            cs: Literal["absolute", "relative"] = "relative",
                            units: Literal["deg", "rad"] = "rad",
                            change_setpoint_immediately: bool = True) -> bool:
        """ Rotate the motor by a specific angle asynchronously.
        The function will return immediately after the movement is started.

        Parameters
        ----------
        angle : float
            The angle in degrees.
        cs : Literal[&quot;absolute&quot;, &quot;relative&quot;], optional
            The coordinate system in which the angle is defined, by default "relative"
        units : Literal[&quot;deg&quot;, &quot;rad&quot;], optional
            The units of the angle, by default "rad"
        change_setpoint_immediately : bool, optional
            If True, the current setpoint can be overwritten by sending a new movement command, by default True
        """
        if units == "deg":
            angle = angle * 3.14159 / 180
        
        steps_per_revolution = await self.get_step_revolution_async()
        if cs == "relative":
            target_position = angle * steps_per_revolution / (2 * 3.14159)
            target_position = int(target_position)
        else:
            current_position = await self.get_actual_position_async()
            target_position = current_position + angle * steps_per_revolution / (2 * 3.14159)
            target_position = int(target_position)
            
        await self.set_control_word_bits_async({4: False, 5: change_setpoint_immediately, 6: cs == "relative"})
        await self.set_target_position_async(target_position)
        await self.set_control_word_bit_async(4, True)
        
        if wait_for_target_reached:
            target_reached = False
            timeout = time.time() + timeout
            while not target_reached:
                sw = self.get_status_word()
                target_reached = sw[1].target_reached
                if time.time() > timeout:
                    return False
               
        return True 
            
    async def switch_on_async(self):
        """Switch on the drive."""
        try:
            await self.set_control_word_bit_async(0, True)
        except ModbusException as e:
            logger.error(f"Error switching on drive: {e}")
    def switch_on(self):
        """Switch on the drive."""
        try:
            self.set_control_word_bit(0, True)
        except ModbusException as e:
            logger.error(f"Error switching on drive: {e}")
            
    async def switch_off_async(self):
        """Switch off the drive."""
        try:
            await self.set_control_word_bit_async(0, False)
        except ModbusException as e:
            logger.error(f"Error switching off drive: {e}")
    def switch_off(self):
        """Switch off the drive."""
        try:
            self.client_sync.write_register(1040, 0)
        except ModbusException as e:
            logger.error(f"Error switching off drive: {e}")
            
    async def enable_voltage_async(self):
        """Enable the voltage."""
        try:
            await self.set_control_word_bit_async(1, True)
        except ModbusException as e:
            logger.error(f"Error enabling voltage: {e}")
    def enable_voltage(self):
        """Enable the voltage."""
        try:
            self.set_control_word_bit(1, True)
        except ModbusException as e:
            logger.error(f"Error enabling voltage: {e}")
            
    async def disable_voltage_async(self):
        """Disable the voltage."""
        try:
            await self.set_control_word_bit_async(1, False)
        except ModbusException as e:
            logger.error(f"Error disabling voltage: {e}")
    def disable_voltage(self):
        """Disable the voltage."""
        try:
            self.set_control_word_bit(1, False)
        except ModbusException as e:
            logger.error(f"Error disabling voltage: {e}")
            
            
    async def quick_stop_async(self):
        """Quick stop the drive."""
        try:
            await self.set_control_word_bit_async(2, True)
        except ModbusException as e:
            logger.error(f"Error quick stopping drive: {e}")
    def quick_stop(self):
        """Quick stop the drive."""
        try:
            self.set_control_word_bit(2, True)
        except ModbusException as e:
            logger.error(f"Error quick stopping drive: {e}")
            
    async def release_quick_stop_async(self):
        """Release the quick stop."""
        try:
            await self.set_control_word_bit_async(2, False)
        except ModbusException as e:
            logger.error(f"Error releasing quick stop: {e}")
    def release_quick_stop(self):
        """Release the quick stop."""
        try:
            self.set_control_word_bit(2, False)
        except ModbusException as e:
            logger.error(f"Error releasing quick stop: {e}")
    
    async def enable_operation_async(self):
        """Enable operation."""
        try:
            await self.set_control_word_bit_async(3, True)
        except ModbusException as e:
            logger.error(f"Error enabling operation: {e}")
    def enable_operation(self):
        """Enable operation."""
        try:
            self.set_control_word_bit(3, True)
        except ModbusException as e:
            logger.error(f"Error enabling operation: {e}")
            
    async def disable_operation_async(self):
        """Disable operation."""
        try:
            await self.set_control_word_bit_async(3, False)
        except ModbusException as e:
            logger.error(f"Error disabling operation: {e}")
    def disable_operation_async(self):
        """Disable operation."""
        try:
            self.set_control_word_bit(3, False)
        except ModbusException as e:
            logger.error(f"Error disabling operation: {e}")      
        
            
    ### Configuration Registers ###
    async def get_ip_address_async(self) -> str:
        result = await self.client.read_holding_registers(1130, 4)
        ip = '.'.join([str(i) for i in result.registers])
        return ip
    async def get_netmask_async(self) -> str:
        result = await self.client.read_holding_registers(1134, 4)
        netmask = '.'.join([str(i) for i in result.registers])
        return netmask
    async def get_gateway_async(self) -> str:
        result = await self.client.read_holding_registers(1138, 4)
        gateway = '.'.join([str(i) for i in result.registers])
        return gateway
    
    ### Identification Registers ###
    async def get_device_info_async(self) -> dict:
        result = await self.client.read_holding_registers(1152, 9)
        software_version = merge_registers(result.registers[0:2])
        product_code = merge_registers(result.registers[2:4])
        hardware_version = merge_registers(result.registers[4:6])
        serial_number = merge_registers(result.registers[6:8])
        little_big_endian = result.registers[8]
        
        return {
            'software_version': software_version,
            'product_code': product_code,
            'hardware_version': hardware_version,
            'serial_number': serial_number,
            'little_big_endian': little_big_endian,
        }
        
    ### Service Registers ###
    async def is_error_async(self) -> bool:
        """Check if the drive is in an error state."""
        result = await self.client.read_holding_registers(1006) #U16
            
        return bool(result.registers[0])
    
    async def get_error_code_async(self) -> Dict[Literal["error_code", "error_message"], Union[str, int]]:
        result = await self.client.read_holding_registers(1007) #U16
        error = ERROR_CODES.get(result.registers[0], "Unknown error")
        
        return {"error_code": result.registers[0], "error_message": error}
        
    async def get_drive_temperature_async(self) -> int:
        """Get the drive temperature in degrees Celsius."""
        result = await self.client.read_holding_registers(1124, 1) #U16
        return result.registers[0]
    
    async def get_warning_temperature(self) -> int:
        raise NotImplementedError
    async def set_warning_temperature(self, temperature: int):
        raise NotImplementedError
    
    async def get_fault_temperature(self) -> int:
        raise NotImplementedError
    async def set_fault_temperature(self, temperature: int):
        raise NotImplementedError
    
    async def get_drive_alarms_async(self) -> List[dict]:
        """ 10 events Alarm Register.
        For each event the event delay since power on and the event code are stored. 

        Returns
        -------
        List[dict]
            List of dictionaries containing the "alarm_time" and "alarm_code".
        """
        result = await self.client.read_holding_registers(1220, 20)
        # Even indexes are the alarm times, odd indexes are the alarm codes
        alarms = []
        for i in range(0, len(result.registers), 2):
            alarm = {
                "alarm_time": result.registers[i],
                "alarm_code": result.registers[i+1],
            }
            alarms.append(alarm)
        return alarms
    def get_drive_alarms(self) -> List[dict]:
        """ 10 events Alarm Register.
        For each event the event delay since power on and the event code are stored. 

        Returns
        -------
        List[dict]
            List of dictionaries containing the "alarm_time" and "alarm_code".
        """
        result = self.client_sync.read_holding_registers(1220, 20)
        # Even indexes are the alarm times, odd indexes are the alarm codes
        alarms = []
        for i in range(0, len(result.registers), 2):
            alarm = {
                "alarm_time": result.registers[i],
                "alarm_code": result.registers[i+1],
            }
            alarms.append(alarm)
        return alarms
    
    async def reset_error_logs_async(self):
        """ Reset the drive alarm registers."""
        try:
            await self.client.write_register(1240, 1)
            await self.client.write_register(1240, 0)
        except ModbusException as e:
            logger.error(f"Error resetting error logs: {e}")
    def reset_error_logs(self):
        """ Reset the drive alarm registers."""
        try:
            self.client_sync.write_register(1240, 1)
            self.client_sync.write_register(1240, 0)
        except ModbusException as e:
            logger.error(f"Error resetting error logs: {e}")
            
    def save_parameters(self, 
                              store_parameters: bool,
                              store_ip_mask_gateway: bool
                              ):
        """ Used to store the parameters in the non-volatile memory.

        Parameters
        ----------
        store_parameters : bool
            Store the parameters in the non-volatile memory.
        store_ip_mask_gateway : bool
            Store the IP address, subnet mask and gateway in the non-volatile memory.
        """
        try:
            if store_parameters:
                self.client_sync.write_register(1260, 0x6173)
            if store_ip_mask_gateway:
                self.client_sync.write_register(1260, 0x1111)
            time.sleep(5)
            logger.info("Parameters saved.")
            
        except ModbusException as e:
            logger.error(f"Error saving parameters: {e}")
        
    def restore_default_parameters(self):
        """Restore the default parameters."""
        try:
            self.client_sync.write_register(1261, 0x6F6C)
            time.sleep(5)
            logger.info("Parameters Restored to default values.")
            
        except ModbusException as e:
            logger.error(f"Error restoring default parameters: {e}")
    
    
    
    
    
    ### Motion Registers ###
    async def get_status_word_async(self) -> Tuple[int, STATUS_WORD]:
        """Get the status word."""
        result = await self.client.read_holding_registers(1001)
        bits = to_bits_list(result.registers[0])
        
        status = STATUS_WORD._make(bits)
       
        return result.registers[0], status
    def get_status_word(self) -> Tuple[int, STATUS_WORD]:
        """Get the status word."""
        result = self.client_sync.read_holding_registers(1001)
        bits = to_bits_list(result.registers[0])
        
        status = STATUS_WORD._make(bits)
       
        return result.registers[0], status
    
    async def get_mode_of_operation_async(self) -> str:
        """Get the current mode of operation."""
        result = await self.client.read_holding_registers(1002) # I16
        mode = result.registers[0]
        
        return mode
    def get_mode_of_operation(self) -> str:
        """Get the current mode of operation."""
        result = self.client_sync.read_holding_registers(1002) # I16
        mode = result.registers[0]
        
        return mode
    
    async def get_actual_position_async(self) -> int:
        """Get the current position of the drive."""
        result = await self.client.read_holding_registers(1004, 2)
        position = merge_registers(result.registers)
        return position
    def get_actual_position(self) -> int:
        """Get the current position of the drive."""
        result = self.client_sync.read_holding_registers(1004, 2)
        position = merge_registers(result.registers)
        return position
    
    async def get_actual_velocity_async(self) -> int:
        """Get the current velocity of the drive."""
        result = await self.client.read_holding_registers(1020, 2)
        velocity = merge_registers(result.registers)
        return velocity
    def get_actual_velocity(self) -> int:
        """Get the current velocity of the drive."""
        result = self.client_sync.read_holding_registers(1020, 2)
        velocity = merge_registers(result.registers)
        return velocity
    
    async def get_target_position_async(self) -> int:
        """Get the target position of the drive."""
        result = await self.client.read_holding_registers(1042, 2)
        position = merge_registers(result.registers)
        return position
    def get_target_position(self) -> int:
        """Get the target position of the drive."""
        result = self.client_sync.read_holding_registers(1042, 2)
        position = merge_registers(result.registers)
        return position
    
    async def set_target_position_async(self, position: int):
        """Set the target position of the drive."""
        if position < -2147483648 or position > 2147483647:
            raise ValueError("Invalid target position.")
        
        lsb, msb = int32_to_uint16(position)
        try:
            await self.client.write_registers(1042, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting target position: {e}")
    def set_target_position(self, position: int):
        """Set the target position of the drive."""
        if position < -2147483648 or position > 2147483647:
            raise ValueError("Invalid target position.")
        
        lsb, msb = int32_to_uint16(position)
        try:
            self.client_sync.write_registers(1042, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting target position: {e}")
    
    async def get_target_velocity_async(self) -> int:
        """Get the target velocity in [Hz]."""
        result = await self.client.read_holding_registers(1048, 2)
        target_velocity = merge_registers(result.registers)
        return target_velocity
    def get_target_velocity(self) -> int:
        """Get the target velocity in [Hz]."""
        result = self.client_sync.read_holding_registers(1048, 2)
        target_velocity = merge_registers(result.registers)
        return target_velocity
    
    async def set_target_velocity_async(self, velocity: int):
        """Set the target velocity of the drive."""
        try:
            lsb, msb = int32_to_uint16(velocity)
            await self.client.write_registers(1048, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting target velocity: {e}")
    def set_target_velocity(self, velocity: int):
        """Set the target velocity of the drive."""
        try:
            lsb, msb = int32_to_uint16(velocity)
            self.client_sync.write_registers(1048, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting target velocity: {e}")
    
    async def get_profile_velocity_async(self) -> int:
        """Get the profile velocity in [Hz]."""
        result = await self.client.read_holding_registers(1044, 2)
        profile_velocity = merge_registers(result.registers)
        return profile_velocity
    def get_profile_velocity(self) -> int:
        """Get the profile velocity in [Hz]."""
        result = self.client_sync.read_holding_registers(1044, 2)
        profile_velocity = merge_registers(result.registers)
        return profile_velocity
    
    async def set_profile_velocity_async(self, velocity: int):
        """Set the profile velocity of the drive [0-800000]"""
        if velocity < 0 or velocity > 800000:
            raise ValueError("Invalid profile velocity.")
        try:
            lsb, msb = int32_to_uint16(velocity)
            await self.client.write_registers(1044, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting profile velocity: {e}")
    def set_profile_velocity(self, velocity: int):
        """Set the profile velocity of the drive [0-800000]"""
        if velocity < 0 or velocity > 800000:
            raise ValueError("Invalid profile velocity.")
        try:
            lsb, msb = int32_to_uint16(velocity)
            self.client_sync.write_registers(1044, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting profile velocity: {e}")
    
    async def get_profile_acceleration_async(self) -> int:
        """Get the profile acceleration in [Hz/s]."""
        result = await self.client.read_holding_registers(1046, 2)
        profile_acceleration = merge_registers(result.registers)
        return profile_acceleration
    def get_profile_acceleration(self) -> int:
        """Get the profile acceleration in [Hz/s]."""
        result = self.client_sync.read_holding_registers(1046, 2)
        profile_acceleration = merge_registers(result.registers)
        return profile_acceleration
    
    async def set_profile_acceleration_async(self, acceleration: int):
        """Set the profile acceleration of the drive [2000-10 000 000]"""
        if acceleration < 2000 or acceleration > 10000000:
            raise ValueError("Invalid profile acceleration.")
        try:
            lsb, msb = int32_to_uint16(acceleration)
            await self.client.write_registers(1046, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting profile acceleration: {e}")
    def set_profile_acceleration(self, acceleration: int):
        """Set the profile acceleration of the drive [2000-10 000 000]"""
        if acceleration < 2000 or acceleration > 10000000:
            raise ValueError("Invalid profile acceleration.")
        try:
            lsb, msb = int32_to_uint16(acceleration)
            self.client_sync.write_registers(1046, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting profile acceleration: {e}")
    
    async def get_profile_deceleration_async(self) -> int:
        """Get the profile deceleration in [Hz/s]."""
        result = await self.client.read_holding_registers(1072, 2)
        profile_deceleration = merge_registers(result.registers)
        return profile_deceleration
    def get_profile_deceleration(self) -> int:
        """Get the profile deceleration in [Hz/s]."""
        result = self.client_sync.read_holding_registers(1072, 2)
        profile_deceleration = merge_registers(result.registers)
        return profile_deceleration
    
    async def set_profile_deceleration_async(self, deceleration: int):
        """Set the profile deceleration of the drive [2000-10 000 000]"""
        if deceleration < 2000 or deceleration > 10000000:
            raise ValueError("Invalid profile deceleration.")
        try:
            lsb, msb = int32_to_uint16(deceleration)
            await self.client.write_registers(1072, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting profile deceleration: {e}")
    def set_profile_deceleration(self, deceleration: int):
        """Set the profile deceleration of the drive [2000-10 000 000]"""
        if deceleration < 2000 or deceleration > 10000000:
            raise ValueError("Invalid profile deceleration.")
        try:
            lsb, msb = int32_to_uint16(deceleration)
            self.client_sync.write_registers(1072, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting profile deceleration: {e}")
    
    async def get_velocity_window(self) -> int:
        raise NotImplementedError
    async def set_velocity_window(self, window: int):
        raise NotImplementedError
    async def get_velocity_window_time(self) -> int:
        raise NotImplementedError
    async def set_velocity_window_time(self, time: int):
        raise NotImplementedError
    async def get_velocity_threshold(self) -> int:
        raise NotImplementedError
    async def set_velocity_threshold(self, threshold: int):
        raise NotImplementedError
    async def get_velocity_threshold_time(self) -> int:
        raise NotImplementedError
    async def set_velocity_threshold_time(self, time: int):
        raise NotImplementedError
    
    
    async def set_mode_of_operation_async(self, mode: MODE_OF_OPERATION):
        """ Set the mode of operation 

        Parameters
        ----------
        mode : MODE_OF_OPERATION
            The desired mode of operation. Options are:
            - 1: Profile position mode
            - 3: Profile velocity mode
            - 6: Homing mode

        Raises
        ------
        ValueError
            If an invalid mode of operation is provided.
        """
        if mode not in [1, 3, 6]:
            raise ValueError("Invalid mode of operation.")
        
        try:
            await self.client.write_register(1041, mode)
        except ModbusException as e:
            logger.error(f"Error setting mode of operation: {e}")
    def set_mode_of_operation(self, mode: MODE_OF_OPERATION):
        """ Set the mode of operation 

        Parameters
        ----------
        mode : MODE_OF_OPERATION
            The desired mode of operation. Options are:
            - 1: Profile position mode
            - 3: Profile velocity mode
            - 6: Homing mode

        Raises
        ------
        ValueError
            If an invalid mode of operation is provided.
        """
        if mode not in [1, 3, 6]:
            raise ValueError("Invalid mode of operation.")
        
        try:
            self.client_sync.write_register(1041, mode)
        except ModbusException as e:
            logger.error(f"Error setting mode of operation: {e}")
            
           
    ### Control Word ###
    async def get_control_word_async(self) -> Tuple[int, CONTROL_WORD]:
        """Get the control word."""
        result = await self.client.read_holding_registers(1040)
        bits = to_bits_list(result.registers[0])
        
        control = CONTROL_WORD(*bits)
        
        return result.registers[0], control
    def get_control_word(self) -> Tuple[int, CONTROL_WORD]:
        """Get the control word."""
        result = self.client_sync.read_holding_registers(1040)
        bits = to_bits_list(result.registers[0])
        
        control = CONTROL_WORD(*bits)
        
        return result.registers[0], control
    
    async def set_control_word_async(self, control: CONTROL_WORD | int):
        """ Sets the whole control word.

        Parameters
        ----------
        control : CONTROL_WORD | int
            The control provided as a CONTROL_WORD class or as an int.
        """
        try:
            if isinstance(control, int):
                await self.client.write_register(1040, control)
            else:
                bits = control.to_bits()
                value = int(''.join([str(int(i)) for i in bits]), 2)
                await self.client.write_register(1040, value)
                
        except ModbusException as e:
            logger.error(f"Error setting control word: {e}")
    def set_control_word(self, control: CONTROL_WORD | int):
        """ Sets the whole control word.

        Parameters
        ----------
        control : CONTROL_WORD | int
            The control provided as a CONTROL_WORD class or as an int.
        """
        try:
            if isinstance(control, int):
                self.client_sync.write_register(1040, control)
            else:
                bits = control.to_bits()
                value = int(''.join([str(int(i)) for i in bits]), 2)
                self.client_sync.write_register(1040, value)
                
        except ModbusException as e:
            logger.error(f"Error setting control word: {e}")
            
    async def set_control_word_bit_async(self, bit: int, value: bool):
        """ Set the n-th bit to the value 0 or 1.

        Parameters
        ----------
        bit : int
            The bit index
        value : bool
            _description_
        """
        try:
            control_word = await self.get_control_word_async()
            control_word = control_word[0]
            # XOR the bit with the control word
            control_word ^= (-value ^ control_word) & (1 << bit)
            await self.set_control_word_async(control_word)
        except ModbusException as e:
            logger.error(f"Error setting control word bit: {e}")
    def set_control_word_bit(self, bit: int, value: bool):
        """ Set the n-th bit to the value 0 or 1.

        Parameters
        ----------
        bit : int
            The bit index
        value : bool
            _description_
        """
        try:
            control_word = self.get_control_word()
            control_word = control_word[0]
            # XOR the bit with the control word
            control_word ^= (-value ^ control_word) & (1 << bit)
            self.set_control_word(control_word)
        except ModbusException as e:
            logger.error(f"Error setting control word bit: {e}")
            
    async def set_control_word_bits_async(self, bits: Dict[int, bool]):
        """Set multiple bits in the control word."""
        try:
            control_word = await self.get_control_word_async()
            control_word = control_word[0]
            for bit, value in bits.items():
                control_word ^= (-value ^ control_word) & (1 << bit)
            await self.set_control_word_async(control_word)
        except ModbusException as e:
            logger.error(f"Error setting control word bits: {e}")
    def set_control_word_bits(self, bits: Dict[int, bool]):
        """Set multiple bits in the control word."""
        try:
            control_word = self.get_control_word()
            control_word = control_word[0]
            for bit, value in bits.items():
                control_word ^= (-value ^ control_word) & (1 << bit)
            self.set_control_word(control_word)
        except ModbusException as e:
            logger.error(f"Error setting control word bits: {e}")

         
    ### Drive Settings / Parameters ###   
    async def get_current_ratio_async(self) -> int:
        """Get the current ratio in [0 - 120 %]."""
        result = await self.client.read_holding_registers(1080)
        return result.registers[0]
    def get_current_ratio(self) -> int:
        """Get the current ratio in [0 - 120 %]."""
        result = self.client_sync.read_holding_registers(1080)
        return result.registers[0]
    
    async def set_current_ratio_async(self, ratio: int):
        """ Set the current ratio in [0 - 120 %].
        Allow to set the desired drive current (peak value supplied to the motor) related to the nominal
        full scale drive curren"""
        if ratio < 0 or ratio > 120:
            raise ValueError("Invalid current ratio.")
        
        try:
            await self.client.write_register(1080, ratio)
        except ModbusException as e:
            logger.error(f"Error setting current ratio: {e}")
    def set_current_ratio(self, ratio: int):
        """ Set the current ratio in [0 - 120 %].
        Allow to set the desired drive current (peak value supplied to the motor) related to the nominal
        full scale drive curren"""
        if ratio < 0 or ratio > 120:
            raise ValueError("Invalid current ratio.")
        
        try:
            self.client_sync.write_register(1080, ratio)
        except ModbusException as e:
            logger.error(f"Error setting current ratio: {e}")   
    
    async def get_step_revolution_async(self) -> int:
        """Get the steps per revolution in [12800 - 12800]."""
        result = await self.client.read_holding_registers(1081)
        return result.registers[0]
    def get_step_revolution(self) -> int:
        """Get the steps per revolution in [12800 - 12800]."""
        result = self.client_sync.read_holding_registers(1081)
        return result.registers[0]     
     
    async def get_current_reduction_async(self) -> int:
        """Get the current reduction in [1]."""
        result = await self.client.read_holding_registers(1083)
        return result.registers[0]
    def get_current_reduction(self) -> int:
        """Get the current reduction in [1]."""
        result = self.client_sync.read_holding_registers(1083)
        return result.registers[0]
    
    async def get_encoder_window_async(self) -> int:
        """Get the encoder window in 
        { 0: 0.9, 1: 1.8, 2: 3.6, 3: 5.4, 4: 7.2, 5: 9}
        """
        result = await self.client.read_holding_registers(1084)
        return result.registers[0]
    def get_encoder_window(self) -> int:
        """Get the encoder window in 
        { 0: 0.9, 1: 1.8, 2: 3.6, 3: 5.4, 4: 7.2, 5: 9}
        """
        result = self.client_sync.read_holding_registers(1084)
        return result.registers[0]
    
    async def set_encoder_window_async(self, window: int):
        """Set the encoder window. Valid values are [0, 1, 2, 3, 4, 5]. corresponding to [0.9, 1.8, 3.6, 5.4, 7.2, 9] degrees.
        
        The value of the encoder window corresponds to the limit of the angular error that causes the
        raising of the synchronism motor loss error with Auto Sync disabled (see note2) (the drive synloss
        reaction can be set by register 1085 Following Error Reaction Code).
        """
        if window not in [0, 1, 2, 3, 4, 5]:
            raise ValueError("Invalid encoder window.")
        
        try:
            await self.client.write_register(1084, window)
        except ModbusException as e:
            logger.error(f"Error setting encoder window: {e}")
    def set_encoder_window(self, window: int):
        """Set the encoder window. Valid values are [0, 1, 2, 3, 4, 5]. corresponding to [0.9, 1.8, 3.6, 5.4, 7.2, 9] degrees.
        
        The value of the encoder window corresponds to the limit of the angular error that causes the
        raising of the synchronism motor loss error with Auto Sync disabled (see note2) (the drive synloss
        reaction can be set by register 1085 Following Error Reaction Code).
        """
        if window not in [0, 1, 2, 3, 4, 5]:
            raise ValueError("Invalid encoder window.")
        
        try:
            self.client_sync.write_register(1084, window)
        except ModbusException as e:
            logger.error(f"Error setting encoder window: {e}")
        
    async def get_following_error_reaction_code_async(self) -> int:
        """Get the following error reaction code in [0 - 17].
        
        Following Error Reaction Code allows to set different possible drive reactions to maximum error,
        set by means of register 1084 if Auto Sync function is disabled or by means of registers 1110
        1111 if the Auto Sync function is enabled.
        Error causes the setting of bit 13 (Following Error) of Status Word at 1.
        
        In case of use of a motor without encoder, this register must be set to 17, see also details about
        registers 1090-1091.
        """
        result = await self.client.read_holding_registers(1085)
        return result.registers[0]
    def get_following_error_reaction_code(self) -> int:
        """Get the following error reaction code in [0 - 17].
        
        Following Error Reaction Code allows to set different possible drive reactions to maximum error,
        set by means of register 1084 if Auto Sync function is disabled or by means of registers 1110
        1111 if the Auto Sync function is enabled.
        Error causes the setting of bit 13 (Following Error) of Status Word at 1.
        
        In case of use of a motor without encoder, this register must be set to 17, see also details about
        registers 1090-1091.
        """
        result = self.client_sync.read_holding_registers(1085)
        return result.registers[0]
    
    async def set_following_error_reaction_code_async(self, code: int):
        """Set the following error reaction code in [0 - 17].
        
        Following Error Reaction Code allows to set different possible drive reactions to maximum error,
        set by means of register 1084 if Auto Sync function is disabled or by means of registers 1110
        1111 if the Auto Sync function is enabled.
        Error causes the setting of bit 13 (Following Error) of Status Word at 1.
        
        In case of use of a motor without encoder, this register must be set to 17, see also details about
        registers 1090-1091.
        """
        if code not in [0x00, 0x01, 0x02, 0x11]:
            raise ValueError("Invalid following error reaction code.")
        
        try:
            await self.client.write_register(1085, code)
        except ModbusException as e:
            logger.error(f"Error setting following error reaction code: {e}")
    def set_following_error_reaction_code(self, code: int):
        """Set the following error reaction code in [0 - 17].
        
        Following Error Reaction Code allows to set different possible drive reactions to maximum error,
        set by means of register 1084 if Auto Sync function is disabled or by means of registers 1110
        1111 if the Auto Sync function is enabled.
        Error causes the setting of bit 13 (Following Error) of Status Word at 1.
        
        In case of use of a motor without encoder, this register must be set to 17, see also details about
        registers 1090-1091.
        """
        if code not in [0x00, 0x01, 0x02, 0x11]:
            raise ValueError("Invalid following error reaction code.")
        
        try:
            self.client_sync.write_register(1085, code)
        except ModbusException as e:
            logger.error(f"Error setting following error reaction code: {e}")
            
    async def position_error_reset_async(self):
        """Reset the position error."""
        try:
            await self.client.write_register(1086, 1)
        except ModbusException as e:
            logger.error(f"Error resetting position error: {e}")
    def position_error_reset(self):
        """Reset the position eror."""
        try:
            self.client_sync.write_register(1086, 1)
        except ModbusException as e:
            logger.error(f"Error resetting position error: {e}")
            
    async def set_output_async(self, code: int):
        """Set the output."""
        if code not in range(0, 32):
            raise ValueError("Invalid output code.")
        
        try:
            await self.client.write_register(1087, code)
        except ModbusException as e:
            logger.error(f"Error setting output: {e}")      
    def set_output(self, code: int):
        """Set the output."""
        if code not in range(0, 32):
            raise ValueError("Invalid output code.")
        
        try:
            self.client_sync.write_register(1087, code)
        except ModbusException as e:
            logger.error(f"Error setting output: {e}")
        
    async def get_motor_code_async(self) -> int:
        """Get the motor code."""
        result = await self.client.read_holding_registers(1090, 2)
        motor_code = merge_registers(result.registers)
        return motor_code
    def get_motor_code(self) -> int:
        """Get the motor code."""
        result = self.client_sync.read_holding_registers(1090, 2)
        motor_code = merge_registers(result.registers)
        return motor_code
    
    async def set_motor_code_async(self, code: int):
        """Set the motor code."""
        try:
            await self.client.write_registers(1090, [code & 0xFFFF, code >> 16])
        except ModbusException as e:
            logger.error(f"Error setting motor code: {e}")
    def set_motor_code(self, code: int):
        """Set the motor code."""
        try:
            self.client_sync.write_registers(1090, [code & 0xFFFF, code >> 16])
        except ModbusException as e:
            logger.error(f"Error setting motor code: {e}")
            
    async def get_revolution_direction_async(self) -> str:
        """Get the revolution direction."""
        result = await self.client.read_holding_registers(1092)
        return result.registers[0]
    def get_revolution_direction(self) -> str:
        """Get the revolution direction."""
        result = self.client_sync.read_holding_registers(1092)
        return result.registers[0]
    
    async def set_revolution_direction_async(self, direction: int):
        """Set the revolution direction."""
        logger.warn("This parameter can only be set at machine start-up. It is not possible to change it during operation.")
        
        if direction not in [0, 1]:
            raise ValueError("Invalid revolution direction.")
        
        try:
            await self.client.write_register(1092, direction)
        except ModbusException as e:
            logger.error(f"Error setting revolution direction: {e}")
    def set_revolution_direction(self, direction: int):
        """Set the revolution direction."""
        logger.warn("This parameter can only be set at machine start-up. It is not possible to change it during operation.")
        
        if direction not in [0, 1]:
            raise ValueError("Invalid revolution direction.")
        
        try:
            self.client.write_register(1092, direction)
        except ModbusException as e:
            logger.error(f"Error setting revolution direction: {e}")
            
    async def get_current_reduction_ratio_async(self) -> int:
        """Get the current reduction ratio in [1 - 100 %]."""
        result = await self.client.read_holding_registers(1112)
        return result.registers[0]
    def get_current_reduction_ratio(self) -> int:
        """Get the current reduction ratio in [1 - 100 %]."""
        result = self.client_sync.read_holding_registers(1112)
        return result.registers[0]
    
    async def set_current_reduction_ratio_async(self, ratio: int):
        """Set the current reduction ratio in [1 - 100 %]."""
        if ratio < 1 or ratio > 100:
            raise ValueError("Invalid current reduction ratio.")
        
        try:
            await self.client.write_register(1112, ratio)
        except ModbusException as e:
            logger.error(f"Error setting current reduction ratio: {e}")
    def set_current_reduction_ratio(self, ratio: int):
        """Set the current reduction ratio in [1 - 100 %]."""
        if ratio < 1 or ratio > 100:
            raise ValueError("Invalid current reduction ratio.")
        
        try:
            self.client_sync.write_register(1112, ratio)
        except ModbusException as e:
            logger.error(f"Error setting current reduction ratio: {e}")
    
    async def get_motor_current_limit_async(self) -> int:
        """Get the motor current limit in [1 - 4 A]."""
        result = await self.client.read_holding_registers(1117)
        return result.registers[0]
    def get_motor_current_limit(self) -> int:
        """Get the motor current limit in [1 - 4 A]."""
        result = self.client_sync.read_holding_registers(1117)
        return result.registers[0]
    
    async def get_motor_proportional_gain_async(self) -> int:
        """Get the motor proportional gain [100 - 400 %]."""
        result = await self.client.read_holding_registers(1118)
        return result.registers[0]
    def get_motor_proportional_gain(self) -> int:
        """Get the motor proportional gain [100 - 400 %]."""
        result = self.client_sync.read_holding_registers(1118)
        return result.registers[0]
    
    async def get_motor_dynamic_balancing_async(self) -> int:
        """Get the motor dynamic balancing [0 - 500 %]."""
        result = await self.client.read_holding_registers(1119)
        return result.registers[0]
    def get_motor_dynamic_balancing(self) -> int:
        """Get the motor dynamic balancing [0 - 500 %]."""
        result = self.client_sync.read_holding_registers(1119)
        return result.registers[0]
    
    async def get_motor_current_recycling_enable_async(self) -> bool:
        """Get the motor current recycling enable."""
        result = await self.client.read_holding_registers(1120)
        return bool(result.registers[0])
    def get_motor_current_recycling_enable(self) -> bool:
        """Get the motor current recycling enable."""
        result = self.client_sync.read_holding_registers(1120)
        return bool(result.registers[0])
    
    async def get_encoder_count_per_revolution_async(self) -> int:
        """Get the encoder count per revolution. [400-4000]"""
        result = await self.client.read_holding_registers(1121)
        return result.registers[0]
    def get_encoder_count_per_revolution(self) -> int:
        """Get the encoder count per revolution. [400-4000]"""
        result = self.client_sync.read_holding_registers(1121)
        return result.registers[0]
    
    async def set_encoder_count_per_revolution_async(self, count: int):
        """Set the encoder count per revolution."""
        if count < 400 or count > 4000:
            raise ValueError("Invalid encoder count per revolution.")
        
        try:
            await self.client.write_register(1121, count)
        except ModbusException as e:
            logger.error(f"Error setting encoder count per revolution: {e}")
    def set_encoder_count_per_revolution(self, count: int):
        """Set the encoder count per revolution."""
        if count < 400 or count > 4000:
            raise ValueError("Invalid encoder count per revolution.")
        
        try:
            self.client_sync.write_register(1121, count)
        except ModbusException as e:
            logger.error(f"Error setting encoder count per revolution: {e}")       
            
            
            
    