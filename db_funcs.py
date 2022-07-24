import psycopg2


class DatabaseWorkerError(BaseException):
    pass


class BirthDateNotExists(DatabaseWorkerError):
    pass


class DatabaseWorker:
    def __init__(self, database_name):
        self.database = psycopg2.connect(database_name, sslmode='require')
        self.cursor = self.database.cursor()

    # user methods
    def birth_date_exists(self, user_id):
        self.cursor.execute('SELECT b_day FROM users WHERE id = %s', (user_id,))
        day = self.cursor.fetchone()
        if day is None:
            return False
        return True

    def get_birth_date(self, user_id):
        if not self.birth_date_exists(user_id):
            raise BirthDateNotExists

        self.cursor.execute('SELECT b_day FROM users WHERE id = %s', (user_id,))
        day = self.cursor.fetchone()
        self.cursor.execute('SELECT b_month FROM users WHERE id = %s', (user_id,))
        month = self.cursor.fetchone()
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
        self.cursor.execute('SELECT id FROM users WHERE (b_day = %s AND b_month = %s)',
                            (day, month,))
        users_to_notify = self.cursor.fetchall()
        users_to_notify = set(map(lambda user: user[0], users_to_notify))
        return users_to_notify

    # chat methods
    def notification_time_exists(self, chat_id):
        self.cursor.execute('SELECT notification_hour FROM chats WHERE id = %s', (chat_id,))
        hour = self.cursor.fetchone()
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
        self.cursor.execute(
            'SELECT id FROM chats WHERE (notification_hour = %s AND notification_minute = %s)',
            (notification_hour, notification_minute,))
        chats_to_notify = self.cursor.fetchall()
        chats_to_notify = list(map(lambda chat: chat[0], chats_to_notify))

        return chats_to_notify
