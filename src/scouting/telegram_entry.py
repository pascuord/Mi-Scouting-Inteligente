# src/scouting/telegram_entry.py
from scouting.agents.telegram_bot import run_handler

def main():
    # entrypoint para el console script "scouting-bot"
    run_handler()

if __name__ == "__main__":
    main()
