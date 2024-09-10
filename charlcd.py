# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
from displayio import Bitmap, Group, Palette, TileGrid
from micropython import const
import adafruit_imageload


class CharLCD:
    # Simulate a dot matrix character LCD using sprites

    def __init__(self, cols=8, x=0, y0=0, y1=32, scale=2):
        # Args:
        # -  cols: number of columns (monospace characters) in the display
        # -     x: x coordinate of both lines' top-left corners
        # -    y0: y coordinate of top line's top-left corner
        # -    y1: y coordinate of bottom lines's top-left corner
        # - scale: scaling factor for the font (scale=2 means 2x zoom)
        self.cols = cols
        # Load font spritesheet into Bitmap and Palette objects
        (bmp, pal) = adafruit_imageload.load(
            "ASCII-font.bmp", bitmap=Bitmap, palette=Palette)
        # Make a Group with TileGrids for the top line, with top left corner at
        # (x0, y0), and the bottom line, with top left corner at (x1, y1)
        tg0 = TileGrid(
            bmp, pixel_shader=pal, width=cols, height=1,
            tile_width=6, tile_height=8, x=x, y=y0, default_tile=0)
        tg1 = TileGrid(
            bmp, pixel_shader=pal, width=cols, height=1,
            tile_width=6, tile_height=8, x=x, y=y1, default_tile=0)
        self.tg0 = tg0
        self.tg1 = tg1
        g = Group(scale=scale)
        g.append(tg0)
        g.append(tg1)
        self.grp = g

    def group(self):
        return self.grp

    def setMsg(self, msg, top=True):
        # Show message left-aligned on the top or bottom character LCD.
        # - msg: string or bytes (should have ASCII chars in range 32..127)
        # - top: True: show msg on top line; False: show msg on bottom line
        #
        ASCII_SPACE = const(32)  # first sprite: space (blank rectangle)
        ASCII_DEL = const(127)   # last sprite: DEL (using this for down arrow)
        _tg = self.tg0 if top else self.tg1
        _cols = self.cols

        # Set sprites for characters of the message (max length = self.cols)
        for (i, char) in zip(range(_cols), msg):
            # Convert the character to a sprite number and update the TileGrid
            n = char if (type(char) == int) else ord(char)
            if (n < ASCII_SPACE) or (ASCII_DEL < n):
                n = ord('?')  # Replace out of range chars with '?'
            _tg[i] = n - 32   # subtract 32 because sprite sheet starts at ' '

        # Clear right padding area with space characters
        for i in range(len(msg), _cols):
            _tg[i] = 0   # sprite sheet starts on ' ', so use 0 instead of 32

