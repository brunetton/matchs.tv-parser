#! /usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Usage:
    {self_filename} [options]
    {self_filename} -h | --help

Options:
    --no-sms                                      do not send SMS (for testing purpose)
    --catch-exceptions                            do not stop on exceptions, but send SMS with error messages
                                                    (unless --no-sms is provided)
    -h --help                                     show this help message and exit
"""

import datetime
import logging
import os
from pathlib import Path

import dateparser
import lxml
import lxml.html
import requests
from docopt import docopt
from dotenv import load_dotenv
from requests import Session, exceptions
from requests.adapters import HTTPAdapter
from urllib3 import Retry


def elem_content(e):
    return e.text_content().strip()


def parse_details(url: str):
    """Get url and parse html page to extract match details.
    Make use of global REQUESTS_SESSION to benefit from retry mechanism.
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
    res = REQUESTS_SESSION.get(url)
    xml_tree = lxml.html.document_fromstring(res.content)
    page_tables = xml_tree.xpath("//div[@class='container']//table")
    if len(page_tables) == 0:
        return []  # No matchs found
    elif len(page_tables) == 1:
        table = page_tables[0]
    elif len(page_tables) == 2:
        table = page_tables[1]  # If there are 2 tables, the first one is for today or past matchs
    else:
        raise Exception(f"Unexpected number of tables in html page: {len(page_tables)}")
    elems = table.xpath(".//tr")
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
            "date": elem_content(date[0]),
            "hour": elem_content(details.xpath(".//td[@class='date']")[0]),
            "teams": elem_content(details.xpath(".//td[@class='fixture']/h4")[0]),
            "competition": elem_content(details.xpath(".//div[@class='competitions']")[0]),
        }
        match.update(
            {"id": f"{match['date']} {datetime.date.today().year} — {match['hour']} — {match['teams']}"}
        )
        res.append(match)
    return res


def parse_date_fr(date_str: str) -> datetime.datetime:
    """Parse a French date string like "mercredi 8 juin 2025" or "mercredi 8 juin"
    and return a datetime object.
    - raises an Exception if the date cannot be parsed
    - if year is not provided, next date occurring will be used
    - do not takes into account the first word (day of the week)
    """
    dt = dateparser.parse(date_str, settings={"PREFER_DATES_FROM": "future"}, languages=["fr"])
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


def scrap_matches(let_send_sms: bool = True) -> None:
    """Scrap matches from matchs.tv and send SMS for upcoming matches within one week."""
    # Scraping
    matches = parse_details("https://matchs.tv/club/real-madrid")
    matches += parse_details("https://matchs.tv/club/fc-barcelone")
    matches += parse_details("https://matchs.tv/club/manchester-city")
    matches += parse_details("https://matchs.tv/club/liverpool")
    matches += parse_details("https://matchs.tv/club/bayern-munich")
    print("All matches:")
    for match in matches:
        print(f"- {match['date']} {match['hour']} — {match['teams']} — {match['competition']}")
    print("")
    filtered_matches = [
        match for match in matches if not is_in_more_than_one_week(parse_date_fr(match["date"]))
    ]
    if filtered_matches:
        # Sort by date
        filtered_matches.sort(key=lambda m: parse_date_fr(m["date"]))
        print("Upcoming matches (filtered):")
        matches_str = "\n".join(
            [
                f"- {match['date']} {match['hour']} — {match['teams']} — {match['competition']}"
                for match in filtered_matches
            ]
        )
        print(matches_str)
        if let_send_sms:
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
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    # Setup requests with retry mechanism
    REQUESTS_SESSION = Session()
    # http://www.coglib.com/~icordasc/blog/2014/12/retries-in-requests.html
    # backoff_factor=2 will make sleep for 2 * (2 ^ (retry_number - 1)), ie 0, 2, 4, 8, 16, 32 ... up to 1 hour (for total=12)
    requests_retry = Retry(
        total=15, backoff_factor=2, status_forcelist=[500, 501, 502, 503, 504]
    )  # retry when server return ont of this statuses
    REQUESTS_SESSION.mount("http://", HTTPAdapter(max_retries=requests_retry))
    REQUESTS_SESSION.mount("https://", HTTPAdapter(max_retries=requests_retry))
    # Makes urllib warn about connections errors and retries
    urllib3_logger = logging.getLogger("urllib3.connectionpool")
    urllib3_logger.setLevel(logging.INFO)

    # Run script
    try:
        scrap_matches(not args["--no-sms"])
    except Exception as e:
        if args["--catch-exceptions"]:
            print(f"Exception occurred: {e}")
            if not args["--no-sms"]:
                send_sms(requests.utils.quote(f"Error in matchs.tv script: {e}"))
        else:
            raise e
