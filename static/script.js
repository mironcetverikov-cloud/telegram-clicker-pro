const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

let gameState = {
    balance: 0,
    energy: 1000,
    maxEnergy: 1000,
    profitPerClick: 1,
    profitPerHour: 0,
    currentBet: 10,
    isProcessing: false
};

let initData = tg.initData || '';
let userId = null;

// Получаем ID пользователя из initData
function getUserIdFromInitData() {
    try {
        const params = new URLSearchParams(initData);
        const userStr = params.get('user');
        if (userStr) {
            const user = JSON.parse(decodeURIComponent(userStr));
            return user.id;
        }
    } catch (e) {}
    return null;
}

userId = getUserIdFromInitData();

async function loadUser() {
    try {
        const response = await fetch('/api/user?init_data=' + encodeURIComponent(initData));
        const data = await response.json();
        if (data.user) {
            gameState.balance = data.user.balance;
            gameState.energy = data.user.energy;
            gameState.maxEnergy = data.user.max_energy || 1000;
            gameState.profitPerClick = data.user.profit_per_click || 1;
            gameState.profitPerHour = data.user.profit_per_hour || 0;
            updateUI();
            updateBetInfo();
        }
    } catch (e) {
        console.log('Demo mode');
        updateUI();
        updateBetInfo();
    }
}

function updateUI() {
    document.getElementById('balance').textContent = Math.floor(gameState.balance).toLocaleString();
    document.getElementById('pph').textContent = gameState.profitPerHour.toLocaleString();
    document.getElementById('ppc').textContent = gameState.profitPerClick.toLocaleString();
    
    const energyPercent = (gameState.energy / gameState.maxEnergy) * 100;
    document.getElementById('energy-bar').style.width = Math.max(0, energyPercent) + '%';
    document.getElementById('energy-text').textContent = Math.floor(Math.max(0, gameState.energy)) + '/' + gameState.maxEnergy;
}

function updateBetInfo() {
    const bet = parseInt(document.getElementById('bet-amount').value) || 10;
    gameState.currentBet = bet;
    document.getElementById('potential-win').textContent = (bet * 2).toLocaleString();
}

function changeBet(delta) {
    const input = document.getElementById('bet-amount');
    let value = parseInt(input.value) || 10;
    value = Math.max(1, Math.min(1000, value + delta));
    input.value = value;
    updateBetInfo();
}

document.getElementById('bet-amount').addEventListener('input', updateBetInfo);

// Обработка клика по ракете (игра)
document.getElementById('click-area').addEventListener('click', async (e) => {
    if (gameState.isProcessing) return;
    
    const bet = gameState.currentBet;
    
    // Проверка баланса
    if (gameState.balance < bet) {
        showGameResult('❌ Недостаточно монет!', 'lose');
        if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred('error');
        }
        return;
    }
    
    // Проверка энергии
    if (gameState.energy < 10) {
        showGameResult('❌ Недостаточно энергии!', 'lose');
        if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred('warning');
        }
        return;
    }
    
    gameState.isProcessing = true;
    
    // Анимация клика
    const rocket = document.getElementById('rocket');
    const wrapper = rocket.parentElement;
    wrapper.classList.add('clicked');
    setTimeout(() => wrapper.classList.remove('clicked'), 200);
    
    // Показываем эффект клика
    showClickEffect(e.clientX, e.clientY);
    
    // Вибрация
    if (tg.HapticFeedback) {
        tg.HapticFeedback.impactOccurred('medium');
    }
    
    // Тратим энергию
    gameState.energy -= 10;
    
    // Списываем ставку
    gameState.balance -= bet;
    updateUI();
    
    // Определяем результат (50% шанс выиграть)
    const isWin = Math.random() > 0.5;
    const winAmount = isWin ? bet * 2 : 0;
    
    if (isWin) {
        gameState.balance += winAmount;
        showGameResult('🎉 ВЫИГРЫШ: +' + winAmount + ' 🪙', 'win');
        showFloatNumber(e.clientX, e.clientY, '+' + winAmount);
        if (tg.HapticFeedback) {
            tg.HapticFeedback.notificationOccurred('success');
        }
        createParticles();
    } else {
        showGameResult('😢 Проигрыш: -' + bet + ' 🪙', 'lose');
    }
    
    updateUI();
    
    // Отправляем на сервер
    try {
        await fetch('/api/game_result?init_data=' + encodeURIComponent(initData), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                bet: bet,
                win: isWin,
                winAmount: winAmount,
                energyUsed: 10
            })
        });
    } catch (err) {
        console.log('Server sync error:', err);
    }
    
    gameState.isProcessing = false;
});

function showClickEffect(x, y) {
    const effect = document.getElementById('click-effect');
    effect.style.left = x + 'px';
    effect.style.top = y + 'px';
    effect.classList.add('show');
    setTimeout(() => effect.classList.remove('show'), 500);
}

function showFloatNumber(x, y, text) {
    const el = document.createElement('div');
    el.className = 'float-number';
    el.textContent = text;
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 800);
}

function showGameResult(text, type) {
    const result = document.getElementById('game-result');
    result.textContent = text;
    result.className = 'game-result show ' + type;
    setTimeout(() => {
        result.classList.remove('show');
    }, 2000);
}

function createParticles() {
    const container = document.createElement('div');
    container.className = 'particles';
    document.body.appendChild(container);
    
    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 2 + 's';
        particle.style.background = ['#ffd700', '#ff6b35', '#4ade80'][Math.floor(Math.random() * 3)];
        container.appendChild(particle);
    }
    
    setTimeout(() => container.remove(), 3000);
}

// Навигация по вкладкам
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
});

// Покупка улучшений
async function buyUpgrade(type, cost) {
    if (gameState.balance < cost) {
        tg.showAlert('Недостаточно монет!');
        return;
    }
    
    gameState.balance -= cost;
    
    if (type === 'click') {
        gameState.profitPerClick += 1;
    } else if (type === 'energy') {
        gameState.maxEnergy += 100;
        gameState.energy += 100;
    }
    
    updateUI();
    
    if (tg.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
    
    try {
        await fetch('/api/buy_upgrade?init_data=' + encodeURIComponent(initData), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({type: type, cost: cost})
        });
    } catch (e) {}
    
    tg.showAlert('✅ Улучшение куплено!');
}

// Регенерация энергии
setInterval(() => {
    if (gameState.energy < gameState.maxEnergy) {
        gameState.energy = Math.min(gameState.energy + gameState.profitPerHour / 3600, gameState.maxEnergy);
        updateUI();
    }
}, 1000);

// Загрузка при старте
loadUser();
