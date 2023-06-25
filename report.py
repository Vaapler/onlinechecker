import datetime
import os
import pandas as pd
import json

SECONDS_IN_DAY = 60 * 60 * 24
DATE_FILE_FORMAT = "%m-%d.txt"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
REPORT_PREFIX = "reports/raw/"

report_date = input("Выберите дату в формате месяц-день >> ") + ".txt"
report_date = datetime.datetime.strptime(report_date, DATE_FILE_FORMAT)

report_table = pd.DataFrame()
report_table["---"] = ["Название сервиса", "Время простоя", "Интервалы простоя", "uptime"]

for service_name in os.listdir(REPORT_PREFIX):
    service_folder = REPORT_PREFIX + service_name + "/"
    filename = service_folder + report_date.strftime(DATE_FILE_FORMAT)
    with open(filename, "r") as file:
        down_time = json.load(file)
    data = [service_name, 0, "", 0]
    for down_interval in down_time:
        start_time, end_time = [datetime.datetime.strptime(i, DATE_FORMAT) for i in down_interval]
        data[1] += (end_time - start_time).seconds
        data[2] += start_time.strftime(DATE_FORMAT) + "-" + end_time.strftime(DATE_FORMAT)
    data[3] = round((SECONDS_IN_DAY - data[1]) / SECONDS_IN_DAY * 100, 2)
    data[2] = "---" if not data[2] else data[2]

    report_table[service_name] = data

report_table.to_csv(report_date.strftime("%d-%m-report.csv"), header=False, index=False)
