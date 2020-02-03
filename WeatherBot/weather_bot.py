import os
import time
import re
import spacy
from slackclient import SlackClient
from spacy import load as spacy_load
from pyowm import OWM
from errors import InvalidOptions

slack_client = SlackClient("xoxb-916817055062-921192447891-jHAJWDfvKbgLCs9AKty6GFCK")
nlp = spacy_load("en_core_web_sm")
owm = OWM("e00689123ab6db5f5d9c7d9358b4a90b")

RTM_READ_DELAY = 1
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"


def parse_bot_commands(slack_events, starterbot_id):
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == starterbot_id:
                return message, event["channel"]
    return None, None


def parse_direct_mention(message_text):
    matches = re.search(MENTION_REGEX, message_text)
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)


def process(message):
    doc = nlp(message)
    subject = get_subject(message)
    location = getLocation(doc.ents)
    return subject, location


def get_subject(message):
    if "temperature" in message:
        return "temperature"
    elif "weather" in message:
        return "weather"
    raise InvalidOptions("Please select weather or temperature")


def getLocation(entities):
    location = None
    for entity in entities:
        if entity.label_ == "GPE":
            location = entity.text
    if location is None:
        raise InvalidOptions("Please enter a valid location!")
    return location


def printTemperature(location, weather):
    return "It is currently {}ºF in {}.".format(getTemperature(weather), location)


def printWeather(location, weather):
    response = printTemperature(location, weather)
    response += "\n{} with {} humidity and wind speeds of {}.".format(
        get_detailed_status(weather), getHumidity(weather), getWind(weather)
    )
    return response


def getTemperature(weather):
    return weather.get_temperature("fahrenheit")["temp"]


def get_detailed_status(weather):
    return weather.get_detailed_status()


def getHumidity(weather):
    return str(weather.get_humidity()) + "%"


def getWind(weather):
    wind = str(round(weather.get_wind("miles_hour")['speed'], 2)) + " MPH"
    return wind


def handle_command(command, channel):
    try:
        query = process(command)

        if query[0] == "temperature":
            response = printTemperature(
                query[1], owm.weather_at_place(query[1]).get_weather()
            )
        else:
            response = printWeather(
                query[1], owm.weather_at_place(query[1]).get_weather()
            )
    except InvalidOptions as e:
        response = str(e)
    slack_client.api_call("chat.postMessage", channel=channel, text=response)


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Bot is running")
        starterbot_id = slack_client.api_call("auth.test")["user_id"]

        while True:
            command, channel = parse_bot_commands(
                slack_client.rtm_read(), starterbot_id
            )

            if command:
                handle_command(command, channel)

            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed.")
