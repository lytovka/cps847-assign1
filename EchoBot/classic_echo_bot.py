import os
from slackclient import SlackClient


client = SlackClient(slack_token)


def say_hello(data):
    channel_id = data["channel"]
    thread_ts = data["ts"]

    client.api_call(
        "chat.postMessage", channel=channel_id, text=data["text"], thread_ts=thread_ts
    )


if client.rtm_connect():
    while client.server.connected is True:
        for data in client.rtm_read():
            if "type" in data and data["type"] == "message":
                say_hello(data)
else:
    print("Connection Failed")
