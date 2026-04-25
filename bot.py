import struct
import asyncio
import random
from functools import wraps

from cachetools import LRUCache
from telethon.sync import TelegramClient, events
from telethon import functions, errors
from telethon.tl.types import ChannelParticipantsSearch
from telethon.tl.custom import Button
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import utils.db_utils as db_utils
import utils.format_utils as format_utils

# settings and constants
db_worker = db_utils.DatabaseWorker(config.DATABASE)
bot = TelegramClient('bot', config.API_ID, config.API_HASH).start(bot_token=config.TOKEN)
bot.parse_mode = 'html'

moscow_timezone = datetime.timezone(datetime.timedelta(hours=3))


def async_lru_ttl_cache(maxsize=50, ttl_seconds=24 * 60 * 60, jitter_seconds=60 * 60):
    def decorator(func):
        cache = LRUCache(maxsize=maxsize)
        lock = asyncio.Lock()

        def freeze(value):
            if isinstance(value, dict):
                return tuple(sorted((freeze(k), freeze(v)) for k, v in value.items()))
            if isinstance(value, (list, tuple)):
                return tuple(freeze(item) for item in value)
            if isinstance(value, set):
                return tuple(sorted(freeze(item) for item in value))
            return value

        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = (freeze(args), freeze(kwargs))
            now = datetime.datetime.now(datetime.timezone.utc).timestamp()

            async with lock:
                cached = cache.get(key)
                if cached is not None:
                    value, expires_at = cached
                    if expires_at > now:
                        return value
                    cache.pop(key, None)

            value = await func(*args, **kwargs)
            expires_at = now + ttl_seconds + random.randint(0, jitter_seconds)

            async with lock:
                cache[key] = (value, expires_at)

            return value

        return wrapper

    return decorator


@async_lru_ttl_cache(maxsize=50, ttl_seconds=24 * 60 * 60, jitter_seconds=60 * 60)
async def get_chat_members(chat_id):
    return await bot(functions.channels.GetParticipantsRequest(
        chat_id, ChannelParticipantsSearch(''), offset=0, limit=10000,
        hash=0
    ))


async def get_users_to_notify_in_chat(chat_id, users_to_notify):
    chat_members = await get_chat_members(chat_id)
    users_to_notify_set = set(users_to_notify)

    users_to_notify_in_chat = list()
    for member in chat_members.users:
        if member.id in users_to_notify_set:
            users_to_notify_in_chat.append(await create_mention(member.id))

    return users_to_notify_in_chat


# USEFUL format_utils
# text
async def create_mention(user_id):
    try:
        user = (await bot(functions.users.GetFullUserRequest(user_id))).user
        mention = user.first_name
        if user.last_name is not None:
            mention = mention + ' ' + user.last_name
        return f'<a href="tg://user?id={user_id}">{mention}</a>'
    except Exception as exception:
        print('create_mention', exception.__class__.__name__)  # debugging


async def create_calendar(users):
    calendar = dict()
    for member in users:
        if not db_worker.birth_date_exists(member.id):
            continue
        birth_day, birth_month = db_worker.get_birth_date(member.id)
        mention = await create_mention(member.id)
        if (birth_month, birth_day) in calendar:
            calendar[(birth_month, birth_day)].append(mention)
        else:
            calendar[(birth_month, birth_day)] = [mention]
    return calendar


def reorder_calendar(days_info):
    current_day, current_month = int(datetime.datetime.now(tz=moscow_timezone).day), int(
        datetime.datetime.now(tz=moscow_timezone).month)
    for pivot in range(len(days_info)):
        if days_info[pivot][0] >= (current_month, current_day):
            for i in range(pivot):
                days_info.append(days_info[0])
                days_info.pop(0)
            break
    return days_info


def create_all_birthdays_list(calendar):
    if len(calendar) == 0:
        return 'В этом чате нет данных о Днях рождения 😔'

    days_info = reorder_calendar(sorted(calendar.items()))
    message_blocks = ['<b>Данные о Днях рождения в этом чате</b>']

    for date, users in days_info:
        day_message = [
            f'<b>{date[1]} {format_utils.month_properties[date[0]].genitive} {format_utils.get_zodiac(date[1], date[0])}</b>',
            ', '.join(users)]
        message_blocks.append('\n'.join(day_message))

    return '\n\n'.join(message_blocks)


# recognition
async def is_user_admin(user_id, chat_id):
    try:
        user = (await bot.get_permissions(chat_id, user_id))
        return user.is_admin or user.is_creator
    except ValueError:
        return False
    except Exception as exception:
        print('is_user_admin', exception.__class__.__name__)  # debugging


async def activity_alert(event, expected, involved):
    try:
        if expected != involved:
            await event.answer('Взаимодействовать с данным сообщением может только пользователь, вызвавший его ⛔',
                               alert=True)
            return True
        return False
    except Exception as exception:
        print('activity_alert', exception.__class__.__name__)  # debugging
        return True


# BOT EVENT BEHAVIOR
@bot.on(events.NewMessage(pattern='^(/start|/help)(|@chatBirthday_bot)$'))
async def greeting(event):
    try:
        await event.reply(config.GREETING_MESSAGE)
    except Exception as exception:
        print('greeting', exception.__class__.__name__)  # debugging


@bot.on(events.NewMessage(pattern='^/remove_bd(|@chatBirthday_bot)$'))
async def remove_birth_date(event):
    try:
        user_id = (await event.get_sender()).id
        if db_worker.birth_date_exists(user_id):
            db_worker.remove_birth_date(user_id)
            await event.reply('Дата Вашего рождения успешно удалена ❌')
        else:
            await event.reply('Вы мне не говорили свою дату рождения 😔')
    except ValueError:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            pass
    except struct.error:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            pass
    except Exception as exception:
        print('remove_birth_date', exception.__class__.__name__)  # debugging


@bot.on(events.NewMessage(pattern='^/edit_bd(|@chatBirthday_bot)'))
async def edit_birth_date(event):
    try:
        args = format_utils.get_args(event.text)
        sender_id = (await event.get_sender()).id
        if len(args) == 0:
            keyboard = list()
            for row_ind in range(0, 12, 4):
                keyboard_row = list()
                for col in range(row_ind, row_ind + 4):
                    keyboard_row.append(Button.inline(format_utils.month_properties[col + 1].name.capitalize(),
                                                      data=f'birthdate {sender_id} set_month {col + 1} -'))
                keyboard.append(keyboard_row)
            keyboard.append([Button.inline('Отмена ❌', data=f'birthdate {sender_id} set_month cancel -')])

            await event.reply('<b>Установка (изменение) даты рождения</b>\nВыберите месяц, в который Вы родились',
                              buttons=keyboard)
            return
        elif len(args) > 1:
            try:
                await event.reply(
                    'Для выполнения этой команды нужен единственный параметр — '
                    'дата рождения в формате \'dd.mm\' без кавычек. '
                    'Также доступно интерактивное изменение даты рождения, '
                    'для этого не нужно вводить дополнительные параметры.')
                return
            except Exception as exception:
                pass

        birth_day, birth_month = map(int, args[0].split('.'))

        if not format_utils.is_date_correct(birth_day, birth_month):
            await event.reply('К сожалению, введённая дата некорректна 😔')
            return

        db_worker.update_birth_date(sender_id, birth_day, birth_month)
        await event.reply(f'Отлично!\nДата Вашего рождения успешно '
                          f'установлена на {birth_day} {format_utils.month_properties[birth_month].genitive} 🎉')
    except ValueError:
        try:
            await event.reply('Это не похоже на дату рождения 🤨')
        except Exception:
            pass
    except Exception as exception:
        print('edit_birth_date', exception.__class__.__name__)  # debugging


@bot.on(events.CallbackQuery(pattern='^birthdate'))
async def birthdate_setting(event):
    user_id, message_id, peer = event.original_update.user_id, event.original_update.msg_id, event.original_update.peer
    caller, stage, pick, previous_pick = format_utils.get_args(event.original_update.data.decode('utf-8'))
    try:
        if await activity_alert(event, int(caller), user_id):
            return

        if pick == 'cancel':
            await bot.edit_message(peer, message_id, 'Изменение даты рождения прервано ❌')
            return

        if stage == 'set_month':
            keyboard = list()
            days = format_utils.month_properties[int(pick)].day_count
            for row_ind in range(1, days + 1, 5):
                keyboard_row = list()
                for col in range(row_ind, min(row_ind + 5, days + 1)):
                    keyboard_row.append(Button.inline(f'{col}', data=f'birthdate {user_id} set_day {col} {pick}'))
                keyboard.append(keyboard_row)
            keyboard.append([Button.inline('Отмена ❌', data=f'birthdate {user_id} set_day cancel -')])
            await bot.edit_message(peer, message_id,
                                   f'<b>Установка (изменение) даты рождения</b>\n'
                                   f'Вы выбрали месяц {format_utils.month_properties[int(pick)].name}, '
                                   f'теперь выберите день Вашего рождения.', buttons=keyboard)
        elif stage == 'set_day':
            birth_month = int(previous_pick)
            birth_day = int(pick)

            db_worker.update_birth_date(user_id, birth_day, birth_month)

            await bot.edit_message(peer, message_id,
                                   f'Отлично!\nДата Вашего рождения успешно '
                                   f'установлена на {birth_day} {format_utils.month_properties[birth_month].genitive} 🎉')
    except Exception as exception:
        print('birthdate_setting', exception.__class__.__name__)  # debugging


@bot.on(events.NewMessage(pattern='^/notify_at(|@chatBirthday_bot)'))
async def update_notification_time(event):
    try:
        sender_id = (await event.get_sender()).id
        chat_id = event.chat.id
        if not (await is_user_admin(sender_id, chat_id)):
            return

        args = format_utils.get_args(event.text)

        if len(args) != 1:
            await event.reply(
                'Для выполнения этой команды необходимо задать время в формате \'hh:mm\' без кавычек.')
            return

        try:
            hours, minutes = map(int, args[0].split(':'))

            if not format_utils.is_time_correct(hours, minutes):
                await event.reply('К сожалению, введённое время суток некорректно 😔')
                return

            db_worker.update_notification_time(chat_id, hours, minutes)
            await event.reply(
                f'Отлично!\nВремя уведомления о наступивших Днях рождения в этом чате'
                f' установлено на {("0" + str(hours))[-2:]}:{("0" + str(minutes))[-2:]} UTC+3 ⏰')
        except ValueError:
            try:
                await event.reply('Интересный формат времени 🧐 Жаль, что я его не понимаю 😔')
            except Exception as exception:
                pass
    except ValueError:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            pass
    except struct.error:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            pass
    except Exception as exception:
        print('update_notification_time', exception.__class__.__name__)  # debugging


@bot.on(events.NewMessage(pattern='^/dont_notify(|@chatBirthday_bot)$'))
async def disable_notifications(event):
    try:
        sender_id = (await event.get_sender()).id
        chat_id = event.chat.id

        if not (await is_user_admin(sender_id, chat_id)):
            return

        db_worker.disable_notification(chat_id)
        await event.reply(f'Уведомления о наступивших Днях рождения в этом чате отключены ❌')
    except ValueError:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            print('disable_notifications', exception.__class__.__name__)  # debugging
    except struct.error:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            print('disable_notifications', exception.__class__.__name__)  # debugging
    except Exception as exception:
        print('disable_notifications', exception.__class__.__name__)  # debugging


async def send_notification():
    hour, minute = int(datetime.datetime.now(tz=moscow_timezone).hour), int(
        datetime.datetime.now(tz=moscow_timezone).minute)
    day, month = int(datetime.datetime.now(tz=moscow_timezone).day), int(
        datetime.datetime.now(tz=moscow_timezone).month)

    chats_to_notify = db_worker.get_chats_to_notify(hour, minute)
    users_to_notify = db_worker.get_users_to_notify(day, month)

    for chat_id in chats_to_notify:
        try:
            users_to_notify_in_chat = await get_users_to_notify_in_chat(chat_id, users_to_notify)

            if len(users_to_notify_in_chat) == 0:
                continue

            notification_text = format_utils.create_congratulation(users_to_notify_in_chat, day, month)
            pin = db_worker.get_pin_type(chat_id)

            message = await bot.send_message(chat_id, notification_text)
            try:
                if pin:
                    await bot.pin_message(chat_id, message)
            except errors.ChatAdminRequiredError:
                pass
            except Exception as exception:
                print('send_notification', exception.__class__.__name__)  # debugging

        except errors.rpcerrorlist.ChannelPrivateError:
            db_worker.disable_notification(chat_id)
        except errors.rpcerrorlist.ChatWriteForbiddenError:
            pass
        except ValueError:
            pass
        except struct.error:
            pass
        except Exception as exception:
            print('send_notification', exception.__class__.__name__)  # debugging


@bot.on(events.NewMessage(pattern='^/(pin|unpin)(|@chatBirthday_bot)$'))
async def handle_notification_pinning(event):
    try:
        sender_id = (await event.get_sender()).id
        chat_id = event.chat.id

        if not (await is_user_admin(sender_id, chat_id)):
            return
        try:
            if 'unpin' in event.text:
                db_worker.update_pin_type(chat_id, False)
                await event.reply('Закрепление уведомлений в этом чате успешно <b>выключено</b> 🎉')
            else:
                db_worker.update_pin_type(chat_id, True)
                await event.reply('Закрепление уведомлений в этом чате успешно <b>включено</b> 🎉')
        except Exception as exception:
            print('handle_notification_pinning', exception.__class__.__name__)
    except db_utils.ChatNotificationsDisabled:
        try:
            await event.reply('В данном чате отключены уведомления о Днях рождения 😔')
        except Exception as exception:
            print('handle_notification_pinning', exception.__class__.__name__)
    except Exception as exception:
        print('handle_notification_pinning', exception.__class__.__name__)


@bot.on(events.NewMessage(pattern='^/(bd_list|list_bd)(|@chatBirthday_bot)$'))
async def show_all_birthdays_in_chat(event):
    try:
        chat_id = event.chat.id
        sender_id = (await event.get_sender()).id

        if not (await is_user_admin(sender_id, chat_id)):
            return

        chat_members = await get_chat_members(chat_id)

        calendar = await create_calendar(chat_members.users)

        message = await event.reply('.')
        await bot.edit_message(chat_id, message, create_all_birthdays_list(calendar))
    except ValueError:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            pass
    except struct.error:
        try:
            await event.reply('Произошла ошибка 😔 Возможно, этот чат не является супергруппой.')
        except Exception as exception:
            pass
    except errors.ChatForbiddenError:
        pass
    except Exception as exception:
        print('show_all_birthdays', exception.__class__.__name__)  # debugging


@bot.on(events.NewMessage(pattern='^/next_bd(|@chatBirthday_bot)$'))
async def show_next_birthdays(event):
    try:
        chat_id = event.chat.id

        chat_members = await get_chat_members(chat_id)

        calendar = await create_calendar(chat_members.users)

        if len(calendar) == 0:
            await event.reply('В этом чате нет данных о Днях рождения 😔')
            return

        days_info = reorder_calendar(sorted(calendar.items()))

        current_day, current_month = int(datetime.datetime.now(tz=moscow_timezone).day), int(
            datetime.datetime.now(tz=moscow_timezone).month)
        if days_info[0][0] == (current_month, current_day):
            days_info.append(days_info[0])
            days_info.pop(0)

        date_and_users = days_info[0]
        message_content = f'<b>Следующий праздник — {date_and_users[0][1]} ' \
                          f'{format_utils.month_properties[date_and_users[0][0]].genitive}.</b>\n\n' \
                          f'Будем поздравлять с Днем рождения {", ".join(date_and_users[1])} 🎉'

        message = await event.reply('.')
        await bot.edit_message(chat_id, message, message_content)
    except TypeError:
        try:
            await event.reply('Здесь недоступно выполнение данного запроса 😔')
        except Exception as exception:
            print('show_next_birthdays', exception.__class__.__name__)  # debugging
    except Exception as exception:
        print('show_next_birthdays', exception.__class__.__name__)  # debugging


# start bot
if __name__ == '__main__':
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_notification, 'interval', minutes=1)
    scheduler.start()

    bot.loop.run_forever()
