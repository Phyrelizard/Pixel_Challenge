# one_lane_test.py
import time
import sacn

# On Raspberry Pi OS, gpiozero is usually preinstalled.
from gpiozero import Button

FALCON_IP = "192.168.50.50"   # <-- set this
UNIVERSE = 1
PIXELS = 150
CHANNELS_PER_PIXEL = 3

# Button between GPIO17 and GND, using internal pull-up.
btn = Button(17, pull_up=True, bounce_time=0.03)

def main():
    sender = sacn.sACNsender()
    sender.start()
    sender.activate_output(UNIVERSE)
    sender[UNIVERSE].destination = FALCON_IP  # unicast
    sender[UNIVERSE].source_name = "EasterGamePi"

    dmx = bytearray(512)
    lit = 0

    def redraw():
        nonlocal dmx, lit
        dmx[:] = b"\x00" * 512
        # green bar: RGB = (0,255,0)
        for p in range(lit):
            base = p * CHANNELS_PER_PIXEL
            dmx[base + 0] = 0     # R
            dmx[base + 1] = 255   # G
            dmx[base + 2] = 0     # B
        sender[UNIVERSE].dmx_data = dmx

    redraw()
    print("Press button to advance. Ctrl+C to exit.")

    try:
        while True:
            btn.wait_for_press()
            lit = min(lit + 1, PIXELS)
            redraw()
            time.sleep(0.01)  # tiny delay to avoid double-trigger edge cases
    except KeyboardInterrupt:
        pass
    finally:
        sender.stop()

if __name__ == "__main__":
    main()

