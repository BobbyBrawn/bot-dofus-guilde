import discord
from discord.ext import commands
import os

# --- CONFIGURATION DES IDS ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294

VOCAL_CREATOR_IDS = {
    1488847181329862679: 2,
    1488847226456506379: 5,
    1488847294244716544: 0
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
temp_channels = []

# --- 1. GESTION DES ERREURS ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"⚠️ Commande inconnue ! Vérifie la syntaxe, ou ouvre un ticket dans <#{ID_SALON_SAV}>.")

# --- 2. SYSTÈME DE TICKETS SAV (MAINTENANT EN THREADS) ---
class SAVView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Demande d'aide", style=discord.ButtonStyle.primary, custom_id="help_btn")
    async def help_callback(self, interaction, button):
        await self.create_sav_thread(interaction, "Aide")

    @discord.ui.button(label="Signalement de bug", style=discord.ButtonStyle.danger, custom_id="bug_btn")
    async def bug_callback(self, interaction, button):
        await self.create_sav_thread(interaction, "Bug")

    async def create_sav_thread(self, interaction, type_t):
        # On répond direct pour éviter "L'interaction a échoué"
        await interaction.response.defer(ephemeral=True)
        
        thread = await interaction.channel.create_thread(
            name=f"[{type_t}] {interaction.user.display_name}", 
            type=discord.ChannelType.private_thread # Thread privé pour le SAV
        )
        
        view = discord.ui.View()
        btn_close = discord.ui.Button(label="Fermer le ticket", style=discord.ButtonStyle.grey)
        async def close_callback(inter):
            await inter.channel.delete()
        btn_close.callback = close_callback
        view.add_item(btn_close)
        
        await thread.send(f"🛡️ Ticket ouvert pour {interaction.user.mention}. Un responsable va arriver.", view=view)
        await interaction.followup.send(f"Ton ticket a été créé ici : {thread.mention}", ephemeral=True)

# --- 3. SYSTÈME D'ENTRAIDE (COOP) ---
class CoopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_coop_thread(self, interaction, label):
        # On dit à Discord qu'on réfléchit pour éviter le bug d'interaction
        await interaction.response.defer(ephemeral=True)
        
        thread = await interaction.channel.create_thread(
            name=f"[{label}] {interaction.user.display_name}", 
            type=discord.ChannelType.public_thread
        )
        
        view = discord.ui.View()
        btn_close = discord.ui.Button(label="Fini !", style=discord.ButtonStyle.grey)
        async def close_callback(inter):
            await inter.channel.delete()
        btn_close.callback = close_callback
        view.add_item(btn_close)
        
        await thread.send(f"⚔️ {interaction.user.mention} a besoin d'aide pour : **{label}**. Qui est dispo ?", view=view)
        await interaction.followup.send(f"Demande d'aide lancée dans {thread.mention} !", ephemeral=True)

    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success)
    async def s_btn(self, interaction, button): await self.create_coop_thread(interaction, "Succès")
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success)
    async def q_btn(self, interaction, button): await self.create_coop_thread(interaction, "Quête")
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.success)
    async def f_btn(self, interaction, button): await self.create_coop_thread(interaction, "Farming")
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.success)
    async def c_btn(self, interaction, button): await self.create_coop_thread(interaction, "Craft/FM")

# --- 4. SALONS VOCAUX DYNAMIQUES ---
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id in VOCAL_CREATOR_IDS:
        limit = VOCAL_CREATOR_IDS[after.channel.id]
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await category.create_voice_channel(name=f"🔊 Salon de {member.display_name}", user_limit=limit)
        await member.move_to(new_chan)
        temp_channels.append(new_chan.id)

    if before.channel and before.channel.id in temp_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            temp_channels.remove(before.channel.id)

# --- INITIALISATION ---
@bot.command()
async def setup(ctx):
    if ctx.author.guild_permissions.administrator:
        sav_chan = bot.get_channel(ID_SALON_SAV)
        await sav_chan.send("🛡️ **Besoin de Bobby ?** Cliquez ci-dessous pour ouvrir un ticket privé :", view=SAVView())
        
        coop_chan = bot.get_channel(ID_SALON_DEMANDE_AIDE)
        await coop_chan.send("🤝 **Entraide de Guilde**\nCliquez sur une catégorie pour ouvrir un fil d'entraide :", view=CoopView())
        await ctx.send("✅ Configuration mise à jour !")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights est prêt !")
    bot.add_view(SAVView())
    bot.add_view(CoopView())

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)import discord
from discord.ext import commands
import os

# --- CONFIGURATION DES IDS ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294

# Dictionnaire des salons créateurs : ID du salon -> Limite de places (0 = illimité)
VOCAL_CREATOR_IDS = {
    1488847181329862679: 2,
    1488847226456506379: 5,
    1488847294244716544: 0
}

# --- SETUP DU BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
temp_channels = []

# --- 1. GESTION DES ERREURS ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"⚠️ Je pense que tu t'es trompé en tapant la commande ! Tape `!commandes` pour vérifier la syntaxe de celle que tu veux utiliser, et si tu as toujours un problème, ouvre un ticket avec le plus d'infos possibles dans <#{ID_SALON_SAV}>, Bobby y répondra dès que possible !")

# --- 2. SYSTÈME DE TICKETS (SAV) ---
class SAVView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Demande d'aide", style=discord.ButtonStyle.primary, custom_id="help_btn")
    async def help_callback(self, interaction, button):
        await self.create_ticket(interaction, "aide")

    @discord.ui.button(label="Signalement de bug", style=discord.ButtonStyle.danger, custom_id="bug_btn")
    async def bug_callback(self, interaction, button):
        await self.create_ticket(interaction, "bug")

    async def create_ticket(self, interaction, type_t):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f"{type_t}-{interaction.user.display_name}", overwrites=overwrites)
        await interaction.response.send_message(f"Ticket créé : {channel.mention}", ephemeral=True)
        await channel.send(f"Bonjour {interaction.user.mention}, un responsable de la guilde va s'occuper de toi ici pour ton {type_t}.")

# --- 3. SYSTÈME D'ENTRAIDE (COOP) ---
class CoopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_coop_thread(self, interaction, label):
        thread = await interaction.channel.create_thread(name=f"[{label}] {interaction.user.display_name}", type=discord.ChannelType.public_thread)
        view = discord.ui.View()
        btn_close = discord.ui.Button(label="Fini !", style=discord.ButtonStyle.grey)
        async def close_callback(inter):
            await inter.channel.delete()
        btn_close.callback = close_callback
        view.add_item(btn_close)
        await thread.send(f"⚔️ {interaction.user.mention} a besoin d'aide pour : **{label}**. Qui est dispo ? Cliquez sur 'Fini !' quand c'est terminé.", view=view)
        await interaction.response.send_message(f"Demande d'aide lancée dans {thread.mention} !", ephemeral=True)

    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success)
    async def s_btn(self, interaction, button): await self.create_coop_thread(interaction, "Succès")
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success)
    async def q_btn(self, interaction, button): await self.create_coop_thread(interaction, "Quête")
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.success)
    async def f_btn(self, interaction, button): await self.create_coop_thread(interaction, "Farming")
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.success)
    async def c_btn(self, interaction, button): await self.create_coop_thread(interaction, "Craft/FM")

# --- 4. SALONS VOCAUX DYNAMIQUES ---
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id in VOCAL_CREATOR_IDS:
        limit = VOCAL_CREATOR_IDS[after.channel.id]
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await category.create_voice_channel(name=f"🔊 Salon de {member.display_name}", user_limit=limit)
        await member.move_to(new_chan)
        temp_channels.append(new_chan.id)

    if before.channel and before.channel.id in temp_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            temp_channels.remove(before.channel.id)

# --- INITIALISATION DES BOUTONS ---
@bot.command()
async def setup(ctx):
    # Seul le créateur peut lancer le setup
    if ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator:
        sav_chan = bot.get_channel(ID_SALON_SAV)
        await sav_chan.send("🛡️ **Besoin de Bobby ?** Cliquez sur un bouton ci-dessous :", view=SAVView())
        
        coop_chan = bot.get_channel(ID_SALON_DEMANDE_AIDE)
        await coop_chan.send("🤝 **Entraide de Guilde**\nChoisissez votre catégorie pour ouvrir une demande :", view=CoopView())
        await ctx.send("✅ Configuration des salons terminée avec succès !")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights est prêt !")
    bot.add_view(SAVView())
    bot.add_view(CoopView())

# --- LANCEMENT ---
token = os.environ.get('DISCORD_TOKEN')
if token:
    bot.run(token)
else:
    print("❌ ERREUR : La variable DISCORD_TOKEN est vide ou introuvable !")
