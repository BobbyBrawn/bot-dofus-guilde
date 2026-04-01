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
    def __init__(self, category_label, question_text, placeholder_text):
        super().__init__(title=f"Demande : {category_label}")
        
        self.goal_input = discord.ui.TextInput(
            label=question_text, # La question personnalisée
            placeholder=placeholder_text, # L'exemple personnalisé
            required=True,
            max_length=50
        )
        self.add_item(self.goal_input)

    async def on_submit(self, interaction: discord.Interaction):
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
        
        await thread.send(f"⚔️ **Nouvelle mission !**\n{interaction.user.mention} a besoin d'un coup de main pour : **{self.goal_input.value}**.\nQui est dispo ?", view=view)
        await interaction.response.send_message("Mission lancée !", ephemeral=True, delete_after=1)

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
        
        msg = (f"🛡️ **Ticket SAV ouvert pour {interaction.user.mention}**\n\n"
               "Explique ton souci ici. Tu peux ajouter des **screenshots** pour nous aider !")
        
        await thread.send(msg, view=view)
        await interaction.response.send_message("Ouverture...", ephemeral=True, delete_after=1)

# --- SYSTÈME D'ENTRAIDE ---
class CoopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success, custom_id="btn_s")
    async def s_btn(self, interaction, button): 
        await interaction.response.send_modal(GoalModal("Succès", "Pour quel succès as-tu besoin d'aide ?", "Koutoulou Hardi, Kabahal Duo, Vortex Focus .."))

    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success, custom_id="btn_q")
    async def q_btn(self, interaction, button): 
        await interaction.response.send_modal(GoalModal("Quête", "Pour quelle quête as-tu besoin d'aide ?", "Mission Solution, les Septs Mercemers .."))

    @discord.ui.button(label="Farming", style=discord.ButtonStyle.success, custom_id="btn_f")
    async def f_btn(self, interaction, button): 
        await interaction.response.send_modal(GoalModal("Farming", "Que veux-tu farmer ?", "Ressources, XP, Donjon précis..."))

    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.success, custom_id="btn_c")
    async def c_btn(self, interaction, button): 
        # Ici pas d'exemple (chaîne vide) et question spécifique métier
        await interaction.response.send_modal(GoalModal("Craft/FM", "De quel métier as-tu besoin ?", ""))

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
        await sav_chan.send("🛡️ **Besoin d'un coup de main technique ?**\nClique ici pour ouvrir un ticket privé :", view=SAVView())
        
        coop_chan = bot.get_channel(ID_SALON_DEMANDE_AIDE)
        await coop_chan.send("🤝 **Entraide Watcher of Knights**\nChoisis une catégorie pour lancer ton appel aux armes :", view=CoopView())
        await ctx.send("✅ Mise à jour effectuée !", delete_after=3)

@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights est prêt !")
    bot.add_view(SAVView())
    bot.add_view(CoopView())

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
