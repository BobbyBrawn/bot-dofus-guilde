import discord
from discord.ext import commands, tasks
import os
from datetime import datetime, time

# --- CONFIGURATION DES IDS ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_GESTION_VOCAL = 1488953466494652446
ID_SALON_LISTE_DEMANDES = 1488953545930702938

# Salon créateur unique (Illimité par défaut)
ID_VOCAL_CREATOR = 1488847294244716544

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- DICTIONNAIRES DE MÉMOIRE ---
# Associe un ID de message dans la liste à un ID de thread
active_missions = {} 
# Associe un ID de salon vocal à son propriétaire
vocal_owners = {}

# --- 1. SYSTÈME ALMANAX (AUTOMATIQUE) ---
@tasks.loop(time=time(hour=0, minute=1)) # Se lance à minuit pile
async def check_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if channel:
        embed = discord.Embed(
            title="📅 Almanax du Jour",
            description="Le Méryde du jour vous salue !",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Offrande", value="🔍 Récupération en cours...", inline=True)
        embed.add_field(name="Bonus", value="✨ Consultez le grimoire !", inline=True)
        embed.set_footer(text="Watcher of Knights - Routine matinale")
        await channel.send(embed=embed)

# --- 2. GESTIONNAIRE DE MISSIONS (ENTRAIDE) ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id

    @discord.ui.button(label="Dispo pour aider", style=discord.ButtonStyle.success, custom_id="dispo_btn")
    async def dispo_callback(self, interaction, button):
        thread = bot.get_channel(self.thread_id)
        if thread:
            await thread.add_user(interaction.user)
            await thread.send(f"⚔️ {interaction.user.mention} a rejoint l'escouade !")
            await interaction.response.send_message("Tu as été ajouté au fil d'aide !", ephemeral=True, delete_after=2)
        else:
            await interaction.response.send_message("Le fil n'existe plus.", ephemeral=True)

class GoalModal(discord.ui.Modal):
    def __init__(self, category, question, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal_input = discord.ui.TextInput(label=question, placeholder=placeholder, required=True, max_length=50)
        self.add_item(self.goal_input)

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Créer le Thread PRIVÉ (seul le demandeur y est au début)
        thread = await interaction.channel.create_thread(
            name=f"[{self.goal_input.value}] {interaction.user.display_name}",
            type=discord.ChannelType.private_thread
        )
        
        # 2. Envoyer le bouton de fermeture dans le thread
        view_close = discord.ui.View()
        btn_close = discord.ui.Button(label="Fini !", style=discord.ButtonStyle.grey)
        
        async def close_callback(inter):
            # Trouver et supprimer le message dans la liste
            for msg_id, t_id in active_missions.items():
                if t_id == thread.id:
                    list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
                    try:
                        old_msg = await list_chan.fetch_message(msg_id)
                        await old_msg.delete()
                    except: pass
            await inter.channel.delete()

        btn_close.callback = close_callback
        view_close.add_item(btn_close)
        await thread.send(f"🛡️ Mission : **{self.goal_input.value}**\nDemandeur : {interaction.user.mention}", view=view_close)

        # 3. Envoyer l'annonce dans LISTE-DEMANDES
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        list_msg = await list_chan.send(
            f"📢 **NOUVELLE DEMANDE**\n**Type** : {self.category}\n**Cible** : {self.goal_input.value}\n**Demandeur** : {interaction.user.display_name}",
            view=MissionView(thread.id)
        )
        active_missions[list_msg.id] = thread.id
        
        await interaction.response.send_message("Demande publiée dans la liste !", ephemeral=True, delete_after=1)

# --- 3. TÉLÉCOMMANDE VOCALE ---
class VocalControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def check_owner(self, interaction):
        for chan_id, owner_id in vocal_owners.items():
            if owner_id == interaction.user.id:
                return bot.get_channel(chan_id)
        return None

    @discord.ui.button(label="🔒 Privé", style=discord.ButtonStyle.secondary)
    async def lock(self, interaction, button):
        chan = await self.check_owner(interaction)
        if chan:
            await chan.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("Salon verrouillé !", ephemeral=True, delete_after=2)
        else: await interaction.response.send_message("Tu n'as pas de salon actif.", ephemeral=True, delete_after=2)

    @discord.ui.button(label="🔓 Public", style=discord.ButtonStyle.secondary)
    async def unlock(self, interaction, button):
        chan = await self.check_owner(interaction)
        if chan:
            await chan.set_permissions(interaction.guild.default_role, connect=True)
            await interaction.response.send_message("Salon ouvert !", ephemeral=True, delete_after=2)
        else: await interaction.response.send_message("Tu n'as pas de salon actif.", ephemeral=True, delete_after=2)

    @discord.ui.button(label="2 Places", style=discord.ButtonStyle.primary)
    async def limit2(self, interaction, button):
        chan = await self.check_owner(interaction)
        if chan: await chan.edit(user_limit=2)
        await interaction.response.send_message("Limite : 2", ephemeral=True, delete_after=1)

    @discord.ui.button(label="5 Places", style=discord.ButtonStyle.primary)
    async def limit5(self, interaction, button):
        chan = await self.check_owner(interaction)
        if chan: await chan.edit(user_limit=5)
        await interaction.response.send_message("Limite : 5", ephemeral=True, delete_after=1)

    @discord.ui.button(label="♾️ Illimité", style=discord.ButtonStyle.primary)
    async def limit0(self, interaction, button):
        chan = await self.check_owner(interaction)
        if chan: await chan.edit(user_limit=0)
        await interaction.response.send_message("Limite retirée", ephemeral=True, delete_after=1)

# --- 4. ÉVÉNEMENTS (VOCAL & READY) ---
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == ID_VOCAL_CREATOR:
        category = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await category.create_voice_channel(name=f"🔊 Salon de {member.display_name}")
        await member.move_to(new_chan)
        vocal_owners[new_chan.id] = member.id

    if before.channel and before.channel.id in vocal_owners:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            del vocal_owners[before.channel.id]

# --- 5. COMMANDE UPDATE (LE GRAND MÉNAGE) ---
@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return

    # Purge des salons de menus
    for sid in [ID_SALON_SAV, ID_SALON_DEMANDE_AIDE, ID_SALON_GESTION_VOCAL]:
        chan = bot.get_channel(sid)
        await chan.purge()

    # Re-setup
    from __main__ import SAVView, CoopView # Import interne pour les classes
    await bot.get_channel(ID_SALON_SAV).send("🛡️ **Besoin d'aide technique ?**", view=SAVView())
    await bot.get_channel(ID_SALON_DEMANDE_AIDE).send("🤝 **Entraide de Guilde**\n*(Les demandes s'affichent dans <#1488953545930702938>)*", view=CoopView())
    await bot.get_channel(ID_SALON_GESTION_VOCAL).send("🎙️ **Télécommande de ton Salon Vocal**\nUtilise les boutons ci-dessous pour modifier ton salon en temps réel :", view=VocalControlView())
    
    await ctx.send("✅ Mise à jour terminée !", delete_after=3)

# Classes SAV et Coop (Adaptées pour la v3)
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Aide / Bug", style=discord.ButtonStyle.danger)
    async def callback(self, interaction, button):
        thread = await interaction.channel.create_thread(name=f"[SAV] {interaction.user.display_name}", type=discord.ChannelType.private_thread)
        await thread.send(f"🛡️ Ticket de {interaction.user.mention}. Décris ton souci.", view=discord.ui.View().add_item(discord.ui.Button(label="Fermer", style=discord.ButtonStyle.grey)))
        await interaction.response.send_message("Ticket ouvert !", ephemeral=True, delete_after=1)

class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", style=discord.ButtonStyle.success)
    async def s(self, interaction, button): await interaction.response.send_modal(GoalModal("Succès", "Quel succès ?", "Koutoulou Hardi..."))
    @discord.ui.button(label="Quête", style=discord.ButtonStyle.success)
    async def q(self, interaction, button): await interaction.response.send_modal(GoalModal("Quête", "Quelle quête ?", "Mission Solution..."))
    @discord.ui.button(label="Farming", style=discord.ButtonStyle.success)
    async def f(self, interaction, button): await interaction.response.send_modal(GoalModal("Farming", "Quoi ?", "Ressources..."))
    @discord.ui.button(label="Craft/FM", style=discord.ButtonStyle.success)
    async def c(self, interaction, button): await interaction.response.send_modal(GoalModal("Craft/FM", "Métier ?", ""))

@bot.event
async def on_ready():
    print(f"🛡️ Bobby v3.0 opérationnel !")
    check_almanax.start()
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(VocalControlView())

token = os.environ.get('DISCORD_TOKEN')
bot.run(token)
