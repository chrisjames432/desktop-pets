"""Species-independent animation timing and calm spontaneous behavior."""
import random


class PetBehavior:
    def __init__(self, definition, rng=None):
        self.definition = definition
        self.rng = rng or random.Random()
        self.clock = 0.0
        self.last_trick = -float("inf")
        self.last_used = {}
        self.enter("idle")

    def enter(self, state, duration=None):
        if state not in self.definition.animations:
            raise ValueError("Unknown animation: " + state)
        animation = self.definition.animations[state]
        self.state = state
        self.elapsed = 0.0
        self.duration = animation.duration if duration is None else duration
        if animation.label:
            self.last_used[state] = self.clock
            self.last_trick = self.clock

    def advance(self, dt):
        self.clock += dt
        self.elapsed += dt

    def rest(self):
        p = self.definition.personality
        candidates = [(key, animation) for key, animation in self.definition.animations.items()
                      if animation.weight > 0 and self.clock - self.last_used.get(key, -float("inf")) >= animation.cooldown]
        if candidates and self.clock - self.last_trick >= p.trick_gap and self.rng.random() < p.trick_chance:
            state = self.rng.choices([key for key, _ in candidates], [a.weight for _, a in candidates])[0]
            self.enter(state)
        else:
            self.enter(self.rng.choice(("idle", "sit", "look")), self.rng.uniform(p.rest_min, p.rest_max))

    def next(self, roam, at_destination, blocked=False):
        next_state = self.definition.animations[self.state].next_state
        if next_state and not blocked:
            self.enter(next_state)
        elif roam and not blocked and not at_destination and self.rng.random() < self.definition.personality.roam_chance:
            self.enter("walk", self.rng.uniform(5, 12))
        else:
            self.rest()

    def frame_index(self):
        animation = self.definition.animations[self.state]
        return int(self.elapsed / animation.frame_seconds) % len(animation.frames)
