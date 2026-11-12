import datetime

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def month_grid(year, month, week_start=0):
    first = datetime.date(year, month, 1)
    start = first - datetime.timedelta(days=(first.weekday() - week_start) % 7)
    days = [start + datetime.timedelta(days=i) for i in range(42)]
    return [(day, day.month == month) for day in days]


def shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def weekday_labels(week_start=0):
    return [WEEKDAYS[(week_start + i) % 7] for i in range(7)]
