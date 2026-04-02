import discord
from discord.ext import commands, tasks
import os
import json
import requests
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION (Tes IDs) ---
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
        with open("data.json", "w") as f: json.dump({"points": {}, "notif_msg_id": 0}, f)
    with open("data.json", "r") as f: return json.load(f)

def save_data(data):
    with open("data.json", "w") as f: json.dump(data, f, indent=4)

# --- ALMANAX ---
async def post_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel: return
    url = f"https://api.dofusdu.de/dofus2/fr/almanax/{datetime.now(PARIS_TZ).strftime('%Y-%m-%d')}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json()
            embed = discord.Embed(title=f"📅 ALMANAX : {d['boss']['name'].upper()}", color=0xE67E22)
            embed.set_thumbnail(url=d['tribute']['item']['image_urls']['icon'])
            embed.add_field(name="✨ Bonus", value=d['bonus']['description'], inline=False)
            embed.add_field(name="🙏 Offrande", value=f"**{d['tribute']['quantity']}x {d['tribute']['item']['name']}**", inline=False)
            role = channel.guild.get_role(ROLE_ALMANAX)
            await channel.send(content=f"{role.mention if role else ''}", embed=embed)
    except: pass

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop(): await post_almanax()

# --- VOCAUX ---
temp_vocal_channels = []
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == ID_VOCAL_CREATOR:
        cat = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await member.guild.create_voice_channel(name=f"🔊 {member.display_name}", category=cat)
        await member.move_to(new_chan)
        temp_vocal_channels.append(new_chan.id)
    if before.channel and before.channel.id in temp_vocal_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            temp_vocal_channels.remove(before.channel.id)

# --- RÉACTIONS NOTIFICATIONS ---
@bot.event
async def on_raw_reaction_add(payload):
    data = load_data()
    if payload.message_id != data.get("notif_msg_id"): return
    if payload.user_id == bot.user.id: return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    
    role_id = 0
    if str(payload.emoji) == "📅": role_id = ROLE_ALMANAX
    elif str(payload.emoji) == "⚔️": role_id = ROLE_ENTRAIDE
    elif str(payload.emoji) == "📢": role_id = ROLE_ANNONCES
    
    if role_id:
        role = guild.get_role(role_id)
        await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    data = load_data()
    if payload.message_id != data.get("notif_msg_id"): return
    
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    
    role_id = 0
    if str(payload.emoji) == "📅": role_id = ROLE_ALMANAX
    elif str(payload.emoji) == "⚔️": role_id = ROLE_ENTRAIDE
    elif str(payload.emoji) == "📢": role_id = ROLE_ANNONCES
    
    if role_id:
        role = guild.get_role(role_id)
        await member.remove_roles(role)

# --- MISSIONS & ENTRAIDE ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id
    @discord.ui.button(label="Je suis dispo pour aider !", style=discord.ButtonStyle.success, custom_id="join_m")
    async def join(self, interaction, button):
        thread = bot.get_channel(self.thread_id)
        if thread:
            await thread.add_user(interaction.user)
            await thread.send(f"⚔️ {interaction.user.mention} rejoint l'escouade !")
            await interaction.response.send_message("Ajouté au fil !", ephemeral=True)

class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Cible", placeholder=placeholder, style=discord.TextStyle.paragraph)
        self.add_item(self.goal)

    async def on_submit(self, interaction):
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        msg = await list_chan.send(f"{role.mention if role else ''}\n📋 **MISSION : {self.category}**\n**Demandeur** : {interaction.user.display_name}\n**Objectif** : {self.goal.value}")
        thread = await msg.create_thread(name=f"Mission-{interaction.user.display_name}", auto_archive_duration=60)
        await msg.edit(view=MissionView(thread.id))
        
        view_f = discord.ui.View(timeout=None)
        btn_f = discord.ui.Button(label="Mission terminée !", style=discord.ButtonStyle.danger)
        async def fini_cb(i):
            if i.user.id != interaction.user.id:
                return await i.response.send_message("Seul le demandeur peut clore.", ephemeral=True)
            data = load_data()
            data["points"][str(i.user.id)] = data["points"].get(str(i.user.id), 0) + 1
            save_data(data)
            await i.response.send_message("Mission validée !", ephemeral=True)
            await msg.delete()
            await thread.delete()
        btn_f.callback = fini_cb
        view_f.add_item(btn_f)
        await thread.send(f"🛡️ Mission lancée ! {interaction.user.mention}, clique ici quand c'est fini :", view=view_f)
        await interaction.response.send_message("Demande publiée !", ephemeral=True)

# --- VIEWS PERSISTANTES ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, custom_id="sav_open")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"🛡️ <@{MY_USER_ID}>, ticket de {i.user.mention}. Il répondra au plus vite.")
        await i.response.send_message(f"Fil ouvert : {t.mention}", ephemeral=True)

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

# --- COMMANDES ---
@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    
    # 1. SAV
    sav_chan = bot.get_channel(ID_SALON_SAV)
    await sav_chan.purge(limit=5)
    await sav_chan.send("👋 **Besoin d'aide ?**\nOuvre un ticket ici pour discuter avec les officiers.", view=SAVView())

    # 2. ENTRAIDE
    aide_chan = bot.get_channel(ID_SALON_DEMANDE_AIDE)
    await aide_chan.purge(limit=5)
    await aide_chan.send("🤝 **Entraide de Guilde**\nClique sur un bouton pour lancer une demande.", view=CoopView())

    # 3. NOTIFICATIONS (Réactions)
    notif_chan = bot.get_channel(ID_SALON_NOTIFICATIONS)
    await notif_chan.purge(limit=10)
    msg = await notif_chan.send(
        "🔔 **Notifications de la Guilde**\nClique sur les icônes sous ce message pour recevoir les notifications associées :\n\n"
        "📅 : **Almanax** (Offrandes et bonus du jour)\n"
        "⚔️ : **Entraide** (Alertes pour les missions Succès, Quêtes, etc.)\n"
        "📢 : **Annonces** (Informations importantes de la guilde)\n\n"
        "> *Pour ne plus recevoir une notification, retire simplement ta réaction.*"
    )
    # Ajouter les réactions automatiquement
    for emoji in ["📅", "⚔️", "📢"]:
        await msg.add_reaction(emoji)
    
    # Sauver l'ID du message pour les réactions
    data = load_data()
    data["notif_msg_id"] = msg.id
    save_data(data)

    await ctx.send("✅ Toutes les interfaces ont été réinitialisées.")

@bot.command()
async def force_almanax(ctx):
    if ctx.author.id == MY_USER_ID:
        await post_almanax()
        await ctx.send("⚙️ Almanax forcé.")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights v6.0 opérationnel")
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    if not almanax_loop.is_running(): almanax_loop.start()

bot.run(os.environ.get('DISCORD_TOKEN'))
