#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import lxml
import lxml.html
import requests


def elem_content(e):
    return e.text_content().strip()

def parse_details(elems):
    """Return an array of dicts containing details about given matchs
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
    }, ... ]
    """
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
        res.append(match)
    return res


# Fetch html page
res = requests.get("https://matchs.tv/club/real-madrid/")
xml_tree = lxml.html.document_fromstring(res.content)
elems = xml_tree.xpath("//div[@class='container']//table//tr")
matches = parse_details(elems)
print("Upcoming matches:")
for match in matches:
    print(f"- {match['date']} {match['hour']} — {match['teams']} — {match['competition']}")
else:
    print("No upcoming matches within one week.")
