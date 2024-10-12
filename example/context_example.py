import asyncio
import os
from dataclasses import dataclass

from aiogram import Bot, Router, Dispatcher
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.utils.formatting import Text, Bold, as_line

from tgutils.consts.aliases import KeyboardBuilder, Button
from tgutils.consts.buttons import MENU_CLOSE, MENU_UP
from tgutils.context.context import Context
from tgutils.context.context import Response

bot = Bot(os.getenv('BOT_TOKEN'))
router = Router()


@dataclass
class DefaultContext(Context):
    name: str = 'Anonymous'


class DefaultState(StatesGroup):
    MAIN = State()
    NAME = State()


@router.message(Command('start'))
@DefaultContext.entry_point
async def handle_start(ctx: DefaultContext, message: Message):
    # ctx.set_default(ctx.senders.EDIT)
    await ctx.advance(DefaultState.MAIN, message.reply, cause=message)


class NameChangeCallback(CallbackData, prefix='change-name'):
    pass


@DefaultContext.register(DefaultState.MAIN)
def main_menu(ctx: DefaultContext) -> Response:
    lines = [
        Text('You are ', Bold(ctx.name)),
        '',
        'What do you want to do?'
    ]

    keyboard = KeyboardBuilder()
    keyboard.row(Button(text='Change your name', callback_data=NameChangeCallback().pack()))
    keyboard.row(ctx.menu_button(ctx.Action.FINISH))

    return Response(
        text=Text(*map(as_line, lines)),
        markup=keyboard.as_markup()
    )


@router.callback_query(DefaultState.MAIN, NameChangeCallback.filter())
@DefaultContext.inject
async def handle_name_change(ctx: DefaultContext, query: CallbackQuery):
    await query.answer('Ok')
    await ctx.advance(DefaultState.NAME)


@DefaultContext.register(DefaultState.NAME)
def name_menu(ctx: DefaultContext) -> Response:
    keyboard = KeyboardBuilder()
    keyboard.row(ctx.menu_button(ctx.Action.BACK), ctx.menu_button(ctx.Action.FINISH))

    return Response(
        text='Please input your name',
        markup=keyboard.as_markup()
    )


@router.message(DefaultState.NAME)
@DefaultContext.inject
async def handle_new_name(ctx: DefaultContext, message: Message):
    ctx.name = message.text
    await message.delete()
    await ctx.back()


DefaultContext.prepare(router)
dispatcher = Dispatcher()
dispatcher.include_router(router)
asyncio.run(dispatcher.start_polling(bot))
