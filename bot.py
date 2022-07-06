from telethon.sync import TelegramClient, events
from telethon import functions
from telethon.tl.types import ChannelParticipantsSearch
from telethon.tl.custom import Button
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import db_funcs


# settings and constants
class Month:
    def __init__(self, name, genitive, day_count):
        self.name = name
        self.genitive = genitive
        self.day_count = day_count


month_properties = {
    1: Month('январь', 'января', 31),
    2: Month('февраль', 'февраля', 29),
    3: Month('март', 'марта', 31),
    4: Month('апрель', 'апреля', 30),
    5: Month('май', 'мая', 31),
    6: Month('июнь', 'июня', 30),
    7: Month('июль', 'июля', 31),
    8: Month('август', 'августа', 31),
    9: Month('сентябрь', 'сентября', 30),
    10: Month('октябрь', 'октября', 31),
    11: Month('ноябрь', 'ноября', 30),
    12: Month('декабрь', 'декабря', 31)
}

db_worker = db_funcs.DatabaseWorker(config.DATABASE)
bot = TelegramClient('bot', config.API_ID, config.API_HASH).start(bot_token=config.TOKEN)
bot.parse_mode = 'html'

moscow_timezone = datetime.timezone(datetime.timedelta(hours=3))


# useful utils
# text
async def create_mention(user_id):
    user = (await bot(functions.users.GetFullUserRequest(user_id))).user
    initials = [user.first_name]
    if user.last_name is not None:
        initials.append(user.last_name)
    return f'<a href="tg://user?id={user_id}">{" ".join(initials)}</a>'


async def congratulation(mentions, day, month, chat_id):
    word_forms = ['празднуют пользователи', 'их']
    if len(mentions) == 0:
        return
    elif len(mentions) == 1:
        word_forms[0] = 'празднует пользователь'
        word_forms[1] = 'его'

    text = f'В этот замечательный день — {day} {month_properties[month].genitive} ' \
           f'свой День рождения {word_forms[0]} {", ".join(mentions)}!\n\nДавайте вместе {word_forms[1]} поздравим 🎉🎉🎉'

    await bot.send_message(chat_id, text)


def create_list(calendar):
    if len(calendar) == 0:
        return 'В этом чате нет данных о Днях рождения 😔'

    days_info = sorted(calendar.items())
    message_blocks = ['<b>Данные о Днях рождения в этом чате</b>']

    current_day, current_month = int(datetime.datetime.now(tz=moscow_timezone).day), int(
        datetime.datetime.now(tz=moscow_timezone).month)
    for point in range(len(days_info)):
        if days_info[point][0] >= (current_month, current_day):
            for i in range(point):
                days_info.append(days_info[0])
                days_info.pop(0)
            break

    for date, users in days_info:
        day_message = [f'<b>{date[1]} {month_properties[date[0]].genitive}</b>', ', '.join(users)]  #
        message_blocks.append('\n'.join(day_message))

    return '\n\n'.join(message_blocks)


# recognize
def is_date_correct(day, month):
    return (month in month_properties) and (1 <= day <= month_properties[month].day_count)


def is_time_correct(hours, minutes):
    return (0 <= hours < 24) and (0 <= minutes < 60)


async def is_user_admin(user_id, chat_id):
    try:
        user = (await bot.get_permissions(chat_id, user_id))
        is_user_chat_creator = user.is_creator
        is_user_chat_admin = user.is_admin
        return is_user_chat_admin or is_user_chat_creator
    except ValueError:
        return False


def get_args(text):
    return (text.split())[1:]


# bot event behavior
@bot.on(events.NewMessage(pattern='^(/start|/help)(|@chatBirthday_bot)$'))
async def greeting(event):
    await event.reply(config.GREETING_MESSAGE)


@bot.on(events.NewMessage(pattern='^/remove_bd(|@chatBirthday_bot)$'))
async def remove_birth_date(event):
    user_id = (await event.get_sender()).id
    if db_worker.birth_date_exists(user_id):
        db_worker.remove_birth_date(user_id)
        await event.reply('Дата Вашего рождения успешно удалена ❌')


@bot.on(events.NewMessage(pattern='^/edit_bd(|@chatBirthday_bot)'))
async def edit_birth_date(event):
    args = get_args(event.text)
    if len(args) == 0:
        sender_id = (await event.get_sender()).id
        keyboard = list()
        for row_ind in range(0, 12, 4):
            keyboard_row = list()
            for col in range(row_ind, row_ind + 4):
                keyboard_row.append(Button.inline(month_properties[col + 1].name.capitalize(),
                                                  data=f"{sender_id} birthdate set_month {col + 1} -"))
            keyboard.append(keyboard_row)
        keyboard.append([Button.inline('Отмена ❌', data=f"{sender_id} birthdate set_month cancel -")])

        await event.reply('<b>Установка (изменение) даты рождения</b>\nВыберите месяц, в который Вы родились',
                          buttons=keyboard)
        return
    elif len(args) > 1:
        await event.reply(
            'Для выполнения этой команды нужен единственный параметр — дата рождения в формате \'dd.mm\' без кавычек. '
            'Также доступно интерактивное изменение даты рождения, для этого не нужно вводить дополнительные параметры.')
        return

    try:
        birth_day, birth_month = map(int, args[0].split('.'))
        sender_id = (await event.get_sender()).id

        if not is_date_correct(birth_day, birth_month):
            await event.reply('К сожалению, введённая дата некорректна 😔')
            return

        db_worker.update_birth_date(sender_id, birth_day, birth_month)
        await event.reply(f'Отлично!\nДата Вашего'
                          f' рождения успешно установлена на {birth_day} {month_properties[birth_month].genitive} 🎉')
    except ValueError:
        await event.reply('Это не похоже на дату рождения 🤨')


@bot.on(events.NewMessage(pattern='^/notify_at(|@chatBirthday_bot)'))
async def update_notification_time(event):
    sender_id = (await event.get_sender()).id
    chat_id = event.chat.id
    if not (await is_user_admin(sender_id, chat_id)):
        return

    args = get_args(event.text)
    if len(args) == 0:
        await event.reply(
            'Для выполнения этой команды необходимо задать время в формате \'hh:mm\' без кавычек.')
        return
    elif len(args) > 1:
        await event.reply(
            'Для выполнения этой команды нужен единственный параметр — время в формате \'hh:mm\' без кавычек.')
        return
    try:
        hours, minutes = map(int, args[0].split(':'))

        if not is_time_correct(hours, minutes):
            await event.reply('К сожалению, введённое время суток некорректно 😔')
            return

        db_worker.update_notification_time(chat_id, hours, minutes)
        await event.reply(
            f'Отлично!\nВремя уведомления о наступивших Днях рождения в этом чате'
            f' установлено на {("0" + str(hours))[-2:]}:{("0" + str(minutes))[-2:]} UTC+3 ⏰')
    except ValueError:
        await event.reply('Интересный формат времени 🧐 Жаль, что я его не понимаю 😔')


@bot.on(events.NewMessage(pattern='^/dont_notify(|@chatBirthday_bot)$'))
async def disable_notifications(event):
    sender_id = (await event.get_sender()).id
    chat_id = event.chat.id

    if not (await is_user_admin(sender_id, chat_id)):
        return

    db_worker.disable_notification(chat_id)
    await event.reply(f'Уведомления о наступивших Днях рождения в этом чате отключены ❌')


@bot.on(events.NewMessage(pattern='^/(bd_list|list_bd)(|@chatBirthday_bot)$'))
async def show_all_birthdays_in_chat(event):
    chat_id = event.chat.id
    sender_id = (await event.get_sender()).id

    if not (await is_user_admin(sender_id, chat_id)):
        return

    try:
        chat_members = await bot(functions.channels.GetParticipantsRequest(
            chat_id, ChannelParticipantsSearch(''), offset=0, limit=10000,
            hash=0
        ))

        calendar = dict()
        for member in chat_members.users:
            if not db_worker.birth_date_exists(member.id):
                continue
            birth_day, birth_month = db_worker.get_birth_date(member.id)
            mention = await create_mention(member.id)
            if (birth_month, birth_day) in calendar:
                calendar[(birth_month, birth_day)].append(mention)
            else:
                calendar[(birth_month, birth_day)] = [mention]

        message = await event.reply('.')
        await bot.edit_message(chat_id, message, create_list(calendar))
    except ValueError:
        await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')


# bot notification sending
async def send_notification():
    hour, minute = int(datetime.datetime.now(tz=moscow_timezone).hour), int(
        datetime.datetime.now(tz=moscow_timezone).minute)
    day, month = int(datetime.datetime.now(tz=moscow_timezone).day), int(
        datetime.datetime.now(tz=moscow_timezone).month)

    chats_to_notify = db_worker.get_chats_to_notify(hour, minute)
    users_to_notify = db_worker.get_users_to_notify(day, month)

    for chat_id in chats_to_notify:
        chat_members = await bot(functions.channels.GetParticipantsRequest(
            chat_id, ChannelParticipantsSearch(''), offset=0, limit=10000,
            hash=0
        ))

        users_to_notify_in_chat = list()

        for member in chat_members.users:
            if member.id in users_to_notify:
                users_to_notify_in_chat.append(await create_mention(member.id))

        await congratulation(users_to_notify_in_chat, day, month, chat_id)


# callback actions
@bot.on(events.CallbackQuery())
async def update_interactive_message(event):
    user_id = event.original_update.user_id
    message_id = event.original_update.msg_id
    peer = event.original_update.peer
    caller, request_type, stage, pick, previous_pick = event.original_update.data.decode('utf-8').split()

    if int(caller) != user_id:
        return

    if request_type == 'birthdate':
        if pick == 'cancel':
            await bot.edit_message(peer, message_id, 'Изменение даты рождения прервано ❌')
            return
        if stage == 'set_month':
            keyboard = list()
            days = month_properties[int(pick)].day_count
            for row_ind in range(1, days + 1, 5):
                keyboard_row = list()
                for col in range(row_ind, min(row_ind + 5, days + 1)):
                    keyboard_row.append(Button.inline(f'{col}', data=f'{user_id} birthdate set_day {col} {pick}'))
                keyboard.append(keyboard_row)
            keyboard.append([Button.inline('Отмена ❌', data=f"{user_id} birthdate set_day cancel -")])
            await bot.edit_message(peer, message_id,
                                   f'<b>Установка (изменение) даты рождения</b>\nВы выбрали месяц {month_properties[int(pick)].name}, '
                                   f'теперь выберите день Вашего рождения.', buttons=keyboard)
        elif stage == 'set_day':
            birth_month = int(previous_pick)
            birth_day = int(pick)

            db_worker.update_birth_date(user_id, birth_day, birth_month)

            await bot.edit_message(peer, message_id,
                                   f'Отлично!\nДата Вашего рождения успешно '
                                   f'установлена на {birth_day} {month_properties[birth_month].genitive} 🎉')


# start bot
if __name__ == "__main__":
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_notification, 'interval', minutes=1)
    scheduler.start()

    bot.loop.run_forever()
