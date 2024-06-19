from typing import Tuple

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