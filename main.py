import json
import asyncio
import logging
from typing import cast
from time_converter import ms_convert
from queue_menu import QueueMenu

import discord
from discord.ext import commands

import wavelink


with open("secrets.json", "r") as f:
    data = json.load(f)

BOT_TOKEN = data["BOT_TOKEN"]

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
        embed.description = f"**[{track.title}]({track.uri})**  - *{ms_convert(track.length)}* by `{track.author}`"

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
async def play(ctx: commands.Context, *, query: str) -> None:
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

            message += f"**{index+1}**. **{song.title}** - *{song_length}*\n"

        message += "\nEnter a number for the song you want to choose:"
        await ctx.send(message)

        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel
        
        try:
            choice_msg = await bot.wait_for("message", check=check, timeout=30)
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
async def queue(ctx: commands.Context) -> None:
    """Views the queue to see what songs are queued up"""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    tracks = []

    if not player:
        return
    
    # check if queue exists
    if player.queue:
        # add formatted tracks to tracks list
        for index, song in enumerate(player.queue):
            tracks.append(f"**{index+1}**. **[{song.title}]({song.uri})** - *{ms_convert(song.length)}*")

        # show queue menu for every 10 tracks
        qm = QueueMenu(tracks)
        await qm.start(ctx)
    elif not player.queue:
        await ctx.send("The queue is currently empty")
    else:
        await ctx.send("Something went wrong...")


# Move track to top in queue command
@bot.command()
async def top(ctx: commands.Context, index: int = 0):
    """
    Sets the requested song from queue to the top of the queue
    
    E.g: top(3) brings the third song in queue to the top
    """
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

    if type(index) != int:
        await ctx.send("Track index must be a number. e.g: 3")
        return
    
    if type(index) == int and index > 0:
        # inserts requested track at the top of the queue
        player.queue.put_at(0, player.queue[index-1])
        player.queue.delete(index)
        await ctx.send(f"Moved ***[{player.queue[0].title}]({player.queue[0].uri})*** to the top of the queue.")
    elif index <= 0:
        await ctx.send("Track index must be more than 0")


# Queue shuffle command
@bot.command()
async def shuffle(ctx: commands.Context):
    """Shuffles the queue to a randomized order"""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

    if not player:
        await ctx.send("I am not in a voice channel.")
        return
    
    if not player.queue:
        await ctx.send("The queue is empty.")
    else:
        player.queue.shuffle()
        await ctx.send("The queue has been shuffled.")


# Queue clear command
@bot.command()
async def clear(ctx: commands.Context):
    """Clear the queue of any tracks that was queued up"""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)

    if not player:
        await ctx.send("I am not in a voice channel.")

    if not player.queue:
        await ctx.send("The queue is empty.")
    else:
        player.queue.clear()
        await ctx.send("The queue has been cleared.")


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
@bot.command(aliases=["dc", "stop", "leave", "bye"])
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