"""Tk-only image cache; pet modules never depend on a GUI instance."""
from PIL import Image, ImageTk

TRANS_KEY = "#ff00ff"


class SpriteCache:
    """Lazily converted frames for one pet. Drop the instance to release its Tk images."""

    def __init__(self, definition, master):
        self.definition = definition
        self.master = master
        self.cache = {}

    def get(self, state, frame, facing):
        frames = self.definition.animations[state].frames
        image = frames[frame % len(frames)]
        # Pets reuse frame objects across animations; identity keeps one Tk image per drawing.
        key = (id(image), facing >= 0)
        if key not in self.cache:
            if not key[1]:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            bg = Image.new("RGBA", image.size, TRANS_KEY)
            self.cache[key] = ImageTk.PhotoImage(Image.alpha_composite(bg, image).convert("RGB"), master=self.master)
        return self.cache[key]

    def clear(self):
        self.cache.clear()
