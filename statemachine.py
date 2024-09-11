# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2024 Sam Blenny
#
# Table of states and state transitions:
#
# | State   | UP     | DOWN   | LEFT | RIGHT | A       | B    | A+B  | SELECT  |
# | ------- | ------ | ------ | ---- | ----- | ------- | ---- | ---- | ------- |
# | demo    | hhmm   | hhmm   | hhmm | hhmm  | hhmm    | hhmm | demo | hhmm    |
# | hhmm    | nop    | nop    | day  | mmss  | nop     | hhmm | demo | setMin  |
# | mmss    | nop    | nop    | hhmm | year  | nop     | hhmm | demo | setSec  |
# | year    | nop    | nop    | mmss | mon   | nop     | hhmm | demo | setYear |
# | mon     | nop    | nop    | year | day   | nop     | hhmm | demo | setYear |
# | day     | nop    | nop    | mon  | hhmm  | nop     | hhmm | demo | setYear |
# | setYear | year+1 | year-1 | nop  | nop   | setMon  | hhmm | demo | hhmm    |
# | setMon  | mon+1  | mon-1  | nop  | nop   | setDay  | hhmm | demo | hhmm    |
# | setDay  | day+1  | day-1  | nop  | nop   | setMin  | hhmm | demo | hhmm    |
# | setMin  | min+1  | min-1  | nop  | nop   | setSec  | hhmm | demo | hhmm    |
# | setSec  | sec=0  | sec=0  | nop  | nop   | setYear | hhmm | demo | hhmm    |
#
from micropython import const

# State Transition Constants (private)
# CAUTION: These values must match row indexes of StateMachine.TABLE
_Demo   = const(0)
_HHMM   = const(1)
_MMSS   = const(2)
_Yr     = const(3)
_Mon    = const(4)
_Day    = const(5)
_SetYr  = const(6)
_SetMon = const(7)
_SetDay = const(8)
_SetMin = const(9)
_SetSec = const(10)

# Action Constants (private)
_NOP    = const(11)
_YrInc  = const(12)
_YrDec  = const(13)
_MonInc = const(14)
_MonDec = const(15)
_DayInc = const(16)
_DayDec = const(17)
_MinInc = const(18)
_MinDec = const(19)
_Sec00  = const(20)

# Digit Sprite Constants (private)
# These are for modifying the digit sprite TileGrid objects
_D0   = const( 0)
_D1   = const( 1)
_D2   = const( 2)
_D3   = const( 3)
_D4   = const( 4)
_D5   = const( 5)
_D6   = const( 6)
_D7   = const( 7)
_D8   = const( 8)
_D9   = const( 9)
_DCol = const(10)  # colon
_DBlk = const(11)  # solid black


class StateMachine:

    # Button Press Constants (public)
    # CAUTION: These values must match column indexes of StateMachine.TABLE
    UP     = const(0)
    DOWN   = const(1)
    LEFT   = const(2)
    RIGHT  = const(3)
    A      = const(4)
    B      = const(5)
    AB     = const(6)
    SELECT = const(7)

    # LookUp Table (private) of actions (including NOP and state transitions)
    # for possible button press events in each of the possible states
    _TABLE = (
        # UP      DOWN     LEFT   RIGHT  A        B      A+B    SELECT     State
        (_HHMM,   _HHMM,   _HHMM, _HHMM, _HHMM,   _HHMM, _Demo, _HHMM  ),  # demo
        (_NOP,    _NOP,    _Day,  _MMSS, _NOP,    _HHMM, _Demo, _SetMin),  # hhmm
        (_NOP,    _NOP,    _HHMM, _Yr,   _NOP,    _HHMM, _Demo, _SetSec),  # mmss
        (_NOP,    _NOP,    _MMSS, _Mon,  _NOP,    _HHMM, _Demo, _SetYr ),  # year
        (_NOP,    _NOP,    _Yr,   _Day,  _NOP,    _HHMM, _Demo, _SetYr ),  # mon
        (_NOP,    _NOP,    _Mon,  _HHMM, _NOP,    _HHMM, _Demo, _SetYr ),  # day
        (_YrInc,  _YrDec,  _NOP,  _NOP,  _SetMon, _HHMM, _Demo, _HHMM  ),  # setYr
        (_MonInc, _MonDec, _NOP,  _NOP,  _SetDay, _HHMM, _Demo, _HHMM  ),  # setMon
        (_DayInc, _DayDec, _NOP,  _NOP,  _SetMin, _HHMM, _Demo, _HHMM  ),  # setDay
        (_MinInc, _MinDec, _NOP,  _NOP,  _SetSec, _HHMM, _Demo, _HHMM  ),  # setMin
        (_Sec00,  _Sec00,  _NOP,  _NOP,  _SetYr,  _HHMM, _Demo, _HHMM  ),  # setSec
    )

    def __init__(self, digits, charLCD):
        # Save references to the collections of sprite TileGrid objects
        self.digits = digits
        self.charLCD = charLCD
        # Start in the state for Clock Mode with hours and minutes sub-mode
        self.state = _HHMM
        # TODO: Change this to use the Adalogger FeatherWing RTC chip
        self.rtcYear = 2024
        self.rtcMon  = 9
        self.rtcDay  = 5
        self.rtcHour = 12
        self.rtcMin_ = 00
        self.rtcSec  = 00
        # Set initial display state
        self._setDigits(_D1, _D2, _DCol, _D0, _D0)


    def _setDigits(self, a, b, c, d, e):
        # Update numeric sprites using digit sprite constants a, b, c, d, and e
        dgts = self.digits
        # These check the old values of the sprites in an attempt to minimize
        # the area of the display which needs to be refreshed
        if dgts[0][0] != a:  # leftmost digit:  0..9 or ' '
            dgts[0][0] = a
        if dgts[1][0] != b:  # second digit:    0..9 or ' '
            dgts[1][0] = b
        if dgts[2][0] != c:  # center position: ':' or ' '
            dgts[2][0] = c
        if dgts[3][0] != d:  # third digit:     0..9
            dgts[3][0] = d
        if dgts[4][0] != e:  # rightmost digit: 0..9
            dgts[4][0] = e


    def handle(self, button):
        # Handle a button press event

        # Check lookup table for the response code for this button press event
        if button < UP or button > SELECT:
            print("Button value out of range:", button)
            return
        r = self._TABLE[self.state][button]

        # Cache frequently used functions
        setD = self._setDigits
        setMsg = self.charLCD.setMsg

        # The help message for Set Mode uses a special up/down arrows sprite
        # that is mapped in the sprite sheet to ASCII DEL (0x7f)
        SET_HELP = b"\x7f:+/-  B:Exit  A:OK"

        # Handle the response code
        # First, check for state transition codes
        if r == _Demo:
            self.state = r
            setD(_D1, _D2, _DCol, _D3, _D4)
            setMsg(b'DEMO MODE 2024-09-10')
            setMsg(b'AaBb~!@#$%^&*()-=_+?', top=False)
        elif r == _HHMM:
            self.state = r
            setMsg(b'')
            setMsg(b'', top=False)
        elif r == _MMSS:
            self.state = r
            setMsg(b'MM:SS')
        elif r == _Yr:
            self.state = r
            setMsg(b'Year')
        elif r == _Mon:
            self.state = r
            setMsg(b'Month')
        elif r == _Day:
            self.state = r
            setMsg(b'Day')
        elif r == _SetYr:
            self.state = r
            setMsg(b'    SET YEAR')
            setMsg(SET_HELP, top=False)
        elif r == _SetMon:
            self.state = r
            setMsg(b'    SET MON')
            setMsg(SET_HELP, top=False)
        elif r == _SetDay:
            self.state = r
            setMsg(b'    SET DAY')
            setMsg(SET_HELP, top=False)
        elif r == _SetMin:
            self.state = r
            setMsg(b'    SET MIN')
            setMsg(SET_HELP, top=False)
        elif r == _SetSec:
            self.state = r
            setMsg(b'    SET SEC')
            setMsg(SET_HELP, top=False)

        # Second, check for action codes that don't change the state
        elif r == _NOP:
            return
        elif r == _YrInc:
            pass          # TODO: IMPLEMENT THIS
        elif r == _YrDec:
            pass          # TODO: IMPLEMENT THIS
        elif r == _MonInc:
            pass          # TODO: IMPLEMENT THIS
        elif r == _MonDec:
            pass          # TODO: IMPLEMENT THIS
        elif r == _DayInc:
            pass          # TODO: IMPLEMENT THIS
        elif r == _DayDec:
            pass          # TODO: IMPLEMENT THIS
        elif r == _MinInc:
            pass          # TODO: IMPLEMENT THIS
        elif r == _MinDec:
            pass          # TODO: IMPLEMENT THIS
        elif r == _Sec00:
            pass          # TODO: IMPLEMENT THIS
