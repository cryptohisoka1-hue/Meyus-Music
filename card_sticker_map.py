# Kart kodu -> sticker index eşlemesi, TEMA BAŞINA ayrı bir sözlük olarak tutulur.
#
# Yeni bir tema eklerken:
#   1) /stickerlar <paket_adı>  komutuyla paketin içeriğini (index + emoji) listele
#   2) Paketi Telegram'da (t.me/addstickers/<paket_adı>) açıp stickerleri GÖRSEL
#      olarak tek tek incele (emoji'ler genelde ayırt edici değildir, hepsi 🃏 olabilir)
#   3) Aşağıya THEME_CARD_MAPS içine yeni bir "tema_id": {...} girdisi ekle
#
# Bir tema için eşleme boş bırakılırsa ({}), o tema seçilebilir ama sticker
# gösteremez; sistem otomatik olarak normal kart görseline (fotoğraf) düşer,
# yani hiçbir şey bozulmaz.

# --- classic_colorblind: 54 sticker ---
# Gerçek sıra: Joker(0-1) → Kırmızı(2-14) → Yeşil(15-27) → Mavi(28-40) → Sarı(41-53)
# Her renk grubu içinde sıra: 0,1,2,3,4,5,6,7,8,9,arti2,yon,dur
_CLASSIC_COLORBLIND_MAP = {
    # Jokerler (0-1)
    "wild_renk":     0,
    "wild_artidort": 1,

    # Kırmızı (2-14)
    "kirmizi_0":     2,
    "kirmizi_1":     3,
    "kirmizi_2":     4,
    "kirmizi_3":     5,
    "kirmizi_4":     6,
    "kirmizi_5":     7,
    "kirmizi_6":     8,
    "kirmizi_7":     9,
    "kirmizi_8":     10,
    "kirmizi_9":     11,
    "kirmizi_arti2": 12,
    "kirmizi_yon":   13,
    "kirmizi_dur":   14,

    # Yeşil (15-27)
    "yesil_0":     15,
    "yesil_1":     16,
    "yesil_2":     17,
    "yesil_3":     18,
    "yesil_4":     19,
    "yesil_5":     20,
    "yesil_6":     21,
    "yesil_7":     22,
    "yesil_8":     23,
    "yesil_9":     24,
    "yesil_arti2": 25,
    "yesil_yon":   26,
    "yesil_dur":   27,

    # Mavi (28-40)
    "mavi_0":     28,
    "mavi_1":     29,
    "mavi_2":     30,
    "mavi_3":     31,
    "mavi_4":     32,
    "mavi_5":     33,
    "mavi_6":     34,
    "mavi_7":     35,
    "mavi_8":     36,
    "mavi_9":     37,
    "mavi_arti2": 38,
    "mavi_yon":   39,
    "mavi_dur":   40,

    # Sarı (41-53)
    "sari_0":     41,
    "sari_1":     42,
    "sari_2":     43,
    "sari_3":     44,
    "sari_4":     45,
    "sari_5":     46,
    "sari_6":     47,
    "sari_7":     48,
    "sari_8":     49,
    "sari_9":     50,
    "sari_arti2": 51,
    "sari_yon":   52,
    "sari_dur":   53,
}

# --- Yeni temalar (cat_arya, princess_arya, bjk_arya, gs_arya, ---
# --- arya_fb_theme_pack, wolf_arya): Görsel incelemeye göre hepsi ---
# --- AYNI 108 sticker'lık düzeni paylaşıyor (deste ile birebir,     ---
# --- her değerden 2 kopya):                                        ---
#   0-1:   Joker (renk)        ×2
#   2-3:   Joker (+4)          ×2
#   4-29:  Kırmızı  0..9,+2,yön,dur   (her biri ×2)
#   30-55: Yeşil    0..9,+2,yön,dur   (her biri ×2)
#   56-81: Mavi     0..9,+2,yön,dur   (her biri ×2)
#   82-107:Sarı     0..9,+2,yön,dur   (her biri ×2)
# Dublikatlar görsel olarak aynı olduğu için her kart kodu için
# sadece ilk kopyanın index'i kullanılıyor.

_VALUE_ORDER = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "arti2", "yon", "dur"]
_COLOR_BASE_OFFSET = {"kirmizi": 4, "yesil": 30, "mavi": 56, "sari": 82}


def _build_standard_108_map():
    m = {"wild_renk": 0, "wild_artidort": 2}
    for color, base in _COLOR_BASE_OFFSET.items():
        for i, val in enumerate(_VALUE_ORDER):
            m[f"{color}_{val}"] = base + i * 2
    return m


_STANDARD_108_MAP = _build_standard_108_map()

_CAT_ARYA_MAP = dict(_STANDARD_108_MAP)
_PRINCESS_ARYA_MAP = dict(_STANDARD_108_MAP)
_BJK_ARYA_MAP = dict(_STANDARD_108_MAP)
_GS_ARYA_MAP = dict(_STANDARD_108_MAP)
_ARYA_FB_THEME_PACK_MAP = dict(_STANDARD_108_MAP)
_WOLF_ARYA_MAP = dict(_STANDARD_108_MAP)

THEME_CARD_MAPS = {
    "classic_colorblind": _CLASSIC_COLORBLIND_MAP,
    "cat_arya": _CAT_ARYA_MAP,
    "princess_arya": _PRINCESS_ARYA_MAP,
    "bjk_arya": _BJK_ARYA_MAP,
    "gs_arya": _GS_ARYA_MAP,
    "arya_fb_theme_pack": _ARYA_FB_THEME_PACK_MAP,
    "wolf_arya": _WOLF_ARYA_MAP,
}

# Geriye dönük uyumluluk: eski kodun import ettiği isim, klasik temayı gösterir.
CARD_TO_STICKER_INDEX = _CLASSIC_COLORBLIND_MAP


def get_card_map_for_theme(theme_id):
    """Verilen tema için kart eşleme sözlüğünü döndürür (yoksa klasik temaya düşer)."""
    return THEME_CARD_MAPS.get(theme_id, _CLASSIC_COLORBLIND_MAP)
    
