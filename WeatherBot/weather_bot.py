import os
import re
import spacy
import time
from collections import Counter
from errors import InvalidOptions
from pyowm import OWM
from slackclient import SlackClient
from spacy import load as spacy_load

RTM_READ_DELAY = 1
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

slack_client = SlackClient("")
nlp = spacy_load("en_core_web_lg")
owm = OWM("")


def words(document):
    return re.findall(r"\w+", document.lower())


WORDS = Counter(words(open("city.list.json", errors="ignore").read()))


def P(word, acc=sum(WORDS.values())):
    return WORDS[word] / acc


def fixSpelling(word):
    return max(possibleSpelllings(word), key=P)


def possibleSpelllings(word):
    inFileWord = inFile([word])
    differenceOfOne = inFile(diffOne(word))
    differenceOfTwo = inFile(diffTwo(word))
    unknownWord = [word]
    return inFileWord or differenceOfOne or differenceOfTwo or unknownWord


def inFile(words):
    s = set()
    for w in words:
        if w in WORDS:
            s.add(w)
    return s


def diffOne(word):
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    letterCombinations, rmOneLetter, swapAdjLetters, replaceLetter, addLetter = (
        [],
        [],
        [],
        [],
        [],
    )
    for i in range(len(word) + 1):
        letterCombinations.append((word[:i], word[i:]))
    for L, R in letterCombinations:
        if R:
            rmOneLetter.append(L + R[1:])
    for L, R in letterCombinations:
        if len(R) > 1:
            swapAdjLetters.append(L + R[1] + R[0] + R[2:])
    for L, R in letterCombinations:
        if R:
            for c in alphabet:
                replaceLetter.append(L + c + R[1:])
    for L, R in letterCombinations:
        for c in alphabet:
            addLetter.append(L + c + R)

    return set(rmOneLetter + swapAdjLetters + replaceLetter + addLetter)


def diffTwo(word):
    L = []
    for e1 in diffOne(word):
        for e2 in diffOne(e1):
            L.append(e2)
    return L


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
    for i in range(len(message.split())):
        correct = fixSpelling(message.split()[i])
        if correct in WORDS:
            message += " " + correct
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
        get_detailed_status(weather)[:1].upper() + get_detailed_status(weather)[1:],
        getHumidity(weather),
        getWind(weather),
    )
    return response


def getTemperature(weather):
    return weather.get_temperature("fahrenheit")["temp"]


def get_detailed_status(weather):
    return weather.get_detailed_status()


def getHumidity(weather):
    return str(weather.get_humidity()) + "%"


def getWind(weather):
    wind = str(round(weather.get_wind("miles_hour")["speed"], 2)) + " MPH"
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
