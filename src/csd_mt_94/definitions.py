from collections import namedtuple
from dataclasses import dataclass
from typing import Union, Literal, TypeAlias

# 0x8611: “Motor following error”
# 0x8400: “Axis speed too high”
# 0x5100: “Error power supply out of range”
# 0x4310: “Error drive excessive temperature”
# 0x2130: “Error short circuit” (or overcurrent on motor phase)
# 0x0000: “Emergency end"
ERROR_CODES = {
    0x8611: "Motor following error",
    0x8400: "Axis speed too high",
    0x5100: "Error power supply out of range",
    0x4310: "Error drive excessive temperature",
    0x2130: "Error short circuit",
    0x0000: "Emergency end",
}

MODE_OF_OPERATION: TypeAlias = Union[Literal[1], Literal[3], Literal[6]]
MODES_OF_OPERATION = {
    1: "Profile position mode",
    3: "Profile velocity mode",
    6: "Homing mode",
}

STATUS_WORD = namedtuple(
    "StatusWord",
    [
        "profile_ramp",
        "closed_loop_active",
        "following_error",
        "set_point_acknowledged",
        "int_limit_active",
        "target_reached",
        "remote",
        "manufact_spec",
        "warning",
        "switch_on_disabled",
        "quick_stop",
        "voltage_enabled",
        "fault",
        "operation_enabled",
        "switched_on",
        "ready_to_switch_on",
    ],
)

@dataclass
class CONTROL_WORD:
    user_specific_15: bool
    user_specific_14: bool
    user_specific_13: bool
    user_specific_12: bool
    user_specific_11: bool
    reserved_10: bool
    reserved_9: bool
    halt: bool
    fault_reset: bool
    relative_cs: bool
    change_set_immediately: bool
    new_set_point: bool
    enable_op: bool
    quick_stop: bool
    enable_voltage: bool
    switch_on: bool

    def to_bits(self):
        return {
            0: self.switch_on,
            1: self.enable_voltage,
            2: self.quick_stop,
            3: self.enable_op,
            4: self.new_set_point,
            5: self.change_set_immediately,
            6: self.relative_cs,
            7: self.fault_reset,
            8: self.halt,
            9: self.reserved_9,
            10: self.reserved_10,
            11: self.user_specific_11,
            12: self.user_specific_12,
            13: self.user_specific_13,
            14: self.user_specific_14,
            15: self.user_specific_15,
        }