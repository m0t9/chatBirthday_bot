# calendar and time utils

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


def is_date_correct(day, month):
    return (month in month_properties) and (1 <= day <= month_properties[month].day_count)


def is_time_correct(hours, minutes):
    return (0 <= hours < 24) and (0 <= minutes < 60)


# arguments utils

def get_args(text):
    return (text.split())[1:]


# Zodiac sign utils

stickers = ['♒️', '♓️', '♈️', '♉️', '♊️', '♋️', '♌️', '♍️', '♎️', '♏️', '♐️', '♑️']
months = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
dates = [[21, 1], [19, 2], [21, 3], [21, 4], [22, 5], [22, 6], [23, 7], [24, 8], [24, 9], [24, 10], [23, 11], [22, 12]]


def get_number_of_day(day: int, month: int):
    number = day
    for i in range(0, month - 1):
        number += months[i]
    return number


def get_zodiac(day: int, month: int):
    for i in range(0, 11):
        if get_number_of_day(dates[i][0], dates[i][1]) <= get_number_of_day(day, month) < get_number_of_day(
                dates[i + 1][0], dates[i + 1][1]):
            return stickers[i]
    return stickers[11]
