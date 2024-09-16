# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Hardware:
# - Adafruit ESP32-S3 TFT Feather - 4MB Flash, 2MB PSRAM (#5483)
# - Adafruit USB Host FeatherWing with MAX3421E (#5858)
# - 8BitDo SN30 Pro USB gamepad
#
# Pinouts:
# | TFT feather | USB Host | ST7789 TFT | Adalogger          |
# | ----------- | -------- | ---------- | ------------------ |
# |  SCK        |  SCK     |            | SCK (SD)           |
# |  MOSI       |  MOSI    |            | MOSI (SD)          |
# |  MISO       |  MISO    |            | MISO (SD)          |
# |  SDA        |          |            | SDA (RTC)          |
# |  SCL        |          |            | SCL (RTC)          |
# |  D9         |  IRQ     |            |                    |
# |  D10        |  CS      |            | (Not SDCS!)        |
# |  D11        |          |            | SDCS (wire jumper) |
# |  TFT_CS     |          |  CS        |                    |
# |  TFT_DC     |          |  DC        |                    |
#
# Related Documentation:
# - https://learn.adafruit.com/adafruit-esp32-s3-tft-feather
# - https://learn.adafruit.com/adafruit-1-14-240x135-color-tft-breakout
# - https://learn.adafruit.com/adafruit-usb-host-featherwing-with-max3421e
# - https://learn.adafruit.com/adafruit-adalogger-featherwing/rtc-with-circuitpython
# - https://docs.circuitpython.org/en/latest/shared-bindings/time/index.html
#
from board import D9, D10, D11, I2C, SPI, TFT_CS, TFT_DC
from digitalio import DigitalInOut, Direction
from displayio import Bitmap, Group, Palette, TileGrid, release_displays
from fourwire import FourWire
import gc
from max3421e import Max3421E
from micropython import const
from supervisor import ticks_ms
from time import sleep, struct_time
from usb.core import USBError

from adafruit_pcf8523 import PCF8523
from adafruit_st7789 import ST7789
from charlcd import CharLCD
from gamepad import (
    XInputGamepad, UP, DOWN, LEFT, RIGHT, START, SELECT, A, B, X, Y)
from sevenseg import SevenSeg
from statemachine import StateMachine


def handle_input(machine, prev, buttons, repeat):
    # Respond to gamepad button state change events
    diff = prev ^  buttons
    mh = machine.handleGamepad
    #print(f"{buttons:016b}")

    if repeat:
        # Check for hold-time triggered repeating events
        if (buttons == UP):        # UP held
            mh(machine.UP, True)
        elif (buttons == DOWN):    # DOWN held
            mh(machine.DOWN, True)
    else:
        # Check for edge-triggered events
        if (diff & A) and (buttons == A):  # A pressed
            mh(machine.A, False)
        elif (diff & B) and (buttons == B):  # B pressed
            mh(machine.B, False)
        elif (diff & UP) and (buttons == UP):  # UP pressed
            mh(machine.UP, False)
        elif (diff & DOWN) and (buttons == DOWN):  # DOWN pressed
            mh(machine.DOWN, repeat)
        elif (diff & LEFT) and (buttons == LEFT):  # LEFT pressed
            mh(machine.LEFT, False)
        elif (diff & RIGHT) and (buttons == RIGHT):  # RIGHT pressed
            mh(machine.RIGHT, False)
        elif (diff & START) and (buttons == START):  # START pressed
            mh(machine.START, False)


def elapsed_ms(prev, now):
    # Calculate elapsed ms between two timestamps from supervisor.ticks_ms().
    # The ticks counter rolls over at 2**29, and (2**29)-1 = 0x3fffffff
    MASK = const(0x3fffffff)
    return (now - prev) & MASK


def main():
    release_displays()
    gc.collect()
    spi = SPI()

    # Initialize ST7789 display with native display size of 240x135px.
    TFT_W = const(240)
    TFT_H = const(135)
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=TFT_W, height=TFT_H, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()
    # Set up the 5 digit/dots sprites to build a 7-segment time display
    # Each sprite is 5*8px wide by 6*8 px high (= 40x48px).

    # Configure the character display areas at top and bottom of screen.
    # This uses a 6x8 px spritesheet font for ASCII characters (32..127).
    SCALE = 2
    PAD = 2
    COLS = 20
    Y1 = (TFT_H // SCALE) - 8 - PAD
    charLCD = CharLCD(cols=COLS, x=0, y0=PAD, y1=Y1, scale=SCALE)
    gc.collect()

    # Configure the 7-segment clock digits display area in the center of the
    # screen. There are eight 7-segment sprites, and each sprite is 30px wide by
    # 50px high.
    X = (TFT_W - (8 * 30)) // 2
    Y = (TFT_H - 50) // 2
    digits = SevenSeg(x=X, y=Y)
    gc.collect()

    # Add the TileGrids to the display's root group
    gc.collect()
    grp = Group(scale=1)
    grp.append(charLCD.group())
    grp.append(digits.group())
    display.root_group = grp
    display.refresh()

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    # The link between usb.core and Max3421E happens by way of invisible
    # magic in the CircuitPython core, kinda like with displayio displays.
    print("Initializing USB host port...")
    gc.collect()
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    gc.collect()
    sleep(0.1)

    # Initialize RTC
    rtc = PCF8523.PCF8523(I2C())
    print("RTC calibration:", rtc.calibration)
    gc.collect()
    # Example, reset time to 2024-09-14 01:23:45:
    # rtc.datetime = struct_time((2024, 9, 14, 1, 23, 45, 0, -1, -1))

    # Initialize State Machine
    machine = StateMachine(digits, charLCD, rtc)

    # Gamepad status update strings
    GP_FIND   = 'Finding USB gamepad'
    GP_READY  = 'gamepad ready'
    GP_DISCON = 'gamepad disconnected'
    GP_ERR    = 'gamepad connection error'

    # Cache frequently used callables to save time on dictionary name lookups
    # NOTE: rtc.datetime is a property, so we can't cache it here!
    _collect = gc.collect
    _elapsed = elapsed_ms
    _ms = ticks_ms
    _refresh = display.refresh
    _setMsg = charLCD.setMsg
    _updateDigits = machine.updateDigits

    # Read RTC time and update display digits
    prevST = rtc.datetime
    _updateDigits(prevST)

    # MAIN EVENT LOOP
    # Establish and maintain a gamepad connection
    gp = XInputGamepad()
    print(GP_FIND)
    _setMsg(GP_FIND, top=False)
    _refresh()
    need_refresh = False
    # OUTER LOOP: Update clock and try to connect to a USB gamepad.
    # Start timers for RTC polling and gamepad button hold detection. The point
    # the RTC timer is to avoid burning unecessary clock cycles waiting for the
    # I2C bus, which is slow.
    RTC_MS    = const(100)  # RTC poll interval (ms)
    DELAY_MS  = const(900)  # Gamepad button hold delay before repeat (ms)
    REPEAT_MS = const(300)  # Gamepad button interval between repeats (ms)
    prev_ms = _ms()
    rtc_ms = 0
    hold_tmr = 0
    repeat_tmr = 0
    while True:
        _collect()
        now_ms = _ms()
        if need_refresh or (_elapsed(rtc_ms, now_ms) >= RTC_MS):
            # Check clock (RTC) and update time display if needed
            rtc_ms = now_ms
            nowST = rtc.datetime
            if need_refresh or (nowST != prevST):
                prevST = nowST
                _updateDigits(prevST)
                _refresh()
                need_refresh = False
        try:
            # Attempt to connect to USB gamepad
            if gp.find_and_configure():
                print(gp.device_info_str())
                connected = True
                _setMsg(GP_READY, top=False)
                _refresh()
                # INNER LOOP: Update clock and poll gamepad for button events
                prev_btn = 0
                hold_tmr = 0
                repeat_tmr = 0
                for buttons in gp.poll():
                    # Update timers
                    now_ms = _ms()
                    interval = _elapsed(prev_ms, now_ms)
                    prev_ms = now_ms
                    if buttons == 0:
                        hold_tmr = 0
                        repeat_tmr = 0
                    elif prev_btn != buttons:
                        hold_tmr = 0
                        repeat_tmr = 0
                    else:
                        hold_tmr += interval
                        repeat_tmr += interval
                    # Check RTC and update display if needed
                    if need_refresh or (_elapsed(rtc_ms, now_ms) >= RTC_MS):
                        rtc_ms = now_ms
                        nowST = rtc.datetime
                        if need_refresh or (nowST != prevST):
                            prevST = nowST
                            _updateDigits(prevST)
                            _refresh()
                            _collect()
                            need_refresh = False
                    # Handle hold-time triggered gamepad input events
                    if hold_tmr >= DELAY_MS:
                        if hold_tmr == repeat_tmr:
                            # First re-trigger event after initial delay
                            repeat_tmr -= DELAY_MS
                            handle_input(machine, prev_btn, buttons, True)
                            need_refresh = True
                        elif repeat_tmr >= REPEAT_MS:
                            # Another re-trigger event after repeat interval
                            repeat_tmr -= REPEAT_MS
                            handle_input(machine, prev_btn, buttons, True)
                            need_refresh = True
                    # Handle edge-triggered gamepad input events
                    if prev_btn != buttons:
                        handle_input(machine, prev_btn, buttons, False)
                        need_refresh = True
                    # Save button values
                    prev_btn = buttons
                # If loop stopped, gamepad connection was lost
                print(GP_DISCON)
                print(GP_FIND)
                _setMsg(GP_FIND, top=False)
                _refresh()
            else:
                # No connection yet, so sleep briefly then try again
                sleep(0.1)
        except USBError as e:
            # This might mean gamepad was unplugged, or maybe some other
            # low-level USB thing happened which this driver does not yet
            # know how to deal with. So, log the error and keep going
            print(e)
            print(GP_ERR)
            print(GP_FIND)
            _setMsg(GP_FIND, top=False)
            _refresh()


main()
