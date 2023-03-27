#!/usr/bin/env python3
import signal

from eth_challenge_base.sui_ui import SuiUserInterface

if __name__ == "__main__":
    signal.alarm(60)
    SuiUserInterface().run()
