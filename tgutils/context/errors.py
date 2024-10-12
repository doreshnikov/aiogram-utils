from abc import ABC

from aiogram.fsm.state import State


class ContextException(Exception, ABC):
    pass


class EmptyContextError(ContextException):
    def __init__(self):
        super().__init__(f'Context used before the entry point or after the context has finished')


class ScopeError(ContextException):
    def __init__(self):
        super().__init__(f'Context can only be called from context-injected handler')


class NoResponderFoundError(ContextException):
    def __init__(self, state: State):
        super().__init__(f'No responder found for state {state}')


class UnboundContextError(ContextException):
    def __init__(self):
        super().__init__('Context was not registered with any router')


class HistoricalStateNotFound(ContextException):
    def __init__(self, state: State):
        super().__init__(f'State {state} was not found in history during backoff')  # noqa E713
