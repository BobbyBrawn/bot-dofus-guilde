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

# --- FORMULAIRE DE SAISIE (MODAL) ---
class GoalModal(discord.ui.Modal):
    def __init__(self, category_label):
        super().__init__(title=f"Aide : {category_label}")
        self.category_label = category_label
        
        self.goal_input = discord.ui.TextInput(
            label=f"Pour quel {category_label} as-tu besoin d'aide ?",
            placeholder="Ex: Koutoulou Hardi, Quête l'Eternel Moissonneur...",
            required=True,
            max_length=50
        )
        self.add_item(self.goal_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Création du fil avec le nom saisi + pseudo
        thread_name = f"[{self.goal_input.value}] {interaction.user.display_name}"
        
        thread = await interaction.channel.create_thread(
            name=thread_name,
            type=discord.ChannelType.public_thread,
            auto_archive_duration=60
        )
        
        view = discord.ui.View()
        btn_close = discord.ui.Button(label="Fini !", style=discord.ButtonStyle.grey)
        async def close_callback(inter):
            await inter.channel.delete()
        btn_close.callback = close_callback
        view.add_item(btn_close)
        
        await thread.send(f"⚔️ {interaction.user.mention} a besoin d'aide pour : **{self.goal_input.value}**. Qui est dispo ?", view=view)
        # On répond avec une réponse vide et invisible pour valider l'interaction sans message
        await interaction.response.send_message("Création en cours...", ephemeral=True, delete_after=1)

# --- SYSTÈME DE TICKETS SAV ---
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
        # On ne deferred pas pour pouvoir envoyer un message direct dans le thread
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
        
        msg = (f"🛡️ **Ticket ouvert pour {interaction.user.mention}**\n\n"
               "Explique-nous ton problème en détail ici. N'hésite pas à envoyer des **screenshots**.")
        
        await thread.send(msg, view=view)
        # Message éphémère qui s'auto-supprime après 1 seconde pour ne pas polluer
        await interaction.response.send_message("Ouverture du ticket...", ephemeral=True, delete_after=1)

# --- SYSTÈME D'ENTRAIDE ---
class CoopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="btn_s")
    async def s_btn(self, interaction, button): 
        await interaction.response.send_modal(GoalModal("Succès"))

    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="btn_q")
    async def q_btn(self, interaction, button): 
        await interaction.response.send_modal(GoalModal("Quête"))

    @discord.ui.button(label="Farming", style=discord.ButtonStyle.success, custom_id="btn_f")
    async def f_btn(self, interaction, button): 
        await interaction.response.send_modal(GoalModal("Farming"))

    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.success, custom_id="btn_c")
    async def c_btn(self, interaction, button): 
        await interaction.response.send_modal(GoalModal("Craft/FM"))

# --- SALONS VOCAUX ---
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id in VOCAL_CREATOR_IDS:
        limit = VOCAL_CREATOR_IDS[after.channel.id]
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await category.create_voice_channel(name=f"🔊 Salon de {member.display_name}", user_limit=limit)
        await member.move_to(new_chan)

    if before.channel and "Salon de" in before.channel.name:
        if len(before.channel.members) == 0:
            await before.channel.delete()

# --- INITIALISATION ---
@bot.command()
async def setup(ctx):
    if ctx.author.guild_permissions.administrator:
        sav_chan = bot.get_channel(ID_SALON_SAV)
        await sav_chan.send("🛡️ **Besoin de Bobby ?** Cliquez ci-dessous pour ouvrir un ticket privé :", view=SAVView())
        
        coop_chan = bot.get_channel(ID_SALON_DEMANDE_AIDE)
        await coop_chan.send("🤝 **Entraide de Guilde**\nCliquez sur une catégorie pour demander de l'aide :", view=CoopView())
        await ctx.send("✅ Mise à jour effectuée !")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights est prêt !")
    bot.add_view(SAVView())
    bot.add_view(CoopView())

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
