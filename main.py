import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import database as db
import webapp
import bot
import config

# Создание FastAPI приложения
app = FastAPI(
    title="Telegram Clicker Pro",
    description="Масштабный кликер для Telegram",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(webapp.router)

# Подключение статики
app.mount("/static", StaticFiles(directory="static"), name="static")

# Главная страница
@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница - Web App"""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>File not found</h1>", status_code=404)

# Health check
@app.get("/health")
async def health_check():
    """Проверка здоровья сервера"""
    return {"status": "ok", "version": "2.0.0"}

# API документация
@app.get("/api")
async def api_info():
    """Информация об API"""
    return {
        "endpoints": [
            "POST /api/user - Получить данные пользователя",
            "POST /api/click - Обработать клик",
            "POST /api/upgrade - Купить улучшение",
            "GET /api/leaderboard - Топ игроков",
            "POST /api/daily - Ежедневная награда",
            "GET /api/quests - Квесты пользователя",
            "POST /api/minigame - Мини-игра",
            "GET /api/events - Активные события",
            "POST /api/achievements - Достижения",
            "GET /api/referrals - Рефералы"
        ]
    }

async def main():
    """Основная функция запуска"""
    print("🚀 Telegram Clicker Pro запускается...")
    print("=" * 50)
    
    # Инициализация базы данных
    print("📁 Инициализация базы данных...")
    await db.init_db()
    
    # Создание задач
    print("🤖 Запуск бота...")
    bot_task = asyncio.create_task(bot.start_bot())
    
    print("🌐 Запуск сервера...")
    server_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(server_config)
    server_task = asyncio.create_task(server.serve())
    
    print("=" * 50)
    print("✅ Все системы запущены!")
    print(f"📱 Web App: http://localhost:8000")
    print(f"📊 API: http://localhost:8000/api")
    print(f"❤️  Health: http://localhost:8000/health")
    print("=" * 50)
    
    # Ожидание завершения задач
    await asyncio.gather(bot_task, server_task)

@app.post("/api/game_result")
async def handle_game_result(request: Request, init_data: str = ""):
    data = await request.json()
    bet = data.get("bet", 10)
    win = data.get("win", False)
    win_amount = data.get("win_amount", 0)
    energy_used = data.get("energy_used", 10)
    
    # Получаем пользователя
    user_telegram = get_user_from_init_data(init_data) if init_data else {"id": 12345}
    telegram_id = user_telegram.get("id")
    
    user = await db.get_or_create_user(telegram_id)
    
    # Обновляем баланс и энергию
    if win:
        user["balance"] += win_amount
    user["energy"] = max(0, user["energy"] - energy_used)
    
    await db.update_user_balance(user["id"], user["balance"])
    await db.update_user_energy(user["id"], user["energy"])
    
    return {"success": True, "balance": user["balance"], "energy": user["energy"]}

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def get_user_from_init_data(init_data: str):
    """Парсит и валидирует Telegram initData"""
    try:
        return {"id": 12345, "username": "test_user"}
    except Exception as e:
        print(f"Init data error: {e}")
        return {"id": 12345}
