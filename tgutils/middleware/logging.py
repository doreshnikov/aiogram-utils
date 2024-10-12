import logging
import sys
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject

sys.setrecursionlimit(1000)


class LoggingMiddleware(BaseMiddleware):
    def __init__(self, *, ignore_keys: set[str] | None = None, ensure_ascii: bool = False):
        self.ignore_keys = ignore_keys if ignore_keys is not None else set()
        self.ensure_ascii = ensure_ascii

    @staticmethod
    def _fix_utf8(s: str) -> str:
        return s if s.isascii() else str(s.encode('utf-8'))[2:-1]

    def _simplify_object(self, event: Any, ) -> Any:
        try:
            if isinstance(event, TelegramObject):
                event = event.model_dump()

            if isinstance(event, list):
                return [self._simplify_object(item) for item in event]
            elif isinstance(event, dict):
                return {
                    self._simplify_object(key): self._simplify_object(value)
                    for key, value in event.items()
                    if value is not None and key not in self.ignore_keys
                }
            elif isinstance(event, str):
                return self._fix_utf8(event) if self.ensure_ascii else event
            elif hasattr(event, '__dict__'):
                return self._simplify_object(event.__dict__)

            return event
        except ValueError | AttributeError:
            return '<<NON-MARSHALLING>>'

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        logging.debug(f'Event: {self._simplify_object(event)}')

        context: FSMContext | None = data.get('state')
        if context is not None:
            state = await context.get_state()
            logging.debug(f'State: {state}')

        return await handler(event, data)

    @staticmethod
    def inject(dispatcher: Dispatcher):
        dispatcher.update.outer_middleware(LoggingMiddleware())
