from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import time
import json
import random
import database as db
import config

router = APIRouter()

# Модели данных
class ClickData(BaseModel):
    init_data: str
    clicks: int
    energy_spent: int

class UpgradeData(BaseModel):
    init_data: str
    upgrade_type: str

class QuestClaimData(BaseModel):
    init_data: str
    quest_id: str

class MinigameData(BaseModel):
    init_data: str
    game_type: str
    score: int

class DailyData(BaseModel):
    init_data: str

def get_telegram_id(init_data: str):
    """Извлечь Telegram ID из initData"""
    try:
        parts = init_data.split('&')
        user_part = [p for p in parts if p.startswith('user=')][0]
        user_json = user_part.replace('user=', '')
        user_obj = json.loads(user_json)
        return user_obj.get('id')
    except:
        return 0

def get_event_multiplier():
    """Получить множитель событий"""
    import asyncio
    events = asyncio.run(db.get_active_events())
    multiplier = 1.0
    for event in events:
        multiplier *= event['multiplier']
    return multiplier

def regenerate_energy(user, current_time):
    """Регенерация энергии"""
    time_passed = current_time - user['last_energy_regen']
    regenerated = int(time_passed) * config.DEFAULT_ENERGY_REGEN
    new_energy = min(user['max_energy'], user['energy'] + regenerated)
    return new_energy

@router.post("/api/user")
async def get_user_data(request: Request):
    """Получить данные пользователя"""
    body = await request.json()
    init_data = body.get("init_data", "")
    tg_id = get_telegram_id(init_data)
    
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user = await db.get_user(tg_id)
    if not user:
        # Создаём нового пользователя
        await db.create_user(tg_id)
        user = await db.get_user(tg_id)
        
        # Создаём стартовые квесты
        await db.create_quest(tg_id, 'clicks', 'first_clicks', 100, 500)
        await db.create_quest(tg_id, 'earn', 'first_earn', 1000, 200)
    
    # Регенерация энергии
    now = time.time()
    new_energy = regenerate_energy(user, now)
    await db.update_energy(tg_id, new_energy)
    user = await db.get_user(tg_id)
    
    # Пассивный доход
    offline_time = now - user['last_login']
    earned = 0
    if offline_time > 60 and user['profit_per_hour'] > 0:
        multiplier = get_event_multiplier()
        earned = int((offline_time / 3600) * user['profit_per_hour'] * multiplier)
        await db.update_balance(tg_id, earned, 'offline', 'Offline earnings')
        user = await db.get_user(tg_id)
    
    # Обновляем last_login
    async with db.aiosqlite.connect(db.DB_NAME) as db_conn:
        await db_conn.execute('UPDATE users SET last_login = ? WHERE telegram_id = ?', (now, tg_id))
        await db_conn.commit()
    
    # Проверка достижений
    await check_achievements(tg_id, user)
    
    return {
        "balance": user['balance'],
        "energy": user['energy'],
        "max_energy": user['max_energy'],
        "profit_per_click": user['profit_per_click'],
        "profit_per_hour": user['profit_per_hour'],
        "login_streak": user['login_streak'],
        "vip_level": user['vip_level'],
        "total_clicks": user['total_clicks'],
        "total_earned": user['total_earned'],
        "multiplier": get_event_multiplier(),
        "username": user['username'] or user['first_name'] or f"User{tg_id}"
    }

@router.post("/api/click")
async def handle_click(data: ClickData):
    """Обработка клика"""
    tg_id = get_telegram_id(data.init_data)
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user = await db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user['is_banned']:
        raise HTTPException(status_code=403, detail="Account banned")
    
    if data.energy_spent > user['energy']:
        raise HTTPException(status_code=400, detail="Not enough energy")
    
    # Расчёт прибыли с множителями
    multiplier = get_event_multiplier()
    combo_bonus = 1.0
    if data.clicks >= 5:
        combo_bonus = 1.5
    if data.clicks >= 10:
        combo_bonus = 2.0
    
    profit = int(data.clicks * user['profit_per_click'] * multiplier * combo_bonus)
    
    await db.update_balance(tg_id, profit, 'click', 'Click earnings')
    await db.update_energy(tg_id, user['energy'] - data.energy_spent)
    await db.update_clicks(tg_id, data.clicks)
    await db.update_quest_progress(tg_id, 'clicks', data.clicks)
    await db.check_and_complete_quest(tg_id, 'clicks')
    
    # Шанс на критический клик (5%)
    crit = random.random() < 0.05
    crit_bonus = 0
    if crit:
        crit_bonus = profit * 2
        await db.update_balance(tg_id, crit_bonus, 'crit', 'Critical click!')
    
    return {
        "status": "ok",
        "new_balance": user['balance'] + profit + crit_bonus,
        "crit": crit,
        "combo_bonus": combo_bonus
    }

@router.post("/api/upgrade")
async def handle_upgrade(data: UpgradeData):
    """Покупка улучшения"""
    tg_id = get_telegram_id(data.init_data)
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user = await db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Конфигурация улучшений
    upgrades_config = {
        'multitap': {'base_cost': 100, 'click_bonus': 1, 'hour_bonus': 0, 'energy_bonus': 0},
        'energy': {'base_cost': 200, 'click_bonus': 0, 'hour_bonus': 0, 'energy_bonus': 500},
        'auto_clicker': {'base_cost': 500, 'click_bonus': 0, 'hour_bonus': 100, 'energy_bonus': 0},
        'profit_boost': {'base_cost': 1000, 'click_bonus': 2, 'hour_bonus': 50, 'energy_bonus': 0},
        'energy_limit': {'base_cost': 1500, 'click_bonus': 0, 'hour_bonus': 0, 'energy_bonus': 1000},
        'gold_pickaxe': {'base_cost': 5000, 'click_bonus': 5, 'hour_bonus': 200, 'energy_bonus': 0}
    }
    
    if data.upgrade_type not in upgrades_config:
        raise HTTPException(status_code=400, detail="Invalid upgrade type")
    
    config_upgrade = upgrades_config[data.upgrade_type]
    current_upgrades = await db.get_user_upgrades(tg_id)
    level = next((u['level'] for u in current_upgrades if u['upgrade_type'] == data.upgrade_type), 0)
    cost = config_upgrade['base_cost'] * (level + 1)
    
    if user['balance'] < cost:
        raise HTTPException(status_code=400, detail="Not enough balance")
    
    success = await db.buy_upgrade(tg_id, data.upgrade_type, cost, level + 1)
    if not success:
        raise HTTPException(status_code=400, detail="Purchase failed")
    
    # Применяем бонусы
    import aiosqlite
    async with aiosqlite.connect(db.DB_NAME) as db_conn:
        if config_upgrade['click_bonus'] > 0:
            await db_conn.execute(
                'UPDATE users SET profit_per_click = profit_per_click + ? WHERE telegram_id = ?',
                (config_upgrade['click_bonus'], tg_id)
            )
        if config_upgrade['hour_bonus'] > 0:
            await db_conn.execute(
                'UPDATE users SET profit_per_hour = profit_per_hour + ? WHERE telegram_id = ?',
                (config_upgrade['hour_bonus'], tg_id)
            )
        if config_upgrade['energy_bonus'] > 0:
            await db_conn.execute(
                'UPDATE users SET max_energy = max_energy + ? WHERE telegram_id = ?',
                (config_upgrade['energy_bonus'], tg_id)
            )
        await db_conn.commit()
    
    return {"status": "ok", "new_level": level + 1, "cost": cost}

@router.get("/api/leaderboard")
async def get_leaderboard():
    """Получить топ игроков"""
    leaders = await db.get_leaderboard(20)
    return [
        {
            "username": l['username'] or l['first_name'] or f"User{l['id']}",
            "balance": l['balance'],
            "total_clicks": l['total_clicks']
        }
        for l in leaders
    ]

@router.post("/api/daily")
async def claim_daily(data: DailyData):
    """Получить ежедневную награду"""
    tg_id = get_telegram_id(data.init_data)
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    reward = await db.claim_daily_reward(tg_id)
    if reward == 0:
        raise HTTPException(status_code=400, detail="Already claimed today")
    
    return {"status": "ok", "reward": reward}

@router.get("/api/quests")
async def get_quests(request: Request):
    """Получить квесты пользователя"""
    body = await request.json()
    init_data = body.get("init_data", "")
    tg_id = get_telegram_id(init_data)
    
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    quests = await db.get_user_quests(tg_id)
    return {"quests": [dict(q) for q in quests]}

@router.post("/api/minigame")
async def handle_minigame(data: MinigameData):
    """Обработка результата мини-игры"""
    tg_id = get_telegram_id(data.init_data)
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user = await db.get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Награда зависит от счета
    reward = data.score * 10
    multiplier = get_event_multiplier()
    final_reward = int(reward * multiplier)
    
    await db.update_balance(tg_id, final_reward, 'minigame', f'{data.game_type} score: {data.score}')
    await db.save_minigame_score(tg_id, data.game_type, data.score, final_reward)
    
    return {"status": "ok", "reward": final_reward}

@router.get("/api/events")
async def get_events():
    """Получить активные события"""
    events = await db.get_active_events()
    return {
        "events": [
            {
                "name": e['event_name'],
                "description": e['description'],
                "multiplier": e['multiplier'],
                "end_time": e['end_time']
            }
            for e in events
        ]
    }

@router.post("/api/achievements")
async def get_achievements(request: Request):
    """Получить достижения пользователя"""
    body = await request.json()
    init_data = body.get("init_data", "")
    tg_id = get_telegram_id(init_data)
    
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    achievements = await db.get_user_achievements(tg_id)
    return {"achievements": [a['achievement_id'] for a in achievements]}

@router.get("/api/referrals")
async def get_referrals(request: Request):
    """Получить информацию о рефералах"""
    init_data = request.query_params.get("init_data", "")
    tg_id = get_telegram_id(init_data)
    
    if not tg_id:
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    count = await db.get_referral_count(tg_id)
    return {"count": count, "bonus": config.REFERRAL_BONUS}

async def check_achievements(tg_id: int, user):
    """Проверка и разблокировка достижений"""
    achievements_config = {
        'first_click': {'condition': lambda u: u['total_clicks'] >= 1},
        'click_master': {'condition': lambda u: u['total_clicks'] >= 1000},
        'click_legend': {'condition': lambda u: u['total_clicks'] >= 10000},
        'rich': {'condition': lambda u: u['balance'] >= 10000},
        'millionaire': {'condition': lambda u: u['balance'] >= 1000000},
        'week_warrior': {'condition': lambda u: u['login_streak'] >= 7},
        'month_master': {'condition': lambda u: u['login_streak'] >= 30},
        'collector': {'condition': lambda u: u['total_earned'] >= 100000}
    }
    
    for achievement_id, config_item in achievements_config.items():
        if config_item['condition'](user):
            await db.unlock_achievement(tg_id, achievement_id)

print("✅ Модуль webapp загружен")
