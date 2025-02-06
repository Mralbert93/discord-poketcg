import discord
from discord.ui import Button, View

page_states = {}

async def update_embed(ctx, user_doc, cards_list, current_page):
    cards_per_page = 15
    total_pages = (len(cards_list) + cards_per_page - 1) // cards_per_page
    page_cards = cards_list[current_page * cards_per_page:(current_page + 1) * cards_per_page]

    embed = discord.Embed(title=f"Your Cards (Page {current_page + 1}/{total_pages-1})")
    for card_name, card_id, set_name, rarity, count, card_image in page_cards:
        embed.add_field(name=f"**{card_name}**", value=f"ID: {card_id}\nSet: {set_name}\nRarity: {rarity}\nCount: {count}\n[View]({card_image})", inline=True)

    return embed

def create_pagination_buttons():
    prev_button = Button(style=discord.ButtonStyle.primary, label="Previous", custom_id="prev_card")
    next_button = Button(style=discord.ButtonStyle.primary, label="Next", custom_id="next_card")
    return prev_button, next_button

async def button_callback(interaction, ctx, user_doc, cards_list, view):
    user_id = str(interaction.user.id)

    current_page = page_states.get(user_id, 0)

    if interaction.user.id != ctx.author.id:
        return await interaction.response.send_message("This is not your card collection!", ephemeral=True)

    if interaction.custom_id == "prev_card" and current_page > 0:
        current_page -= 1
    elif interaction.custom_id == "next_card" and current_page < (len(cards_list) // 18):
        current_page += 1

    page_states[user_id] = current_page

    embed = await update_embed(ctx, user_doc, cards_list, current_page)

    await interaction.response.edit_message(embed=embed, view=view)

async def handle_cards(ctx, bot, all_cards, all_sets, users_col):
    user_id = str(ctx.author.id)
    user_doc = users_col.find_one({"user_id": user_id})

    if not user_doc or not user_doc.get('collected_cards'):
        embed = discord.Embed(
            title="🚨 **You need to begin first!**",
            description=f"\u200b\nUse `/begin` to start playing.\n\n{ctx.author.mention}",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        return await ctx.respond(embeds=[embed])

    collected_cards = user_doc['collected_cards']
    cards_list = []

    for card_set, cards in collected_cards.items():
        set_name = next((s['name'] for s in all_sets if s['id'] == card_set), card_set)
        for card_id, count in cards.items():
            card = next((c for c in all_cards if c['id'] == card_id), None)
            if card:
                cards_list.append((card['name'], card_id, set_name, card['rarity'], count, card['image']))

    cards_list.sort(key=lambda x: x[0])

    page_states[user_id] = 0

    prev_button, next_button = create_pagination_buttons()

    view = View(timeout=None)
    view.add_item(prev_button)
    view.add_item(next_button)

    prev_button.callback = lambda interaction: button_callback(interaction, ctx, user_doc, cards_list, view)
    next_button.callback = lambda interaction: button_callback(interaction, ctx, user_doc, cards_list, view)

    embed = await update_embed(ctx, user_doc, cards_list, page_states[user_id])

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)

    await ctx.respond(embed=embed, view=view)
