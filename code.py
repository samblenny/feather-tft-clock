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
# - https://learn.adafruit.com/adafruit-adalogger-featherwing
#
from board import D9, D10, D11, I2C, SPI, TFT_CS, TFT_DC
from digitalio import DigitalInOut, Direction
from displayio import (Bitmap, Group, Palette, TileGrid, release_displays)
from fourwire import FourWire
import gc
from max3421e import Max3421E
from time import sleep
from usb.core import USBError

import adafruit_imageload
from adafruit_st7789 import ST7789
from gamepad import (
    XInputGamepad, UP, DOWN, LEFT, RIGHT, START, SELECT, A, B, X, Y)
from statemachine import StateMachine


def handle_input(machine, prev, buttons):
    # Respond to gamepad button state change events
    diff = prev ^  buttons
    mh = machine.handle
    if (diff & (A | B)) and (buttons == (A | B)):  # A+B pressed
        mh(machine.AB)
    elif (diff & A) and (buttons == A):  # A pressed
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
    elif (diff & SELECT) and (buttons == SELECT):  # SELECT pressed
        mh(machine.SELECT)
    print(f"{buttons:016b}")


def main():
    release_displays()
    gc.collect()
    spi = SPI()

    # Initialize ST7789 display with native display size of 240x135px.
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=240, height=135, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()
    # load spritesheet and palette for digits
    (bitmapD, paletteD) = adafruit_imageload.load("digit-sprites.bmp",
        bitmap=Bitmap, palette=Palette)
    # load spritesheet and palette for badges
    (bitmapB, paletteB) = adafruit_imageload.load("badge-sprites.bmp",
        bitmap=Bitmap, palette=Palette)
    gc.collect()
    # Set up the 5 digit/dots sprites to build a 7-segment time display
    # Each sprite is 3*8px wide by 6*8 px high (= 24x48px). The hour and minute
    # digits have a 16px horizontal gap between them, but the dots sprite only
    # has an 8px gap on each side.
    #
    # The time display is 168x48px and the active screen area is 240x128px. So,
    # to center time in the display, the top left corner coordinates should be:
    #   ((240-168)/2, (128-48)/2) = (36, 40)
    #
    # Table of top-left sprite coordinates for digits:
    #    hour 10's digit: (36       , 40) = ( 36, 40)
    #    hour  1's digit: (36+( 5*8), 40) = ( 76, 40)
    #               dots: (36+( 9*8), 40) = (108, 40)
    #  minute 10's digit: (36+(13*8), 40) = (140, 40)
    #  minute  1's digit: (36+(18*8), 40) = (180, 40)
    #
    digits = (
        # Most significant digit (N....)
        TileGrid(bitmapD, pixel_shader=paletteD, width=1, height=1,
            tile_width=24, tile_height=48, x=36, y=40, default_tile=0),
        # Second digit (.N...)
        TileGrid(bitmapD, pixel_shader=paletteD, width=1, height=1,
            tile_width=24, tile_height=48, x=76, y=40, default_tile=1),
        # Colon (..:..)
        TileGrid(bitmapD, pixel_shader=paletteD, width=1, height=1,
            tile_width=24, tile_height=48, x=108, y=40, default_tile=10),
        # Third digit (...N.)
        TileGrid(bitmapD, pixel_shader=paletteD, width=1, height=1,
            tile_width=24, tile_height=48, x=140, y=40, default_tile=2),
        # Least significant digit (....N)
        TileGrid(bitmapD, pixel_shader=paletteD, width=1, height=1,
            tile_width=24, tile_height=48, x=180, y=40, default_tile=3),
    )
    # Table of top-left sprite coordinates for mode badges
    # | Badge |  X  |  Y  |
    # | ----- | --- | --- |
    # | YEAR  |  10 |   5 |
    # | MON   |  90 |   5 |
    # | DAY   | 160 |   5 |
    # | SET   |  10 | 100 |
    # | HHMM  |  80 | 100 |
    # | MMSS  | 160 | 100 |
    badges = {
        'YEAR': TileGrid(bitmapB, pixel_shader=paletteB, width=1, height=1,
            tile_width=70, tile_height=22, x=10, y=5, default_tile=0),
        'MON': TileGrid(bitmapB, pixel_shader=paletteB, width=1, height=1,
            tile_width=70, tile_height=22, x=90, y=5, default_tile=1),
        'DAY': TileGrid(bitmapB, pixel_shader=paletteB, width=1, height=1,
            tile_width=70, tile_height=22, x=160, y=5, default_tile=2),
        'SET': TileGrid(bitmapB, pixel_shader=paletteB, width=1, height=1,
            tile_width=70, tile_height=22, x=10, y=100, default_tile=3),
        'HHMM': TileGrid(bitmapB, pixel_shader=paletteB, width=1, height=1,
            tile_width=70, tile_height=22, x=80, y=100, default_tile=4),
        'MMSS': TileGrid(bitmapB, pixel_shader=paletteB, width=1, height=1,
            tile_width=70, tile_height=22, x=160, y=100, default_tile=5),
    }
    gc.collect()
    grp = Group(scale=1)
    for tg in digits:
        gc.collect()
        grp.append(tg)
    for (key, val) in badges.items():
        gc.collect()
        grp.append(val)
    display.root_group = grp
    display.refresh()

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    # The link between usb.core and Max3421E happens by way of invisible
    # magic in the CircuitPython core, kinda like with displayio displays.
    print("Initializing USB host port...")
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    sleep(0.1)

    # TODO: Initialize RTC

    # Initialize State Machine in clock mode
    machine = StateMachine(digits, badges)

    # MAIN EVENT LOOP
    # Establish and maintain a gamepad connection
    gp = XInputGamepad()
    print("Looking for USB gamepad...")
    while True:
        gc.collect()
        try:
            if gp.find_and_configure(retries=25):
                # Found a gamepad, so configure it and start polling
                print(gp.device_info_str())
                connected = True
                prev = 0
                while connected:
                    (connected, changed, buttons) = gp.poll()
                    if connected and changed:
                        handle_input(machine, prev, buttons)
                        display.refresh()
                        prev = buttons
                    sleep(0.002)
                    gc.collect()
                # If loop stopped, gamepad connection was lost
                print("Gamepad disconnected")
                print("Looking for USB gamepad...")
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


main()
