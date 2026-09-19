"""Deterministic variation (spec sec. 17): every 'random' choice in the factory comes from here, seeded by story_id + shot_id (+ a salt).
Same story + same seed -> identical film; a different seed -> controlled variation. Nothing else may call random without a seed from this module."""
import hashlib
import random


def rng(story_id, shot_id="", salt=""):
    return random.Random(hashlib.sha256(f"{story_id}|{shot_id}|{salt}".encode()).hexdigest())


def seed_int(story_id, shot_id="", salt=""):
    return int(hashlib.sha256(f"{story_id}|{shot_id}|{salt}".encode()).hexdigest()[:8], 16)


def pick(story_id, shot_id, salt, options):
    return rng(story_id, shot_id, salt).choice(list(options))
