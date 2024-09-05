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

# State Transition Constants
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

# Digit Sprite Constants (private) for modifying number TileGrid objects
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

# Badge Sprite Constants (private) for modifying mode badge TileGrid objects
_BYr   = const(0)
_BMon  = const(1)
_BDay  = const(2)
_BSet  = const(3)
_BHHMM = const(4)
_BMMSS = const(5)
_BBlk  = const(6)


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

    def __init__(self, digits, badges):
        # Save references to the collections of sprite TileGrid objects
        self.digits = digits
        self.badges = badges
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
        self._setBadges(_BBlk, _BBlk, _BBlk, _BBlk, _BBlk, _BBlk)


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


    def _setBadges(self, yr, mon, day, set_, hhmm, mmss):
        # Set mode badges according to booleans: yr, mon, ... mmss
        # True means show the badge, False means show a black rectangle

        # Cache frequently used TileGrid object references
        tgYEAR = self.badges['YEAR']
        tgMON  = self.badges['MON']
        tgDAY  = self.badges['DAY']
        tgSET  = self.badges['SET']
        tgHHMM = self.badges['HHMM']
        tgMMSS = self.badges['MMSS']

        # These check the old values of the badges in an attempt to minimize
        # the area of the display which needs to be refreshed.
        if yr != (tgYEAR[0] == _BYr):
            tgYEAR[0] = _BYr  if yr else _BBlk
        if mon != (tgMON[0] == _BMon):
            tgMON[0]  = _BMon if mon else _BBlk
        if day != (tgDAY[0] == _BDay):
            tgDAY[0]  = _BDay if day else _BBlk
        if set_ != (tgSET[0] == _BSet):
            tgSET[0]  = _BSet if set_ else _BBlk
        if hhmm != (tgHHMM[0] == _BHHMM):
            tgHHMM[0] = _BHHMM if hhmm else _BBlk
        if mmss != (tgMMSS[0] == _BMMSS):
            tgMMSS[0] = _BMMSS if mmss else _BBlk


    def handle(self, button):
        # Handle a button press event

        # Check lookup table for the response code for this button press event
        if button < UP or button > SELECT:
            print("Button value out of range:", button)
            return
        r = self._TABLE[self.state][button]

        # Cache frequently used functions
        setD = self._setDigits
        setB = self._setBadges

        # Handle the response code
        # First, check for state transition codes
        if r == _Demo:
            self.state = r
            setD(_D1, _D2, _DCol, _D3, _D4)
            setB(True, True, True, True, True, True)
        elif r == _HHMM:
            self.state = r
            setB(False, False, False, False, False, False)
        elif r == _MMSS:
            self.state = r
            setB(False, False, False, False, False, True)
        elif r == _Yr:
            self.state = r
            setB(True, False, False, False, False, False)
        elif r == _Mon:
            self.state = r
            setB(False, True, False, False, False, False)
        elif r == _Day:
            self.state = r
            setB(False, False, True, False, False, False)
        elif r == _SetYr:
            self.state = r
            setB(True, False, False, True, False, False)
        elif r == _SetMon:
            self.state = r
            setB(False, True, False, True, False, False)
        elif r == _SetDay:
            self.state = r
            setB(False, False, True, True, False, False)
        elif r == _SetMin:
            self.state = r
            setB(False, False, False, True, True, False)
        elif r == _SetSec:
            self.state = r
            setB(False, False, False, True, False, True)

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
