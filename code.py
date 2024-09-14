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


def handle_input(machine, prev, buttons):
    # Respond to gamepad button state change events
    diff = prev ^  buttons
    mh = machine.handleGamepad
    if (diff & A) and (buttons == A):  # A pressed
        mh(machine.A)
    elif (diff & B) and (buttons == B):  # B pressed
        mh(machine.B)
    elif (diff & UP) and (buttons == UP):  # UP pressed
        mh(machine.UP)
    elif (diff & DOWN) and (buttons == DOWN):  # DOWN pressed
        mh(machine.DOWN)
    elif (diff & LEFT) and (buttons == LEFT):  # LEFT pressed
        mh(machine.LEFT)
    elif (diff & RIGHT) and (buttons == RIGHT):  # RIGHT pressed
        mh(machine.RIGHT)
    elif (diff & START) and (buttons == START):  # START pressed
        mh(machine.START)
    #print(f"{buttons:016b}")


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
    gc.collect()
    # to set time:
    # rtc.datetime = struct_time((year, mon, day, hour, min, sec, 0, -1, -1))

    # Initialize State Machine
    machine = StateMachine(digits, charLCD, rtc)

    # Caching frequently used objects saves time on dictionary name lookups
    _collect = gc.collect
    _elapsed = elapsed_ms
    _ms = ticks_ms
    _refresh = display.refresh
    _setMsg = charLCD.setMsg
    _updateDigits = machine.updateDigits

    # Start watching VM millisecond ticks. The point of this is that it should
    # take fewer clock cycles to check the supervisor ticks than to poll the
    # RTC over I2C. I2C IO is slow, and constantly banging on the I2C bus might
    # cause problems. So, use the ticks timer to avoid doing that.
    prev_ms = _ms()

    # Read RTC time and update display digits
    RTC_POLL_MS = const(100)
    prevST = rtc.datetime
    _updateDigits(prevST)

    # MAIN EVENT LOOP
    # Establish and maintain a gamepad connection
    gp = XInputGamepad()
    FINDING = b'Finding USB gamepad'
    print("Looking for USB gamepad...")
    _setMsg(FINDING, top=False)
    _refresh()
    dirty = False
    # Outer Loop: Update clock and try to connect to a USB gamepad.
    # The tick timer checks with ms() help keep the system responsive by rate
    # limiting I2C and SPI bus activity for polling the RTC, polling the
    # gamepad, and updating the display.
    while True:
        _collect()
        now_ms = _ms()
        if dirty or (_elapsed(prev_ms, now_ms) >= RTC_POLL_MS):
            # Check clock (RTC) and update time display if needed
            prev_ms = now_ms
            nowST = rtc.datetime
            if dirty or (nowST != prevST):
                prevST = nowST
                _updateDigits(prevST)
                _refresh()
                dirty = False
        try:
            # Attempt to connect to USB gamepad
            if gp.find_and_configure():
                print(gp.device_info_str())
                connected = True
                _setMsg(b'gamepad ready', top=False)
                _refresh()
                # Inner Loop: Update clock and poll gamepad for button events
                prev_btn = 0
                for buttons in gp.poll():
                    now_ms = _ms()
                    # Check RTC and update clock digits if needed
                    if dirty or ( _elapsed(prev_ms, now_ms) >= RTC_POLL_MS):
                        prev_ms = now_ms
                        nowST = rtc.datetime
                        if dirty or (nowST != prevST):
                            prevST = nowST
                            _updateDigits(prevST)
                            _refresh()
                            dirty = False
                    _collect()
                    # Handle gamepad input events
                    if prev_btn != buttons:
                        handle_input(machine, prev_btn, buttons)
                        _refresh()
                        prev_btn = buttons
                        dirty = True
                    sleep(0.002)
                # If loop stopped, gamepad connection was lost
                print("Gamepad disconnected")
                print("Looking for USB gamepad...")
                _setMsg(FINDING, top=False)
                _refresh()
            else:
                # No connection yet, so sleep briefly then try again
                sleep(0.1)
        except USBError as e:
            # This might mean gamepad was unplugged, or maybe some other
            # low-level USB thing happened which this driver does not yet
            # know how to deal with. So, log the error and keep going
            print(e)
            print("Gamepad connection error")
            print("Looking for USB gamepad...")
            _setMsg(FINDING, top=False)
            _refresh()


main()
