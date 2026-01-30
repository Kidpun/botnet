import os
import asyncio
import random
import string
from typing import Optional, Tuple
from telethon import TelegramClient, errors
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest

from core.session_manager import SessionManager
from utils.logger import get_logger

logger = get_logger(__name__)

class ProfileManager:
    def __init__(self, session_path: str, proxy=None):
        self.session_manager = SessionManager()
        self.session_path = session_path
        self.client = TelegramClient(
            session_path,
            self.session_manager.api_id,
            self.session_manager.api_hash,
            proxy=proxy
        )
        self.started = False
    
    async def start(self) -> bool:
        if self.started:
            return True
        
        try:
            if not os.path.exists(self.session_path + '.session'):
                logger.error(f"Сессия {self.session_path}.session не найдена")
                return False
            
            await self.client.start()
            self.started = True
            logger.info(f"✅ Клиент запущен: {os.path.basename(self.session_path)}")
            return True
        except errors.AuthKeyUnregisteredError:
            logger.error(f"❌ Сессия недействительна (AuthKeyUnregisteredError)")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка запуска: {e}")
            return False
    
    async def get_current_profile(self) -> Tuple[str, str]:
        try:
            me = await self.client.get_me()
            first_name = me.first_name or ""
            last_name = me.last_name or ""
            return first_name, last_name
        except Exception as e:
            logger.error(f"Ошибка получения профиля: {e}")
            return "", ""
    
    async def change_name(self, first_name: str, last_name: str = "") -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        try:
            await self.client(UpdateProfileRequest(
                first_name=first_name,
                last_name=last_name or ""
            ))
            logger.info(f"✅ Имя изменено: {first_name} {last_name}".strip())
            return True, "Имя успешно изменено"
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Ошибка изменения имени: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def change_bio(self, bio: str) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        if len(bio) > 70:
            return False, "Описание не может быть длиннее 70 символов"
        
        try:
            me = await self.client.get_me()
            current_first_name = me.first_name or ""
            current_last_name = me.last_name or ""
            
            await self.client(UpdateProfileRequest(
                first_name=current_first_name,
                last_name=current_last_name or "",
                about=bio
            ))
            
            await asyncio.sleep(1)
            new_bio = await self.get_current_bio()
            
            if new_bio == bio:
                logger.info(f"✅ Описание изменено: {bio[:50]}...")
                return True, "Описание успешно изменено"
            else:
                logger.warning(f"⚠️  Описание отправлено, но не подтверждено. Текущее: {new_bio}")
                return True, f"Описание отправлено (проверьте вручную)"
                
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Ошибка изменения описания: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_current_bio(self) -> Optional[str]:
        if not self.started:
            return None
        
        try:
            from telethon.tl.functions.users import GetFullUserRequest
            me = await self.client.get_me()
            full_user = await self.client(GetFullUserRequest(me))
            return getattr(full_user, 'about', None) or ""
        except Exception as e:
            logger.error(f"Ошибка получения описания: {e}")
            return None
    
    async def change_photo(self, photo_path: str) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        if not os.path.exists(photo_path):
            return False, f"Файл не найден: {photo_path}"
        
        try:
            file = await self.client.upload_file(photo_path)
            await self.client(UploadProfilePhotoRequest(file=file))
            
            logger.info(f"✅ Аватарка изменена: {photo_path}")
            return True, "Аватарка успешно изменена"
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Ошибка изменения аватарки: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def delete_photo(self) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        try:
            photos = await self.client.get_profile_photos('me')
            if not photos:
                return False, "Нет фото для удаления"
            
            await self.client(DeletePhotosRequest([photos[0]]))
            logger.info("✅ Аватарка удалена")
            return True, "Аватарка успешно удалена"
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Ошибка удаления аватарки: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def change_username(self, username: str) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        if not username:
            return False, "Username не может быть пустым"
        
        username = username.lstrip('@')
        if len(username) < 5 or len(username) > 32:
            return False, "Username должен быть от 5 до 32 символов"
        
        if not all(c.isalnum() or c == '_' for c in username):
            return False, "Username может содержать только буквы, цифры и подчеркивания"
        
        try:
            await self.client(UpdateUsernameRequest(username=username))
            logger.info(f"✅ Username изменен: @{username}")
            return True, f"Username успешно изменен на @{username}"
        except errors.UsernameOccupiedError:
            error_msg = f"Username @{username} уже занят"
            logger.warning(error_msg)
            return False, error_msg
        except errors.UsernameNotModifiedError:
            error_msg = f"Username @{username} уже установлен"
            logger.warning(error_msg)
            return False, error_msg
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Ошибка изменения username: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_current_username(self) -> Optional[str]:
        if not self.started:
            return None
        
        try:
            me = await self.client.get_me()
            return getattr(me, 'username', None)
        except Exception as e:
            logger.error(f"Ошибка получения username: {e}")
            return None
    
    async def disconnect(self):
        if self.started:
            await self.client.disconnect()
            self.started = False
            logger.info("Клиент отключен")
