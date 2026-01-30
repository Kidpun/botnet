import asyncio
from typing import List, Tuple
from BOTNET.chat_manager import ChatManager
from utils.logger import get_logger

logger = get_logger(__name__)

async def get_all_chat_managers(sessions_list: List[Tuple[str, str]], check_valid: bool = True) -> List[Tuple[str, ChatManager]]:
    valid_managers = []
    print(f"\n🔄 Подключение к {len(sessions_list)} сессиям...")
    for session_name, session_path in sessions_list:
        try:
            manager = ChatManager(session_path)
            success = await manager.start()
            if success:
                valid_managers.append((session_name, manager))
                print(f"  ✅ {session_name}")
            else:
                print(f"  ❌ {session_name} - не удалось подключиться")
        except Exception as e:
            logger.error(f"Ошибка подключения к {session_name}: {e}")
            print(f"  ❌ {session_name} - ошибка: {e}")
    return valid_managers
