# sets_pagination.py
import discord
from discord.ui import Button, View

# A global dictionary to store current page for each user
page_states = {}

# Function to update the embed with the current set information
async def update_embed(ctx, user_doc, sorted_sets, current_page):
    collected_cards = user_doc['collected_cards']
    set_data = sorted_sets[current_page]
    set_id = set_data['id']
    set_name = set_data['name']
    set_image = set_data['image']
    total_cards_in_set = set_data.get('total_cards', 0)
    cards_collected_in_set = sum(collected_cards.get(set_id, {}).values())

    set_info = f"**{set_name}:**\n{cards_collected_in_set}/{total_cards_in_set} card{'s' if cards_collected_in_set != 1 else ''}\n"

    embed = discord.Embed(
        title="Your Set Progress",
        description=f"{set_info}\n{ctx.author.mention}",
        color=0x3498db
    )
    embed.set_thumbnail(url=set_image)
    embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)

    return embed

# Function to create buttons for pagination
def create_pagination_buttons():
    prev_button = Button(style=discord.ButtonStyle.secondary, label="Previous", custom_id="prev_set")
    next_button = Button(style=discord.ButtonStyle.secondary, label="Next", custom_id="next_set")
    return prev_button, next_button

# Callback function to handle pagination button clicks
async def button_callback(interaction, ctx, user_doc, sorted_sets, view):
    user_id = str(interaction.user.id)
    
    # Retrieve current page from global page state
    current_page = page_states.get(user_id, 0)

    if interaction.user.id != ctx.author.id:
        return await interaction.response.send_message("This is not your set progress!", ephemeral=True)

    if interaction.custom_id == "prev_set" and current_page > 0:
        current_page -= 1
    elif interaction.custom_id == "next_set" and current_page < len(sorted_sets) - 1:
        current_page += 1

    # Update the page state for the user
    page_states[user_id] = current_page

    # Generate the new embed with the updated page
    embed = await update_embed(ctx, user_doc, sorted_sets, current_page)

    # Update the message with the new embed
    await interaction.response.edit_message(embed=embed, view=view)

# Main function to handle sets command and pagination
async def handle_sets(ctx, bot, all_sets, users_col):
    user_id = str(ctx.author.id)
    user_doc = users_col.find_one({"user_id": user_id})

    if not user_doc or not user_doc.get('collected_cards'):
        embed = discord.Embed(
            title="🚨 **No Cards Collected Yet!**",
            description=f"\u200b\nYou haven't collected any cards yet.\nOpen some booster packs first!\n\nUse `/open` to open a pack.\n\n{ctx.author.mention}",
            color=0xe74c3c
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        return await ctx.respond(embeds=[embed])

    collected_cards = user_doc['collected_cards']
    sorted_sets = sorted(all_sets, key=lambda s: s['name'])
    
    # Set initial page state for the user
    page_states[user_id] = 0

    # Create buttons
    prev_button, next_button = create_pagination_buttons()

    # Create a view and add buttons
    view = View(timeout=None)
    view.add_item(prev_button)
    view.add_item(next_button)

    prev_button.callback = lambda interaction: button_callback(interaction, ctx, user_doc, sorted_sets, view)
    next_button.callback = lambda interaction: button_callback(interaction, ctx, user_doc, sorted_sets, view)

    # Send initial embed
    embed = await update_embed(ctx, user_doc, sorted_sets, page_states[user_id])
    await ctx.respond(embed=embed, view=view)
