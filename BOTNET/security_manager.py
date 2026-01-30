import os
import asyncio
from typing import Optional, Tuple, List
from telethon import TelegramClient, errors
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest, GetPasswordRequest, UpdatePasswordSettingsRequest
from telethon.tl.types.account import PasswordInputSettings
from telethon.tl.types import InputCheckPasswordEmpty

from core.session_manager import SessionManager
from utils.logger import get_logger

logger = get_logger(__name__)

class SecurityManager:
    
    def __init__(self, session_path: str, proxy=None):
        self.session_manager = SessionManager()
        self.session_path = session_path
        self.client: Optional[TelegramClient] = None
        self.started = False
        api_id = self.session_manager.api_id
        api_hash = self.session_manager.api_hash
        self.client = TelegramClient(
            self.session_path,
            api_id,
            api_hash,
            proxy=proxy
        )
    
    async def start(self) -> bool:
        if self.started:
            return True
        
        try:
            await self.client.start()
            self.started = True
            logger.info("Клиент безопасности запущен")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка запуска: {e}")
            return False
    
    async def get_authorizations(self) -> Tuple[bool, List[dict], str]:
        if not self.started:
            return False, [], "Клиент не запущен"
        
        try:
            result = await self.client(GetAuthorizationsRequest())
            
            me = await self.client.get_me()
            current_auth_hash = getattr(result, 'current_hash', None)
            
            authorizations = []
            for auth in result.authorizations:
                auth_info = {
                    'hash': auth.hash,
                    'device_model': auth.device_model,
                    'platform': auth.platform,
                    'system_version': auth.system_version,
                    'app_name': auth.app_name,
                    'app_version': auth.app_version,
                    'country': auth.country,
                    'region': auth.region,
                    'official_app': getattr(auth, 'official_app', False),
                    'password_pending': getattr(auth, 'password_pending', False),
                    'is_current': auth.hash == current_auth_hash
                }
                authorizations.append(auth_info)
            
            logger.info(f"Найдено {len(authorizations)} активных сессий")
            return True, authorizations, f"Найдено {len(authorizations)} активных сессий"
        except Exception as e:
            error_msg = f"Ошибка получения сессий: {str(e)[:50]}"
            logger.error(error_msg)
            return False, [], error_msg
    
    async def reset_other_authorizations(self) -> Tuple[bool, str, int]:
        if not self.started:
            return False, "Клиент не запущен", 0
        
        try:
            success, authorizations, msg = await self.get_authorizations()
            if not success:
                return False, f"Не удалось получить список сессий: {msg}", 0
            
            deleted_count = 0
            errors_list = []
            
            
            for auth in authorizations:
                try:
                    auth_hash = auth['hash']
                    await self.client(ResetAuthorizationRequest(hash=auth_hash))
                    deleted_count += 1
                    logger.info(f"✅ Сессия {auth['device_model']} ({auth['platform']}) удалена")
                    await asyncio.sleep(0.5)
                except errors.FloodWaitError as e:
                    errors_list.append(f"FloodWait при удалении {auth['device_model']}: {e.seconds} сек")
                    await asyncio.sleep(e.seconds)
                except errors.AuthKeyUnregisteredError:
                    logger.debug(f"Сессия {auth['device_model']} уже удалена или недействительна")
                    pass
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ["invalid hash", "hash is invalid", "current", "active session"]):
                        logger.debug(f"Сессия {auth['device_model']} не может быть удалена (текущая или уже удалена)")
                        pass
                    else:
                        errors_list.append(f"Ошибка удаления {auth['device_model']}: {str(e)[:40]}")
                        logger.warning(f"Ошибка удаления сессии {auth['device_model']}: {e}")
            
            if deleted_count > 0:
                message = f"Удалено {deleted_count} других сессий"
                if errors_list:
                    message += f" ({len(errors_list)} ошибок)"
                return True, message, deleted_count
            else:
                if errors_list:
                    return False, f"Не удалось удалить сессии: {errors_list[0]}", 0
                return False, "Нет других сессий для удаления", 0
                
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg, 0
        except Exception as e:
            error_msg = f"Ошибка удаления сессий: {str(e)[:50]}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, 0
    
    async def get_password_info(self) -> Tuple[bool, Optional[dict], str]:
        if not self.started:
            return False, None, "Клиент не запущен"
        
        try:
            result = await self.client(GetPasswordRequest())
            
            has_password = result.has_password
            
            info = {
                'has_password': has_password,
                'hint': getattr(result, 'hint', None) if has_password else None,
            }
            
            if has_password:
                logger.info("Облачный пароль установлен")
                return True, info, f"Облачный пароль установлен (подсказка: {info.get('hint', 'нет')})"
            else:
                logger.info("Облачный пароль не установлен")
                return True, info, "Облачный пароль не установлен"
        except Exception as e:
            error_msg = f"Ошибка получения информации о пароле: {str(e)[:50]}"
            logger.error(error_msg)
            return False, None, error_msg
    
    async def set_cloud_password(self, password: str, hint: Optional[str] = None) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        if not password or len(password) < 6:
            return False, "Пароль должен быть не менее 6 символов"
        
        try:
            success, password_info, msg = await self.get_password_info()
            if not success:
                return False, f"Не удалось получить информацию о пароле: {msg}"
            
            if password_info and password_info.get('has_password'):
                return False, "Облачный пароль уже установлен. Для изменения используйте приложение Telegram"
            
            result = await self.client(GetPasswordRequest())
            
            
            try:
                from telethon.tl.types.account import PasswordInputSettings
                import hashlib
                
                algo = result.new_algo
                
                
                password_hash = None
                try:
                    if hasattr(algo, 'salt1') and hasattr(algo, 'salt2'):
                        password_bytes = password.encode('utf-8')
                        salt1 = algo.salt1
                        salt2 = algo.salt2
                        
                        hash1 = hashlib.sha256(password_bytes + salt1).digest()
                        
                        try:
                            from hashlib import pbkdf2_hmac
                            hash2 = pbkdf2_hmac('sha512', hash1, salt2, 100000)
                        except ImportError:
                            import hmac
                            hash2 = hash1
                            for _ in range(100000):
                                hash2 = hmac.new(salt2, hash2, hashlib.sha512).digest()
                        
                        password_hash = hashlib.sha256(hash2).digest()
                    else:
                        logger.warning("Неизвестный алгоритм, используем упрощенный метод")
                        password_hash = hashlib.sha256(password.encode('utf-8')).digest()
                except Exception as hash_error:
                    logger.error(f"Ошибка вычисления хеша пароля: {hash_error}")
                    return False, f"Не удалось вычислить хеш пароля. Установите пароль вручную через приложение Telegram."
                
                new_settings = PasswordInputSettings(
                    new_algo=algo,
                    new_password_hash=password_hash,
                    hint=hint or "",
                    email=None,
                    new_secure_settings=None
                )
                
                await self.client(UpdatePasswordSettingsRequest(
                    password=InputCheckPasswordEmpty(),
                    new_settings=new_settings
                ))
                
                logger.info("✅ Облачный пароль установлен")
                return True, f"Облачный пароль успешно установлен (подсказка: {hint or 'нет'})"
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Ошибка установки пароля: {error_msg}", exc_info=True)
                return False, f"Не удалось установить пароль через API. Рекомендуется установить пароль вручную через приложение Telegram. Ошибка: {error_msg[:50]}"
                
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Ошибка установки пароля: {str(e)[:50]}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    async def disconnect(self):
        if self.started:
            await self.client.disconnect()
            self.started = False
            logger.info("Клиент безопасности отключен")
