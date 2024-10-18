import re
import os
import json
import pprint
from collections import defaultdict
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage

API_TOKEN = '7806219149:AAHuLtR831yVmi_i3uUZdwLW-jKL2whslbQ'
allowed_user_id = 1049993667

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

players_stats = defaultdict(lambda: {
    "tournaments": defaultdict(lambda: {}),
    "reentries": 0,
    "knocked_out_for_reentry": 0,
    "total_knocked_out": 0,
    "max_level": 0,
    "games_played": 0
})

buyin_pattern = re.compile(r"\d{2}:\d{2}:\d{2} .*: (.*) bought-in")
bustout_pattern = re.compile(r"\d{2}:\d{2}:\d{2} .*: (.*) busted out.*by (.*)")
round_start_pattern = re.compile(r"Start of round (\d+)")
tournament_start_pattern = re.compile(r"Tournament started")
tournament_end_pattern = re.compile(r"Tournament ended")

def save_stats_to_file(filename='tournament_stats.json'):
    with open(filename, 'w') as f:
        json.dump(players_stats, f, default=str, indent=4)

def load_stats_from_file(filename='tournament_stats.json'):
    global players_stats
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            players_stats = json.load(f)

def process_logs(logs):
    players = []
    busted_players = set()
    tournament = defaultdict(lambda: {
        "start_time": 0,
        "date": None,
        "end_level": 0
    })
    levels_starts_time = defaultdict(lambda: {})
    current_level = 0

    for line in logs:
        if buyin_pattern.search(line):
            players.append(buyin_pattern.search(line).group(1))

        if tournament_start_pattern.search(line):
            tournament["start_time"] = parse_time(line)
            tournament["date"] = line.split()[2]
            for player in players:
                if (player not in players_stats.keys()):
                    players_stats[player] = {
                    "tournaments": defaultdict(lambda: {}),
                    "reentries": 0,
                    "total_knocked_out": 0,
                    "max_level": 0,
                    "games_played": 0
                    }
                players_stats[player]["tournaments"][tournament["date"]] = defaultdict(lambda: {
                    "count_players": 0,
                    "players_names": [],
                    "live_time": 0,
                    "knockouts": 0,
                    "knocks_enemies": [],
                    "end_level": 0,
                    "place": "",
                })
                players_stats[player]["tournaments"][tournament["date"]]["count_players"] = len(players)
                players_stats[player]["tournaments"][tournament["date"]]["players_names"] = players
            continue

        if round_start_pattern.search(line):
            current_level = int(round_start_pattern.search(line).group(1))
            levels_starts_time[current_level] = parse_time(line)
            continue

        if bustout_pattern.search(line):
            busted = bustout_pattern.search(line).group(1).split()[0]
            knocked_by = bustout_pattern.search(line).group(2).split()[0]

            bust_time = parse_time(line)
            lifetime = bust_time - tournament["start_time"]

            busted_player_tournament = players_stats[busted]["tournaments"][tournament["date"]]
            busted_player_tournament["end_level"] = current_level
            busted_player_tournament["live_time"] = lifetime
            busted_player_tournament["place"] = f"{len(players) - len(busted_players)}/{len(players)}"

            knocked_player_tournament = players_stats[knocked_by]["tournaments"][tournament["date"]]
            if ("knockouts" not in knocked_player_tournament):
                knocked_player_tournament["knockouts"] = 1
            else:
                knocked_player_tournament["knockouts"] += 1

            if ("knocks_enemies" not in knocked_player_tournament):
                knocked_player_tournament["knocks_enemies"] = [busted]
            else:
                knocked_player_tournament["knocks_enemies"].append(busted)

            players_stats[busted]["games_played"] += 1
            players_stats[busted]["max_level"] = max(players_stats[busted]["max_level"], current_level)
            busted_players.add(busted)

            players_stats[knocked_by]["total_knocked_out"] += 1
            if "knocked_out_for_reentry" not in players_stats[knocked_by]:
                players_stats[knocked_by]["knocked_out_for_reentry"] = 1
            else:
                players_stats[knocked_by]["knocked_out_for_reentry"] += 1

            if players_stats[knocked_by]["knocked_out_for_reentry"] >= 5:
                players_stats[knocked_by]["reentries"] += int(players_stats[knocked_by]["knocked_out_for_reentry"] / 5)
                players_stats[knocked_by]["knocked_out_for_reentry"] -= int(
                    players_stats[knocked_by]["knocked_out_for_reentry"] / 5) * 5


        if tournament_end_pattern.search(line):
            break

    for player in players:
        if player not in busted_players:
            if (player not in players_stats.keys()):
                players_stats[player] = {
                    "tournaments": defaultdict(lambda: {}),
                    "reentries": 0,
                    "total_knocked_out": 0,
                    "max_level": 0,
                    "games_played": 0
                }
            players_stats[player]["tournaments"][tournament["date"]]["live_time"] = datetime.min
            players_stats[player]["max_level"] = max(players_stats[player]["max_level"], current_level)
            players_stats[player]["games_played"] += 1
            if "knocked_out_for_reentry" not in players_stats[player]:
                players_stats[player]["knocked_out_for_reentry"] = 0
            if players_stats[player]["knocked_out_for_reentry"] >= 5:
                players_stats[player]["reentries"] += int(players_stats[player]["knocked_out_for_reentry"] / 5)
                players_stats[player]["knocked_out_for_reentry"] -= int(
                    players_stats[player]["knocked_out_for_reentry"] / 5) * 5

def parse_time(line):
    time_str = line.split()[0]
    return datetime.strptime(time_str, '%H:%M:%S')

@dp.message(Command("start"))
async def send_welcome(message: Message):
    await message.answer("Привет! Отправь мне файл логов турнира для анализа.")

@dp.message(Command("help"))
async def send_help(message: Message):
    help_text = (
        "📋 Команды доступные для использования:\n"
        "\n"
        "1. /start - Приветственное сообщение и информация о боте.\n"
        "2. /send_file - Отправьте файл логов турнира для анализа.\n"
        "3. /reentry [Имя] [+|-] [Количество] - Изменить количество реентри для игрока.\n"
        "4. /knocks [Имя] [+|-] [Количество] - Изменить количество выбиваний для игрока.\n"
        "5. /get_full_stats_for [Имя] - Получить полную статистику для указанного игрока.\n"
        "6. /get_full_stats - Получить полную статистику для вашего профиля.\n"
        "7. /getstats_for [Имя] - Получить сводную статистику для указанного игрока.\n"
        "8. /getstats - Получить сводную статистику для вашего профиля.\n"
        "\n"
        "💬 Если у вас возникли вопросы, не стесняйтесь обращаться!"
    )
    await message.answer(help_text)

@dp.message(Command("send_file"))
async def handle_file(message: types.Message):
    if message.from_user.id != allowed_user_id:
        await message.answer("У вас нет прав для загрузки файлов.")
        return

    mime_type = message.document.mime_type
    if mime_type != 'text/plain':
        await message.answer("Пожалуйста, загрузите файл в формате .txt.")
        return

    load_stats_from_file()

    file_info = await bot.get_file(message.document.file_id)
    file = await bot.download_file(file_info.file_path)
    logs = file.read().decode('utf-8').splitlines()

    process_logs(logs)

    save_stats_to_file()
    await message.answer("Статистика турнира обновлена.")
    pprint.pprint(players_stats, sort_dicts=False, indent=4)


@dp.message(Command(commands=["reentry"]))
async def handle_reentry(message: types.Message):
    if message.from_user.id != allowed_user_id:
        await message.answer("У вас нет прав для изменения реентри")
        return
    load_stats_from_file()
    try:
        _, name, znak, reentries = message.text.split()
        player = name[0].upper() + name[1:]
        if znak == "+":
            players_stats[player]["reentries"] += int(reentries)
        elif znak == "-":
            players_stats[player]["reentries"] -= int(reentries)
        save_stats_to_file()
        await message.answer(f"Количество реентри для {player} обновлено: {players_stats[player]['reentries']}")
    except ValueError:
        players_list = list(players_stats.keys())
        if not players_list:
            await message.answer("Список игроков пуст.")
            return
        player_names = "\n".join(players_list)
        await message.answer(
            f"Список игроков:\n{player_names}\nВыберите игрока для изменения реентри")
    except KeyError:
        await message.answer(f"Игрок {player} не найден.")

@dp.message(Command(commands=["knocks"]))
async def handle_reentry(message: types.Message):
    if message.from_user.id != allowed_user_id:
        await message.answer("У вас нет прав для изменения knocks")
        return
    load_stats_from_file()
    try:
        _, name, znak, knocks = message.text.split()
        player = name[0].upper() + name[1:]
        if znak == "+":
            players_stats[player]["knocked_out_for_reentry"] += int(knocks)
            players_stats[player]["total_knocked_out"] += int(knocks)
        elif znak == "-":
            players_stats[player]["knocked_out_for_reentry"] -= int(knocks)
            players_stats[player]["total_knocked_out"] -= int(knocks)

        if players_stats[player]["knocked_out_for_reentry"] >= 5:
            players_stats[player]["reentries"] += int(players_stats[player]["knocked_out_for_reentry"] / 5)
            players_stats[player]["knocked_out_for_reentry"] -= int(players_stats[player]["knocked_out_for_reentry"] / 5) * 5

        save_stats_to_file()
        await message.answer(f"Количество knocked_out_for_reentry для {player} обновлено: {players_stats[player]['knocked_out_for_reentry']}")
    except ValueError:
        players_list = list(players_stats.keys())
        if not players_list:
            await message.answer("Список игроков пуст.")
            return
        player_names = "\n".join(players_list)
        await message.answer(
            f"Список игроков:\n{player_names}\nВыберите игрока для изменения knocked_out_for_reentry")
    except KeyError:
        await message.answer(f"Игрок {player} не найден.")

@dp.message(Command(commands=["get_full_stats_for"]))
async def handle_reentry(message: types.Message):
    load_stats_from_file()
    try:
        _, name = message.text.split()
        player = name[0].upper() + name[1:]
        await message.answer(pprint.pformat(players_stats[player]))
    except Exception:
        players_list = list(players_stats.keys())
        if not players_list:
            await message.answer("Список игроков пуст.")
            return
        player_names = "\n".join(players_list)
        await message.answer(
            f"Список игроков:\n{player_names}\nВыберите игрока для получения статистики, указав его имя.")

@dp.message(Command(commands=["get_full_stats"]))
async def handle_reentry(message: types.Message):
    load_stats_from_file()
    try:
        name = message.from_user.username
        player = name[0].upper() + name[1:]
        await message.answer(pprint.pformat(players_stats[player]))
    except Exception:
        players_list = list(players_stats.keys())
        if not players_list:
            await message.answer("Список игроков пуст.")
            return
        player_names = "\n".join(players_list)
        await message.answer(
            f"Список игроков:\n{player_names}\nВыберите игрока для получения статистики, указав его имя.")

@dp.message(Command(commands=["getstats_all"]))
async def handle_reentry(message: types.Message):
    load_stats_from_file()
    try:
        name = message.from_user.username
        player = name[0].upper() + name[1:]
        players_stats[player]["tournaments"] = "..."
        for player in players_stats.keys():
            p = players_stats[player]
            p["tournaments"] = "..."
            await message.answer(pprint.pformat(p))
    except Exception:
        players_list = list(players_stats.keys())
        if not players_list:
            await message.answer("Список игроков пуст.")
            return
        player_names = "\n".join(players_list)
        await message.answer(
            f"Список игроков:\n{player_names}\nВыберите игрока для получения статистики, указав его имя.")

@dp.message(Command(commands=["getstats"]))
async def handle_reentry(message: types.Message):
    load_stats_from_file()
    try:
        name = message.from_user.username
        player = name[0].upper() + name[1:]
        players_stats[player]["tournaments"] = "..."
        await message.answer(pprint.pformat(players_stats[player]))
    except Exception:
        players_list = list(players_stats.keys())
        if not players_list:
            await message.answer("Список игроков пуст.")
            return
        player_names = "\n".join(players_list)
        await message.answer(
            f"Список игроков:\n{player_names}\nВыберите игрока для получения статистики, указав его имя.")

@dp.message(Command(commands=["getstats_for"]))
async def handle_reentry(message: types.Message):
    load_stats_from_file()
    try:
        _, name = message.text.split()
        player = name[0].upper() + name[1:]
        players_stats[player]["tournaments"] = "..."
        await message.answer(pprint.pformat(players_stats[player]))
    except Exception:
        players_list = list(players_stats.keys())
        if not players_list:
            await message.answer("Список игроков пуст.")
            return
        player_names = "\n".join(players_list)
        await message.answer(
            f"Список игроков:\n{player_names}\nВыберите игрока для получения статистики, указав его имя.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
