from __future__ import annotations

import colorsys
import json
import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFile

try:
    import oxipng
except ImportError:  # pragma: no cover - optional compression dependency
    oxipng = None


ROOT = Path(__file__).resolve().parent
SPLASH_DIR = ROOT / "splash"
ELEMENTS_DIR = ROOT / "elements"
RESULT_DIR = ROOT / "result"
SETTINGS_PATH = ROOT / "settings.json"
CANVAS_SIZE = (619, 617)
CANVAS_CENTER = (CANVAS_SIZE[0] / 2, CANVAS_SIZE[1] / 2)
ELEMENT_SCALE = 0.5
ImageFile.LOAD_TRUNCATED_IMAGES = True

ELEMENT_MOTION = [
    {"angle": -120, "distance": 154, "speed": 1.18, "rotate": 40, "offset": (-6, 4), "lift": 4},
    {"angle": -104, "distance": 168, "speed": 1.05, "rotate": 20, "offset": (-3, -2), "lift": 34},
    {"angle": -90, "distance": 112, "speed": 0.96, "rotate": 0, "offset": (2, 1), "lift": 0},
    {"angle": -76, "distance": 170, "speed": 1.1, "rotate": -20, "offset": (5, -3), "lift": 34},
    {"angle": -60, "distance": 158, "speed": 1.24, "rotate": -40, "offset": (7, 3), "lift": 4},
]


def parse_hex_color(value: str) -> tuple[int, int, int]:
    color = value.strip().lstrip("#")
    if len(color) == 3:
        color = "".join(part * 2 for part in color)
    if len(color) != 6:
        raise ValueError(f"Unsupported color value: {value}")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))


def parse_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("settings.json must include a non-empty name")
    return name


def parse_dark(value: object) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError("settings.json dark must be true or false")
    return value


def load_rgba(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            return image.convert("RGBA")
    except OSError as exc:
        raise OSError(f"Could not read PNG image {path}: {exc}") from exc


def circular_average_hue(hues: Iterable[float]) -> float:
    x = 0.0
    y = 0.0
    count = 0

    for hue in hues:
        radians = math.radians(hue)
        x += math.cos(radians)
        y += math.sin(radians)
        count += 1

    if count == 0:
        return 0.0

    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def detect_source_hue(paths: list[Path]) -> float:
    hues: list[float] = []

    for path in paths:
        image = load_rgba(path)
        for red, green, blue, alpha in image.getdata():
            if alpha <= 10:
                continue

            hue, saturation, value = colorsys.rgb_to_hsv(
                red / 255.0,
                green / 255.0,
                blue / 255.0,
            )
            if saturation > 0.08 and value > 0.2:
                hues.append(hue * 360.0)

    return circular_average_hue(hues)


def hue_rotate_frame(image: Image.Image, hue_delta: float) -> Image.Image:
    image = image.convert("RGBA")
    pixels = []

    for red, green, blue, alpha in image.getdata():
        if alpha == 0:
            pixels.append((red, green, blue, alpha))
            continue

        hue, saturation, value = colorsys.rgb_to_hsv(
            red / 255.0,
            green / 255.0,
            blue / 255.0,
        )

        if saturation > 0.02:
            hue = ((hue * 360.0 + hue_delta) % 360.0) / 360.0

        out_red, out_green, out_blue = colorsys.hsv_to_rgb(hue, saturation, value)
        pixels.append(
            (
                round(out_red * 255),
                round(out_green * 255),
                round(out_blue * 255),
                alpha,
            )
        )

    result = Image.new("RGBA", image.size)
    result.putdata(pixels)
    return result


def apply_dark_splash(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    pixels = []

    for red, green, blue, alpha in image.getdata():
        if alpha == 0:
            pixels.append((red, green, blue, alpha))
            continue

        hue, saturation, value = colorsys.rgb_to_hsv(
            red / 255.0,
            green / 255.0,
            blue / 255.0,
        )
        saturation = min(1.0, saturation * 1.62)
        value = max(0.0, min(1.0, ((value - 0.34) * 2.75 + 0.34) * 0.42))

        out_red, out_green, out_blue = colorsys.hsv_to_rgb(hue, saturation, value)
        pixels.append(
            (
                round(out_red * 255),
                round(out_green * 255),
                round(out_blue * 255),
                alpha,
            )
        )

    result = Image.new("RGBA", image.size)
    result.putdata(pixels)
    return result


def ease_out_cubic(value: float) -> float:
    return 1.0 - pow(1.0 - value, 3)


def ease_in_out_sine(value: float) -> float:
    return -(math.cos(math.pi * value) - 1.0) / 2.0


def trim_alpha(image: Image.Image) -> Image.Image:
    bbox = image.getbbox()
    if not bbox:
        return image
    return image.crop(bbox)


def place_centered(canvas: Image.Image, image: Image.Image, center: tuple[float, float]) -> None:
    left = round(center[0] - image.width / 2)
    top = round(center[1] - image.height / 2)
    canvas.alpha_composite(image, (left, top))


def transform_element(
    image: Image.Image,
    progress: float,
    motion: dict[str, float],
) -> tuple[Image.Image, tuple[float, float]]:
    speed_progress = min(1.0, progress * motion["speed"])
    eased = ease_out_cubic(speed_progress)
    scale_eased = ease_in_out_sine(progress)

    angle = math.radians(motion["angle"])
    offset_x, offset_y = motion["offset"]
    start_center = (CANVAS_CENTER[0] + offset_x, CANVAS_SIZE[1] + 70 + offset_y)
    end_center = (
        start_center[0] + math.cos(angle) * motion["distance"],
        start_center[1] + math.sin(angle) * motion["distance"],
    )

    arc_lift = math.sin(math.pi * progress) * 18
    final_lift = (50 + motion["lift"]) * eased
    center = (
        start_center[0] + (end_center[0] - start_center[0]) * eased,
        start_center[1] + (end_center[1] - start_center[1]) * eased - arc_lift - final_lift,
    )

    scale = ELEMENT_SCALE * (1.0 + 0.1 * scale_eased)
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    transformed = image.resize((width, height), Image.Resampling.LANCZOS)

    rotation = motion["rotate"] * scale_eased
    transformed = transformed.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)

    if progress < 0.18:
        alpha_multiplier = progress / 0.18
        alpha = transformed.getchannel("A").point(
            lambda value: round(value * alpha_multiplier),
        )
        transformed.putalpha(alpha)

    return transformed, center


def save_png(image: Image.Image, output_path: Path) -> None:
    image.save(output_path, optimize=True, compress_level=9)

    if oxipng is None:
        return

    oxipng.optimize(
        output_path,
        level=4,
        optimize_alpha=True,
        strip=oxipng.StripChunks.safe(),
    )


def draw_elements(canvas: Image.Image, element_images: list[Image.Image], progress: float) -> None:
    if progress <= 0:
        return

    for index, element in enumerate(element_images):
        motion = ELEMENT_MOTION[index % len(ELEMENT_MOTION)]
        phase_delay = index * 0.018
        local_progress = min(1.0, max(0.0, (progress - phase_delay) / (1.0 - phase_delay)))
        transformed, center = transform_element(element, local_progress, motion)
        place_centered(canvas, transformed, center)


def main() -> None:
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    taste_name = parse_name(settings["name"])
    dark_splash = parse_dark(settings.get("dark"))
    target_rgb = parse_hex_color(settings["color"])
    target_hue = colorsys.rgb_to_hsv(
        target_rgb[0] / 255.0,
        target_rgb[1] / 255.0,
        target_rgb[2] / 255.0,
    )[0] * 360.0

    splash_paths = sorted(SPLASH_DIR.glob("*.png"))
    if not splash_paths:
        raise FileNotFoundError(f"No png frames found in {SPLASH_DIR}")

    element_paths = sorted(ELEMENTS_DIR.glob("*.png"))[:5]
    if len(element_paths) < 5:
        raise FileNotFoundError(f"Expected 5 png elements in {ELEMENTS_DIR}")

    element_images = [trim_alpha(load_rgba(path)) for path in element_paths]
    source_hue = detect_source_hue(splash_paths)
    hue_delta = target_hue - source_hue

    RESULT_DIR.mkdir(exist_ok=True)
    for stale_file in RESULT_DIR.glob("*.png"):
        stale_file.unlink()

    total_frames = len(splash_paths)

    for index, path in enumerate(splash_paths, start=1):
        canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
        progress = (index - 1) / max(total_frames - 1, 1)

        if index > 1:
            draw_elements(canvas, element_images, progress)
            frame = hue_rotate_frame(load_rgba(path), hue_delta)
            if dark_splash:
                frame = apply_dark_splash(frame)
            canvas.alpha_composite(frame, (0, 0))

        output_path = RESULT_DIR / f"taste-{taste_name}_{index:02d}.png"
        save_png(canvas, output_path)

    print(
        f"Generated {len(splash_paths)} frames with {len(element_images)} moving elements in {RESULT_DIR} "
        f"(source hue {source_hue:.2f} -> target hue {target_hue:.2f}, delta {hue_delta:.2f}, "
        f"dark={dark_splash})."
    )


if __name__ == "__main__":
    main()
