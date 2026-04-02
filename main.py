import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import requests
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION (Tes IDs) ---
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_LISTE_DEMANDES = 1488953545930702938
ID_SALON_LOGS = 1489021869133791273
ID_SALON_NOTIFICATIONS = 1489022043839140010
ID_SALON_ANNONCES = 1488953370667647076 
ID_SALON_CONFIG = 1488847369322745917

ROLE_ALMANAX = 1489021032965738636
ROLE_ENTRAIDE = 1489021136011530282
ROLE_ANNONCES = 1489021205011890410

MY_USER_ID = 270182770163187712 # @bobbybrawn
PARIS_TZ = timezone(timedelta(hours=2))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- MÉMOIRE ---
def load_data():
    if not os.path.exists("data.json"):
        with open("data.json", "w") as f:
            json.dump({"points": {}, "messages": {}, "last_almanax": ""}, f)
        return {"points": {}, "messages": {}, "last_almanax": ""}
    with open("data.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)

# --- ALMANAX ---
def fetch_almanax_api():
    today = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    url = f"https://api.dofusdu.de/dofus2/fr/almanax/{today}"
    try:
        r = requests.get(url, timeout=10)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"Erreur API DofusDude : {e}")
        return None

async def post_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel:
        print("❌ Salon Almanax introuvable.")
        return
    
    data = load_data()
    today = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    
    if data.get("last_almanax") != today:
        api_data = fetch_almanax_api()
        if not api_data: return

        role = channel.guild.get_role(ROLE_ALMANAX)
        embed = discord.Embed(
            title=f"📅 ALMANAX : {api_data['boss']['name'].upper()}", 
            description=f"**L'effet Méryde**\n{api_data['boss']['description']}",
            color=0xE67E22
        )
        embed.set_thumbnail(url=api_data['tribute']['item']['image_urls']['icon'])
        embed.add_field(name="✨ Bonus", value=api_data['bonus']['description'], inline=False)
        embed.add_field(name="🙏 Offrande", value=f"Récupérer **{api_data['tribute']['quantity']}x {api_data['tribute']['item']['name']}**", inline=False)
        
        await channel.send(content=f"{role.mention if role else ''}", embed=embed)
        data["last_almanax"] = today
        save_data(data)

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop():
    await post_almanax()

# --- VIEWS PERSISTANTES ---
class NotifView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Almanax", style=discord.ButtonStyle.grey, emoji="📅", custom_id="notif_almanax")
    async def b1(self, i, b): await self.toggle_role(i, ROLE_ALMANAX)
    @discord.ui.button(label="Entraide", style=discord.ButtonStyle.grey, emoji="⚔️", custom_id="notif_entraide")
    async def b2(self, i, b): await self.toggle_role(i, ROLE_ENTRAIDE)
    @discord.ui.button(label="Annonces", style=discord.ButtonStyle.grey, emoji="📢", custom_id="notif_annonces")
    async def b3(self, i, b): await self.toggle_role(i, ROLE_ANNONCES)

    async def toggle_role(self, interaction, role_id):
        role = interaction.guild.get_role(role_id)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Retiré.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Ajouté.", ephemeral=True)

class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, emoji="🎫", custom_id="open_sav")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"🛡️ <@{MY_USER_ID}>, un nouveau ticket a été ouvert par {i.user.mention}. Il te répondra au plus vite !")
        await i.response.send_message(f"Ticket ouvert ici : {t.mention}", ephemeral=True)

class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="btn_succes")
    async def s(self, i, b): await i.response.send_modal(GoalModal("Succès"))
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="btn_quete")
    async def q(self, i, b): await i.response.send_modal(GoalModal("Quête"))
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.primary, custom_id="btn_craft")
    async def c(self, i, b): await i.response.send_modal(GoalModal("Craft/FM"))
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.secondary, custom_id="btn_farm")
    async def f(self, i, b): await i.response.send_modal(GoalModal("Farming"))

class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id
    @discord.ui.button(label="Dispo pour aider", style=discord.ButtonStyle.success, custom_id="join_mission")
    async def callback(self, i, b):
        t = bot.get_channel(self.thread_id)
        if t:
            await t.add_user(i.user)
            await t.send(f"⚔️ {i.user.mention} rejoint l'escouade !")
            await i.response.send_message("Ajouté !", ephemeral=True)

class GoalModal(discord.ui.Modal):
    def __init__(self, category):
        super().__init__(title=f"Demande : {category}")
        self.goal = discord.ui.TextInput(label="Cible / Détails", placeholder="Ex: Koutoulou Hardi", required=True)
        self.add_item(self.goal)

    async def on_submit(self, interaction: discord.Interaction):
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        msg = await list_chan.send(f"{role.mention if role else ''}\n📋 **MISSION : {self.title}**\n**Cible** : {self.goal.value}\n**Demandeur** : {interaction.user.mention}")
        thread = await list_chan.create_thread(name=f"Mission-{interaction.user.display_name}", type=discord.ChannelType.private_thread)
        await msg.edit(view=MissionView(thread.id))
        
        btn_f = discord.ui.Button(label="Mission terminée !", style=discord.ButtonStyle.success)
        async def fini_cb(i):
            data = load_data()
            uid = str(interaction.user.id)
            data["points"][uid] = data["points"].get(uid, 0) + 1
            save_data(data)
            await i.response.send_message("Validé ! +1 point.", ephemeral=True)
            await msg.delete()
            await thread.delete()

        view_f = discord.ui.View(timeout=None).add_item(btn_f)
        btn_f.callback = fini_cb
        await thread.send(f"🛡️ Mission lancée ! {interaction.user.mention}, clique sur terminé une fois fini.", view=view_f)
        await interaction.response.send_message("Mission publiée !", ephemeral=True)

# --- COMMANDES ---
@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    data = load_data()
    
    # Update SAV
    chan_sav = bot.get_channel(ID_SALON_SAV)
    await chan_sav.purge(limit=5)
    msg_sav = await chan_sav.send("👋 **Besoin d'aide ?**\nOuvre un ticket ici pour discuter avec les officiers.", view=SAVView())
    data["messages"]["sav"] = msg_sav.id

    # Update Aide
    chan_aide = bot.get_channel(ID_SALON_DEMANDE_AIDE)
    await chan_aide.purge(limit=5)
    msg_aide = await chan_aide.send("🤝 **Entraide de Guilde**\nClique sur un bouton pour lancer une demande.", view=CoopView())
    data["messages"]["aide"] = msg_aide.id

    # Update Notifs
    chan_notif = bot.get_channel(ID_SALON_NOTIFICATIONS)
    await chan_notif.purge(limit=5)
    msg_notif = await chan_notif.send("🔔 **Notifications**\nChoisis tes alertes :", view=NotifView())
    data["messages"]["notifs"] = msg_notif.id

    save_data(data)
    await ctx.send("✅ Interface mise à jour.", delete_after=3)

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights v4.3 opérationnel !")
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(NotifView())
    if not almanax_loop.is_running(): almanax_loop.start()
    await post_almanax()

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
