from sqlite3 import connect


class DatabaseWorkerError(BaseException):
    pass


class BirthDateNotExists(DatabaseWorkerError):
    pass


class DatabaseWorker:
    def __init__(self, database_name):
        self.database = connect(database_name, check_same_thread=False)
        self.cursor = self.database.cursor()

    # user methods
    def birth_date_exists(self, user_id):
        day = self.cursor.execute('SELECT b_day FROM users WHERE id = ?', (user_id,)).fetchone()
        if day is None:
            return False
        return True

    def get_birth_date(self, user_id):
        if not self.birth_date_exists(user_id):
            raise BirthDateNotExists

        day = self.cursor.execute('SELECT b_day FROM users WHERE id = ?', (user_id,)).fetchone()
        month = self.cursor.execute('SELECT b_month FROM users WHERE id = ?', (user_id,)).fetchone()
        return day[0], month[0]

    def set_birth_date(self, user_id, birth_day, birth_month):
        self.cursor.execute('INSERT INTO users (id, b_day, b_month) VALUES(?, ?, ?)', (user_id, birth_day, birth_month))
        self.database.commit()

    def update_birth_date(self, user_id, birth_day, birth_month):
        if not self.birth_date_exists(user_id):
            self.set_birth_date(user_id, birth_day, birth_month)
        else:
            self.cursor.execute('UPDATE users SET b_day = ?, b_month = ? WHERE id = ?',
                                (birth_day, birth_month, user_id,))
            self.database.commit()

    def remove_birth_date(self, user_id):
        if self.birth_date_exists(user_id):
            self.cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            self.database.commit()

    def get_users_to_notify(self, day, month):
        respond = self.cursor.execute('SELECT id FROM users WHERE (b_day = ? AND b_month = ?)',
                                      (day, month,)).fetchall()
        users_to_notify = set()
        for pair in respond:
            users_to_notify.add(pair[0])
        return users_to_notify

    # chat methods
    def notification_time_exists(self, chat_id):
        hour = self.cursor.execute('SELECT notification_hour FROM chats WHERE id = ?', (chat_id,)).fetchone()
        if hour is None:
            return False
        return True

    def set_notification_time(self, chat_id, notification_hour, notification_minute):
        self.cursor.execute('INSERT INTO chats (id, notification_hour, notification_minute) VALUES(?, ?, ?)',
                            (chat_id, notification_hour, notification_minute))
        self.database.commit()

    def update_notification_time(self, chat_id, notification_hour, notification_minute):
        if not self.notification_time_exists(chat_id):
            self.set_notification_time(chat_id, notification_hour, notification_minute)
        else:
            self.cursor.execute('UPDATE chats SET notification_hour = ?, notification_minute = ? WHERE id = ?',
                                (notification_hour, notification_minute, chat_id,))
            self.database.commit()

    def disable_notification(self, chat_id):
        if self.notification_time_exists(chat_id):
            self.cursor.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
            self.database.commit()

    def get_chats_to_notify(self, notification_hour, notification_minute):
        respond = self.cursor.execute('SELECT id FROM chats WHERE (notification_hour = ? AND notification_minute = ?)',
                                      (notification_hour, notification_minute,)).fetchall()
        chats_to_notify = list()
        for pair in respond:
            chats_to_notify.append(pair[0])

        return chats_to_notify
