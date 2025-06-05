import os
import random
import requests
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
import dotenv
from slack_sdk import WebClient
import re

dotenv.load_dotenv()
flask_app = Flask(__name__)
app = App(token=os.getenv("BOT_TOKEN"), signing_secret=os.getenv("SIGNING_SECRET"))
handler = SlackRequestHandler(app)
client = WebClient(token=os.getenv("BOT_TOKEN"))
wordle_games = {}
temp_games = {} 

with open("wordle.txt", "r") as f:
    wordles = [line.strip() for line in f if len(line.strip()) == 5]

def wordle_feedback(guess, answer):
    result, used = [], [False]*5
    answer, guess = list(answer), list(guess)
    for i in range(5):
        if guess[i] == answer[i]:
            result.append("🟩")
            used[i] = True
        else:
            result.append(None)
    for i in range(5):
        if result[i] is not None:
            continue
        if guess[i] in answer:
            for j in range(5):
                if not used[j] and guess[i] == answer[j]:
                    result[i] = "🟨"
                    used[j] = True
                    break
            else:
                result[i] = "⬜"
        else:
            result[i] = "⬜"
    return "".join(result)

@app.command("/game")
def game(ack, command):
    ack()
    channel_id = command['channel_id']
    user_id = command['user_id']
    response = client.chat_postMessage(
        channel=channel_id,
        text=f"*would you like to play a game, <@{user_id}>?*"
    )
    thread_ts = response["ts"]
    client.chat_postMessage(
        channel=channel_id,
        text="Choose a game to play",
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "choose a game to play..."}
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Wordle", "emoji": True},
                        "value": "wordle",
                        "action_id": "wordle"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Weather Hopper", "emoji": True},
                        "value": "guess_temp",
                        "action_id": "guess_temp"
                    }
                ]
            }
        ],
        thread_ts=thread_ts
    )

@app.action("wordle")
def wordle(ack, body, client):
    ack()
    channel_id = body["channel"]["id"]
    parent_ts = body["message"].get("thread_ts") or body["message"]["ts"]
    chosen = random.choice(wordles)
    wordle_games[parent_ts] = {"word": chosen, "guesses": 0}
    client.reactions_add(channel=channel_id, name="wordle", timestamp=parent_ts)
    for msg in [
        "if you're ready... begin! type help for help, if you need it.",
        "hit me with your guesses in thread! :downvotex:"
    ]:
        client.chat_postMessage(channel=channel_id, thread_ts=parent_ts, text=msg)

@app.event("message")
def guess(event, say):
    if event.get("subtype") == "bot_message":
        return
    thread_ts = event.get("thread_ts")
    user_id = event.get("user")
    text = event.get("text", "").strip().lower()

    if thread_ts in wordle_games:
        if text == "help":
            for msg in [
                "i'm thinking of a word. it's a 5-letter word and you've got to try and guess it.",
                "🟩=right letter in right place, 🟨=right letter in wrong place, ⬜=wrong letter.",
                "now go forth and play!"
            ]:
                say(text=msg, thread_ts=thread_ts)
            return
        if len(text) != 5 or not text.isalpha():
            say(text="hey wait, that's not 5 letters!", thread_ts=thread_ts)
            return
        if text not in wordles:
            say(text="hey wait, that's not a word! or at least, not according to me.", thread_ts=thread_ts)
            return
        game = wordle_games[thread_ts]
        game["guesses"] += 1
        answer = game["word"]
        feedback = wordle_feedback(text, answer)
        if text == answer:
            say(
                text=f"{feedback}\n🎉 welp, you did it. and it only took {game['guesses']} tries. but can you do it again? :orpheus:",
                thread_ts=thread_ts
            )
            del wordle_games[thread_ts]
        else:
            say(text=f"{feedback}\nnope, guess again!", thread_ts=thread_ts)
        return

    if thread_ts in temp_games:
        game = temp_games[thread_ts]
        if text == "answer":
            if not game["guesses"]:
                say(text="ahem, you have to _make_ a guess first!", thread_ts=thread_ts)
                del temp_games[thread_ts]
                return
            closest_user, closest_guess = min(
                game["guesses"].items(),
                key=lambda item: abs(item[1] - game["temp"])
            )
            say(
                text=f"drum roll... the temperature in {game['location']} is {game['temp']}°C! 🎉\n",
                thread_ts=thread_ts
            )
            say (
                text = f"so that means you won, <@{closest_user}>. you guessed {closest_guess}°C. but can you do it again?",
                thread_ts=thread_ts
            )
            del temp_games[thread_ts]
            return
        match = re.search(r"(-?\d+)", text)
        if match:
            guess = int(match.group(1))
            game["guesses"][user_id] = guess
            say(text=f"ok <@{user_id}>, let's see how close your guess of {guess} was!", thread_ts=thread_ts)
        return

@app.action("guess_temp")
def guess_temp(ack, body, client):
    ack()
    channel_id = body["channel"]["id"]
    parent_ts = body["message"].get("thread_ts") or body["message"]["ts"]
    cities = ["London", "Paris", "New York", "Tokyo", "Sydney", "Cairo", "Rio de Janeiro"]
    location = random.choice(cities)
    resp = requests.get(f"https://api.open-meteo.com/v1/forecast?current_weather=true&latitude=0&longitude=0")
    coords = {
        "London": (51.5074, -0.1278),
        "Paris": (48.8566, 2.3522),
        "New York": (40.7128, -74.0060),
        "Tokyo": (35.6895, 139.6917),
        "Sydney": (-33.8688, 151.2093),
        "Cairo": (30.0444, 31.2357),
        "Rio de Janeiro": (-22.9068, -43.1729)
    }
    lat, lon = coords[location]
    weather = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    ).json()
    temp = int(round(weather["current_weather"]["temperature"]))
    temp_games[parent_ts] = {"location": location, "temp": temp, "guesses": {}}
    client.reactions_add(channel=channel_id, name="beach_with_umbrella", timestamp=parent_ts)
    client.chat_postMessage(
        channel=channel_id,
        thread_ts=parent_ts,
        text=f"make your guesses! what's the temperature (°C) in *{location}* right now? type a number in this thread or type `answer` to reveal the answer."
    )

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(port=8000)