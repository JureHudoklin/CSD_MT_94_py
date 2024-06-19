# CSD_MT_94 Python Library

This Python library enables simple communication with the RTA CSD-MT-94 stepper motor controller. For more information please refer to official RTA manual.

## Installation

To install the library cd into the root directory of the repository and run the following command:

```sh
pip install -e .
```

## Usage

Here is an example of how to use the library:

```python
    from csd_mt_94 import CSD_MT_94
    import asyncio

    async def main():
        csd_mt_94 = CSD_MT_94(host='192.168.1.10', port=502)
        await csd_mt_94.start_connection()

        await csd_mt_94.set_motor_code(0x15B1)
        await csd_mt_94.set_mode_of_operation(1)
        await csd_mt_94.set_profile_velocity(3000)

        # Turn on the drive
        await csd_mt_94.quick_stop()
        await csd_mt_94.enable_voltage()
        await csd_mt_94.switch_on()
        await csd_mt_94.enable_operation()

        # Move the motor
        await csd_mt_94.move(25600, cs="relative") # Move by 25600 steps
        await csd_mt_94.rotate(0, cs="absolute", units="deg") # Rotate to 0 degrees

    if __name__ == '__main__':
        asyncio.run(main())
```

This will connect to the motor controller at the specified IP address and port, set the motor code and mode of operation, set the profile velocity, and move the motor to a specified position. Additional examples can be found in the examples directory.

## API Reference
For detailed information about the API, please refer to the source code in the src/csd_mt_94 directory.

## Contributing
Contributions are welcome! Please feel free to submit a pull request.

## License
This project is licensed under the MIT License.