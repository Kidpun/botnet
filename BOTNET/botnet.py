#!/usr/bin/env python3
import os
import sys
import asyncio
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BOTNET.profile_manager import ProfileManager
from BOTNET.session_checker import SessionChecker
from BOTNET.username_generator import generate_random_username, generate_unique_username
from BOTNET.chat_manager import ChatManager
from BOTNET.report_manager import ReportManager
from BOTNET.security_manager import SecurityManager
from telethon import errors
from utils.logger import setup_logger, get_logger

logger = setup_logger()

BOTNET_DIR = os.path.dirname(os.path.abspath(__file__))
BOTNET_ROOT = os.path.dirname(os.path.dirname(BOTNET_DIR))
BOTNET_SESSIONS_DIR = os.path.join(BOTNET_DIR, "sessions")
BOTNET_ENV_PATH = os.path.join(BOTNET_ROOT, ".env")
BOTNET_USER_TXT = os.path.join(BOTNET_ROOT, "user.txt")

try:
    from dotenv import load_dotenv
    load_dotenv(BOTNET_ENV_PATH)
except Exception:
    load_dotenv = None


def _get_proxies():
    from BOTNET.proxy_loader import load_proxies
    return load_proxies(BOTNET_DIR)


def _proxy_for_index(idx):
    from BOTNET.proxy_loader import get_proxy_for_index
    return get_proxy_for_index(_get_proxies(), idx)


def ensure_sessions_dir():
    if not os.path.exists(BOTNET_SESSIONS_DIR):
        os.makedirs(BOTNET_SESSIONS_DIR)
        logger.info(f"Создана папка для сессий: {BOTNET_SESSIONS_DIR}")


def get_session_files(session_dir: str = None) -> list:
    if session_dir is None:
        session_dir = BOTNET_SESSIONS_DIR
    
    ensure_sessions_dir()
    
    if not os.path.exists(session_dir):
        return []
    
    sessions = []
    for file in os.listdir(session_dir):
        if file.endswith('.session'):
            session_name = file.replace('.session', '')
            sessions.append((session_name, os.path.join(session_dir, session_name)))
    
    return sorted(sessions)


def print_menu():
    menu = """
    ┌─────────────────────────────────────────┐
    │  BOTNET - Управление профилями          │
    ├─────────────────────────────────────────┤
    │  👤 ИМЯ:                                │
    │  1. Изменить имя (одна сессия)          │
    │  2. Изменить имя (все сессии)           │
    │                                         │
    │  🖼️  АВАТАРКА:                          │
    │  3. Изменить аватарку (одна сессия)     │
    │  4. Изменить аватарку (все сессии)      │
    │  5. Удалить аватарку (одна сессия)      │
    │                                         │
    │  🔤 USERNAME:                            │
    │  6. Рандомный username (одна сессия)    │
    │  7. Рандомный username (все сессии)     │
    │                                         │
    │  📝 ОПИСАНИЕ:                            │
    │  27. Изменить описание (одна сессия)    │
    │  28. Изменить описание (все сессии)     │
    │                                         │
    │  📋 ИНФОРМАЦИЯ:                          │
    │  8. Текущий профиль (одна сессия)       │
    │  9. Проверить все сессии                │
    │                                         │
    │  💬 ЧАТЫ И СООБЩЕНИЯ:                   │
    │  11. Присоединиться к чату (одна сессия)│
    │  12. Присоединиться к чату (все сессии) │
    │  13. Отправить сообщение (одна сессия)  │
    │  14. Отправить сообщение (все сессии)   │
    │  21. Покинуть чат (одна сессия)         │
    │  22. Покинуть чат (все сессии)          │
    │                                         │
    │  👥 ИНВАЙТЕР:                            │
    │  30. В чат из user.txt (одна сессия)     │
    │  31. В чат из user.txt (все сессии)      │
    │                                         │
    │  🤖 БОТЫ И РЕФЕРАЛЫ:                     │
    │  15. Запустить бота /start (одна сессия)│
    │  16. Запустить бота /start (все сессии) │
    │                                         │
    │  🚨 ЖАЛОБЫ:                             │
    │  17. Отправить жалобу (одна сессия)     │
    │  18. Отправить жалобу (все сессии)      │
    │                                         │
    │  🔒 БЕЗОПАСНОСТЬ:                       │
    │  23. Удалить другие сессии              │
    │                                         │
    │  📢 РАССЫЛКА:                           │
    │  24. Умная рассылка по ссылкам          │
    │                                         │
    │  🤖 ПАРСЕР БОТА:                       │
    │  26. Парсер @en_SearchBot              │
    │                                         │
    │  🗑️  УПРАВЛЕНИЕ:                        │
    │  10. Удалить невалидные сессии          │
    │                                         │
    │  ⚙️  НАСТРОЙКИ:                          │
    │  29. Изменить настройки (API ID / Hash) │
    │                                         │
    │  0. ❌ Выход                            │
    ├─────────────────────────────────────────┤
    │  Создано by @pentawork                  │
    └─────────────────────────────────────────┘
    """
    print(menu)


def print_sessions(sessions: list, with_status: bool = False, status_info: dict = None):
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    print(f"\n📋 Доступные сессии ({BOTNET_SESSIONS_DIR}/):")
    print("─" * 60)
    for idx, (name, path) in enumerate(sessions, 1):
        status_str = ""
        if with_status and status_info:
            is_valid, phone, _ = status_info.get(name, (False, None, None))
            if is_valid:
                status_str = f" ✅ [{phone}]" if phone else " ✅"
            else:
                status_str = " ❌"
        print(f"  {idx}. {name}{status_str}")
    print("─" * 60)


async def select_session_or_all(check_valid: bool = True, allow_all: bool = False) -> Tuple[Optional[ProfileManager], bool]:
    """
    Выбор сессии или всех сессий
    
    Returns:
        (manager, is_all) - ProfileManager или None, и флаг "все сессии"
    """
    sessions = get_session_files()
    
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        print(f"💡 Поместите .session файлы в папку: {BOTNET_SESSIONS_DIR}/")
        return None, False
    
    status_info = {}
    if check_valid:
        print("\n🔄 Проверяю актуальность сессий...")
        checker = SessionChecker()
        check_results = await checker.check_all_sessions(BOTNET_SESSIONS_DIR, timeout=5, get_proxy_for_index=_proxy_for_index)
        status_info = {name: (is_valid, phone, error) for name, is_valid, phone, error in check_results}
    
    print_sessions(sessions, with_status=check_valid, status_info=status_info)
    
    try:
        if allow_all:
            choice = input(f"\nВыберите сессию (1-{len(sessions)}) или 'all' для всех: ").strip().lower()
        else:
            choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        
        if allow_all and choice == 'all':
            return None, True
        
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return None, False
        
        session_name, session_path = sessions[idx]
        
        if check_valid and status_info:
            is_valid, phone, error = status_info.get(session_name, (False, None, None))
            if not is_valid:
                print(f"\n⚠️  Сессия {session_name} невалидна: {error}")
                proceed = input("Продолжить? (yes/no): ").strip().lower()
                if proceed != 'yes':
                    return None, False
        
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        
        manager = ProfileManager(session_path, proxy=_proxy_for_index(idx))
        success = await manager.start()
        
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return None, False
        
        return manager, False
    except ValueError:
        print("❌ Введите число или 'all'")
        return None, False
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        return None, False


async def select_session(check_valid: bool = True) -> Optional[ProfileManager]:
    """Выбор одной сессии (для обратной совместимости)"""
    manager, _ = await select_session_or_all(check_valid, allow_all=False)
    return manager


async def get_all_sessions(check_valid: bool = True) -> list:
    """Получить список всех валидных сессий"""
    sessions = get_session_files()
    
    if not sessions:
        return []
    
    valid_managers = []
    
    status_info = {}
    if check_valid:
        checker = SessionChecker()
        check_results = await checker.check_all_sessions(BOTNET_SESSIONS_DIR, timeout=5, get_proxy_for_index=_proxy_for_index)
        status_info = {name: (is_valid, phone, error) for name, is_valid, phone, error in check_results}
    
    print(f"\n🔄 Подключение к {len(sessions)} сессиям...")
    
    for idx, (session_name, session_path) in enumerate(sessions):
        if check_valid and status_info:
            is_valid, _, _ = status_info.get(session_name, (False, None, None))
            if not is_valid:
                print(f"  ⏭️  Пропуск невалидной сессии: {session_name}")
                continue
        
        try:
            manager = ProfileManager(session_path, proxy=_proxy_for_index(idx))
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


async def change_name_menu():
    """Меню изменения имени"""
    print("\n" + "=" * 50)
    print("👤 Изменение имени")
    print("=" * 50)
    
    manager = await select_session()
    if not manager:
        return
    
    try:
        first_name, last_name = await manager.get_current_profile()
        print(f"\n📋 Текущее имя: {first_name} {last_name}".strip())
        
        new_first = input("\n✏️  Введите новое имя: ").strip()
        if not new_first:
            print("❌ Имя не может быть пустым")
            await manager.disconnect()
            return
        
        new_last = input("✏️  Введите фамилию (Enter для пропуска): ").strip()
        
        print("\n🔄 Изменяю имя...")
        success, message = await manager.change_name(new_first, new_last)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        await manager.disconnect()
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await manager.disconnect()


async def change_name_all_menu():
    """Меню изменения имени для всех сессий"""
    print("\n" + "=" * 50)
    print("👤 Изменение имени (все сессии)")
    print("=" * 50)
    
    confirm = input("\n⚠️  Изменить имя для ВСЕХ сессий? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    new_first = input("\n✏️  Введите новое имя: ").strip()
    if not new_first:
        print("❌ Имя не может быть пустым")
        return
    
    new_last = input("✏️  Введите фамилию (Enter для пропуска): ").strip()
    
    sessions = await get_all_sessions()
    
    if not sessions:
        print("\n❌ Нет валидных сессий")
        return

    print(f"\n🔄 Изменяю имя для {len(sessions)} сессий...")
    print("⚠️  ВНИМАНИЕ: Используются увеличенные задержки (3-7 сек) для предотвращения заморозки")
    print("─" * 50)

    success_count = 0
    for idx, (session_name, manager) in enumerate(sessions, 1):
        try:
            success, message = await manager.change_name(new_first, new_last)
            if success:
                print(f"✅ [{idx}/{len(sessions)}] {session_name}: {message}")
                success_count += 1
            else:
                print(f"❌ [{idx}/{len(sessions)}] {session_name}: {message}")
            await manager.disconnect()

            if idx < len(sessions):
                import random
                delay = random.uniform(3, 7)
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"Ошибка в {session_name}: {e}")
            print(f"❌ [{idx}/{len(sessions)}] {session_name}: ошибка")
            try:
                await manager.disconnect()
            except Exception:
                pass
            if idx < len(sessions):
                import random
                delay = random.uniform(2, 5)
                await asyncio.sleep(delay)

    print("─" * 50)
    print(f"\n📊 Результат: {success_count}/{len(sessions)} успешно")


async def change_photo_menu():
    """Меню изменения аватарки (одна сессия)"""
    print("\n" + "=" * 50)
    print("🖼️  Изменение аватарки (одна сессия)")
    print("=" * 50)
    
    manager, _ = await select_session_or_all(allow_all=False)
    if not manager:
        return
    
    try:
        photo_path = input("\n📁 Введите путь к изображению: ").strip()
        
        photo_path = photo_path.strip('"\'')
        
        if not photo_path:
            print("❌ Путь не может быть пустым")
            await manager.disconnect()
            return
        
        if not os.path.isabs(photo_path):
            photo_path = os.path.join(os.getcwd(), photo_path)
        
        print(f"\n🔄 Загружаю аватарку: {photo_path}...")
        success, message = await manager.change_photo(photo_path)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        await manager.disconnect()
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await manager.disconnect()


async def change_photo_all_menu():
    """Меню изменения аватарки для всех сессий"""
    print("\n" + "=" * 50)
    print("🖼️  Изменение аватарки (все сессии)")
    print("=" * 50)
    
    confirm = input("\n⚠️  Изменить аватарку для ВСЕХ сессий? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    photo_path = input("\n📁 Введите путь к изображению: ").strip()
    photo_path = photo_path.strip('"\'')
    
    if not photo_path:
        print("❌ Путь не может быть пустым")
        return
    
    if not os.path.isabs(photo_path):
        photo_path = os.path.join(os.getcwd(), photo_path)
    
    if not os.path.exists(photo_path):
        print(f"❌ Файл не найден: {photo_path}")
        return
    
    sessions = await get_all_sessions()
    
    if not sessions:
        print("\n❌ Нет валидных сессий")
        return

    print(f"\n🔄 Загружаю аватарку для {len(sessions)} сессий...")
    print("⚠️  ВНИМАНИЕ: Используются увеличенные задержки (8-15 сек) для предотвращения заморозки")
    print("─" * 50)

    success_count = 0
    for idx, (session_name, manager) in enumerate(sessions, 1):
        try:
            success, message = await manager.change_photo(photo_path)
            if success:
                print(f"✅ {session_name}: {message}")
                success_count += 1
            else:
                print(f"❌ {session_name}: {message}")
            await manager.disconnect()

            if idx < len(sessions):
                import random
                delay = random.uniform(8, 15)
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"Ошибка в {session_name}: {e}")
            print(f"❌ {session_name}: ошибка")
            try:
                await manager.disconnect()
            except Exception:
                pass

    print("─" * 50)
    print(f"\n📊 Результат: {success_count}/{len(sessions)} успешно")


async def delete_photo_menu():
    """Меню удаления аватарки (одна сессия)"""
    print("\n" + "=" * 50)
    print("🗑️  Удаление аватарки (одна сессия)")
    print("=" * 50)
    
    manager, _ = await select_session_or_all(allow_all=False)
    if not manager:
        return
    
    try:
        confirm = input("\n⚠️  Вы уверены? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Отменено")
            await manager.disconnect()
            return
        
        print("\n🔄 Удаляю аватарку...")
        success, message = await manager.delete_photo()
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        await manager.disconnect()
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await manager.disconnect()


async def change_bio_menu():
    """Меню изменения описания профиля (одна сессия)"""
    print("\n" + "=" * 50)
    print("📝 Изменение описания профиля (одна сессия)")
    print("=" * 50)
    
    manager, _ = await select_session_or_all(allow_all=False)
    if not manager:
        return
    
    try:
        current_bio = await manager.get_current_bio()
        if current_bio:
            print(f"\n📋 Текущее описание: {current_bio}")
        else:
            print("\n📋 Текущее описание: Не установлено")
        
        bio = input("\n📝 Введите новое описание (макс. 70 символов): ").strip()
        if not bio:
            print("❌ Описание не может быть пустым")
            await manager.disconnect()
            return
        
        if len(bio) > 70:
            print("❌ Описание не может быть длиннее 70 символов")
            await manager.disconnect()
            return
        
        print("\n🔄 Изменяю описание...")
        success, message = await manager.change_bio(bio)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        await manager.disconnect()
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await manager.disconnect()


async def change_bio_all_menu():
    """Меню изменения описания профиля (все сессии)"""
    print("\n" + "=" * 50)
    print("📝 Изменение описания профиля (все сессии)")
    print("=" * 50)
    
    try:
        bio = input("\n📝 Введите описание для всех аккаунтов (макс. 70 символов): ").strip()
        if not bio:
            print("❌ Описание не может быть пустым")
            return
        
        if len(bio) > 70:
            print("❌ Описание не может быть длиннее 70 символов")
            return
        
        confirm = input(f"\n⚠️  Изменить описание на '{bio}' для ВСЕХ сессий? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Отменено")
            return
        
        sessions = get_session_files()
        if not sessions:
            print("\n❌ Нет сессий")
            return
        
        print(f"\n🔄 Изменяю описание для {len(sessions)} сессий...")
        print("⚠️  ВНИМАНИЕ: Используются увеличенные задержки (5-10 сек) для предотвращения заморозки")
        print("─" * 50)
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for idx, (session_name, session_path) in enumerate(sessions, 1):
            manager = None
            try:
                print(f"[{idx}/{len(sessions)}] {session_name}...", end=" ", flush=True)
                manager = ProfileManager(session_path, proxy=_proxy_for_index(idx - 1))
                success_start = await manager.start()
                if not success_start:
                    print("⏭️  невалидная сессия")
                    skipped_count += 1
                    continue
                
                success, message = await manager.change_bio(bio)
                if success:
                    print("✅")
                    success_count += 1
                else:
                    print(f"❌ {message[:30]}")
                    error_count += 1
                
                await manager.disconnect()
                
                if idx < len(sessions):
                    import random
                    delay = random.uniform(5, 10)
                    await asyncio.sleep(delay)
                
            except errors.AuthKeyUnregisteredError:
                print("⏭️  невалидная сессия")
                skipped_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
            except KeyboardInterrupt:
                print("\n\n⚠️  Операция прервана пользователем")
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
                return
            except Exception as e:
                error_msg = str(e)
                if any(keyword in error_msg.lower() for keyword in ["phone", "not authorized", "auth", "session", "login"]):
                    print("⏭️  невалидная сессия")
                    skipped_count += 1
                else:
                    logger.error(f"Ошибка в {session_name}: {e}", exc_info=True)
                    print(f"❌ ошибка: {error_msg[:30]}")
                    error_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
        
        print("─" * 50)
        print(f"\n📊 Результат:")
        print(f"   ✅ Успешно: {success_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   ⏭️  Пропущено: {skipped_count}")
        print(f"   📊 Всего: {len(sessions)}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")


async def show_profile_menu():
    """Меню просмотра профиля (одна сессия)"""
    print("\n" + "=" * 50)
    print("📋 Текущий профиль (одна сессия)")
    print("=" * 50)
    
    manager, _ = await select_session_or_all(allow_all=False)
    if not manager:
        return
    
    try:
        first_name, last_name = await manager.get_current_profile()
        me = await manager.client.get_me()
        username = await manager.get_current_username()
        bio = await manager.get_current_bio()
        
        print("\n📋 Информация о профиле:")
        print("─" * 50)
        print(f"👤 Имя: {first_name} {last_name}".strip())
        print(f"📱 ID: {me.id}")
        print(f"📞 Телефон: {me.phone or 'Не указан'}")
        print(f"🔗 Username: @{username}" if username else "🔗 Username: Не установлен")
        print(f"📝 Описание: {bio or 'Не установлено'}")
        print("─" * 50)
        
        await manager.disconnect()
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        await manager.disconnect()
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await manager.disconnect()


async def set_random_username_menu():
    """Меню установки рандомного username (одна сессия)"""
    print("\n" + "=" * 50)
    print("🔤 Установка рандомного username (одна сессия)")
    print("=" * 50)
    
    manager, _ = await select_session_or_all(allow_all=False)
    if not manager:
        return
    
    try:
        current_username = await manager.get_current_username()
        if current_username:
            print(f"\n📋 Текущий username: @{current_username}")
        else:
            print("\n📋 Текущий username: Не установлен")
        
        length_input = input("\n📏 Введите длину username (8-15, Enter для случайной): ").strip()
        length = None
        if length_input:
            try:
                length = int(length_input)
                if length < 5:
                    length = 5
                elif length > 32:
                    length = 32
            except ValueError:
                print("⚠️  Неверный формат, использую случайную длину")
        
        if length:
            new_username = generate_random_username(length=length)
        else:
            new_username = generate_unique_username(min_length=8, max_length=15)
        
        print(f"\n🎲 Сгенерирован username: @{new_username}")
        print(f"📋 Полный путь: https://t.me/{new_username}")
        print("\n" + "=" * 50)
        print(f"🔗 ФЕРМА НАЙДЕНА: @{new_username}")
        print("=" * 50)
        
        confirm = input(f"\n⚠️  Установить username @{new_username}? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Отменено")
            await manager.disconnect()
            return
        
        print("\n🔄 Устанавливаю username...")
        success, message = await manager.change_username(new_username)
        
        if success:
            print(f"✅ {message}")
            print("\n" + "=" * 50)
            print(f"🎉 ФЕРМА УСТАНОВЛЕНА: @{new_username}")
            print(f"📋 t.me/{new_username}")
            print("=" * 50)
        else:
            print(f"❌ {message}")
            if "уже занят" in message:
                print("\n🔄 Пробую другой вариант...")
                for _ in range(3):
                    if length:
                        new_username = generate_random_username(length=length)
                    else:
                        new_username = generate_unique_username()
                    print(f"   Попытка: @{new_username}")
                    success, message = await manager.change_username(new_username)
                    if success:
                        print(f"✅ {message}")
                        print("\n" + "=" * 50)
                        print(f"🎉 ФЕРМА УСТАНОВЛЕНА: @{new_username}")
                        print(f"📋 t.me/{new_username}")
                        print("=" * 50)
                        break
                else:
                    print("❌ Не удалось найти свободный username после нескольких попыток")
        
        await manager.disconnect()
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        await manager.disconnect()
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await manager.disconnect()


async def set_random_username_all_menu():
    """Меню установки рандомного username для всех сессий"""
    print("\n" + "=" * 50)
    print("🔤 Установка рандомного username (все сессии)")
    print("=" * 50)
    
    confirm = input("\n⚠️  Установить рандомные username для ВСЕХ сессий? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    length_input = input("\n📏 Введите длину username (8-15, Enter для случайной): ").strip()
    length = None
    if length_input:
        try:
            length = int(length_input)
            if length < 5:
                length = 5
            elif length > 32:
                length = 32
        except ValueError:
            print("⚠️  Неверный формат, использую случайную длину")
    
    sessions = await get_all_sessions()
    
    if not sessions:
        print("\n❌ Нет валидных сессий")
        return
    
    print(f"\n🔄 Устанавливаю рандомные username для {len(sessions)} сессий...")
    print("─" * 50)
    print("\n🔗 ФЕРМЫ НАЙДЕНЫ:")
    print("=" * 50)
    
    success_count = 0
    all_usernames = []
    
    for session_name, manager in sessions:
        try:
            for attempt in range(5):
                if length:
                    new_username = generate_random_username(length=length)
                else:
                    new_username = generate_unique_username(min_length=8, max_length=15)
                
                success, message = await manager.change_username(new_username)
                if success:
                    print(f"✅ {session_name}: @{new_username}")
                    print(f"   📋 t.me/{new_username}")
                    all_usernames.append((session_name, new_username))
                    success_count += 1
                    import random
                    await asyncio.sleep(random.uniform(3, 6))
                    break
                elif "уже занят" not in message:
                    print(f"❌ {session_name}: {message}")
                    break
            else:
                print(f"❌ {session_name}: не удалось найти свободный username")
            
            await manager.disconnect()
        except Exception as e:
            logger.error(f"Ошибка в {session_name}: {e}")
            print(f"❌ {session_name}: ошибка")
            try:
                await manager.disconnect()
            except Exception:
                pass
    
    print("=" * 50)
    print(f"\n📊 Результат: {success_count}/{len(sessions)} успешно")
    
    if all_usernames:
        print("\n📋 Список всех установленных username:")
        print("─" * 50)
        for session_name, username in all_usernames:
            print(f"  {session_name}: @{username} → t.me/{username}")
        print("─" * 50)


async def change_both_menu():
    """Меню изменения имени и аватарки"""
    print("\n" + "=" * 50)
    print("🔄 Изменение имени и аватарки")
    print("=" * 50)
    
    manager = await select_session()
    if not manager:
        return
    
    try:
        first_name, last_name = await manager.get_current_profile()
        print(f"\n📋 Текущее имя: {first_name} {last_name}".strip())
        
        new_first = input("\n✏️  Введите новое имя: ").strip()
        if not new_first:
            print("❌ Имя не может быть пустым")
            await manager.disconnect()
            return
        
        new_last = input("✏️  Введите фамилию (Enter для пропуска): ").strip()
        
        photo_path = input("\n📁 Введите путь к изображению (Enter для пропуска): ").strip()
        photo_path = photo_path.strip('"\'')
        
        if photo_path and not os.path.isabs(photo_path):
            photo_path = os.path.join(os.getcwd(), photo_path)
        
        if new_first:
            print("\n🔄 Изменяю имя...")
            success_name, msg_name = await manager.change_name(new_first, new_last)
            if success_name:
                print(f"✅ {msg_name}")
            else:
                print(f"❌ {msg_name}")
            import random
            await asyncio.sleep(random.uniform(3, 6))
        
        if photo_path and os.path.exists(photo_path):
            print("\n🔄 Загружаю аватарку...")
            success_photo, msg_photo = await manager.change_photo(photo_path)
            if success_photo:
                print(f"✅ {msg_photo}")
            else:
                print(f"❌ {msg_photo}")
        elif photo_path:
            print(f"⚠️  Файл не найден: {photo_path}")
        
        await manager.disconnect()
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        await manager.disconnect()
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        await manager.disconnect()


async def check_all_sessions_menu():
    """Меню проверки всех сессий"""
    print("\n" + "=" * 50)
    print("✅ Проверка всех сессий")
    print("=" * 50)
    
    ensure_sessions_dir()
    
    checker = SessionChecker()
    results = await checker.check_all_sessions(BOTNET_SESSIONS_DIR, timeout=10, get_proxy_for_index=_proxy_for_index)
    
    if not results:
        print("\n❌ Сессии не найдены")
        return
    
    valid_count = sum(1 for _, is_valid, _, _ in results if is_valid)
    invalid_count = len(results) - valid_count
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты проверки:")
    print(f"   ✅ Валидных: {valid_count}")
    print(f"   ❌ Невалидных: {invalid_count}")
    print("=" * 50)
    
    if invalid_count > 0:
        print("\n❌ Невалидные сессии:")
        for session_name, is_valid, phone, error in results:
            if not is_valid:
                print(f"   • {session_name}: {error}")


async def reset_other_sessions_menu():
    """Меню удаления других сессий и установки облачного пароля"""
    print("\n" + "=" * 50)
    print("🔒 Безопасность аккаунта")
    print("=" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    print_sessions(sessions)
    
    security = None
    try:
        choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return
        
        session_name, session_path = sessions[idx]
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        
        security = SecurityManager(session_path, proxy=_proxy_for_index(idx))
        success = await security.start()
        
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return
        
        print("\n📋 Выберите действие:")
        print("  1. Удалить все другие сессии")
        print("  4. Проверить статус пароля")
        
        action = input("\nВыберите действие (1 или 4): ").strip()
        
        if action == '1':
            confirm = input("\n⚠️  Удалить все другие активные сессии? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Отменено")
                await security.disconnect()
                return
            
            print("\n🔄 Удаляю другие сессии...")
            success, message, deleted_count = await security.reset_other_authorizations()
            
            if success:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
        
        elif action == '4':
            print("\n🔄 Проверяю статус облачного пароля...")
            success, password_info, message = await security.get_password_info()
            
            if success:
                print(f"ℹ️  {message}")
                if password_info and password_info.get('has_password'):
                    hint = password_info.get('hint')
                    if hint:
                        print(f"💡 Подсказка: {hint}")
            else:
                print(f"❌ {message}")
        
        else:
            print("❌ Неверный выбор")
        
        await security.disconnect()
    except ValueError:
        print("❌ Введите число")
        if security:
            try:
                await security.disconnect()
            except Exception:
                pass
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        if security:
            try:
                await security.disconnect()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        if security:
            try:
                await security.disconnect()
            except Exception:
                pass


async def remove_invalid_sessions_menu():
    """Меню удаления невалидных сессий"""
    print("\n" + "=" * 50)
    print("🗑️  Удаление невалидных сессий")
    print("=" * 50)
    
    ensure_sessions_dir()
    
    checker = SessionChecker()
    results = await checker.check_all_sessions(BOTNET_SESSIONS_DIR, timeout=10, get_proxy_for_index=_proxy_for_index)
    
    if not results:
        print("\n❌ Сессии не найдены")
        return
    
    invalid_sessions = [name for name, is_valid, _, _ in results if not is_valid]
    
    if not invalid_sessions:
        print("\n✅ Невалидных сессий не найдено")
        return
    
    print(f"\n⚠️  Найдено {len(invalid_sessions)} невалидных сессий:")
    for name in invalid_sessions:
        print(f"   • {name}")
    
    confirm = input(f"\n⚠️  Удалить эти сессии? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    removed = checker.remove_invalid_sessions(BOTNET_SESSIONS_DIR, results)
    print(f"\n✅ Удалено {removed} невалидных сессий")


async def change_settings_menu():
    """Меню изменения настроек: API ID и API Hash, сохраняются в .env"""
    print("\n" + "=" * 50)
    print("⚙️  Настройки (API ID / API Hash)")
    print("=" * 50)
    try:
        from dotenv import load_dotenv, set_key
    except ImportError:
        print("\n❌ Установите python-dotenv: pip install python-dotenv")
        return
    api_id = input("\nAPI ID (число с my.telegram.org): ").strip()
    api_hash = input("API Hash (строка с my.telegram.org): ").strip()
    if not api_id or not api_hash:
        print("❌ Оба поля обязательны. Отменено.")
        return
    try:
        int(api_id)
    except ValueError:
        print("❌ API ID должен быть числом. Отменено.")
        return
    set_key(BOTNET_ENV_PATH, "API_ID", api_id)
    set_key(BOTNET_ENV_PATH, "API_HASH", api_hash)
    load_dotenv(BOTNET_ENV_PATH, override=True)
    os.environ["API_ID"] = api_id
    os.environ["API_HASH"] = api_hash
    print(f"\n✅ Настройки сохранены в {BOTNET_ENV_PATH}")


async def join_chat_menu():
    """Меню присоединения к чату (одна сессия)"""
    print("\n" + "=" * 50)
    print("💬 Присоединение к чату (одна сессия)")
    print("=" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    print_sessions(sessions)
    
    try:
        choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return
        
        session_name, session_path = sessions[idx]
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        
        manager = ChatManager(session_path, proxy=_proxy_for_index(idx))
        success = await manager.start()
        
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return
        
        invite_link = input("\n🔗 Введите ссылку на чат (t.me/joinchat/..., t.me/username): ").strip()
        if not invite_link:
            print("❌ Ссылка не может быть пустой")
            await manager.disconnect()
            return
        
        print("\n🔄 Присоединяюсь к чату...")
        success, message, chat_username = await manager.join_chat(invite_link)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except ValueError:
        print("❌ Введите число")
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        try:
            await manager.disconnect()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        try:
            await manager.disconnect()
        except Exception:
            pass


async def join_chat_all_menu():
    """Меню присоединения к чату (все сессии)"""
    print("\n" + "=" * 50)
    print("💬 Присоединение к чату (все сессии)")
    print("=" * 50)
    
    try:
        confirm = input("\n⚠️  Присоединить ВСЕ сессии к чату? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Отменено")
            return
        
        invite_link = input("\n🔗 Введите ссылку на чат (t.me/joinchat/..., t.me/username): ").strip()
        if not invite_link:
            print("❌ Ссылка не может быть пустой")
            return
        
        sessions = get_session_files()
        if not sessions:
            print("\n❌ Нет сессий")
            return
        
        print(f"\n🔄 Присоединяю {len(sessions)} сессий к чату...")
        print("─" * 50)
        
        success_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, (session_name, session_path) in enumerate(sessions, 1):
            manager = None
            try:
                print(f"[{idx}/{len(sessions)}] {session_name}...", end=" ", flush=True)
                manager = ChatManager(session_path, proxy=_proxy_for_index(idx - 1))
                success_start = await manager.start()
                if not success_start:
                    print("⏭️  невалидная сессия")
                    skipped_count += 1
                    continue
                
                success, message, _ = await manager.join_chat(invite_link)
                if success:
                    print(f"✅ {message}")
                    success_count += 1
                else:
                    print(f"❌ {message}")
                    error_count += 1
                
                await manager.disconnect()
                await asyncio.sleep(0.5)
                
            except errors.AuthKeyUnregisteredError:
                print("⏭️  невалидная сессия")
                skipped_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
            except KeyboardInterrupt:
                print("\n\n⚠️  Операция прервана пользователем")
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
                return
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                if any(keyword in error_msg.lower() for keyword in ["phone", "not authorized", "auth", "session", "login"]):
                    print(f"⏭️  невалидная сессия")
                    skipped_count += 1
                else:
                    logger.error(f"Ошибка в {session_name}: {error_type}: {e}", exc_info=True)
                    print(f"❌ ошибка: {error_msg[:40]}")
                    error_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
        
        print("─" * 50)
        print(f"\n📊 Результат:")
        print(f"   ✅ Успешно: {success_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   ⏭️  Пропущено: {skipped_count}")
        print(f"   📊 Всего: {len(sessions)}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка в join_chat_all_menu: {e}", exc_info=True)
        print(f"\n❌ Критическая ошибка: {e}")


def _load_usernames_from_file(path: str) -> list:
    if not os.path.exists(path):
        return []
    usernames = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().lstrip("@")
            if line and not line.startswith("#"):
                usernames.append(line)
    return usernames


async def inviter_menu():
    print("\n" + "=" * 50)
    print("👥 Инвайтер — пригласить в чат из user.txt (одна сессия)")
    print("=" * 50)
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    if not os.path.exists(BOTNET_USER_TXT):
        print(f"\n❌ Файл не найден: {BOTNET_USER_TXT}")
        print("   Создайте user.txt и укажите по одному юзернейму на строку (с @ или без).")
        return
    usernames = _load_usernames_from_file(BOTNET_USER_TXT)
    if not usernames:
        print(f"\n❌ В файле {BOTNET_USER_TXT} нет юзернеймов.")
        return
    print_sessions(sessions)
    try:
        choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        idx = int(choice) - 1
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return
        session_name, session_path = sessions[idx]
        chat_link = input("\n🔗 Введите ссылку/username чата (t.me/..., @chat): ").strip()
        if not chat_link:
            print("❌ Ссылка не может быть пустой")
            return
        delay_str = input("⏱ Задержка между приглашениями, сек (Enter = 2): ").strip() or "2"
        try:
            delay_sec = float(delay_str)
            if delay_sec < 0:
                delay_sec = 0
        except ValueError:
            delay_sec = 2.0
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        manager = ChatManager(session_path, proxy=_proxy_for_index(idx))
        success = await manager.start()
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return
        print(f"📋 Приглашаю {len(usernames)} пользователей из user.txt в чат...")
        invited, failed_count, failed_list = await manager.invite_users_to_chat(chat_link, usernames, delay_sec=delay_sec)
        await manager.disconnect()
        print(f"\n✅ Приглашено: {invited}, ошибок: {failed_count}")
        if failed_list:
            for u, err in failed_list[:20]:
                print(f"   ❌ @{u}: {err}")
            if len(failed_list) > 20:
                print(f"   ... и ещё {len(failed_list) - 20}")
    except ValueError:
        print("❌ Введите число")
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
    except Exception as e:
        logger.error(f"Ошибка инвайтера: {e}", exc_info=True)
        print(f"\n❌ Ошибка: {e}")


async def inviter_all_menu():
    print("\n" + "=" * 50)
    print("👥 Инвайтер — пригласить в чат из user.txt (все сессии)")
    print("=" * 50)
    if not os.path.exists(BOTNET_USER_TXT):
        print(f"\n❌ Файл не найден: {BOTNET_USER_TXT}")
        return
    usernames = _load_usernames_from_file(BOTNET_USER_TXT)
    if not usernames:
        print(f"\n❌ В файле {BOTNET_USER_TXT} нет юзернеймов.")
        return
    sessions = get_session_files()
    if not sessions:
        print("\n❌ Нет сессий")
        return
    chat_link = input("\n🔗 Введите ссылку/username чата (t.me/..., @chat): ").strip()
    if not chat_link:
        print("❌ Ссылка не может быть пустой")
        return
    delay_str = input("⏱ Задержка между приглашениями, сек (Enter = 2): ").strip() or "2"
    try:
        delay_sec = float(delay_str)
        if delay_sec < 0:
            delay_sec = 0
    except ValueError:
        delay_sec = 2.0
    confirm = input(f"\n⚠️ Пригласить из {len(usernames)} юзернеймов в чат с {len(sessions)} сессий? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("❌ Отменено")
        return
    print(f"\n🔄 Запуск инвайтера для {len(sessions)} сессий...")
    print("─" * 50)
    total_invited = 0
    total_failed = 0
    for idx, (session_name, session_path) in enumerate(sessions):
        manager = None
        try:
            manager = ChatManager(session_path, proxy=_proxy_for_index(idx))
            if not await manager.start():
                print(f"   [{idx+1}/{len(sessions)}] {session_name} — не удалось подключиться")
                continue
            invited, failed_count, failed_list = await manager.invite_users_to_chat(chat_link, usernames, delay_sec=delay_sec)
            total_invited += invited
            total_failed += failed_count
            print(f"   [{idx+1}/{len(sessions)}] {session_name} — приглашено: {invited}, ошибок: {failed_count}")
        except Exception as e:
            print(f"   [{idx+1}/{len(sessions)}] {session_name} — ошибка: {e}")
        finally:
            if manager:
                try:
                    await manager.disconnect()
                except Exception:
                    pass
    print("─" * 50)
    print(f"📊 Всего приглашено: {total_invited}, всего ошибок: {total_failed}")


async def leave_chat_menu():
    """Меню выхода из чата (одна сессия)"""
    print("\n" + "=" * 50)
    print("🚪 Выход из чата (одна сессия)")
    print("=" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    print_sessions(sessions)
    
    try:
        choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return
        
        session_name, session_path = sessions[idx]
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        
        manager = ChatManager(session_path, proxy=_proxy_for_index(idx))
        success = await manager.start()
        
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return
        
        chat_identifier = input("\n🔗 Введите @username чата/канала: ").strip()
        if not chat_identifier:
            print("❌ Username не может быть пустым")
            await manager.disconnect()
            return
        
        if chat_identifier.startswith('@'):
            chat_identifier = chat_identifier[1:]
        
        confirm = input(f"\n⚠️  Покинуть @{chat_identifier}? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Отменено")
            await manager.disconnect()
            return
        
        print("\n🔄 Покидаю чат...")
        success, message = await manager.leave_chat(chat_identifier)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except ValueError:
        print("❌ Введите число")
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        try:
            await manager.disconnect()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        try:
            await manager.disconnect()
        except Exception:
            pass


async def leave_chat_all_menu():
    """Меню выхода из чата (все сессии)"""
    print("\n" + "=" * 50)
    print("🚪 Выход из чата (все сессии)")
    print("=" * 50)
    
    try:
        chat_identifier = input("\n🔗 Введите @username чата/канала: ").strip()
        if not chat_identifier:
            print("❌ Username не может быть пустым")
            return
        
        if chat_identifier.startswith('@'):
            chat_identifier = chat_identifier[1:]
        
        confirm = input(f"\n⚠️  Покинуть @{chat_identifier} со ВСЕХ сессий? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Отменено")
            return
        
        sessions = get_session_files()
        if not sessions:
            print("\n❌ Нет сессий")
            return
        
        print(f"\n🔄 Покидаю {len(sessions)} сессий из чата...")
        print("─" * 50)
        
        success_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, (session_name, session_path) in enumerate(sessions, 1):
            manager = None
            try:
                print(f"[{idx}/{len(sessions)}] {session_name}...", end=" ", flush=True)
                manager = ChatManager(session_path, proxy=_proxy_for_index(idx - 1))
                success_start = await manager.start()
                if not success_start:
                    print("⏭️  невалидная сессия")
                    skipped_count += 1
                    continue
                
                success, message = await manager.leave_chat(chat_identifier)
                if success:
                    print(f"✅ {message}")
                    success_count += 1
                else:
                    print(f"❌ {message}")
                    error_count += 1
                
                await manager.disconnect()
                await asyncio.sleep(0.5)
                
            except errors.AuthKeyUnregisteredError:
                print("⏭️  невалидная сессия")
                skipped_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
            except KeyboardInterrupt:
                print("\n\n⚠️  Операция прервана пользователем")
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
                return
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                if any(keyword in error_msg.lower() for keyword in ["phone", "not authorized", "auth", "session", "login"]):
                    print(f"⏭️  невалидная сессия")
                    skipped_count += 1
                else:
                    logger.error(f"Ошибка в {session_name}: {error_type}: {e}", exc_info=True)
                    print(f"❌ ошибка: {error_msg[:40]}")
                    error_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
        
        print("─" * 50)
        print(f"\n📊 Результат:")
        print(f"   ✅ Успешно: {success_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   ⏭️  Пропущено: {skipped_count}")
        print(f"   📊 Всего: {len(sessions)}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка в leave_chat_all_menu: {e}", exc_info=True)
        print(f"\n❌ Критическая ошибка: {e}")


async def send_message_menu():
    """Меню отправки сообщения (одна сессия)"""
    print("\n" + "=" * 50)
    print("💬 Отправка сообщения (одна сессия)")
    print("=" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    print_sessions(sessions)
    
    try:
        choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return
        
        session_name, session_path = sessions[idx]
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        
        manager = ChatManager(session_path, proxy=_proxy_for_index(idx))
        success = await manager.start()
        
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return
        
        chat_identifier = input("\n🔗 Введите @username чата или ссылку: ").strip()
        if not chat_identifier:
            print("❌ Идентификатор чата не может быть пустым")
            await manager.disconnect()
            return
        
        message_text = input("\n✏️  Введите текст сообщения: ").strip()
        if not message_text:
            print("❌ Сообщение не может быть пустым")
            await manager.disconnect()
            return
        
        print("\n🔄 Отправляю сообщение...")
        success, message = await manager.send_message(chat_identifier, message_text)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except ValueError:
        print("❌ Введите число")
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        try:
            await manager.disconnect()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        try:
            await manager.disconnect()
        except Exception:
            pass


async def send_message_all_menu():
    """Меню отправки сообщения (все сессии)"""
    print("\n" + "=" * 50)
    print("💬 Отправка сообщения (все сессии)")
    print("=" * 50)
    
    confirm = input("\n⚠️  Отправить сообщение со ВСЕХ сессий? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    chat_identifier = input("\n🔗 Введите @username чата или ссылку: ").strip()
    if not chat_identifier:
        print("❌ Идентификатор чата не может быть пустым")
        return
    
    message_text = input("\n✏️  Введите текст сообщения: ").strip()
    if not message_text:
        print("❌ Сообщение не может быть пустым")
        return
    
    sessions = get_session_files()
    if not sessions:
        print("\n❌ Нет сессий")
        return
    
    print(f"\n🔄 Отправляю сообщение из {len(sessions)} сессий...")
    print("─" * 50)
    
    success_count = 0
    skipped_count = 0
    for idx, (session_name, session_path) in enumerate(sessions):
        manager = None
        try:
            manager = ChatManager(session_path, proxy=_proxy_for_index(idx))
            success_start = await manager.start()
            if not success_start:
                print(f"⏭️  {session_name}: невалидная сессия (пропуск)")
                skipped_count += 1
                continue
            
            success, message = await manager.send_message(chat_identifier, message_text, join_if_needed=True)
            if success:
                print(f"✅ {session_name}: {message}")
                success_count += 1
            else:
                print(f"❌ {session_name}: {message}")
            
            await manager.disconnect()
            import random
            await asyncio.sleep(random.uniform(5, 10))
        except errors.AuthKeyUnregisteredError:
            print(f"⏭️  {session_name}: невалидная сессия (пропуск)")
            skipped_count += 1
            if manager:
                try:
                    await manager.disconnect()
                except Exception:
                    pass
        except KeyboardInterrupt:
            print("\n\n⚠️  Операция прервана пользователем")
            if manager:
                try:
                    await manager.disconnect()
                except Exception:
                    pass
            break
        except Exception as e:
            error_msg = str(e)
            if "phone" in error_msg.lower() or "not authorized" in error_msg.lower() or "auth" in error_msg.lower():
                print(f"⏭️  {session_name}: невалидная сессия (пропуск)")
                skipped_count += 1
            else:
                logger.error(f"Ошибка в {session_name}: {e}")
                print(f"❌ {session_name}: ошибка - {error_msg[:50]}")
            if manager:
                try:
                    await manager.disconnect()
                except Exception:
                    pass
    
    print("─" * 50)
    print(f"\n📊 Результат: {success_count}/{len(sessions)} успешно, {skipped_count} пропущено")


async def start_bot_menu():
    """Меню запуска бота (одна сессия)"""
    print("\n" + "=" * 50)
    print("🤖 Запуск бота /start (одна сессия)")
    print("=" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    print_sessions(sessions)
    
    try:
        choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return
        
        session_name, session_path = sessions[idx]
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        
        manager = ChatManager(session_path, proxy=_proxy_for_index(idx))
        success = await manager.start()
        
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return
        
        bot_link = input("\n🤖 Введите ссылку на бота (t.me/botname?start=CODE, @botname CODE): ").strip()
        if not bot_link:
            print("❌ Ссылка на бота не может быть пустой")
            await manager.disconnect()
            return
        
        print("\n🔄 Отправляю /start боту...")
        success, message = await manager.start_bot(bot_link)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except ValueError:
        print("❌ Введите число")
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        try:
            await manager.disconnect()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        try:
            await manager.disconnect()
        except Exception:
            pass


async def start_bot_all_menu():
    """Меню запуска бота (все сессии)"""
    print("\n" + "=" * 50)
    print("🤖 Запуск бота /start (все сессии)")
    print("=" * 50)
    
    try:
        confirm = input("\n⚠️  Отправить /start со ВСЕХ сессий? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Отменено")
            return
        
        bot_link = input("\n🤖 Введите ссылку на бота (t.me/botname?start=CODE, @botname CODE): ").strip()
        if not bot_link:
            print("❌ Ссылка на бота не может быть пустой")
            return
        
        sessions = get_session_files()
        if not sessions:
            print("\n❌ Нет сессий")
            return
        
        print(f"\n🔄 Отправляю /start из {len(sessions)} сессий...")
        print("─" * 50)
        
        success_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, (session_name, session_path) in enumerate(sessions, 1):
            manager = None
            try:
                print(f"[{idx}/{len(sessions)}] {session_name}...", end=" ", flush=True)
                manager = ChatManager(session_path, proxy=_proxy_for_index(idx - 1))
                success_start = await manager.start()
                if not success_start:
                    print("⏭️  невалидная сессия")
                    skipped_count += 1
                    continue
                
                success, message = await manager.start_bot(bot_link)
                if success:
                    print(f"✅ {message}")
                    success_count += 1
                else:
                    print(f"❌ {message}")
                    error_count += 1
                
                await manager.disconnect()
                await asyncio.sleep(0.5)
                
            except errors.AuthKeyUnregisteredError:
                print("⏭️  невалидная сессия")
                skipped_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
            except KeyboardInterrupt:
                print("\n\n⚠️  Операция прервана пользователем")
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
                return
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                if any(keyword in error_msg.lower() for keyword in ["phone", "not authorized", "auth", "session", "login"]):
                    print(f"⏭️  невалидная сессия")
                    skipped_count += 1
                else:
                    logger.error(f"Ошибка в {session_name}: {error_type}: {e}", exc_info=True)
                    print(f"❌ ошибка: {error_msg[:40]}")
                    error_count += 1
                if manager:
                    try:
                        await manager.disconnect()
                    except Exception:
                        pass
        
        print("─" * 50)
        print(f"\n📊 Результат:")
        print(f"   ✅ Успешно: {success_count}")
        print(f"   ❌ Ошибок: {error_count}")
        print(f"   ⏭️  Пропущено: {skipped_count}")
        print(f"   📊 Всего: {len(sessions)}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка в start_bot_all_menu: {e}", exc_info=True)
        print(f"\n❌ Критическая ошибка: {e}")


def print_report_reasons():
    """Вывод списка причин для жалобы"""
    reasons = ReportManager.REASON_CLASSES
    print("\n📋 Причины для жалобы:")
    print("─" * 50)
    for code, (name, _) in sorted(reasons.items()):
        print(f"  {code}. {name}")
    print("─" * 50)


async def send_report_menu():
    """Меню отправки жалобы (одна сессия)"""
    print("\n" + "=" * 50)
    print("🚨 Отправка жалобы на сообщение (одна сессия)")
    print("=" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    print_sessions(sessions)
    
    manager = None
    try:
        choice = input(f"\nВыберите сессию (1-{len(sessions)}): ").strip()
        idx = int(choice) - 1
        
        if idx < 0 or idx >= len(sessions):
            print("❌ Неверный выбор")
            return
        
        session_name, session_path = sessions[idx]
        print(f"\n🔄 Подключение к сессии: {session_name}...")
        
        manager = ReportManager(session_path, proxy=_proxy_for_index(idx))
        success = await manager.start()
        
        if not success:
            print("❌ Не удалось подключиться к сессии")
            return
        
        message_link = input("\n🔗 Введите ссылку на сообщение (t.me/channel/message_id): ").strip()
        if not message_link:
            print("❌ Ссылка не может быть пустой")
            await manager.disconnect()
            return
        
        print_report_reasons()
        reason_code = input("\n📋 Выберите причину (1-9): ").strip()
        if not reason_code or reason_code not in ReportManager.REASON_CLASSES:
            print("❌ Неверный код причины")
            await manager.disconnect()
            return
        
        comment = input("\n✏️  Введите комментарий (Enter для пропуска): ").strip()
        
        print("\n🔄 Отправляю жалобу...")
        success, message = await manager.send_report(message_link, reason_code, comment)
        
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        await manager.disconnect()
    except ValueError:
        print("❌ Введите число")
        if manager:
            try:
                await manager.disconnect()
            except Exception:
                pass
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана")
        if manager:
            try:
                await manager.disconnect()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        if manager:
            try:
                await manager.disconnect()
            except Exception:
                pass


async def send_report_all_menu():
    """Меню отправки жалобы (все сессии)"""
    print("\n" + "=" * 50)
    print("🚨 Отправка жалобы на сообщение (все сессии)")
    print("=" * 50)
    
    confirm = input("\n⚠️  Отправить жалобу со ВСЕХ сессий? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    message_link = input("\n🔗 Введите ссылку на сообщение (t.me/channel/message_id): ").strip()
    if not message_link:
        print("❌ Ссылка не может быть пустой")
        return
    
    print_report_reasons()
    reason_code = input("\n📋 Выберите причину (1-9): ").strip()
    if not reason_code or reason_code not in ReportManager.REASON_CLASSES:
        print("❌ Неверный код причины")
        return
    
    comment = input("\n✏️  Введите комментарий (Enter для пропуска): ").strip()
    
    sessions = get_session_files()
    if not sessions:
        print("\n❌ Нет сессий")
        return
    
    reason_name, _ = ReportManager.get_reason(reason_code)
    print(f"\n🔄 Отправляю жалобу '{reason_name}' из {len(sessions)} сессий...")
    print("─" * 50)
    
    success_count = 0
    skipped_count = 0
    error_count = 0
    
    for idx, (session_name, session_path) in enumerate(sessions, 1):
        manager = None
        try:
            print(f"[{idx}/{len(sessions)}] {session_name}...", end=" ", flush=True)
            manager = ReportManager(session_path, proxy=_proxy_for_index(idx - 1))
            success_start = await manager.start()
            if not success_start:
                print("⏭️  невалидная сессия")
                skipped_count += 1
                continue
            
            success, message = await manager.send_report(message_link, reason_code, comment)
            if success:
                print(f"✅ {message}")
                success_count += 1
            else:
                print(f"❌ {message[:40]}")
                error_count += 1
            
            await manager.disconnect()
            await asyncio.sleep(0.5)
            
        except errors.AuthKeyUnregisteredError:
            print("⏭️  невалидная сессия")
            skipped_count += 1
            if manager:
                try:
                    await manager.disconnect()
                except Exception:
                    pass
        except KeyboardInterrupt:
            print("\n\n⚠️  Операция прервана пользователем")
            if manager:
                try:
                    await manager.disconnect()
                except Exception:
                    pass
            return
        except Exception as e:
            error_msg = str(e)
            if any(keyword in error_msg.lower() for keyword in ["phone", "not authorized", "auth", "session", "login"]):
                print("⏭️  невалидная сессия")
                skipped_count += 1
            else:
                logger.error(f"Ошибка в {session_name}: {e}", exc_info=True)
                print(f"❌ ошибка: {error_msg[:30]}")
                error_count += 1
            if manager:
                try:
                    await manager.disconnect()
                except Exception:
                    pass
    
    print("─" * 50)
    print(f"\n📊 Результат:")
    print(f"   ✅ Успешно: {success_count}")
    print(f"   ❌ Ошибок: {error_count}")
    print(f"   ⏭️  Пропущено: {skipped_count}")
    print(f"   📊 Всего: {len(sessions)}")
async def main():
    """Главная функция"""
    print("\n" + "=" * 50)
    print("🤖 BOTNET - Управление профилями Telegram")
    print("=" * 50)
    ensure_sessions_dir()
    print(f"📁 Папка сессий: {BOTNET_SESSIONS_DIR}/")
    
    while True:
        try:
            print_menu()
            choice = input("Выберите действие: ").strip()
            
            if choice == '1':
                await change_name_menu()
            elif choice == '2':
                await change_name_all_menu()
            elif choice == '3':
                await change_photo_menu()
            elif choice == '4':
                await change_photo_all_menu()
            elif choice == '5':
                await delete_photo_menu()
            elif choice == '6':
                await set_random_username_menu()
            elif choice == '7':
                await set_random_username_all_menu()
            elif choice == '8':
                await show_profile_menu()
            elif choice == '9':
                await check_all_sessions_menu()
            elif choice == '10':
                await remove_invalid_sessions_menu()
            elif choice == '11':
                await join_chat_menu()
            elif choice == '12':
                await join_chat_all_menu()
            elif choice == '13':
                await send_message_menu()
            elif choice == '14':
                await send_message_all_menu()
            elif choice == '15':
                await start_bot_menu()
            elif choice == '16':
                await start_bot_all_menu()
            elif choice == '17':
                await send_report_menu()
            elif choice == '18':
                await send_report_all_menu()
            elif choice == '21':
                await leave_chat_menu()
            elif choice == '22':
                await leave_chat_all_menu()
            elif choice == '30':
                await inviter_menu()
            elif choice == '31':
                await inviter_all_menu()
            elif choice == '23':
                await reset_other_sessions_menu()
            elif choice == '24':
                from BOTNET.mass_sender_menu import smart_mass_send_menu
                await smart_mass_send_menu()
            elif choice == '26':
                from BOTNET.bot_parser_menu import bot_parser_menu
                await bot_parser_menu()
            elif choice == '27':
                await change_bio_menu()
            elif choice == '28':
                await change_bio_all_menu()
            elif choice == '29':
                await change_settings_menu()
            elif choice == '0':
                print("\n👋 До свидания!\n")
                break
            else:
                print("\n❌ Неверный выбор. Попробуйте снова.\n")
        except KeyboardInterrupt:
            print("\n\n👋 До свидания!\n")
            break
        except Exception as e:
            logger.error(f"Ошибка в меню: {e}", exc_info=True)
            print(f"\n❌ Ошибка: {e}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 До свидания!\n")
