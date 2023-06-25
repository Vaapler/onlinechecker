import telebot
import os
import json
import time
import requests
import threading
import datetime

ACCESS_TOKEN = ""
BOT_STATE_PATH = "bot_state.json"
REPORT_PREFIX = "reports/raw/"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
CHECK_TIME = 60
SAVE_TIME = 60

bot = telebot.TeleBot(ACCESS_TOKEN)
bot_state = None
state_is_changed = False

if os.path.exists(BOT_STATE_PATH):
    print("Загружаем сохраненное стостояние")

    with open(BOT_STATE_PATH, "r") as file:
        bot_state = json.load(file)
else:
    print("Предыдущие состояние не найдено, создаём новое по умолчанию")

    bot_state = {"users": dict(), "channels": dict(), "services": dict()}

bot_users = bot_state["users"]
bot_channels = bot_state["channels"]
bot_services = bot_state["services"]

current_report = dict()
for i in bot_services.keys():
    current_report[i] = []

print("Конфигурация загружена")


@bot.my_chat_member_handler()
def handle_channel_event(message):
    user_id = str(message.from_user.id)
    chat_id = str(message.chat.id)

    status = message.new_chat_member.status
    if status == "administrator":
        bot.send_message(user_id, "Вы успешно добавили бота в чат, напишите /add для добавления сервисов")
        if user_id not in bot_users.keys():
            bot_users[user_id] = [chat_id]
        else:
            bot_users[user_id] += [chat_id]
        bot_channels[chat_id] = {"owner_id": user_id, "title": message.chat.title, "services": dict()}
    elif status == "left":
        bot.send_message(bot_channels[chat_id]["owner_id"], "Бот был удален из чата, настройки сброшены")
        bot_channels.pop(chat_id)
        bot_users[user_id].delete(message.char_id)


@bot.message_handler(commands=["status", "start"])
def show_status(message):
    user_id = str(message.from_user.id)
    chat_id = str(message.chat.id)

    if user_id not in bot_users.keys() or len(bot_users[user_id]) == 0:
        bot.send_message(chat_id, "Вы не добавляли бота в чаты")
    else:
        bot.send_message(chat_id, "С вами ассоциированы следующие чаты")
        bot.send_message(chat_id, "\n".join([f"ID: {n+1}, Название: {bot_channels[v]['title']}" for n, v in enumerate(bot_users[user_id])]))

@bot.message_handler(commands=["add"])
def add_service(message):
    args = message.text.split()
    chat_id = str(message.chat.id)

    if len(args) != 5:
        bot.send_message(chat_id, "Ошибка в аргументах. /add <id> <service_url> <service_name> <service_type>")
        return

    channel_id, service_url, service_name, service_type = args[1:]
    channel_id = bot_users[str(message.from_user.id)][int(channel_id) - 1]

    bot_channels[channel_id]["services"][service_url] = [service_name, service_type]
    if service_url in bot_services.keys():
        bot_services[service_url]["channels"] += [channel_id]
    request = requests.request("GET", "https://" + service_url, headers={'User-agent': 'Mozilla/5.0'})
    bot_services[service_url] = {"available": request.status_code == 200,
                                 "last_online": str(datetime.datetime.now().strftime(DATE_FORMAT)),
                                 "channels": [channel_id]}

    if service_url not in current_report.keys():
        current_report[service_url] = []

    bot.send_message(chat_id, f"Сервис {service_name}, типа {service_type} удачно добавлен в выбранный канал")


if __name__ == "__main__":
    last_report = datetime.datetime.now()

    threading.Thread(target=bot.infinity_polling, daemon=True).start()

    while True:
        time.sleep(CHECK_TIME)

        with open(BOT_STATE_PATH, "w") as file:
            json.dump(bot_state, file)
            print("Изменения сохранены")

        current_datetime = str(datetime.datetime.now().strftime(DATE_FORMAT))
        for service in bot_services.keys():
            status, retries_left = None, 10
            while retries_left > 0:
                try:
                    request = requests.request("GET", "https://" + service, headers={'User-agent': 'Mozilla/5.0'})
                    status = request.status_code
                    break
                except requests.exceptions.ConnectionError as exception:
                    status = str(exception)
                time.sleep(1)

            if status != 200:
                if bot_services[service]["available"]:
                    for channel in bot_services[service]["channels"]:
                        if service in bot_channels[channel]["services"].keys():
                            name, stype = bot_channels[channel]["services"][service]
                            message = f"Ресурс недоступен:" \
                                      f"{name}-{stype}-{service}-{current_datetime}-Код ошибки: {status}"
                            bot.send_message(channel, message)
                bot_services[service]["available"] = False
            else:
                if not bot_services[service]["available"]:
                    current_report[service] += [[bot_services[service]["last_online"], current_datetime]]
                    for channel in bot_services[service]["channels"]:
                        if service in bot_channels[channel]["services"].keys():
                            name, stype = bot_channels[channel]["services"][service]
                            message = f"Ресурс снова доступен:" \
                                      f"{name}-{stype}-{service}-{current_datetime}"
                            bot.send_message(channel, message)
                bot_services[service]["available"] = True
                bot_services[service]["last_online"] = current_datetime

        if datetime.datetime.now().day != last_report.day:
            path = ""
            for i in REPORT_PREFIX.split("/"):
                path += i if path == "" else "/" + i
                if not os.path.exists(path):
                    os.mkdir(path)

            for service_url, data in current_report.items():
                folder_path = REPORT_PREFIX + "/" + service_url
                if not os.path.exists(folder_path):
                    os.mkdir(folder_path)

                with open(folder_path + "/" + last_report.strftime("%m-%d.txt"), "w") as file:
                    json.dump(data, file)

                current_report[service_url] = []

            last_report = datetime.datetime.now()
