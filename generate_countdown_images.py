#!/usr/bin/env python3
"""
Generate countdown images for Pixel Challenge
Run once to create the PNG files in assets/
"""
from PIL import Image, ImageDraw, ImageFont
import os

ASSETS_DIR = "/home/ledgame/easter_game/assets"
WIDTH = 1920
HEIGHT = 1080
BG_COLOR = (12, 6, 31)  # Dark purple matching console theme

def create_countdown_image(text, text_color, filename):
    """Create a countdown image with large centered text"""
    img = Image.new('RGB', (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Try to use a bold font, fall back to default
    font_size = 400 if len(text) <= 2 else 300
    try:
        # Try common Linux fonts
        for font_name in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                          '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
                          '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf']:
            if os.path.exists(font_name):
                font = ImageFont.truetype(font_name, font_size)
                break
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    
    # Get text bounding box for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (WIDTH - text_width) // 2
    y = (HEIGHT - text_height) // 2 - 50  # Slightly above center
    
    # Draw shadow
    shadow_offset = 8
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0))
    
    # Draw main text
    draw.text((x, y), text, font=font, fill=text_color)
    
    # Save
    filepath = os.path.join(ASSETS_DIR, filename)
    img.save(filepath, 'PNG')
    print(f"Created: {filepath}")

def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    
    # Create countdown images
    create_countdown_image("3", (255, 80, 80), "countdown_3.png")      # Red
    create_countdown_image("2", (255, 220, 80), "countdown_2.png")     # Yellow
    create_countdown_image("1", (80, 255, 80), "countdown_1.png")      # Green
    create_countdown_image("GO!", (80, 255, 80), "countdown_go.png")   # Green
    
    print("\nAll countdown images created!")
    print(f"Location: {ASSETS_DIR}")

if __name__ == "__main__":
    main()