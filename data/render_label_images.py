#!/usr/bin/env python3
"""
render_label_images.py
----------------------
Renders the "scanned image" behind each label capture in DB1: a photograph-like
picture of the medicine pack label, degraded the way a counter camera degrades it
(tilt, blur, sensor noise, glare, JPEG compression).

The picture always shows what is really printed on the pack, which is the
product's registered data. The OCR text stored in DB1.label_text is the damaged
reading of that picture. Comparing the two is the whole point of the demo.

Needs Pillow. Without it the script says so and exits cleanly; the rest of the
system works without the images.
"""

from __future__ import annotations
import hashlib
import json
import os
import random
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from integration.uncertainty import paths
from integration.uncertainty.standardize import to_date

FONT_CANDIDATES = {
    "bold": ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "regular": ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf"],
    "mono": ["C:/Windows/Fonts/consola.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
             "/System/Library/Fonts/Menlo.ttc"],
}


def _font(kind, size):
    from PIL import ImageFont
    for path in FONT_CANDIDATES[kind]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render(product: dict, out_path: str, seed: int) -> None:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    rng = random.Random(seed)
    w, h = 900, 430
    img = Image.new("RGB", (w, h), (247, 245, 238))
    d = ImageDraw.Draw(img)
    hue = int(hashlib.md5(str(product.get("manufacturer_id")).encode()).hexdigest()[:6], 16)
    band = ((hue >> 16) % 120 + 40, (hue >> 8) % 120 + 60, hue % 120 + 90)
    d.rectangle([0, 0, w, 92], fill=band)
    name = str(product.get("product_name") or "").upper()
    d.text((30, 14), name, font=_font("bold", 54), fill=(255, 255, 255))
    d.text((32, 108), f"{product.get('generic_name')} {product.get('dosage_form', '')}s IP",
           font=_font("regular", 28), fill=(40, 40, 40))
    mfg, exp = to_date(product.get("manufacture_date")), to_date(product.get("expiry_date"))
    lines = [f"B.No.  {product.get('batch_number')}",
             f"MFD    {mfg:%m/%Y}" if mfg else "MFD",
             f"EXP    {exp:%m/%Y}" if exp else "EXP",
             f"MRP Rs.{float(product.get('msrp_kes') or 0):.2f} (incl. of all taxes)"]
    for i, line in enumerate(lines):
        d.text((32, 158 + i * 40), line, font=_font("regular", 28), fill=(20, 20, 20))
    d.text((32, 340), f"UID  {product.get('product_uid')}", font=_font("mono", 40), fill=(10, 10, 10))
    d.text((32, 392), f"Mfd. by {product.get('manufacturer_name') or product.get('manufacturer_id')}",
           font=_font("regular", 22), fill=(70, 70, 70))
    # A pseudo 2D code: deterministic per product, so the same pack always looks the same.
    cell, n, x0, y0 = 9, 17, 690, 150
    code_rng = random.Random(product.get("product_uid"))
    d.rectangle([x0 - 8, y0 - 8, x0 + n * cell + 8, y0 + n * cell + 8], fill=(255, 255, 255))
    for i in range(n):
        for j in range(n):
            edge = i == 0 or j == 0
            if edge or code_rng.random() < 0.5:
                d.rectangle([x0 + i * cell, y0 + j * cell, x0 + (i + 1) * cell - 1, y0 + (j + 1) * cell - 1],
                            fill=(0, 0, 0))

    # Camera damage.
    img = img.rotate(rng.uniform(-3.2, 3.2), resample=Image.BICUBIC, expand=True, fillcolor=(120, 115, 105))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.9, 1.7)))
    noise = Image.effect_noise(img.size, rng.uniform(18, 34)).convert("RGB")
    img = Image.blend(img, noise, rng.uniform(0.07, 0.13))
    glare = Image.new("L", img.size, 0)
    gd = ImageDraw.Draw(glare)
    gx, gy = rng.randint(100, img.size[0] - 200), rng.randint(40, img.size[1] - 140)
    gd.ellipse([gx, gy, gx + rng.randint(160, 300), gy + rng.randint(70, 140)], fill=rng.randint(70, 120))
    glare = glare.filter(ImageFilter.GaussianBlur(28))
    img = Image.composite(Image.new("RGB", img.size, (255, 255, 255)), img, glare)
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.75, 0.95))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, "JPEG", quality=58)


def main():
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("  Pillow not installed: skipping label images (pip install pillow to render them).")
        return
    try:
        with open(paths.ground_truth_file(), "r", encoding="utf-8") as f:
            truth = json.load(f)["records"]
    except (OSError, ValueError, KeyError):
        truth = {}
    c1 = sqlite3.connect(paths.db_path("db1"))
    c3 = sqlite3.connect(paths.db_path("db3"))
    c3.row_factory = sqlite3.Row
    products = {r["product_uid"]: dict(r) for r in c3.execute(
        "SELECT p.*, m.company_name AS manufacturer_name FROM products p "
        "LEFT JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id")}
    rows = c1.execute("SELECT event_id, scan_code, label_image FROM purchase_events "
                      "WHERE label_image IS NOT NULL").fetchall()
    out_dir = os.path.join(BASE, "dashboard")
    made = 0
    for event_id, scan_code, image in rows:
        uid = (truth.get(f"db1:purchase_events:{event_id}") or {}).get("true_uid") or scan_code
        p = products.get(uid)
        if not p:
            continue
        render(p, os.path.join(out_dir, image), seed=int(hashlib.md5(event_id.encode()).hexdigest()[:8], 16))
        made += 1
    print(f"  rendered {made} label image(s) -> dashboard/samples/labels/")


if __name__ == "__main__":
    main()
