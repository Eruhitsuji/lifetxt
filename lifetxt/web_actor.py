"""Request-scoped authenticated actor for ordinary Web Native History writes."""

from contextvars import ContextVar


_CURRENT_WEB_ACTOR = ContextVar("lifetxt_standard_web_actor", default=None)


def activate_web_actor(actor):
    """Set an actor from authenticated server request state, never payload data."""
    return _CURRENT_WEB_ACTOR.set(str(actor) if actor not in (None, "") else None)


def reset_web_actor(token):
    _CURRENT_WEB_ACTOR.reset(token)


def current_web_actor():
    return _CURRENT_WEB_ACTOR.get()
