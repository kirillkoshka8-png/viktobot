import asyncio
import json
import random
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.filters import Command

# Настройка логирования с автоматической очисткой (mode='w')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.txt", mode='w', encoding="utf-8"),
        logging.StreamHandler()
    ]
)

BOT_TOKEN = "8701412706:AAFR7oqTDGpBynMZ-_nGVLhHmLmCFJm-f2s"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Загружаем базу вопросов из JSON
try:
    with open("questions.json", "r", encoding="utf-8") as f:
        QUESTIONS = json.load(f)
    logging.info("База вопросов успешно загружена из файла JSON.")
except Exception as e:
    logging.critical(f"Критическая ошибка загрузки вопросов: {e}")

LEADERBOARD_FILE = "leaderboard.json"

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_leaderboard(data):
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка保存 таблицы лидеров: {e}")

users_data = {}

def get_themes_keyboard():
    """Клавиатура выбора игровых категорий"""
    buttons = [
        [InlineKeyboardButton(text="🏒 Хоккей", callback_data="theme_hockey")],
        [InlineKeyboardButton(text="🎬 Кино", callback_data="theme_cinema")],
        [InlineKeyboardButton(text="📜 История", callback_data="theme_history")],
        [InlineKeyboardButton(text="🌍 География", callback_data="theme_geography")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_keyboard(variants, show_hint_button=False):
    """Клавиатура с вариантами ответов"""
    buttons = []
    for variant in variants:
        buttons.append([
            InlineKeyboardButton(
                text=variant, 
                callback_data=f"ans_{variant}"
            )
        ])
    if show_hint_button:
        buttons.append([
            InlineKeyboardButton(
                text="🤔 Подсказка 50/50", 
                callback_data="hint_50_50"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def send_question(message: Message, chat_id: int):
    """Выбирает и отправляет уникальный вопрос или завершает игру"""
    user_theme = users_data[chat_id]["theme"]
    user_lvl = str(users_data[chat_id]["level"])
    
    all_questions = QUESTIONS[user_theme][user_lvl]
    answered = users_data[chat_id]["answered_questions"]
    
    # Фильтруем вопросы, исключая уже заданные
    available_questions = [
        q for q in all_questions if q["text"] not in answered
    ]
    
    # ЛОГИКА ФИНАЛА: если уникальные вопросы кончились НА 3-М УРОВНЕ
    if not available_questions and user_lvl == "3":
        logging.info(f"Игрок {chat_id} полностью прошел тему {user_theme}!")
        
        data = users_data[chat_id]
        accuracy = (data["correct_answers"] / data["total_answers"]) * 100
        
        finish_text = (
            "🎉🏆 **ПОЗДРАВЛЯЕМ! ВЫ ПОЛНОСТЬЮ ПРОШЛИ ВИКТОРИНУ!** 🏆🎉\n\n"
            f"Вы ответили на все самые сложные вопросы в этой теме!\n\n"
            f"📊 **Ваши итоги за этот забег:**\n"
            f"💰 Набрано очков: {data['score']}\n"
            f"🎯 Точность ответов: {accuracy:.1f}%\n\n"
            "Вы можете выбрать новую тему для игры ниже:"
        )
        await bot.send_message(
            chat_id=chat_id, 
            text=finish_text, 
            parse_mode="Markdown",
            reply_markup=get_themes_keyboard()
        )
        return

    # Если вопросы кончились на 1 или 2 уровне, просто сбрасываем историю для этого уровня
    if not available_questions:
        lvl_texts = [q["text"] for q in all_questions]
        users_data[chat_id]["answered_questions"] = [
            t for t in answered if t not in lvl_texts
        ]
        available_questions = all_questions
        logging.info(f"Вопросы уровня {user_lvl} закончились. История сброшена.")

    question = random.choice(available_questions)
    users_data[chat_id]["current_question"] = question
    has_hint = users_data[chat_id]["hint_available"]
    
    text = (
        f"📊 Сложность: {user_lvl}\n"
        f"💰 Очки: {users_data[chat_id]['score']}\n\n"
        f"❓ Вопрос: {question['text']}"
    )
    await bot.send_message(
        chat_id=chat_id, 
        text=text, 
        reply_markup=get_keyboard(
            question['variants'], 
            show_hint_button=has_hint
        )
    )

@dp.message(Command("stats"))
async def show_stats(message: Message):
    """Выводит личную статистику и точность в процентах"""
    chat_id = message.chat.id
    logging.info(f"Игрок {chat_id} запросил личную статистику.")
    
    if chat_id not in users_data or users_data[chat_id]["total_answers"] == 0:
        await message.answer("📈 У вас пока нет сыгранных матчей.")
        return
        
    data = users_data[chat_id]
    accuracy = (data["correct_answers"] / data["total_answers"]) * 100
    
    stats_text = (
        "📊 **АНАЛИТИКА ТВОИХ РЕЗУЛЬТАТОВ** 📊\n\n"
        f"🏆 Ваш рекорд: {data['high_score']} очков\n"
        f"📝 Вопросов сыграно: {data['total_answers']}\n"
        f"✅ Правильных: {data['correct_answers']}\n"
        f"🎯 Точность: {accuracy:.1f}%\n\n"
        "Чтобы начать заново, введите /start"
    )
    await message.answer(stats_text, parse_mode="Markdown")

@dp.message(Command("top"))
async def show_top(message: Message):
    """Выводит глобальную таблицу рекордов Топ-5"""
    logging.info("Запрошена глобальная таблица лидеров.")
    leaderboard = load_leaderboard()
    if not leaderboard:
        await message.answer("🏆 Таблица лидеров пока пуста. Станьте первым!")
        return
        
    sorted_top = sorted(leaderboard.items(), key=lambda x: x, reverse=True)[:5]
    top_text = "🏆 **ГЛОБАЛЬНАЯ ТАБЛИЦА ЛИДЕРОВ (ТОП-5)** 🏆\n\n"
    for index, (user_name, score) in enumerate(sorted_top, 1):
        top_text += f"{index}. 👤 {user_name} — **{score}** очков\n"
    await message.answer(top_text, parse_mode="Markdown")

@dp.message(Command("start"))
async def start_game(message: Message):
    """Инициализация игры и выбор темы"""
    chat_id = message.chat.id
    user_name = message.from_user.full_name
    logging.info(f"Пользователь {user_name} ({chat_id}) запустил новую сессию.")
    
    leaderboard = load_leaderboard()
    saved_high_score = leaderboard.get(user_name, 0)
    
    users_data[chat_id] = {
        "theme": None, "level": 1, "streak": 0, "score": 0, 
        "current_question": None, "total_answers": 0, 
        "correct_answers": 0, "high_score": saved_high_score, 
        "hint_available": True, "answered_questions": [], "user_name": user_name
    }
    await message.answer(
        f"Привет, {user_name}! Выберите тему викторины.\n"
        f"Посмотреть таблицу лидеров: /top", 
        reply_markup=get_themes_keyboard()
    )

@dp.callback_query(F.data.startswith("theme_"))
async def handle_theme_choice(call: CallbackQuery):
    """Запуск викторины после клика на категорию"""
    chat_id = call.message.chat.id
    if chat_id not in users_data:
        await call.answer()
        return
        
    chosen_theme = call.data.replace("theme_", "")
    users_data[chat_id]["theme"] = chosen_theme
    logging.info(f"Игрок {chat_id} выбрал тему: {chosen_theme}")
    
    await call.message.edit_reply_markup(reply_markup=None)
    themes_ru = {
        "hockey": "Хоккей", "cinema": "Кино", 
        "history": "История", "geography": "География"
    }
    await call.message.answer(f"🏁 Выбрана тема: {themes_ru[chosen_theme]}. Начинаем!")
    await send_question(call.message, chat_id)
    await call.answer()

@dp.callback_query(F.data == "hint_50_50")
async def handle_hint(call: CallbackQuery):
    """Классическая подсказка 50/50 на две кнопки"""
    chat_id = call.message.chat.id
    if chat_id not in users_data or not users_data[chat_id]["hint_available"]:
        await call.answer()
        return
        
    current_q = users_data[chat_id]["current_question"]
    correct_ans = current_q["correct"]
    
    wrong_variants = [v for v in current_q["variants"] if v != correct_ans]
    wrong_to_keep = random.choice(wrong_variants)
    
    new_variants = [correct_ans, wrong_to_keep]
    random.shuffle(new_variants)
    
    users_data[chat_id]["hint_available"] = False
    logging.info(f"Игрок {chat_id} применил подсказку 50/50.")
    
    removed_variants = [v for v in current_q["variants"] if v not in new_variants]
    removed_text = ", ".join([f"'{v}'" for v in removed_variants])
    
    await call.message.edit_reply_markup(
        reply_markup=get_keyboard(new_variants, show_hint_button=False)
    )
    await call.message.answer(f"💥 Подсказка 50/50 использована! Удалены варианты: {removed_text}.")
    await call.answer()

@dp.callback_query(F.data.startswith("ans_"))
async def handle_answer(call: CallbackQuery):
    """Проверка ответа и адаптивное изменение сложности"""
    chat_id = call.message.chat.id
    if chat_id not in users_data or not users_data[chat_id]["current_question"]:
        await call.answer()
        return

    user_answer = call.data.replace("ans_", "")
    current_q = users_data[chat_id]["current_question"]
    users_data[chat_id]["answered_questions"].append(current_q["text"])
    
    await call.message.edit_reply_markup(reply_markup=None)
    users_data[chat_id]["total_answers"] += 1

    if user_answer == current_q["correct"]:
        users_data[chat_id]["score"] += users_data[chat_id]["level"] * 10
        users_data[chat_id]["streak"] += 1
        users_data[chat_id]["correct_answers"] += 1
        logging.info(f"Игрок {chat_id} ответил ВЕРНО.")
        
        if users_data[chat_id]["score"] > users_data[chat_id]["high_score"]:
            users_data[chat_id]["high_score"] = users_data[chat_id]["score"]
            leaderboard = load_leaderboard()
            leaderboard[users_data[chat_id]["user_name"]] = users_data[chat_id]["high_score"]
            save_leaderboard(leaderboard)
            
        await call.message.answer("✅ Правильно!")
        
        if users_data[chat_id]["streak"] == 2 and users_data[chat_id]["level"] < 3:
            users_data[chat_id]["level"] += 1
            users_data[chat_id]["streak"] = 0
            await call.message.answer("🚀 Сложность повышена!")
    else:
        users_data[chat_id]["streak"] = 0
        logging.info(f"Игрок {chat_id} ошибся.")
        await call.message.answer(f"❌ Ошибка! Ответ: {current_q['correct']}")
        
        if users_data[chat_id]["level"] > 1:
            users_data[chat_id]["level"] -= 1
            await call.message.answer("📉 Сложность снижена.")

    await call.answer()
    await send_question(call.message, chat_id)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("Бот на aiogram успешно запущен...")
    asyncio.run(main())