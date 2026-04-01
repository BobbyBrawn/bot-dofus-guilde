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
        await ctx.send(f"⚠️ Commande inconnue ! Ouvre un ticket dans <#{ID_SALON_SAV}> si besoin.")

# --- 2. SYSTÈME DE TICKETS SAV (THREADS PRIVÉS) ---
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
        await interaction.response.defer(ephemeral=True)
        thread = await interaction.channel.create_thread(
            name=f"[{type_t}] {interaction.user.display_name}", 
            type=discord.ChannelType.private_thread 
        )
        
        view = discord.ui.View()
        btn_close = discord.ui.Button(label="Fermer le ticket", style=discord.ButtonStyle.grey)
        async def close_callback(inter):
            await inter.channel.delete()
        btn_close.callback = close_callback
        view.add_item(btn_close)
        
        # Message de bienvenue personnalisé
        msg = (f"🛡️ **Ticket ouvert pour {interaction.user.mention}**\n\n"
               "Explique-nous ton problème en détail ici. N'hésite pas à envoyer des **screenshots** "
               "ou toute info qui pourrait aider Bobby à te répondre au plus vite !")
        
        await thread.send(msg, view=view)
        await interaction.followup.send(f"Ton ticket privé est ici : {thread.mention}", ephemeral=True)

# --- 3. SYSTÈME D'ENTRAIDE (COOP) ---
class CoopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_coop_thread(self, interaction, label):
        # Correction : On utilise followup pour être sûr que l'interaction ne time out pas
        await interaction.response.defer(ephemeral=True)
        try:
            thread = await interaction.channel.create_thread(
                name=f"[{label}] {interaction.user.display_name}", 
                type=discord.ChannelType.public_thread,
                auto_archive_duration=60
            )
            
            view = discord.ui.View()
            btn_close = discord.ui.Button(label="Fini !", style=discord.ButtonStyle.grey)
            async def close_callback(inter):
                await inter.channel.delete()
            btn_close.callback = close_callback
            view.add_item(btn_close)
            
            await thread.send(f"⚔️ {interaction.user.mention} a besoin d'aide pour : **{label}**. Qui est dispo ?", view=view)
            await interaction.followup.send(f"Demande lancée dans {thread.mention} !", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Erreur : Vérifie que Bobby a la permission de créer des fils publics.", ephemeral=True)

    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="btn_s")
    async def s_btn(self, interaction, button): await self.create_coop_thread(interaction, "Succès")
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="btn_q")
    async def q_btn(self, interaction, button): await self.create_coop_thread(interaction, "Quête")
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.success, custom_id="btn_f")
    async def f_btn(self, interaction, button): await self.create_coop_thread(interaction, "Farming")
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.success, custom_id="btn_c")
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
            try:
                await before.channel.delete()
                temp_channels.remove(before.channel.id)
            except: pass

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
bot.run(token)
