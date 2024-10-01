from typing import Any, Dict, List, Tuple, Literal, Union, cast
import time
import threading
import queue
import types
import time

from pymodbus.client import ModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.constants import Endian
from pymodbus.framer import FramerType
from pymodbus import (
    ExceptionResponse,
    ModbusException,
    pymodbus_apply_logging_config,
)
import asyncio
import logging
from .utils import merge_registers, to_bits_list, int32_to_uint16, encode_bits_to_payload, decode_payload_to_bits
from .thread_safe_wrapper import ThreadSafeClientWrapper
from .definitions import *

logger = logging.getLogger(__name__)

class CSD_MT_94:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._client = ModbusTcpClient(
            host,
            port=port,
            framer=FramerType.SOCKET,
        )
        self._client = cast(ModbusTcpClient, ThreadSafeClientWrapper(self._client))
        
    def connect(self):
        self._client.connect()
        
    def __del__(self):
        self._client.stop()
        self.switch_off()
        self._client.close()
        
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.switch_off()
        self._client.close()
     
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self._client.is_socket_open()
   
    def move(self,
            position: int,
            cs: Literal["absolute", "relative"] = "relative",
            change_setpoint_immediately: bool = False,
            wait_for_target_reached: bool = False,
            timeout: float = 10,
        ) -> bool:
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
        scs = self.set_control_word_bits({4: False, 5: change_setpoint_immediately, 6: cs == "relative"})
        scs += self.set_target_position(position)        
        scs += self.set_control_word_bit(4, True)
        
        if scs != 3:
            return False
        
        if wait_for_target_reached:
            target_reached = False
            timeout = time.time() + timeout
            while not target_reached:
                sw = self.get_status_word()
                if sw is None:
                    return False                
                
                target_reached = sw[1].target_reached
                if time.time() > timeout:
                    return False
        
        return True
   
    def halt(self) -> bool:
        """ Toggles the halt bit in the control word. Does not permanently stop the drive."""
        success = self.set_control_word_bit(8, True)
        self.set_control_word_bit(8, False)
        return success
        
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
        current_position = self.get_actual_position()
        if steps_per_revolution is None or current_position is None:
            return False
        
        if cs == "relative":
            target_position = angle * steps_per_revolution / (2 * 3.14159)
            target_position = int(target_position)
        else:
            target_position = current_position + angle * steps_per_revolution / (2 * 3.14159)
            target_position = int(target_position)
            
        scs = self.set_control_word_bits({4: False, 5: change_setpoint_immediately, 6: cs == "relative"})
        scs += self.set_target_position(target_position)
        scs += self.set_control_word_bit(4, True)
        
        if scs != 3:
            return False
        
        if wait_for_target_reached:
            target_reached = False
            timeout = time.time() + timeout
            while not target_reached:
                sw = self.get_status_word()
                if sw is None:
                    return False
                
                target_reached = sw[1].target_reached
                if time.time() > timeout:
                    return False
               
        return True 

    def switch_on(self) -> bool:
        """Switch on the drive."""
        try:
            success = self.set_control_word_bit(0, True)
            if success:
                return True
            else:
                return False
        except ModbusException as e:
            logger.error(f"Error switching on drive: {e}")
            return False
            
    def switch_off(self) -> bool:
        """Switch off the drive."""
        try:
            success = self._client.write_register(1040, 0)
            if success:
                return True
            else:
                return False
            
        except ModbusException as e:
            logger.error(f"Error switching off drive: {e}")
            return False
            
    def enable_voltage(self) -> bool:
        """Enable the voltage."""
        try:
            success = self.set_control_word_bit(1, True)
            if success:
                return True
            else:
                return False
        except ModbusException as e:
            logger.error(f"Error enabling voltage: {e}")
            return False
            
    def disable_voltage(self) -> bool:
        """Disable the voltage."""
        try:
            success = self.set_control_word_bit(1, False)
            if success:
                return True
            else:
                return False
            
        except ModbusException as e:
            logger.error(f"Error disabling voltage: {e}")
            return False
            
    def quick_stop(self) -> bool:
        """Quick stop the drive."""
        try:
            success = self.set_control_word_bit(2, True)
            if not success:
                return False
            else:
                return True          
            
        except ModbusException as e:
            logger.error(f"Error quick stopping drive: {e}")
            return False
            
    def release_quick_stop(self) -> bool:
        """Release the quick stop."""
        try:
            success = self.set_control_word_bit(2, False)
            if not success:
                return False
            else:
                return True
            
            
        except ModbusException as e:
            logger.error(f"Error releasing quick stop: {e}")
            return False
    
    def enable_operation(self) -> bool:
        """Enable operation."""
        try:
            success = self.set_control_word_bit(3, True)
            if not success:
                return False
            else:
                return True
        except ModbusException as e:
            logger.error(f"Error enabling operation: {e}")
            return False
        
            
    ### Configuration Registers ###
    def get_ip_address(self) -> str | None:
        try:
            result = self._client.read_holding_registers(1130, 4)
        except ModbusException as e:
            logger.error(f"Error getting IP address: {e}")
            return None
            
        p1 = BinaryPayloadDecoder.fromRegisters([result.registers[0]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p2 = BinaryPayloadDecoder.fromRegisters([result.registers[1]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p3 = BinaryPayloadDecoder.fromRegisters([result.registers[2]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p4 = BinaryPayloadDecoder.fromRegisters([result.registers[3]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        
        ip = '.'.join([str(p1), str(p2), str(p3), str(p4)])
        return ip
    
    def get_netmask_async(self) -> str | None:
        try:
            result = self._client.read_holding_registers(1134, 4)
        except ModbusException as e:
            logger.error(f"Error getting netmask: {e}")
            return None
        
        p1 = BinaryPayloadDecoder.fromRegisters([result.registers[0]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p2 = BinaryPayloadDecoder.fromRegisters([result.registers[1]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p3 = BinaryPayloadDecoder.fromRegisters([result.registers[2]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p4 = BinaryPayloadDecoder.fromRegisters([result.registers[3]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        
        netmask = '.'.join([str(p1), str(p2), str(p3), str(p4)])
        return netmask
    
    def get_gateway_async(self) -> str | None:
        try:
            result = self._client.read_holding_registers(1138, 4)
        except ModbusException as e:
            logger.error(f"Error getting gateway: {e}")
            return None
        
        p1 = BinaryPayloadDecoder.fromRegisters([result.registers[0]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p2 = BinaryPayloadDecoder.fromRegisters([result.registers[1]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p3 = BinaryPayloadDecoder.fromRegisters([result.registers[2]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        p4 = BinaryPayloadDecoder.fromRegisters([result.registers[3]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        
        gateway = '.'.join([str(p1), str(p2), str(p3), str(p4)])
        
        return gateway
    
    ### Identification Registers ###
    def get_device_info(self) -> Dict[str, Union[str, int]] | None:
        try:
            result = self._client.read_holding_registers(1152, 9)
        except ModbusException as e:
            logger.error(f"Error getting device info: {e}")
            return None
        
        software_version = BinaryPayloadDecoder.fromRegisters(result.registers[0:2], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_uint()
        product_code = BinaryPayloadDecoder.fromRegisters(result.registers[2:4], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_uint()
        hardware_version = BinaryPayloadDecoder.fromRegisters(result.registers[4:6], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_uint()
        serial_number = BinaryPayloadDecoder.fromRegisters(result.registers[6:8], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_uint()
        little_big_endian = result.registers[8]
            
        return {
            'software_version': software_version,
            'product_code': product_code,
            'hardware_version': hardware_version,
            'serial_number': serial_number,
            'little_big_endian': little_big_endian,
        }
        
    ### Service Registers ###
    def is_error(self) -> bool | None:
        """Check if the drive is in an error state."""
        try:
            result = self._client.read_holding_registers(1006) #U16
        except ModbusException as e:
            logger.error(f"Error checking if drive is in error state: {e}")
            return None
        
        is_error = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        
        return bool(is_error)
    
    def get_error_code(self) -> Dict[Literal["error_code", "error_message"], Union[str, int]] | None:
        try:
            result = self._client.read_holding_registers(1007) #U16
        except ModbusException as e:
            logger.error(f"Error getting error code: {e}")
            return None
        
        error_code = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        
        error = ERROR_CODES.get(error_code, "Unknown error")
        
        return {"error_code": error_code, "error_message": error}
        
    def get_drive_temperature(self) -> int | None:
        """Get the drive temperature in degrees Celsius."""
        try:
            result = self._client.read_holding_registers(1124, 1) #U16
        except ModbusException as e:
            logger.error(f"Error getting drive temperature: {e}")
            return None
        
        drive_temperature = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
        
        return drive_temperature
    
    def get_warning_temperature(self) -> int | None:
        raise NotImplementedError
    
    def set_warning_temperature(self, temperature: int):
        raise NotImplementedError
    
    def get_fault_temperature(self) -> int:
        raise NotImplementedError
    
    def set_fault_temperature(self, temperature: int):
        raise NotImplementedError
    

    def get_drive_alarms(self) -> List[dict] | None:
        """ 10 events Alarm Register.
        For each event the event delay since power on and the event code are stored. 

        Returns
        -------
        List[dict]
            List of dictionaries containing the "alarm_time" and "alarm_code".
        """
        try:
            result = self._client.read_holding_registers(1220, 20)
        except ModbusException as e:
            logger.error(f"Error getting drive alarms: {e}")
            return None
        
        # Even indexes are the alarm times, odd indexes are the alarm codes
        alarms = []
        for i in range(0, len(result.registers), 2):
            alarm = {
                "alarm_time": BinaryPayloadDecoder.fromRegisters([result.registers[i]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint(),
                "alarm_code": BinaryPayloadDecoder.fromRegisters([result.registers[i+1]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint(),
            }
            alarms.append(alarm)
        return alarms
    
    def reset_error_logs(self) -> bool:
        """ Reset the drive alarm registers."""
        try:
            self._client.write_register(1240, 1)
            self._client.write_register(1240, 0)
            return True
        except ModbusException as e:
            logger.error(f"Error resetting error logs: {e}")
            return False
            
    def save_parameters(self, 
                              store_parameters: bool,
                              store_ip_mask_gateway: bool
                              ) -> bool:
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
                self._client.write_register(1260, 0x6173)
            if store_ip_mask_gateway:
                self._client.write_register(1260, 0x1111)
            time.sleep(5)
            logger.info("Parameters saved.")
            return True
            
        except ModbusException as e:
            logger.error(f"Error saving parameters: {e}")
            return False
        
    def restore_default_parameters(self) -> bool:
        """Restore the default parameters."""
        try:
            self._client.write_register(1261, 0x6F6C)
            time.sleep(5)
            logger.info("Parameters Restored to default values.")
            return True
            
        except ModbusException as e:
            logger.error(f"Error restoring default parameters: {e}")
            return False
    
    
    ### Motion Registers ###
    def get_status_word(self) -> Tuple[int, STATUS_WORD] | None:
        """Get the status word."""
        try:
            result = self._client.read_holding_registers(1001)
        except ModbusException as e:
            logger.error(f"Error getting status word: {e}")
            return None
        
        payload = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        
        bits = decode_payload_to_bits(payload, "uint16")
        values = list(bits.values())
        
        status = STATUS_WORD(*values[::-1])
       
        return result.registers[0], status
    
    def get_mode_of_operation(self) -> MODE_OF_OPERATION | None:
        """Get the current mode of operation."""
        try:
            result = self._client.read_holding_registers(1002) # I16
        except ModbusException as e:
            logger.error(f"Error getting mode of operation: {e}")
            return None
            
        mode = BinaryPayloadDecoder.fromRegisters([result.registers[0]], byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_int()
                    
        return mode
    
    def get_actual_position(self) -> int | None:
        """Get the current position of the drive."""
        try:
            result = self._client.read_holding_registers(1004, 2)
        except ModbusException as e:
            logger.error(f"Error getting actual position: {e}")
            return None
        
        position = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_int()
        
        return position
    
    def get_actual_velocity(self) -> int | None:
        """Get the current velocity of the drive."""
        try:
            result = self._client.read_holding_registers(1020, 2)
        except ModbusException as e:
            logger.error(f"Error getting actual velocity: {e}")
            return None
        
        velocity = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_int()
        
        return velocity
    
    def get_target_position(self) -> int | None:
        """Get the target position of the drive."""
        try:
            result = self._client.read_holding_registers(1042, 2)
        except ModbusException as e:
            logger.error(f"Error getting target position: {e}")
            return None
        
        position = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_int()

        return position
    

    def set_target_position(self, position: int) -> bool:
        """Set the target position of the drive."""
        if position < -2**31 or position > 2**31 - 1:
            logger.error("Invalid position Value. Should be between -2^31 and 2^31 - 1.")
            return False
        
        payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        payload.add_32bit_int(position)
        
        try:
            self._client.write_registers(1042, payload.to_registers())
            return True
        except ModbusException as e:
            logger.error(f"Error setting target position: {e}")
            return False
    
    def get_target_velocity(self) -> int | None:
        """Get the target velocity in [Hz]."""
        try:
            result = self._client.read_holding_registers(1048, 2)
        except ModbusException as e:
            logger.error(f"Error getting target velocity: {e}")
            return None
            
        target_velocity = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_int()
        return target_velocity
    
    def set_target_velocity(self, velocity: int) -> bool:
        """Set the target velocity of the drive."""
        if velocity < 0 or velocity > 800000:
            logger.error("Invalid target velocity. Should be between 0 and 800000.")
            return False
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_32bit_int(velocity)
            self._client.write_registers(1048, payload.to_registers())
            return True

        except ModbusException as e:
            logger.error(f"Error setting target velocity: {e}")
            return False
    
    def get_profile_velocity(self) -> int | None:
        """Get the profile velocity in [Hz]."""
        try:
            result = self._client.read_holding_registers(1044, 2)
        except ModbusException as e:
            logger.error(f"Error getting profile velocity: {e}")
            return None
        profile_velocity = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_int()
        return profile_velocity
    
    def set_profile_velocity(self, velocity: int) -> bool:
        """Set the profile velocity of the drive [0-800000]"""
        if velocity < 0 or velocity > 800000:
            logger.error("Invalid profile velocity. Should be between 0 and 800000.")
            return False
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_32bit_int(velocity)
            self._client.write_registers(1044, payload.to_registers())
            return True
        except ModbusException as e:
            logger.error(f"Error setting profile velocity: {e}")
            return False
    
    def get_profile_acceleration(self) -> int | None:
        """Get the profile acceleration in [Hz/s]."""
        try:
            result = self._client.read_holding_registers(1046, 2)
        except ModbusException as e:
            logger.error(f"Error getting profile acceleration: {e}")
            return None
            
        profile_acceleration = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_int()
        return profile_acceleration
    
    def set_profile_acceleration(self, acceleration: int) -> bool:
        """Set the profile acceleration of the drive [2000-10 000 000]"""
        if acceleration < 2000 or acceleration > 10000000:
            logger.error("Invalid profile acceleration.")
            return False
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_32bit_int(acceleration)
            self._client.write_registers(1046, payload.to_registers())
            return True
        except ModbusException as e:
            logger.error(f"Error setting profile acceleration: {e}")
            return False
    
    def get_profile_deceleration(self) -> int | None:
        """Get the profile deceleration in [Hz/s]."""
        try:
            result = self._client.read_holding_registers(1072, 2)
        except ModbusException as e:
            logger.error(f"Error getting profile deceleration: {e}")
            return None
        profile_deceleration = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_int()
        
        return profile_deceleration
    
    def set_profile_deceleration(self, deceleration: int) -> bool:
        """Set the profile deceleration of the drive [2000-10 000 000]"""
        if deceleration < 2000 or deceleration > 10000000:
            logger.error("Invalid profile deceleration.")
            return False
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_32bit_int(deceleration)
            self._client.write_registers(1072, payload.to_registers())
            return True
            
        except ModbusException as e:
            logger.error(f"Error setting profile deceleration: {e}")
            return False
    
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
    
    def set_mode_of_operation(self, mode: MODE_OF_OPERATION) -> bool:
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
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_16bit_int(mode)
            self._client.write_register(1041, payload.to_registers()[0])
            return True
        except ModbusException as e:
            logger.error(f"Error setting mode of operation: {e}")
            return False
            
                 
    ### Control Word ###
    def get_control_word(self) -> None | Tuple[int, CONTROL_WORD]:
        """Get the control word."""
        try:
            result = self._client.read_holding_registers(1040)
        except ModbusException as e:
            logger.error(f"Error getting control word: {e}")
            return None
            
        payload = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        bits = decode_payload_to_bits(payload, "uint16")
        
        values = list(bits.values())
        
        
        control = CONTROL_WORD(*values[::-1])
        
        return result.registers[0], control
    
    def set_control_word(self, control: CONTROL_WORD | int | BinaryPayloadBuilder) -> bool:
        """ Sets the whole control word.

        Parameters
        ----------
        control : CONTROL_WORD | int
            The control provided as a CONTROL_WORD class or as an int.
        """
        try:
            if isinstance(control, int):
                payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
                payload.add_16bit_uint(control)
                
                self._client.write_register(1040, payload.to_registers()[0])
                
            elif isinstance(control, BinaryPayloadBuilder):
                self._client.write_register(1040, control.to_registers()[0])
                
            else:
                payload = encode_bits_to_payload(control.to_bits(), "uint16", byteorder=Endian.BIG, wordorder=Endian.LITTLE)
                self._client.write_register(1040, payload.to_registers()[0])
            return True
                
        except ModbusException as e:
            logger.error(f"Error setting control word: {e}")
            return False

    def set_control_word_bit(self, bit: int, value: bool) -> bool:
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
            if control_word is None:
                return False
            
            payload = BinaryPayloadDecoder.fromRegisters([control_word[0]], byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            
            bits = decode_payload_to_bits(payload, "uint16")
            bits[bit] = value
            payload = encode_bits_to_payload(bits, "uint16", byteorder=Endian.BIG, wordorder=Endian.LITTLE)

            suc = self.set_control_word(payload)
            return suc
        
        except ModbusException as e:
            logger.error(f"Error setting control word bit: {e}")
            return False
            
    def set_control_word_bits(self, bits: Dict[int, bool]) -> bool:
        """Set multiple bits in the control word."""
        try:
            control_word = self.get_control_word()
            if control_word is None:
                return False
            
            payload = BinaryPayloadDecoder.fromRegisters([control_word[0]], byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            
            bits_old = decode_payload_to_bits(payload, "uint16")
            for bit, value in bits.items():
                bits_old[bit] = value
                
            payload = encode_bits_to_payload(bits_old, "uint16", byteorder=Endian.BIG, wordorder=Endian.LITTLE)

            suc = self.set_control_word(payload)
            return suc
        except ModbusException as e:
            logger.error(f"Error setting control word bits: {e}")
            return False
       
    ### Drive Settings / Parameters ###   
    def get_current_ratio(self) -> int | None:
        """Get the current ratio in [0 - 120 %]."""
        try:
            result = self._client.read_holding_registers(1080)
        except ModbusException as e:
            logger.error(f"Error getting current ratio: {e}")
            return None
        
        ratio = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_8bit_uint()
            
        return ratio
    
    def set_current_ratio(self, ratio: int) -> bool:
        """ Set the current ratio in [0 - 120 %].
        Allow to set the desired drive current (peak value supplied to the motor) related to the nominal
        full scale drive curren"""
        if ratio < 0 or ratio > 120:
            logger.error("Invalid current ratio.")
            return False
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_8bit_uint(ratio)
            self._client.write_register(1080, payload.to_registers()[0])
            return True
        except ModbusException as e:
            logger.error(f"Error setting current ratio: {e}")
            return False 
    
    def get_step_revolution(self) -> int | None:
        """Get the steps per revolution in [12800 - 12800]."""
        try:
            result = self._client.read_holding_registers(1081)
            if result.isError():
                logger.error(f"Error getting step revolution: {result}")
                return None
            step_revolution = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
            return step_revolution
            
        except ModbusException as e:
            logger.error(f"Error getting step revolution: {e}")
            return None
     
    def get_current_reduction(self) -> int | None:
        """Get the current reduction in [1]."""
        try:
            result = self._client.read_holding_registers(1083)
            reduction = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_8bit_uint()
            return reduction
        except ModbusException as e:
            logger.error(f"Error getting current reduction: {e}")
            return None
                
    def get_encoder_window(self) -> int | None:
        """Get the encoder window in 
        { 0: 0.9, 1: 1.8, 2: 3.6, 3: 5.4, 4: 7.2, 5: 9}
        """
        try:
            result = self._client.read_holding_registers(1084)
            encoder_window = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_8bit_uint()
            return encoder_window
        except ModbusException as e:
            logger.error(f"Error getting encoder window: {e}")
            return None
                
    def set_encoder_window(self, window: int) -> bool:
        """Set the encoder window. Valid values are [0, 1, 2, 3, 4, 5]. corresponding to [0.9, 1.8, 3.6, 5.4, 7.2, 9] degrees.
        
        The value of the encoder window corresponds to the limit of the angular error that causes the
        raising of the synchronism motor loss error with Auto Sync disabled (see note2) (the drive synloss
        reaction can be set by register 1085 Following Error Reaction Code).
        """
        if window not in [0, 1, 2, 3, 4, 5]:
            raise ValueError("Invalid encoder window.")
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_8bit_uint(window)
            self._client.write_register(1084, payload.to_registers()[0])
            return True
        except ModbusException as e:
            logger.error(f"Error setting encoder window: {e}")
            return False
        
    def get_following_error_reaction_code(self) -> int | None:
        """Get the following error reaction code in [0 - 17].
        
        Following Error Reaction Code allows to set different possible drive reactions to maximum error,
        set by means of register 1084 if Auto Sync function is disabled or by means of registers 1110
        1111 if the Auto Sync function is enabled.
        Error causes the setting of bit 13 (Following Error) of Status Word at 1.
        
        In case of use of a motor without encoder, this register must be set to 17, see also details about
        registers 1090-1091.
        """
        try:
            result = self._client.read_holding_registers(1085)
            error_reaction_code = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_8bit_uint()
            return error_reaction_code
        except ModbusException as e:
            logger.error(f"Error getting following error reaction code: {e}")
            return None
    
    def set_following_error_reaction_code(self, code: int) -> bool:
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
            self._client.write_register(1085, code)
            return True
            
        except ModbusException as e:
            logger.error(f"Error setting following error reaction code: {e}")
            return False
            
    def position_error_reset(self) -> bool:
        """Reset the position eror."""
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_8bit_uint(1)
            
            self._client.write_register(1086, payload.to_registers()[0])
            return True
        except ModbusException as e:
            logger.error(f"Error resetting position error: {e}")
            return False
               
    def set_output(self, code: int) -> bool:
        """Set the output."""
        if code not in range(0, 32):
            raise ValueError("Invalid output code.")
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_8bit_uint(code)
            self._client.write_register(1087, payload.to_registers()[0])
            return True
        except ModbusException as e:
            logger.error(f"Error setting output: {e}")
            return False
        
    def get_motor_code(self) -> int | None:
        """Get the motor code."""
        try:
            result = self._client.read_holding_registers(1090, 2)
            motor_code = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_32bit_uint()
            return motor_code
        except ModbusException as e:
            logger.error(f"Error getting motor code: {e}")
            return None
    
    def set_motor_code(self, code: int) -> bool:
        """Set the motor code."""
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_32bit_uint(code)
            
            self._client.write_registers(1090, payload.to_registers())
            return True
        
        except ModbusException as e:
            logger.error(f"Error setting motor code: {e}")
            return False
            
    def get_revolution_direction(self) -> int | None:
        """Get the revolution direction."""
        try:
            result = self._client.read_holding_registers(1092)
            direction = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_8bit_uint()
            return direction
        except ModbusException as e:
            logger.error(f"Error getting revolution direction: {e}")
            return None
    
    def set_revolution_direction(self, direction: int) -> bool:
        """Set the revolution direction."""
        logger.warn("This parameter can only be set at machine start-up. It is not possible to change it during operation.")
        
        if direction not in [0, 1]:
            raise ValueError("Invalid revolution direction.")
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_8bit_uint(direction)
            self._client.write_register(1092, payload.to_registers()[0])
            return True
        except ModbusException as e:
            logger.error(f"Error setting revolution direction: {e}")
            return False
            
    def get_current_reduction_ratio(self) -> int | None:
        """Get the current reduction ratio in [1 - 100 %]."""
        try:
            result = self._client.read_holding_registers(1112)
            reduction_ratio = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE).decode_16bit_uint()
            return reduction_ratio
        except ModbusException as e:
            logger.error(f"Error getting current reduction ratio: {e}")
            return None
    
    def set_current_reduction_ratio(self, ratio: int) -> bool:
        """Set the current reduction ratio in [1 - 100 %]."""
        if ratio < 1 or ratio > 100:
            raise ValueError("Invalid current reduction ratio.")
        
        try:
            payload = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
            payload.add_16bit_uint(ratio)
            self._client.write_register(1112, payload.to_registers()[0])
            return True
        except ModbusException as e:
            logger.error(f"Error setting current reduction ratio: {e}")
            return False
    
    def get_motor_current_limit(self) -> int:
        """Get the motor current limit in [1 - 4 A]."""
        result = self._client.read_holding_registers(1117)
        return result.registers[0]
    
    def get_motor_proportional_gain(self) -> int:
        """Get the motor proportional gain [100 - 400 %]."""
        result = self._client.read_holding_registers(1118)
        return result.registers[0]
    
    def get_motor_dynamic_balancing(self) -> int:
        """Get the motor dynamic balancing [0 - 500 %]."""
        result = self._client.read_holding_registers(1119)
        return result.registers[0]
    
    def get_motor_current_recycling_enable(self) -> bool:
        """Get the motor current recycling enable."""
        result = self._client.read_holding_registers(1120)
        return bool(result.registers[0])
    
    def get_encoder_count_per_revolution(self) -> int:
        """Get the encoder count per revolution. [400-4000]"""
        result = self._client.read_holding_registers(1121)
        return result.registers[0]
    
    def set_encoder_count_per_revolution(self, count: int):
        """Set the encoder count per revolution."""
        if count < 400 or count > 4000:
            raise ValueError("Invalid encoder count per revolution.")
        
        try:
            self._client.write_register(1121, count)
        except ModbusException as e:
            logger.error(f"Error setting encoder count per revolution: {e}")       
            
            
            
    