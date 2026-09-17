from dataclasses import replace
import unittest
from desktop_pet.pets.base import CANVAS_SIZE, REQUIRED_STATES
from desktop_pet.pets.registry import load_pets
from desktop_pet.behavior import PetBehavior
from tools.preview_pet import build_sheet


class PetContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pets = load_pets()

    def test_every_pet_obeys_shared_contract(self):
        for pet in self.pets.values():
            with self.subTest(pet=pet.id):
                self.assertIs(pet.validate(), pet)
                self.assertTrue(REQUIRED_STATES <= pet.animations.keys())
                for animation in pet.animations.values():
                    self.assertTrue(all(frame.size == CANVAS_SIZE for frame in animation.frames))

    def test_walks_and_menu_actions_have_animation(self):
        for pet in self.pets.values():
            for state in ("walk", *pet.actions):
                with self.subTest(pet=pet.id, state=state):
                    frames = pet.animations[state].frames
                    self.assertGreater(len({frame.tobytes() for frame in frames}), 1)

    def test_behavior_can_play_every_registered_state(self):
        for pet in self.pets.values():
            behavior = PetBehavior(pet)
            for state, animation in pet.animations.items():
                behavior.enter(state)
                for _ in range(len(animation.frames)+1):
                    self.assertLess(behavior.frame_index(), len(animation.frames))
                    behavior.advance(animation.frame_seconds)

    def test_grounded_poses_stand_on_the_bottom_row(self):
        # Every pet shares one floor line: feet flush with the frame bottom, nothing clipped at the sides.
        for pet in self.pets.values():
            for state in ("idle", "sit", "look", "walk", "alert"):
                for index, frame in enumerate(pet.animations[state].frames):
                    with self.subTest(pet=pet.id, state=state, frame=index):
                        left, _top, right, bottom = frame.getbbox()
                        self.assertEqual(bottom, CANVAS_SIZE[1])
                        self.assertGreater(left, 0)
                        self.assertLess(right, CANVAS_SIZE[0])

    def test_contract_does_not_depend_on_logical_art_grid(self):
        pet = next(iter(self.pets.values()))
        changed = dict(pet.animations)
        animation = changed["idle"]
        frame = animation.frames[0].copy()
        frame.putpixel((1, 1), (20, 30, 40, 255))  # A one-pixel detail is valid.
        changed["idle"] = replace(animation, frames=(frame,))
        replace(pet, animations=changed).validate()

    def test_preview_works_without_registration_or_tk(self):
        pet = replace(next(iter(self.pets.values())), id="unregistered_pet")
        image = build_sheet(pet)
        self.assertEqual(image.mode, "RGB")
        self.assertGreater(image.width, CANVAS_SIZE[0]*2)

    def test_missing_required_animation_rejected(self):
        pet = next(iter(self.pets.values()))
        animations = dict(pet.animations)
        del animations["fall"]
        with self.assertRaises(ValueError):
            replace(pet, animations=animations).validate()
