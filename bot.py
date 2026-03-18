from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
import config
import database as db
import asyncio

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

def get_main_keyboard(webapp_url: str):
    """Создать основную клавиатуру"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎮 Играть", web_app=WebAppInfo(url=webapp_url))],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🎁 Бонусы")],
        [KeyboardButton(text="👥 Пригласить"), KeyboardButton(text="ℹ️ Помощь")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработка команды /start"""
    webapp_url = config.SERVER_URL if config.SERVER_URL else "https://your-domain.com"
    
    # Проверяем реферала
    referrer_id = None
    args = message.get_args()
    if args and args.startswith('ref_'):
        try:
            referrer_id = int(args.replace('ref_', ''))
        except:
            pass
    
    # Создаём пользователя
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            referrer_id
        )
        
        # Бонус за регистрацию
        if referrer_id:
            await db.add_referral(referrer_id, message.from_user.id)
            await db.update_balance(referrer_id, config.REFERRAL_BONUS, 'referral', 'Friend joined')
        
        # Стартовый бонус
        await db.update_balance(message.from_user.id, 1000, 'bonus', 'Welcome bonus')
    
    markup = get_main_keyboard(webapp_url)
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name or 'Игрок'}!\n\n"
        "🎮 <b>Crypto Clicker Pro</b> - твой путь к богатству!\n\n"
        "⚡ <b>Что тебя ждёт:</b>\n"
        "• Кликай и зарабатывай монеты\n"
        "• Прокачивай улучшения\n"
        "• Участвуй в событиях\n"
        "• Приглашай друзей\n"
        "• Мини-игры с призами\n"
        "• Ежедневные награды\n\n"
        "🚀 Жми кнопку ниже и начинай!",
        reply_markup=markup,
        parse_mode="HTML"
    )

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Показать статистику игрока"""
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала запусти бота командой /start")
        return
    
    referral_count = await db.get_referral_count(message.from_user.id)
    
    await message.answer(
        f"📊 <b>Твоя статистика:</b>\n\n"
        f"💰 Баланс: {user['balance']:,} монет\n"
        f"👆 Всего кликов: {user['total_clicks']:,}\n"
        f"💵 Всего заработано: {user['total_earned']:,}\n"
        f"🔥 Стрик дней: {user['login_streak']}\n"
        f"⚡ Прибыль/час: {user['profit_per_hour']:,}\n"
        f"👥 Приглашено друзей: {referral_count}\n"
        f"💎 VIP уровень: {user['vip_level']}",
        parse_mode="HTML"
    )

@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    """Информация о бонусах"""
    await message.answer(
        "🎁 <b>Бонусы и награды:</b>\n\n"
        "📅 <b>Ежедневная награда:</b>\n"
        "Заходи каждый день и получай всё больше монет!\n\n"
        "👥 <b>Реферальная программа:</b>\n"
        f"Пригласи друга и получи {config.REFERRAL_BONUS:,} монет\n\n"
        "🎮 <b>Мини-игры:</b>\n"
        "Играй и выигрывай дополнительные призы\n\n"
        "🏆 <b>События:</b>\n"
        "Участвуй в специальных событиях с множителями",
        parse_mode="HTML"
    )

@dp.message(Command("invite"))
async def cmd_invite(message: types.Message):
    """Ссылка для приглашения"""
    bot_username = (await bot.get_me()).username
    invite_link = f"https://t.me/{bot_username}?start=ref_{message.from_user.id}"
    
    await message.answer(
        f"👥 <b>Пригласи друзей!</b>\n\n"
        f"Отправь эту ссылку друзьям:\n"
        f"<code>{invite_link}</code>\n\n"
        f"За каждого друга ты получишь {config.REFERRAL_BONUS:,} монет! 💰",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Справка"""
    await message.answer(
        "ℹ️ <b>Помощь:</b>\n\n"
        "🎮 /start - Запустить игру\n"
        "📊 /stats - Твоя статистика\n"
        "🎁 /bonus - Информация о бонусах\n"
        "👥 /invite - Пригласить друзей\n"
        "ℹ️ /help - Эта справка\n\n"
        "💡 <b>Советы:</b>\n"
        "• Кликай быстро для комбо-бонусов\n"
        "• Прокачивай улучшения для большей прибыли\n"
        "• Заходи каждый день для стрик-бонусов\n"
        "• Участвуй в событиях для множителей",
        parse_mode="HTML"
    )

@dp.message()
async def handle_text(message: types.Message):
    """Обработка текстовых сообщений"""
    text = message.text
    
    if text == "📊 Статистика":
        await cmd_stats(message)
    elif text == "🎁 Бонусы":
        await cmd_bonus(message)
    elif text == "👥 Пригласить":
        await cmd_invite(message)
    elif text == "ℹ️ Помощь":
        await cmd_help(message)

async def start_bot():
    """Запуск бота"""
    print("🤖 Бот запускается...")
    await dp.start_polling(bot)
    print("✅ Бот запущен")

print("✅ Модуль bot загружен")
