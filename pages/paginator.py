import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery

from consts.aliases import Button, KeyboardBuilder
from consts.buttons import BUTTON_OFF, PAGE_UP, PAGE_DOWN, PAGE_LEFT, PAGE_RIGHT

DEFAULT_MAX_ROWS = 8
DEFAULT_ROW_ITEMS = 1


@dataclass
class Paginator(ABC):
    items: list[Button] = field(default_factory=list)
    offset: int = 0

    max_rows: int = DEFAULT_MAX_ROWS
    row_items: int = DEFAULT_ROW_ITEMS

    def __post_init__(self):
        self._id = f'{self.__class__.__name__}-{uuid.uuid4()}'

        class PaginatorCallback(CallbackData, prefix=self._id):
            delta: int

        self.callback = PaginatorCallback

    def advance(self, query: CallbackQuery):
        data = self.callback.unpack(query.data)
        self.offset += data.delta

    @abstractmethod
    def page_size(self) -> int:
        pass

    @abstractmethod
    def to_builder(self, keyboard: KeyboardBuilder):
        pass


class VerticalPaginator(Paginator, ABC):
    def _up_enabled(self) -> bool:
        return self.offset > 0

    def _down_enabled(self) -> bool:
        items_fit = self.offset + (self.max_rows - self._up_enabled())
        return items_fit < len(self.items)

    def page_size(self) -> int:
        return self.max_rows - self._up_enabled() - self._down_enabled()

    def to_builder(self, keyboard: KeyboardBuilder):
        page_size = self.page_size()
        if self._up_enabled():
            keyboard.row(Button(text=f'{PAGE_UP} ({self.offset})', callback_data=self.callback(delta=-1).pack()))
        for item in self.items[self.offset:self.offset + page_size]:
            keyboard.row(item)
        if self._down_enabled():
            remaining = len(self.items) - self.offset - page_size
            keyboard.row(Button(text=f'{PAGE_DOWN} ({remaining})', callback_data=self.callback(delta=1).pack()))


class HorizontalPaginator(Paginator, ABC):
    def page_size(self) -> int:
        return self.max_rows - 1

    def _left_enabled(self) -> bool:
        return self.offset > 0

    def _right_enabled(self):
        return self.offset + self.page_size() < len(self.items)

    def to_builder(self, keyboard: KeyboardBuilder):
        page_size = self.page_size()
        for item in self.items[self.offset:self.offset + page_size]:
            keyboard.row(item)

        left = (self.offset + page_size - 1) // page_size
        right = (len(self.items) - self.offset - 1) // page_size
        row = [
            Button(text=f'{PAGE_LEFT} ({left})', callback_data=self.callback(delta=-page_size).pack()),
            Button(text=f'{PAGE_RIGHT} ({right})', callback_data=self.callback(delta=page_size).pack())
        ]
        if not self._left_enabled():
            row[0] = Button(text=BUTTON_OFF, callback_data=self.callback(delta=0).pack())
        if not self._right_enabled():
            row[1] = Button(text=BUTTON_OFF, callback_data=self.callback(delta=0).pack())
        keyboard.row(*row)
