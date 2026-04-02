import discord
from discord.ext import commands, tasks
import os
import json
import requests
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_LISTE_DEMANDES = 1488953545930702938
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
        with open("data.json", "w") as f: json.dump({"points": {}}, f)
    with open("data.json", "r") as f: return json.load(f)

def save_data(data):
    with open("data.json", "w") as f: json.dump(data, f, indent=4)

# --- ALMANAX ---
async def post_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel: return
    today = datetime.now(PARIS_TZ).strftime("%Y-%m-%d")
    url = f"https://api.dofusdu.de/dofus2/fr/almanax/{today}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            api_data = r.json()
            embed = discord.Embed(
                title=f"📅 ALMANAX : {api_data['boss']['name'].upper()}", 
                description=f"**L'effet Méryde**\n{api_data['boss']['description']}",
                color=0xE67E22
            )
            embed.set_thumbnail(url=api_data['tribute']['item']['image_urls']['icon'])
            embed.add_field(name="✨ Bonus et Quêtes DOFUS", value=f"**Bonus :** {api_data['bonus']['description']}", inline=False)
            embed.add_field(name="🙏 Offrande", value=f"Récupérer **{api_data['tribute']['quantity']}x {api_data['tribute']['item']['name']}** et rapporter l'offrande à Théodoran Ax.", inline=False)
            role = channel.guild.get_role(ROLE_ALMANAX)
            await channel.send(content=f"{role.mention if role else ''}", embed=embed)
    except: pass

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop(): await post_almanax()

# --- MISSIONS ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id
    @discord.ui.button(label="Je suis dispo pour aider !", style=discord.ButtonStyle.success, custom_id="join_mission")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        thread = bot.get_channel(self.thread_id)
        if thread:
            await thread.add_user(interaction.user)
            await thread.send(f"⚔️ {interaction.user.mention} rejoint l'escouade !")
            await interaction.response.send_message("Tu as été ajouté au fil !", ephemeral=True)

class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Cible", placeholder=placeholder, required=True)
        self.add_item(self.goal)

    async def on_submit(self, interaction: discord.Interaction):
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        msg = await list_chan.send(f"{role.mention if role else ''}\n📋 **MISSION : {self.category}**\n**Demandeur** : {interaction.user.display_name}\n**Objectif** : {self.goal.value}")
        thread = await msg.create_thread(name=f"Mission-{self.goal.value}", auto_archive_duration=60)
        await msg.edit(view=MissionView(thread.id))
        
        view_f = discord.ui.View(timeout=None)
        btn_f = discord.ui.Button(label="Fini !", style=discord.ButtonStyle.success)
        async def fini_cb(i):
            if i.user.id != interaction.user.id:
                return await i.response.send_message("Seul le demandeur peut valider.", ephemeral=True)
            data = load_data()
            data["points"][str(i.user.id)] = data["points"].get(str(i.user.id), 0) + 1
            save_data(data)
            await i.response.send_message("Mission validée ! +1 point.", ephemeral=True)
            await msg.delete()
            await thread.delete()
        btn_f.callback = fini_cb
        view_f.add_item(btn_f)
        await thread.send(f"🛡️ Mission lancée ! {interaction.user.mention}, clique sur Fini une fois terminé.", view=view_f)
        await interaction.response.send_message("Publié !", ephemeral=True)

# --- NOTIFICATIONS (TOGGLE) ---
class NotifView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Almanax", emoji="📅", custom_id="n_alm")
    async def b1(self, i, b): await self.toggle(i, ROLE_ALMANAX)
    @discord.ui.button(label="Entraide", emoji="⚔️", custom_id="n_ent")
    async def b2(self, i, b): await self.toggle(i, ROLE_ENTRAIDE)
    @discord.ui.button(label="Annonces", emoji="📢", custom_id="n_ann")
    async def b3(self, i, b): await self.toggle(i, ROLE_ANNONCES)
    async def toggle(self, interaction, r_id):
        role = interaction.guild.get_role(r_id)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Notifs {role.name} retirées.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Notifs {role.name} activées !", ephemeral=True)

# --- CONFIGURATION INTERFACES ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, custom_id="sav_t")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"🛡️ <@{MY_USER_ID}>, ticket de {i.user.mention}. Il répondra au plus vite.")
        await i.response.send_message(f"Fil ouvert : {t.mention}", ephemeral=True)

class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="coop_s")
    async def s(self, i, b): await i.response.send_modal(GoalModal("Succès", "Ex: Koutoulou Hardi"))
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="coop_q")
    async def q(self, i, b): await i.response.send_modal(GoalModal("Quête", "Ex: Combat final Bolgrot"))
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.primary, custom_id="coop_c")
    async def c(self, i, b): await i.response.send_modal(GoalModal("Craft/FM", "Ex: Craft Voile d'Encre / FM dague Erhy"))
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.secondary, custom_id="coop_f")
    async def f(self, i, b): await i.response.send_modal(GoalModal("Farming", "Ex: Donjon Korriandre en boucle"))

@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    await bot.get_channel(ID_SALON_SAV).purge(limit=5)
    await bot.get_channel(ID_SALON_SAV).send("🛡️ **Support Technique**\nOuvre un ticket ici.", view=SAVView())
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).purge(limit=5)
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).send("🤝 **Entraide de Guilde**", view=CoopView())
    await bot.get_channel(ID_SALON_NOTIFICATIONS).purge(limit=5)
    await bot.get_channel(ID_SALON_NOTIFICATIONS).send("🔔 **Notifications**", view=NotifView())
    await ctx.send("✅ Config mise à jour.")

@bot.command()
async def force_almanax(ctx):
    if ctx.author.id == MY_USER_ID: await post_almanax()

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights v4.9 opérationnel")
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(NotifView())
    if not almanax_loop.is_running(): almanax_loop.start()

bot.run(os.environ.get('DISCORD_TOKEN'))
