import asyncio
from typing import List, Dict, Tuple
from BOTNET.mass_sender import MassSender
from BOTNET.botnet import get_session_files, BOTNET_SESSIONS_DIR, print_sessions, _proxy_for_index
from utils.logger import get_logger
from telethon import errors

logger = get_logger(__name__)

async def smart_mass_send_menu():
    print("\n" + "=" * 50)
    print("📢 Умная рассылка по ссылкам")
    print("=" * 50)
    
    sessions = get_session_files()
    if not sessions:
        print(f"\n❌ Сессии не найдены в папке {BOTNET_SESSIONS_DIR}/")
        return
    
    links_post = input("\n🔗 Введите ссылку на пост с ссылками (например, https://t.me/kids_project/3): ").strip()
    if not links_post:
        print("❌ Ссылка не может быть пустой")
        return
    
    text_post = input("\n📝 Введите ссылку на пост с текстом сообщения (например, https://t.me/kidhik/38): ").strip()
    if not text_post:
        print("❌ Ссылка не может быть пустой")
        return
    
    print("\n🔄 Парсинг постов...")
    parser = MassSender(sessions[0][1], proxy=_proxy_for_index(0))
    success_start = await parser.start()
    
    if not success_start:
        print("❌ Не удалось подключиться к сессии для парсинга")
        return
    
    success_links, links, msg_links = await parser.parse_post_links(links_post)
    if not success_links:
        print(f"❌ Ошибка парсинга ссылок: {msg_links}")
        await parser.disconnect()
        return
    
    print(f"✅ Найдено {len(links)} ссылок")
    
    success_text, text, msg_text = await parser.parse_post_text(text_post)
    if not success_text:
        print(f"❌ Ошибка парсинга текста: {msg_text}")
        await parser.disconnect()
        return
    
    print(f"✅ Получен текст сообщения ({len(text)} символов)")
    await parser.disconnect()
    
    print(f"\n📊 Информация:")
    print(f"   • Ссылок: {len(links)}")
    print(f"   • Аккаунтов: {len(sessions)}")
    print(f"   • Текст: {text[:50]}...")
    
    confirm = input("\n⚠️  Начать рассылку? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Отменено")
        return
    
    print(f"\n🔄 Начинаю цикличную рассылку через {len(sessions)} аккаунтов по {len(links)} ссылкам...")
    print("─" * 50)
    
    success_count = 0
    error_count = 0
    skipped_count = 0
    total_operations = len(sessions) * len(links)
    current_operation = 0
    
    for idx, (session_name, session_path) in enumerate(sessions):
        sender = None
        try:
            print(f"\n[{idx+1}/{len(sessions)}] {session_name}:")
            
            sender = MassSender(session_path, proxy=_proxy_for_index(idx))
            success_start = await sender.start()
            
            if not success_start:
                print("   ⏭️  невалидная сессия, пропускаю")
                skipped_count += len(links)
                continue
            
            account_success = 0
            account_errors = 0
            account_skipped = 0
            
            for link_idx, chat_link in enumerate(links):
                current_operation += 1
                try:
                    print(f"   [{link_idx+1}/{len(links)}] {chat_link}...", end=" ", flush=True)
                    
                    join_success, join_msg, requires_approval = await sender.join_chat(chat_link)
                    if not join_success:
                        if requires_approval:
                            print(f"⏭️  Требуется заявка")
                            account_skipped += 1
                            skipped_count += 1
                        else:
                            print(f"❌ {join_msg[:30]}")
                            account_errors += 1
                            error_count += 1
                        await asyncio.sleep(1)
                        continue
                    
                    send_success, send_msg = await sender.send_message(chat_link, text)
                    if send_success:
                        print(f"✅ {send_msg[:30]}")
                        account_success += 1
                        success_count += 1
                    else:
                        print(f"⚠️  {send_msg[:30]}")
                        account_errors += 1
                        error_count += 1
                    
                    await asyncio.sleep(2)
                    
                except errors.FloodWaitError as e:
                    wait_time = e.seconds
                    if wait_time > 300:
                        print(f"⏭️  FloodWait {wait_time} сек (слишком долго)")
                        account_skipped += 1
                        skipped_count += 1
                    else:
                        print(f"⏳ FloodWait {wait_time} сек, жду...")
                        await asyncio.sleep(wait_time)
                        try:
                            join_success, join_msg, requires_approval = await sender.join_chat(chat_link)
                            if join_success:
                                send_success, send_msg = await sender.send_message(chat_link, text)
                                if send_success:
                                    print(f"✅ {send_msg[:30]}")
                                    account_success += 1
                                    success_count += 1
                                else:
                                    print(f"⚠️  {send_msg[:30]}")
                                    account_errors += 1
                                    error_count += 1
                            else:
                                if requires_approval:
                                    print(f"⏭️  Требуется заявка")
                                    account_skipped += 1
                                    skipped_count += 1
                                else:
                                    print(f"❌ {join_msg[:30]}")
                                    account_errors += 1
                                    error_count += 1
                        except Exception as retry_error:
                            print(f"❌ ошибка после ожидания: {str(retry_error)[:30]}")
                            account_errors += 1
                            error_count += 1
                except Exception as e:
                    error_msg = str(e)
                    if "wait" in error_msg.lower() and "second" in error_msg.lower():
                        import re
                        wait_match = re.search(r'(\d+)\s*second', error_msg.lower())
                        if wait_match:
                            wait_time = int(wait_match.group(1))
                            if wait_time > 300:
                                print(f"⏭️  FloodWait {wait_time} сек (слишком долго)")
                                account_skipped += 1
                                skipped_count += 1
                            else:
                                print(f"⏳ FloodWait {wait_time} сек, жду...")
                                await asyncio.sleep(wait_time)
                                continue
                    print(f"❌ ошибка: {error_msg[:30]}")
                    account_errors += 1
                    error_count += 1
                    logger.error(f"Ошибка при обработке {chat_link} для {session_name}: {e}", exc_info=True)
                    await asyncio.sleep(1)
            
            print(f"   📊 Аккаунт: ✅ {account_success} | ❌ {account_errors} | ⏭️  {account_skipped}")
            
            await sender.disconnect()
            await asyncio.sleep(2)
            
        except errors.AuthKeyUnregisteredError:
            print("⏭️  невалидная сессия")
            skipped_count += 1
            if sender:
                try:
                    await sender.disconnect()
                except Exception:
                    pass
        except KeyboardInterrupt:
            print("\n\n⚠️  Операция прервана пользователем")
            if sender:
                try:
                    await sender.disconnect()
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
            if sender:
                try:
                    await sender.disconnect()
                except Exception:
                    pass
    
    print("─" * 50)
    print(f"\n📊 Итоговый результат:")
    print(f"   ✅ Успешно: {success_count}")
    print(f"   ❌ Ошибок: {error_count}")
    print(f"   ⏭️  Пропущено: {skipped_count}")
    print(f"   📊 Всего операций: {total_operations} ({len(sessions)} аккаунтов × {len(links)} ссылок)")
