import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import requests
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_LISTE_DEMANDES = 1488953545930702938
ID_SALON_LOGS = 1489021869133791273
ID_SALON_NOTIFICATIONS = 1489022043839140010
ID_SALON_CONFIG = 1488847369322745917
ID_VOCAL_CREATOR = 1488847294244716544 # Salon "Clique pour créer"

ROLE_ALMANAX = 1489021032965738636
ROLE_ENTRAIDE = 1489021136011530282
ROLE_ANNONCES = 1489021205011890410

MY_USER_ID = 270182770163187712
PARIS_TZ = timezone(timedelta(hours=2))

intents = discord.Intents.all() # Obligatoire pour les vocaux
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
    except: return None

async def post_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel: return
    
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

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop():
    await post_almanax()

# --- VOCAUX TEMPORAIRES ---
temp_vocal_channels = []

@bot.event
async def on_voice_state_update(member, before, after):
    # Création
    if after.channel and after.channel.id == ID_VOCAL_CREATOR:
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await member.guild.create_voice_channel(
            name=f"🔊 {member.display_name}",
            category=category
        )
        await member.move_to(new_chan)
        temp_vocal_channels.append(new_chan.id)

    # Suppression si vide
    if before.channel and before.channel.id in temp_vocal_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            temp_vocal_channels.remove(before.channel.id)

# --- FORMULAIRES D'AIDE ---
class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Détails de la demande", placeholder=placeholder, style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.goal)

    async def on_submit(self, interaction: discord.Interaction):
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        msg = await list_chan.send(f"{role.mention if role else ''}\n📋 **MISSION : {self.category}**\n**Cible** : {self.goal.value}\n**Demandeur** : {interaction.user.mention}")
        thread = await list_chan.create_thread(name=f"Mission-{interaction.user.display_name}", type=discord.ChannelType.private_thread)
        
        # Bouton Terminer
        view_f = discord.ui.View(timeout=None)
        btn_f = discord.ui.Button(label="Mission terminée !", style=discord.ButtonStyle.success)
        async def fini_cb(i):
            data = load_data()
            data["points"][str(interaction.user.id)] = data["points"].get(str(interaction.user.id), 0) + 1
            save_data(data)
            await i.response.send_message("Validé ! +1 point.", ephemeral=True)
            await msg.delete()
            await thread.delete()
        btn_f.callback = fini_cb
        view_f.add_item(btn_f)

        await thread.send(f"🛡️ Mission {self.category} lancée ! Clique sur le bouton une fois fini.", view=view_f)
        await interaction.response.send_message("Mission publiée !", ephemeral=True)

class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="btn_s")
    async def s(self, i, b): await i.response.send_modal(GoalModal("Succès", "Ex: Koutoulou Hardi"))
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="btn_q")
    async def q(self, i, b): await i.response.send_modal(GoalModal("Quête", "Ex: Combat final Bolgrot"))
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.primary, custom_id="btn_c")
    async def c(self, i, b): await i.response.send_modal(GoalModal("Craft/FM", "Ex: Craft Voile d'Encre / FM dague Erhy"))
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.secondary, custom_id="btn_f")
    async def f(self, i, b): await i.response.send_modal(GoalModal("Farming", "Ex: Donjon Korriandre en boucle"))

# --- SAV & NOTIFS ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, emoji="🎫", custom_id="open_sav")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"🛡️ <@{MY_USER_ID}>, ticket de {i.user.mention}. Il répondra dès que possible.")
        await i.response.send_message(f"Ticket ouvert : {t.mention}", ephemeral=True)

class NotifView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Almanax", style=discord.ButtonStyle.grey, emoji="📅", custom_id="n_alm")
    async def b1(self, i, b): await self.toggle(i, ROLE_ALMANAX)
    async def toggle(self, interaction, r_id):
        role = interaction.guild.get_role(r_id)
        if role in interaction.user.roles: await interaction.user.remove_roles(role)
        else: await interaction.user.add_roles(role)
        await interaction.response.send_message("Statut notif mis à jour.", ephemeral=True)

# --- COMMANDES ---
@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    c_sav = bot.get_channel(ID_SALON_SAV)
    await c_sav.purge(limit=5)
    await c_sav.send("👋 **Besoin d'aide ?**\nOuvre un ticket pour parler aux officiers.", view=SAVView())
    
    c_aide = bot.get_channel(ID_SALON_DEMANDE_AIDE)
    await c_aide.purge(limit=5)
    await c_aide.send("🤝 **Entraide de Guilde**\nChoisis ta catégorie :", view=CoopView())
    await ctx.send("✅ Interface à jour.")

@bot.command()
async def force_almanax(ctx):
    if ctx.author.id == MY_USER_ID:
        await post_almanax()
        await ctx.send("✅ Almanax forcé.")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights v4.4 Opérationnel")
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(NotifView())
    if not almanax_loop.is_running(): almanax_loop.start()

bot.run(os.environ.get('DISCORD_TOKEN'))
