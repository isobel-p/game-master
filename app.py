import os
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
import dotenv
from slack_sdk import WebClient

dotenv.load_dotenv()
flask_app = Flask(__name__)
app = App(token=os.getenv("BOT_TOKEN"), signing_secret=os.getenv("SIGNING_SECRET"))
handler = SlackRequestHandler(app)
client = WebClient(token=os.getenv("BOT_TOKEN"))

@app.command("/greet")
def greet(ack, command):
    ack()
    channel_id = command['channel_id']
    client.chat_postMessage(channel=channel_id, text="*would you like to play a game?*")

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(port=3000)