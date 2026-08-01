"""
Ozgun (Mattel UNO tasarimina ait olmayan) kart gorselleri uretir.
Cikti: assets/cards/*.png

Her renk icin: 0-9, +2, skip (S), reverse (R)
Ayrica: wild (W), wild+4 (W4)

Kullanim:
    python generate_cards.py
"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "cards")
os.makedirs(OUT_DIR, exist_ok=True)

FONT_PATH_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

COLORS = {
    "kirmizi": (211, 47, 47),
    "yesil": (56, 142, 60),
    "mavi": (25, 118, 210),
    "sari": (251, 192, 45),
}

W, H = 300, 440
RADIUS = 28


def rounded_card(bg_color):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=RADIUS, fill=bg_color, outline=(255, 255, 255), width=6)
    # ic beyaz oval (klasik uno hissi, ozgun oran/aci ile)
    draw.ellipse([W * 0.12, H * 0.28, W * 0.88, H * 0.72], fill=(255, 255, 255, 235))
    return img, draw


def center_text(draw, text, font, color, cx, cy):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), text, font=font, fill=color)


def corner_labels(draw, label, font_small, color):
    center_text(draw, label, font_small, color, 34, 30)
    center_text(draw, label, font_small, color, W - 34, H - 30)


def make_number_card(color_name, color_rgb, number):
    img, draw = rounded_card(color_rgb)
    big_font = ImageFont.truetype(FONT_PATH_BOLD, 150)
    small_font = ImageFont.truetype(FONT_PATH_BOLD, 40)
    center_text(draw, str(number), big_font, color_rgb, W / 2, H / 2)
    corner_labels(draw, str(number), small_font, (255, 255, 255))
    img.save(os.path.join(OUT_DIR, f"{color_name}_{number}.png"))


def make_symbol_card(color_name, color_rgb, symbol_code, glyph, label):
    img, draw = rounded_card(color_rgb)
    big_font = ImageFont.truetype(FONT_PATH_BOLD, 110)
    small_font = ImageFont.truetype(FONT_PATH_BOLD, 34)
    center_text(draw, glyph, big_font, color_rgb, W / 2, H / 2)
    corner_labels(draw, label, small_font, (255, 255, 255))
    img.save(os.path.join(OUT_DIR, f"{color_name}_{symbol_code}.png"))


def make_wild_card(symbol_code, glyph, label):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=RADIUS, fill=(20, 20, 20), outline=(255, 255, 255), width=6)
    quad_colors = [COLORS["kirmizi"], COLORS["mavi"], COLORS["sari"], COLORS["yesil"]]
    cx, cy = W / 2, H / 2
    quads = [
        [(0, 0), (cx, 0), (cx, cy), (0, cy)],
        [(cx, 0), (W, 0), (W, cy), (cx, cy)],
        [(0, cy), (cx, cy), (cx, H), (0, H)],
        [(cx, cy), (W, cy), (W, H), (cx, H)],
    ]
    mask = Image.new("L", (W, H), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, W - 1, H - 1], radius=RADIUS, fill=255)
    quad_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    qdraw = ImageDraw.Draw(quad_layer)
    for quad, col in zip(quads, quad_colors):
        qdraw.polygon(quad, fill=col)
    img = Image.composite(quad_layer, img, mask)
    draw = ImageDraw.Draw(img)
    ellipse_box = [W * 0.15, H * 0.32, W * 0.85, H * 0.68]
    draw.ellipse(ellipse_box, fill=(255, 255, 255, 235))
    big_font = ImageFont.truetype(FONT_PATH_BOLD, 90)
    small_font = ImageFont.truetype(FONT_PATH_BOLD, 34)
    center_text(draw, glyph, big_font, (30, 30, 30), W / 2, H / 2)
    corner_labels(draw, label, small_font, (255, 255, 255))
    img.save(os.path.join(OUT_DIR, f"wild_{symbol_code}.png"))


def main():
    for color_name, rgb in COLORS.items():
        for n in range(10):
            make_number_card(color_name, rgb, n)
        make_symbol_card(color_name, rgb, "artiiki", "+2", "+2")
        make_symbol_card(color_name, rgb, "durdur", "⊘", "DUR")
        make_symbol_card(color_name, rgb, "yonvedegis", "⇄", "YÖN")

    make_wild_card("renk", "★", "JOKER")
    make_wild_card("artidort", "+4", "+4")

    print(f"Toplam kart uretildi, klasor: {OUT_DIR}")


if __name__ == "__main__":
    main()
