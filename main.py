import discord
from discord.ext import commands, tasks
import os
import json
import requests
import asyncio
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION (Tes IDs) ---
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

# --- ALMANAX (BOUCLE AUTO) ---
async def post_almanax():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel: return
    url = f"https://api.dofusdu.de/dofus2/fr/almanax/{datetime.now(PARIS_TZ).strftime('%Y-%m-%d')}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json()
            embed = discord.Embed(title=f"📅 ALMANAX : {d['boss']['name'].upper()}", color=0xE67E22)
            embed.set_thumbnail(url=d['tribute']['item']['image_urls']['icon'])
            embed.add_field(name="✨ Bonus", value=d['bonus']['description'], inline=False)
            embed.add_field(name="🙏 Offrande", value=f"**{d['tribute']['quantity']}x {d['tribute']['item']['name']}**", inline=False)
            role = channel.guild.get_role(ROLE_ALMANAX)
            await channel.send(content=f"{role.mention if role else ''}", embed=embed)
    except Exception as e:
        print(f"Erreur Almanax: {e}")

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop(): await post_almanax()

# --- VOCAUX TEMPORAIRES ---
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

# --- RÉACTIONS NOTIFICATIONS ---
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

# --- ENTRAIDE & MISSIONS ---
class MissionView(discord.ui.View):
    def __init__(self, thread_id):
        super().__init__(timeout=None)
        self.thread_id = thread_id

    @discord.ui.button(label="Je suis dispo pour aider !", emoji="⚔️", style=discord.ButtonStyle.success, custom_id="join_v74")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. On récupère le fil privé grâce à l'ID qu'on a stocké
        thread = bot.get_channel(self.thread_id)
        
        if thread:
            # 2. On ajoute l'aidant au fil privé
            await thread.add_user(interaction.user)
            
            # 3. On envoie un petit message de bienvenue DANS LE FIL (pas dans le salon public)
            await thread.send(f"🛡️ **{interaction.user.display_name}** vient de rejoindre l'escouade !")
            
            # 4. On confirme à l'aidant que c'est bon (en message privé/éphémère)
            await interaction.response.send_message(f"✅ Super ! Tu as été ajouté au fil privé : <#{self.thread_id}>", ephemeral=True)
        else:
            # Si le fil a été supprimé entre temps
            await interaction.response.send_message("❌ Cette mission n'existe plus ou a été terminée.", ephemeral=True)
            
class FinishView(discord.ui.View):
    def __init__(self, thread_id, announcement_id, list_chan_id, creator_id):
        # On enlève le timeout pour que le bouton ne périme jamais
        super().__init__(timeout=None)
        self.thread_id = thread_id
        self.announcement_id = announcement_id
        self.list_chan_id = list_chan_id
        self.creator_id = creator_id

    # On donne un ID unique au bouton qui contient l'ID du créateur pour vérifier
    @discord.ui.button(label="Mission terminée !", style=discord.ButtonStyle.danger, custom_id="persistent_finish_btn")
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        # On vérifie que c'est bien le créateur qui clique
        if interaction.user.id == self.creator_id:
            list_chan = bot.get_channel(self.list_chan_id)
            
            # 1. Suppression de l'annonce
            try:
                msg = await list_chan.fetch_message(self.announcement_id)
                await msg.delete()
            except: 
                print("Annonce déjà supprimée ou introuvable.")
            
            # 2. Nettoyage JSON
            data = load_data()
            if str(self.thread_id) in data["active_missions"]:
                del data["active_missions"][str(self.thread_id)]
            save_data(data)
            
            # 3. Message de fin et suppression du fil
            await interaction.response.send_message("✅ Mission close, suppression du canal...")
            await asyncio.sleep(2)
            await interaction.channel.delete()
        else:
            await interaction.response.send_message("❌ Seul le demandeur peut clore la mission.", ephemeral=True)
            
class GoalModal(discord.ui.Modal):
    def __init__(self, category, placeholder):
        super().__init__(title=f"Demande : {category}")
        self.category = category
        self.goal = discord.ui.TextInput(label="Cible", placeholder=placeholder, style=discord.TextStyle.paragraph)
        self.add_item(self.goal)

    async def on_submit(self, interaction):
        # 1. Travail en silence
        await interaction.response.defer(ephemeral=True)
        
        list_chan = bot.get_channel(ID_SALON_LISTE_DEMANDES)
        role = interaction.guild.get_role(ROLE_ENTRAIDE)
        
        # 2. Nom du fil : "Objectif - Pseudo"
        thread_name = f"{self.goal.value[:80]} - {interaction.user.display_name}"
        
        # 3. Création du fil privé et ajout du demandeur
        thread = await list_chan.create_thread(name=thread_name, type=discord.ChannelType.private_thread)
        await thread.add_user(interaction.user)

        # 4. Envoi de l'annonce publique dans #liste-demande-en-cours
        announcement = await list_chan.send(
            content=f"{role.mention if role else ''}\n📋 **MISSION : {self.category}**\n**Demandeur** : {interaction.user.display_name}\n**Objectif** : {self.goal.value}",
            view=MissionView(thread.id)
        )

        # 5. MAPPING : On lie l'ID du fil à l'ID de l'annonce dans le JSON
        data = load_data()
        data["active_missions"][str(thread.id)] = announcement.id
        save_data(data)

        # 6. ENVOI DU BOUTON ROUGE (Via la classe FinishView)
        # On passe toutes les infos nécessaires pour que le bouton sache quoi supprimer
        view_f = FinishView(thread.id, announcement.id, list_chan.id, interaction.user.id)
        
        await thread.send(
            content=f"⚔️ **Canal d'entraide ouvert !**\n\n{interaction.user.mention}, tes alliés apparaîtront ici au fur et à mesure.\nClique sur le bouton ci-dessous pour déclarer la mission comme **terminée** :",
            view=view_f
        )

# --- VIEWS PERSISTANTES ---
class SAVView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.danger, custom_id="sav_v72")
    async def cb(self, i, b):
        t = await i.channel.create_thread(name=f"SAV-{i.user.display_name}", type=discord.ChannelType.private_thread)
        await t.send(f"Coucou {i.user.mention}, explique moi ton problème ici, met un max d'infos, des screens si possible, et <@{MY_USER_ID}> se penchera dessus au plus vite !")
        await i.response.defer()
        
class VocalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Nommer le salon", emoji="📝", style=discord.ButtonStyle.primary, custom_id="voc_name")
    async def rename(self, interaction, button):
        # Vérification : l'utilisateur est-il dans un salon créé par le bot ?
        if interaction.user.voice and interaction.user.voice.channel.id in temp_vocal_channels:
            
            # On crée la petite fenêtre (Modal) pour taper le nom
            modal = discord.ui.Modal(title="Renommer ton salon")
            name_input = discord.ui.TextInput(label="Nouveau nom", placeholder="Ex: Donjon Korri", min_length=2, max_length=20)
            modal.add_item(name_input)

            # Ce qui se passe quand on valide le nom
            async def on_modal_submit(int_modal):
                await interaction.user.voice.channel.edit(name=f"🔊 {name_input.value}")
                await int_modal.response.defer() # Ferme la fenêtre sans message d'erreur

            modal.on_submit = on_modal_submit
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Tu dois être dans TON salon vocal !", ephemeral=True)

    @discord.ui.button(label="Limiter les places", emoji="👥", style=discord.ButtonStyle.secondary, custom_id="voc_limit")
    async def limit(self, interaction, button):
        if interaction.user.voice and interaction.user.voice.channel.id in temp_vocal_channels:
            
            modal = discord.ui.Modal(title="Limite de places")
            limit_input = discord.ui.TextInput(label="Nombre (0 pour illimité)", placeholder="Entre un chiffre entre 0 et 99", min_length=1, max_length=2)
            modal.add_item(limit_input)

            async def on_limit_submit(int_modal):
                try:
                    val = int(limit_input.value)
                    await interaction.user.voice.channel.edit(user_limit=val if val <= 99 else 99)
                    await int_modal.response.defer()
                except:
                    await int_modal.response.send_message("Mets un chiffre valide !", ephemeral=True)

            modal.on_submit = on_limit_submit
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Tu dois être dans TON salon vocal !", ephemeral=True)
            
class CoopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Succès", emoji="🏆", style=discord.ButtonStyle.success, custom_id="c_s_v2")
    async def s(self, i, b):
        await i.response.send_modal(GoalModal("Succès", "Ex: Koutoulou Hardi, Vortex Focus"))

    @discord.ui.button(label="Quête", emoji="📜", style=discord.ButtonStyle.success, custom_id="c_q_v2")
    async def q(self, i, b):
        await i.response.send_modal(GoalModal("Quête", "Ex: Les sept mercemers, Oiseau du temps"))

    @discord.ui.button(label="Craft/FM", emoji="🛠️", style=discord.ButtonStyle.primary, custom_id="c_c_v2")
    async def c(self, i, b):
        await i.response.send_modal(GoalModal("Craft/FM", "Ex: Craft Voile d'Encre / FM Dagues Erhy"))

    @discord.ui.button(label="Farming", emoji="🌾", style=discord.ButtonStyle.secondary, custom_id="c_f_v2")
    async def f(self, i, b):
        await i.response.send_modal(GoalModal("Farming", "Ex: Donjon Korriandre en boucle"))

# --- COMMANDES ---
@bot.command()
async def update(ctx, module=None):
    if not ctx.author.guild_permissions.administrator: return

    # Si tu tapes "!update voc"
    if module == "voc":
        vocal_chan = bot.get_channel(ID_SALON_CONFIG)
        if vocal_chan:
            await vocal_chan.purge(limit=10)
            await vocal_chan.send("🎙️ **Gestion de ton salon vocal**\nUtilise les boutons ci-dessous.", view=VocalView())
            await ctx.send("✅ Module Vocal mis à jour.")

    # Si tu tapes "!update sav"
    elif module == "sav":
        sav_chan = bot.get_channel(ID_SALON_SAV)
        if sav_chan:
            await sav_chan.purge(limit=5)
            await sav_chan.send("👋 **Besoin d'aide ?**\nOuvre un ticket ici.", view=SAVView())
            await ctx.send("✅ Module SAV mis à jour.")

    # Si tu tapes "!update aide"
    elif module == "aide":
        aide_chan = bot.get_channel(ID_SALON_DEMANDE_AIDE)
        if aide_chan:
            await aide_chan.purge(limit=5)
            await aide_chan.send("🤝 **Entraide de Guilde**\nClique sur un bouton pour demander de l'aide à la guilde !", view=CoopView())
            await ctx.send("✅ Module Entraide (Formulaires) mis à jour.")
    
    # Si tu tapes "!update notif"
    elif module == "notif":
        notif_chan = bot.get_channel(ID_SALON_NOTIFICATIONS)
        if notif_chan:
            await notif_chan.purge(limit=10)
            msg = await notif_chan.send("🔔 **Notifications**\n📅 : **Almanax**\n⚔️ : **Entraide**\n📢 : **Annonces**")
            for emoji in ["📅", "⚔️", "📢"]: await msg.add_reaction(emoji)
            data = load_data()
            data["notif_msg_id"] = msg.id
            save_data(data)
            await ctx.send("✅ Module Notifications mis à jour.")

    # Si tu tapes juste "!update" sans rien, il te demande quoi faire
    else:
        await ctx.send("❓ Précise le module : `!update voc`, `!update sav`, `!update notif` ou `!update aide`.")

@bot.command()
async def force_almanax(ctx):
    if ctx.author.id == MY_USER_ID:
        await post_almanax()
        await ctx.send("⚙️ Almanax envoyé.")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher v7.2 opérationnel")
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(VocalView())
    if not almanax_loop.is_running(): almanax_loop.start()

bot.run(os.environ.get('DISCORD_TOKEN'))
