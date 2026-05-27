import os
import asyncio
import re
from typing import List, Tuple, Optional
from telethon import TelegramClient, errors
from telethon.tl.types import Channel, Chat, User

from core.session_manager import SessionManager
from utils.logger import get_logger

logger = get_logger(__name__)

class BotParser:
    
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
            logger.info("Клиент парсера бота запущен")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка запуска: {e}")
            return False
    
    async def parse_bot_chats(self, bot_username: str = "en_SearchBot", max_chats: int = 50) -> Tuple[bool, List[str], str]:
        if not self.started:
            return False, [], "Клиент не запущен"
        
        try:
            if bot_username.startswith('@'):
                bot_username = bot_username[1:]
            
            try:
                bot = await self.client.get_entity(bot_username)
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower() or "cannot find" in error_msg.lower():
                    return False, [], f"Бот @{bot_username} не найден"
                return False, [], f"Ошибка получения бота: {error_msg[:50]}"
            
            if not isinstance(bot, User) or not bot.bot:
                return False, [], f"@{bot_username} не является ботом"
            
            try:
                await self.client.send_message(bot, '/start')
                logger.info(f"✅ Отправлен /start боту @{bot_username}")
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"⚠️  Ошибка отправки /start: {e}")
            
            logger.info(f"🔄 Отправляю /rand боту @{bot_username}...")
            for rand_attempt in range(5):
                try:
                    await self.client.send_message(bot, '/rand')
                    logger.info(f"✅ [{rand_attempt+1}/5] Отправлен /rand боту @{bot_username}")
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.warning(f"⚠️  Ошибка отправки /rand (попытка {rand_attempt+1}): {e}")
                    await asyncio.sleep(1)
            
            chats = []
            processed_message_ids = set()
            
            logger.info(f"🔄 Получаю сообщения от бота @{bot_username}...")
            
            try:
                messages = await self.client.get_messages(bot, limit=50)
                logger.info(f"✅ Получено {len(messages)} сообщений от бота")
                
                if not messages:
                    logger.warning("⚠️  Бот не отправил сообщений")
                    return False, [], "Бот не отправил сообщений. Попробуйте позже."
                
                for message in messages:
                    if not message or message.id in processed_message_ids:
                        continue
                    
                    processed_message_ids.add(message.id)
                    
                    text = message.text or message.message or ""
                    if not text:
                        continue
                    
                    logger.debug(f"📄 Обрабатываю сообщение {message.id}: {text[:50]}...")
                    
                    chat_links = []
                    
                    url_pattern = r'(?:https?://)?(?:www\.)?t\.me/([a-zA-Z0-9_]+)'
                    found_links = re.findall(url_pattern, text)
                    
                    for link in found_links:
                        full_link = f"https://t.me/{link}"
                        if full_link not in chat_links:
                            chat_links.append(full_link)
                    
                    if hasattr(message, 'entities') and message.entities:
                        from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl
                        
                        for entity in message.entities:
                            if isinstance(entity, MessageEntityUrl):
                                url_start = entity.offset
                                url_length = entity.length
                                if url_start + url_length <= len(text):
                                    url_text = text[url_start:url_start + url_length]
                                    
                                    found_links = re.findall(url_pattern, url_text)
                                    for link in found_links:
                                        full_link = f"https://t.me/{link}"
                                        if full_link not in chat_links:
                                            chat_links.append(full_link)
                                        
                            elif isinstance(entity, MessageEntityTextUrl):
                                url = entity.url
                                found_links = re.findall(url_pattern, url)
                                for link in found_links:
                                    full_link = f"https://t.me/{link}"
                                    if full_link not in chat_links:
                                        chat_links.append(full_link)
                    
                    for chat_link in chat_links:
                        if chat_link in chats:
                            continue
                        
                        match = re.match(r'https?://t\.me/([a-zA-Z0-9_]+)', chat_link)
                        if not match:
                            continue
                        
                        chat_username = match.group(1)
                        
                        try:
                            entity = await asyncio.wait_for(
                                self.client.get_entity(chat_username),
                                timeout=10.0
                            )
                            
                            if isinstance(entity, Chat):
                                chats.append(chat_link)
                                logger.info(f"✅ Найден чат: {chat_link}")
                            elif isinstance(entity, Channel):
                                if not getattr(entity, 'broadcast', True):
                                    chats.append(chat_link)
                                    logger.info(f"✅ Найден чат (группа): {chat_link}")
                                else:
                                    logger.debug(f"⏭️  Пропущен канал: {chat_link}")
                            
                            if len(chats) >= max_chats:
                                logger.info(f"✅ Достигнут лимит чатов: {max_chats}")
                                break
                                
                        except asyncio.TimeoutError:
                            logger.warning(f"⏱️  Таймаут при проверке {chat_link}")
                            continue
                        except Exception as e:
                            logger.debug(f"⏭️  Не удалось проверить {chat_link}: {str(e)[:50]}")
                            continue
                    
                    if len(chats) >= max_chats:
                        break
                
                logger.info(f"✅ Найдено {len(chats)} чатов после обработки всех сообщений")
                
            except Exception as e:
                error_msg = f"Ошибка получения сообщений от бота: {e}"
                logger.error(error_msg, exc_info=True)
                return False, [], error_msg
            
            if not chats:
                return False, [], "Не найдено чатов в ответах бота"
            
            logger.info(f"Найдено {len(chats)} чатов из бота @{bot_username}")
            return True, chats, f"Найдено {len(chats)} чатов"
                
        except Exception as e:
            error_msg = f"Ошибка парсинга бота: {str(e)[:50]}"
            logger.error(error_msg)
            return False, [], error_msg
    
    async def parse_post_text(self, post_link: str) -> Tuple[bool, Optional[str], str]:
        if not self.started:
            return False, None, "Клиент не запущен"
        
        try:
            match_public = re.match(r'https?://t\.me/([^/]+)/(\d+)', post_link)
            match_private = re.match(r'https?://t\.me/c/(\d+)/(\d+)', post_link)
            
            message = None
            chat_id = None
            channel_username = None
            
            if match_private:
                chat_id_raw = int(match_private.group(1))
                message_id = int(match_private.group(2))
                
                if chat_id_raw > 1000000000000:
                    chat_id = -int(str(chat_id_raw)[3:]) if len(str(chat_id_raw)) > 12 else -chat_id_raw
                else:
                    chat_id = -chat_id_raw
                
                try:
                    chat_entity = await self.client.get_entity(chat_id)
                    message = await self.client.get_messages(chat_entity, ids=message_id)
                except Exception:
                    try:
                        chat_entity = await self.client.get_entity(chat_id_raw)
                        message = await self.client.get_messages(chat_entity, ids=message_id)
                    except Exception as e:
                        return False, None, f"Ошибка получения поста: {str(e)[:50]}"
            elif match_public:
                channel_username = match_public.group(1)
                message_id = int(match_public.group(2))
                
                channel = await self.client.get_entity(channel_username)
                message = await self.client.get_messages(channel, ids=message_id)
            else:
                return False, None, "Неверный формат ссылки. Используйте: https://t.me/channel/message_id или https://t.me/c/chat_id/message_id"
            
            if not message:
                if match_private:
                    return False, None, f"Сообщение {message_id} не найдено в чате {chat_id}"
                else:
                    return False, None, f"Сообщение {message_id} не найдено в канале {channel_username}"
            
            text = message.text or message.message or ""
            
            if not text:
                return False, None, "В посте нет текста"
            
            logger.info(f"Получен текст из поста ({len(text)} символов)")
            return True, text, "Текст успешно получен"
                
        except Exception as e:
            error_msg = f"Ошибка парсинга ссылки: {str(e)[:50]}"
            logger.error(error_msg)
            return False, None, error_msg
    
    async def join_chat(self, chat_link: str) -> Tuple[bool, str, bool]:
        if not self.started:
            return False, "Клиент не запущен", False
        
        try:
            if chat_link.startswith('https://t.me/'):
                chat_link = chat_link.replace('https://t.me/', '')
            elif chat_link.startswith('http://t.me/'):
                chat_link = chat_link.replace('http://t.me/', '')
            elif chat_link.startswith('t.me/'):
                chat_link = chat_link.replace('t.me/', '')
            
            if chat_link.startswith('@'):
                chat_link = chat_link[1:]
            
            try:
                entity = await self.client.get_entity(chat_link)
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower() or "cannot find" in error_msg.lower():
                    return False, f"Чат {chat_link} не найден", False
                return False, f"Ошибка получения чата: {error_msg[:50]}", False
            
            if isinstance(entity, Channel):
                if getattr(entity, 'broadcast', True):
                    return False, f"{chat_link} является каналом, пропускаю", False
                try:
                    from telethon.tl.functions.channels import JoinChannelRequest
                    await self.client(JoinChannelRequest(entity))
                    username = getattr(entity, 'username', None) or f"ID:{entity.id}"
                    logger.info(f"✅ Присоединился к группе: {username}")
                    return True, f"Присоединился к группе @{username}", False
                except errors.UserAlreadyParticipantError:
                    username = getattr(entity, 'username', None) or f"ID:{entity.id}"
                    logger.info(f"✅ Уже участник группы: {username}")
                    return True, f"Уже участник группы @{username}", False
                except errors.ChatWriteForbiddenError:
                    return False, f"Требуется заявка для {chat_link}", True
                except errors.InviteRequestSentError:
                    return False, f"Заявка отправлена, требуется одобрение для {chat_link}", True
                except Exception as join_error:
                    error_msg = str(join_error).lower()
                    if any(keyword in error_msg for keyword in ["request", "approval", "заявк", "invite", "permission", "forbidden"]):
                        return False, f"Требуется заявка для {chat_link}", True
                    return False, f"Ошибка присоединения: {error_msg[:50]}", False
            elif isinstance(entity, Chat):
                try:
                    from telethon.tl.functions.messages import ImportChatInviteRequest
                    await self.client.get_messages(entity, limit=1)
                    logger.info(f"✅ Доступ к чату получен: {chat_link}")
                    return True, f"Доступ к чату @{chat_link} получен", False
                except Exception as e:
                    error_msg = str(e)
                    if "request" in error_msg.lower() or "approval" in error_msg.lower():
                        return False, f"Требуется заявка для {chat_link}", True
                    return False, f"Ошибка доступа: {error_msg[:50]}", False
            else:
                return False, f"{chat_link} не является чатом", False
                
        except Exception as e:
            error_msg = f"Ошибка присоединения к {chat_link}: {str(e)[:50]}"
            logger.error(error_msg)
            return False, error_msg, False
    
    async def send_message(self, chat_link: str, text: str) -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        try:
            if chat_link.startswith('https://t.me/'):
                chat_link = chat_link.replace('https://t.me/', '')
            elif chat_link.startswith('http://t.me/'):
                chat_link = chat_link.replace('http://t.me/', '')
            elif chat_link.startswith('t.me/'):
                chat_link = chat_link.replace('t.me/', '')
            
            if chat_link.startswith('@'):
                chat_link = chat_link[1:]
            
            try:
                entity = await self.client.get_entity(chat_link)
                
                try:
                    sent_message = await self.client.send_message(entity, text)
                    username = getattr(entity, 'username', None) or f"ID:{getattr(entity, 'id', 'unknown')}"
                    logger.info(f"✅ Отправил сообщение в {username}")
                    return True, f"Сообщение отправлено в {chat_link}"
                except Exception as send_err:
                    error_str = str(send_err).lower()
                    if "messageempty" in error_str or "missing message mapping" in error_str:
                        username = getattr(entity, 'username', None) or f"ID:{getattr(entity, 'id', 'unknown')}"
                        logger.info(f"✅ Сообщение отправлено в {username} (MessageEmpty в Updates)")
                        return True, f"Сообщение отправлено в {chat_link}"
                    raise
                    
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                if wait_time > 300:
                    return False, f"FloodWait {wait_time} сек (слишком долго)"
                logger.info(f"⏳ FloodWait {wait_time} секунд для отправки в {chat_link}, жду...")
                await asyncio.sleep(wait_time)
                try:
                    sent_message = await self.client.send_message(entity, text)
                    return True, f"Сообщение отправлено в {chat_link}"
                except Exception as retry_err:
                    error_str = str(retry_err).lower()
                    if "messageempty" in error_str or "missing message mapping" in error_str:
                        return True, f"Сообщение отправлено в {chat_link}"
                    return False, f"Ошибка после ожидания: {str(retry_err)[:50]}"
                except Exception as retry_error:
                    return False, f"Ошибка после ожидания: {str(retry_error)[:50]}"
            except errors.ChatWriteForbiddenError:
                return False, f"Нет прав на отправку в {chat_link}"
            except errors.UserPrivacyRestrictedError:
                return False, f"Приватность ограничена для {chat_link}"
            except Exception as e:
                error_msg = str(e)
                if "banned" in error_msg.lower():
                    return False, f"You're banned"
                if "as username" in error_msg.lower():
                    return False, f"Чат {chat_link} не найден"
                return False, f"Ошибка отправки: {error_msg[:50]}"
                
        except Exception as e:
            error_msg = f"Ошибка отправки в {chat_link}: {str(e)[:50]}"
            logger.error(error_msg)
            return False, error_msg
    
    async def disconnect(self):
        if self.started:
            await self.client.disconnect()
            self.started = False
            logger.info("Клиент парсера бота отключен")
