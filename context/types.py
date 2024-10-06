from dataclasses import dataclass
from typing import Callable, Awaitable

from aiogram.types import Message
from aiogram.utils.formatting import Text

from consts.aliases import Keyboard


@dataclass
class Response:
    text: str | Text
    markup: Keyboard | None = None

    def as_kwargs(self) -> dict[str, object]:
        kwargs = {'reply_markup': self.markup}
        if isinstance(self.text, Text):
            return kwargs | self.text.as_kwargs()
        return kwargs | {'text': self.text}


Handler = Callable[..., Awaitable[object]]
Sender = Callable[..., Awaitable[Message]]
