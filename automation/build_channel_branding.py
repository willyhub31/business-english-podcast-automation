from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_IMAGE = BASE_DIR / "business_english_episode_frame_v2.png"
OUTPUT_DIR = BASE_DIR / "branding"

THUMBNAIL_PATH = OUTPUT_DIR / "english_pod_club_thumbnail.png"
LOGO_PATH = OUTPUT_DIR / "english_pod_club_logo.png"
BANNER_PATH = OUTPUT_DIR / "english_pod_club_banner.png"
WATERMARK_PATH = OUTPUT_DIR / "english_pod_club_watermark.png"

NAVY = (10, 21, 42)
YELLOW = (255, 206, 58)
RED = (232, 38, 38)
WHITE = (250, 250, 247)
TEAL = (47, 183, 197)


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size=size)


FONT_BLACK = "arialbd.ttf"
FONT_IMPACT = "impact.ttf"
FONT_UI = "seguisb.ttf"


def cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    src_w, src_h = image.size
    dst_w, dst_h = size
    scale = max(dst_w / src_w, dst_h / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - dst_w) // 2)
    top = max(0, (resized.height - dst_h) // 2)
    return resized.crop((left, top, left + dst_w, top + dst_h))


def fit_crop(image: Image.Image, box: tuple[int, int, int, int], focus_x: float = 0.5, focus_y: float = 0.5) -> Image.Image:
    left, top, right, bottom = box
    dst_w = right - left
    dst_h = bottom - top
    scale = max(dst_w / image.width, dst_h / image.height)
    resized = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    max_left = max(0, resized.width - dst_w)
    max_top = max(0, resized.height - dst_h)
    crop_left = int(max_left * focus_x)
    crop_top = int(max_top * focus_y)
    crop_left = min(max(crop_left, 0), max_left)
    crop_top = min(max(crop_top, 0), max_top)
    return resized.crop((crop_left, crop_top, crop_left + dst_w, crop_top + dst_h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def add_text_block(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont,
                   fill: tuple[int, int, int], stroke_width: int = 0, stroke_fill: tuple[int, int, int] | None = None,
                   spacing: int = 0, anchor: str | None = None) -> None:
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
        spacing=spacing,
        anchor=anchor,
    )


def draw_wave(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    bars = [0.15, 0.3, 0.55, 0.85, 0.45, 0.2, 0.65, 1.0, 0.7, 0.3, 0.55, 0.2, 0.15]
    gap = width // (len(bars) * 2)
    bar_w = gap
    cur_x = x
    for level in bars:
        bar_h = max(8, int(height * level))
        top = y + (height - bar_h) // 2
        draw.rounded_rectangle((cur_x, top, cur_x + bar_w, top + bar_h), radius=bar_w // 2, fill=color)
        cur_x += bar_w + gap


def face_source(source: Image.Image) -> Image.Image:
    top = int(source.height * 0.36)
    return source.crop((0, top, source.width, source.height))


def make_thumbnail(source: Image.Image) -> None:
    faces = face_source(source)
    canvas = Image.new("RGB", (1280, 720), NAVY)
    background = cover_crop(faces, canvas.size).filter(ImageFilter.GaussianBlur(10))
    background = Image.blend(background, Image.new("RGB", canvas.size, NAVY), 0.38)
    canvas.paste(background, (0, 0))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((32, 32, 1248, 688), radius=36, fill=(8, 16, 30, 58), outline=(255, 255, 255, 40), width=2)
    draw.rounded_rectangle((72, 46, 388, 112), radius=30, fill=RED)
    add_text_block(draw, (102, 78), "THE ENGLISH POD CLUB", load_font(FONT_UI, 28), WHITE, anchor="lm")

    left_box = (70, 160, 392, 680)
    right_box = (890, 160, 1210, 680)
    left_card = fit_crop(faces, left_box, focus_x=0.14, focus_y=0.02)
    right_card = fit_crop(faces, right_box, focus_x=0.86, focus_y=0.02)
    left_mask = rounded_mask((left_box[2] - left_box[0], left_box[3] - left_box[1]), 28)
    right_mask = rounded_mask((right_box[2] - right_box[0], right_box[3] - right_box[1]), 28)

    left_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    left_layer.paste(left_card, (70, 160), left_mask)
    right_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    right_layer.paste(right_card, (890, 160), right_mask)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((58, 150, 404, 692), radius=34, fill=(0, 0, 0, 120))
    sdraw.rounded_rectangle((878, 150, 1222, 692), radius=34, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))

    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)
    canvas = Image.alpha_composite(canvas, left_layer)
    canvas = Image.alpha_composite(canvas, right_layer)
    canvas = Image.alpha_composite(canvas, overlay)

    draw = ImageDraw.Draw(canvas)
    add_text_block(draw, (640, 170), "SALES CALL", load_font(FONT_IMPACT, 92), YELLOW, stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")
    add_text_block(draw, (640, 268), "ENGLISH", load_font(FONT_IMPACT, 118), WHITE, stroke_width=4, stroke_fill=(0, 0, 0), anchor="mm")
    add_text_block(draw, (640, 352), "Speak naturally from hello to close", load_font(FONT_UI, 32), WHITE, anchor="mm")

    draw.rounded_rectangle((438, 404, 842, 492), radius=26, fill=(255, 206, 58, 235))
    add_text_block(draw, (640, 449), "REAL PODCAST LESSON", load_font(FONT_BLACK, 32), NAVY, anchor="mm")
    draw.rounded_rectangle((444, 520, 836, 626), radius=30, fill=(10, 21, 42, 230), outline=(255, 255, 255, 100), width=2)
    draw_wave(draw, 510, 547, 260, 52, TEAL)
    add_text_block(draw, (640, 612), "Sophie + Leo", load_font(FONT_UI, 28), WHITE, anchor="mm")

    canvas.convert("RGB").save(THUMBNAIL_PATH, quality=95)


def make_logo(source: Image.Image) -> None:
    faces = face_source(source)
    canvas = Image.new("RGB", (800, 800), NAVY)
    bg = fit_crop(faces, (0, 0, 800, 800), focus_x=0.5, focus_y=0.08).filter(ImageFilter.GaussianBlur(8))
    bg = Image.blend(bg, Image.new("RGB", (800, 800), NAVY), 0.45)
    canvas.paste(bg, (0, 0))

    overlay = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((36, 36, 764, 764), outline=YELLOW, width=18)
    draw.ellipse((74, 74, 726, 726), outline=(255, 255, 255, 60), width=2)
    draw.rounded_rectangle((170, 448, 630, 620), radius=28, fill=(10, 21, 42, 210))
    add_text_block(draw, (400, 180), "EP", load_font(FONT_IMPACT, 210), YELLOW, stroke_width=3, stroke_fill=(0, 0, 0), anchor="mm")
    add_text_block(draw, (400, 292), "CLUB", load_font(FONT_BLACK, 62), WHITE, anchor="mm")
    draw_wave(draw, 260, 336, 280, 64, WHITE)
    add_text_block(draw, (400, 500), "Business English", load_font(FONT_UI, 38), WHITE, anchor="mm")
    add_text_block(draw, (400, 552), "Podcast", load_font(FONT_BLACK, 56), YELLOW, anchor="mm")
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)
    canvas.convert("RGB").save(LOGO_PATH, quality=95)


def make_banner(source: Image.Image) -> None:
    faces = face_source(source)
    canvas = Image.new("RGB", (2560, 1440), NAVY)
    bg = cover_crop(faces, (2560, 1440)).filter(ImageFilter.GaussianBlur(12))
    bg = Image.blend(bg, Image.new("RGB", (2560, 1440), NAVY), 0.44)
    canvas.paste(bg, (0, 0))

    left_face = fit_crop(faces, (80, 180, 910, 1360), focus_x=0.13, focus_y=0.02)
    right_face = fit_crop(faces, (1650, 180, 2480, 1360), focus_x=0.87, focus_y=0.02)
    left_mask = rounded_mask((830, 1180), 72)
    right_mask = rounded_mask((830, 1180), 72)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((56, 150, 934, 1386), radius=88, fill=(0, 0, 0, 110))
    sdraw.rounded_rectangle((1626, 150, 2504, 1386), radius=88, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)

    left_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    left_layer.paste(left_face, (80, 180), left_mask)
    right_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    right_layer.paste(right_face, (1650, 180), right_mask)
    canvas = Image.alpha_composite(canvas, left_layer)
    canvas = Image.alpha_composite(canvas, right_layer)

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    safe_left = (2560 - 1546) // 2
    safe_right = safe_left + 1546
    draw.rounded_rectangle((safe_left + 40, 460, safe_right - 40, 980), radius=64, fill=(8, 16, 30, 185))
    draw.rounded_rectangle((safe_left + 138, 520, safe_left + 622, 616), radius=42, fill=RED)
    add_text_block(draw, (safe_left + 188, 568), "NEW DAILY EPISODES", load_font(FONT_BLACK, 42), WHITE, anchor="lm")
    add_text_block(draw, ((safe_left + safe_right) // 2, 706), "THE ENGLISH POD CLUB", load_font(FONT_IMPACT, 120), WHITE, stroke_width=4, stroke_fill=(0, 0, 0), anchor="mm")
    add_text_block(draw, ((safe_left + safe_right) // 2, 822), "Business English with Sophie & Leo", load_font(FONT_BLACK, 58), YELLOW, anchor="mm")
    draw_wave(draw, safe_left + 470, 860, 610, 92, TEAL)
    add_text_block(draw, ((safe_left + safe_right) // 2, 940), "Real work conversations. Clear explanations. Better speaking.", load_font(FONT_UI, 42), WHITE, anchor="mm")

    canvas = Image.alpha_composite(canvas, overlay)
    canvas.convert("RGB").save(BANNER_PATH, quality=95)


def make_watermark() -> None:
    canvas = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((22, 22, 218, 218), radius=42, fill=(10, 21, 42, 180), outline=(255, 255, 255, 90), width=2)
    add_text_block(draw, (120, 86), "EP", load_font(FONT_IMPACT, 88), YELLOW, stroke_width=2, stroke_fill=(0, 0, 0), anchor="mm")
    add_text_block(draw, (120, 138), "CLUB", load_font(FONT_BLACK, 28), WHITE, anchor="mm")
    draw_wave(draw, 70, 168, 100, 28, WHITE)
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
