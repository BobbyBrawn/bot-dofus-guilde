import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import requests
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION (Vérifie bien ces IDs sur ton Discord) ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_LISTE_DEMANDES = 1488953545930702938
ID_SALON_LOGS = 1489021869133791273
ID_SALON_NOTIFICATIONS = 1489022043839140010
ID_SALON_CONFIG = 1488847369322745917
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
        with open("data.json", "w") as f:
            json.dump({"points": {}, "messages": {}, "last_almanax": ""}, f)
        return {"points": {}, "messages": {}, "last_almanax": ""}
    with open("data.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=4)

# --- ALMANAX ---
async def post_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel:
        print(f"❌ ERREUR : Le salon Almanax (ID: {ID_SALON_ALMANAX}) est introuvable.")
        return

    today = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    url = f"https://api.dofusdu.de/dofus2/fr/almanax/{today}"
    
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            api_data = r.json()
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
            print("✅ Almanax posté avec succès.")
    except Exception as e:
        print(f"❌ Erreur Almanax : {e}")

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop():
    await post_almanax()

# --- VOCAUX TEMPORAIRES ---
temp_vocal_channels = []

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == ID_VOCAL_CREATOR:
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await member.guild.create_voice_channel(name=f"🔊 {member.display_name}", category=category)
        await member.move_to(new_chan)
        temp_vocal_channels.append(new_chan.id)

    if before.channel and before.channel.id in temp_vocal_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            temp_vocal_channels.remove(before.channel.id)

# --- MISSIONS & FIL ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id

    @discord.ui.button(label="Je suis dispo !", style=discord.ButtonStyle.success, custom_id="join_mission_btn")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        thread = bot.get_channel(self.thread_id)
        if thread:
            await thread.add_user(interaction.user)
            await thread.send(f"⚔️ {interaction.user.mention} a rejoint l'escouade !")
            await interaction.response.send_message("Tu as été ajouté au fil de discussion !", ephemeral=True)

class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Détails", placeholder=placeholder, style=discord.TextStyle.paragraph)
        self.add_item(self.goal)

    async def on_submit(self, interaction: discord.Interaction):
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        
        # 1. Message principal
        msg = await list_chan.send(f"{role.mention if role else ''}\n📋 **NOUVELLE MISSION : {self.category}**\n**Cible** : {self.goal.value}\n**Demandeur** : {interaction.user.mention}")
        
        # 2. Création du fil
        thread = await msg.create_thread(name=f"Mission-{interaction.user.display_name}", auto_archive_duration=60)
        
        # 3. Ajout du bouton "Dispo" au message d'origine
        await msg.edit(view=MissionView(thread.id))
        
        # 4. Message de clôture dans le fil
        view_f = discord.ui.View(timeout=None)
        btn_f = discord.ui.Button(label="Mission terminée !", style=discord.ButtonStyle.danger)
        async def fini_cb(i):
            data = load_data()
            data["points"][str(interaction.user.id)] = data["points"].get(str(interaction.user.id), 0) + 1
            save_data(data)
            await i.response.send_message("Félicitations ! Mission archivée.", ephemeral=True)
            await msg.delete()
            await thread.delete()
        btn_f.callback = fini_cb
        view_f.add_item(btn_f)

        await thread.send(f"🛡️ {interaction.user.mention}, utilise ce bouton quand l'objectif est rempli.", view=view_f)
        await interaction.response.send_message("Ta demande est en ligne !", ephemeral=True)

# --- INTERFACES ---
class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="c_succes")
    async def s(self, i, b): await i.response.send_modal(GoalModal("Succès", "Ex: Koutoulou Hardi"))
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="c_quete")
    async def q(self, i, b): await i.response.send_modal(GoalModal("Quête", "Ex: Combat Bolgrot"))
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.primary, custom_id="c_craft")
    async def c(self, i, b): await i.response.send_modal(GoalModal("Craft/FM", "Ex: Craft Voile d'Encre"))
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.secondary, custom_id="c_farm")
    async def f(self, i, b): await i.response.send_modal(GoalModal("Farming", "Ex: Donjon Korriandre"))

class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, custom_id="c_sav")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"🛡️ <@{MY_USER_ID}>, ticket de {i.user.mention}.")
        await i.response.send_message(f"Ticket ouvert : {t.mention}", ephemeral=True)

class NotifView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Almanax", style=discord.ButtonStyle.grey, emoji="📅", custom_id="n_alm")
    async def b1(self, i, b): await self.toggle(i, ROLE_ALMANAX)
    @discord.ui.button(label="Entraide", style=discord.ButtonStyle.grey, emoji="⚔️", custom_id="n_ent")
    async def b2(self, i, b): await self.toggle(i, ROLE_ENTRAIDE)
    @discord.ui.button(label="Annonces", style=discord.ButtonStyle.grey, emoji="📢", custom_id="n_ann")
    async def b3(self, i, b): await self.toggle(i, ROLE_ANNONCES)
    
    async def toggle(self, interaction, r_id):
        role = interaction.guild.get_role(r_id)
        if role in interaction.user.roles: await interaction.user.remove_roles(role)
        else: await interaction.user.add_roles(role)
        await interaction.response.send_message("Rôles mis à jour !", ephemeral=True)

# --- COMMANDES ---
@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    # Purge et renvoi des interfaces pour garantir les IDs
    await bot.get_channel(ID_SALON_SAV).purge(limit=5)
    await bot.get_channel(ID_SALON_SAV).send("👋 **Besoin d'aide ?**\nOuvre un ticket ici.", view=SAVView())
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).purge(limit=5)
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).send("🤝 **Entraide**\nLancer une demande :", view=CoopView())
    await bot.get_channel(ID_SALON_NOTIFICATIONS).purge(limit=5)
    await bot.get_channel(ID_SALON_NOTIFICATIONS).send("🔔 **Notifications**", view=NotifView())
    await ctx.send("✅ Interfaces rafraîchies.")

@bot.command()
async def force_almanax(ctx):
    if ctx.author.id == MY_USER_ID:
        await post_almanax()
        await ctx.send("✅ Tentative d'Almanax lancée. Vérifie les logs si rien n'apparaît.")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights v4.5 en ligne")
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(NotifView())
    if not almanax_loop.is_running(): almanax_loop.start()

bot.run(os.environ.get('DISCORD_TOKEN'))
