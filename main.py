import discord
from discord.ext import commands
import os

# Configuration ultra-basique
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("-------------------------")
    print(f"✅ BOT CONNECTE : {bot.user}")
    print("-------------------------")

@bot.command()
async def test(ctx):
    await ctx.send("Bobby est bien vivant !")

# Utilisation directe du nom de la variable Railway
token = os.environ.get('DISCORD_TOKEN')

if token:
    bot.run(token)
else:
    print("❌ ERREUR : La variable DISCORD_TOKEN est vide ou introuvable !")
