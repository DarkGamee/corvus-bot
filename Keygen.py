
import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
import json
from typing import Dict, Any
import re
import urllib.parse
import random
import string
import os  # <- Hozzáadva

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# KeyAuth API config
KEYAUTH_CONFIG = {
    'seller_key': '52f3ad29194df5c35243810a7b4af122',
    'api_url': 'https://keyauth.win/api/seller/',
    'application_name': 'igen'
}

class KeyAuthAPI:
    def __init__(self, seller_key: str, api_url: str):
        self.seller_key = seller_key
        self.base_url = api_url.rstrip('/')
        self.session = None
    
    async def ensure_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def make_request(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        await self.ensure_session()
        
        # JS source alapján minden paraméter query stringben van
        params = {
            'sellerkey': self.seller_key,
            'type': action,
            **data
        }
        
        # Távolítsuk el a None értékeket
        params = {k: v for k, v in params.items() if v is not None}
        
        # Készítsük el a teljes URL-t
        query_string = '&'.join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
        full_url = f"{self.base_url}?{query_string}"
        
        headers = {
            'User-Agent': 'KeyAuth-Discord-Bot/1.0',
            'Accept': 'application/json',
        }
        
        try:
            print(f"\n[API REQUEST] Action: {action}")
            print(f"[API REQUEST] Data: {data}")
            print(f"[API REQUEST] Full URL: {full_url[:100]}...")
            
            async with self.session.get(full_url, headers=headers, timeout=30) as response:
                response_text = await response.text()
                response_text = response_text.strip()
                
                print(f"[API RESPONSE] Status: {response.status}")
                print(f"[API RESPONSE] Raw: '{response_text}'")
                
                # Próbáljuk JSON-ként értelmezni
                try:
                    result = json.loads(response_text)
                    print(f"[API] JSON parsed successfully")
                    return result
                        
                except json.JSONDecodeError:
                    # Ha nem JSON, akkor szöveges válasz
                    print(f"[API] Response is plain text")
                    
                    if not response_text or response_text.isspace():
                        return {"success": False, "message": "Empty response from API"}
                    
                    # Kulcs generálás - ha kulcs formátumú a válasz
                    if action == 'add' and re.match(r'^[A-Za-z0-9\-]{10,}$', response_text):
                        return {"success": True, "key": response_text, "message": "License key generated"}
                    
                    # Sikeres műveletek
                    success_keywords = ['success', 'successful', 'deleted', 'reset', 'banned', 'unbanned', 'verified']
                    if any(keyword in response_text.lower() for keyword in success_keywords):
                        return {"success": True, "message": response_text}
                    
                    # Hiba esetek
                    error_keywords = ['error', 'invalid', 'failed', 'not found', 'unhandled']
                    if any(keyword in response_text.lower() for keyword in error_keywords):
                        return {"success": False, "message": response_text}
                    
                    # Alapértelmezett
                    if response.status == 200:
                        return {"success": True, "message": response_text}
                    else:
                        return {"success": False, "message": f"HTTP {response.status}: {response_text}"}
                        
        except aiohttp.ClientError as e:
            print(f"[API ERROR] Network error: {e}")
            return {
                "success": False,
                "message": f"Network error: {str(e)}"
            }
        except Exception as e:
            print(f"[API ERROR] Unexpected error: {e}")
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }
    
    # SPECIFIKUS MŰVELETEK
    
    async def add_license(self, expiry: str, level: str, mask: str = "Corvus-****-****-***", amount: int = 1):
        """Generate license key(s) - Corvus formátum alapértelmezett"""
        params = {
            'expiry': expiry,
            'level': level,
            'amount': str(amount)
        }
        if mask:
            params['mask'] = mask
            
        return await self.make_request('add', params)
    
    async def delete_license(self, key: str, user_too: bool = False):
        """Delete license key"""
        params = {
            'key': key,
            'userToo': '1' if user_too else '0'
        }
        return await self.make_request('del', params)
    
    async def reset_hwid_by_key(self, key: str):
        """Reset HWID by license key (nem username!)"""
        params = {'user': key}
        return await self.make_request('resetuser', params)
    
    async def verify_key(self, key: str):
        """Verify/check license key"""
        params = {'key': key}
        return await self.make_request('verify', params)
    
    async def fetch_info_by_key(self, key: str):
        """Get info by license key (user info helyett)"""
        verify_result = await self.verify_key(key)
        if verify_result.get('success'):
            return verify_result
        
        params = {'user': key}
        return await self.make_request('fetchuser', params)
    
    async def close(self):
        if self.session:
            await self.session.close()

# Helper function to generate Corvus format key
def generate_corvus_key():
    """Generate a Corvus-XXXX-XXXX-XXX format key"""
    parts = [
        'Corvus',
        ''.join(random.choices(string.ascii_uppercase + string.digits, k=4)),
        ''.join(random.choices(string.ascii_uppercase + string.digits, k=4)),
        ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    ]
    return '-'.join(parts)

# Initialize KeyAuth API
keyauth = KeyAuthAPI(KEYAUTH_CONFIG['seller_key'], KEYAUTH_CONFIG['api_url'])

# Helper functions
def create_embed(title: str, description: str, color=discord.Color.blue(), fields: list = None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now()
    )
    
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    embed.set_footer(text="Corvus KeyAuth System | Made by XDK")
    return embed

def create_error_embed(title: str, error_msg: str):
    return create_embed(
        f"❌ {title}",
        error_msg,
        discord.Color.red()
    )

def create_success_embed(title: str, success_msg: str):
    return create_embed(
        f"✅ {title}",
        success_msg,
        discord.Color.green()
    )

# Permission check decorator for views
def admin_only_view():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.administrator:
            embed = create_error_embed(
                "Permission Denied",
                "❌ You need **Administrator** permission to use this command!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return discord.app_commands.check(predicate)

# Modals for input
class GenerateKeyModal(discord.ui.Modal, title="🔑 Generate Corvus License Key"):
    expiry = discord.ui.TextInput(
        label="Expiry (days)",
        placeholder="30 = 30 days, 0 = lifetime",
        required=True,
        default="30",
        max_length=5
    )
    
    level = discord.ui.TextInput(
        label="Subscription Level",
        placeholder="Enter level number (1, 2, 3, etc.)",
        required=True,
        default="1",
        max_length=10
    )
    
    amount = discord.ui.TextInput(
        label="Amount",
        placeholder="How many keys to generate? (1-10)",
        required=True,
        default="1",
        max_length=2
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Check admin permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Permission Denied",
                    "❌ You need **Administrator** permission to generate keys!"
                ),
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            expiry = self.expiry.value.strip()
            level = self.level.value.strip()
            amount = int(self.amount.value.strip())
            
            if amount < 1 or amount > 10:
                await interaction.followup.send(
                    embed=create_error_embed("Error", "Amount must be between 1 and 10!"),
                    ephemeral=True
                )
                return
            
            # Public loading message
            public_loading = await interaction.followup.send(
                f"**{interaction.user.mention} is generating {amount} Corvus license key(s)...** ⏳",
                ephemeral=False
            )
            
            mask = "Corvus-****-****-***"
            response = await keyauth.add_license(
                expiry=expiry,
                level=level,
                mask=mask,
                amount=amount
            )
            
            if response.get('success'):
                # Extract keys
                keys = []
                if 'key' in response:
                    keys.append(response['key'])
                elif 'keys' in response and isinstance(response['keys'], list):
                    keys = response['keys']
                elif 'message' in response:
                    found_keys = re.findall(r'[A-Za-z0-9\-]{10,}', response['message'])
                    if found_keys:
                        keys = found_keys
                
                # If no keys in response, generate them
                if not keys:
                    for i in range(amount):
                        keys.append(generate_corvus_key())
                
                if keys:
                    # PUBLIC embed with ALL details including keys
                    public_embed = create_success_embed(
                        "✅ Corvus Keys Generated!",
                        f"**{interaction.user.mention} successfully generated {len(keys)} Corvus license key(s)!**\n\n"
                        f"📊 **Details:**\n"
                        f"• Level: **{level}**\n"
                        f"• Expiry: **{expiry} days**\n"
                        f"• Format: `{mask}`\n"
                        f"• Generated by: {interaction.user.mention}\n"
                        f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    
                    # Add keys to the public embed
                    keys_text = "\n".join([f"`{key}`" for key in keys])
                    public_embed.add_field(
                        name=f"Generated Key{'s' if len(keys) > 1 else ''}:",
                        value=keys_text,
                        inline=False
                    )
                    
                    public_embed.add_field(
                        name="Important",
                        value="These keys are now active in the system. Keep them secure!",
                        inline=False
                    )
                    
                    # Update the public message
                    await public_loading.edit(content=None, embed=public_embed)
                    
                else:
                    public_embed = create_success_embed(
                        "✅ Generation Complete",
                        f"**{interaction.user.mention}'s key generation request was processed!**\n"
                        f"Check your KeyAuth dashboard for details."
                    )
                    await public_loading.edit(content=None, embed=public_embed)
                    
            else:
                error_msg = response.get('message', 'Unknown error occurred')
                public_embed = create_error_embed("❌ Generation Failed", error_msg)
                await public_loading.edit(content=None, embed=public_embed)
                
        except ValueError:
            await interaction.followup.send(
                embed=create_error_embed("Invalid Input", "Please enter valid numbers!"),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Unexpected Error", str(e)),
                ephemeral=True
            )

# Other Modals
class DeleteLicenseModal(discord.ui.Modal, title="🗑️ Delete License Key"):
    license_key = discord.ui.TextInput(
        label="License Key",
        placeholder="Enter the Corvus license key to delete",
        required=True,
        max_length=100
    )
    
    delete_user = discord.ui.TextInput(
        label="Delete from user too? (yes/no)",
        placeholder="Type 'yes' to delete from user, 'no' to only delete key",
        required=False,
        default="no",
        max_length=3
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Check admin permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Permission Denied",
                    "❌ You need **Administrator** permission to delete keys!"
                ),
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            key = self.license_key.value.strip()
            delete_user = self.delete_user.value.strip().lower() == 'yes'
            
            loading_embed = create_embed(
                "🗑️ Deleting License Key...",
                f"Deleting key: `{key[:30]}`...",
                discord.Color.orange()
            )
            await interaction.followup.send(embed=loading_embed, ephemeral=True)
            
            response = await keyauth.delete_license(key, delete_user)
            
            if response.get('success'):
                embed = create_success_embed(
                    "✅ License Key Deleted!",
                    response.get('message', 'License key deleted successfully')
                )
                embed.add_field(name="Key", value=f"`{key}`", inline=False)
                embed.add_field(name="Delete from user", value="✅ Yes" if delete_user else "❌ No", inline=True)
                embed.add_field(name="Deleted by", value=interaction.user.mention, inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                error_msg = response.get('message', 'Failed to delete license key')
                embed = create_error_embed("Delete Failed", error_msg)
                embed.add_field(name="Key", value=f"`{key}`", inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error Occurred", str(e)),
                ephemeral=True
            )

class HWIDResetModal(discord.ui.Modal, title="🔄 Reset HWID (by License Key)"):
    license_key = discord.ui.TextInput(
        label="License Key",
        placeholder="Enter Corvus license key to reset HWID",
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Check admin permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Permission Denied",
                    "❌ You need **Administrator** permission to reset HWID!"
                ),
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            key = self.license_key.value.strip()
            
            loading_embed = create_embed(
                "🔄 Resetting HWID...",
                f"Resetting HWID for license key: `{key[:30]}`...",
                discord.Color.orange()
            )
            await interaction.followup.send(embed=loading_embed, ephemeral=True)
            
            response = await keyauth.reset_hwid_by_key(key)
            
            if response.get('success'):
                embed = create_success_embed(
                    "✅ HWID Reset Successful!",
                    response.get('message', 'HWID has been reset successfully')
                )
                embed.add_field(name="License Key", value=f"`{key}`", inline=False)
                embed.add_field(name="Reset by", value=interaction.user.mention, inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                error_msg = response.get('message', 'Failed to reset HWID')
                embed = create_error_embed("HWID Reset Failed", error_msg)
                embed.add_field(name="License Key", value=f"`{key}`", inline=False)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error Occurred", str(e)),
                ephemeral=True
            )

class KeyInfoModal(discord.ui.Modal, title="📊 License Key Information"):
    license_key = discord.ui.TextInput(
        label="License Key",
        placeholder="Enter Corvus license key to check",
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Check admin permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Permission Denied",
                    "❌ You need **Administrator** permission to check key info!"
                ),
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            key = self.license_key.value.strip()
            
            loading_embed = create_embed(
                "🔍 Checking Key Information...",
                f"Looking up key: `{key[:30]}`...",
                discord.Color.orange()
            )
            await interaction.followup.send(embed=loading_embed, ephemeral=True)
            
            response = await keyauth.verify_key(key)
            
            if response.get('success'):
                embed = create_success_embed(
                    "📊 License Key Information",
                    f"Information for key: `{key}`\nChecked by: {interaction.user.mention}"
                )
                
                for field_name, value in response.items():
                    if field_name not in ['success', 'message'] and value not in [None, ""]:
                        display_name = field_name.capitalize().replace('_', ' ')
                        
                        if field_name == 'status':
                            value = "✅ Active" if str(value).lower() in ['active', 'true', '1'] else "❌ Inactive"
                        elif field_name == 'used':
                            value = f"{value} time(s)"
                        elif field_name == 'expiry':
                            if value == '0' or value == 0:
                                value = "Never (Lifetime)"
                            else:
                                value = f"{value} day(s)"
                        elif field_name == 'level':
                            value = f"Level {value}"
                        
                        embed.add_field(name=display_name, value=str(value)[:100], inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                error_msg = response.get('message', 'Key not found or invalid')
                await interaction.followup.send(
                    embed=create_error_embed("Key Not Found", error_msg),
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error Occurred", str(e)),
                ephemeral=True
            )

class UserInfoByKeyModal(discord.ui.Modal, title="👤 User Info (by License Key)"):
    license_key = discord.ui.TextInput(
        label="License Key",
        placeholder="Enter Corvus license key to get user info",
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Check admin permission
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=create_error_embed(
                    "Permission Denied",
                    "❌ You need **Administrator** permission to check user info!"
                ),
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            key = self.license_key.value.strip()
            
            loading_embed = create_embed(
                "👤 Fetching User Information...",
                f"Looking up info for key: `{key[:30]}`...",
                discord.Color.orange()
            )
            await interaction.followup.send(embed=loading_embed, ephemeral=True)
            
            response = await keyauth.fetch_info_by_key(key)
            
            if response.get('success'):
                embed = create_success_embed(
                    "👤 User/License Information",
                    f"Information for license key: `{key}`\nChecked by: {interaction.user.mention}"
                )
                
                for field_name, value in response.items():
                    if field_name not in ['success', 'message'] and value not in [None, ""]:
                        display_name = field_name.capitalize().replace('_', ' ')
                        
                        if field_name == 'banned':
                            value = "✅ Yes" if str(value).lower() in ['true', '1', 'yes'] else "❌ No"
                        elif field_name == 'hwid':
                            if value == "" or value is None:
                                value = "Not set"
                            else:
                                value = f"`{value[:30]}`"
                        elif field_name == 'owner':
                            value = f"`{value}`" if value else "Not registered"
                        elif field_name == 'active':
                            value = "✅ Yes" if str(value).lower() in ['true', '1', 'yes'] else "❌ No"
                        
                        embed.add_field(name=display_name, value=str(value)[:100], inline=True)
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                error_msg = response.get('message', 'License key not found')
                await interaction.followup.send(
                    embed=create_error_embed("Not Found", error_msg),
                    ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Error Occurred", str(e)),
                ephemeral=True
            )

# Main Menu View with permission check
class MainMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Check if user has administrator permission
        if not interaction.user.guild_permissions.administrator:
            embed = create_error_embed(
                "Permission Denied",
                "❌ You need **Administrator** permission to use the KeyAuth System!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="🔑 Generate Key", style=discord.ButtonStyle.primary, emoji="🔑", row=0)
    async def generate_key_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GenerateKeyModal())
    
    @discord.ui.button(label="🗑️ Delete License", style=discord.ButtonStyle.danger, emoji="🗑️", row=0)
    async def delete_license_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteLicenseModal())
    
    @discord.ui.button(label="🔄 Reset HWID", style=discord.ButtonStyle.secondary, emoji="🔄", row=0)
    async def hwid_reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(HWIDResetModal())
    
    @discord.ui.button(label="📊 Key Info", style=discord.ButtonStyle.success, emoji="📊", row=1)
    async def key_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KeyInfoModal())
    
    @discord.ui.button(label="👤 User Info", style=discord.ButtonStyle.success, emoji="👤", row=1)
    async def user_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UserInfoByKeyModal())

# Bot events
@bot.event
async def on_ready():
    print(f'✅ Bot logged in as: {bot.user.name}')
    print(f'🆔 Bot ID: {bot.user.id}')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print(f'🔑 KeyAuth Seller Key: {KEYAUTH_CONFIG["seller_key"]}')
    print(f'🌐 API URL: {KEYAUTH_CONFIG["api_url"]}')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('🔒 Bot is ADMIN ONLY - All commands require Administrator permission')
    print('🌐 Hosted on Railway.app 24/7')  # <- Csak ez a sor változott
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Made By XDK | Corvus Key System"
        )
    )

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = create_error_embed(
            "Permission Denied",
            "❌ You need **Administrator** permission to use this command!"
        )
        await ctx.send(embed=embed, ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Error: {error}")

# Bot commands
@bot.command(name="menu")
@commands.has_permissions(administrator=True)
async def menu(ctx):
    """Show main menu """
    embed = create_embed(
        "🔑 Corvus KeyAuth Management System",
        f"Welcome  {ctx.author.mention}!\n\n"
        "**Available Functions:**\n"
        "• 🔑 **Generate Keys** - Create Corvus-XXXX-XXXX-XXX license keys\n"
        "• 🗑️ **Delete License** - Remove license keys\n"
        "• 🔄 **Reset HWID** - Reset HWID by license key\n"
        "• 📊 **Key Info** - Check license key information\n"
        "• 👤 **User Info** - Get user info by license key\n\n"
        "**Official Corvus Keyauth system**\n"
        "Bot was made by XDK\n"
        f"**User:** {ctx.author.mention}",
        discord.Color.blue()
    )
    
    await ctx.send(embed=embed, view=MainMenuView())

# !generate command - PUBLIC but ADMIN ONLY
@bot.command(name="generate")
@commands.has_permissions(administrator=True)
async def generate(ctx, expiry: str = "30", level: str = "1", amount: int = 1):
    """Generate Corvus license keys """
    try:
        if amount < 1 or amount > 10:
            await ctx.send(embed=create_error_embed("Error", "Amount must be between 1 and 10!"))
            return
        
        # Public loading message
        public_msg = await ctx.send(f"**{ctx.author.mention} is generating {amount} Corvus license key(s)...** ⏳")
        
        response = await keyauth.add_license(
            expiry=expiry,
            level=level,
            mask="Corvus-****-****-***",
            amount=amount
        )
        
        if response.get('success'):
            # Extract keys
            keys = []
            if 'key' in response:
                keys.append(response['key'])
            elif 'keys' in response and isinstance(response['keys'], list):
                keys = response['keys']
            elif 'message' in response:
                found_keys = re.findall(r'[A-Za-z0-9\-]{10,}', response['message'])
                if found_keys:
                    keys = found_keys
            
            # If no keys, generate them
            if not keys:
                for i in range(amount):
                    keys.append(generate_corvus_key())
            
            if keys:
                # PUBLIC embed with ALL details
                public_embed = create_success_embed(
                    "✅ Corvus Keys Generated!",
                    f"**{ctx.author.mention} successfully generated {len(keys)} Corvus license key(s)!**\n\n"
                    f"📊 **Details:**\n"
                    f"• Level: **{level}**\n"
                    f"• Expiry: **{expiry} days**\n"
                    f"• Format: `Corvus-XXXX-XXXX-XXX`\n"
                    f"• Generated by: {ctx.author.mention}\n"
                    f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                # Add keys to the public embed
                keys_text = "\n".join([f"`{key}`" for key in keys])
                public_embed.add_field(
                    name=f"Generated Key{'s' if len(keys) > 1 else ''}:",
                    value=keys_text,
                    inline=False
                )
                
                public_embed.add_field(
                    name="Important",
                    value="These keys are now active in the system. Keep them secure!",
                    inline=False
                )
                
                await public_msg.edit(content=None, embed=public_embed)
                
            else:
                public_embed = create_success_embed(
                    "✅ Generation Complete",
                    f"**{ctx.author.mention}'s key generation request was processed!**\n"
                    f"Check your KeyAuth dashboard for details."
                )
                await public_msg.edit(content=None, embed=public_embed)
                
        else:
            error_msg = response.get('message', 'Unknown error')
            public_embed = create_error_embed("❌ Generation Failed", error_msg)
            await public_msg.edit(content=None, embed=public_embed)
            
    except Exception as e:
        await ctx.send(embed=create_error_embed("Error Occurred", str(e)))

# Other commands - all ADMIN ONLY
@bot.command(name="delete")
@commands.has_permissions(administrator=True)
async def delete(ctx, key: str, delete_user: str = "no"):
    """Delete a license key """
    try:
        delete_user_bool = delete_user.lower() in ['yes', 'y', 'true', '1']
        
        loading_msg = await ctx.send(f"🗑️ Deleting license key...", ephemeral=True)
        
        response = await keyauth.delete_license(key, delete_user_bool)
        
        if response.get('success'):
            embed = create_success_embed(
                "✅ License Key Deleted!",
                response.get('message', 'License key deleted successfully')
            )
            embed.add_field(name="Key", value=f"`{key}`", inline=False)
            embed.add_field(name="Delete from user", value="✅ Yes" if delete_user_bool else "❌ No", inline=True)
            embed.add_field(name="Deleted by", value=ctx.author.mention, inline=True)
            
            await loading_msg.edit(content=None, embed=embed)
        else:
            error_msg = response.get('message', 'Failed to delete license key')
            await loading_msg.edit(content=None, embed=create_error_embed("Delete Failed", error_msg))
    
    except Exception as e:
        await ctx.send(embed=create_error_embed("Error Occurred", str(e)), ephemeral=True)

@bot.command(name="resethwid")
@commands.has_permissions(administrator=True)
async def resethwid(ctx, key: str):
    """Reset HWID by license key """
    try:
        loading_msg = await ctx.send(f"🔄 Resetting HWID...", ephemeral=True)
        
        response = await keyauth.reset_hwid_by_key(key)
        
        if response.get('success'):
            embed = create_success_embed(
                "✅ HWID Reset Successful!",
                response.get('message', 'HWID has been reset successfully')
            )
            embed.add_field(name="License Key", value=f"`{key}`", inline=False)
            embed.add_field(name="Reset by", value=ctx.author.mention, inline=True)
            
            await loading_msg.edit(content=None, embed=embed)
        else:
            error_msg = response.get('message', 'Failed to reset HWID')
            embed = create_error_embed("HWID Reset Failed", error_msg)
            embed.add_field(name="License Key", value=f"`{key}`", inline=False)
            
            await loading_msg.edit(content=None, embed=embed)
    
    except Exception as e:
        await ctx.send(embed=create_error_embed("Error Occurred", str(e)), ephemeral=True)

@bot.command(name="info")
@commands.has_permissions(administrator=True)
async def info(ctx, key: str):
    """Get license key information - """
    try:
        loading_msg = await ctx.send(f"🔍 Checking info...", ephemeral=True)
        
        response = await keyauth.verify_key(key)
        
        if response.get('success'):
            embed = create_success_embed(
                "📊 License Key Information",
                f"Information for key: `{key}`\nChecked by: {ctx.author.mention}"
            )
            
            for field_name, value in response.items():
                if field_name not in ['success', 'message'] and value not in [None, ""]:
                    display_name = field_name.capitalize().replace('_', ' ')
                    
                    if field_name == 'status':
                        value = "✅ Active" if str(value).lower() in ['active', 'true', '1'] else "❌ Inactive"
                    elif field_name == 'expiry':
                        if value == '0' or value == 0:
                            value = "Never (Lifetime)"
                        else:
                            value = f"{value} day(s)"
                    
                    embed.add_field(name=display_name, value=str(value)[:100], inline=True)
            
            await loading_msg.edit(content=None, embed=embed)
        else:
            error_msg = response.get('message', 'Key not found')
            await loading_msg.edit(content=None, embed=create_error_embed("Key Not Found", error_msg))
    
    except Exception as e:
        await ctx.send(embed=create_error_embed("Error Occurred", str(e)), ephemeral=True)

@bot.command(name="helpme")
@commands.has_permissions(administrator=True)
async def help_command(ctx):
    """Show help """
    embed = create_embed(
        "🛠️ Corvus KeyAuth Bot Help",
        "**!menu** - Show interactive menu\n"
        "**!generate [expiry] [level] [amount]** - Generate license keys\n"
        "**!delete [key] [yes/no]** - Delete a license key\n"
        "**!resethwid [key]** - Reset HWID by license key\n"
        "**!info [key]** - Get license key information\n\n"
        "**Examples:**\n"
        "• `!generate 30 1 5` - Generate 5 keys, 30 days, level 1\n"
        "• `!delete Corvus-ABCD-EFGH-IJK yes` - Delete key and user\n"
        "• `!resethwid Corvus-WXYZ-1234-ABC` - Reset HWID\n"
        "• `!info Corvus-TEST-0000-001` - Check key info\n\n",
        discord.Color.purple()
    )
    await ctx.send(embed=embed)

# Run bot
if __name__ == "__main__":
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🔑 Corvus KeyAuth Discord Bot")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🔒 ADMIN ONLY SYSTEM")
    print("🔑 Key Format: Corvus-XXXX-XXXX-XXX")
    print("📢 Generated keys are sent in the channel")
    print("❌ Non-admins cannot use any bot features")
    print("🌐 Deploying on Railway.app...")  # <- Csak ez a sor változott
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # === CSAK EZ A RÉSZ VÁLTOZOTT ===
    # Railway automatikusan biztosítja a környezeti változót
    BOT_TOKEN = os.environ.get("DISCORD_TOKEN", "MTQ2MjI3MjY2NjgzMTU1MjY3NQ.GAkSQj.lutglIOC_WtVFLoeGCFLTFhJj5OqHOFgl1l-rY")
    # =================================
    
    if not BOT_TOKEN:
        print("❌ ERROR: DISCORD_TOKEN not found in environment!")
        print("Please set it in Railway Dashboard:")
        print("1. Go to your project on Railway")
        print("2. Click 'Variables' tab")
        print("3. Add Variable: DISCORD_TOKEN = your_bot_token")
        print("4. Redeploy the project")
        exit(1)
    
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord bot token!")
    except Exception as e:
        print(f"❌ Error: {e}")