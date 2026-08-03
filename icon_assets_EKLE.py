"""
Meyus UNO - Telegram Bot
Pas Geç ve Bilgi ikonları

Bu dosya ikonları base64 olarak saklar ve Telegram'a
BytesIO üzerinden gönderilebilmesini sağlar.

Kullanım:
    from icon_assets_EKLE import pass_icon_bytes, info_icon_bytes
"""

import base64
from io import BytesIO


# ============================================================
# PAS GEÇ İKONU
# ============================================================

PASS_ICON_B64 = (
    # Buraya PAS ikonunun base64 verisi gelecek.
    # Örnek:
    # "iVBORw0KGgoAAAANSUhEUgAA..."
    ""
)


# ============================================================
# BİLGİ İKONU
# ============================================================

INFO_ICON_B64 = (
    # Buraya BİLGİ ikonunun base64 verisi gelecek.
    # Örnek:
    # "iVBORw0KGgoAAAANSUhEUgAA..."
    ""
)


# ============================================================
# BYTESIO YARDIMCISI
# ============================================================

def _base64_to_bytesio(data: str, name: str) -> BytesIO:
    """
    Base64 verisini Telegram tarafından kullanılabilecek
    BytesIO nesnesine dönüştürür.
    """

    if not data:
        raise ValueError(
            f"{name} base64 verisi boş. "
            f"{name}_B64 değişkenine ikonun base64 verisini ekleyin."
        )

    try:
        raw = base64.b64decode(data)
    except Exception as exc:
        raise ValueError(
            f"{name} base64 verisi geçersiz."
        ) from exc

    stream = BytesIO(raw)
    stream.name = f"{name.lower()}.png"
    stream.seek(0)

    return stream


# ============================================================
# TELEGRAM'DA KULLANILACAK İKONLAR
# ============================================================

def get_pass_icon():
    """Pas geç ikonunu BytesIO olarak döndürür."""
    return _base64_to_bytesio(
        PASS_ICON_B64,
        "PASS_ICON"
    )


def get_info_icon():
    """Bilgi ikonunu BytesIO olarak döndürür."""
    return _base64_to_bytesio(
        INFO_ICON_B64,
        "INFO_ICON"
    )


# ============================================================
# MAIN.PY UYUMLULUĞU
# ============================================================

# main.py şu şekilde kullanıyorsa:
#
# from icon_assets_EKLE import pass_icon_bytes, info_icon_bytes
#
# aşağıdaki değişkenler hazırdır.

pass_icon_bytes = get_pass_icon()
info_icon_bytes = get_info_icon()
