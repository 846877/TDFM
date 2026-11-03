"""Test rapide sur Windows (CI) : l'OCR Windows et la capture d'écran fonctionnent."""

from PIL import Image, ImageDraw, ImageFont

from tdfm.live.ocr import WindowsOcr
from tdfm.live.parser import parse_forge

img = Image.new("RGB", (900, 260), (20, 22, 28))
d = ImageDraw.Draw(img)
font = ImageFont.truetype("arial.ttf", 22)
rows = [("reliquat : 2,5", 0), ("Min      Max      Effets / Carac.", 1),
        ("151      200      176 Vitalité", 2), ("31        50        24 Sagesse", 3)]
for text, i in rows:
    d.text((40, 20 + i * 50), text, fill=(230, 230, 230), font=font)

ocr = WindowsOcr()
words = ocr.read(img, scale=1.5)
print("Langue OCR :", ocr.language)
print("Mots lus :", [w.text for w in words])
state = parse_forge(words)
print("État lu :", state)
assert state is not None, "fenêtre non reconnue"
got = {l.code: l.current for l in state.lines}
assert got.get("vi") == 176 and got.get("sa") == 24, got

try:
    from tdfm.live.capture import grab_screen
    shot = grab_screen()
    print("Capture d'écran OK :", shot.size)
except Exception as exc:  # le runner CI n'a pas toujours d'écran
    print("Capture d'écran indisponible sur le runner :", exc)
print("OK")
