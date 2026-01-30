import asyncio
from typing import List, Tuple
from BOTNET.bot_parser import BotParser
from BOTNET.botnet import get_session_files, BOTNET_SESSIONS_DIR, _proxy_for_index
from utils.logger import get_logger
from telethon import errors

logger = get_logger(__name__)

async def bot_parser_menu():
    print("\n" + "=" * 50)
    print("🤖 Парсер бота @en_SearchBot")
    print("=" * 50)
    print("\nЧто делает: бот @en_SearchBot по команде /rand присылает случайные чаты (группы).")
    print("Парсер собирает ссылки на эти чаты, затем вы указываете текст сообщения (из поста),")
    print("после чего все ваши сессии вступают в собранные чаты и отправляют туда этот текст.")
    print("─" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    max_chats_input = input("\n📊 Сколько чатов собрать у бота? (Enter = 50): ").strip()
    max_chats = 50
    if max_chats_input:
        try:
            max_chats = int(max_chats_input)
            if max_chats < 1:
                max_chats = 50
        except ValueError:
            max_chats = 50
    
    print("\n📝 Ссылка на пост — откуда взять текст сообщения для рассылки.")
    print("   Пример: https://t.me/username/123 или https://t.me/c/1234567890/1")
    text_post = input("   Введите ссылку на пост: ").strip()
    if not text_post:
        print("❌ Ссылка не может быть пустой")
        return
    
    print("\n🔄 Собираю чаты у бота @en_SearchBot...")
    parser = BotParser(sessions[0][1], proxy=_proxy_for_index(0))
    success_start = await parser.start()
    
    if not success_start:
        print("❌ Не удалось подключиться к сессии для парсинга")
        return
    
    success_chats, chats, msg_chats = await parser.parse_bot_chats("en_SearchBot", max_chats=max_chats)
    if not success_chats:
        print(f"❌ Ошибка парсинга чатов: {msg_chats}")
        await parser.disconnect()
        return
    
    print(f"✅ Найдено {len(chats)} чатов")
    
    success_text, text, msg_text = await parser.parse_post_text(text_post)
    if not success_text:
        print(f"❌ Ошибка парсинга текста: {msg_text}")
        await parser.disconnect()
        return
    
    print(f"✅ Получен текст сообщения ({len(text)} символов)")
    await parser.disconnect()
    
    print(f"\n📊 Информация:")
    print(f"   • Чатов: {len(chats)}")
    print(f"   • Аккаунтов: {len(sessions)}")
    print(f"   • Текст: {text[:50]}...")
    
    confirm = input("\n⚠️  Начать рассылку? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    print(f"\n🔄 Начинаю параллельную рассылку через {len(sessions)} аккаунтов...")
    print("─" * 50)
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    total_operations = len(sessions) * len(chats)
    
    async def process_account(session_name: str, session_path: str, account_idx: int):
        parser = None
        account_success = 0
        account_errors = 0
        account_skipped = 0
        
        try:
            parser = BotParser(session_path, proxy=_proxy_for_index(account_idx))
            success_start = await parser.start()
            
            if not success_start:
                logger.warning(f"[{account_idx+1}/{len(sessions)}] {session_name}: невалидная сессия")
                return account_success, account_errors, len(chats)
            
            async def process_single_chat(chat_link: str, chat_idx: int):
                try:
                    join_success, join_msg, requires_approval = await parser.join_chat(chat_link)
                    if not join_success:
                        if requires_approval:
                            logger.warning(f"[{account_idx+1}/{len(sessions)}] {session_name} - [{chat_idx+1}/{len(chats)}] {chat_link}: ⏭️  Требуется заявка")
                            return False, "skipped"
                        else:
                            logger.warning(f"[{account_idx+1}/{len(sessions)}] {session_name} - [{chat_idx+1}/{len(chats)}] {chat_link}: ❌ {join_msg[:30]}")
                            return False, "error"
                    
                    send_success, send_msg = await parser.send_message(chat_link, text)
                    if send_success:
                        logger.info(f"[{account_idx+1}/{len(sessions)}] {session_name} - [{chat_idx+1}/{len(chats)}] {chat_link}: ✅")
                        return True, None
                    else:
                        logger.warning(f"[{account_idx+1}/{len(sessions)}] {session_name} - [{chat_idx+1}/{len(chats)}] {chat_link}: ⚠️  {send_msg[:30]}")
                        return False, "error"
                        
                except errors.FloodWaitError as e:
                    wait_time = e.seconds
                    if wait_time > 300:
                        logger.warning(f"[{account_idx+1}/{len(sessions)}] {session_name} - [{chat_idx+1}/{len(chats)}]: ⏭️  FloodWait {wait_time} сек")
                        return False, "skipped"
                    else:
                        logger.info(f"[{account_idx+1}/{len(sessions)}] {session_name} - [{chat_idx+1}/{len(chats)}]: ⏳ FloodWait {wait_time} сек")
                        await asyncio.sleep(wait_time)
                        try:
                            join_success, join_msg, requires_approval = await parser.join_chat(chat_link)
                            if join_success:
                                send_success, send_msg = await parser.send_message(chat_link, text)
                                if send_success:
                                    return True, None
                            return False, "error"
                        except:
                            return False, "error"
                except Exception as e:
                    logger.error(f"[{account_idx+1}/{len(sessions)}] {session_name} - [{chat_idx+1}/{len(chats)}]: ❌ ошибка: {str(e)[:30]}")
                    return False, "error"
            
            semaphore = asyncio.Semaphore(10)
            
            async def process_with_limit(chat_link, chat_idx):
                async with semaphore:
                    return await process_single_chat(chat_link, chat_idx)
            
            results = await asyncio.gather(*[
                process_with_limit(chat_link, chat_idx)
                for chat_idx, chat_link in enumerate(chats)
            ], return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    account_errors += 1
                    error_count += 1
                elif isinstance(result, tuple):
                    success, error_type = result
                    if success:
                        account_success += 1
                        success_count += 1
                    elif error_type == "skipped":
                        account_skipped += 1
                        skipped_count += 1
                    else:
                        account_errors += 1
                        error_count += 1
                else:
                    account_errors += 1
                    error_count += 1
            
            logger.info(f"[{account_idx+1}/{len(sessions)}] {session_name}: ✅ {account_success} | ❌ {account_errors} | ⏭️  {account_skipped}")
            
            await parser.disconnect()
            return account_success, account_errors, account_skipped
            
        except errors.AuthKeyUnregisteredError:
            logger.warning(f"[{account_idx+1}/{len(sessions)}] {session_name}: невалидная сессия")
            return 0, 0, len(chats)
        except Exception as e:
            logger.error(f"[{account_idx+1}/{len(sessions)}] {session_name}: ошибка: {e}", exc_info=True)
            if parser:
                try:
                    await parser.disconnect()
                except:
                    pass
            return 0, 1, 0
    
    global_semaphore = asyncio.Semaphore(20)
    
    async def process_with_limit(session_name, session_path, account_idx):
        async with global_semaphore:
            return await process_account(session_name, session_path, account_idx)
    
    print("🚀 Запускаю все аккаунты параллельно...")
    try:
        results = await asyncio.gather(*[
            process_with_limit(session_name, session_path, idx)
            for idx, (session_name, session_path) in enumerate(sessions)
        ], return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                logger.error(f"Ошибка обработки аккаунта: {result}", exc_info=True)
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана пользователем")
        return
    
    print("─" * 50)
    print(f"\n📊 Итоговый результат:")
    print(f"   ✅ Успешно: {success_count}")
    print(f"   ❌ Ошибок: {error_count}")
    print(f"   ⏭️  Пропущено: {skipped_count}")
    print(f"   📊 Всего операций: {total_operations} ({len(sessions)} аккаунтов × {len(chats)} чатов)")
