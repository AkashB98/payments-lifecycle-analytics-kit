"""Lifecycle state machine: initiated -> authorized -> settled, or fail/retry."""

ALLOWED_TRANSITIONS = {
    "initiated": {"authorized", "failed"},
    "authorized": {"settled", "failed"},
    "failed": {"retry_scheduled", "failed_permanent", "written_off"},
    "retry_scheduled": {"initiated"},
    "settled": set(),
    "failed_permanent": set(),
    "written_off": set(),
}

TERMINAL_STATES = {"settled", "failed_permanent", "written_off"}
ALL_STATES = set(ALLOWED_TRANSITIONS.keys())

class IllegalTransitionError(ValueError):
    pass

def is_allowed(current, nxt):
    return nxt in ALLOWED_TRANSITIONS.get(current, set())

def transition(current, nxt):
    if current not in ALLOWED_TRANSITIONS:
        raise IllegalTransitionError(f"unknown state: {current}")
    if nxt not in ALLOWED_TRANSITIONS[current]:
        raise IllegalTransitionError(f"illegal transition: {current} -> {nxt}")
    return nxt

class LifecycleMachine:
    def __init__(self, initial="initiated"):
        if initial not in ALL_STATES:
            raise IllegalTransitionError(f"unknown initial state: {initial}")
        self.state = initial
        self.history = [initial]

    def move(self, nxt):
        self.state = transition(self.state, nxt)
        self.history.append(self.state)
        return self.state

    @property
    def is_terminal(self):
        return self.state in TERMINAL_STATES
