"""Independent Ukrainian-language beauty booking demo (not affiliated with AM NAIL)."""
import asyncio
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN', '').strip()
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
DB = Path(__file__).with_name('bookings.sqlite3')
router = Router()
SERVICES = {
    'classic': ('Манікюр', 450),
    'gel': ('Манікюр + гель-лак', 650),
    'remove': ('Зняття покриття', 200),
    'pedicure': ('Педикюр', 750),
}

class Booking(StatesGroup):
    service = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            day TEXT NOT NULL,
            time TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            created_at TEXT NOT NULL
        )''')

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📅 Записатися', callback_data='book')],
        [InlineKeyboardButton(text='💅 Послуги та ціни', callback_data='services')],
        [InlineKeyboardButton(text='📍 Контакти', callback_data='contacts')],
        [InlineKeyboardButton(text='ℹ️ Про демоверсію', callback_data='about')],
    ])

def service_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'{name} — {price} грн', callback_data=f'svc:{key}')]
        for key, (name, price) in SERVICES.items()
    ] + [[InlineKeyboardButton(text='↩️ Меню', callback_data='home')]])

def days_keyboard():
    today = date.today()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=(today + timedelta(days=i)).strftime('%d.%m.%Y'), callback_data=f'day:{(today + timedelta(days=i)).isoformat()}')]
        for i in range(1, 8)
    ])

def times_keyboard():
    slots = ['09:00', '10:30', '12:00', '13:30', '15:00', '16:30', '18:00']
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=f'time:{t}') for t in slots[i:i+2]]
        for i in range(0, len(slots), 2)
    ])

def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Надіслати заявку', callback_data='confirm:yes')],
        [InlineKeyboardButton(text='❌ Скасувати', callback_data='confirm:no')],
    ])

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Вітаємо! 💅\nЦе незалежна демонстрація Telegram-бота для запису в beauty-студію.\nНе є офіційним ботом AM NAIL.\n\nОберіть дію:', reply_markup=menu())

@router.message(Command('cancel'))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Дію скасовано.', reply_markup=ReplyKeyboardRemove())
    await message.answer('Головне меню:', reply_markup=menu())

@router.callback_query(F.data == 'home')
async def home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer('Головне меню:', reply_markup=menu())
    await callback.answer()

@router.callback_query(F.data == 'services')
async def services(callback: CallbackQuery):
    await callback.message.answer('💅 Демонстраційні послуги та ціни (не прайс AM NAIL):', reply_markup=service_keyboard())
    await callback.answer()

@router.callback_query(F.data == 'contacts')
async def contacts(callback: CallbackQuery):
    await callback.message.answer('📍 Це демонстраційний бот. Реальні контакти та адресу студії буде додано лише після узгодження з власником.\n\nПовернутися: /start')
    await callback.answer()

@router.callback_query(F.data == 'about')
async def about(callback: CallbackQuery):
    await callback.message.answer('ℹ️ Незалежний прототип для демонстрації можливостей автоматизації запису. Заявки не створюють реального бронювання. Не надсилайте справжні персональні дані під час тестування.')
    await callback.answer()

@router.callback_query(F.data == 'book')
async def book(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Booking.service)
    await callback.message.answer('Оберіть послугу:', reply_markup=service_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith('svc:'))
async def choose_service(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(':', 1)[1]
    if key not in SERVICES:
        await callback.answer('Невідома послуга', show_alert=True)
        return
    await state.update_data(service=key)
    await state.set_state(Booking.day)
    await callback.message.answer('📆 Оберіть бажану дату (не гарантує вільний час):', reply_markup=days_keyboard())
    await callback.answer()

@router.callback_query(Booking.day, F.data.startswith('day:'))
async def choose_day(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.split(':', 1)[1]
    try:
        chosen = date.fromisoformat(raw)
    except ValueError:
        await callback.answer('Невірна дата', show_alert=True)
        return
    if not date.today() < chosen <= date.today() + timedelta(days=7):
        await callback.answer('Дата вже недоступна. Почніть з /start', show_alert=True)
        return
    await state.update_data(day=raw)
    await state.set_state(Booking.time)
    await callback.message.answer('🕒 Оберіть бажаний час (адміністратор підтверджує вручну):', reply_markup=times_keyboard())
    await callback.answer()

@router.callback_query(Booking.time, F.data.startswith('time:'))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(':', 1)[1]
    if value not in ['09:00', '10:30', '12:00', '13:30', '15:00', '16:30', '18:00']:
        await callback.answer('Невірний час', show_alert=True)
        return
    await state.update_data(time=value)
    await state.set_state(Booking.name)
    await callback.message.answer('Як до вас звертатися? Для демо можна ввести вигадане ім’я.')
    await callback.answer()

@router.message(Booking.name, F.text)
async def name(message: Message, state: FSMContext):
    value = message.text.strip()
    if not 2 <= len(value) <= 60:
        await message.answer('Введіть ім’я від 2 до 60 символів.')
        return
    await state.update_data(name=value)
    await state.set_state(Booking.phone)
    await message.answer('Введіть тестовий номер телефону (наприклад, +380000000000). Не використовуйте реальні дані у демо.')

@router.message(Booking.phone, F.text)
async def phone(message: Message, state: FSMContext):
    value = message.text.strip()
    if len(value) > 20 or not (value.startswith('+') and value[1:].isdigit() and 10 <= len(value[1:]) <= 15):
        await message.answer('Вкажіть номер у форматі +380XXXXXXXXX (для демо — вигаданий).')
        return
    await state.update_data(phone=value)
    data = await state.get_data()
    service_name, price = SERVICES[data['service']]
    await state.set_state(Booking.confirm)
    await message.answer(
        f'📝 Перевірте заявку:\nПослуга: {service_name} ({price} грн, демо)\nДата: {data["day"]}\nЧас: {data["time"]}\nІм’я: {data["name"]}\nТелефон: {data["phone"]}\n\nЦе лише тестова заявка, а не реальний запис.',
        reply_markup=confirm_keyboard()
    )

@router.callback_query(Booking.confirm, F.data == 'confirm:no')
async def no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer('Заявку скасовано. /start')
    await callback.answer()

@router.callback_query(Booking.confirm, F.data == 'confirm:yes')
async def yes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not all(k in data for k in ('service', 'day', 'time', 'name', 'phone')):
        await callback.answer('Почніть з /start', show_alert=True)
        return
    with sqlite3.connect(DB) as con:
        cur = con.execute('INSERT INTO bookings (user_id, service, day, time, name, phone, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (callback.from_user.id, data['service'], data['day'], data['time'], data['name'], data['phone'], datetime.now().isoformat(timespec='seconds')))
        booking_id = cur.lastrowid
    service_name, _ = SERVICES[data['service']]
    await state.clear()
    await callback.message.answer(f'✅ Тестову заявку №{booking_id} збережено! Це не підтвердження реального запису. /start')
    await callback.answer()
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, f'🔔 Нова тестова заявка №{booking_id}\nПослуга: {service_name}\nДата: {data["day"]} {data["time"]}\nІм’я: {data["name"]}\nТелефон: {data["phone"]}\nTelegram ID: {callback.from_user.id}')
        except Exception:
            logging.exception('Cannot notify admin; ensure admin has started bot')

@router.message(Command('myid'))
async def myid(message: Message):
    await message.answer(f'Ваш Telegram ID: {message.from_user.id}')

@router.message(Command('orders'))
async def orders(message: Message):
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        await message.answer('Команда доступна лише адміністратору.')
        return
    with sqlite3.connect(DB) as con:
        rows = con.execute('SELECT id, service, day, time, name FROM bookings ORDER BY id DESC LIMIT 10').fetchall()
    if not rows:
        await message.answer('Заявок поки немає.')
        return
    await message.answer('Останні заявки:\n' + '\n'.join(f'#{rid}: {SERVICES[svc][0]}, {day} {time}, {person}' for rid, svc, day, time, person in rows))

@router.message()
async def fallback(message: Message):
    await message.answer('Використайте /start для відкриття меню або /cancel для скасування.')

async def main():
    if not TOKEN or TOKEN == 'PASTE_YOUR_BOTFATHER_TOKEN_HERE':
        raise RuntimeError('Set BOT_TOKEN in .env before running')
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
