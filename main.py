import os
from aiogram import Bot, types, executor
from aiogram.types import Message
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.utils.executor import start_webhook
import logging
import psycopg2
from urllib.parse import urlparse
from transactions_parser import parsing
import asyncio
import datetime
# from dotenv import load_dotenv
# load_dotenv()

# Bot initialization
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
logging.basicConfig(level=logging.INFO)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

# Admin id define
admin = os.getenv('ADMIN_ID')

# Database setup
DB_URL = os.getenv('DATABASE_URL')
db_parse = urlparse(DB_URL)
db_username = db_parse.username
db_password = db_parse.password
db_name = db_parse.path[1:]
db_hostname = db_parse.hostname
db_port = db_parse.port
conn = psycopg2.connect(
    database=db_name,
    user=db_username,
    password=db_password,
    host=db_hostname,
    port=db_port
)
cur = conn.cursor()
'''
Database structure:
- "*" means preset value 
column(0): id; integer (default = -1)
*column(1): username; char(300)
*column(2): full_name; char(300)
*column(3): wallet_id; char(64) (contains lolcoin wallet id of len 64)
column(4): balance; integer (default = 0)
column(5): is_active; boolean (default = false)
'''


# States initialization
class SG(StatesGroup):
    BasicState = State()
    ReportState = State()


# Keyboards initialization
reportkb = types.ReplyKeyboardMarkup(resize_keyboard=True)
reportkb.add(types.InlineKeyboardButton(text='Отменить ❌'))

basekb = types.ReplyKeyboardMarkup(resize_keyboard=True)
button1 = types.InlineKeyboardButton(text='Баланс 💸')
button2 = types.InlineKeyboardButton(text="Жалоба ❗")
button3 = types.InlineKeyboardButton(text='Список предложений 📄')
button4 = types.InlineKeyboardButton(text='Заключить сделку 📝')
button5 = types.InlineKeyboardButton(text='Выставить на продажу 💰')
button6 = types.InlineKeyboardButton(text='Текущие сделки 💼')
button7 = types.InlineKeyboardButton(text="Команды ❔")
button8 = types.InlineKeyboardButton(text="FAQ ❓")
basekb.row(button1, button2).row(button3, button4).row(button5, button6).row(button7, button8)


# Switching state and keyboard to basic function
async def switch_to_base(message: Message):
    await SG.BasicState.set()
    await message.answer("Выберите дейсвтие:", reply_markup=basekb)


# Main part with all bot commands:


# Sending commands list function
async def help_message(message: Message):
    await message.answer('- Как пополнить баланс вы можете узнать при помощи команды /balance.\n'
                         '- Посмотреть текущие товары и услуги можно командой /services.\n'
                         '- Оформить заказ вы можете с помощью /buy.\n'
                         '- Чтобы выставить товар на продажу используйте /sell. \n'
                         '- Просмотр статуса текущих сделок осушествляется комадой /status \n'
                         '- Если у вас остались вопросы, возможно вы найдете ответы, введя команду /faq, в противном'
                         ' случае задайте вопрос админу при помощи всё того же /report.'
                         '- Если вам понадобится перечитать это сообщение, напишите /help.\n'
                         'Вы также можете использовать встроенную клавиатуру вместо того, чтобы писать команды.')


# Checking if user is in db when starting using bot. If he is not,
# he won't be able to use bot commands until admin add him to users table.
@dp.message_handler()
async def start(message: Message):
    username = '@' + message.from_user.username
    cur.execute(f"""SELECT * FROM users WHERE username = '{username}'""")
    result = cur.fetchone()
    if not result:
        username = message.from_user.first_name + ' ' + message.from_user.last_name
        cur.execute(f"""SELECT * FROM users WHERE username = '{username}'""")
        result = cur.fetchone()
    if result:
        if not result[5]:
            cur.execute(
                f"""UPDATE users SET is_active = true WHERE username = '{username}'"""
            )
            cur.execute(
                f"""UPDATE users SET id = {message.from_user.id} WHERE username = '{username}'"""
            )
            conn.commit()
            await message.answer(f'Приветствую, {result[1]}! Мы опредеили вас, как {result[2].strip()}. Если это не так'
                                 f', пожалуйста, напишите нам свои имя и фамилию при помощи команды /report. Если '
                                 f'этого не сделать, вы будете привязаны к чужому кошельку и не сможете пополнять ваш '
                                 f'баланс.')
            await help_message(message)
            await message.answer('Приятного пользования 🙃')
            await switch_to_base(message)
        else:
            if result[0] != message.from_user.id:
                await message.answer('Извините, кажется произошла какая-то накладка, видимо у вас совпал ник в '
                                     'телеграм-аккаунте с кем-то другим. Пожалуйста, напишите нам свои имя и '
                                     'фамилию при помощи команды /report, чтобы мы исправили эту ошибку.')
            else:
                await message.answer(f'Ещё раз приветствую вас, {result[1]}! Бот был перезапущен и ваша сессия была '
                                     f'оборвана, перенаправляем вас обрано...')
                await switch_to_base(message)
    else:
        await message.answer('Извините, мы не смогли определить вас как ученика лагеря ЛОЛ. Увы, мы не смогли найти '
                             'телеграм-аккаунт каждого, пожалуйста, напишите нам свои имя и фамилию при помощи '
                             'команды /report')


# Checking balance command
@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Баланс 💸', '/balance'])
async def balance_command(message: Message):
    cur.execute(f"""SELECT balance FROM users WHERE id = '{message.from_user.id}'""")
    user_balance = float(cur.fetchone()[0]) / 100
    await message.answer(f'На вашем счету {user_balance} lolcoin\nЧтобы пополнить счет переведите от 2 lolcoin на '
                         f'lolcoin_platform.near. При любом переводе 1 lolcoin будет взят в качестве комиссии, '
                         f'а остальное будет зачислено на ваш баланс. После перевода в течении следующих 5-ти минут '
                         f'система прочитает ваш перевод и вам придёт сообщение о успешном пополнении баланса. Если '
                         f'же этого не произошло, убедитесь что вы перевели не менее 2 lolcoin, после чего напишите о '
                         f'проблеме через /report.')


# Report command
@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Жалоба ❗', '/report'])
async def report_command(message: Message):
    await SG.ReportState.set()
    await message.answer('Следующим сообщением напишите текст вашего обращения. Если вы передумали, напишите команду '
                         '/cancel, или выберете соответствующую опцию в вашей встроенной клавиатуре.',
                         reply_markup=reportkb)


@dp.message_handler(state=SG.ReportState)
async def report_send(message: Message):
    if message.text == '/cancel' or message.text == 'Отменить ❌':
        await message.answer('Действие успешно отменено ✅')
        await switch_to_base(message)
    else:
        await bot.send_message(admin, message.text)
        await message.answer('Репорт успешно отправлен ✅')
        await switch_to_base(message)


@dp.message_handler(state=SG.BasicState, content_types=['text'], text=['Команды ❔', '/help'])
async def help_command(message: Message):
    await help_message(message)


@dp.message_handler(state=SG.BasicState)
async def unknown_command(message: Message):
    await message.answer("Команда не была опознана.")


# Checking for new transfer every "wait_for" seconds
async def check(wait_for):
    print("Debug: check is awaited")

    while True:
        print("Debug: inside while")
        await asyncio.sleep(wait_for)
        print("after sleep")
        transactions = parsing()
        if transactions:
            for transaction in transactions:
                logging.warning(transaction["amount"])
                cur.execute(f"""SELECT * FROM users WHERE wallet_id = '{transaction["sender"]}'""")
                result = cur.fetchone()
                if result and transaction["amount"] >= 200:
                    result = [result[0], result[4]]
                    cur.execute(
                        f"""UPDATE users SET balance = {result[1] + transaction["amount"] - 100} WHERE id = '{result[0]}'"""
                    )
                    await bot.send_message(result[0], f"✅ Вы перевели на платформу {transaction['amount'] / 100}"
                                                      f" lolcoin, из которых {transaction['amount'] / 100 - 1} были"
                                                      " зачислены на баланс, а оставшийся 1 ЛОЛкоин взят в качестве"
                                                      " комиссии.")
            conn.commit()


# Bot start
if __name__ == '__main__':
    future = asyncio.ensure_future(check(60))
    executor.start_polling(dp, skip_updates=True)
