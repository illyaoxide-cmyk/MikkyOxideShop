import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- НАСТРОЙКИ ---
BOT_TOKEN = "9127543916:AAEk5EsiIrYDOiq5iDG2ef7s9rYL52RluBA"
ADMIN_ID = 8683926371  # Твой ID администратора
CARD_NUMBER = "4441111008011946"
BANNER_URL = "https://files.catbox.moe/la3ubw.jpg"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    
    # Таблица товаров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            name TEXT,
            price INTEGER
        )
    """)
    
    # Таблица ключей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            key_text TEXT,
            is_used INTEGER DEFAULT 0
        )
    """)
    
    # Таблица заказов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product_id INTEGER,
            product_name TEXT,
            price INTEGER,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    
    # Заполнение дефолтных товаров, если база пуста
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        default_items = [
            ("Android", "Cryme", 200),
            ("Android", "Magic Vip", 350),
            ("Android", "Magic Lite", 150),
            ("iOS", "Ultima", 400),
            ("iOS", "Aqrex", 300)
        ]
        cursor.executemany("INSERT INTO products (category, name, price) VALUES (?, ?, ?)", default_items)
        conn.commit()
    conn.close()

# --- СОСТОЯНИЯ (FSM) ---
class BuyState(StatesGroup):
    waiting_for_receipt = State()
    product_id = State()

class AddKeyState(StatesGroup):
    choosing_product = State()
    entering_key = State()

# --- КЛАВИАТУРЫ ---
def main_menu(user_id):
    buttons = [
        [KeyboardButton(text="🛍 Каталог софта")],
        [KeyboardButton(text="👤 Мои покупки"), KeyboardButton(text="ℹ️ Оплата и реквизиты")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def catalog_categories_markup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Android", callback_data="cat_Android")],
        [InlineKeyboardButton(text="🍏 iOS", callback_data="cat_iOS")]
    ])

# --- ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer_photo(
        photo=BANNER_URL,
        caption=(
            "👋 <b>Добро пожаловать в лучший магазин читов!</b>\n\n"
            "🔥 У нас самый надежный софт для Android и iOS.\n"
            "Выберите категорию в каталоге ниже, чтобы сделать покупку 👇"
        ),
        parse_mode="HTML",
        reply_markup=main_menu(message.from_user.id)
    )

@dp.message(F.text == "ℹ️ Оплата и реквизиты")
async def info_payment(message: types.Message):
    await message.answer(
        f"💳 <b>Инструкция по оплате:</b>\n\n"
        f"1. Переведите точную сумму на карту UAH:\n"
        f"<code>{CARD_NUMBER}</code>\n\n"
        f"2. После оплаты отправьте скриншот/чек в этот чат.\n"
        f"3. Администратор проверит перевод, после чего бот **автоматически выдаст ключ**!",
        parse_mode="HTML"
    )

@dp.message(F.text == "🛍 Каталог софта")
async def show_catalog(message: types.Message):
    await message.answer("📂 Выберите операционную систему:", reply_markup=catalog_categories_markup())

@dp.callback_query(F.data.startswith("cat_"))
async def show_products_by_category(callback: types.CallbackQuery):
    category = callback.data.split("_")[1]
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products WHERE category = ?", (category,))
    products = cursor.fetchall()
    conn.close()

    if not products:
        await callback.answer("В этой категории пока нет товаров.", show_alert=True)
        return

    keyboard = []
    for pid, name, price in products:
        conn = sqlite3.connect("cheat_shop.db")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM keys WHERE product_id = ? AND is_used = 0", (pid,))
        stock = cur.fetchone()[0]
        conn.close()

        status_stock = f"🟢 В наличии ({stock})" if stock > 0 else "🔴 Нет в наличии"
        keyboard.append([InlineKeyboardButton(text=f"{name} — {price} грн [{status_stock}]", callback_data=f"prod_{pid}")])

    keyboard.append([InlineKeyboardButton(text="🔙 Назад к категориям", callback_data="back_to_cats")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_caption(
        caption=f"📱 Категория: <b>{category}</b>\nВыберите товар:",
        parse_mode="HTML",
        reply_markup=markup
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(callback: types.CallbackQuery):
    await callback.message.edit_caption(
        caption="📂 Выберите операционную систему:",
        reply_markup=catalog_categories_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("prod_"))
async def product_card(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT category, name, price FROM products WHERE id = ?", (pid,))
    prod = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM keys WHERE product_id = ? AND is_used = 0", (pid,))
    stock = cursor.fetchone()[0]
    conn.close()

    if not prod:
        await callback.answer("Товар не найден.", show_alert=True)
        return

    category, name, price = prod

    keyboard = []
    if stock > 0:
        keyboard.append([InlineKeyboardButton(text=f"💳 Купить за {price} грн", callback_data=f"buy_{pid}")])
    else:
        keyboard.append([InlineKeyboardButton(text="❌ Нет в наличии", callback_data="none")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"cat_{category}")])

    await callback.message.edit_caption(
        caption=(
            f"🎮 <b>{name}</b>\n\n"
            f"📌 Платформа: {category}\n"
            f"💰 Цена: <b>{price} грн</b>\n"
            f"📦 Доступно ключей: <b>{stock} шт.</b>\n\n"
            f"Для покупки нажмите кнопку ниже и переведите средства на карту."
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def start_buy(callback: types.CallbackQuery, state: FSMContext):
    pid = int(callback.data.split("_")[1])
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (pid,))
    prod = cursor.fetchone()
    conn.close()

    if not prod:
        await callback.answer("Товар не найден", show_alert=True)
        return

    name, price = prod
    await state.update_data(product_id=pid, product_name=name, price=price)
    
    await callback.message.answer(
        f"🧾 Вы оформляете покупку: <b>{name}</b> ({price} грн).\n\n"
        f"1️⃣ Сделайте перевод на карту:\n<code>{CARD_NUMBER}</code>\n\n"
        f"2️⃣ <b>Отправьте скриншот (фото) чека в этот чат сообщением!</b>",
        parse_mode="HTML"
    )
    await state.set_state(BuyState.waiting_for_receipt)
    await callback.answer()

@dp.message(BuyState.waiting_for_receipt, F.photo)
async def receive_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pid = data['product_id']
    pname = data['product_name']
    price = data['price']
    
    photo_id = message.photo[-1].file_id
    username = message.from_user.username or f"id{message.from_user.id}"
    
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, username, product_id, product_name, price, status) VALUES (?, ?, ?, ?, ?, 'pending')",
        (message.from_user.id, username, pid, pname, price)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    admin_markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm_yes_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_no_{order_id}")
        ]
    ])

    await bot.send_photo(
        ADMIN_ID,
        photo=photo_id,
        caption=(
            f"🔔 <b>Новый заказ #{order_id}!</b>\n\n"
            f"👤 Покупатель: @{username} (ID: <code>{message.from_user.id}</code>)\n"
            f"📦 Товар: {pname}\n"
            f"💰 Сумма: {price} грн"
        ),
        parse_mode="HTML",
        reply_markup=admin_markup
    )

    await message.answer("✅ Чек успешно отправлен администратору!\nОжидайте проверки. Ключ придет сюда автоматически после подтверждения.")
    await state.clear()

@dp.message(BuyState.waiting_for_receipt)
async def wrong_receipt_format(message: types.Message):
    await message.answer("⚠️ Пожалуйста, отправьте именно **фотографию (скриншот) чека** об оплате.")

# --- АДМИН-ПАНЕЛЬ ---
@dp.message(F.text == "⚙️ Админ-панель")
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ключ", callback_data="adm_add_key")],
        [InlineKeyboardButton(text="📊 Статистика / Остатки", callback_data="adm_stats")]
    ])
    await message.answer("⚙️ <b>Панель администратора:</b>", parse_mode="HTML", reply_markup=markup)

@dp.callback_query(F.data == "adm_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, name FROM products")
    products = cursor.fetchall()
    
    text = "📊 <b>Остатки ключей по товарам:</b>\n\n"
    for pid, cat, name in products:
        cursor.execute("SELECT COUNT(*) FROM keys WHERE product_id = ? AND is_used = 0", (pid,))
        count = cursor.fetchone()[0]
        text += f"• [{cat}] {name}: <b>{count} шт.</b> доступно\n"
    conn.close()

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "adm_add_key")
async def admin_add_key_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, name FROM products")
    products = cursor.fetchall()
    conn.close()

    keyboard = []
    for pid, cat, name in products:
        keyboard.append([InlineKeyboardButton(text=f"[{cat}] {name}", callback_data=f"select_prod_{pid}")])
    
    await callback.message.answer("Выберите товар, к которому хотите добавить ключ:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()

@dp.callback_query(F.data.startswith("select_prod_"))
async def select_product_for_key(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    pid = int(callback.data.split("_")[2])
    await state.update_data(product_id=pid)
    
    await callback.message.answer("✏️ Введите сам ключ (или несколько ключей, каждый с новой строки):")
    await state.set_state(AddKeyState.entering_key)
    await callback.answer()

@dp.message(AddKeyState.entering_key)
async def save_keys(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    pid = data['product_id']
    
    raw_keys = message.text.strip().split("\n")
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    
    added_count = 0
    for key in raw_keys:
        key = key.strip()
        if key:
            cursor.execute("INSERT INTO keys (product_id, key_text, is_used) VALUES (?, ?, 0)", (pid, key))
            added_count += 1
            
    conn.commit()
    conn.close()
    
    await state.clear()
    await message.answer(f"✅ Успешно добавлено ключей: <b>{added_count} шт.</b>", parse_mode="HTML")

# --- ПОДТВЕРЖДЕНИЕ ИЛИ ОТКЛОНЕНИЕ ЗАКАЗА АДМИНОМ ---
@dp.callback_query(F.data.startswith("adm_yes_"))
async def approve_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback.data.split("_")[2])
    
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, product_id, product_name FROM orders WHERE id = ? AND status = 'pending'", (order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        await callback.answer("Заказ уже обработан или не найден.", show_alert=True)
        return
    
    user_id, pid, pname = order
    
    cursor.execute("SELECT id, key_text FROM keys WHERE product_id = ? AND is_used = 0 LIMIT 1", (pid,))
    key_row = cursor.fetchone()
    
    if not key_row:
        conn.close()
        await callback.answer("❌ Ошибка: Нет свободных ключей для этого товара в базе! Сначала добавьте ключ.", show_alert=True)
        return
    
    key_id, key_text = key_row
    
    cursor.execute("UPDATE keys SET is_used = 1 WHERE id = ?", (key_id,))
    cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    
    try:
        await bot.send_message(
            user_id,
            f"🎉 <b>Оплата подтверждена! Ваш заказ готов:</b>\n\n"
            f"📦 Товар: <b>{pname}</b>\n"
            f"🔑 Ключ активации:\n<code>{key_text}</code>\n\n"
            f"Спасибо за покупку!",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить сообщение пользователю: {e}")

    await callback.message.edit_caption(
        caption=callback.message.caption + f"\n\n✅ <b>СТАТУС: Одобрено (Ключ выдан)</b>",
        parse_mode="HTML"
    )
    await callback.answer("Оплата подтверждена, ключ отправлен клиенту!")

@dp.callback_query(F.data.startswith("adm_no_"))
async def reject_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    order_id = int(callback.data.split("_")[2])
    
    conn = sqlite3.connect("cheat_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    
    if order:
        user_id = order[0]
        cursor.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
        conn.commit()
        
        try:
            await bot.send_message(
                user_id,
                "❌ К сожалению, ваш платеж был **отклонен** администратором.\nЕсли это ошибка, обратитесь в поддержку.",
                parse_mode="HTML"
            )
        except:
            pass
            
    conn.close()
    
    await callback.message.edit_caption(
        caption=callback.message.caption + f"\n\n❌ <b>СТАТУС: Отклонено</b>",
        parse_mode="HTML"
    )
    await callback.answer("Заказ отклонен.")

# --- ЗАПУСК БОТА ---
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
