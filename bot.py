import struct

from telethon.sync import TelegramClient, events
from telethon import functions, errors
from telethon.tl.types import ChannelParticipantsSearch
from telethon.tl.custom import Button
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import db_funcs
import utils

# settings and constants
db_worker = db_funcs.DatabaseWorker(config.DATABASE)
bot = TelegramClient('bot', config.API_ID, config.API_HASH).start(bot_token=config.TOKEN)
bot.parse_mode = 'html'

moscow_timezone = datetime.timezone(datetime.timedelta(hours=3))


# USEFUL UTILS
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


def congratulation(mentions, day, month):
    word_form = 'празднуют'
    if len(mentions) == 0:
        return
    elif len(mentions) == 1:
        word_form = 'празднует'

    text = f'В этот замечательный день — {day} {utils.month_properties[month].genitive} ' \
           f'свой День рождения {word_form} {", ".join(mentions)}!\n\nДавайте вместе поздравим 🎉🎉🎉'
    return text


def create_list(calendar):
    if len(calendar) == 0:
        return 'В этом чате нет данных о Днях рождения 😔'

    days_info = sorted(calendar.items())
    message_blocks = ['<b>Данные о Днях рождения в этом чате</b>']

    current_day, current_month = int(datetime.datetime.now(tz=moscow_timezone).day), int(
        datetime.datetime.now(tz=moscow_timezone).month)
    for pivot in range(len(days_info)):
        if days_info[pivot][0] >= (current_month, current_day):
            for i in range(pivot):
                days_info.append(days_info[0])
                days_info.pop(0)
            break

    for date, users in days_info:
        day_message = [
            f'<b>{date[1]} {utils.month_properties[date[0]].genitive} {utils.get_zodiac(date[1], date[0])}</b>',
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
        args = utils.get_args(event.text)
        sender_id = (await event.get_sender()).id
        if len(args) == 0:
            keyboard = list()
            for row_ind in range(0, 12, 4):
                keyboard_row = list()
                for col in range(row_ind, row_ind + 4):
                    keyboard_row.append(Button.inline(utils.month_properties[col + 1].name.capitalize(),
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

        if not utils.is_date_correct(birth_day, birth_month):
            await event.reply('К сожалению, введённая дата некорректна 😔')
            return

        db_worker.update_birth_date(sender_id, birth_day, birth_month)
        await event.reply(f'Отлично!\nДата Вашего рождения успешно '
                          f'установлена на {birth_day} {utils.month_properties[birth_month].genitive} 🎉')
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
    caller, stage, pick, previous_pick = utils.get_args(event.original_update.data.decode('utf-8'))
    try:
        if await activity_alert(event, int(caller), user_id):
            return

        if pick == 'cancel':
            await bot.edit_message(peer, message_id, 'Изменение даты рождения прервано ❌')
            return

        if stage == 'set_month':
            keyboard = list()
            days = utils.month_properties[int(pick)].day_count
            for row_ind in range(1, days + 1, 5):
                keyboard_row = list()
                for col in range(row_ind, min(row_ind + 5, days + 1)):
                    keyboard_row.append(Button.inline(f'{col}', data=f'birthdate {user_id} set_day {col} {pick}'))
                keyboard.append(keyboard_row)
            keyboard.append([Button.inline('Отмена ❌', data=f'birthdate {user_id} set_day cancel -')])
            await bot.edit_message(peer, message_id,
                                   f'<b>Установка (изменение) даты рождения</b>\n'
                                   f'Вы выбрали месяц {utils.month_properties[int(pick)].name}, '
                                   f'теперь выберите день Вашего рождения.', buttons=keyboard)
        elif stage == 'set_day':
            birth_month = int(previous_pick)
            birth_day = int(pick)

            db_worker.update_birth_date(user_id, birth_day, birth_month)

            await bot.edit_message(peer, message_id,
                                   f'Отлично!\nДата Вашего рождения успешно '
                                   f'установлена на {birth_day} {utils.month_properties[birth_month].genitive} 🎉')
    except Exception as exception:
        print('birthdate_setting', exception.__class__.__name__)  # debugging


@bot.on(events.NewMessage(pattern='^/notify_at(|@chatBirthday_bot)'))
async def update_notification_time(event):
    try:
        sender_id = (await event.get_sender()).id
        chat_id = event.chat.id
        if not (await is_user_admin(sender_id, chat_id)):
            return

        args = utils.get_args(event.text)

        if len(args) != 1:
            await event.reply(
                'Для выполнения этой команды необходимо задать время в формате \'hh:mm\' без кавычек.')
            return

        try:
            hours, minutes = map(int, args[0].split(':'))

            if not utils.is_time_correct(hours, minutes):
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
            chat_members = await bot(functions.channels.GetParticipantsRequest(
                chat_id, ChannelParticipantsSearch(''), offset=0, limit=10000,
                hash=0
            ))

            users_to_notify_in_chat = list()

            for member in chat_members.users:
                if member.id in users_to_notify:
                    users_to_notify_in_chat.append(await create_mention(member.id))

            if len(users_to_notify_in_chat) == 0:
                continue

            notification_text = congratulation(users_to_notify_in_chat, day, month)
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
    except db_funcs.ChatNotificationsDisabled:
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


# start bot
if __name__ == '__main__':
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_notification, 'interval', minutes=1)
    scheduler.start()

    bot.loop.run_forever()
