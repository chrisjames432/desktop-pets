"""Headless contact sheet: every frame, both directions, light/dark backgrounds."""
import argparse
import importlib
from pathlib import Path
import re
import sys
from PIL import Image, ImageDraw

# Running a script under tools/ must still resolve the source package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def build_sheet(pet, scale=1):
    pet.validate()
    width, height = next(iter(pet.animations.values())).frames[0].size
    width, height = width*scale, height*scale
    label_width, pad, header = 180, 8, 54
    cell_width, row_height = width*2+pad*3, height*2+52
    columns = max(len(animation.frames) for animation in pet.animations.values())
    sheet = Image.new("RGB", (label_width+columns*cell_width+pad, header+len(pet.animations)*row_height), "#d1d0cd")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), f"{pet.name} ({pet.id}) | {scale}x nearest-neighbor", fill="#202020")
    draw.text((12, 28), "Each numbered frame: right-facing above, left-facing below; light and dark tiles. Bottom line = canvas ground.", fill="#202020")
    for row, (state, animation) in enumerate(pet.animations.items()):
        top = header+row*row_height
        draw.text((12, top+12), state, fill="#202020")
        draw.text((12, top+30), f"{len(animation.frames)} frames", fill="#202020")
        draw.text((12, top+46), f"{animation.frame_seconds:g}s / frame", fill="#202020")
        for index, frame in enumerate(animation.frames):
            left = label_width+index*cell_width
            draw.text((left+pad, top+2), str(index), fill="#202020")
            for direction in (0, 1):
                image = frame if direction == 0 else frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if scale != 1:
                    image = image.resize((width, height), Image.Resampling.NEAREST)
                for background, color in enumerate(("#f5efe4", "#252c36")):
                    x, y = left+pad+background*(width+pad), top+20+direction*(height+12)
                    tile = Image.new("RGBA", (width, height), color)
                    tile.alpha_composite(image)
                    sheet.paste(tile.convert("RGB"), (x, y))
                    draw.line((x, y+height, x+width-1, y+height), fill="#958873", width=1)
    return sheet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pet_id")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scale", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.pet_id):
        parser.error("pet_id must be lowercase snake_case")
    module = importlib.import_module("desktop_pet.pets." + args.pet_id)
    pet = module.build_pet().validate()
    if pet.id != args.pet_id:
        parser.error("module name and PetDefinition.id must match")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_sheet(pet, args.scale).save(args.output)
    print(f"Validated {pet.id}: {len(pet.animations)} animations. Preview: {args.output}")


if __name__ == "__main__":
    main()
