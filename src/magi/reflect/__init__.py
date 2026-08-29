"""The slow loop: what the sessions themselves say about how the work went.

Read-only, and read from outside the project. A host's transcript is its own
private cache (design-v2 §9): it lives in the user's home, it rotates, four
hosts write four formats, and none of it is ours to edit. What MAGI takes from
it is what could not be recomputed later — which is why `reflect` writes what
it finds down instead of deriving it on demand (§12).
"""
