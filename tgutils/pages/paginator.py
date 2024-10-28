from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Type, TypeVar, Generic

from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery

from ..consts.aliases import Button, KeyboardBuilder
from ..consts.buttons import DISABLED, PAGE_UP, PAGE_DOWN, PAGE_LEFT, PAGE_RIGHT, STUB

DEFAULT_MAX_ROWS = 8
DEFAULT_ROW_ITEMS = 1

_paginator_callbacks: dict[str, Type[CallbackData]] = {}
PaginatorType = TypeVar('PaginatorType')

@dataclass
class Paginator(ABC, Generic[PaginatorType]):
    items: list[PaginatorType] = field(default_factory=list)
    _offset: int = 0

    _max_rows: int = DEFAULT_MAX_ROWS
    _row_items: int = DEFAULT_ROW_ITEMS

    @classmethod
    def callback(cls) -> Type[CallbackData]:
        name = f'{cls.__name__.lower()}'
        if name in _paginator_callbacks:
            return _paginator_callbacks[name]

        class PaginatorCallback(CallbackData, prefix=name):
            delta: int

        _paginator_callbacks[name] = PaginatorCallback
        return PaginatorCallback

    def advance(self, query: CallbackQuery):
        data = self.callback().unpack(query.data)
        self._offset += data.delta

    @abstractmethod
    def to_builder(self, keyboard: KeyboardBuilder):
        pass

    @abstractmethod
    def make_button(self, item: PaginatorType) -> Button:
        pass


class VerticalPaginator(Paginator[PaginatorType], ABC):
    _STUB_BUTTON = Button(text=STUB, callback_data='ignore-me')

    def __init__(self, max_rows: int, row_items: int, items: list | None = None, stub_incomplete_row: bool = True):
        if items is None:
            items = []
        self.items = items
        self._max_rows = max_rows
        self._row_items = row_items
        self.stub_incomplete_row = stub_incomplete_row

    @property
    def _content_rows(self) -> int:
        return self._max_rows - 2

    @property
    def _up_enabled(self) -> bool:
        return self._offset > 0

    @property
    def _down_enabled(self) -> bool:
        items_fit = self._offset + self._content_rows * self._row_items
        return items_fit < len(self.items)

    def to_builder(self, keyboard: KeyboardBuilder):
        if self._up_enabled:
            keyboard.row(Button(
                text=f'{PAGE_UP} ({self._offset})',
                callback_data=self.callback()(delta=-self._row_items).pack()
            ))

        used_items = 0
        for row in range(self._content_rows):
            if self._offset + row * self._row_items >= len(self.items):
                break

            buttons = []
            for column in range(self._row_items):
                item_no = self._offset + row * self._row_items + column
                if item_no < len(self.items):
                    buttons.append(self.make_button(self.items[item_no]))
                    used_items += 1
                elif self.stub_incomplete_row:
                    buttons.append(self._STUB_BUTTON)

            keyboard.row(*buttons)

        if self._down_enabled:
            remaining = len(self.items) - self._offset - used_items
            keyboard.row(Button(
                text=f'{PAGE_DOWN} ({remaining})',
                callback_data=self.callback()(delta=self._row_items).pack()
            ))


class HorizontalPaginator(Paginator[PaginatorType], ABC):
    def __init__(self, max_rows: int, items: list | None = None):
        if items is None:
            items = []
        self.items = items
        self._max_rows = max_rows
        self._row_items = 1

    @property
    def _page_size(self) -> int:
        return self._max_rows - 1

    @property
    def _left_enabled(self) -> bool:
        return self._offset > 0

    @property
    def _right_enabled(self):
        return self._offset + self._page_size < len(self.items)

    def to_builder(self, keyboard: KeyboardBuilder):
        page_size = self._page_size
        for item in self.items[self._offset:self._offset + page_size]:
            keyboard.row(self.make_button(item))

        left = (self._offset + page_size - 1) // page_size
        right = (len(self.items) - self._offset - 1) // page_size
        row = [
            Button(text=f'{PAGE_LEFT} ({left})', callback_data=self.callback()(delta=-page_size).pack()),
            Button(text=f'{PAGE_RIGHT} ({right})', callback_data=self.callback()(delta=page_size).pack())
        ]
        has_sides = 2
        if not self._left_enabled:
            row[0] = Button(text=DISABLED, callback_data=self.callback()(delta=0).pack())
            has_sides -= 1
        if not self._right_enabled:
            row[1] = Button(text=DISABLED, callback_data=self.callback()(delta=0).pack())
            has_sides -= 1

        if has_sides > 0:
            keyboard.row(*row)
