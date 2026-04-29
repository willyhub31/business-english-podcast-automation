from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "branding"
SOURCE_IMAGE = OUTPUT_DIR / "source_frames" / "frame_01.png"

THUMBNAIL_PATH = OUTPUT_DIR / "french_for_canada_thumbnail.png"
LOGO_PATH = OUTPUT_DIR / "french_for_canada_logo.png"
BANNER_PATH = OUTPUT_DIR / "french_for_canada_banner.png"
WATERMARK_PATH = OUTPUT_DIR / "french_for_canada_watermark.png"

RED = (210, 43, 43)
DEEP_RED = (137, 25, 25)
INK = (16, 24, 39)
CREAM = (250, 247, 242)
GOLD = (246, 194, 68)
SLATE = (43, 57, 78)

FONT_BLACK = "arialbd.ttf"
FONT_IMPACT = "impact.ttf"
FONT_UI = "seguisb.ttf"


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size=size)


def cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    src_w, src_h = image.size
    dst_w, dst_h = size
    scale = max(dst_w / src_w, dst_h / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - dst_w) // 2)
    top = max(0, (resized.height - dst_h) // 2)
    return resized.crop((left, top, left + dst_w, top + dst_h))


def fit_crop(
    image: Image.Image,
    box: tuple[int, int, int, int],
    focus_x: float = 0.5,
    focus_y: float = 0.5,
) -> Image.Image:
    left, top, right, bottom = box
    dst_w = right - left
    dst_h = bottom - top
    scale = max(dst_w / image.width, dst_h / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    max_left = max(0, resized.width - dst_w)
    max_top = max(0, resized.height - dst_h)
    crop_left = min(max(int(max_left * focus_x), 0), max_left)
    crop_top = min(max(int(max_top * focus_y), 0), max_top)
    return resized.crop((crop_left, crop_top, crop_left + dst_w, crop_top + dst_h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def add_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    anchor: str | None = None,
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int] | None = None,
) -> None:
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def draw_wave(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    bars = [0.18, 0.32, 0.55, 0.9, 0.42, 0.25, 0.62, 1.0, 0.7, 0.28, 0.5, 0.22]
    gap = width // (len(bars) * 2)
    bar_w = max(8, gap)
    cur_x = x
    for level in bars:
        bar_h = max(10, int(height * level))
        top = y + (height - bar_h) // 2
        draw.rounded_rectangle((cur_x, top, cur_x + bar_w, top + bar_h), radius=bar_w // 2, fill=color)
        cur_x += bar_w + gap


def maple_leaf(draw: ImageDraw.ImageDraw, center_x: int, center_y: int, scale: float, fill: tuple[int, int, int]) -> None:
    points = [
        (0, -74),
        (14, -42),
        (44, -58),
        (35, -18),
        (68, -8),
        (42, 14),
        (62, 50),
        (22, 40),
        (14, 82),
        (0, 58),
        (-14, 82),
        (-22, 40),
        (-62, 50),
        (-42, 14),
        (-68, -8),
        (-35, -18),
        (-44, -58),
        (-14, -42),
    ]
    scaled = [(center_x + int(px * scale), center_y + int(py * scale)) for px, py in points]
    draw.polygon(scaled, fill=fill)


def portrait_source(source: Image.Image) -> Image.Image:
    top = int(source.height * 0.34)
    return source.crop((0, top, source.width, source.height))


def background_source(source: Image.Image) -> Image.Image:
    top = int(source.height * 0.5)
    return source.crop((0, top, source.width, source.height))


def make_thumbnail(source: Image.Image) -> None:
    faces = portrait_source(source)
    backdrop = background_source(source)
    canvas = Image.new("RGB", (1280, 720), INK)
    bg = cover_crop(backdrop, canvas.size).filter(ImageFilter.GaussianBlur(18))
    bg = Image.blend(bg, Image.new("RGB", canvas.size, INK), 0.62)
    canvas.paste(bg, (0, 0))

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((52, 116, 420, 690), radius=36, fill=(0, 0, 0, 110))
    sdraw.rounded_rectangle((860, 116, 1228, 690), radius=36, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)

    left_box = (64, 128, 408, 680)
    right_box = (872, 128, 1216, 680)
    left_card = fit_crop(faces, left_box, focus_x=0.16, focus_y=0.08)
    right_card = fit_crop(faces, right_box, focus_x=0.84, focus_y=0.08)
    card_mask = rounded_mask((left_box[2] - left_box[0], left_box[3] - left_box[1]), 28)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(left_card, (left_box[0], left_box[1]), card_mask)
    layer.paste(right_card, (right_box[0], right_box[1]), card_mask)
    canvas = Image.alpha_composite(canvas, layer)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((38, 30, 1242, 692), radius=38, outline=(255, 255, 255, 40), width=2)
    draw.rounded_rectangle((428, 56, 852, 120), radius=28, fill=RED)
    maple_leaf(draw, 462, 88, 0.18, CREAM)
    add_text(draw, (640, 88), "FRENCH FOR CANADA", load_font(FONT_BLACK, 28), CREAM, anchor="mm")
    draw.rounded_rectangle((416, 414, 864, 506), radius=24, fill=(250, 247, 242, 232))
    add_text(draw, (640, 460), "REAL PODCAST LESSON", load_font(FONT_BLACK, 30), INK, anchor="mm")
    draw.rounded_rectangle((432, 530, 848, 636), radius=32, fill=(16, 24, 39, 222), outline=(255, 255, 255, 80), width=2)
    draw_wave(draw, 508, 560, 262, 46, RED)
    add_text(draw, (640, 613), "Sophie + Leo", load_font(FONT_UI, 28), CREAM, anchor="mm")

    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)
    add_text(draw, (640, 196), "FRENCH", load_font(FONT_IMPACT, 114), CREAM, anchor="mm", stroke_width=4, stroke_fill=INK)
    add_text(draw, (640, 286), "FOR CANADA", load_font(FONT_IMPACT, 102), GOLD, anchor="mm", stroke_width=4, stroke_fill=INK)
    add_text(draw, (640, 358), "Quebec phrases for real life", load_font(FONT_UI, 34), CREAM, anchor="mm")
    canvas.convert("RGB").save(THUMBNAIL_PATH, quality=95)


def make_logo(source: Image.Image) -> None:
    faces = portrait_source(source)
    backdrop = background_source(source)
    canvas = Image.new("RGB", (800, 800), INK)
    bg = fit_crop(backdrop, (0, 0, 800, 800), focus_x=0.5, focus_y=0.1).filter(ImageFilter.GaussianBlur(18))
    bg = Image.blend(bg, Image.new("RGB", (800, 800), INK), 0.78)
    canvas.paste(bg, (0, 0))

    overlay = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((34, 34, 766, 766), outline=RED, width=18)
    draw.ellipse((72, 72, 728, 728), outline=(255, 255, 255, 60), width=2)
    draw.rounded_rectangle((166, 440, 634, 628), radius=30, fill=(14, 20, 34, 214))
    maple_leaf(draw, 400, 170, 0.55, RED)
    add_text(draw, (400, 308), "FC", load_font(FONT_IMPACT, 184), CREAM, anchor="mm", stroke_width=3, stroke_fill=INK)
    draw_wave(draw, 250, 356, 300, 60, GOLD)
    add_text(draw, (400, 502), "French For", load_font(FONT_UI, 40), CREAM, anchor="mm")
    add_text(draw, (400, 560), "Canada", load_font(FONT_BLACK, 62), GOLD, anchor="mm")
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)
    canvas.convert("RGB").save(LOGO_PATH, quality=95)


def make_banner(source: Image.Image) -> None:
    faces = portrait_source(source)
    backdrop = background_source(source)
    canvas = Image.new("RGB", (2560, 1440), INK)
    bg = cover_crop(backdrop, canvas.size).filter(ImageFilter.GaussianBlur(22))
    bg = Image.blend(bg, Image.new("RGB", canvas.size, INK), 0.72)
    canvas.paste(bg, (0, 0))

    left_face = fit_crop(faces, (120, 190, 930, 1360), focus_x=0.16, focus_y=0.1)
    right_face = fit_crop(faces, (1630, 190, 2440, 1360), focus_x=0.84, focus_y=0.1)
    face_mask = rounded_mask((810, 1170), 74)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((94, 160, 956, 1386), radius=88, fill=(0, 0, 0, 100))
    sdraw.rounded_rectangle((1604, 160, 2466, 1386), radius=88, fill=(0, 0, 0, 100))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(left_face, (120, 190), face_mask)
    layer.paste(right_face, (1630, 190), face_mask)
    canvas = Image.alpha_composite(canvas, layer)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    safe_left = (2560 - 1546) // 2
    safe_right = safe_left + 1546
    draw.rounded_rectangle((safe_left + 24, 448, safe_right - 24, 992), radius=72, fill=(13, 18, 31, 194))
    draw.rounded_rectangle((safe_left + 142, 520, safe_left + 654, 618), radius=42, fill=RED)
    maple_leaf(draw, safe_left + 194, 570, 0.17, CREAM)
    add_text(draw, (safe_left + 416, 570), "NEW PODCAST EPISODES", load_font(FONT_BLACK, 42), CREAM, anchor="mm")
    add_text(draw, ((safe_left + safe_right) // 2, 704), "FRENCH FOR CANADA", load_font(FONT_IMPACT, 118), CREAM, anchor="mm", stroke_width=4, stroke_fill=INK)
    add_text(draw, ((safe_left + safe_right) // 2, 820), "Real French for life in Canada", load_font(FONT_BLACK, 58), GOLD, anchor="mm")
    draw_wave(draw, safe_left + 446, 858, 654, 92, RED)
    add_text(draw, ((safe_left + safe_right) // 2, 944), "Quebec  |  Work  |  TEF  |  Daily Life", load_font(FONT_UI, 42), CREAM, anchor="mm")
    canvas = Image.alpha_composite(canvas, overlay)
    canvas.convert("RGB").save(BANNER_PATH, quality=95)


def make_watermark() -> None:
    canvas = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((18, 18, 222, 222), radius=44, fill=(16, 24, 39, 190), outline=(255, 255, 255, 90), width=2)
    maple_leaf(draw, 120, 72, 0.16, RED)
    add_text(draw, (120, 124), "FC", load_font(FONT_IMPACT, 72), CREAM, anchor="mm", stroke_width=2, stroke_fill=INK)
    add_text(draw, (120, 170), "CANADA", load_font(FONT_BLACK, 22), GOLD, anchor="mm")
    canvas.save(WATERMARK_PATH)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE_IMAGE).convert("RGB")
    make_thumbnail(source)
    make_logo(source)
    make_banner(source)
    make_watermark()
    print(f"Created: {THUMBNAIL_PATH}")
    print(f"Created: {LOGO_PATH}")
    print(f"Created: {BANNER_PATH}")
    print(f"Created: {WATERMARK_PATH}")


if __name__ == "__main__":
    main()
