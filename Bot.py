import discord
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

# Create tables
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

# Register account
@bot.command()
async def register(ctx):
    user_id = ctx.author.id
    username = str(ctx.author)
    created_at = datetime.now().isoformat()

    c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    if c.fetchone():
        embed = discord.Embed(
            title="Registration Failed",
            description="You already have an account.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
    else:
        c.execute("INSERT INTO accounts (user_id, username, balance, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, username, 0.0, created_at))
        conn.commit()

        embed = discord.Embed(
            title="Account Registered",
            description=f"Account registered for {username}.",
            color=COLOR_SUCCESS
        )
        await ctx.send(embed=embed)

# Request deposit
@bot.command()
async def deposit(ctx, amount: float):
    user_id = ctx.author.id
    if amount <= 0:
        embed = discord.Embed(
            title="Invalid Amount",
            description="Deposit amount must be positive.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    if c.fetchone():
        c.execute("INSERT INTO pending_requests (user_id, type, amount, status, date) VALUES (?, 'deposit', ?, 'pending', ?)",
                  (user_id, amount, datetime.now().isoformat()))
        conn.commit()
        request_id = c.lastrowid  # Get the ID of the last inserted request

        embed = discord.Embed(
            title="Deposit Requested",
            description=f"Deposit request submitted with ID {request_id}. Awaiting admin approval.",
            color=COLOR_WARNING
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="No Account Found",
            description="You do not have an account. Use /register to create one.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)

# Request withdrawal
@bot.command()
async def withdraw(ctx, amount: float):
    user_id = ctx.author.id
    if amount <= 0:
        embed = discord.Embed(
            title="Invalid Amount",
            description="Withdrawal amount must be positive.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
    if c.fetchone():
        c.execute("INSERT INTO pending_requests (user_id, type, amount, status, date) VALUES (?, 'withdraw', ?, 'pending', ?)",
                  (user_id, amount, datetime.now().isoformat()))
        conn.commit()
        request_id = c.lastrowid  # Get the ID of the last inserted request

        embed = discord.Embed(
            title="Withdrawal Requested",
            description=f"Withdrawal request submitted with ID {request_id}. Awaiting admin approval.",
            color=COLOR_WARNING
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="No Account Found",
            description="You do not have an account. Use /register to create one.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)

# Approve request
@bot.command()
@commands.has_permissions(administrator=True)
async def approve(ctx, request_id: int):
    c.execute("SELECT * FROM pending_requests WHERE id=? AND status='pending'", (request_id,))
    request = c.fetchone()
    if request:
        user_id, req_type, amount = request[1], request[2], request[3]
        c.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,))
        account = c.fetchone()

        if req_type == 'deposit':
            if account:
                new_balance = account[2] + amount  # Add full amount
                c.execute("UPDATE accounts SET balance=? WHERE user_id=?", (new_balance, user_id))
                c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, 'deposit', ?, ?)",
                          (user_id, amount, datetime.now().isoformat()))
            else:
                embed = discord.Embed(
                    title="Error",
                    description="Account not found. Cannot process deposit.",
                    color=COLOR_ERROR
                )
                await ctx.send(embed=embed)
                return

        elif req_type == 'withdraw':
            if account and account[2] >= amount:
                new_balance = account[2] - amount
                c.execute("UPDATE accounts SET balance=? WHERE user_id=?", (new_balance, user_id))
                c.execute("INSERT INTO transactions (user_id, type, amount, date) VALUES (?, 'withdrawal', ?, ?)",
                          (user_id, -amount, datetime.now().isoformat()))
            else:
                embed = discord.Embed(
                    title="Error",
                    description="Insufficient funds or account not found. Cannot process withdrawal.",
                    color=COLOR_ERROR
                )
                await ctx.send(embed=embed)
                return

        c.execute("UPDATE pending_requests SET status='approved' WHERE id=?", (request_id,))
        conn.commit()

        embed = discord.Embed(
            title="Request Approved",
            description=f"Request {request_id} has been approved.",
            color=COLOR_SUCCESS
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Request Not Found",
            description="Request not found or already processed.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)

# Reject request
@bot.command()
@commands.has_permissions(administrator=True)
async def reject(ctx, request_id: int):
    c.execute("SELECT * FROM pending_requests WHERE id=? AND status='pending'", (request_id,))
    request = c.fetchone()
    if request:
        c.execute("UPDATE pending_requests SET status='rejected' WHERE id=?", (request_id,))
        conn.commit()

        embed = discord.Embed(
            title="Request Rejected",
            description=f"Request {request_id} has been rejected.",
            color=COLOR_WARNING
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Request Not Found",
            description="Request not found or already processed.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)

# View all pending requests
@bot.command()
@commands.has_permissions(administrator=True)
async def view_requests(ctx):
    c.execute("SELECT * FROM pending_requests WHERE status='pending'")
    requests = c.fetchall()
    if requests:
        embed = discord.Embed(
            title="Pending Requests",
            color=COLOR_INFO
        )
        for r in requests:
            request_info = f"Request ID: {r[0]}, User ID: {r[1]}, Type: {r[2]}, Amount: {r[3]}, Date: {r[5]}"
            embed.add_field(name="Request", value=request_info, inline=False)

        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="No Pending Requests",
            description="There are no pending requests.",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)

# Get info about a specific request
@bot.command()
@commands.has_permissions(administrator=True)
async def request_info(ctx, request_id: int):
    c.execute("SELECT * FROM pending_requests WHERE id=?", (request_id,))
    request = c.fetchone()
    if request:
        embed = discord.Embed(
            title="Request Information",
            description=f"Request ID: {request[0]}\nUser ID: {request[1]}\nType: {request[2]}\nAmount: {request[3]}\nStatus: {request[4]}\nDate: {request[5]}",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Request Not Found",
            description="No request found with that ID.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)

# Set balance for a specific user
@bot.command()
@commands.has_permissions(administrator=True)
async def setbalance(ctx, user_id: int, amount: float):
    if amount < 0:
        embed = discord.Embed(
            title="Invalid Amount",
            description="Balance cannot be negative.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
        return

    c.execute("UPDATE accounts SET balance=? WHERE user_id=?", (amount, user_id))
    conn.commit()

    embed = discord.Embed(
        title="Balance Set",
        description=f"Balance for user {user_id} set to {amount:.2f}.",
        color=COLOR_SUCCESS
    )
    await ctx.send(embed=embed)

# Lock a user’s account
@bot.command()
@commands.has_permissions(administrator=True)
async def lock(ctx, user_id: int):
    c.execute("UPDATE accounts SET balance=0 WHERE user_id=?", (user_id,))
    conn.commit()

    embed = discord.Embed(
        title="Account Locked",
        description=f"User {user_id}'s account has been locked and balance set to $0.",
        color=COLOR_WARNING
    )
    await ctx.send(embed=embed)

# Unlock a user’s account
@bot.command()
@commands.has_permissions(administrator=True)
async def unlock(ctx, user_id: int):
    c.execute("UPDATE accounts SET balance=0 WHERE user_id=?", (user_id,))
    conn.commit()

    embed = discord.Embed(
        title="Account Unlocked",
        description=f"User {user_id}'s account has been unlocked.",
        color=COLOR_SUCCESS
    )
    await ctx.send(embed=embed)

# Reset a user’s account balance to $0
@bot.command()
@commands.has_permissions(administrator=True)
async def reset(ctx, user_id: int):
    c.execute("UPDATE accounts SET balance=0 WHERE user_id=?", (user_id,))
    conn.commit()

    embed = discord.Embed(
        title="Account Reset",
        description=f"User {user_id}'s account balance has been reset to $0.",
        color=COLOR_WARNING
    )
    await ctx.send(embed=embed)

# View dashboard
@bot.command()
async def dashboard(ctx):
    user_id = ctx.author.id
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

        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="No Account Found",
            description="You do not have an account. Use /register to create one.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)

# Transfer money
@bot.command()
async def transfer(ctx, recipient_id: int, amount: float):
    sender_id = ctx.author.id
    if amount <= 0:
        embed = discord.Embed(
            title="Invalid Amount",
            description="Transfer amount must be positive.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)
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
                description=f"Transferred {amount:.2f} from {sender_id} to {recipient_id}.",
                color=COLOR_SUCCESS
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Insufficient Funds",
                description="You do not have enough funds to complete this transfer.",
                color=COLOR_ERROR
            )
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Account Not Found",
            description="One or both accounts were not found.",
            color=COLOR_ERROR
        )
        await ctx.send(embed=embed)

# Review transactions
@bot.command()
async def transactions(ctx):
    user_id = ctx.author.id
    c.execute("SELECT * FROM transactions WHERE user_id=?", (user_id,))
    transactions = c.fetchall()
    if transactions:
        embed = discord.Embed(
            title="Transaction History",
            color=COLOR_INFO
        )
        for t in transactions:
            embed.add_field(name=t[2], value=f"Amount: {t[3]} on {t[4]}", inline=False)

        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="No Transactions Found",
            description="No transactions available for your account.",
            color=COLOR_INFO
        )
        await ctx.send(embed=embed)

# Custom help command
@bot.command(name='info')
async def info_command(ctx):
    embed = discord.Embed(
        title="Help Menu",
        description=(
            "**Available Commands:**\n"
            "**/register** - Register a new account.\n"
            "**/deposit <amount>** - Request to deposit <amount> into your account.\n"
            "**/withdraw <amount>** - Request to withdraw <amount> from your account.\n"
            "**/dashboard** - View your account details and balance.\n"
            "**/transfer <recipient_id> <amount>** - Transfer <amount> to the user with <recipient_id>.\n"
            "**/transactions** - Review your transaction history.\n"
            "**Admin Commands:**\n"
            "**/approve <request_id>** - Approve a deposit or withdrawal request (admin only).\n"
            "**/reject <request_id>** - Reject a deposit or withdrawal request (admin only).\n"
            "**/view_requests** - View all pending requests (admin only).\n"
            "**/request_info <request_id>** - Get info about a specific request (admin only).\n"
            "**/setbalance <user> <amount>** - Set the balance for a specific user (admin only).\n"
            "**/lock <user>** - Lock a user’s account (admin only).\n"
            "**/unlock <user>** - Unlock a user’s account (admin only).\n"
            "**/reset <user>** - Reset a user’s account balance to $0 (admin only).\n"
            "### Inspire Bank (c)2024 All rights reserved."
        ),
        color=COLOR_INFO
    )
    await ctx.send(embed=embed)

# Run the bot with your token
bot.run(DISCORD_API_KEY)
