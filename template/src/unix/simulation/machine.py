"""
`machine` stand-in for running the application on the unix port.

Re-exports mock_machine, which models Pin, I2C, SPI, UART, ADC, PWM, Timer,
WDT and RTC. Anything needing real peripheral behaviour belongs in an on-target
test.
"""

from mock_machine import *
