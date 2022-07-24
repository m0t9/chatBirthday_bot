from os import environ

TOKEN = environ["TOKEN"]
API_ID = environ["API_ID"]
API_HASH = environ["API_HASH"]

DATABASE = environ["DATABASE_URL"]

GREETING_MESSAGE = '''
Привет 👋 Я — бот Поздравитель!

<b>Моя задача проста</b> — напоминать о наступивших Днях рождения участников чата.
Чтобы я мог приступить к ее выполнению, я расскажу, как со мной взаимодействовать.

⚠️ <b>Я полноценно работаю только в супергруппах!</b> Если Ваш чат еще не является таковой, то скорее исправляйте это.

👤 <b>ДОСТУПНО ВСЕМ УЧАСТНИКАМ ЧАТА</b>
/help — получить данное сообщение со списком команд
/edit_bd — установить или изменить дату Вашего рождения
/remove_bd — удалить из базы дату Вашего рождения

🌟 <b>ДОСТУПНО ТОЛЬКО АДМИНИСТРАТОРАМ ЧАТА</b>
/notify_at hh:mm — установить время ежедневного уведомления о наступивших Днях рождения по поясу UTC+3 (формат — 'hh:mm' без кавычек)
/dont_notify — отключить уведомления в этом чате
/bd_list или /list_bd — получить данные о Днях рождения в этом чате

И пусть в каждом чате наступит праздник 🥳
'''
