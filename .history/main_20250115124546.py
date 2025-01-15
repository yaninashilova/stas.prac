import telebot
from telebot import types
import requests
from telebot import apihelper
import json
import os

# Настройка прокси (если требуется)
# apihelper.proxy = {
#     'https': 'socks5://user:password@host:port'  # Замените на свои данные
# }

# Увеличьте тайм-аут для запросов (в секундах)
apihelper.READ_TIMEOUT = 30
apihelper.CONNECT_TIMEOUT = 30

# Замените 'YOUR_TELEGRAM_BOT_TOKEN' на токен вашего бота
bot = telebot.TeleBot('YOUR_TELEGRAM_BOT_TOKEN')

# Файл для хранения просмотренных рецептов
VIEWED_RECIPES_FILE = "viewed_recipes.json"

# Загрузка просмотренных рецептов из файла
def load_viewed_recipes():
    if os.path.exists(VIEWED_RECIPES_FILE):
        with open(VIEWED_RECIPES_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

# Сохранение просмотренных рецептов в файл
def save_viewed_recipes():
    with open(VIEWED_RECIPES_FILE, "w", encoding="utf-8") as file:
        json.dump(viewed_recipes, file, ensure_ascii=False, indent=4)

# Загружаем просмотренные рецепты при старте
viewed_recipes = load_viewed_recipes()

# Функция для создания главного меню
def create_main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔍 Поиск рецептов", callback_data="search"))
    markup.add(types.InlineKeyboardButton("🔥 Случайный рецепт", callback_data="random"))
    markup.add(types.InlineKeyboardButton("📚 Ранее просмотренные", callback_data="viewed"))
    return markup

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=create_main_menu())

# Обработчик inline-кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = str(call.from_user.id)  # Преобразуем ID в строку для JSON

    if call.data == "search":
        bot.send_message(call.message.chat.id, "Введите ингредиент для поиска рецептов (например, chicken):")
    elif call.data == "random":
        # Получаем случайный рецепт
        recipe = get_random_recipe()
        if recipe:
            send_recipe(call.message.chat.id, recipe)
        else:
            bot.send_message(call.message.chat.id, "Не удалось получить рецепт.")
    elif call.data == "viewed":
        # Отправляем ранее просмотренные рецепты
        if user_id in viewed_recipes and viewed_recipes[user_id]:
            response = "📚 Ранее просмотренные рецепты:\n\n"
            for recipe_id in viewed_recipes[user_id]:
                recipe = get_recipe_by_id(recipe_id)
                if recipe:
                    response += f"🍴 {recipe['strMeal']}\n"
            bot.send_message(call.message.chat.id, response)
        else:
            bot.send_message(call.message.chat.id, "Вы еще не просматривали рецепты.")
    else:
        bot.send_message(call.message.chat.id, "Неизвестная команда.")

# Обработчик текстовых сообщений (поиск рецептов)
@bot.message_handler(func=lambda message: True)
def search_recipes(message):
    user_id = str(message.from_user.id)  # Преобразуем ID в строку для JSON
    ingredient = message.text.lower()  # Получаем ингредиент

    # Ищем рецепты по ингредиенту
    recipes = search_recipes_by_ingredient(ingredient)
    if not recipes:
        bot.send_message(message.chat.id, "Рецепты не найдены. Попробуйте другой ингредиент.")
        return

    # Создаем inline-кнопки для каждого рецепта
    markup = types.InlineKeyboardMarkup()
    for recipe in recipes:
        markup.add(types.InlineKeyboardButton(recipe["strMeal"], callback_data=f"recipe_{recipe['idMeal']}"))

    bot.send_message(message.chat.id, "Вот что я нашел:", reply_markup=markup)

# Обработчик выбора рецепта
@bot.callback_query_handler(func=lambda call: call.data.startswith("recipe_"))
def handle_recipe_callback(call):
    user_id = str(call.from_user.id)  # Преобразуем ID в строку для JSON
    recipe_id = call.data.split("_")[1]  # Получаем ID рецепта

    # Добавляем рецепт в список просмотренных
    if user_id not in viewed_recipes:
        viewed_recipes[user_id] = []
    if recipe_id not in viewed_recipes[user_id]:  # Проверяем, чтобы не дублировать
        viewed_recipes[user_id].append(recipe_id)
        save_viewed_recipes()  # Сохраняем изменения в файл

    # Получаем детали рецепта
    recipe = get_recipe_by_id(recipe_id)
    if recipe:
        send_recipe(call.message.chat.id, recipe)
    else:
        bot.send_message(call.message.chat.id, "Не удалось получить рецепт.")

    # Удаляем inline-кнопки
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

# Функция для поиска рецептов по ингредиенту
def search_recipes_by_ingredient(ingredient):
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php"
    params = {
        "i": ingredient  # Ищем рецепты по ингредиенту
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("meals", [])
        else:
            return None
    except requests.exceptions.RequestException as e:
        print("Ошибка при запросе к API:", e)
        return None

# Функция для получения случайного рецепта
def get_random_recipe():
    url = "https://www.themealdb.com/api/json/v1/1/random.php"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("meals", [])[0] if data.get("meals") else None
        else:
            return None
    except requests.exceptions.RequestException as e:
        print("Ошибка при запросе к API:", e)
        return None

# Функция для получения рецепта по ID
def get_recipe_by_id(recipe_id):
    url = f"https://www.themealdb.com/api/json/v1/1/lookup.php"
    params = {
        "i": recipe_id  # Ищем рецепт по ID
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("meals", [])[0] if data.get("meals") else None
        else:
            return None
    except requests.exceptions.RequestException as e:
        print("Ошибка при запросе к API:", e)
        return None

# Функция для отправки рецепта
def send_recipe(chat_id, recipe):
    response = f"🍴 {recipe['strMeal']}\n\n"
    response += f"📝 Ингредиенты:\n"
    for i in range(1, 21):
        ingredient = recipe.get(f"strIngredient{i}")
        measure = recipe.get(f"strMeasure{i}")
        if ingredient and measure:
            response += f"- {ingredient}: {measure}\n"
    response += f"\n📖 Инструкции:\n{recipe['strInstructions']}\n"
    response += f"\n🔗 Подробнее: {recipe['strSource']}" if recipe.get("strSource") else ""
    bot.send_message(chat_id, response)

# Запуск бота
bot.polling(none_stop=True)