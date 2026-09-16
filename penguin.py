"""Penguin Pet compatibility entrypoint.

Runs Patches the Calico Cat Desktop Pet.
The original penguin implementation is safely backed up at:
  - C:\\Users\\Chris McDonough\\Desktop\\penguin\\penguin_original.py
  - C:\\Users\\Chris McDonough\\Desktop\\penguin_backup\\
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cat

if __name__ == "__main__":
    cat.attach_to_interactive_desktop()
    port = cat.start_server(cat.DEFAULT_PORT)
    pet = cat.CatPet()
    pet.mainloop()
