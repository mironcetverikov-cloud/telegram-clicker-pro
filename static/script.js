// Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Состояние игры
let gameState = {
    balance: 0,
    energy: 1000,
    maxEnergy: 1000,
    profitPerClick: 1,
    profitPerHour: 0,
    loginStreak: 0,
    totalClicks: 0,
    totalEarned: 0,
    multiplier: 1.0,
    combo: 0,
    comboTimer: null,
    username: 'User'
};

let initData = tg.initData || '';
let upgradeLevels = {};
let lastClickTime = 0;

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    loadUser();
    setupNavigation();
    startEnergyRegen();
    startAutoSave();
});

// Загрузка данных пользователя
async function loadUser() {
    try {
        const response = await fetch('/api/user', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({init_data: initData})
        });
        
        if (response.ok) {
            const data = await response.json();
            gameState = {
                ...gameState,
                balance: data.balance,
                energy: data.energy,
                maxEnergy: data.max_energy,
                profitPerClick: data.profit_per_click,
                profitPerHour: data.profit_per_hour,
                loginStreak: data.login_streak,
                totalClicks: data.total_clicks,
                totalEarned: data.total_earned,
                multiplier: data.multiplier,
                username: data.username
            };
            updateUI();
            loadEvents();
            loadReferrals();
        }
    } catch (e) {
        console.log('Offline mode');
        showNotification('⚠️ Работа в офлайн режиме', 'warning');
    }
}

// Обновление интерфейса
function updateUI() {
    document.getElementById('balance').textContent = Math.floor(gameState.balance).toLocaleString();
    document.getElementById('pph').textContent = Math.floor(gameState.profitPerHour).toLocaleString();
    document.getElementById('ppc').textContent = gameState.profitPerClick.toLocaleString();
    document.getElementById('streak').textContent = gameState.loginStreak;
    
    const energyPercent = (gameState.energy / gameState.maxEnergy) * 100;
    document.getElementById('energy-bar').style.width = energyPercent + '%';
    document.getElementById('energy-text').textContent = `${Math.floor(gameState.energy)}/${gameState.maxEnergy}`;
    
    // Баннер события
    if (gameState.multiplier > 1) {
        document.getElementById('event-banner').style.display = 'block';
        document.getElementById('event-multiplier').textContent = gameState.multiplier.toFixed(1);
    }
}

// Обработка клика
document.getElementById('click-area').addEventListener('click', async (e) => {
    if (gameState.energy < 1) {
        tg.HapticFeedback.notificationOccurred('error');
        showNotification('⚡ Недостаточно энергии!', 'warning');
        return;
    }
    
    // Комбо система
    const now = Date.now();
    if (now - lastClickTime < 500) {
        gameState.combo++;
        document.getElementById('combo-count').textContent = gameState.combo;
        document.getElementById('combo-meter').style.display = 'block';
        
        clearTimeout(gameState.comboTimer);
        gameState.comboTimer = setTimeout(() => {
            gameState.combo = 0;
            document.getElementById('combo-meter').style.display = 'none';
        }, 2000);
    } else {
        gameState.combo = 1;
    }
    lastClickTime = now;
    
    // Бонус за комбо
    let clickProfit = gameState.profitPerClick;
    if (gameState.combo >= 5) clickProfit *= 1.5;
    if (gameState.combo >= 10) clickProfit *= 2;
    
    // Визуальное обновление
    gameState.balance += clickProfit;
    gameState.energy -= 1;
    showFloatNumber(e.clientX, e.clientY, `+${Math.floor(clickProfit)}`);
    tg.HapticFeedback.impactOccurred('light');
    updateUI();
    
    // Отправка на сервер
    try {
        await fetch('/api/click', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                init_data: initData,
                clicks: 1,
                energy_spent: 1
            })
        });
    } catch (e) {
        console.error('Sync error');
    }
});

// Плавающие числа
function showFloatNumber(x, y, text) {
    const el = document.createElement('div');
    el.className = 'float-number';
    el.textContent = text;
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 800);
}

// Навигация
function setupNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            
            btn.classList.add('active');
            const tabName = btn.dataset.tab;
            document.getElementById(`tab-${tabName}`).classList.add('active');
            
            if (tabName === 'friends') loadLeaderboard();
            if (tabName === 'quests') { loadQuests(); loadAchievements(); }
        });
    });
}

// Покупка улучшения
async function buyUpgrade(type) {
    try {
        const response = await fetch('/api/upgrade', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({init_data: initData, upgrade_type: type})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showNotification(`✅ Улучшение куплено! Уровень: ${data.new_level}`, 'success');
            upgradeLevels[type] = data.new_level;
            document.getElementById(`${type.split('_')[0]}-level`).textContent = `Ур. ${data.new_level}`;
            loadUser();
        } else {
            showNotification(`❌ ${data.detail}`, 'error');
        }
    } catch (e) {
        showNotification('❌ Ошибка соединения', 'error');
    }
}

// Ежедневная награда
function showDaily() {
    document.getElementById('modal-daily').style.display = 'flex';
    document.getElementById('daily-streak').textContent = gameState.loginStreak + 1;
    document.getElementById('daily-reward').textContent = (100 * (gameState.loginStreak + 1)).toLocaleString();
}

async function claimDaily() {
    try {
        const response = await fetch('/api/daily', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({init_data: initData})
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showNotification(`🎁 Получено ${data.reward.toLocaleString()} монет!`, 'success');
            loadUser();
        } else {
            showNotification('⚠️ Уже получено сегодня!', 'warning');
        }
    } catch (e) {
        showNotification('❌ Ошибка', 'error');
    }
    closeModal('modal-daily');
}

// Мини-игры
function showMinigames() {
    document.querySelector('[data-tab="minigames"]').click();
}

async function playMinigame(gameType) {
    document.getElementById('modal-minigame').style.display = 'flex';
    document.getElementById('minigame-title').textContent = getMinigameTitle(gameType);
    
    const content = document.getElementById('minigame-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    
    // Симуляция игры
    setTimeout(() => {
        const win = Math.random() > 0.5;
        const reward = win ? Math.floor(Math.random() * 500) + 100 : 0;
        
        content.innerHTML = win 
            ? `<div class="win-text">🎉 Вы выиграли ${reward.toLocaleString()} 💰!</div>`
            : `<div class="lose-text">😔 Попробуйте еще раз!</div>`;
        
        if (win) {
            submitMinigameScore(gameType, 100, reward);
        }
    }, 1500);
}

function getMinigameTitle(type) {
    const titles = {
        roulette: '🎰 Рулетка',
        wheel: '🎡 Колесо фортуны',
        scratch: '🎫 Скретч-карта',
        dice: '🎲 Кости'
    };
    return titles[type] || 'Игра';
}

async function submitMinigameScore(gameType, score, reward) {
    try {
        await fetch('/api/minigame', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({init_data: initData, game_type: gameType, score: score})
        });
    } catch (e) {}
}

// Квесты
async function loadQuests() {
    try {
        const response = await fetch('/api/quests', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({init_data: initData})
        });
        
        const data = await response.json();
        const list = document.getElementById('quests-list');
        
        if (data.quests && data.quests.length > 0) {
            list.innerHTML = data.quests.map(q => `
                <div class="quest-item">
                    <span>${q.quest_type}</span>
                    <div class="quest-progress">
                        <progress value="${q.progress}" max="${q.target}"></progress>
                    </div>
                    <span>${q.progress}/${q.target}</span>
                    <span style="color: var(--gold)">🏆 ${q.reward}</span>
                </div>
            `).join('');
        } else {
            list.innerHTML = '<p style="text-align:center;color:var(--text-secondary)">Нет активных квестов</p>';
        }
    } catch (e) {}
}

// Достижения
async function loadAchievements() {
    try {
        const response = await fetch('/api/achievements', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({init_data: initData})
        });
        
        const data = await response.json();
        const list = document.getElementById('achievements-list');
        
        const allAchievements = [
            {id: 'first_click', name: 'Первый клик', icon: '👆'},
            {id: 'click_master', name: 'Мастер кликов (1K)', icon: '⚡'},
            {id: 'click_legend', name: 'Легенда кликов (10K)', icon: '🔥'},
            {id: 'rich', name: 'Богач (10K)', icon: '💰'},
            {id: 'millionaire', name: 'Миллионер (1M)', icon: '💎'},
            {id: 'week_warrior', name: 'Недельный воин', icon: '📅'},
            {id: 'month_master', name: 'Месячный мастер', icon: '🏆'},
            {id: 'collector', name: 'Коллекционер', icon: '🎯'}
        ];
        
        list.innerHTML = allAchievements.map(a => {
            const unlocked = data.achievements && data.achievements.includes(a.id);
            return `
                <div class="achievement-item ${unlocked ? 'unlocked' : 'locked'}">
                    <span>${a.icon} ${a.name}</span>
                    <span>${unlocked ? '✅' : '🔒'}</span>
                </div>
            `;
        }).join('');
    } catch (e) {}
}

// Лидерборд
async function loadLeaderboard() {
    try {
        const response = await fetch('/api/leaderboard');
        const data = await response.json();
        
        const list = document.getElementById('leaderboard-list');
        list.innerHTML = data.map((user, index) => `
            <li>
                <span>#${index + 1} ${user.username}</span>
                <span style="color: var(--gold)">${user.balance.toLocaleString()} 💰</span>
            </li>
        `).join('');
    } catch (e) {}
}

// События
async function loadEvents() {
    try {
        const response = await fetch('/api/events');
        const data = await response.json();
        
        if (data.events && data.events.length > 0) {
            document.getElementById('event-banner').style.display = 'block';
            document.getElementById('event-name').textContent = data.events[0].name;
            document.getElementById('event-multiplier').textContent = data.events[0].multiplier.toFixed(1);
        }
    } catch (e) {}
}

// Рефералы
async function loadReferrals() {
    try {
        const response = await fetch('/api/referrals?init_data=' + encodeURIComponent(initData));
        const data = await response.json();
        document.getElementById('referral-count').textContent = data.count;
    } catch (e) {}
}

// Поделиться ссылкой
function shareLink() {
    const botUsername = tg.initDataUnsafe?.user?.username || 'your_bot';
    const userId = tg.initDataUnsafe?.user?.id || '';
    tg.openTelegramLink(`https://t.me/${botUsername}?start=ref_${userId}`);
}

// Модальные окна
function closeModal(id) {
    document.getElementById(id).style.display = 'none';
}

// Уведомления
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.style.display = 'block';
    notification.style.background = type === 'success' ? 'rgba(74, 222, 128, 0.2)' :
                                    type === 'error' ? 'rgba(248, 113, 113, 0.2)' :
                                    'var(--bg-tertiary)';
    notification.style.borderColor = type === 'success' ? 'var(--success)' :
                                     type === 'error' ? 'var(--danger)' : 'var(--border-color)';
    
    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

// Регенерация энергии
function startEnergyRegen() {
    setInterval(() => {
        if (gameState.energy < gameState.maxEnergy) {
            gameState.energy = Math.min(gameState.energy + 3, gameState.maxEnergy);
            updateUI();
        }
    }, 1000);
}

// Авто-сохранение
function startAutoSave() {
    setInterval(() => {
        loadUser();
    }, 30000);
}

// Закрытие модальных окон по клику вне
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

console.log('🎮 Crypto Clicker Pro loaded');