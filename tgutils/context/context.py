import inspect
import logging
import uuid
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Type

import aiogram.exceptions as tg_exc
from aiogram import Router
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message, CallbackQuery

from tgutils.consts.aliases import Button
from tgutils.consts.buttons import MENU_UP, MENU_CLOSE

from .errors import EmptyContextError, ScopeError, NoResponderFoundError, UnboundContextError, HistoricalStateNotFound
from .types import Response, Handler, Sender


@dataclass
class _ContextMenu:
    message: Message
    state: State
    is_new: bool
    cause: Message | None = None


class Context(ABC):
    Responder = Callable[['Context'], Response]

    _responders: dict[tuple[type, State], Responder] = {}
    _callback: dict[type, Type[CallbackData]] = {}

    def __init__(self):
        self._fsm: FSMContext | None = None
        self._states_stack: list[_ContextMenu] = []

        async def _edit(*args, **kwargs):
            try:
                return await self._menu.message.edit_text(*args, **kwargs)
            except tg_exc.TelegramBadRequest as e:
                logging.info(f'Bad request trying to edit message: {e}')

        async def _send(*args, **kwargs):
            return await self._menu.message.reply(*args, **kwargs)

        class SenderOption(Enum):
            EDIT: Sender = _edit
            NEW: Sender = _send

        self.senders = SenderOption
        self._default_sender = self.senders.NEW

    def set_default(self, sender: Sender):
        self._default_sender = sender

    def _ensure_stack(self) -> list[_ContextMenu]:
        if len(self._states_stack) == 0:
            raise EmptyContextError()
        return self._states_stack

    def _ensure_fsm(self) -> FSMContext:
        if self._fsm is None:
            raise ScopeError()
        return self._fsm

    @property
    def _menu(self) -> _ContextMenu:
        return self._ensure_stack()[-1]

    def _safe_state(self) -> State | None:
        if len(self._states_stack) == 0:
            return None
        return self._menu.state

    def _safe_message_id(self) -> int | None:
        if len(self._states_stack) == 0:
            return None
        return self._menu.message.message_id

    @classmethod
    def _id(cls) -> str:
        return cls.__name__

    @staticmethod
    def _resolve_kwargs(handler: Handler, kwargs: dict[str, object]):
        spec = inspect.getfullargspec(handler)
        params = {*spec.args, *spec.kwonlyargs}
        return {key: kwargs[key] for key in params if key in kwargs}

    @classmethod
    def _handler_wrapper(cls, ctx: 'Context', fsm: FSMContext, handler: Handler):
        # noinspection PyProtectedMember
        async def wrapper(*args, **kwargs):
            ctx._fsm = fsm
            result = await handler(ctx, *args, **cls._resolve_kwargs(handler, kwargs))
            ctx._fsm = None
            await fsm.update_data({cls._id(): ctx})
            return result

        return wrapper

    @classmethod
    def entry_point(cls, handler: Handler):
        async def wrapper(*args, **kwargs):
            fsm: FSMContext = kwargs['state']
            # noinspection PyArgumentList
            ctx = cls()
            Context.__init__(ctx)
            await fsm.update_data({cls._id(): ctx})
            return await cls._handler_wrapper(ctx, fsm, handler)(*args, **kwargs)

        return wrapper

    @classmethod
    def inject(cls, handler: Handler):
        async def wrapper(*args, **kwargs):
            fsm: FSMContext = kwargs['state']
            ctx = (await fsm.get_data()).get(cls._id())
            if ctx is None:
                raise EmptyContextError()
            return await cls._handler_wrapper(ctx, fsm, handler)(*args, **kwargs)

        return wrapper

    @classmethod
    def register(cls, trigger: State):
        key = (cls, trigger)
        if (key, trigger) in Context._responders:
            raise AttributeError(f'Duplicate {trigger} trigger for scenario class {cls.__name__}')

        def decorator(reply_builder: Context.Responder):
            Context._responders[key] = reply_builder
            return reply_builder

        return decorator

    async def _close_last_menu(self):
        while len(self._states_stack) > 0:
            menu = self._states_stack.pop()
            if not menu.is_new:
                continue
            await menu.message.delete()
            if menu.cause is not None:
                await menu.cause.delete()
        await self._fsm.set_state(self._safe_state())

    async def _cleanup(self):
        while len(self._states_stack) > 0:
            await self._close_last_menu()

    async def _fit_message(self, trigger: State, sender: Sender) -> Message:
        key = (self.__class__, trigger)
        responder = Context._responders.get(key)
        if responder is None:
            raise NoResponderFoundError(trigger)

        response = responder(self)
        return await sender(**response.as_kwargs())

    async def advance(self, new_state: State, sender: Sender | None = None, *, cause: Message | None = None):
        if sender is None:
            sender = self._default_sender
        if self._safe_state() == new_state:
            sender = self.senders.EDIT

        await self._ensure_fsm().set_state(new_state)
        msg = await self._fit_message(new_state, sender)
        if self._safe_state() != new_state:
            is_new = self._safe_message_id() != msg.message_id
            self._states_stack.append(_ContextMenu(msg, new_state, is_new, cause))

    async def back(self):
        menu = self._ensure_stack().pop()
        new_state = self._safe_state()
        await self._fsm.set_state(new_state)
        if new_state is None:
            return await self._cleanup()

        if menu.is_new:
            await menu.message.delete()
        # noinspection PyTypeChecker
        await self._fit_message(new_state, self.senders.EDIT)

    async def backoff_until(self, state: State):
        while self._safe_state() != state:
            await self.back()
            if self._safe_state() is None:
                raise HistoricalStateNotFound(state)

    async def finish(self):
        await self._cleanup()

    class Action(Enum):
        BACK = MENU_UP
        FINISH = MENU_CLOSE

    @classmethod
    def prepare(cls, router: Router):
        class MenuCallback(CallbackData, prefix=f'menu-{uuid.uuid4()}'):
            action: cls.Action

        Context._callback[cls] = MenuCallback

        @router.callback_query(MenuCallback.filter())
        @cls.inject
        async def handle_callback(ctx: Context, query: CallbackQuery):
            data = MenuCallback.unpack(query.data)
            # formatter:off
            match data.action:
                case cls.Action.BACK: await ctx.back()
                case cls.Action.FINISH: await ctx.finish()
            # formatter:on

        logging.info(f'Registered context {cls} for router {router}')

    @classmethod
    def menu_button(cls, action: 'Context.Action') -> Button:
        if cls not in Context._callback:
            raise UnboundContextError()

        return Button(
            text=action.value,
            callback_data=Context._callback[cls](action=action).pack(),
        )
