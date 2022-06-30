import psycopg2
from psycopg2.errors import DuplicateTable


class DatabaseWorkerError(BaseException):
    pass


class BirthDateNotExists(DatabaseWorkerError):
    pass


class DatabaseWorker:
    def __init__(self, database_name):
        self.database = psycopg2.connect(database_name, sslmode='require')
        self.cursor = self.database.cursor()
        initial_commands = [
            '''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                b_day INTEGER NOT NULL,
                b_month INTEGER NOT NULL
            )''',
            '''CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY,
                notification_hour INTEGER NOT NULL,
                notification_minute INTEGER NOT NULL
            )
            '''
        ]

        for command in initial_commands:
            self.cursor.execute(command)

        self.database.commit()

    # user methods
    def birth_date_exists(self, user_id):
        day = self.cursor.execute('SELECT b_day FROM users WHERE id = %s', (user_id,)).fetchone()
        if day is None:
            return False
        return True

    def get_birth_date(self, user_id):
        if not self.birth_date_exists(user_id):
            raise BirthDateNotExists

        day = self.cursor.execute('SELECT b_day FROM users WHERE id = %s', (user_id,)).fetchone()
        month = self.cursor.execute('SELECT b_month FROM users WHERE id = %s', (user_id,)).fetchone()
        return day[0], month[0]

    def set_birth_date(self, user_id, birth_day, birth_month):
        self.cursor.execute('INSERT INTO users (id, b_day, b_month) VALUES(%s, %s, %s)',
                            (user_id, birth_day, birth_month))
        self.database.commit()

    def update_birth_date(self, user_id, birth_day, birth_month):
        if not self.birth_date_exists(user_id):
            self.set_birth_date(user_id, birth_day, birth_month)
        else:
            self.cursor.execute('UPDATE users SET b_day = %s, b_month = %s WHERE id = %s',
                                (birth_day, birth_month, user_id,))
            self.database.commit()

    def remove_birth_date(self, user_id):
        if self.birth_date_exists(user_id):
            self.cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
            self.database.commit()

    def get_users_to_notify(self, day, month):
        respond = self.cursor.execute('SELECT id FROM users WHERE (b_day = %s AND b_month = %s)',
                                      (day, month,)).fetchall()
        users_to_notify = set()
        for pair in respond:
            users_to_notify.add(pair[0])
        return users_to_notify

    # chat methods
    def notification_time_exists(self, chat_id):
        hour = self.cursor.execute('SELECT notification_hour FROM chats WHERE id = %s', (chat_id,)).fetchone()
        if hour is None:
            return False
        return True

    def set_notification_time(self, chat_id, notification_hour, notification_minute):
        self.cursor.execute('INSERT INTO chats (id, notification_hour, notification_minute) VALUES(%s, %s, %s)',
                            (chat_id, notification_hour, notification_minute))
        self.database.commit()

    def update_notification_time(self, chat_id, notification_hour, notification_minute):
        if not self.notification_time_exists(chat_id):
            self.set_notification_time(chat_id, notification_hour, notification_minute)
        else:
            self.cursor.execute('UPDATE chats SET notification_hour = %s, notification_minute = %s WHERE id = %s',
                                (notification_hour, notification_minute, chat_id,))
            self.database.commit()

    def disable_notification(self, chat_id):
        if self.notification_time_exists(chat_id):
            self.cursor.execute('DELETE FROM chats WHERE id = %s', (chat_id,))
            self.database.commit()

    def get_chats_to_notify(self, notification_hour, notification_minute):
        respond = self.cursor.execute(
            'SELECT id FROM chats WHERE (notification_hour = %s AND notification_minute = %s)',
            (notification_hour, notification_minute,)).fetchall()
        chats_to_notify = list()
        for pair in respond:
            chats_to_notify.append(pair[0])

        return chats_to_notify
