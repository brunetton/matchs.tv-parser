#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import os

import lxml
import lxml.html
import requests
from dotenv import load_dotenv


def elem_content(e):
    return e.text_content().strip()

def parse_details(url):
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


def parse_date_fr(date_str):
    months_fr = {
        'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
        'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
    }

    parts = date_str.split()
    day = int(parts[1])
    month_name = parts[2].lower()
    month = months_fr.get(month_name)
    year = int(parts[3]) if len(parts) >= 4 else datetime.datetime.now().year

    if month:
        dt = datetime.datetime(year, month, day)
        # print(dt.date())
        return(dt)
    else:
        raise Exception("Unparsed month")


def is_in_more_than_one_week(dt):
    diff = dt - datetime.datetime.now()
    return diff > datetime.timedelta(days=7)

def send_sms(match):
    sms_base_url = "https://smsapi.free-mobile.fr/sendmsg"
    sms_user = os.getenv('SMSAPI_USER')
    sms_pass = os.getenv('SMSAPI_PASS')
    sms_msg = requests.utils.quote(
        f"Upcoming match: {match['teams']} — {match['date']} — {match['hour']} — ({match['competition']})"
    )
    sms_url = f"{sms_base_url}?user={sms_user}&pass={sms_pass}&msg={sms_msg}"
    response = requests.get(sms_url)
    if response.status_code == 200:
        print(f"SMS sent successfully for match: {match['id']}")
    else:
        print(f"Failed to send SMS for match: {match['id']}, status code: {response.status_code}")

# Load env
load_dotenv()
# Check if environment variables are defined (typically in .env file)
required_env_vars = ['SMSAPI_USER', 'SMSAPI_PASS']
for var in required_env_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

# Scrapping
matches = parse_details("https://matchs.tv/club/real-madrid")
matches += parse_details("https://matchs.tv/club/fc-barcelone")
matches += parse_details("https://matchs.tv/club/manchester-city")
matches += parse_details("https://matchs.tv/club/liverpool")
matches += parse_details("https://matchs.tv/club/bayern-munich")
print("All matches:")
for match in matches:
    print(f"- {match['date']} {match['hour']} — {match['teams']} — {match['competition']}")
print("")
filtered_matches = [match for match in matches if not is_in_more_than_one_week(parse_date_fr(match['date']))]
if filtered_matches:
    print("Upcoming matches (filtered):")
    for match in filtered_matches:
        print(f"- {match['date']} {match['hour']} — {match['teams']} — {match['competition']}")
        send_sms(match)
else:
    print("No upcoming matches within one week.")
