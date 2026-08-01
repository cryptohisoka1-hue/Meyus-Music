# Kart kodu -> sticker paketindeki index (0'dan baslar) eslesmesi.
#
# NOT: Bu eslesme, paketteki sticker emoji'leri hepsi ayni (bos/placeholder)
# oldugu icin GORSEL OLARAK DOGRULANAMADI. Standart bir UNO destesinin
# tipik dizilisine (renk sirasiyla 0,1..9,+2,DUR,YON, sonra jokerler)
# gore VARSAYIMLA olusturuldu. Oyunda test ederken bir kartin gorunen
# sticker'i ile gercek kart kodu uyusmuyorsa, asagidaki sozlukteki ilgili
# index'i duzeltmemiz gerekecek - bana hangi kartin yanlis goruntu ile
# ciktigini soyle (or. "kirmizi_7 oynadim ama sari 3 gorundu").

COLORS = ["kirmizi", "yesil", "mavi", "sari"]

CARD_TO_STICKER_INDEX = {}

idx = 0
for color in COLORS:
    CARD_TO_STICKER_INDEX[f"{color}_0"] = idx
    idx += 1
    for n in range(1, 10):
        CARD_TO_STICKER_INDEX[f"{color}_{n}"] = idx
        idx += 1
    for symbol in ["artiiki", "durdur", "yonvedegis"]:
        CARD_TO_STICKER_INDEX[f"{color}_{symbol}"] = idx
        idx += 1

CARD_TO_STICKER_INDEX["wild_renk"] = idx
idx += 1
CARD_TO_STICKER_INDEX["wild_artidort"] = idx
idx += 1
      
