#! /usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Usage:
    {self_filename} [options]
    {self_filename} -h | --help

Options:
    --no-sms                                      do not send SMS (for testing purpose)
"""

import datetime
import os
from pathlib import Path

import dateparser
import lxml
import lxml.html
import requests
from docopt import docopt
from dotenv import load_dotenv


def elem_content(e):
    return e.text_content().strip()


def parse_details(url: str):
    """Get url and parse html page to extract match details.
    Return an array of dicts containing details about given matchs
    Args:
        elems: array of tr from html page
    Returns:
        array of dicts
    Example:
    [{
        'date': 'mercredi 18 juin',
        'hour': '21h00',
        'teams': 'Real Madrid - Al-Hilal',
        'competition': 'Coupe du Monde des Clubs, Match de groupe 1',
        'id': 'mercredi 18 juin 2025 — 21h00 — Real Madrid - Al-Hilal',
    }, ... ]
    """
    # Fetch html page
    print(f"-> {url} ...")
    res = requests.get(url)
    xml_tree = lxml.html.document_fromstring(res.content)
    elems = xml_tree.xpath("//div[@class='container']//table//tr")
    # Browse through tr elements by groups of 2
    res = []
    elems_iter = iter(elems)
    while True:
        # Take tr two by two as html page is built like <tr>DATE</tr> <tr>MATCH DETAILS</tr>
        try:
            date = next(elems_iter)
            details = next(elems_iter)
        except StopIteration:
            # No more matchs to parse
            break
        match = {
            'date': elem_content(date[0]),
            'hour': elem_content(details.xpath(".//td[@class='date']")[0]),
            'teams': elem_content(details.xpath(".//td[@class='fixture']/h4")[0]),
            'competition': elem_content(details.xpath(".//div[@class='competitions']")[0])
        }
        match.update({'id': f"{match['date']} {datetime.date.today().year} — {match['hour']} — {match['teams']}"})
        res.append(match)
    return res


def parse_date_fr(date_str: str) -> datetime.datetime:
    """Parse a French date string like "mercredi 8 juin 2025" or "mercredi 8 juin"
    and return a datetime object.
    - raises an Exception if the date cannot be parsed
    - if year is not provided, next date occurring will be used
    - do not takes into account the first word (day of the week)
    """
    dt = dateparser.parse(
        date_str, settings={"PREFER_DATES_FROM": "future"}, languages=["fr"]
    )
    if not dt:
        raise Exception("Unparsed date")
    return dt


def is_in_more_than_one_week(dt: datetime.datetime) -> bool:
    """
    Check if the given date is more than one week from now.
    >>> from datetime import datetime, timedelta
    >>> now = datetime.now()
    >>> is_in_more_than_one_week(now + timedelta(days=10))
    True
    >>> is_in_more_than_one_week(now - timedelta(days=3))
    False
    >>> is_in_more_than_one_week(now + timedelta(days=3))
    False
    """
    diff = dt - datetime.datetime.now()
    return diff > datetime.timedelta(days=7)


def send_sms(message: str) -> None:
    sms_base_url = "https://smsapi.free-mobile.fr/sendmsg"
    sms_user = os.getenv("SMSAPI_USER")
    sms_pass = os.getenv("SMSAPI_PASS")
    sms_url = f"{sms_base_url}?user={sms_user}&pass={sms_pass}&msg={message}"
    response = requests.get(sms_url)
    if response.status_code == 200:
        print(f"SMS sent successfully")
    else:
        print(f"Failed to send SMS !\n{message}\nstatus code: {response.status_code}")


def scrap_matches(send_sms: bool = True) -> None:
    """Scrap matches from matchs.tv and send SMS for upcoming matches within one week."""
    # Scraping
    matches = parse_details("https://matchs.tv/club/real-madrid")
    matches += parse_details("https://matchs.tv/club/fc-barcelone")
    matches += parse_details("https://matchs.tv/club/manchester-city")
    matches += parse_details("https://matchs.tv/club/liverpool")
    matches += parse_details("https://matchs.tv/club/bayern-munich")
    print("All matches:")
    for match in matches:
        print(
            f"- {match['date']} {match['hour']} — {match['teams']} — {match['competition']}"
        )
    print("")
    filtered_matches = [
        match
        for match in matches
        if not is_in_more_than_one_week(parse_date_fr(match["date"]))
    ]
    if filtered_matches:
        print("Upcoming matches (filtered):")
        for match in filtered_matches:
            print(
                f"- {match['date']} {match['hour']} — {match['teams']} — {match['competition']}"
            )
            sms_msg = requests.utils.quote(
                f"Upcoming match: {match['teams']} — {match['date']} — {match['hour']} — ({match['competition']})"
            )
            send_sms(sms_msg)
        if send_sms:
            send_sms(requests.utils.quote(f"Prochains matchs:\n{matches_str}"))
    else:
        print("No upcoming matches within one week.")


if __name__ == "__main__":
    # Parse command line arguments
    args = docopt(__doc__.format(self_filename=Path(__file__).name))
    # Load env
    load_dotenv()
    # Check if environment variables are defined (typically in .env file)
    required_env_vars = ["SMSAPI_USER", "SMSAPI_PASS"]
    for var in required_env_vars:
        if not os.getenv(var):
            raise EnvironmentError(f"Missing required environment variable: {var}")

    # Run script
    try:
        scrap_matches(not args["--no-sms"])
    except Exception as e:
        print(f"Exception occurred: {e}")
        if not args["--no-sms"]:
            send_sms(requests.utils.quote(f"Error in matchs.tv script: {e}"))
