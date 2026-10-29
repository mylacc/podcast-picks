# Renders assets/cover.png (3000x3000 RGB). Usage: python3 scripts/cover.py assets/cover.png
import math, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
S = 3000
SS = 2  # supersample for smooth edges
W = S * SS
F = "/usr/share/fonts/opentype/inter/"
def font(name, px): return ImageFont.truetype(F + name, px * SS)

# background: vertical gradient, deep green to darker teal
bg = Image.new("RGB", (W, W))
top, bot = (24, 92, 76), (10, 40, 38)
grad = Image.linear_gradient("L").resize((W, W))
bg = Image.composite(Image.new("RGB", (W, W), bot), Image.new("RGB", (W, W), top), grad)
d = ImageDraw.Draw(bg)

cream = (246, 241, 227)
gold = (232, 178, 88)
mint = (124, 206, 178)

# waveform bars rising like a growth curve, bottom third
n = 23
left, right = 300 * SS, 2700 * SS
base = 2620 * SS
gap = (right - left) / n
bw = gap * 0.58
for i in range(n):
    t = i / (n - 1)
    trend = 0.18 + 0.82 * (t ** 1.6)          # rising curve
    wobble = 1.0 if i == n - 1 else 0.55 + 0.4 * abs(math.sin(i * 1.7 + 0.4))
    h = (700 * SS) * trend * wobble + 60 * SS
    x0 = left + i * gap + (gap - bw) / 2
    col = gold if i == n - 1 else mint
    d.rounded_rectangle([x0, base - h, x0 + bw, base], radius=bw / 2, fill=col)

# baseline
d.rounded_rectangle([left, base + 40 * SS, right, base + 64 * SS], radius=12 * SS, fill=(cream[0], cream[1], cream[2]))

# Title
big = font("InterDisplay-Black.otf", 1100)
txt = "FI"
bb = d.textbbox((0, 0), txt, font=big)
tw, th = bb[2] - bb[0], bb[3] - bb[1]
d.text(((W - tw) / 2 - bb[0], 260 * SS - bb[1]), txt, font=big, fill=cream)

sub = font("InterDisplay-Bold.otf", 270)
txt2 = "PODCAST PICKS"
bb2 = d.textbbox((0, 0), txt2, font=sub)
# letter spacing by drawing per char
spacing = 22 * SS
chars = list(txt2)
adv = [sub.getlength(c) for c in chars]
total = sum(adv) + spacing * (len(chars) - 1)
x = (W - total) / 2
y = 1480 * SS - bb2[1]
for c, a in zip(chars, adv):
    d.text((x, y), c, font=sub, fill=gold)
    x += a + spacing

img = bg.resize((S, S), Image.LANCZOS)
out = sys.argv[1]
img.save(out, optimize=True)
