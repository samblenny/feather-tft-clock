# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
from displayio import Bitmap, Group, Palette, TileGrid
import gc
from micropython import const

import adafruit_imageload


class SevenSeg:
    # Simulate a 7-segment LED clock display using sprites

    def __init__(self, x=0, y=0, cols=8):
        # Args:
        # - x: x coordinate of first digit's top-left corner
        # - y: y coordinate of top line's top-left corner
        # Load font spritesheet into Bitmap and Palette objects
        #
        # CAUTION 1: This uses adafruit_imageload.load() with a PNG file, and
        # the PNG loader currently has a bug where sprites are misaligned by
        # one pixel. (https://github.com/adafruit/circuitpython/issues/9587 )
        # To work around the bug, I made the spritesheet with 1 pixel of
        # vertical padding above and below the important area of each digit.
        #
        # CAUTION 2: When I tried this spritesheet with a BMP file, the image
        # loaded without any exceptions, but the resulting bitmap was badly
        # glitched (rows were skewed, colors were wrong, etc). The BMP file was
        # about 14KB, so maybe it overflowed a buffer or something? Not sure.
        #
        gc.collect()
        (bmp, pal) = adafruit_imageload.load(
            "digit-sprites.png", bitmap=Bitmap, palette=Palette)
        gc.collect()
        # Make a Group with TileGrids with top left corner at (x, y)
        tg = TileGrid(
            bmp, pixel_shader=pal, width=cols, height=1,
            tile_width=30, tile_height=50, x=x, y=y, default_tile=12)
        gc.collect()
        self.tg = tg
        self.cols = cols
        g = Group(scale=1)
        g.append(tg)
        self.grp = g

    def group(self):
        return self.grp

    def setDigits(self, digits):
        # Show message left-aligned on the top or bottom character LCD.
        # - digits: string or bytes in the set: "0123456789: "
        #
        ASCII_SPACE = const(32)
        ASCII_DASH  = const(45)
        ASCII_ZERO  = const(48)
        ASCII_COLON = const(58)  # conveniently, ASCII ":" is right after "9"!
        _DASH_SPRITE  = const(11)
        _SPACE_SPRITE = const(12)
        _tg = self.tg
        _cols = self.cols

        # Set sprites for characters of the message (max length = self.cols)
        for (i, char) in zip(range(_cols), digits):
            # Convert the character to a sprite number and update the TileGrid
            n = char if (type(char) == int) else ord(char)
            sprite = _SPACE_SPRITE                        # default: ' '
            if (ASCII_ZERO <= n) and (n <= ASCII_COLON):  # '0'..'9' and ':'
                sprite = n - ASCII_ZERO
            elif n == ASCII_DASH:                         # '-'
                sprite = _DASH_SPRITE
            if _tg[i] != sprite:         # Avoid triggering redundant repaints
                _tg[i] = sprite

        # Clear right padding area with space characters
        for i in range(len(digits), _cols):
            if _tg[i] != _SPACE_SPRITE:
                _tg[i] = _SPACE_SPRITE

