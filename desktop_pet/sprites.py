"""Tk-only image cache; pet modules never depend on a GUI instance."""
from PIL import Image, ImageTk

TRANS_KEY = "#ff00ff"


class SpriteCache:
    """Lazily converted frames for one pet. Drop the instance to release its Tk images."""

    def __init__(self, definition, master):
        self.definition = definition
        self.master = master
        self.cache = {}
        self.shapes = {}

    def _frame(self, state, frame, facing):
        frames = self.definition.animations[state].frames
        image = frames[frame % len(frames)]
        # Pets reuse frame objects across animations; identity keeps one Tk image per drawing.
        return (id(image), facing >= 0), image

    @staticmethod
    def _facing(image, right):
        return image if right else image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    def get(self, state, frame, facing):
        key, image = self._frame(state, frame, facing)
        if key not in self.cache:
            image = self._facing(image, key[1])
            bg = Image.new("RGBA", image.size, TRANS_KEY)
            self.cache[key] = ImageTk.PhotoImage(Image.alpha_composite(bg, image).convert("RGB"), master=self.master)
        return self.cache[key]

    def shape(self, state, frame, facing):
        """The frame's opaque pixels as (left, top, right, bottom) runs, top to bottom.

        Shapes a window that cannot use the transparent colour (see DesktopLayer).
        """
        key, image = self._frame(state, frame, facing)
        if key not in self.shapes:
            image = self._facing(image, key[1])
            width, height = image.size
            alpha = image.getchannel("A").tobytes()
            runs = []
            for y in range(height):
                row, x = alpha[y * width:(y + 1) * width], 0
                while x < width:
                    if row[x]:
                        start = x
                        while x < width and row[x]:
                            x += 1
                        runs.append((start, y, x, y + 1))
                    else:
                        x += 1
            self.shapes[key] = tuple(runs)
        return self.shapes[key]
