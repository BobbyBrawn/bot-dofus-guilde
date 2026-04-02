import discord
from discord.ext import commands, tasks
import os
import json
import requests
from datetime import datetime, time, timedelta, timezone

# --- CONFIGURATION (Vérifie une dernière fois ces IDs) ---
ID_SALON_ALMANAX = 1488953370667647076
ID_SALON_NOTIFICATIONS = 1489022043839140010
ID_SALON_CONFIG = 1488847369322745917
ID_SALON_SAV = 1488846991026032711
ID_SALON_DEMANDE_AIDE = 1488847060433375294

ROLE_ALMANAX = 1489021032965738636
ROLE_ENTRAIDE = 1489021136011530282
ROLE_ANNONCES = 1489021205011890410

MY_USER_ID = 270182770163187712
PARIS_TZ = timezone(timedelta(hours=2))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- BOUTONS NOTIFICATIONS ---
class NotifView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Almanax", emoji="📅", custom_id="btn_alm_51")
    async def b1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, ROLE_ALMANAX)

    @discord.ui.button(label="Entraide", emoji="⚔️", custom_id="btn_ent_51")
    async def b2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, ROLE_ENTRAIDE)

    @discord.ui.button(label="Annonces", emoji="📢", custom_id="btn_ann_51")
    async def b3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, ROLE_ANNONCES)

    async def toggle_role(self, interaction, role_id):
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message("Erreur : Rôle introuvable.", ephemeral=True)
        
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Role {role.name} retiré.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Role {role.name} ajouté !", ephemeral=True)

# --- FONCTION POST ALMANAX ---
async def post_almanax():
    chan = bot.get_channel(ID_SALON_ALMANAX)
    if not chan:
        print(f"DEBUG: Salon {ID_SALON_ALMANAX} introuvable.")
        return

    url = f"https://api.dofusdu.de/dofus2/fr/almanax/{datetime.now(PARIS_TZ).strftime('%Y-%m-%d')}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            embed = discord.Embed(title=f"📅 ALMANAX : {data['boss']['name'].upper()}", color=0xE67E22)
            embed.set_thumbnail(url=data['tribute']['item']['image_urls']['icon'])
            embed.add_field(name="✨ Bonus", value=data['bonus']['description'], inline=False)
            embed.add_field(name="🙏 Offrande", value=f"{data['tribute']['quantity']}x {data['tribute']['item']['name']}", inline=False)
            
            role = chan.guild.get_role(ROLE_ALMANAX)
            await chan.send(content=role.mention if role else "", embed=embed)
            print("DEBUG: Almanax envoyé avec succès.")
    except Exception as e:
        print(f"DEBUG: Erreur API Almanax : {e}")

@tasks.loop(time=time(hour=0, minute=1))
async def almanax_loop():
    await post_almanax()

# --- COMMANDES ---
@bot.command()
async def update(ctx):
    if not ctx.author.guild_permissions.administrator: return
    
    # Refresh Notifs
    notif_chan = bot.get_channel(ID_SALON_NOTIFICATIONS)
    if notif_chan:
        await notif_chan.purge(limit=10)
        await notif_chan.send("🔔 **Choisis tes rôles de notifications :**", view=NotifView())
    
    await ctx.send("✅ Système mis à jour. Teste les boutons maintenant.")

@bot.command()
async def force_almanax(ctx):
    if ctx.author.id == MY_USER_ID:
        print(f"DEBUG: Commande force_almanax lancée par {ctx.author}")
        await post_almanax()
        await ctx.send("⚙️ Tentative d'envoi lancée (check logs Railway si rien).")

# --- INITIALISATION ---
@bot.event
async def on_ready():
    print(f"🛡️ Watcher of Knights v5.1 en ligne")
    bot.add_view(NotifView())
    if not almanax_loop.is_running():
        almanax_loop.start()

# Important : permet aux commandes de marcher si on utilise aussi on_message
@bot.event
async def on_message(message):
    await bot.process_commands(message)

bot.run(os.environ.get('DISCORD_TOKEN'))
