import json
import asyncio
import logging
from typing import cast

import discord
from discord.ext import commands

import wavelink


with open("C:/Users/User/Desktop/Portfolio/DiscordBots/DB/Assets/secrets.json", "r") as f:
    data = json.load(f)

BOT_TOKEN = data["BOT_TOKEN"]

# Function to calculate milliseconds into minutes and seconds
def ms_convert(duration: int) -> list[int]:
    """
    Time converter to convert milliseconds into a list of minutes and seconds
    
    Returns [minutes: int, seconds: int]
    Type: <class 'list'>
    """
    # time conversion for item length
    mill_sec = duration
    total_sec = mill_sec / 1000
    mins = int(total_sec // 60)
    secs = int(total_sec % 60)

    return [mins, secs]

# Bot class
class Bot(commands.Bot):
    def __init__(self) -> None:
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True

        discord.utils.setup_logging(level=logging.INFO)
        super().__init__(command_prefix="d!", intents=intents)

    async def setup_hook(self) -> None:
        nodes = [wavelink.Node(uri="http://localhost:2333", password="youshallnotpass")]

        await wavelink.Pool.connect(nodes=nodes, client=self)

    async def on_ready(self) -> None:
        logging.info(f"Logged in: {self.user} | {self.user.id}")

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        logging.info(f"Wavelink Node connected: {payload.node!r} | Resumed: {payload.resumed}")

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player: wavelink.Player | None = payload.player
        if not player:
            # Handle edge cases...
            return

        original: wavelink.Playable | None = payload.original
        track: wavelink.Playable = payload.track

        embed: discord.Embed = discord.Embed(title="Now Playing")
        embed.description = f"**[{track.title}]({track.uri})** by `{track.author}`"

        if track.artwork:
            embed.set_image(url=track.artwork)

        if original and original.recommended:
            embed.description += f"\n\n`This track was recommended via {track.source}`"

        if track.album.name:
            embed.add_field(name="Album", value=track.album.name)

        await player.home.send(embed=embed)


bot: Bot = Bot()

# Play command
@bot.command()
async def play(ctx: commands.Context, query: str) -> None:
    if not ctx.guild:
        return
    
    player: wavelink.Player
    player = cast(wavelink.player, ctx.voice_client)

    if not player:
        try:
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        except AttributeError:
            await ctx.send("Please join a voice channel first before using this command.")
            return
        except discord.ClientException:
            await ctx.send("I was unable to join this voice channel. Please try again.")
            return
        
    # Turn on AutoPlay
    # enabled = AutoPlay will automatically play songs in the queue and fetch recommendations after queue finishes
    # partial = AutoPlay will automatically play songs in the queue but will not fetch recommendations after queue finishes
    # disabled = AutoPlay will do nothing
    player.autoplay = wavelink.AutoPlayMode.partial # set to only play songs in queue without fetching recommendations after

    # Lock player to this channel
    if not hasattr(player, "home"):
        player.home = ctx.channel
    elif player.home != ctx.channel:
        await ctx.send(f"You can only play songs in {player.home.mention}, as the player has already started there.")
        return
    

    # This will handle fetching Tracks and Playlists...
    # See the doc strings for more information on this method...
    # If spotify is enabled via LavaSrc, this will automatically fetch Spotify tracks if you pass a URL...
    # Defaults to YouTube for non URL based queries...
    tracks: wavelink.Search = await wavelink.Playable.search(query)
    if not tracks:
        await ctx.send(f"{ctx.author.mention} - Could not find any tracks for that song. Please try again.")
        return

    if isinstance(tracks, wavelink.Playlist):
        # tracks is a playlist...
        added: int = await player.queue.put_wait(tracks)
        await ctx.send(f"Added the playlist **`{tracks.name}`** ({added} songs) to the queue.")
    else:
        message = "Top 5 Results:\n"
        results = tracks[:5] # gets the top 5 results from tracks list

        # Get the first 5 results
        for index, song in enumerate(results):
            # time conversion for item length
            # song_length[0] is minutes and song_length[1] is seconds
            song_length = ms_convert(song.length)

            message += f"**{index+1}**. {song.title} - *{song_length[0]}:{song_length[1]}*\n"

        message += "\nEnter a number for the song you want to choose:"
        await ctx.send(message)

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel
        
        try:
            choice_msg = await bot.wait_for("message", check=check, timeout=20)
            choice = int(choice_msg.content)

            if choice < 1 or choice > 5:
                await ctx.send("Invalid choice, enter number from 1 to 5 only")
                return
            
            track: wavelink.Playable = tracks[choice - 1]
            await player.queue.put_wait(track)
            await ctx.send(f"Added **`{track}`** to the queue.")
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond.")

    if not player.playing:
        # Play now since we aren't playing anything...
        await player.play(player.queue.get(), volume=10)


# View the Player Queue command
@bot.command(aliases=["q"])
async def queue(ctx: commands.Context, page_num=None) -> None:
    """Views the queue to see what songs are queued up"""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

    if not player:
        return
    
    # if queue exists
    if player.queue:
        # if queue is longer than 10
        if player.queue.count > 10:
            # paginating the queues for every 10 tracks
            paginated_queue = [player.queue[i:i+10] for i in range(0, len(player.queue), 10)]

            # if page number is none, return first page as default
            if page_num == None:
                # message for queue pages
                message = f"Queue: **1** of **{len(paginated_queue)}** pages\n"
                
                # gets the tracks from the first page
                for index, song in enumerate(paginated_queue[0]):
                    # time conversion for item length
                    song_length = ms_convert(song.length)

                    message += f"**{index+1}**. {song.title} - *{song_length[0]}:{song_length[1]}*\n"
                await ctx.send(message)
            # if page number is a digit and isn't 0 return that page in the queue
            elif page_num.isdigit() and page_num != 0:
                #ensure that the page_num input is integer
                page_num = int(page_num)

                message = f"Queue: **{page_num}** of **{len(paginated_queue)}** pages\n"

                # gets the tracks from the first page
                for index, song in enumerate(paginated_queue[page_num-1]):
                    # time conversion for item length
                    song_length = ms_convert(song.length)

                    message += f"**{index+1}**. {song.title} - *{song_length[0]}:{song_length[1]}*\n"
                await ctx.send(message)
            else:
                await ctx.send("Invalid page number")
        elif player.queue.count > 0 and player.queue.count <= 10:
            # set message to 1 of 1 page in queue
            message = f"Queue: 1 of {len(player.queue)}\n"

            # loop through queue add tracks to message
            for index, song in enumerate(player.queue):
                song_length = ms_convert(song.length)

                message += f"**{index+1}**. {song.title} - *{song_length[0]}:{song_length[1]}*\n"

            # send formatted message for queue
            await ctx.send(message)
        else:
            return
    elif not player.queue:
        await ctx.send("The queue is currently empty")
    else:
        await ctx.send("Something went wrong...")


# Skip song command
@bot.command()
async def skip(ctx: commands.Context) -> None:
    """Skip the current song."""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return

    await player.skip(force=True)
    await ctx.message.add_reaction("\u2705")


# Pause and Resume Player command
@bot.command(name="toggle", aliases=["pause", "resume"])
async def pause_resume(ctx: commands.Context) -> None:
    """Pause or Resume the Player depending on its current state."""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

    if not player:
        return
    
    await player.pause(not player.paused)
    await ctx.message.add_reaction("\u2705")


# Player volume control command
@bot.command()
async def volume(ctx: commands.Context, value: int) -> None:
    """Change the volume of the player."""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return

    await player.set_volume(value)
    await ctx.message.add_reaction("\u2705")


# Disconnect Player command
@bot.command(aliases=["dc"])
async def disconnect(ctx: commands.Context) -> None:
    """Disconnect the Player."""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return

    await player.disconnect()
    await ctx.message.add_reaction("\u2705")


# tester command
@bot.command()
async def test(ctx: commands.Context, query=None):
    if query == None:
        await ctx.send(f"Hello, there {ctx.author.mention}!")
    elif query != None:
        if query.isdigit() and query != 0:
            await ctx.send(f"Hello, there {ctx.author.mention}! Your number is: {query}.")
        else:
            await ctx.send(f"Hello, there {ctx.author.mention}! Your query is: {query}.")


async def main() -> None:
    async with bot:
        await bot.start(BOT_TOKEN)

asyncio.run(main())