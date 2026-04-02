import discord
from discord.ext import commands, tasks
import os
import json
import requests
from bs4 import BeautifulSoup
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
ID_SALON_ANNONCES = 1489302420684279938

ROLE_ALMANAX = 1489021032965738636
ROLE_ENTRAIDE = 1489021136011530282
ROLE_ANNONCES = 1489021205011890410

MY_USER_ID = 270182770163187712
PARIS_TZ = timezone(timedelta(hours=2))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- MÉMOIRE SÉCURISÉE (VOLUME RAILWAY) ---
DATA_DIR = "data"
DATA_PATH = os.path.join(DATA_DIR, "data.json")

def load_data():
    # On vérifie si le dossier 'data' existe dans /app/
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # Si le fichier n'existe pas encore sur le volume, on le crée
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH, "w") as f: 
            json.dump({
                "points": {}, 
                "notif_msg_id": 0, 
                "active_missions": {}, 
                "temp_vocaux": [] 
            }, f)
            
    with open(DATA_PATH, "r") as f: 
        return json.load(f)

def save_data(data):
    with open(DATA_PATH, "w") as f: 
        json.dump(data, f, indent=4)

# --- ALMANAX ---
import re

async def get_almanax_embed():
    url = "https://www.krosmoz.com/fr/almanax"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        bloc_dofus = soup.find("div", id="achievement_dofus")
        
        if not bloc_dofus: return None

        # --- 1. BONUS (Nettoyage et Gras) ---
        more_div = bloc_dofus.find("div", class_="more")
        for b_tag in more_div.find_all("b"):
            b_tag.replace_with(f"**{b_tag.text}**")
        bonus_complet = more_div.get_text(separator=" ").split("Quête")[0].strip()

        # --- 2. QUÊTE ET OFFRANDE ---
        more_infos = bloc_dofus.find("div", class_="more-infos")
        quete = more_infos.find("p").get_text().strip() if more_infos else "Quête"
        
        fleft = bloc_dofus.find("p", class_="fleft")
        offrande = fleft.get_text().strip() if fleft else "Offrande"

        # --- 3. RÉCUPÉRATION DE L'IMAGE VIA ID ---
        img_tag = bloc_dofus.find("div", class_="more-infos-content").find("img")
        item_id = "0"
        if img_tag:
            match = re.search(r'/(\d+)\.', img_tag["src"])
            if match: item_id = match.group(1)
        
        image_hd = f"https://api.dofusdb.fr/img/items/{item_id}.png"

        # --- CONSTRUCTION DE L'EMBED AÉRÉ ---
        embed = discord.Embed(
            title="📅  ALMANAX DU JOUR",
            color=0xF1C40F,
            description="\u200b" # Ligne vide sous le titre pour aérer
        )

        # On utilise des Fields pour créer des blocs distincts
        embed.add_field(
            name="✨  BONUS", 
            value=f"{bonus_complet}\n\u200b", # \n\u200b crée un vrai saut de ligne
            inline=False
        )

        embed.add_field(
            name="🙏  OFFRANDE", 
            value=f"**{quete}**\n{offrande}\n\u200b", 
            inline=False
        )

        # L'image HD en bas
        if item_id != "0":
            embed.set_image(url=image_hd)
            
        embed.set_footer(text="WatcherBot • Source : Krosmoz & DofusDB")
        
        return embed

    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None

@tasks.loop(time=time(hour=0, minute=1, tzinfo=PARIS_TZ))
async def almanax_loop():
    channel = bot.get_channel(ID_SALON_ALMANAX)
    if not channel: 
        print("❌ Salon Almanax introuvable.")
        return

    embed = await get_almanax_embed()
    if embed:
        await channel.send(content=f"<@&{ROLE_ALMANAX}>", embed=embed)
    else:
        print("❌ Impossible de générer l'embed Almanax.")

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
        # On acquitte l'appui sur le bouton immédiatement et de manière invisible
        await interaction.response.defer() 
        
        data = load_data()
        target_thread_id = None
        
        # On cherche quel fil est lié à ce message d'annonce via le JSON
        for tid, mid in data.get("active_missions", {}).items():
            if mid == interaction.message.id:
                target_thread_id = int(tid)
                break
        
        if target_thread_id:
            thread = bot.get_channel(target_thread_id)
            if thread:
                # On ajoute l'utilisateur au fil et on prévient l'équipe
                await thread.add_user(interaction.user)
                await thread.send(f"🛡️ **{interaction.user.display_name}** a rejoint l'escouade !")

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

async def check_notif_message():
    data = load_data()
    channel = bot.get_channel(ID_SALON_NOTIFICATIONS)
    if not channel: 
        print("❌ Salon Notifications introuvable.")
        return

    msg_id = data.get("notif_msg_id")
    msg = None

    if msg_id:
        try:
            # On tente de récupérer le message via son ID stocké dans le volume
            msg = await channel.fetch_message(msg_id)
        except:
            # Si le message a été supprimé ou n'existe pas, on reste à None
            msg = None

    # Si pas de message valide, on en crée un tout neuf
    if not msg:
        print("🔔 Message de notifications manquant ou expiré, création...")
        await channel.purge(limit=5)
        msg = await channel.send("🔔 **Choisis tes Notifications**\n\n📅 : **Almanax**\n⚔️ : **Entraide**\n📢 : **Annonces**\n\n*Réagis avec l'emoji correspondant pour obtenir le rôle.*")
        for emoji in ["📅", "⚔️", "📢"]: 
            await msg.add_reaction(emoji)
        
        # On met à jour l'ID dans le volume pour le prochain reboot
        data["notif_msg_id"] = msg.id
        save_data(data)
    else:
        print("🔔 Message de notifications détecté et opérationnel.")

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

@bot.command()
async def annonce(ctx, *, message=None):
    # Sécurité : Seul toi ou un admin peut utiliser cette commande
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ Tu n'as pas la permission de faire une annonce.")

    if not message:
        return await ctx.send("❓ Utilisation : `!annonce Ton texte ici`")

    channel = bot.get_channel(ID_SALON_ANNONCES)
    role_annonces = ctx.guild.get_role(ROLE_ANNONCES)

    if channel:
        # On construit l'annonce
        texte_final = f"{role_annonces.mention if role_annonces else ''}\n\n{message}"
        
        # Envoi dans le salon officiel
        await channel.send(texte_final)
        
        # Confirmation discrète pour toi
        await ctx.message.add_reaction("✅")
    else:
        await ctx.send("❌ Impossible de trouver le salon des annonces.")

@bot.event
async def on_ready():
    print(f"🛡️ Watcher v7.5 - Système de survie activé")
    
    # 1. On enregistre TOUTES les vues pour la persistance des boutons
    # C'est ce qui permet aux vieux boutons de répondre encore au clic
    bot.add_view(SAVView())
    bot.add_view(CoopView())
    bot.add_view(VocalView())
    bot.add_view(MissionView()) 
    bot.add_view(FinishView())  
    
    # 2. On lance la vérification automatique des notifications
    await check_notif_message()
    
    # 3. On lance la boucle Almanax
    if not almanax_loop.is_running(): 
        almanax_loop.start()
        
    print("✅ Tout est opérationnel et branché sur le Volume.")
    
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
        await ctx.send("❌ Erreur pour la récupération de l'almanax du jour")

bot.run(os.environ.get('DISCORD_TOKEN'))
