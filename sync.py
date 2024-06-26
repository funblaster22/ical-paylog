import math
from typing import Union

from icalendar import Calendar
import requests
import pandas as pd
from InquirerPy import inquirer
from datetime import datetime, timezone, date
import re


def get_ical_link():
    try:
        with open("calendar.txt", "r") as file:
            return file.read()
    except FileNotFoundError:
        ical_link = inquirer.text(
            message="Enter the iCal link:",
            validate=lambda selection: len(selection) >= 2,
            invalid_message="Please enter a valid link",
        ).execute()
        with open("calendar.txt", "w") as file:
            file.write(ical_link)
        return ical_link


def format_date(date_datetime: Union[datetime, date]) -> str:
    if isinstance(date_datetime, datetime):
        return date_datetime.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(date_datetime, date):
        return date_datetime.strftime("%Y-%m-%d 00:00:00")


def cvt_cal(ical_url: str):
    ical = Calendar.from_ical(requests.get(ical_url).text)
    rows = []
    for component in ical.walk("VEVENT"):
        start: Union[datetime, date] = component.get("DTSTART").dt
        is_all_day = not isinstance(start, datetime)
        startDate: date = start.date() if isinstance(start, datetime) else start
        if startDate > datetime.now(timezone.utc).date():
            continue  # skip future events
        end: Union[datetime, date] = start if is_all_day else component.get("DTEND").dt
        duration = end - start

        description = component.get("DESCRIPTION", "")
        paydata = {}
        KEY_VAL_REGEX = r"^([A-Za-z]+): +\$?([0-9A-Za-z\.]+)$"
        for key, value in re.findall(KEY_VAL_REGEX, description):
            paydata[key.capitalize()] = value

        # if income present, assume paid today
        income = float(paydata.get("Income", "NaN").strip("$"))
        paid = startDate if not math.isnan(income) else None

        rows.append({
            # convert to local timezone
            "Start": format_date(start),
            "End": format_date(end),
            "Time": str(duration),  # format duration as HH:MM:SS.000
            "Income": income,
            "Tips": float(paydata.get("Tips", "NaN").strip("$")),
            "Paid": paid,
            "Project": component.get("SUMMARY").title(),
            # Decided against subprojects because it would add complexity, plus it makes more sense to make seperate project
            "Description": re.sub(KEY_VAL_REGEX, "", description),
        })
    sorted_rows = sorted(rows, key=lambda obj: obj["Start"])
    return sorted_rows


def set_paid_dates(events: list[dict]):
    paid_dates = {}
    for event in events[::-1]:
        is_all_day = event["Time"] == "0:00:00"
        this_is_paid = event.get("Paid") is not None
        # if not all-day event, only set paid date for current day
        if is_all_day or this_is_paid:
            paid_dates[event["Project"]] = event["Paid"] if this_is_paid and is_all_day else None
        if not this_is_paid:
            event["Paid"] = paid_dates.get(event["Project"])


def main():
    events = cvt_cal(get_ical_link())
    set_paid_dates(events)
    shifts = pd.DataFrame(events)
    shifts.to_csv("shifts.csv", index=False)
    print("Successfully synced with iCal!")


if __name__ == "__main__":
    main()