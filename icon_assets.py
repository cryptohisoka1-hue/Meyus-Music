"""
Meyus UNO - Icon Assets

Telegram inline kart menüsünde kullanılan:
- Pas geç ikonunu
- Bilgi ikonunu

harici PNG dosyası gerektirmeden Python üzerinden üretir.
"""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# AYARLAR
# ============================================================

ICON_SIZE = 512


def _get_font(size: int):
    """
    Sistemde uygun bir font bulmaya çalışır.
    Font bulunamazsa PIL varsayılan fontunu kullanır.
    """

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/system/fonts/Roboto-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    return ImageFont.load_default()


def _png_bytes(image: Image.Image) -> bytes:
    """
    PIL Image nesnesini PNG byte verisine çevirir.
    """

    output = BytesIO()

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    return output.getvalue()


# ============================================================
# PAS GEÇ İKONU
# ============================================================

def _create_pass_icon() -> bytes:
    """
    Pas geç ikonunu oluşturur.

    Şeffaf arka plan üzerinde:
    - Yuvarlak ikon
    - İleri yönlü ok
    - PAS yazısı
    """

    image = Image.new(
        "RGBA",
        (ICON_SIZE, ICON_SIZE),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(image)

    # Dış yuvarlak
    margin = 20

    draw.ellipse(
        (
            margin,
            margin,
            ICON_SIZE - margin,
            ICON_SIZE - margin,
        ),
        fill=(35, 35, 35, 255),
        outline=(255, 255, 255, 255),
        width=12,
    )

    # Ok
    center_y = 205

    draw.line(
        (
            110,
            center_y,
            350,
            center_y,
        ),
        fill=(255, 255, 255, 255),
        width=30,
    )

    draw.polygon(
        (
            350,
            center_y - 65,
            425,
            center_y,
            350,
            center_y + 65,
        ),
        fill=(255, 255, 255, 255),
    )

    # PAS yazısı
    font = _get_font(105)

    text = "PAS"

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (ICON_SIZE - text_width) // 2
    y = 285

    draw.text(
        (
            x,
            y,
        ),
        text,
        font=font,
        fill=(255, 255, 255, 255),
    )

    return _png_bytes(image)


# ============================================================
# BİLGİ İKONU
# ============================================================

def _create_info_icon() -> bytes:
    """
    Bilgi ikonunu oluşturur.

    Şeffaf arka plan üzerinde beyaz 'i'
    bulunan dairesel ikon.
    """

    image = Image.new(
        "RGBA",
        (ICON_SIZE, ICON_SIZE),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(image)

    margin = 20

    # Dış yuvarlak
    draw.ellipse(
        (
            margin,
            margin,
            ICON_SIZE - margin,
            ICON_SIZE - margin,
        ),
        fill=(35, 35, 35, 255),
        outline=(255, 255, 255, 255),
        width=12,
    )

    # "i" noktası
    dot_radius = 30

    draw.ellipse(
        (
            ICON_SIZE // 2 - dot_radius,
            100,
            ICON_SIZE // 2 + dot_radius,
            100 + dot_radius * 2,
        ),
        fill=(255, 255, 255, 255),
    )

    # "i" gövdesi
    draw.rounded_rectangle(
        (
            ICON_SIZE // 2 - 28,
            180,
            ICON_SIZE // 2 + 28,
            390,
        ),
        radius=25,
        fill=(255, 255, 255, 255),
    )

    return _png_bytes(image)


# ============================================================
# DIŞARIDAN KULLANILACAK BYTE DEĞİŞKENLERİ
# ============================================================

pass_icon_bytes = _create_pass_icon()

info_icon_bytes = _create_info_icon()


# ============================================================
# OPSİYONEL YARDIMCI FONKSİYONLAR
# ============================================================

def get_pass_icon_bytes() -> bytes:
    """Pas ikonunun PNG byte verisini döndürür."""
    return pass_icon_bytes


def get_info_icon_bytes() -> bytes:
    """Bilgi ikonunun PNG byte verisini döndürür."""
    return info_icon_bytes
