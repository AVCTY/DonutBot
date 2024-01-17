import json
import wavelink
import discord
from discord.ext import commands

with open("./Assets/secrets.json", "r") as f:
    data = json.load(f)

BOT_TOKEN = data["BOT_TOKEN"]

intents = discord.Intents.all()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix="d!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="Listening to d!play"))

@bot.event
async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
    print(f"Node {payload.node!r} is ready!")

@bot.command()
async def test(ctx):
    await ctx.send(f"Hello {ctx.author.mention}, I am Donut Music Bot!")

@bot.command()
async def stop(ctx):
    pass

bot.run(BOT_TOKEN)