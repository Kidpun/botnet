import os
import re
import asyncio
from typing import Optional, Tuple, List
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest, AddChatUserRequest, DeleteChatUserRequest
from telethon.tl.functions.channels import JoinChannelRequest, InviteToChannelRequest, LeaveChannelRequest
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.types import InputUser, InputChannel, Channel, Chat

from core.session_manager import SessionManager
from utils.logger import get_logger

logger = get_logger(__name__)

class ChatManager:
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
    
    def _parse_invite_link(self, link: str) -> Tuple[Optional[str], str]:
        link = link.strip()
        link = link.replace('\n', '').replace('\r', '')
        if 'joinchat' in link:
            match = re.search(r'joinchat/([a-zA-Z0-9_-]+)', link)
            if match:
                return match.group(1), 'invite'
        if 't.me/+' in link:
            match = re.search(r't\.me/\+(.+)', link)
            if match:
                return match.group(1), 'invite'
        if 't.me/' in link:
            match = re.search(r't\.me/([a-zA-Z0-9_]+)', link)
            if match:
                username = match.group(1)
                if len(username) >= 22 and re.match(r'^[a-zA-Z0-9_-]+$', username):
                    return username, 'invite'
                return username, 'username'
        if link.startswith('@'):
            return link[1:], 'username'
        if re.match(r'^[a-zA-Z0-9_-]{22,}$', link):
            return link, 'invite'
        if re.match(r'^[a-zA-Z0-9_]{5,}$', link):
            return link, 'username'
        
        return None, 'unknown'
    
    async def join_chat(self, invite_link: str) -> Tuple[bool, str, Optional[str]]:
        if not self.started:
            return False, "Клиент не запущен", None
        
        try:
            parsed, link_type = self._parse_invite_link(invite_link)
            if not parsed:
                return False, "Не удалось распарсить ссылку", None
            if link_type == 'username':
                try:
                    entity = await self.client.get_entity(parsed)
                    await self.client(JoinChannelRequest(entity))
                    chat_username = getattr(entity, 'username', None)
                    logger.info(f"✅ Присоединился к чату: {parsed}")
                    return True, f"Успешно присоединился к @{chat_username or parsed}", chat_username or parsed
                except errors.UsernameNotOccupiedError:
                    return False, f"Username @{parsed} не найден", None
                except errors.UserAlreadyParticipantError:
                    return True, f"Уже участник @{parsed}", parsed
                except errors.FloodWaitError as e:
                    return False, f"FloodWait: нужно подождать {e.seconds} секунд", None
                except Exception as e:
                    error_msg = f"Ошибка присоединения к @{parsed}: {str(e)[:50]}"
                    logger.error(error_msg)
                    return False, error_msg, None
            elif link_type == 'invite':
                try:
                    invite = await self.client(CheckChatInviteRequest(parsed))
                    updates = await self.client(ImportChatInviteRequest(parsed))
                    chat_username = None
                    if hasattr(updates, 'chats') and updates.chats:
                        for chat in updates.chats:
                            chat_username = getattr(chat, 'username', None)
                            break
                    
                    logger.info(f"✅ Присоединился к чату по invite")
                    return True, "Успешно присоединился к чату", chat_username
                    
                except errors.InviteHashExpiredError:
                    return False, "Ссылка-приглашение устарела", None
                except errors.UserAlreadyParticipantError:
                    return True, "Уже участник этого чата", None
                except errors.InviteHashInvalidError:
                    return False, "Недействительная ссылка-приглашение", None
                except errors.FloodWaitError as e:
                    return False, f"FloodWait: нужно подождать {e.seconds} секунд", None
                except Exception as e:
                    error_msg = f"Ошибка присоединения: {str(e)[:50]}"
                    logger.error(error_msg)
                    return False, error_msg, None
            else:
                return False, "Неизвестный тип ссылки", None
                
        except Exception as e:
            error_msg = f"Ошибка: {str(e)[:50]}"
            logger.error(error_msg)
            return False, error_msg, None
    
    async def send_message(self, chat_identifier: str, message_text: str, join_if_needed: bool = True) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        if not message_text:
            return False, "Сообщение не может быть пустым"
        
        try:
            parsed, link_type = self._parse_invite_link(chat_identifier)
            if not parsed:
                return False, "Не удалось распарсить идентификатор чата"
            if link_type == 'invite' and join_if_needed:
                success, join_msg, chat_username = await self.join_chat(chat_identifier)
                if not success:
                    return False, f"Не удалось присоединиться: {join_msg}"
                if chat_username:
                    parsed = chat_username
                    link_type = 'username'
            try:
                entity = await self.client.get_entity(parsed)
            except errors.UsernameNotOccupiedError:
                return False, f"Чат @{parsed} не найден"
            except Exception as e:
                return False, f"Ошибка получения чата: {str(e)[:50]}"
            await self.client.send_message(entity, message_text)
            logger.info(f"✅ Сообщение отправлено в {parsed}")
            return True, f"Сообщение успешно отправлено в @{parsed}"
            
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except errors.ChatWriteForbiddenError:
            return False, "Нет прав на отправку сообщений в этот чат"
        except Exception as e:
            error_msg = f"Ошибка отправки: {str(e)[:50]}"
            logger.error(error_msg)
            return False, error_msg
    
    def _parse_bot_link(self, bot_link: str) -> Tuple[Optional[str], Optional[str]]:
        bot_link = bot_link.strip().replace('\n', '').replace('\r', '')
        if '.t.me?' in bot_link and 'start' in bot_link:
            match = re.search(r'([a-zA-Z0-9_]+)\.t\.me\?start(?:group)?=(.+)', bot_link)
            if match:
                bot_username = match.group(1)
                referral_code = match.group(2)
                return bot_username, referral_code
        if '.t.me' in bot_link and '?' not in bot_link:
            match = re.search(r'([a-zA-Z0-9_]+)\.t\.me', bot_link)
            if match:
                return match.group(1), None
        if 't.me/' in bot_link and '?start' in bot_link:
            match = re.search(r't\.me/([a-zA-Z0-9_]+)\?start(?:group)?=(.+)', bot_link)
            if match:
                bot_username = match.group(1)
                referral_code = match.group(2)
                return bot_username, referral_code
        if 't.me/' in bot_link and '?' not in bot_link:
            match = re.search(r't\.me/([a-zA-Z0-9_]+)', bot_link)
            if match:
                return match.group(1), None
        if bot_link.startswith('@'):
            parts = bot_link[1:].split(' ', 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            return parts[0], None
        if re.match(r'^[a-zA-Z0-9_]{5,}$', bot_link):
            return bot_link, None
        
        return None, None
    
    async def start_bot(self, bot_link: str, referral_code: Optional[str] = None) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        try:
            bot_username, code_from_link = self._parse_bot_link(bot_link)
            if not bot_username:
                return False, "Не удалось распарсить ссылку на бота"
            referral_code = code_from_link or referral_code
            if referral_code:
                start_command = f"/start {referral_code}"
            else:
                start_command = "/start"
            try:
                bot_entity = await self.client.get_entity(bot_username)
            except errors.UsernameNotOccupiedError:
                return False, f"Бот @{bot_username} не найден"
            except Exception as e:
                return False, f"Ошибка получения бота: {str(e)[:50]}"
            try:
                await self.client.send_message(bot_entity, start_command)
                if referral_code:
                    logger.info(f"✅ Отправлен /start с кодом {referral_code} боту @{bot_username}")
                    return True, f"Успешно отправлен /start с кодом {referral_code} боту @{bot_username}"
                else:
                    logger.info(f"✅ Отправлен /start боту @{bot_username}")
                    return True, f"Успешно отправлен /start боту @{bot_username}"
            except errors.FloodWaitError as e:
                error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
                logger.warning(error_msg)
                return False, error_msg
            except Exception as e:
                error_msg = f"Ошибка отправки: {str(e)[:50]}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Ошибка: {str(e)[:50]}"
            logger.error(error_msg)
            return False, error_msg
    
    async def get_contacts(self) -> list:
        if not self.started:
            return []
        
        try:
            contacts_result = await asyncio.wait_for(
                self.client(GetContactsRequest(hash=0)),
                timeout=30.0
            )
            if hasattr(contacts_result, 'users'):
                contacts = []
                for user in contacts_result.users:
                    if not user.bot and not user.is_self:
                        contacts.append(user)
                logger.info(f"Получено {len(contacts)} контактов")
                return contacts
            else:
                logger.info("Контакты не изменены (ContactsNotModified)")
                return []
        except asyncio.TimeoutError:
            logger.error("Таймаут при получении контактов")
            return []
        except Exception as e:
            logger.error(f"Ошибка получения контактов: {e}")
            return []
    
    async def invite_users_to_chat(
        self,
        chat_identifier: str,
        usernames: List[str],
        delay_sec: float = 2.0,
    ) -> Tuple[int, int, List[Tuple[str, str]]]:
        if not self.started:
            return 0, len(usernames), [(u, "Клиент не запущен") for u in usernames]
        invited = 0
        failed_list: List[Tuple[str, str]] = []
        try:
            chat = await self.client.get_entity(chat_identifier)
        except Exception as e:
            err = str(e)[:80]
            return 0, len(usernames), [(u, f"Чат не найден: {err}") for u in usernames]
        for username in usernames:
            username = username.strip().lstrip("@")
            if not username or username.startswith("#"):
                continue
            try:
                user_entity = await self.client.get_entity(username)
            except errors.UsernameNotOccupiedError:
                failed_list.append((username, "Юзернейм не найден"))
                continue
            except errors.UsernameInvalidError:
                failed_list.append((username, "Некорректный юзернейм"))
                continue
            except Exception as e:
                failed_list.append((username, str(e)[:50]))
                continue
            if getattr(user_entity, "bot", False):
                failed_list.append((username, "Не приглашаем ботов"))
                continue
            try:
                if isinstance(chat, Channel):
                    await self.client(InviteToChannelRequest(chat, [user_entity]))
                elif isinstance(chat, Chat):
                    await self.client(AddChatUserRequest(chat_id=chat.id, user_id=user_entity, fwd_limit=0))
                else:
                    failed_list.append((username, "Тип чата не поддерживается"))
                    continue
                invited += 1
                logger.info(f"✅ Приглашён в чат: @{username}")
            except errors.UserAlreadyParticipantError:
                invited += 1
                logger.info(f"✅ Уже в чате: @{username}")
            except errors.UserPrivacyRestrictedError:
                failed_list.append((username, "Приватность не позволяет"))
            except errors.UsersTooMuchError:
                failed_list.append((username, "Лимит участников чата"))
            except errors.FloodWaitError as e:
                failed_list.append((username, f"FloodWait {e.seconds} сек"))
                await asyncio.sleep(min(e.seconds, 60))
            except errors.ChatAdminRequiredError:
                failed_list.append((username, "Нет прав приглашать в чат"))
                break
            except Exception as e:
                failed_list.append((username, str(e)[:50]))
            if delay_sec > 0:
                await asyncio.sleep(delay_sec)
        return invited, len(failed_list), failed_list
    
    async def leave_chat(self, chat_identifier: str) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        try:
            try:
                chat = await self.client.get_entity(chat_identifier)
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower():
                    return False, f"Канал/чат не найден: {error_msg}"
                return False, f"Ошибка получения канала/чата: {error_msg[:50]}"
            if isinstance(chat, Channel):
                try:
                    await self.client(LeaveChannelRequest(chat))
                    chat_username = getattr(chat, 'username', None) or f"ID:{chat.id}"
                    logger.info(f"✅ Покинул канал: {chat_username}")
                    return True, f"Успешно покинул канал @{chat_username}"
                except errors.UserNotParticipantError:
                    return False, "Вы не являетесь участником этого канала"
                except errors.FloodWaitError as e:
                    return False, f"FloodWait: нужно подождать {e.seconds} секунд"
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Ошибка выхода из канала: {error_msg}")
                    return False, f"Ошибка: {error_msg[:50]}"
            else:
                try:
                    me = await self.client.get_me()
                    await self.client(DeleteChatUserRequest(
                        chat_id=chat.id,
                        user_id=me,
                        revoke_history=False
                    ))
                    chat_title = getattr(chat, 'title', None) or f"ID:{chat.id}"
                    logger.info(f"✅ Покинул группу: {chat_title}")
                    return True, f"Успешно покинул группу '{chat_title}'"
                except errors.UserNotParticipantError:
                    return False, "Вы не являетесь участником этой группы"
                except errors.FloodWaitError as e:
                    return False, f"FloodWait: нужно подождать {e.seconds} секунд"
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Ошибка выхода из группы: {error_msg}")
                    return False, f"Ошибка: {error_msg[:50]}"
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка выхода из чата: {error_msg}", exc_info=True)
            error_type = type(e).__name__
            return False, f"Ошибка ({error_type}): {error_msg[:50]}"
    
    async def disconnect(self):
        if self.started:
            await self.client.disconnect()
            self.started = False
            logger.info("Клиент отключен")
