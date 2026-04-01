import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_GESTION_VOCAL = 1488953466494652446
ID_SALON_LISTE_DEMANDES = 1488953545930702938
ID_SALON_CLASSEMENT = 1489021662212128999
ID_SALON_LOGS = 1489021869133791273
ID_SALON_NOTIFICATIONS = 1489022043839140010
ID_SALON_ANNONCES = 1488953370667647076 
ID_SALON_CONFIG = 1488847369322745917
ID_VOCAL_CREATOR = 1488847294244716544

ROLE_ALMANAX = 1489021032965738636
ROLE_ENTRAIDE = 1489021136011530282
ROLE_ANNONCES = 1489021205011890410

MY_USER_ID = 270182770163187712

# Décalage UTC+2 pour Paris (Heure d'été)
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

async def send_log(title, description, color=discord.Color.blue()):
    channel = bot.get_channel(ID_SALON_LOGS)
    if channel:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now(PARIS_TZ))
        await channel.send(embed=embed)

# --- ALMANAX ---
async def post_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if channel:
        data = load_data()
        today = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
        
        if data.get("last_almanax") != today:
            role = channel.guild.get_role(ROLE_ALMANAX)
            embed = discord.Embed(title="📅 Almanax du Jour", description=f"Meryde du {today}", color=discord.Color.gold())
            embed.add_field(name="Offrande", value="🔍 Consultez le grimoire en jeu !", inline=False)
            content = f"{role.mention}" if role else ""
            await channel.send(content=content, embed=embed)
            data["last_almanax"] = today
            save_data(data)
            await send_log("📅 Almanax", "Message quotidien posté.")

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop():
    await post_almanax()

# --- NOTIFICATIONS (Boutons) ---
class NotifView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    async def toggle_role(self, interaction, role_id):
        role = interaction.guild.get_role(role_id)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Notifs {role.name} retirées.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Notifs {role.name} activées !", ephemeral=True)

    @discord.ui.button(label="Almanax", style=discord.ButtonStyle.grey, emoji="📅", custom_id="notif_almanax")
    async def b1(self, i, b): await self.toggle_role(i, ROLE_ALMANAX)
    @discord.ui.button(label="Entraide", style=discord.ButtonStyle.grey, emoji="⚔️", custom_id="notif_entraide")
    async def b2(self, i, b): await self.toggle_role(i, ROLE_ENTRAIDE)
    @discord.ui.button(label="Annonces", style=discord.ButtonStyle.grey, emoji="📢", custom_id="notif_annonces")
    async def b3(self, i, b): await self.toggle_role(i, ROLE_ANNONCES)

# --- MISSIONS ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id

    @discord.ui.button(label="Dispo pour aider", style=discord.ButtonStyle.success, custom_id="dispo_btn")
    async def callback(self, i, b):
        t = bot.get_channel(self.thread_id)
        if t:
            await t.add_user(i.user)
            await t.send(f"⚔️ {i.user.mention} rejoint l'escouade !")
            await i.response.send_message("Ajouté au fil !", ephemeral=True)

class GoalModal(discord.ui.Modal):
    def __init__(self, category):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Cible", placeholder="Ex: Koutoulou Hardi", required=True)
        self.add_item(self.goal)

    async def on_submit(self, interaction: discord.Interaction):
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        msg = await list_chan.send(f"{role.mention if role else ''}\n📋 **MISSION : {self.goal.value}**\n**Demandeur** : {interaction.user.display_name}")
        thread = await list_chan.create_thread(name=f"Mission-{self.goal.value}", type=discord.ChannelType.private_thread)
        await msg.edit(view=MissionView(thread.id))
        
        view_f = discord.ui.View(timeout=None)
        btn_f = discord.ui.Button(label="Fini !", style=discord.ButtonStyle.success)
        
        async def fini_cb(i):
            duration = datetime.now(timezone.utc) - thread.created_at
            if duration.total_seconds() < 300:
                await i.response.send_message("Trop rapide pour les points (min 5min).", ephemeral=True)
            else:
                data = load_data()
                uid = str(interaction.user.id)
                data["points"][uid] = data["points"].get(uid, 0) + 1
                save_data(data)
                await i.response.send_message("Mission validée ! +1 point.", ephemeral=True)
            await msg.delete()
            await thread.delete()

        btn_f.callback = fini_cb
        view_f.add_item(btn_f)
        await thread.send(f"🛡️ Mission lancée ! {interaction.user.mention}, clique sur Fini une fois terminé.", view=view_f)
        await thread.add_user(interaction.user)
        await interaction.response.send_message("Publié !", ephemeral=True)

# --- COMMANDES ---
@bot.command()
async def annonce(ctx, *, message):
    if ctx.channel.id != ID_SALON_CONFIG: return
    await ctx.message.delete()
    chan = bot.get_channel(ID_SALON_ANNONCES)
    role = ctx.guild.get_role(ROLE_ANNONCES)
    embed = discord.Embed(title="📢 ANNONCE", description=message, color=discord.Color.blue())
    await chan.send(content=f"{role.mention if role else ''}", embed=embed)

@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    data = load_data()
    async def update_msg(chan_id, key, text, view):
        chan = bot.get_channel(chan_id)
        msg_id = data["messages"].get(key)
        if msg_id:
            try:
                msg = await chan.fetch_message(msg_id)
                await msg.edit(content=text, view=view)
                return
            except: pass
        new_msg = await chan.send(content=text, view=view)
        data["messages"][key] = new_msg.id

    await update_msg(ID_SALON_SAV, "sav", "🛡️ **Support Technique**", SAVView())
    await update_msg(ID_SALON_DEMANDE_AIDE, "aide", "🤝 **Entraide de Guilde**", CoopView())
    await update_msg(ID_SALON_NOTIFICATIONS, "notifs", "🔔 **Notifications**", NotifView())
    save_data(data)
    await ctx.send("✅ Mise à jour effectuée.", delete_after=3)

# --- SETUP ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ticket", style=discord.ButtonStyle.danger)
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"🛡️ <@{MY_USER_ID}>, ticket de {i.user.mention}")
        await i.response.send_message("Ticket ouvert !", ephemeral=True)

class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success)
    async def s(self, i, b): await i.response.send_modal(GoalModal("Succès"))
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success)
    async def q(self, i, b): await i.response.send_modal(GoalModal("Quête"))

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights v4.2 opérationnel !")
    if not almanax_loop.is_running(): almanax_loop.start()
    await post_almanax()
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(NotifView())

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
