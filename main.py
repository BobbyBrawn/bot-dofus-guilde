import discord
from discord.ext import commands, tasks
import os
import json
import requests
import asyncio
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION ---
ID_CATEGORIE_VOCAL = 1488846909622849566
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_LISTE_DEMANDES = 1488953545930702938
ID_SALON_CONFIG = 1488953466494652446
ID_SALON_NOTIFICATIONS = 1489022043839140010
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
            json.dump({"points": {}, "notif_msg_id": 0, "active_missions": {}}, f)
    with open("data.json", "r") as f: return json.load(f)

def save_data(data):
    with open("data.json", "w") as f: json.dump(data, f, indent=4)

# --- ALMANAX ---
async def get_almanax_embed():
    try:
        # URL V3 (Standard 2026 pour Dofus Unity / 2.0)
        url = "https://api.dofusdu.de/dofus2/fr/almanax"
        headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
        
        # On essaie d'abord l'URL classique
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        # Si c'est une liste vide, on tente l'URL "v3" qui est le nouveau standard
        if not data or (isinstance(data, list) and len(data) == 0):
            url_v3 = "https://api.dofusdu.de/dofus2/fr/almanax/today"
            response = requests.get(url_v3, headers=headers, timeout=10)
            data = response.json()

        # Extraction selon le format dictionnaire direct (standard V3)
        # On ne force plus le [0] si c'est déjà un dictionnaire
        item = data[0] if isinstance(data, list) and len(data) > 0 else data
        
        if not item or not isinstance(item, dict):
            print("❌ Données Almanax vides ou mal formées.")
            return None

        meryde_name = item.get("meryde", {}).get("name", "Inconnu")
        bonus_desc = item.get("bonus", {}).get("description", "Pas de bonus")
        offrande_name = item.get("offering", {}).get("name", "Pas d'offrande")
        image_url = item.get("meryde", {}).get("image_url", "")

        embed = discord.Embed(
            title=f"📅 ALMANAX : {meryde_name.upper()}",
            description=f"✨ **Bonus**\n{bonus_desc}\n\n🙏 **Offrande**\n{offrande_name}",
            color=0xF1C40F,
            timestamp=datetime.now()
        )
        if image_url: embed.set_thumbnail(url=image_url)
        return embed

    except Exception as e:
        print(f"❌ Erreur Script : {e}")
        return None
@tasks.loop(time=time(hour=0, minute=1, tzinfo=PARIS_TZ))
async def almanax_loop():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel: return

    embed = await get_almanax_embed()
    if embed:
        # On mentionne le rôle pour ceux qui veulent la notif
        await channel.send(content=f"<@&{ROLE_ALMANAX}>", embed=embed)

# --- VOCAUX ---
temp_vocal_channels = []
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == ID_VOCAL_CREATOR:
        cat = bot.get_channel(ID_CATEGORIE_VOCAL)
        new_chan = await member.guild.create_voice_channel(name=f"🔊 {member.display_name}", category=cat)
        await member.move_to(new_chan)
        temp_vocal_channels.append(new_chan.id)
    if before.channel and before.channel.id in temp_vocal_channels:
        if len(before.channel.members) == 0:
            try:
                await before.channel.delete()
                temp_vocal_channels.remove(before.channel.id)
            except: pass

# --- NOTIFICATIONS (RÉACTIONS) ---
@bot.event
async def on_raw_reaction_add(payload):
    data = load_data()
    if payload.message_id != data.get("notif_msg_id") or payload.user_id == bot.user.id: return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role_id = { "📅": ROLE_ALMANAX, "⚔️": ROLE_ENTRAIDE, "📢": ROLE_ANNONCES }.get(str(payload.emoji))
    if role_id:
        role = guild.get_role(role_id)
        if role: await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    data = load_data()
    if payload.message_id != data.get("notif_msg_id") or payload.user_id == bot.user.id: return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role_id = { "📅": ROLE_ALMANAX, "⚔️": ROLE_ENTRAIDE, "📢": ROLE_ANNONCES }.get(str(payload.emoji))
    if role_id:
        role = guild.get_role(role_id)
        if role: await member.remove_roles(role)

# --- CLASSES MISSIONS (ORDRE CORRIGÉ) ---

class MissionView(discord.ui.View):
    def __init__(self, thread_id=None):
        super().__init__(timeout=None)
        self.thread_id = thread_id

    @discord.ui.button(label="Je suis dispo !", emoji="⚔️", style=discord.ButtonStyle.success, custom_id="join_mission_btn")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Si thread_id est None (cas du reboot), on le récupère via le nom du bouton ou la logique du salon
        t_id = self.thread_id or interaction.message.id # fallback
        # Note: En persistance pure, on stocke souvent l'ID dans le custom_id, mais restons simple :
        data = load_data()
        # On retrouve l'ID du fil car on a stocké {ID_FIL: ID_MESSAGE}
        target_thread_id = None
        for tid, mid in data["active_missions"].items():
            if mid == interaction.message.id:
                target_thread_id = int(tid)
                break
        
        if target_thread_id:
            thread = bot.get_channel(target_thread_id)
            if thread:
                await thread.add_user(interaction.user)
                await thread.send(f"🛡️ **{interaction.user.display_name}** a rejoint l'escouade !")
                await interaction.response.send_message(f"✅ Ajouté au fil : <#{target_thread_id}>", ephemeral=True)
                return
        await interaction.response.send_message("❌ Impossible de trouver le fil lié.", ephemeral=True)

class FinishView(discord.ui.View):
    def __init__(self, creator_id=None):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="Mission terminée !", style=discord.ButtonStyle.danger, custom_id="persistent_finish_btn")
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            return await interaction.response.send_message("❌ Seul le demandeur peut clore la mission.", ephemeral=True)

        await interaction.response.defer()
        data = load_data()
        thread_id_str = str(interaction.channel.id)
        msg_id = data["active_missions"].get(thread_id_str)

        if msg_id:
            try:
                list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
                msg = await list_chan.fetch_message(msg_id)
                await msg.delete()
            except: pass
            del data["active_missions"][thread_id_str]
            save_data(data)

        await interaction.followup.send("✅ Mission close, suppression...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Objectif", placeholder=placeholder, style=discord.TextStyle.paragraph, max_length=200)
        self.add_item(self.goal)

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True)
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        
        # Création du fil
        thread_name = f"{self.goal.value[:70]} - {interaction.user.display_name}"
        thread = await list_chan.create_thread(name=thread_name, type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)

        # Envoi de l'annonce (on récupère l'ID pour le mapping)
        announcement = await list_chan.send(
            content=f"{role.mention if role else ''}\n📋 **MISSION : {self.category}**\n**Demandeur** : {interaction.user.display_name}\n**Objectif** : {self.goal.value}",
            view=MissionView(thread.id)
        )

        # Mapping immédiat
        data = load_data()
        data["active_missions"][str(thread.id)] = announcement.id
        save_data(data)

        # ENVOI DU BOUTON (On ne passe QUE l'ID de l'user pour éviter tout crash d'init)
        view_f = FinishView(interaction.user.id)
        await thread.send(
            content=f"⚔️ **Canal ouvert !**\n{interaction.user.mention}, clique ici une fois fini :",
            view=view_f
        )

# --- AUTRES VIEWS ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, custom_id="sav_v72")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"Coucou {i.user.mention}, explique ton problème ici. <@{MY_USER_ID}> t'aidera bientôt.")
        await i.response.defer()

class VocalView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Nommer le salon", emoji="📝", style=discord.ButtonStyle.primary, custom_id="voc_name")
    async def rename(self, interaction, button):
        if interaction.user.voice and interaction.user.voice.channel.id in temp_vocal_channels:
            modal = discord.ui.Modal(title="Renommer ton salon")
            name_input = discord.ui.TextInput(label="Nouveau nom", placeholder="Ex: Donjon Korri", min_length=2, max_length=20)
            modal.add_item(name_input)
            async def on_modal_submit(int_modal):
                await interaction.user.voice.channel.edit(name=f"🔊 {name_input.value}")
                await int_modal.response.defer()
            modal.on_submit = on_modal_submit
            await interaction.response.send_modal(modal)
        else: await interaction.response.send_message("Tu dois être dans TON salon vocal !", ephemeral=True)

    @discord.ui.button(label="Limiter les places", emoji="👥", style=discord.ButtonStyle.secondary, custom_id="voc_limit")
    async def limit(self, interaction, button):
        if interaction.user.voice and interaction.user.voice.channel.id in temp_vocal_channels:
            modal = discord.ui.Modal(title="Limite de places")
            limit_input = discord.ui.TextInput(label="Nombre (0-99)", min_length=1, max_length=2)
            modal.add_item(limit_input)
            async def on_limit_submit(int_modal):
                try:
                    val = int(limit_input.value)
                    await interaction.user.voice.channel.edit(user_limit=val if val <= 99 else 99)
                    await int_modal.response.defer()
                except: await int_modal.response.send_message("Chiffre invalide !", ephemeral=True)
            modal.on_submit = on_limit_submit
            await interaction.response.send_modal(modal)
        else: await interaction.response.send_message("Tu dois être dans TON salon vocal !", ephemeral=True)

class CoopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Succès", emoji="🏆", style=discord.ButtonStyle.success, custom_id="c_s_v2")
    async def s(self, i, b): await i.response.send_modal(GoalModal("Succès", "Ex: Koutoulou Hardi"))
    @discord.ui.button(label="Quête", emoji="📜", style=discord.ButtonStyle.success, custom_id="c_q_v2")
    async def q(self, i, b): await i.response.send_modal(GoalModal("Quête", "Ex: Les sept mercemers"))
    @discord.ui.button(label="Craft/FM", emoji="🛠️", style=discord.ButtonStyle.primary, custom_id="c_c_v2")
    async def c(self, i, b): await i.response.send_modal(GoalModal("Craft/FM", "Ex: Craft Voile d'Encre"))
    @discord.ui.button(label="Farming", emoji="🌾", style=discord.ButtonStyle.secondary, custom_id="c_f_v2")
    async def f(self, i, b): await i.response.send_modal(GoalModal("Farming", "Ex: Donjon Korri en boucle"))

# --- COMMANDES ---
@bot.command()
async def update(ctx, module=None):
    if not ctx.author.guild_permissions.administrator: return

    # Si module est None ou "all", on fait tout. Sinon, juste le module demandé.
    to_update = ["voc", "sav", "aide", "notif"] if module in [None, "all"] else [module]

    for m in to_update:
        if m == "voc":
            c = bot.get_channel(ID_SALON_CONFIG)
            if c: 
                await c.purge(limit=10)
                await c.send("🎙️ **Gestion de ton salon vocal**\nUtilise les boutons ci-dessous.", view=VocalView())
        
        elif m == "sav":
            c = bot.get_channel(ID_SALON_SAV)
            if c:
                await c.purge(limit=5)
                await c.send("👋 **Besoin d'aide ?**\nOuvre un ticket ici.", view=SAVView())
        
        elif m == "aide":
            c = bot.get_channel(ID_SALON_DEMANDE_AIDE)
            if c:
                await c.purge(limit=5)
                await c.send("🤝 **Entraide de Guilde**\nClique sur un bouton pour demander de l'aide !", view=CoopView())
        
        elif m == "notif":
            c = bot.get_channel(ID_SALON_NOTIFICATIONS)
            if c:
                await c.purge(limit=10)
                msg = await c.send("🔔 **Notifications**\n📅 : **Almanax**\n⚔️ : **Entraide**\n📢 : **Annonces**")
                for emoji in ["📅", "⚔️", "📢"]: await msg.add_reaction(emoji)
                data = load_data()
                data["notif_msg_id"] = msg.id
                save_data(data)

    await ctx.send(f"✅ Mise à jour terminée pour : {', '.join(to_update)}")
    
@bot.event
async def on_ready():
    print(f"🛡️ Watcher v7.2 opérationnel")
    # ENREGISTREMENT DE TOUTES LES VUES POUR LA PERSISTANCE
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(VocalView())
    bot.add_view(MissionView()) # ESSENTIEL
    bot.add_view(FinishView())  # ESSENTIEL
    if not almanax_loop.is_running(): almanax_loop.start()
@bot.command()
async def force_almanax(ctx):
    if not ctx.author.guild_permissions.administrator: return
    
    await ctx.send("🔍 Récupération de l'Almanax en cours...")
    embed = await get_almanax_embed()
    
    if embed:
        channel = bot.get_channel(ID_SALON_ALMANAX)
        if channel:
            await channel.send(content=f"<@&{ROLE_ALMANAX}>", embed=embed)
            await ctx.send("✅ Almanax posté avec succès.")
    else:
        await ctx.send("❌ Erreur : Impossible de joindre l'API DofusDuDe.")

bot.run(os.environ.get('DISCORD_TOKEN'))
