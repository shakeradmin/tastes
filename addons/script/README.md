# Taste Splash Generator

Generates recolored splash frames from `splash/*.png` into `result/*.png` and
adds a universal 5-object fly-out animation from `elements/*.png`.

```bash
python3 -m pip install -r requirements.txt
python3 generate.py
```

or:

```bash
yarn setup
yarn dev
```

The script reads `settings.json`, creates a `619 x 617` transparent canvas for
each frame, hue-rotates the visible purple pixels toward `settings.color`, adds
the first 5 transparent PNG objects from `elements`, and saves the 20 generated
PNG files in `result`.

Set `"dark": true` in `settings.json` to render the splash color darker and
with stronger contrast.

Frame 1 is intentionally empty. From frame 2 onward, objects start near the
bottom-center splash origin and smoothly fly outward with small rotation and
scale changes. Moving elements are rendered at 50% of their source size. The
animation is content-agnostic, so `elements` can contain
berries, fruit, powders, icons, or other transparent PNG objects.

Generated PNGs are saved with Pillow compression and additionally optimized
with `pyoxipng` when installed.
