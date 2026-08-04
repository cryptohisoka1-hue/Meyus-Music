"""
icon_assets.py dosyanızdaki, base64 satırlarının başına yanlışlıkla
karışmış "79\t", "156\t" gibi satır numarası öneklerini temizler.

Hiçbir base64 karakterine dokunmaz; sadece satır başındaki
   <rakamlar><TAB veya boşluklar>
kalıbını, kendisinden sonra bir tırnak (") geliyorsa siler.

Kullanım:
    python fix_icon_assets.py /path/to/icon_assets.py

Çıktı olarak aynı klasöre "icon_assets.fixed.py" yazar.
Orijinal dosyanıza dokunmaz.
"""

import re
import sys
import ast


def clean_line_number_prefixes(text: str) -> str:
    # Satır başındaki "  79\t"  veya  "156\t" gibi
    # (boşluk*)(rakamlar)(tab/boşluklar)(") kalıbını temizler.
    pattern = re.compile(r'^[ \t]*\d+\t(?=\s*")', re.MULTILINE)
    return pattern.sub("", text)


def main():
    if len(sys.argv) != 2:
        print("Kullanım: python fix_icon_assets.py /path/to/icon_assets.py")
        sys.exit(1)

    src_path = sys.argv[1]
    with open(src_path, "r", encoding="utf-8") as f:
        original = f.read()

    cleaned = clean_line_number_prefixes(original)

    # Doğrulama: dosya artık geçerli Python olarak parse ediliyor mu?
    try:
        ast.parse(cleaned)
        print("✅ Temizlenen dosya geçerli Python sözdizimine sahip.")
    except SyntaxError as e:
        print(f"⚠️  Temizlikten sonra hâlâ SyntaxError var: {e}")
        print("Dosyayı yine de yazıyorum, ama satırı elle kontrol etmeniz gerekebilir.")

    out_path = src_path.rsplit(".", 1)[0] + ".fixed.py"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(cleaned)

    n_removed = len(re.findall(r'^[ \t]*\d+\t(?=\s*")', original, re.MULTILINE))
    print(f"Temizlenen satır sayısı: {n_removed}")
    print(f"Düzeltilmiş dosya yazıldı: {out_path}")


if __name__ == "__main__":
    main()
    
