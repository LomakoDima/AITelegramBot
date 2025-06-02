import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import os
from dotenv import load_dotenv
from logic import ChatGPTHandler, ImageGenerator, UserManager

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Необходимо установить BOT_TOKEN и OPENAI_API_KEY в .env файле")

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

chatgpt_handler = ChatGPTHandler(OPENAI_API_KEY)
image_generator = ImageGenerator(OPENAI_API_KEY)
user_manager = UserManager()

class BotStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_image_prompt = State()

def get_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Чат с ИИ", callback_data="chat_ai")],
        [InlineKeyboardButton(text="🎨 Генерация изображений", callback_data="generate_image")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🔄 Очистить историю", callback_data="clear_history")]
    ])
    return keyboard

@dp.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    user_manager.register_user(user_id, username)

    welcome_text = (
        f"👋 Привет, {username}!\n\n"
        "Я многофункциональный ИИ-бот с возможностями:\n"
        "💬 Общение с ChatGPT\n"
        "🎨 Генерация изображений с помощью DALL-E\n\n"
        "Выберите действие из меню ниже:"
    )

    await message.answer(welcome_text, reply_markup=get_main_menu())
    await state.clear()

@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = (
        "🤖 <b>Доступные команды:</b>\n\n"
        "/start - Главное меню\n"
        "/help - Помощь\n"
        "/stats - Статистика использования\n"
        "/clear - Очистить историю чата\n\n"
        "<b>Возможности бота:</b>\n"
        "💬 Общение с ChatGPT - задавайте любые вопросы\n"
        "🎨 Генерация изображений - создавайте картинки по описанию\n"
        "📊 Статистика - отслеживание использования\n"
        "🔄 Очистка истории - начать диалог заново"
    )
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_main_menu())

@dp.callback_query(lambda c: c.data == "chat_ai")
async def chat_ai_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()

    await callback_query.message.edit_text(
        "💬 <b>Режим чата с ИИ активирован</b>\n\n"
        "Напишите ваше сообщение, и я отвечу с помощью ChatGPT.\n"
        "Для возврата в меню используйте /start",
        parse_mode="HTML"
    )

    await state.set_state(BotStates.waiting_for_message)

@dp.callback_query(lambda c: c.data == "generate_image")
async def generate_image_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()

    await callback_query.message.edit_text(
        "🎨 <b>Режим генерации изображений активирован</b>\n\n"
        "Опишите изображение, которое хотите создать.\n"
        "Например: 'кот в космосе среди звезд'\n\n"
        "Для возврата в меню используйте /start",
        parse_mode="HTML"
    )

    await state.set_state(BotStates.waiting_for_image_prompt)

@dp.callback_query(lambda c: c.data == "stats")
async def stats_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()

    user_id = callback_query.from_user.id
    stats = user_manager.get_user_stats(user_id)

    stats_text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"💬 Сообщений в чате: {stats['messages_sent']}\n"
        f"🎨 Изображений создано: {stats['images_generated']}\n"
        f"📅 Дата регистрации: {stats['registration_date']}\n"
        f"🕒 Последняя активность: {stats['last_activity']}"
    )

    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu")]
    ])

    await callback_query.message.edit_text(stats_text, parse_mode="HTML", reply_markup=back_keyboard)

@dp.callback_query(lambda c: c.data == "clear_history")
async def clear_history_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()

    user_id = callback_query.from_user.id
    chatgpt_handler.clear_history(user_id)

    await callback_query.message.edit_text(
        "🔄 <b>История чата очищена</b>\n\n"
        "Теперь ИИ не помнит предыдущие сообщения.",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu_callback(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await state.clear()

    await callback_query.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )

@dp.message(BotStates.waiting_for_message)
async def handle_chat_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_message = message.text

    await bot.send_chat_action(message.chat.id, "typing")

    try:
        response = await chatgpt_handler.get_response(user_id, user_message)

        user_manager.increment_messages(user_id)

        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])

        await message.answer(response, reply_markup=back_keyboard)

    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке сообщения. Попробуйте еще раз.",
            reply_markup=get_main_menu()
        )

@dp.message(BotStates.waiting_for_image_prompt)
async def handle_image_generation(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prompt = message.text

    await bot.send_chat_action(message.chat.id, "upload_photo")

    try:
        image_url = await image_generator.generate_image(prompt)

        if image_url:
            user_manager.increment_images(user_id)

            back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎨 Создать еще", callback_data="generate_image")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
            ])

            await message.answer_photo(
                photo=image_url,
                caption=f"🎨 <b>Изображение готово!</b>\n\nЗапрос: {prompt}",
                parse_mode="HTML",
                reply_markup=back_keyboard
            )
        else:
            await message.answer(
                "❌ Не удалось создать изображение. Попробуйте изменить описание.",
                reply_markup=get_main_menu()
            )

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании изображения. Попробуйте еще раз.",
            reply_markup=get_main_menu()
        )

@dp.message(Command("stats"))
async def stats_command(message: Message):
    user_id = message.from_user.id
    stats = user_manager.get_user_stats(user_id)

    stats_text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"💬 Сообщений в чате: {stats['messages_sent']}\n"
        f"🎨 Изображений создано: {stats['images_generated']}\n"
        f"📅 Дата регистрации: {stats['registration_date']}\n"
        f"🕒 Последняя активность: {stats['last_activity']}"
    )

    await message.answer(stats_text, parse_mode="HTML", reply_markup=get_main_menu())

@dp.message(Command("clear"))
async def clear_command(message: Message):
    user_id = message.from_user.id
    chatgpt_handler.clear_history(user_id)

    await message.answer(
        "🔄 История чата очищена!",
        reply_markup=get_main_menu()
    )

@dp.message()
async def handle_unknown_message(message: Message):
    await message.answer(
        "🤔 Выберите действие из меню или используйте команды.",
        reply_markup=get_main_menu()
    )

async def main():
    try:
        logger.info("Запуск бота...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())