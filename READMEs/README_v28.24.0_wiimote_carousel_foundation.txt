Pixel Challenge v28.24.0 - Wii Remote External Carousel Foundation

Adds the first implementation foundation for the Wii Remote menu-wand/external screen front-end:

- Viewer supports a centered 3-tile PNG carousel overlay.
- Tiles smooth-scroll left/right with keyboard Left/Right or mouse side-clicks.
- Center tile activates with mouse click, Enter, or Space.
- Tile actions are sent back to the console through console_command.txt.
- Console handles Home, Previous Game, Next Game, Start Game, Score, and Menu placeholder actions.
- Scoreboard timeout returns to the external carousel after 30 seconds and advances to the next playable game.
- Menu is intentionally a placeholder for future development.
- External carousel background defaults to selected game splash artwork, but can be switched to a custom background via external_carousel_config.json.
- Adds replaceable PNG tile artwork under assets/ui/tiles/.

Notes:
- This is the UI/control foundation. It does not yet include the actual Wii Remote Bluetooth mouse service.
- Existing laptop/operator controls remain on the laptop screen; the external overlay stays public-facing.
- games/global.config.json still has invert_playfield=true.
