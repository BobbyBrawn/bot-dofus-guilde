import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
from datetime import datetime, timezone

# --- CONFIGURATION ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_LISTE_DEMANDES = 1488953545930702938
ID_SALON_CONFIG = 1488847369322745917
ID_SALON_NOTIFICATIONS = 1489022043839140010
ID_VOCAL_CREATOR = 1488847294244716544
ID_SALON_GESTION_VOCAL = 1488847333671211048

ROLE_ALMANAX = 1489021032965738636
ROLE_ENTRAIDE = 1489021136011530282
ROLE_ANNONCES = 1489021205011890410

MY_USER_ID = 270182770163187712

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- MÉMOIRE ---
def load_data():
    if not os.path.exists("data.json"):
        with open("data.json", "w") as f: json.dump({"points": {}, "notif_msg_id": 0, "active_missions": {}}, f)
    with open("data.json", "r") as f: return json.load(f)

def save_data(data):
    with open("data.json", "w") as f: json.dump(data, f, indent=4)

# --- GESTION VOCAL ---
temp_vocal_channels = {}

class VoiceControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="Modifier le Nom", style=discord.ButtonStyle.primary, custom_id="v_rename")
    async def rename(self, interaction, button):
        if interaction.user.voice and interaction.user.voice.channel.id in temp_vocal_channels:
            modal = discord.ui.Modal(title="Nouveau nom du salon")
            name_input = discord.ui.TextInput(label="Nom", placeholder="Mon super salon")
            modal.add_item(name_input)
            async def on_submit(i):
                await interaction.user.voice.channel.edit(name=f"🔊 {name_input.value}")
                await i.response.send_message("Nom modifié !", ephemeral=True)
            modal.on_submit = on_submit
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Tu dois être dans ton salon vocal !", ephemeral=True)

    @discord.ui.button(label="Limite Place", style=discord.ButtonStyle.secondary, custom_id="v_limit")
    async def limit(self, interaction, button):
        if interaction.user.voice and interaction.user.voice.channel.id in temp_vocal_channels:
            modal = discord.ui.Modal(title="Limite de places")
            limit_input = discord.ui.TextInput(label="Nombre (0 pour illimité)", placeholder="5")
            modal.add_item(limit_input)
            async def on_submit(i):
                try:
                    await interaction.user.voice.channel.edit(user_limit=int(limit_input.value))
                    await i.response.send_message(f"Limite fixée à {limit_input.value} !", ephemeral=True)
                except: await i.response.send_message("Mets un chiffre valide.", ephemeral=True)
            modal.on_submit = on_submit
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Tu dois être dans ton salon vocal !", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == ID_VOCAL_CREATOR:
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await member.guild.create_voice_channel(name=f"🔊 {member.display_name}", category=category)
        await member.move_to(new_chan)
        temp_vocal_channels[new_chan.id] = member.id
    if before.channel and before.channel.id in temp_vocal_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            del temp_vocal_channels[before.channel.id]

# --- ENTRAIDE ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id
    @discord.ui.button(label="Je suis dispo !", style=discord.ButtonStyle.success, custom_id="join_v7")
    async def join(self, interaction, button):
        thread = bot.get_channel(self.thread_id)
        if thread:
            await thread.add_user(interaction.user)
            await thread.send(f"⚔️ {interaction.user.mention} est en route !")
        await interaction.response.defer()

class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Objectif", placeholder=placeholder, style=discord.TextStyle.paragraph)
        self.add_item(self.goal)

    async def on_submit(self, interaction):
        await interaction.response.defer() # Évite l'erreur "Une erreur s'est produite"
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        
        # On crée le message d'annonce d'abord
        announcement = await list_chan.send(f"{role.mention if role else ''}\n📋 **MISSION : {self.category}**\n**Par** : {interaction.user.display_name}\n**Cible** : {self.goal.value}")
        
        # On crée le fil SUR le message pour qu'il s'ouvre tout de suite
        thread = await announcement.create_thread(name=f"Mission-{interaction.user.display_name}", auto_archive_duration=60)
        
        # Nettoyage du message système "a créé un fil"
        async for message in list_chan.history(limit=5):
            if message.type == discord.MessageType.thread_created:
                await message.delete()
                break

        # On ajoute le bouton au message
        await announcement.edit(view=MissionView(thread.id))
        
        data = load_data()
        data["active_missions"][str(thread.id)] = announcement.id
        save_data(data)
        
        # Bouton fin dans le fil
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
                save_data(data)
                await thread.delete()
        btn_f.callback = fini_cb
        view_f.add_item(btn_f)
        await thread.send(f"🛡️ {interaction.user.mention}, clique ici quand c'est fini :", view=view_f)

# --- VIEWS GÉNÉRALES ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, custom_id="sav_v7")
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
    async def c(self, i, b): await i.response.send_modal(GoalModal("Craft/FM", "Ex: Craft Voile d'Encre"))
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.secondary, custom_id="c_f")
    async def f(self, i, b): await i.response.send_modal(GoalModal("Farming", "Ex: Donjon Korriandre"))

@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    # SAV
    await bot.get_channel(ID_SALON_SAV).purge(limit=5)
    await bot.get_channel(ID_SALON_SAV).send("👋 **Besoin d'aide ?**", view=SAVView())
    # ENTRAIDE
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).purge(limit=5)
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).send("🤝 **Entraide**", view=CoopView())
    # VOCAL
    await bot.get_channel(ID_SALON_GESTION_VOCAL).purge(limit=5)
    await bot.get_channel(ID_SALON_GESTION_VOCAL).send("⚙️ **Gestion de ton salon**", view=VoiceControlView())
    # NOTIFS
    notif_chan = bot.get_channel(ID_SALON_NOTIFICATIONS)
    await notif_chan.purge(limit=5)
    msg = await notif_chan.send("🔔 **Notifications**\n📅 : Almanax\n⚔️ : Entraide\n📢 : Annonces")
    for e in ["📅", "⚔️", "📢"]: await msg.add_reaction(e)
    data = load_data(); data["notif_msg_id"] = msg.id; save_data(data)
    await ctx.send("✅ Config v7.0 OK.")

@bot.event
async def on_ready():
    print("🛡️ Watcher v7.0 Ready")
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(VoiceControlView())

bot.run(os.environ.get('DISCORD_TOKEN'))
