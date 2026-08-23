from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "public" / "icons"
ICON_SIZES = (16, 32, 48, 128)
CANVAS_SIZE = 1024


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    base = draw_icon(CANVAS_SIZE)
    for size in ICON_SIZES:
        resized = base.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(ICON_DIR / f"icon{size}.png")


def draw_icon(size: int) -> Image.Image:
    scale = size / CANVAS_SIZE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    draw_blue_marks(glow_draw, scale, alpha=100, width_boost=12)
    draw_pen(glow_draw, scale, alpha=100, width_boost=10)
    glow = glow.filter(ImageFilter.GaussianBlur(max(1, int(6 * scale))))
    image.alpha_composite(glow)

    draw = ImageDraw.Draw(image)
    draw_blue_marks(draw, scale)
    draw_pen(draw, scale)
    draw_notion_cube(draw, scale)
    return trim_and_fit(image, size)


def draw_blue_marks(
    draw: ImageDraw.ImageDraw,
    scale: float,
    *,
    alpha: int = 255,
    width_boost: int = 0,
) -> None:
    blue = (44, 99, 255, alpha)
    width = max(4, int((54 + width_boost) * scale))
    radius = width // 2

    for y, right in ((315, 340), (455, 315), (595, 230)):
        draw.rounded_rectangle(
            box(scale, 28, y - 27, right, y + 27),
            radius=radius,
            fill=blue,
        )


def draw_pen(
    draw: ImageDraw.ImageDraw,
    scale: float,
    *,
    alpha: int = 255,
    width_boost: int = 0,
) -> None:
    blue = (44, 99, 255, alpha)
    width = max(12, int((92 + width_boost) * scale))
    draw.line(
        [point(scale, 315, 735), point(scale, 500, 500)],
        fill=blue,
        width=width,
    )
    draw.line(
        [point(scale, 500, 500), point(scale, 560, 560)],
        fill=blue,
        width=width,
    )
    draw.polygon(
        [
            point(scale, 274, 814),
            point(scale, 315, 735),
            point(scale, 374, 790),
        ],
        fill=blue,
    )
    draw.polygon(
        [
            point(scale, 294, 782),
            point(scale, 320, 741),
            point(scale, 350, 770),
        ],
        fill=(255, 255, 255, alpha),
    )


def draw_notion_cube(draw: ImageDraw.ImageDraw, scale: float) -> None:
    black = (15, 16, 17, 255)
    near_black = (25, 26, 28, 255)
    white = (248, 249, 250, 255)
    width = max(4, int(34 * scale))

    front = box(scale, 610, 360, 1010, 815)
    left_face = [
        point(scale, 500, 220),
        point(scale, 610, 360),
        point(scale, 610, 815),
        point(scale, 500, 670),
    ]
    top_face = [
        point(scale, 500, 220),
        point(scale, 880, 205),
        point(scale, 1010, 360),
        point(scale, 610, 360),
    ]

    draw.polygon(left_face, fill=black)
    draw.polygon(top_face, fill=(255, 255, 255, 245))
    draw.line(
        [point(scale, 500, 220), point(scale, 880, 205), point(scale, 1010, 360)],
        fill=near_black,
        width=width,
        joint="curve",
    )
    draw.line(
        [point(scale, 500, 220), point(scale, 610, 360), point(scale, 610, 815), point(scale, 500, 670), point(scale, 500, 220)],
        fill=near_black,
        width=width,
        joint="curve",
    )
    draw.rounded_rectangle(
        front,
        radius=max(10, int(34 * scale)),
        fill=white,
        outline=near_black,
        width=width,
    )

    font = load_font(int(300 * scale))
    draw.text(
        point(scale, 710, 430),
        "N",
        fill=black,
        font=font,
        anchor="la",
        stroke_width=max(1, int(2 * scale)),
        stroke_fill=black,
    )


def trim_and_fit(image: Image.Image, size: int) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return image

    cropped = image.crop(bbox)
    target = int(size * 0.97)
    ratio = min(target / cropped.width, target / cropped.height)
    fitted = cropped.resize(
        (max(1, int(cropped.width * ratio)), max(1, int(cropped.height * ratio))),
        Image.Resampling.LANCZOS,
    )
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.alpha_composite(
        fitted,
        ((size - fitted.width) // 2, (size - fitted.height) // 2),
    )
    return output


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_name in ("timesbd.ttf", "georgiab.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def box(
    scale: float,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> tuple[int, int, int, int]:
    return (
        int(left * scale),
        int(top * scale),
        int(right * scale),
        int(bottom * scale),
    )


def point(scale: float, x: float, y: float) -> tuple[int, int]:
    return int(x * scale), int(y * scale)


if __name__ == "__main__":
    main()
