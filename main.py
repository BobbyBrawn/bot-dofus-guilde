import discord
from discord.ext import commands, tasks
import os
import json
import requests
import asyncio
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_LISTE_DEMANDES = 1488953545930702938
ID_SALON_CONFIG = 1488847369322745917
ID_SALON_NOTIFICATIONS = 1489022043839140010
ID_VOCAL_CREATOR = 1488847294244716544

ROLE_ALMANAX = 1489021032965738636
ROLE_ENTRAIDE = 1489021136011530282
ROLE_ANNONCES = 1489021205011890410

MY_USER_ID = 270182770163187712
PARIS_TZ = timezone(timedelta(hours=2))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- MÉMOIRE ---
def load_data():
    if not os.path.exists("data.json"):
        with open("data.json", "w") as f: json.dump({"points": {}, "notif_msg_id": 0, "active_missions": {}}, f)
    with open("data.json", "r") as f: return json.load(f)

def save_data(data):
    with open("data.json", "w") as f: json.dump(data, f, indent=4)

# --- VOCAUX TEMPORAIRES ---
temp_vocal_channels = []

@bot.event
async def on_voice_state_update(member, before, after):
    # Création du salon
    if after.channel and after.channel.id == ID_VOCAL_CREATOR:
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await member.guild.create_voice_channel(name=f"🔊 {member.display_name}", category=category)
        await member.move_to(new_chan)
        temp_vocal_channels.append(new_chan.id)
    
    # Suppression si vide
    if before.channel and before.channel.id in temp_vocal_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            temp_vocal_channels.remove(before.channel.id)

# --- RÉACTIONS NOTIFICATIONS ---
@bot.event
async def on_raw_reaction_add(payload):
    data = load_data()
    if payload.message_id != data.get("notif_msg_id") or payload.user_id == bot.user.id: return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role_id = { "📅": ROLE_ALMANAX, "⚔️": ROLE_ENTRAIDE, "📢": ROLE_ANNONCES }.get(str(payload.emoji))
    if role_id: await member.add_roles(guild.get_role(role_id))

@bot.event
async def on_raw_reaction_remove(payload):
    data = load_data()
    if payload.message_id != data.get("notif_msg_id"): return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role_id = { "📅": ROLE_ALMANAX, "⚔️": ROLE_ENTRAIDE, "📢": ROLE_ANNONCES }.get(str(payload.emoji))
    if role_id: await member.remove_roles(guild.get_role(role_id))

# --- ENTRAIDE & MISSIONS ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id
    @discord.ui.button(label="Je suis dispo pour aider !", style=discord.ButtonStyle.success, custom_id="join_v68")
    async def join(self, interaction, button):
        thread = bot.get_channel(self.thread_id)
        if thread:
            await thread.add_user(interaction.user)
            await thread.send(f"⚔️ {interaction.user.mention} rejoint l'escouade !")
        await interaction.response.defer()

class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Cible", placeholder=placeholder, style=discord.TextStyle.paragraph)
        self.add_item(self.goal)

    async def on_submit(self, interaction):
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        thread = await list_chan.create_thread(name=f"Mission-{interaction.user.display_name}", type=discord.ChannelType.public_thread)
        
        await asyncio.sleep(1)
        async for message in list_chan.history(limit=5):
            if message.type == discord.MessageType.thread_created:
                await message.delete()
                break

        announcement = await list_chan.send(
            content=f"{role.mention if role else ''}\n📋 **MISSION : {self.category}**\n**Demandeur** : {interaction.user.display_name}\n**Objectif** : {self.goal.value}",
            view=MissionView(thread.id)
        )
        
        data = load_data()
        data["active_missions"][str(thread.id)] = announcement.id
        save_data(data)
        
        view_f = discord.ui.View(timeout=None)
        btn_f = discord.ui.Button(label="Mission terminée !", style=discord.ButtonStyle.danger)
        async def fini_cb(i):
            if i.user.id == interaction.user.id:
                data = load_data()
                data["points"][str(i.user.id)] = data["points"].get(str(i.user.id), 0) + 1
                msg_id = data["active_missions"].get(str(thread.id))
                if msg_id:
                    try:
                        m = await list_chan.fetch_message(msg_id)
                        await m.delete()
                    except: pass
                    del data["active_missions"][str(thread.id)]
                save_data(data)
                await thread.delete()
        btn_f.callback = fini_cb
        view_f.add_item(btn_f)
        await thread.send(f"🛡️ {interaction.user.mention}, clique ici quand c'est fini :", view=view_f)
        await interaction.response.defer()

# --- VIEWS PERSISTANTES ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, custom_id="sav_v68")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"Coucou {i.user.mention}, explique moi ton problème ici, met un max d'infos, des screens si possible, et <@{MY_USER_ID}> se penchera dessus au plus vite !")
        await i.response.defer()

class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="c_s")
    async def s(self, i, b): await i.response.send_modal(GoalModal("Succès", "Ex: Koutoulou Hardi"))
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="c_q")
    async def q(self, i, b): await i.response.send_modal(GoalModal("Quête", "Ex: Combat final Bolgrot"))
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.primary, custom_id="c_c")
    async def c(self, i, b): await i.response.send_modal(GoalModal("Craft/FM", "Ex: Craft Voile d'Encre / FM dague Erhy"))
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.secondary, custom_id="c_f")
    async def f(self, i, b): await i.response.send_modal(GoalModal("Farming", "Ex: Donjon Korriandre en boucle"))

@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    await bot.get_channel(ID_SALON_SAV).purge(limit=5)
    await bot.get_channel(ID_SALON_SAV).send("👋 **Besoin d'aide ?**\nOuvre un ticket ici.", view=SAVView())
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).purge(limit=5)
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).send("🤝 **Entraide de Guilde**", view=CoopView())
    notif_chan = bot.get_channel(ID_SALON_NOTIFICATIONS)
    await notif_chan.purge(limit=10)
    msg = await notif_chan.send("🔔 **Notifications**\n📅 : **Almanax**\n⚔️ : **Entraide**\n📢 : **Annonces**")
    for emoji in ["📅", "⚔️", "📢"]: await msg.add_reaction(emoji)
    data = load_data(); data["notif_msg_id"] = msg.id; save_data(data)
    await ctx.send("✅ Config rafraîchie.")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher v6.8 opérationnel"); bot.add_view(SAVView()); bot.add_view(CoopView())

bot.run(os.environ.get('DISCORD_TOKEN'))
