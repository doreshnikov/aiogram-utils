import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery

from ..consts.aliases import Button, KeyboardBuilder
from ..consts.buttons import BUTTON_OFF, PAGE_UP, PAGE_DOWN, PAGE_LEFT, PAGE_RIGHT, BUTTON_STUB

DEFAULT_MAX_ROWS = 8
DEFAULT_ROW_ITEMS = 1


@dataclass
class Paginator(ABC):
    items: list[Button] = field(default_factory=list)
    _offset: int = 0

    _max_rows: int = DEFAULT_MAX_ROWS
    _row_items: int = DEFAULT_ROW_ITEMS

    def __post_init__(self):
        self._id = f'{self.__class__.__name__}-{uuid.uuid4()}'

        class PaginatorCallback(CallbackData, prefix=self._id):
            delta: int

        self.callback = PaginatorCallback

    def advance(self, query: CallbackQuery):
        data = self.callback.unpack(query.data)
        self._offset += data.delta

    @abstractmethod
    def to_builder(self, keyboard: KeyboardBuilder):
        pass


class VerticalPaginator(Paginator, ABC):
    _STUB_BUTTON = Button(text=BUTTON_STUB)

    def __init__(self, max_rows: int, row_items: int, items: list | None = None, stub_incomplete_row: bool = True):
        if items is None:
            items = []
        super(Paginator, self).__init__(items, 0, max_rows, row_items)
        self.stub_incomplete_row = stub_incomplete_row

    def _up_enabled(self) -> bool:
        return self._offset > 0

    def _down_enabled(self) -> bool:
        items_fit = self._offset + (self._max_rows * self._row_items - self._up_enabled())
        return items_fit < len(self.items)

    def _content_rows(self) -> int:
        return self._max_rows - self._up_enabled() - self._down_enabled()

    def to_builder(self, keyboard: KeyboardBuilder):
        if self._up_enabled():
            keyboard.row(Button(
                text=f'{PAGE_UP} ({self._offset})',
                callback_data=self.callback(delta=-self._row_items).pack()
            ))

        for row in range(self._content_rows()):
            buttons = []
            for column in range(self._row_items):
                item_no = self._offset + row * self._row_items + column
                buttons.append(self.items[item_no] if item_no < len(self.items) else self._STUB_BUTTON)
            keyboard.row(*buttons)

        if self._down_enabled():
            remaining = len(self.items) - self._offset - self._content_rows() * self._row_items
            keyboard.row(Button(
                text=f'{PAGE_DOWN} ({remaining})',
                callback_data=self.callback(delta=self._row_items).pack()
            ))


class HorizontalPaginator(Paginator, ABC):
    def _page_size(self) -> int:
        return self._max_rows - 1

    def _left_enabled(self) -> bool:
        return self._offset > 0

    def _right_enabled(self):
        return self._offset + self._page_size() < len(self.items)

    def to_builder(self, keyboard: KeyboardBuilder):
        page_size = self._page_size()
        for item in self.items[self._offset:self._offset + page_size]:
            keyboard.row(item)

        left = (self._offset + page_size - 1) // page_size
        right = (len(self.items) - self._offset - 1) // page_size
        row = [
            Button(text=f'{PAGE_LEFT} ({left})', callback_data=self.callback(delta=-page_size).pack()),
            Button(text=f'{PAGE_RIGHT} ({right})', callback_data=self.callback(delta=page_size).pack())
        ]
        if not self._left_enabled():
            row[0] = Button(text=BUTTON_OFF, callback_data=self.callback(delta=0).pack())
        if not self._right_enabled():
            row[1] = Button(text=BUTTON_OFF, callback_data=self.callback(delta=0).pack())
        keyboard.row(*row)
