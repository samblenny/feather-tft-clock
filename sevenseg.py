# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
from displayio import Bitmap, Group, Palette, TileGrid
from micropython import const
import adafruit_imageload


class SevenSeg:
    # Simulate a 7-segment LED clock display using sprites

    def __init__(self, x=0, y=0, cols=5):
        # Args:
        # - x: x coordinate of first digit's top-left corner
        # - y: y coordinate of top line's top-left corner
        # Load font spritesheet into Bitmap and Palette objects
        (bmp, pal) = adafruit_imageload.load(
            "digit-sprites.bmp", bitmap=Bitmap, palette=Palette)
        # Make a Group with TileGrids with top left corner at (x, y)
        tg = TileGrid(
            bmp, pixel_shader=pal, width=cols, height=1,
            tile_width=32, tile_height=48, x=x, y=y, default_tile=0)
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
        ASCII_ZERO  = const(48)
        ASCII_COLON = const(58)  # conveniently, ASCII ":" is right after "9"!
        _tg = self.tg
        _cols = self.cols

        # Set sprites for characters of the message (max length = self.cols)
        for (i, char) in zip(range(_cols), digits):
            # Convert the character to a sprite number and update the TileGrid
            n = char if (type(char) == int) else ord(char)
            sprite = 11  # default: use space for ' ' or unexpected bytes
            if (ASCII_ZERO <= n) and (n <= ASCII_COLON):
                sprite = n - ASCII_ZERO  # This covers '0'..'9' and ':'
            if _tg[i] != sprite:         # Avoid triggering redundant repaints
                _tg[i] = sprite

        # Clear right padding area with space characters
        for i in range(len(digits), _cols):
            if _tg[i] != 11:
                _tg[i] = 11   # space sprite

