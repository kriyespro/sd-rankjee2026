"""Generate PWA icons — blue #3b4cb8 rounded square with white R (matches site logo)."""

from pathlib import Path

from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

BRAND = (59, 76, 184)
WHITE = (255, 255, 255)
FONT_CANDIDATES = [
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/Library/Fonts/Arial Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
]


def _load_font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_r_icon(size: int, *, maskable: bool = False) -> Image.Image:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = int(size * (0.12 if maskable else 0.08))
    box = (pad, pad, size - pad, size - pad)
    radius = int(size * 0.16)
    draw.rounded_rectangle(box, radius=radius, fill=BRAND + (255,))
    font_size = int(size * (0.42 if maskable else 0.5))
    font = _load_font(font_size)
    text = 'R'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), text, fill=WHITE + (255,), font=font)
    return img.convert('RGB')


class Command(BaseCommand):
    help = 'Regenerate PWA icons (blue R logo) into static/img/icons/'

    def handle(self, *args, **options):
        out = Path('static/img/icons')
        out.mkdir(parents=True, exist_ok=True)
        for name, size, maskable in [
            ('icon-192.png', 192, False),
            ('icon-512.png', 512, False),
            ('icon-512-maskable.png', 512, True),
            ('apple-touch-icon.png', 180, False),
        ]:
            path = out / name
            _draw_r_icon(size, maskable=maskable).save(path, 'PNG')
            self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))
