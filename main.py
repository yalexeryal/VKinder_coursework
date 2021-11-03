import logging
import os
from os.path import join, dirname

from dotenv import load_dotenv

from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkEventType

from bot.vkinder_bot import Vkinder_Bot
from model.vkinder_db import Vkinder_DB

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


def get_start_keyboard():
    keyboard = VkKeyboard(one_time=True)

    keyboard.add_button('Изменить параметры поиска',
                        color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Показать страницы',
                        color=VkKeyboardColor.PRIMARY)

    return keyboard.get_keyboard()


def get_next_fav_keyboard():
    keyboard = VkKeyboard(one_time=False)

    keyboard.add_button('Изменить параметры поиска',
                        color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Дальше', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()

    keyboard.add_button('Добавить в избранное', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()

    keyboard.add_button('Показать избранное', color=VkKeyboardColor.PRIMARY)

    return keyboard.get_keyboard()


def get_favorite_keyboard():
    keyboard = VkKeyboard(one_time=False)

    keyboard.add_button('Убрать из избранного', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()

    keyboard.add_button('Следующее избранное', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()

    keyboard.add_button('Перейти к поиску', color=VkKeyboardColor.PRIMARY)

    return keyboard.get_keyboard()


def get_empty_keyboard():
    keyboard = VkKeyboard.get_empty_keyboard()

    return keyboard


def add_new_user(user_id, database: Vkinder_DB):
    database.add_user(user_id)


def menu_set_search_params(user_id, db: Vkinder_DB, bot: Vkinder_Bot):
    user_info = bot.get_user_info(user_id)
    search_params = {'gender': user_info['sex'] % 2 + 1}

    bot.send_msg(user_id, 'Какого года рождения будем искать?',
                 keyboard=get_empty_keyboard())
    for event in bot.longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW \
                and event.to_me \
                and event.user_id == user_id:
            if len(event.text) == 4 and event.text.isdigit():
                search_params['b_year'] = int(event.text)
                break
            else:
                bot.send_msg(user_id, 'Неверный ввод')

    bot.send_msg(user_id, 'Семейное положение?\n'
                          '1 — не женат/не замужем;\n'
                          '2 — есть друг/есть подруга;\n'
                          '3 — помолвлен/помолвлена;\n'
                          '4 — женат/замужем;\n'
                          '5 — всё сложно;\n'
                          '6 — в активном поиске;\n'
                          '7 — влюблён/влюблена;\n'
                          '8 — в гражданском браке;\n')

    for event in bot.longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW \
                and event.to_me \
                and event.user_id == user_id:
            if event.text and event.text.isdigit() and \
                    int(event.text) in [i for i in range(1, 9)]:
                search_params['status'] = int(event.text)
                break
            else:
                print(event.text)
                bot.send_msg(user_id, 'Неверный ввод')

    bot.send_msg(user_id, 'Город?')
    for event in bot.longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW \
                and event.to_me \
                and event.user_id == user_id:
            city_id = bot.get_city_id(event.text)
            if city_id:
                search_params['city'] = city_id
                break
            else:
                bot.send_msg(user_id, 'Попробуй еще')

    bot.send_msg(user_id, keyboard=get_start_keyboard())

    db.set_search_params(user_id, search_params)
    db.delete_searched(user_id)
    menu_next(user_id, db, bot)


def user_is_exist(user_id, database):
    return bool(database.get_user(user_id))


def search_users(user_id, db: Vkinder_DB, bot: Vkinder_Bot):
    params = db.get_search_params(user_id)
    search_list = bot.search_all_users(params)
    db.add_searched_users(user_id, search_list)


def menu_start(user_id, db, bot):
    if not db.get_user(event.user_id):
        add_new_user(event.user_id, db)


    bot.send_msg(user_id, 'Занес тебя в базу', get_start_keyboard())


def menu_next(user_id, db, bot):
    params = db.get_search_params(user_id)

    if not db.get_user(event.user_id):
        add_new_user(event.user_id, db)

    if params:
        next = db.get_searched_id(event.user_id)
        if next:
            request = bot.get_photos_msg(event.user_id, next)
            bot.send_msg(user_id, message=request['msg'],
                         attachment=request['attach'],
                         keyboard=get_next_fav_keyboard())
        else:
            bot.send_msg(user_id, 'Начинаю поиск вариантов')
            search_list = list(bot.search_all_users(params))

            if not search_list:
                bot.send_msg(user_id, 'Вариантов нет',
                             keyboard=get_start_keyboard())
                return

            db.add_searched_users(user_id, search_list)
            menu_next(user_id, db, bot)
    else:
        menu_set_search_params(user_id, db, bot)
        menu_next(user_id, db, bot)


if __name__ == '__main__':

    logging.basicConfig(filename='exceptions.log')
    bot = Vkinder_Bot(os.getenv('VK_GROUP_TOKEN'), os.getenv('VK_PERSONAL_TOKEN'))
    db = Vkinder_DB(
        f"postgresql://"
        f"{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@localhost:5432/{os.getenv('DB_NAME')}"
    )
    db.drop_all()
    db.init_db()
    menu = {
        'Начать': menu_start,
        'Изменить параметры поиска': menu_set_search_params,
        'Показать страницы': menu_next,
        'Дальше': menu_next,
    }

    for event in bot.longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            if event.to_me:
                request = event.text
                try:
                    if request in menu:
                        menu[request](event.user_id, db, bot)
                    else:
                        bot.send_msg(event.user_id,
                                     f" Не понял вашего запроса...\n"
                                     f" Для начала поиска введите: \n"
                                     f"Начать\n"
                                     f"Дальше\n"
                                     f" И далее следуйте командам или используйте кнопки бота")
                except Exception as e:
                    logging.error(e, exc_info=True)
