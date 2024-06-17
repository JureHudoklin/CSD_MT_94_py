from typing import Any, Dict, List, Tuple, Literal, Union
import time

from pymodbus.client import AsyncModbusTcpClient
from pymodbus import (
    ExceptionResponse,
    Framer,
    ModbusException,
    pymodbus_apply_logging_config,
)
import asyncio
import logging
import utils

logger = logging.getLogger(__name__)


class CSD_MT_94:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client = AsyncModbusTcpClient(
            host,
            port=port,
            framer=Framer.SOCKET,
        )        
        
    async def start_connection(self):
        await self.client.connect()
        
    def __del__(self):
        self.client.close()

    def _merge_registers(self, registers):
        return (registers[1] << 16) + registers[0]
    
    def _to_bits(self, value) -> list:
        return [bool(int(i)) for i in f"{value:016b}"]
    
    def _to_uint16(self, value) -> Tuple[int, int]:
        return value & 0xFFFF, value >> 16
    
    async def is_error(self) -> bool:
        """Check if the drive is in an error state."""
        result = await self.client.read_holding_registers(1006) #U16
        return bool(result.registers[0])
    
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self.client.is_active()
    
    async def switch_on(self):
        """Switch on the drive."""
        try:
            await self.set_control_word_bit(0, True)
        except ModbusException as e:
            logger.error(f"Error switching on drive: {e}")
    async def switch_off(self):
        """Switch off the drive."""
        try:
            await self.set_control_word_bit(0, False)
        except ModbusException as e:
            logger.error(f"Error switching off drive: {e}")
            
    async def enable_voltage(self):
        """Enable the voltage."""
        try:
            await self.set_control_word_bit(1, True)
        except ModbusException as e:
            logger.error(f"Error enabling voltage: {e}")
    async def disable_voltage(self):
        """Disable the voltage."""
        try:
            await self.set_control_word_bit(1, False)
        except ModbusException as e:
            logger.error(f"Error disabling voltage: {e}")
            
    async def quick_stop(self):
        """Quick stop the drive."""
        try:
            await self.set_control_word_bit(2, True)
        except ModbusException as e:
            logger.error(f"Error quick stopping drive: {e}")
    async def release_quick_stop(self):
        """Release the quick stop."""
        try:
            await self.set_control_word_bit(2, False)
        except ModbusException as e:
            logger.error(f"Error releasing quick stop: {e}")
    
    async def enable_operation(self):
        """Enable operation."""
        try:
            await self.set_control_word_bit(3, True)
        except ModbusException as e:
            logger.error(f"Error enabling operation: {e}")
    async def disable_operation(self):
        """Disable operation."""
        try:
            await self.set_control_word_bit(3, False)
        except ModbusException as e:
            logger.error(f"Error disabling operation: {e}")
        
    async def move(self,
                   position: int,
                   cs: Literal["absolute", "relative"] = "relative",
                   timeout: float = 10):
        """Move to a specific position."""
        await self.set_control_word_bit(4, False)
        await self.set_control_word_bit(5, False)
        
        await self.set_target_position(position)

        if cs == "relative":
            await self.set_control_word_bit(6, True)
        else:
            await self.set_control_word_bit(6, False)
            
        await self.set_control_word_bit(4, True)
        
               
        target_reached = False
        timeout = time.time() + timeout
        while not target_reached:
            sw = await self.get_status_word()
            target_reached = sw[1].target_reached
            if time.time() > timeout:
                return
        
    async def move_async(self, position: int, cs: Literal["absolute", "relative"] = "relative"):
        """Move to a specific position."""
        await self.set_control_word_bit(4, False)
        await self.set_target_position(position)
        
        if cs == "relative":
            await self.set_control_word_bit(6, True)
        else:
            await self.set_control_word_bit(6, False)
            
        await self.set_control_word_bit(4, True)
        
        
            
    ### Getters ###
        
    async def get_ip_address(self) -> str:
        result = await self.client.read_holding_registers(1130, 4)
        ip = '.'.join([str(i) for i in result.registers])
        return ip
    
    async def get_netmask(self) -> str:
        result = await self.client.read_holding_registers(1134, 4)
        netmask = '.'.join([str(i) for i in result.registers])
        return netmask

    async def get_gateway(self) -> str:
        result = await self.client.read_holding_registers(1138, 4)
        gateway = '.'.join([str(i) for i in result.registers])
        return gateway
    
    async def get_device_info(self) -> dict:
        result = await self.client.read_holding_registers(1152, 9)
        software_version = self._merge_registers(result.registers[0:2])
        product_code = self._merge_registers(result.registers[2:4])
        hardware_version = self._merge_registers(result.registers[4:6])
        serial_number = self._merge_registers(result.registers[6:8])
        little_big_endian = result.registers[8]
        
        return {
            'software_version': software_version,
            'product_code': product_code,
            'hardware_version': hardware_version,
            'serial_number': serial_number,
            'little_big_endian': little_big_endian,
        }
        
    async def get_error_code(self) -> Dict[Literal["error_code", "error_message"], Union[str, int]]:
        result = await self.client.read_holding_registers(1007) #U16
        error = utils.ERROR_CODES.get(result.registers[0], "Unknown error")
        
        return {"error_code": result.registers[0], "error_message": error}
        
    async def get_drive_temperature(self) -> int:
        """Get the drive temperature in degrees Celsius."""
        result = await self.client.read_holding_registers(1124, 1) #U16
        return result.registers[0]
    
    async def get_status_word(self) -> Tuple[int, utils.STATUS_WORD]:
        """Get the status word."""
        result = await self.client.read_holding_registers(1001)
        bits = self._to_bits(result.registers[0])
        
        status = utils.STATUS_WORD._make(bits)
       
        return result.registers[0], status
    
    async def get_mode_of_operation(self) -> str:
        """Get the current mode of operation."""
        result = await self.client.read_holding_registers(1002) # I16
        # Read the register as a signed 16 bit integer
        mode = result.registers[0]
        
        return mode
    
    async def get_actual_position(self) -> int:
        """Get the current position of the drive."""
        result = await self.client.read_holding_registers(1004, 2)
        position = self._merge_registers(result.registers)
        return position
    
    async def get_actual_velocity(self) -> int:
        """Get the current velocity of the drive."""
        result = await self.client.read_holding_registers(1020, 2)
        velocity = self._merge_registers(result.registers)
        return velocity
    
    async def get_target_position(self) -> int:
        """Get the target position of the drive."""
        result = await self.client.read_holding_registers(1042, 2)
        position = self._merge_registers(result.registers)
        return position
    
    async def get_target_velocity(self) -> int:
        """Get the target velocity in [Hz]."""
        result = await self.client.read_holding_registers(1048, 2)
        target_velocity = self._merge_registers(result.registers)
        return target_velocity
    
    async def get_profile_velocity(self) -> int:
        """Get the profile velocity in [Hz]."""
        result = await self.client.read_holding_registers(1044, 2)
        profile_velocity = self._merge_registers(result.registers)
        return profile_velocity
    
    async def get_profile_acceleration(self) -> int:
        """Get the profile acceleration in [Hz/s]."""
        result = await self.client.read_holding_registers(1046, 2)
        profile_acceleration = self._merge_registers(result.registers)
        return profile_acceleration
    
    async def get_profile_deceleration(self) -> int:
        """Get the profile deceleration in [Hz/s]."""
        result = await self.client.read_holding_registers(1072, 2)
        profile_deceleration = self._merge_registers(result.registers)
        return profile_deceleration
    
    ### Setters ###
    async def set_mode_of_operation(self, mode: utils.MODE_OF_OPERATION):
        """Set the mode of operation."""
        if mode not in [1, 3, 6]:
            raise ValueError("Invalid mode of operation.")
        
        try:
            await self.client.write_register(1041, mode)
        except ModbusException as e:
            logger.error(f"Error setting mode of operation: {e}")
            
    async def set_target_position(self, position: int):
        """Set the target position of the drive."""
        # Convert to two 16 bit numbers. They should represent an Signed 32 bit integer
        position = position & 0xFFFFFFFF
        lsb = position & 0xFFFF  # 0xFFFF is the hexadecimal representation for 16 bits of 1s.
        msb = (position >> 16) & 0xFFFF
        
        try:
            await self.client.write_registers(1042, [lsb, msb])
        except ModbusException as e:
            logger.error(f"Error setting target position: {e}")
            
    async def set_target_velocity(self, velocity: int):
        """Set the target velocity of the drive."""
        try:
            await self.client.write_registers(1048, [velocity & 0xFFFF, velocity >> 16])
        except ModbusException as e:
            logger.error(f"Error setting target velocity: {e}")
            
    async def set_profile_velocity(self, velocity: int):
        """Set the profile velocity of the drive [0-800000]"""
        if velocity < 0 or velocity > 800000:
            raise ValueError("Invalid profile velocity.")
        
        try:
            await self.client.write_registers(1044, [velocity & 0xFFFF, velocity >> 16])
        except ModbusException as e:
            logger.error(f"Error setting profile velocity: {e}")
           
    ### Control Word ###
    async def get_control_word(self) -> Tuple[int, utils.CONTROL_WORD]:
        """Get the control word."""
        result = await self.client.read_holding_registers(1040)
        bits = self._to_bits(result.registers[0])
        
        control = utils.CONTROL_WORD(*bits)
        
        return result.registers[0], control
    
    async def set_control_word(self, control: utils.CONTROL_WORD | int):
        """Set the control word."""
        try:
            if isinstance(control, int):
                await self.client.write_register(1040, control)
            else:
                bits = control.to_bits()
                value = int(''.join([str(int(i)) for i in bits]), 2)
                print(bits)
                await self.client.write_register(1040, value)
                
        except ModbusException as e:
            logger.error(f"Error setting control word: {e}")
            
    async def set_control_word_bit(self, bit: int, value: bool):
        """Set a specific bit in the control word."""
        try:
            control_word = await self.get_control_word()
            control_word = control_word[0]
            # XOR the bit with the control word
            control_word ^= (-value ^ control_word) & (1 << bit)
            await self.set_control_word(control_word)
        except ModbusException as e:
            logger.error(f"Error setting control word bit: {e}")

         
    ### Drive Settings / Parameters ###   
    async def get_current_ratio(self) -> int:
        """Get the current ratio in [0 - 120 %]."""
        result = await self.client.read_holding_registers(1080)
        return result.registers[0]
    async def set_current_ratio(self, ratio: int):
        """ Set the current ratio in [0 - 120 %].
        Allow to set the desired drive current (peak value supplied to the motor) related to the nominal
        full scale drive curren"""
        if ratio < 0 or ratio > 120:
            raise ValueError("Invalid current ratio.")
        
        try:
            await self.client.write_register(1080, ratio)
        except ModbusException as e:
            logger.error(f"Error setting current ratio: {e}")    
    
    async def get_step_revolution(self) -> int:
        """Get the steps per revolution in [12800 - 12800]."""
        result = await self.client.read_holding_registers(1081)
        return result.registers[0]    
     
    async def get_current_reduction(self) -> int:
        """Get the current reduction in [1]."""
        result = await self.client.read_holding_registers(1083)
        return result.registers[0]
    
    
    async def get_encoder_window(self) -> int:
        """Get the encoder window in 
        { 0: 0.9, 1: 1.8, 2: 3.6, 3: 5.4, 4: 7.2, 5: 9}
        """
        result = await self.client.read_holding_registers(1084)
        return result.registers[0]
    async def set_encoder_window(self, window: int):
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
        
    async def get_following_error_reaction_code(self) -> int:
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
    async def set_following_error_reaction_code(self, code: int):
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
            
    async def position_error_reset(self):
        """Reset the position error."""
        try:
            await self.client.write_register(1086, 1)
        except ModbusException as e:
            logger.error(f"Error resetting position error: {e}")
            
    async def set_output(self, code: int):
        """Set the output."""
        if code not in range(0, 32):
            raise ValueError("Invalid output code.")
        
        try:
            await self.client.write_register(1087, code)
        except ModbusException as e:
            logger.error(f"Error setting output: {e}")
        
    async def get_motor_code(self) -> int:
        """Get the motor code."""
        result = await self.client.read_holding_registers(1090, 2)
        motor_code = self._merge_registers(result.registers)
        return motor_code
    
    async def set_motor_code(self, code: int):
        """Set the motor code."""
        try:
            await self.client.write_registers(1090, [code & 0xFFFF, code >> 16])
        except ModbusException as e:
            logger.error(f"Error setting motor code: {e}")
            
    async def get_revolution_direction(self) -> str:
        """Get the revolution direction."""
        result = await self.client.read_holding_registers(1092)
        return result.registers[0]
    
    async def set_revolution_direction(self, direction: int):
        """Set the revolution direction."""
        if direction not in [0, 1]:
            raise ValueError("Invalid revolution direction.")
        
        try:
            await self.client.write_register(1092, direction)
        except ModbusException as e:
            logger.error(f"Error setting revolution direction: {e}")
            
    async def get_current_reduction_ratio(self) -> int:
        """Get the current reduction ratio in [1 - 100 %]."""
        result = await self.client.read_holding_registers(1112)
        return result.registers[0]
    async def set_current_reduction_ratio(self, ratio: int):
        """Set the current reduction ratio in [1 - 100 %]."""
        if ratio < 1 or ratio > 100:
            raise ValueError("Invalid current reduction ratio.")
        
        try:
            await self.client.write_register(1112, ratio)
        except ModbusException as e:
            logger.error(f"Error setting current reduction ratio: {e}")
    
    async def get_motor_current_limit(self) -> int:
        """Get the motor current limit in [1 - 4 A]."""
        result = await self.client.read_holding_registers(1117)
        return result.registers[0]
    
    async def get_motor_proportional_gain(self) -> int:
        """Get the motor proportional gain [100 - 400 %]."""
        result = await self.client.read_holding_registers(1118)
        return result.registers[0]
    
    async def get_motor_dynamic_balancing(self) -> int:
        """Get the motor dynamic balancing [0 - 500 %]."""
        result = await self.client.read_holding_registers(1119)
        return result.registers[0]
    
    async def get_motor_curent_recycling_enable(self) -> bool:
        """Get the motor current recycling enable."""
        result = await self.client.read_holding_registers(1120)
        return bool(result.registers[0])
    
    async def get_encoder_count_per_revolution(self) -> int:
        """Get the encoder count per revolution. [400-4000]"""
        result = await self.client.read_holding_registers(1121)
        return result.registers[0]
    
    async def set_encoder_count_per_revolution(self, count: int):
        """Set the encoder count per revolution."""
        if count < 400 or count > 4000:
            raise ValueError("Invalid encoder count per revolution.")
        
        try:
            await self.client.write_register(1121, count)
        except ModbusException as e:
            logger.error(f"Error setting encoder count per revolution: {e}")