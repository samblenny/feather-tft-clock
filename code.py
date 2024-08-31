# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# feather-tft-gamepad
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


def handle_input(world, prev, buttons):
    # Respond to gamepad button state change events
    diff = prev ^  buttons
    if diff & buttons & A:  # A pressed
        pass
    if diff & buttons & B:  # B pressed
        pass
    if diff & buttons & X:  # X pressed
        pass
    if diff & buttons & Y:  # Y pressed
        pass
    if diff & buttons & UP:  # UP pressed
        pass
    if diff & buttons & DOWN:  # DOWN pressed
        pass
    if diff & buttons & LEFT:  # LEFT pressed
        pass
    if diff & buttons & RIGHT:  # RIGHT pressed
        pass
    if diff & buttons & SELECT:  # SELECT pressed
        pass
    if diff & buttons & START:  # START pressed
        pass
    print(f"{buttons:016b}")


def main():
    release_displays()
    gc.collect()
    spi = SPI()

    # Initialize ST7789 display with native display size of 240x135px.
    #
    # This uses 2x scaling and crops to an active of 240 px (15*16px) wide by
    # 128 px (8*16px) tall. The result is that I can treat the display as a
    # scene of 15 sprites wide by 8 sprites tall, using 8x8 px sprite tiles.
    #
    bus = FourWire(spi, command=TFT_DC, chip_select=TFT_CS)
    display = ST7789(bus, rotation=270, width=240, height=135, rowstart=40,
        colstart=53, auto_refresh=False)
    gc.collect()
    # load spritesheet and palette
    (bitmap, palette) = adafruit_imageload.load("clock.png", bitmap=Bitmap,
        palette=Palette)
    scene = TileGrid(bitmap, pixel_shader=palette, width=1, height=1,
        tile_width=168, tile_height=48, x=36, y=40)  # (240-168)/2=36, (128-48)/2=40
    grp = Group(scale=1)
    grp.append(scene)
    display.root_group = grp
    display.refresh()

    # Initialize MAX3421E USB host chip which is needed by usb.core.
    # The link between usb.core and Max3421E happens by way of invisible
    # magic in the CircuitPython core, kinda like with displayio displays.
    print("Initializing USB host port...")
    usbHost = Max3421E(spi, chip_select=D10, irq=D9)
    sleep(0.1)

    # TODO: Initialize RTC

    # Initialize global state
    world = {"scene": scene, "clock": None}

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
                        handle_input(world, prev, buttons)
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
