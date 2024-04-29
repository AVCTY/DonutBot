import discord
from discord.ext import menus

# Custom menu class
class QueueMenu(menus.Menu):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.current_page = 0
        self.per_page = 10

    async def send_initial_message(self, ctx, channel):
        return await channel.send(embed=self.get_embed())

    def get_embed(self):
        start_index = self.current_page * self.per_page
        end_index = (self.current_page + 1) * self.per_page
        page_data = self.data[start_index:end_index]

        embed = discord.Embed(title="DonutBot Queue", description="\n".join(page_data))
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.get_max_pages()}")
        return embed

    async def update_embed(self):
        await self.message.edit(embed=self.get_embed())

    def get_max_pages(self):
        return -(-len(self.data) // self.per_page)

    @menus.button('⬅️')
    async def on_previous(self, payload):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed()

    @menus.button('➡️')
    async def on_next(self, payload):
        if self.current_page < self.get_max_pages() - 1:
            self.current_page += 1
            await self.update_embed()

    @menus.button('❌')
    async def on_stop(self, payload):
        self.stop()
