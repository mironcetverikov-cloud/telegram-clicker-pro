import aiosqlite
import time

DB_NAME = "game_database.db"

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                balance INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 1000,
                max_energy INTEGER DEFAULT 1000,
                profit_per_click INTEGER DEFAULT 1,
                profit_per_hour INTEGER DEFAULT 0,
                last_login REAL,
                referrer_id INTEGER,
                joined_at REAL DEFAULT (strftime('%s', 'now')),
                login_streak INTEGER DEFAULT 0,
                last_daily_claim REAL DEFAULT 0,
                vip_level INTEGER DEFAULT 0,
                vip_expires REAL DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                last_energy_regen REAL DEFAULT (strftime('%s', 'now')),
                is_banned INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица улучшений
        await db.execute('''
            CREATE TABLE IF NOT EXISTS upgrades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                upgrade_type TEXT NOT NULL,
                level INTEGER DEFAULT 0,
                purchased_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица квестов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                quest_type TEXT NOT NULL,
                quest_id TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                progress INTEGER DEFAULT 0,
                target INTEGER NOT NULL,
                reward INTEGER NOT NULL,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                completed_at REAL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица достижений
        await db.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, achievement_id)
            )
        ''')
        
        # Таблица событий
        await db.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_name TEXT NOT NULL,
                description TEXT,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                multiplier REAL DEFAULT 1.0,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Таблица транзакций
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица рефералов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                reward_claimed INTEGER DEFAULT 0,
                created_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY(referrer_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(referred_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица результатов мини-игр
        await db.execute('''
            CREATE TABLE IF NOT EXISTS minigame_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_type TEXT NOT NULL,
                score INTEGER NOT NULL,
                reward INTEGER NOT NULL,
                played_at REAL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Индексы для производительности
        await db.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_upgrades_user ON upgrades(user_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_quests_user ON quests(user_id, status)')
        
        # Создадим тестовое событие
        await db.execute('''
            INSERT OR IGNORE INTO events (event_type, event_name, description, start_time, end_time, multiplier)
            VALUES ('welcome', 'Добро пожаловать!', 'Бонус для новых игроков', 0, 9999999999, 1.0)
        ''')
        
        await db.commit()
    
    print("✅ База данных инициализирована")

async def get_user(telegram_id: int):
    """Получить пользователя по Telegram ID"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        return await cursor.fetchone()

async def create_user(telegram_id: int, username: str = None, first_name: str = None, referrer_id: int = None):
    """Создать нового пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            '''INSERT INTO users (telegram_id, username, first_name, last_login, referrer_id) 
               VALUES (?, ?, ?, ?, ?)''',
            (telegram_id, username, first_name, time.time(), referrer_id)
        )
        await db.commit()
    
    # Если есть реферер, создаём запись
    if referrer_id:
        await add_referral(referrer_id, telegram_id)

async def update_balance(telegram_id: int, amount: int, tx_type: str = 'earn', description: str = ''):
    """Обновить баланс пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE telegram_id = ?',
            (amount, max(0, amount), telegram_id)
        )
        await db.execute(
            'INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
            (telegram_id, amount, tx_type, description)
        )
        await db.commit()

async def update_energy(telegram_id: int, energy: int):
    """Обновить энергию пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET energy = ?, last_energy_regen = ? WHERE telegram_id = ?',
                        (energy, time.time(), telegram_id))
        await db.commit()

async def update_clicks(telegram_id: int, clicks: int):
    """Обновить счётчик кликов"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET total_clicks = total_clicks + ? WHERE telegram_id = ?', (clicks, telegram_id))
        await db.commit()

async def get_leaderboard(limit: int = 10):
    """Получить топ игроков"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT username, first_name, balance, total_clicks FROM users WHERE is_banned = 0 ORDER BY balance DESC LIMIT ?',
            (limit,)
        )
        return await cursor.fetchall()

async def get_user_upgrades(telegram_id: int):
    """Получить улучшения пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user(telegram_id)
        if not user:
            return []
        cursor = await db.execute('SELECT * FROM upgrades WHERE user_id = ?', (user['id'],))
        return await cursor.fetchall()

async def buy_upgrade(telegram_id: int, upgrade_type: str, cost: int, level: int):
    """Купить улучшение"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user or user['balance'] < cost:
            return False
        
        await db.execute('UPDATE users SET balance = balance - ? WHERE telegram_id = ?', (cost, telegram_id))
        
        cursor = await db.execute('SELECT * FROM upgrades WHERE user_id = ? AND upgrade_type = ?', (user['id'], upgrade_type))
        row = await cursor.fetchone()
        
        if row:
            await db.execute('UPDATE upgrades SET level = level + 1 WHERE user_id = ? AND upgrade_type = ?',
                           (user['id'], upgrade_type))
        else:
            await db.execute('INSERT INTO upgrades (user_id, upgrade_type, level) VALUES (?, ?, ?)',
                           (user['id'], upgrade_type, level))
        
        await db.execute(
            'INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
            (telegram_id, -cost, 'upgrade', f'Purchase {upgrade_type} level {level}')
        )
        await db.commit()
        return True

async def get_active_events():
    """Получить активные события"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        now = time.time()
        cursor = await db.execute(
            'SELECT * FROM events WHERE is_active = 1 AND start_time <= ? AND end_time >= ?',
            (now, now)
        )
        return await cursor.fetchall()

async def get_user_achievements(telegram_id: int):
    """Получить достижения пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user(telegram_id)
        if not user:
            return []
        cursor = await db.execute('SELECT * FROM achievements WHERE user_id = ?', (user['id'],))
        return await cursor.fetchall()

async def unlock_achievement(telegram_id: int, achievement_id: str):
    """Разблокировать достижение"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return False
        
        try:
            await db.execute(
                'INSERT INTO achievements (user_id, achievement_id) VALUES (?, ?)',
                (user['id'], achievement_id)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def get_user_quests(telegram_id: int):
    """Получить квесты пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user(telegram_id)
        if not user:
            return []
        cursor = await db.execute(
            'SELECT * FROM quests WHERE user_id = ? AND status = ?',
            (user['id'], 'active')
        )
        return await cursor.fetchall()

async def update_quest_progress(telegram_id: int, quest_type: str, progress: int):
    """Обновить прогресс квеста"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return
        await db.execute(
            'UPDATE quests SET progress = progress + ? WHERE user_id = ? AND quest_type = ? AND status = ?',
            (progress, user['id'], quest_type, 'active')
        )
        await db.commit()

async def claim_daily_reward(telegram_id: int):
    """Получить ежедневную награду"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return 0
        
        now = time.time()
        last_claim = user['last_daily_claim']
        
        # Прошло ли 24 часа
        if now - last_claim < 86400:
            return 0
        
        # Увеличиваем стрик
        streak = user['login_streak'] + 1
        if now - last_claim > 172800:  # Больше 48 часов - сброс
            streak = 1
        
        # Награда зависит от стрика
        from config import DAILY_BASE_REWARD, DAILY_STREAK_MULTIPLIER
        reward = int(DAILY_BASE_REWARD * streak * DAILY_STREAK_MULTIPLIER)
        
        await db.execute(
            'UPDATE users SET balance = balance + ?, login_streak = ?, last_daily_claim = ? WHERE telegram_id = ?',
            (reward, streak, now, telegram_id)
        )
        await db.execute(
            'INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
            (telegram_id, reward, 'daily', f'Daily reward streak {streak}')
        )
        await db.commit()
        return reward

async def get_referral_count(telegram_id: int):
    """Получить количество рефералов"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return 0
        cursor = await db.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user['id'],))
        result = await cursor.fetchone()
        return result[0] if result else 0

async def add_referral(referrer_id: int, referred_id: int):
    """Добавить реферала"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Проверка на дубликат
        cursor = await db.execute(
            'SELECT * FROM referrals WHERE referrer_id = ? AND referred_id = ?',
            (referrer_id, referred_id)
        )
        if await cursor.fetchone():
            return False
        
        await db.execute(
            'INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)',
            (referrer_id, referred_id)
        )
        await db.commit()
        return True

async def get_minigame_best_score(telegram_id: int, game_type: str):
    """Получить лучший результат в мини-игре"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return 0
        cursor = await db.execute(
            'SELECT MAX(score) FROM minigame_scores WHERE user_id = ? AND game_type = ?',
            (user['id'], game_type)
        )
        result = await cursor.fetchone()
        return result[0] if result and result[0] else 0

async def save_minigame_score(telegram_id: int, game_type: str, score: int, reward: int):
    """Сохранить результат мини-игры"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return
        await db.execute(
            'INSERT INTO minigame_scores (user_id, game_type, score, reward) VALUES (?, ?, ?, ?)',
            (user['id'], game_type, score, reward)
        )
        await db.commit()

async def create_quest(telegram_id: int, quest_type: str, quest_id: str, target: int, reward: int):
    """Создать квест для пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return False
        
        # Проверка на существующий квест
        cursor = await db.execute(
            'SELECT * FROM quests WHERE user_id = ? AND quest_id = ? AND status = ?',
            (user['id'], quest_id, 'active')
        )
        if await cursor.fetchone():
            return False
        
        await db.execute(
            'INSERT INTO quests (user_id, quest_type, quest_id, target, reward) VALUES (?, ?, ?, ?, ?)',
            (user['id'], quest_type, quest_id, target, reward)
        )
        await db.commit()
        return True

async def check_and_complete_quest(telegram_id: int, quest_type: str):
    """Проверить и завершить квесты"""
    async with aiosqlite.connect(DB_NAME) as db:
        user = await get_user(telegram_id)
        if not user:
            return []
        
        completed = []
        cursor = await db.execute(
            'SELECT * FROM quests WHERE user_id = ? AND quest_type = ? AND status = ? AND progress >= target',
            (user['id'], quest_type, 'active')
        )
        quests = await cursor.fetchall()
        
        for quest in quests:
            await db.execute(
                'UPDATE quests SET status = ?, completed_at = ? WHERE id = ?',
                ('completed', time.time(), quest['id'])
            )
            await db.execute(
                'UPDATE users SET balance = balance + ? WHERE id = ?',
                (quest['reward'], user['id'])
            )
            completed.append(quest['quest_id'])
        
        await db.commit()
        return completed

print("✅ Модуль database загружен")
