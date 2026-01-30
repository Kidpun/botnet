import os
import asyncio
from typing import List, Tuple, Optional
from telethon import TelegramClient, errors
from telethon.tl.types import User

from core.session_manager import SessionManager
from utils.logger import get_logger

logger = get_logger(__name__)

class SessionChecker:
    def __init__(self):
        self.session_manager = SessionManager()
        self.api_id = self.session_manager.api_id
        self.api_hash = self.session_manager.api_hash
    
    async def check_session(self, session_path: str, timeout: int = 10, proxy=None) -> Tuple[bool, Optional[str], Optional[str]]:
        if not os.path.exists(session_path + '.session'):
            return False, None, "Файл сессии не найден"
        client = None
        try:
            client = TelegramClient(session_path, self.api_id, self.api_hash, proxy=proxy)
            await asyncio.wait_for(client.start(), timeout=timeout)
            me = await client.get_me()
            
            if not me:
                return False, None, "Сессия не авторизована"
            
            phone = getattr(me, 'phone', None)
            return True, phone, None
            
        except asyncio.TimeoutError:
            return False, None, f"Таймаут подключения ({timeout}s)"
        except errors.AuthKeyUnregisteredError:
            return False, None, "Сессия недействительна (AuthKeyUnregisteredError)"
        except errors.FloodWaitError as e:
            return False, None, f"FloodWait: нужно подождать {e.seconds} секунд"
        except errors.SessionPasswordNeededError:
            return False, None, "Требуется пароль 2FA"
        except Exception as e:
            return False, None, f"Ошибка: {str(e)[:50]}"
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
    
    async def check_all_sessions(self, sessions_dir: str, timeout: int = 10, get_proxy_for_index=None) -> List[Tuple[str, bool, Optional[str], Optional[str]]]:
        if not os.path.exists(sessions_dir):
            return []
        sessions = []
        for file in os.listdir(sessions_dir):
            if file.endswith('.session'):
                session_name = file.replace('.session', '')
                session_path = os.path.join(sessions_dir, session_name)
                sessions.append((session_name, session_path))
        if not sessions:
            return []
        results = []
        print(f"\n🔄 Проверяю {len(sessions)} сессий...")
        semaphore = asyncio.Semaphore(5)

        async def check_with_semaphore(session_name, session_path, idx):
            async with semaphore:
                proxy = get_proxy_for_index(idx) if get_proxy_for_index else None
                is_valid, phone, error = await self.check_session(session_path, timeout, proxy=proxy)
                status = "✅" if is_valid else "❌"
                print(f"  {status} {session_name}: {phone or error}")
                return (session_name, is_valid, phone, error)
        
        tasks = [check_with_semaphore(name, path, idx) for idx, (name, path) in enumerate(sessions)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Ошибка при проверке сессии: {result}")
                continue
            final_results.append(result)
        
        return final_results
    
    def remove_invalid_sessions(self, sessions_dir: str, check_results: List[Tuple[str, bool, Optional[str], Optional[str]]]) -> int:
        removed_count = 0
        for session_name, is_valid, _, _ in check_results:
            if not is_valid:
                session_file = os.path.join(sessions_dir, f"{session_name}.session")
                try:
                    if os.path.exists(session_file):
                        os.remove(session_file)
                        removed_count += 1
                        logger.info(f"Удалена невалидная сессия: {session_name}")
                except Exception as e:
                    logger.error(f"Ошибка удаления {session_name}: {e}")
        
        return removed_count
