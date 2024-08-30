import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
from datetime import datetime
import os

DISCORD_API_KEY = os.getenv('DISCORD_API_KEY')

# Set up the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Connect to SQLite database
conn = sqlite3.connect('bank.db')
c = conn.cursor()

# Create tables if not exists
c.execute('''CREATE TABLE IF NOT EXISTS accounts (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL,
                created_at TEXT
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                date TEXT
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS pending_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                status TEXT,
                date TEXT
            )''')

conn.commit()

# Define Embed Colors
COLOR_SUCCESS = discord.Color.green()
COLOR_WARNING = discord.Color.orange()
COLOR_ERROR = discord.Color.red()
COLOR_INFO = discord.Color.from_rgb(255, 255, 255)  # White

### User Commands ###

# Send DM
async def send_dm(user: discord.User, title: str, description: str, color: discord.Color):
    try:
        embed = discord.Embed(title=title, description=description, color=color)
        await user.send(embed=embed)
    except discord.Forbidden:
        print(f"Could not send DM to {user}. They may have DMs disabled.")

# Register account
@bot.tree.command(name="register", description="Register a new bank account.")
async def register(interaction: discord.Interaction):
    user_id = interaction.user.id
    username = str(interaction.user)
    created_at = datetime.now().isoformat()

    c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    if c.fetchone():
        embed = discord.Embed(
            title="Registration Failed",
            description="You already have an account.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        c.execute("INSERT INTO accounts (user_id, username, balance, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, username, 0.0, created_at))
        conn.commit()

        embed = discord.Embed(
            title="Account Registered",
            description=f"Account successfully registered for {username}.",
            color=COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_dm(interaction.user, "Account Registered", "Your bank account has been successfully registered.", COLOR_SUCCESS)

# Request deposit
@bot.tree.command(name="deposit", description="Request to deposit an amount into your account.")
@app_commands.describe(amount="Amount to deposit")
async def deposit(interaction: discord.Interaction, amount: float):
    user_id = interaction.user.id
    if amount <= 0:
        embed = discord.Embed(
            title="Invalid Amount",
            description="Deposit amount must be a positive value.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    if c.fetchone():
        c.execute("INSERT INTO pending_requests (user_id, type, amount, status, date) VALUES (?, 'deposit', ?, 'pending', ?)",
                  (user_id, amount, datetime.now().isoformat()))
        conn.commit()
        request_id = c.lastrowid  # Get the ID of the last inserted request

        embed = discord.Embed(
            title="Deposit Requested",
            description=f"Your deposit request has been submitted with ID {request_id}. Please wait for admin approval.",
            color=COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_dm(interaction.user, "Deposit Requested", f"Your deposit request has been submitted with ID {request_id}.", COLOR_WARNING)
    else:
        embed = discord.Embed(
            title="Account Not Found",
            description="No account found. Please use /register to create one.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Request withdrawal
@bot.tree.command(name="withdraw", description="Request to withdraw an amount from your account.")
@app_commands.describe(amount="Amount to withdraw")
async def withdraw(interaction: discord.Interaction, amount: float):
    user_id = interaction.user.id
    if amount <= 0:
        embed = discord.Embed(
            title="Invalid Amount",
            description="Withdrawal amount must be a positive value.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    if c.fetchone():
        c.execute("INSERT INTO pending_requests (user_id, type, amount, status, date) VALUES (?, 'withdraw', ?, 'pending', ?)",
                  (user_id, amount, datetime.now().isoformat()))
        conn.commit()
        request_id = c.lastrowid  # Get the ID of the last inserted request

        embed = discord.Embed(
            title="Withdrawal Requested",
            description=f"Your withdrawal request has been submitted with ID {request_id}. Please wait for admin approval.",
            color=COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await send_dm(interaction.user, "Withdrawal Requested", f"Your withdrawal request has been submitted with ID {request_id}.", COLOR_WARNING)
    else:
        embed = discord.Embed(
            title="Account Not Found",
            description="No account found. Please use /register to create one.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# View dashboard
@bot.tree.command(name="dashboard", description="View your account details and balance.")
async def dashboard(interaction: discord.Interaction):
    user_id = interaction.user.id
    c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    account = c.fetchone()
    if account:
        username = account[1]
        account_id = account[0]
        balance = account[2]
        created_at = account[3]

        embed = discord.Embed(
            title="Account Dashboard",
            color=COLOR_INFO
        )
        embed.add_field(name="Account Holder", value=username, inline=False)
        embed.add_field(name="Account ID", value=account_id, inline=False)
        embed.add_field(name="Balance", value=f"{balance:.2f}", inline=False)
        embed.add_field(name="Created At", value=created_at, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="Account Not Found",
            description="No account found. Please use /register to create one.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Transfer money
@bot.tree.command(name="transfer", description="Transfer an amount to another user's account.")
@app_commands.describe(recipient_id="Recipient's user ID", amount="Amount to transfer")
async def transfer(interaction: discord.Interaction, recipient_id: int, amount: float):
    sender_id = interaction.user.id
    if amount <= 0:
        embed = discord.Embed(
            title="Invalid Amount",
            description="Transfer amount must be a positive value.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Check if sender's account exists
    c.execute("SELECT * FROM accounts WHERE user_id=?", (sender_id,))
    sender_account = c.fetchone()

    # Check if recipient's account exists
    c.execute("SELECT * FROM accounts WHERE user_id=?", (recipient_id,))
    recipient_account = c.fetchone()

    if sender_account and recipient_account:
        if sender_account[2] >= amount:
            new_sender_balance = sender_account[2] - amount
            new_recipient_balance = recipient_account[2] + amount

            c.execute("UPDATE accounts SET balance=? WHERE user_id=?", (new_sender_balance, sender_id))
            c.execute("UPDATE accounts SET balance=? WHERE user_id=?", (new_recipient_balance, recipient_id))
            c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, 'transfer out', ?, ?)",
                      (sender_id, -amount, datetime.now().isoformat()))
            c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, 'transfer in', ?, ?)",
                      (recipient_id, amount, datetime.now().isoformat()))
            conn.commit()

            embed = discord.Embed(
                title="Transfer Completed",
                description=f"Successfully transferred {amount:.2f} to user with ID {recipient_id}.",
                color=COLOR_SUCCESS
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            # Send DM to the sender
            await send_dm(interaction.user, "Transfer Completed", f"You have successfully transferred {amount:.2f} to user with ID {recipient_id}.", COLOR_SUCCESS)
            # Send DM to the recipient
            recipient_user = await bot.fetch_user(recipient_id)
            await send_dm(recipient_user, "Money Received", f"You have received {amount:.2f} from user with ID {sender_id}.", COLOR_SUCCESS)
        else:
            embed = discord.Embed(
                title="Insufficient Funds",
                description="You do not have enough funds to complete this transfer.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="Account Not Found",
            description="One or both accounts were not found. Please check the recipient ID and try again.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Review transactions
@bot.tree.command(name="transactions", description="Review your transaction history.")
async def transactions(interaction: discord.Interaction):
    user_id = interaction.user.id
    c.execute("SELECT * FROM transactions WHERE user_id=?", (user_id,))
    transactions = c.fetchall()
    if transactions:
        embed = discord.Embed(
            title="Transaction History",
            color=COLOR_INFO
        )
        for t in transactions:
            embed.add_field(name=t[2], value=f"Amount: {t[3]} on {t[4]}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="No Transactions Found",
            description="You have no transaction history.",
            color=COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

### Admin Commands ###

# Approve deposit
@bot.tree.command(name="approve_deposit", description="Approve a deposit request.")
@app_commands.describe(request_id="Request ID to approve")
async def approve_deposit(interaction: discord.Interaction, request_id: int):
    c.execute("SELECT * FROM pending_requests WHERE id=? AND type='deposit'", (request_id,))
    request = c.fetchone()
    if request:
        user_id = request[1]
        amount = request[2]

        c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
        account = c.fetchone()
        if account:
            new_balance = account[2] + amount
            c.execute("UPDATE accounts SET balance=? WHERE user_id=?", (new_balance, user_id))
            c.execute("DELETE FROM pending_requests WHERE id=?", (request_id,))
            c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, 'deposit', ?, ?)",
                      (user_id, amount, datetime.now().isoformat()))
            conn.commit()

            embed = discord.Embed(
                title="Deposit Approved",
                description=f"Deposit request ID {request_id} has been approved and the funds have been added to the account.",
                color=COLOR_SUCCESS
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            # Send DM to the user
            user = await bot.fetch_user(user_id)
            await send_dm(user, "Deposit Approved", f"Your deposit request ID {request_id} has been approved and the funds have been added to your account.", COLOR_SUCCESS)
        else:
            embed = discord.Embed(
                title="Account Not Found",
                description="The account associated with this deposit request was not found.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="Request Not Found",
            description="Deposit request not found. Please check the request ID and try again.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Approve withdrawal
@bot.tree.command(name="approve_withdrawal", description="Approve a withdrawal request.")
@app_commands.describe(request_id="Request ID to approve")
async def approve_withdrawal(interaction: discord.Interaction, request_id: int):
    c.execute("SELECT * FROM pending_requests WHERE id=? AND type='withdraw'", (request_id,))
    request = c.fetchone()
    if request:
        user_id = request[1]
        amount = request[2]

        c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
        account = c.fetchone()
        if account:
            if account[2] >= amount:
                new_balance = account[2] - amount
                c.execute("UPDATE accounts SET balance=? WHERE user_id=?", (new_balance, user_id))
                c.execute("DELETE FROM pending_requests WHERE id=?", (request_id,))
                c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, 'withdrawal', ?, ?)",
                          (user_id, -amount, datetime.now().isoformat()))
                conn.commit()

                embed = discord.Embed(
                    title="Withdrawal Approved",
                    description=f"Withdrawal request ID {request_id} has been approved and the funds have been withdrawn from the account.",
                    color=COLOR_SUCCESS
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                # Send DM to the user
                user = await bot.fetch_user(user_id)
                await send_dm(user, "Withdrawal Approved", f"Your withdrawal request ID {request_id} has been approved and the funds have been withdrawn from your account.", COLOR_SUCCESS)
            else:
                embed = discord.Embed(
                    title="Insufficient Funds",
                    description="The account does not have enough funds to complete this withdrawal.",
                    color=COLOR_ERROR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="Account Not Found",
                description="The account associated with this withdrawal request was not found.",
                color=COLOR_ERROR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="Request Not Found",
            description="Withdrawal request not found. Please check the request ID and try again.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Deny request
@bot.tree.command(name="deny_request", description="Deny a pending request.")
@app_commands.describe(request_id="Request ID to deny")
async def deny_request(interaction: discord.Interaction, request_id: int):
    c.execute("SELECT * FROM pending_requests WHERE id=?", (request_id,))
    request = c.fetchone()
    if request:
        c.execute("DELETE FROM pending_requests WHERE id=?", (request_id,))
        conn.commit()

        embed = discord.Embed(
            title="Request Denied",
            description=f"Request ID {request_id} has been denied and removed.",
            color=COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        # Send DM to the user
        user_id = request[1]
        user = await bot.fetch_user(user_id)
        await send_dm(user, "Request Denied", f"Your request ID {request_id} has been denied.", COLOR_WARNING)
    else:
        embed = discord.Embed(
            title="Request Not Found",
            description="Request not found. Please check the request ID and try again.",
            color=COLOR_ERROR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Sync commands with Discord
@bot.event
async def on_ready():
    await bot.tree.sync()  # Sync the commands to Discord
    print(f'Logged in as {bot.user}')

# Run the bot
bot.run(DISCORD_API_KEY)
