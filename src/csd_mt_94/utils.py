
from typing import Tuple, Union, Dict, Literal
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder

def merge_registers(registers):
    return (registers[1] << 16) + registers[0]

def to_bits_list(value,
                n_bits=16) -> list:

    return [bool(int(i)) for i in f"{value:0{n_bits}b}"]

def int32_to_uint16(value) -> Tuple[int, int]:
    # Convert to two 16 bit numbers. They should represent an Signed 32 bit integer
    value = value & 0xFFFFFFFF
    lsb = value & 0xFFFF  # 0xFFFF is the hexadecimal representation for 16 bits of 1s.
    msb = (value >> 16) & 0xFFFF
    
    return lsb, msb

def decode_payload_to_bits(payload: BinaryPayloadDecoder,
                           type: Literal["uint16", "int16", "uint32", "int32"]
                           ) -> dict:
    
    # Decode the first (and in this case, only) register.
    if type == "uint16":
        register_value = payload.decode_16bit_uint()
        length = 16
    elif type == "int16":
        register_value = payload.decode_16bit_int()
        length = 16
    elif type == "uint32":
        register_value = payload.decode_32bit_uint()
        length = 32
    elif type == "int32":
        register_value = payload.decode_32bit_int()
        length = 32
    else:
        raise ValueError("Invalid type. It should be either 'uint16', 'int16', 'uint32' or 'int32'")

    # Now, extract each bit from this register value.
    bits = {bit: (register_value >> bit) & 1 for bit in range(length)}

    return bits

def encode_bits_to_payload(
    bits: Dict[int, bool],
    type: Literal["uint16", "int16", "uint32", "int32"],
    byteorder: Endian = Endian.LITTLE,
    wordorder: Endian = Endian.LITTLE
) -> BinaryPayloadBuilder:
    
    builder = BinaryPayloadBuilder(byteorder=byteorder, wordorder=wordorder)
    
    # Convert the bits to a single integer
    if type in ["uint16", "int16"]:
        value = sum([int(bits[i]) << i for i in range(16)])
    elif type in ["uint32", "int32"]:
        value = sum([int(bits[i]) << i for i in range(32)])
    else:
        raise ValueError("Invalid type. Must be 'uint16', 'int16', 'uint32', or 'int32'.")
    
    # Add the value to the builder based on the specified type
    if type == "uint16":
        builder.add_16bit_uint(value)
    elif type == "int16":
        builder.add_16bit_int(value)
    elif type == "uint32":
        builder.add_32bit_uint(value)
    elif type == "int32":
        builder.add_32bit_int(value)
    
    return builder