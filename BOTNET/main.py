#!/usr/bin/env python3
"""Точка входа: запуск BOTNET. Запуск из папки BOTNET: python3 main.py"""
import os
import sys
import asyncio

_github_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _github_dir not in sys.path:
    sys.path.insert(0, _github_dir)

from BOTNET.botnet import main as botnet_main

if __name__ == "__main__":
    try:
        asyncio.run(botnet_main())
    except KeyboardInterrupt:
        print("\n\n👋 До свидания!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}\n")
        sys.exit(1)
