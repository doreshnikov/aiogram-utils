import json
import logging
import re
import sys
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject

sys.setrecursionlimit(1000)

ALLOW_ALL_FIELD_RULES = {'.*': True}

DEFAULT_FIELD_RULES = {
    r'.*\.date': False,
    r'.*\.first_name': False,
    r'.*\.last_name': False,
    r'.*\.language_code': False,
    r'.*\.is_bot': False,
    r'.*\.is_premium': False,
    r'.*\.message\.reply_to_message': False,
    r'.*\.message\.entities': False,
    r'.*\.callback_query\.message': False,
    r'.*': True
}


class LoggingMiddleware(BaseMiddleware):
    def __init__(self, *, field_rules: dict[str, bool] | None = None, ensure_ascii: bool = False):
        super().__init__()

        if field_rules is None:
            field_rules = DEFAULT_FIELD_RULES
        self.field_rules = {re.compile(pattern): verdict for pattern, verdict in field_rules.items()}

        self.ensure_ascii = ensure_ascii

    def _allow_path(self, path: str) -> bool:
        for pattern, verdict in self.field_rules.items():
            if re.fullmatch(pattern, path):
                return verdict
        return False

    def _ensure_str(self, s: Any) -> str:
        if not isinstance(s, str):
            s = str(s)
        if not self.ensure_ascii or s.isascii():
            return s
        return str(s.encode('utf-8'))[2:-1]

    def _simplify_object(self, event: Any, path: str) -> Any:
        if not self._allow_path(path):
            return None

        try:
            if isinstance(event, TelegramObject):
                event = event.model_dump()

            if isinstance(event, list):
                next_path = f'{path}[]'
                result = []
                for item in event:
                    if (fmt := self._simplify_object(item, next_path)) is not None:
                        result.append(fmt)
                return result

            if isinstance(event, str):
                return self._ensure_str(event)

            if hasattr(event, '__dict__'):
                event = event.__dict__

            if isinstance(event, dict):
                result = {}
                for key, value in event.items():
                    if (fmt := self._simplify_object(value, f'{path}.{key}')) is not None:
                        result[self._ensure_str(key)] = fmt
                return result

            return event
        except ValueError | AttributeError:
            return '<<NON-MARSHALLING>>'

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        event_data = json.dumps(self._simplify_object(event, ''), ensure_ascii=False, indent=2)
        logging.debug(f'Event: {event_data}')

        context: FSMContext | None = data.get('state')
        if context is not None:
            state = await context.get_state()
            logging.debug(f'State: {state}')

        return await handler(event, data)
