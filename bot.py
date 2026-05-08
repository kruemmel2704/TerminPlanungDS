import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.members = True  # Wichtig, um Mitglieder und Rollen zu sehen

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} ist jetzt online und bereit für den Dienst!')
    print(f'Server-ID: {os.getenv("DISCORD_GUILD_ID")}')

@bot.command()
async def status(ctx):
    await ctx.send('Ich bin online und die Termin-App ist bereit!')

if __name__ == '__main__':
    if not TOKEN:
        print("❌ Fehler: Kein DISCORD_BOT_TOKEN in der .env gefunden!")
    else:
        bot.run(TOKEN)
