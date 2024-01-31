import discord
from discord.ext import tasks
import psutil
import configparser
import requests
import json
import mcrcon
import subprocess
import asyncio
import datetime
import aiohttp

############### init ###############
inipath = "./settings.ini"

ini = configparser.ConfigParser()
ini.read(inipath, "UTF-8")

# [SETTINGS]
settings = ini["SETTINGS"]
DISCORD_BOT_TOKEN = settings["DISCORD_BOT_TOKEN"]
DISCORD_WEBHOOK_URL = settings["DISCORD_WEBHOOK_URL"]
LOOP_SEC = int(settings["LOOP_SEC"])
RESTART_MEMORY_USAGE_THRESHOLD = int(settings["RESTART_MEMORY_USAGE_THRESHOLD"])
RCON_HOST = settings["RCON_HOST"]
RCON_PORT = int(settings["RCON_PORT"])
RCON_PASSWORD = settings["RCON_PASSWORD"]
GRACEFUL_SHUTDOWN_TIME = int(settings["GRACEFUL_SHUTDOWN_TIME"])
STEAM_CMD_PATH = settings["STEAM_CMD_PATH"]


PALSERVER_DIR_PATH = STEAM_CMD_PATH + "\\steamapps\\common\\PalServer"
PALSERVER_EXE_PATH = PALSERVER_DIR_PATH + "\\PalServer.exe"
PALSERVER_SAVED_PATH = PALSERVER_DIR_PATH + "\\Pal\\Saved"
PALSERVER_BACKUP_PATH = PALSERVER_DIR_PATH + "\\Pal\\Saved_Backups"

RCON_RETRY_COUNT = 20
###################################
discord_client = discord.Client(intents=discord.Intents.all())
palserver_pipe = None
is_restarting = False


@discord_client.event
async def on_ready():
    await stop_palserver_if_already_exists()
    await start_palserver()
    # await asyncio.sleep(20)
    loop_calc.start()
    print("Login!!!")


@tasks.loop(seconds=LOOP_SEC)
async def loop_calc():
    if is_restarting:
        # should not reach here
        print("サーバー再起動中...")
        return
    if palserver_pipe.poll() is not None:
        msg = "サーバーが停止しています。再起動します。"
        print(msg)
        await send_message_to_discord(msg)
        await backup_saved_directory()
        await start_palserver()
        return
    mem_percent = psutil.virtual_memory().percent
    print(mem_percent)
    # await send_message_to_discord(mem_percent)
    if mem_percent > RESTART_MEMORY_USAGE_THRESHOLD:
        await restart_palserver()
    disc_name = "メモリ使用率 {} %".format(mem_percent)
    await discord_client.change_presence(activity=discord.Game(name=disc_name))


async def stop_palserver_if_already_exists():
    for proc in psutil.process_iter():
        if proc.name() == "PalServer.exe":
            msg = "Bot 起動時にすでにサーバーが起動しているため、{} 秒後に停止します。".format(
                GRACEFUL_SHUTDOWN_TIME
            )
            print(msg)
            await send_message_to_discord("@here " + msg)
            shutdown_start_time = datetime.datetime.now()
            rcon = await connect_rcon()
            with rcon:
                await send_shutdown_command_to_palserver(rcon)
                print("サーバー終了待機中...")
                # await asyncio.sleep(GRACEFUL_SHUTDOWN_TIME)
                await wait_until_shoutdown(rcon, shutdown_start_time)
            proc.wait()
            await backup_saved_directory()
            msg = "サーバーを停止しました。"
            print(msg)
            # await send_message_to_discord(msg)


async def start_palserver():
    global palserver_pipe
    msg = "サーバーを起動します。"
    print(msg)
    # await send_message_to_discord(msg)
    palserver_pipe = subprocess.Popen(PALSERVER_EXE_PATH)
    msg = "サーバーを起動しました。"
    print(msg)
    await send_message_to_discord("@here " + msg)


async def backup_saved_directory():
    date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_saved_directory = "{}\\{}".format(PALSERVER_BACKUP_PATH, date)
    msg = "savedディレクトリをバックアップします。バックアップ先: {}".format(
        backup_saved_directory
    )
    print(msg)
    # await send_message_to_discord(msg)
    command = "robocopy /E /NFL /NDL /NJH /NJS /nc /ns /np {} {}".format(
        PALSERVER_SAVED_PATH, backup_saved_directory
    )
    # print('running ' + command)
    ret = subprocess.call(command)
    # All files were copied successfully.
    if ret != 1:
        msg = "savedディレクトリのバックアップに失敗しました。"
        print(msg)
        # await send_message_to_discord(msg)
        return exit(1)
    msg = "savedディレクトリをバックアップしました。"
    print(msg)
    # await send_message_to_discord(msg)


async def connect_rcon():
    rcon = None
    for i in range(RCON_RETRY_COUNT):
        try:
            rcon = mcrcon.MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT)
            rcon.connect()
            break
        except Exception as e:
            print("RCON接続失敗({}): {}".format(i + 1, e))
            rcon = None
            await asyncio.sleep(1)
    if rcon is None:
        msg = "RCON接続に失敗しました。継続できません。 help me!"
        print(msg)
        await send_message_to_discord(msg)
        return exit(1)
    return rcon


async def send_shutdown_command_to_palserver(rcon, seconds=GRACEFUL_SHUTDOWN_TIME):
    # 日本語は文字化けする。
    # 空白が入っているとスペースの前の単語しか表示されないため、_で置換。
    msg = "Shutdown_in_{}_seconds.".format(seconds)
    command = "shutdown {} {}".format(seconds, msg)
    print("サーバー終了コマンド送信: {}".format(command))
    ret = rcon.command(command)
    print("サーバー終了コマンド送信結果: {}".format(ret))


async def send_broadcast_command_to_palserver(rcon, msg):
    command = "broadcast {}".format(msg)
    print("サーバーブロードキャスト送信: {}".format(command))
    try:
        ret = rcon.command(command)
    except Exception as e:
        print("サーバーブロードキャスト送信失敗: {}".format(e))
        return
    print("サーバーブロードキャスト送信結果: {}".format(ret))


async def restart_palserver():
    global is_restarting
    if is_restarting:
        return
    is_restarting = True
    msg = "メモリ使用率が{}%を超えました。{}秒後に再起動します。".format(
        RESTART_MEMORY_USAGE_THRESHOLD, GRACEFUL_SHUTDOWN_TIME
    )
    print(msg)

    await send_message_to_discord("@here " + msg)
    shutdown_start_time = datetime.datetime.now()
    rcon = await connect_rcon()
    with rcon:
        await send_shutdown_command_to_palserver(rcon)
        print("サーバー終了待機中...")
        # await asyncio.sleep(GRACEFUL_SHUTDOWN_TIME)
        await wait_until_shoutdown(rcon, shutdown_start_time)
    # TODO: 例外処理
    palserver_pipe.wait()

    await backup_saved_directory()
    await start_palserver()
    is_restarting = False


async def wait_until_shoutdown(
    rcon, shutdown_start_time, shoutdown_time=GRACEFUL_SHUTDOWN_TIME
):
    while True:
        time_remaining = (
            shoutdown_time - (datetime.datetime.now() - shutdown_start_time).seconds
        )
        if time_remaining <= 0:
            break
        disc_name = "再起動中… {} 秒後にシャットダウン".format(time_remaining)
        await discord_client.change_presence(activity=discord.Game(name=disc_name))
        await send_broadcast_command_to_palserver(
            rcon, "Shutdown_in_{}_seconds.".format(time_remaining)
        )
        await asyncio.sleep(5)


async def send_message_to_discord(text):
    main_content = {"content": text}
    headers = {"Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(DISCORD_WEBHOOK_URL, json=main_content, headers=headers)
    except Exception as e:
        print("Discordへの通知に失敗しました。 {}".format(e))
        pass


discord_client.run(DISCORD_BOT_TOKEN)
