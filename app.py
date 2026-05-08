import threading
from website import create_app
from bot import bot
import os

app = create_app()

def run_bot():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if token:
        bot.run(token)

if __name__ == '__main__':
    # Start Discord Bot in a background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask App
    app.run(debug=True, use_reloader=False) # use_reloader=False prevents double bot startup
