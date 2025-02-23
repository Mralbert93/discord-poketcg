import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
import os
from pymongo.mongo_client import MongoClient
import random
import uuid
from cards_pagination import handle_cards
from sets_pagination import handle_sets

load_dotenv()

mongo_uri = os.getenv("MONGO_URI")
discord_token = os.environ.get("DISCORD_TOKEN")

mongo = MongoClient(mongo_uri)
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

db = mongo['pokemon_tcg']
cards_col = db['cards']
sets_col = db['sets']
users_col = db['users']

all_cards = []
all_sets = []
user_states = {}
page_states = {}

rarity_probabilities = {
    "Common": 0.70,
    "Uncommon": 0.20,
    "Rare": 0.08,
    "Rare Holo": 0.015,
    "Rare Secret": 0.005
}

def get_cards_by_rarity(rarity):
    return [card for card in all_cards if card.get('rarity') == rarity]

def roll_rarity():
    roll = random.random()
    if roll < rarity_probabilities["Common"]:
        return "Common"
    elif roll < rarity_probabilities["Common"] + rarity_probabilities["Uncommon"]:
        return "Uncommon"
    elif roll < rarity_probabilities["Common"] + rarity_probabilities["Uncommon"] + rarity_probabilities["Rare"]:
        return "Rare"
    elif roll < rarity_probabilities["Common"] + rarity_probabilities["Uncommon"] + rarity_probabilities["Rare"] + rarity_probabilities["Rare Holo"]:
        return "Rare Holo"
    else:
        return "Rare Secret"

def select_booster_pack():
    booster_pack = []
    
    for _ in range(5): 
        rarity = roll_rarity()
        possible_cards = get_cards_by_rarity(rarity)
        card = random.choice(possible_cards) 
        booster_pack.append(card)

    return booster_pack

def get_card_collection_count(user_id, card_id, set_id):
    user_doc = users_col.find_one({"user_id": user_id})
    
    set_collection = user_doc.get('collected_cards', {}).get(set_id, {})
    return set_collection.get(card_id, 0)

@bot.slash_command(name="begin", description="Use this to begin playing")
async def begin(ctx):
    user_id = str(ctx.author.id)

    user_doc = users_col.find_one({"user_id": user_id})

    if not user_doc:
        user_doc = {
            "user_id": user_id,
            "packs_left": 5,
            "packs_opened": 0,
            "collected_cards": {} 
        }

        users_col.insert_one(user_doc)

        embed = discord.Embed(
            title="🎉 **Welcome to the game!**",
            description=f"\u200b\nYou've been given **5 booster packs** to open.\nUse `/open` to open a booster pack!\n\n{ctx.author.mention}",
            color=0x3498db 
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        await ctx.respond(
            embeds=[embed]  
        )
    else:
        embed = discord.Embed(
            title="🚨 **You've already begun!**",
            description=f"\u200b\nUse `/open` to start opening booster packs.\n\n{ctx.author.mention}",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        await ctx.respond(embeds=[embed])

@bot.slash_command(name="sets", description="Use this to show your card progress for sets")
async def sets(ctx):
    await handle_sets(ctx, bot, all_sets, users_col)

@bot.slash_command(name="cards", description="Use this to show all your cards")
async def cards(ctx):
    await handle_cards(ctx, bot, all_cards, all_sets, users_col, bot.user.display_avatar.url)

@bot.slash_command(name="open", description="Use this to open a booster pack")
async def open(ctx):
    booster_pack = select_booster_pack()

    user_id = str(ctx.author.id)
    interaction_guid = str(uuid.uuid4())

    user_doc = users_col.find_one({"user_id": user_id})

    if not user_doc:
        embed = discord.Embed(
            title="🚨 **You need to begin first!**",
            description=f"\u200b\nUse `/begin` to start playing.\n\n{ctx.author.mention}",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        return await ctx.respond(embeds=[embed])

    packs_left = user_doc.get("packs_left", 0)

    if packs_left <= 0:
        embed = discord.Embed(
            title="🚨 **You're out of packs!**",
            description=f"\u200b\nYou can gain one pack to open every 4 hours.\nTry again later!\n\n{ctx.author.mention}\n\u200b",
            color=0xe74c3c
        )
        embed.set_footer(text="Note: You can only hold up to 5 packs at a time.")
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        return await ctx.respond(embeds=[embed])

    embed = discord.Embed(
        title="🎉 **You opened a booster pack!** 🎉",
        description=f"\u200b\nPress 'Next Card' to reveal your first card.\n\n{ctx.author.mention}",
        color=0x3498db 
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    next_button = Button(style=discord.ButtonStyle.secondary, label="Next Card", custom_id=f"next_card_{interaction_guid}")
    prev_button = Button(style=discord.ButtonStyle.secondary, label="Previous Card", custom_id=f"prev_card_{interaction_guid}", disabled=True)
    finish_button = Button(style=discord.ButtonStyle.success, label="Finish", custom_id=f"finish_{interaction_guid}", disabled=True)

    view = View(timeout=None)
    view.add_item(prev_button)
    view.add_item(next_button)

    await ctx.respond(
        embeds=[embed],
        view=view
    )


    user_states[interaction_guid] = {
        "cards": booster_pack,
        "current_index": 0
    }

    for card in booster_pack:
        card_id = card['id'] 
        set_id = card['set']

        if set_id not in user_doc['collected_cards']:
            user_doc['collected_cards'][set_id] = {}

        if card_id in user_doc['collected_cards'][set_id]:
            user_doc['collected_cards'][set_id][card_id] += 1
        else:
            user_doc['collected_cards'][set_id][card_id] = 1

    users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"packs_left": -1, "packs_opened": 1}},
    )

    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"collected_cards": user_doc['collected_cards']}}
    )

    async def button_callback(interaction):
        user_id = str(interaction.user.id)

        custom_id = interaction.custom_id
        interaction_guid = custom_id.split('_')[-1]

        user_state = user_states.get(interaction_guid, None)

        if not user_state:
            return await interaction.response.send_message("Sorry, this pull is no longer available.", ephemeral=True)

        cards = user_state["cards"]
        current_index = user_state["current_index"]

        if interaction.custom_id.startswith("next_card"):
            if current_index < len(cards):
                card = cards[current_index]
                
                card_id = card.get('id', 'Unknown Id')
                name = card.get('name', 'Unknown Card')
                rarity = card.get('rarity', 'Unknown Rarity')
                rarity_percent = round(rarity_probabilities[rarity] * 100, 2)
                card_image = card.get('image', 'https://via.placeholder.com/150')
                
                set_id = card.get('set', None)
                set_image = 'https://via.placeholder.com/150'
                if set_id:
                    set = next((s for s in all_sets if s['id'] == set_id), None)
                    if set:
                        set_name = set.get('name', 'Unknown Set')
                        set_image = set.get('image', 'https://via.placeholder.com/150')
                
                card_count = get_card_collection_count(user_id, card_id, set_id)-1
                if card_count > 0:
                    collection_info = f"**Times Collected:** {card_count+1}"
                else:
                    collection_info = f"**New Card!** {pika}{pika}{pika}"

                embed = discord.Embed(
                    title=f"Card {current_index+1}/{len(cards)}",
                    description=f"**Name:** {name}\n**Set:** {set_name}\n**Rarity:** {rarity} ({rarity_percent}%)\n\n{collection_info}\n\n{ctx.author.mention}",
                    color=0x3498db
                )
                embed.set_image(url=card_image)
                embed.set_thumbnail(url=set_image)
                embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
                
                prev_button.disabled = (current_index == 0)
                next_button.disabled = (current_index == len(cards) - 1)
                finish_button.disabled = (current_index != len(cards) - 1)

                view.clear_items()
                view.add_item(prev_button)
                if current_index == len(cards) - 1:
                    view.add_item(finish_button)  
                else:
                    view.add_item(next_button)  
                await interaction.response.edit_message(
                    embeds=[embed],
                    view=view
                )

                user_states[interaction_guid]["current_index"] = current_index + 1

        # Handle "Previous Card"
        elif interaction.custom_id.startswith("prev_card"):
            if current_index > 0:
                user_states[interaction_guid]["current_index"] = current_index - 1
                card = cards[current_index - 1]
                
                card_id = card.get('id', 'Unknown Id')
                name = card.get('name', 'Unknown Card')
                rarity = card.get('rarity', 'Unknown Rarity')
                rarity_percent = round(rarity_probabilities[rarity] * 100, 2)
                card_image = card.get('image', 'https://via.placeholder.com/150')
                
                set_id = card.get('set', None)
                set_image = 'https://via.placeholder.com/150'
                if set_id:
                    set = next((s for s in all_sets if s['id'] == set_id), None)
                    if set:
                        set_name = set.get('name', 'Unknown Set')
                        set_image = set.get('image', 'https://via.placeholder.com/150')
                
                card_count = get_card_collection_count(user_id, card_id, set_id)-1
                if card_count > 0:
                    collection_info = f"**Times Collected:** {card_count+1}"
                else:
                    collection_info = f"**New Card!** {pika}{pika}{pika}"

                embed = discord.Embed(
                    title=f"Card {current_index}/{len(cards)}",
                    description=f"**Name:** {name}\n**Set:** {set_name}\n**Rarity:** {rarity} ({rarity_percent}%)\n\n{collection_info}\n\n{ctx.author.mention}",
                    color=0x3498db
                )
                embed.set_image(url=card_image)
                embed.set_thumbnail(url=set_image)
                embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

                prev_button.disabled = (current_index == 1)
                next_button.disabled = (current_index == len(cards))

                view.clear_items()
                view.add_item(prev_button)
                if current_index == len(cards):
                    view.add_item(finish_button)
                else:
                    view.add_item(next_button) 
                await interaction.response.edit_message(
                    embeds=[embed],
                    view=view
                )

        elif interaction.custom_id.startswith("finish"):
            packs_left = user_doc['packs_left']-1
            if packs_left > 0:
                pack_info = f"You have **{packs_left} booster packs** left.\nYou can open another pack with `/open`."
            else:
                pack_info = f"You have **{packs_left} booster packs** left.\nPlease wait **4 hours**.\nThen, you can open another pack with `/open`." 

            final_embed = discord.Embed(
                title="🎉 **All cards pulled!** 🎉",
                description=f"{pack_info}\n\n{ctx.author.mention}",
                color=0x3498db
            )
            final_embed.set_thumbnail(url=ctx.author.display_avatar.url)

            view.clear_items()
            view.add_item(prev_button)
            if current_index == len(cards) - 1:
                view.add_item(finish_button)
            elif current_index != len(cards):
                view.add_item(next_button) 

            await interaction.response.edit_message(
                embeds=[final_embed],
                view=view
            )

    next_button.callback = button_callback
    prev_button.callback = button_callback
    finish_button.callback = button_callback

async def hourly_packs_loop():
    while True:
        for user_doc in users_col.find({"packs_left": {"$lt": 5}}):
            users_col.update_one(
                {"user_id": user_doc["user_id"]},
                {"$inc": {"packs_left": 1}}
            )
        embed = discord.Embed(
            title="🎁 **Packs Distributed!** 🎁",
            description=f"\u200b\nOne additional pack has been added for users with less than 5 packs. The next distribution will happen in approximately 4 hours.\n\u200b",
            color=0x3498db 
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        channel = bot.get_channel(1335401186429501525)
        await channel.send(embed=embed)
        await asyncio.sleep(14400)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    
    global all_sets
    global all_cards
    global pika

    all_sets = list(sets_col.find()) 
    print(f"Loaded {len(all_sets)} sets into memory.")
    
    all_cards = list(cards_col.find()) 
    print(f"Loaded {len(all_cards)} cards into memory.")

    guild = bot.get_guild(1094098329937379422)
    pika = discord.utils.get(guild.emojis, name="TCGPika")

    await hourly_packs_loop()

bot.run(discord_token)
