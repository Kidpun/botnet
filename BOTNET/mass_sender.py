import os
import asyncio
import re
from typing import List, Tuple, Optional, Dict
from telethon import TelegramClient, errors
from telethon.tl.types import Channel, User, Chat
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

from core.session_manager import SessionManager
from utils.logger import get_logger

logger = get_logger(__name__)

class MassSender:
    
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
            logger.info("Клиент массовой рассылки запущен")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка запуска: {e}")
            return False
    
    async def parse_post_links(self, post_link: str) -> Tuple[bool, List[str], str]:
        if not self.started:
            return False, [], "Клиент не запущен"
        
        try:
            match = re.match(r'https?://t\.me/([^/]+)/(\d+)', post_link)
            if not match:
                return False, [], "Неверный формат ссылки. Используйте: https://t.me/channel/message_id"
            
            channel_username = match.group(1)
            message_id = int(match.group(2))
            
            try:
                channel = await self.client.get_entity(channel_username)
                message = await self.client.get_messages(channel, ids=message_id)
                
                if not message:
                    return False, [], f"Сообщение {message_id} не найдено в канале {channel_username}"
                
                text = message.text or message.message or ""
                
                if not text:
                    return False, [], "В посте нет текста"
                
                links = []
                
                if hasattr(message, 'entities') and message.entities:
                    from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl
                    
                    for entity in message.entities:
                        if isinstance(entity, MessageEntityUrl):
                            url_start = entity.offset
                            url_length = entity.length
                            url_text = text[url_start:url_start + url_length]
                            
                            if 't.me' in url_text or url_text.startswith('@'):
                                if url_text.startswith('@'):
                                    clean_link = f"https://t.me/{url_text[1:]}"
                                elif not url_text.startswith('http'):
                                    clean_link = f"https://t.me/{url_text.replace('t.me/', '')}"
                                else:
                                    clean_link = url_text
                                
                                if clean_link not in links:
                                    links.append(clean_link)
                                    
                        elif isinstance(entity, MessageEntityTextUrl):
                            url = entity.url
                            
                            if 't.me' in url or url.startswith('@'):
                                if url.startswith('@'):
                                    clean_link = f"https://t.me/{url[1:]}"
                                elif not url.startswith('http'):
                                    clean_link = f"https://t.me/{url.replace('t.me/', '')}"
                                else:
                                    clean_link = url
                                
                                if clean_link not in links:
                                    links.append(clean_link)
                
                if not links:
                    lines = text.strip().split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        url_pattern = r'(?:https?://)?(?:t\.me/|@)([a-zA-Z0-9_]+)'
                        found_links = re.findall(url_pattern, line)
                        
                        for link in found_links:
                            if link.startswith('@'):
                                full_link = f"https://t.me/{link[1:]}"
                            else:
                                full_link = f"https://t.me/{link}"
                            
                            if full_link not in links:
                                links.append(full_link)
                        
                        if not found_links and line:
                            if line.startswith('http') or line.startswith('t.me/') or line.startswith('@'):
                                if not line.startswith('http'):
                                    if line.startswith('@'):
                                        line = f"https://t.me/{line[1:]}"
                                    else:
                                        line = f"https://t.me/{line}"
                                if line not in links:
                                    links.append(line)
                else:
                    lines = text.strip().split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        url_pattern = r'https?://(?:t\.me/|www\.t\.me/)([a-zA-Z0-9_]+)'
                        found_urls = re.findall(url_pattern, line)
                        
                        for url_match in found_urls:
                            full_link = f"https://t.me/{url_match}"
                            if full_link not in links:
                                links.append(full_link)
                        
                        username_pattern = r'@([a-zA-Z0-9_]+)'
                        found_usernames = re.findall(username_pattern, line)
                        
                        for username in found_usernames:
                            full_link = f"https://t.me/{username}"
                            if full_link not in links:
                                links.append(full_link)
                
                if not links:
                    return False, [], "В посте не найдено ссылок"
                
                logger.info(f"Найдено {len(links)} ссылок в посте")
                return True, links, f"Найдено {len(links)} ссылок"
                
            except errors.UsernameNotOccupiedError:
                return False, [], f"Канал {channel_username} не найден"
            except errors.ChannelPrivateError:
                return False, [], f"Канал {channel_username} приватный или недоступен"
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower():
                    return False, [], f"Канал {channel_username} не найден"
                return False, [], f"Ошибка получения поста: {error_msg[:50]}"
                
        except Exception as e:
            error_msg = f"Ошибка парсинга ссылки: {str(e)[:50]}"
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
                
                chat_id = None
                chat_entity = None
                
                try:
                    chat_entity = await self.client.get_entity(chat_id_raw)
                    message = await self.client.get_messages(chat_entity, ids=message_id)
                    chat_id = chat_id_raw
                except:
                    try:
                        chat_id = -chat_id_raw
                        chat_entity = await self.client.get_entity(chat_id)
                        message = await self.client.get_messages(chat_entity, ids=message_id)
                    except:
                        try:
                            if chat_id_raw > 1000000000:
                                chat_id = -1000000000000 + chat_id_raw
                                chat_entity = await self.client.get_entity(chat_id)
                                message = await self.client.get_messages(chat_entity, ids=message_id)
                            else:
                                raise Exception("Не удалось определить формат ID")
                        except:
                            from telethon.tl.types import PeerChannel
                            try:
                                peer = PeerChannel(-chat_id_raw)
                                message = await self.client.get_messages(peer, ids=message_id)
                                chat_id = -chat_id_raw
                            except:
                                raise Exception(f"Не удалось получить доступ к чату {chat_id_raw}")
                        
            elif match_public:
                channel_username = match_public.group(1)
                message_id = int(match_public.group(2))
                
                channel = await self.client.get_entity(channel_username)
                message = await self.client.get_messages(channel, ids=message_id)
            else:
                return False, None, "Неверный формат ссылки. Используйте: https://t.me/channel/message_id или https://t.me/c/chat_id/message_id"
            
            try:
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
                
            except errors.UsernameNotOccupiedError:
                if match_private:
                    return False, None, f"Чат {chat_id} не найден"
                return False, None, f"Канал {channel_username} не найден"
            except errors.ChannelPrivateError:
                if match_private:
                    return False, None, f"Чат {chat_id} приватный или недоступен"
                return False, None, f"Канал {channel_username} приватный или недоступен"
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower() or "cannot find" in error_msg.lower():
                    if match_private:
                        return False, None, f"Чат {chat_id} не найден или недоступен"
                    return False, None, f"Канал {channel_username} не найден"
                return False, None, f"Ошибка получения поста: {error_msg[:50]}"
                
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
                
                if isinstance(entity, Channel):
                    try:
                        from telethon.tl.functions.channels import GetFullChannelRequest
                        full_channel = await self.client(GetFullChannelRequest(entity))
                        
                        if hasattr(full_channel, 'full_chat') and hasattr(full_channel.full_chat, 'restricted'):
                            if full_channel.full_chat.restricted:
                                logger.info(f"⏭️  Канал {chat_link} требует заявку, пропускаю")
                                return False, f"Требуется заявка для {chat_link}", True
                    except:
                        pass
                    
                    try:
                        await self.client(JoinChannelRequest(entity))
                        username = getattr(entity, 'username', None) or f"ID:{entity.id}"
                        logger.info(f"✅ Присоединился к каналу: {username}")
                        return True, f"Присоединился к каналу @{username}", False
                    except errors.ChatWriteForbiddenError:
                        logger.info(f"⏭️  Канал {chat_link} требует заявку, пропускаю")
                        return False, f"Требуется заявка для {chat_link}", True
                    except errors.InviteRequestSentError:
                        logger.info(f"⏭️  Заявка отправлена в {chat_link}, но требуется одобрение")
                        return False, f"Заявка отправлена, требуется одобрение для {chat_link}", True
                elif isinstance(entity, User) and entity.bot:
                    await self.client.send_message(entity, '/start')
                    logger.info(f"✅ Запустил бота: {chat_link}")
                    return True, f"Запустил бота @{chat_link}", False
                else:
                    try:
                        await self.client(JoinChannelRequest(entity))
                        return True, f"Присоединился к {chat_link}", False
                    except errors.ChatWriteForbiddenError:
                        logger.info(f"⏭️  Группа {chat_link} требует заявку, пропускаю")
                        return False, f"Требуется заявка для {chat_link}", True
                    except Exception as join_error:
                        error_msg = str(join_error).lower()
                        if any(keyword in error_msg for keyword in ["request", "approval", "заявк", "invite", "permission", "forbidden"]):
                            logger.info(f"⏭️  Группа {chat_link} требует заявку, пропускаю")
                            return False, f"Требуется заявка для {chat_link}", True
                        try:
                            await self.client.send_message(entity, '/start')
                            return True, f"Отправил /start в {chat_link}", False
                        except:
                            raise join_error
                        
            except errors.UserAlreadyParticipantError:
                return True, f"Уже участник {chat_link}", False
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                if wait_time > 300:
                    logger.warning(f"FloodWait {wait_time} секунд для {chat_link} - слишком долго, пропускаю")
                    return False, f"FloodWait {wait_time} сек (слишком долго)", False
                logger.info(f"FloodWait {wait_time} секунд для {chat_link}, жду...")
                await asyncio.sleep(wait_time)
                try:
                    entity = await self.client.get_entity(chat_link)
                    if isinstance(entity, Channel):
                        await self.client(JoinChannelRequest(entity))
                        username = getattr(entity, 'username', None) or f"ID:{entity.id}"
                        return True, f"Присоединился к каналу @{username}", False
                    elif isinstance(entity, User) and entity.bot:
                        await self.client.send_message(entity, '/start')
                        return True, f"Запустил бота @{chat_link}", False
                    else:
                        await self.client(JoinChannelRequest(entity))
                        return True, f"Присоединился к {chat_link}", False
                except Exception as retry_error:
                    error_msg = str(retry_error)
                    if "as username" in error_msg.lower():
                        return False, f"Чат/бот {chat_link} не найден", False
                    return False, f"Ошибка после ожидания: {error_msg[:50]}", False
            except errors.InviteHashExpiredError:
                return False, f"Ссылка-приглашение истекла для {chat_link}", False
            except errors.UsersTooMuchError:
                return False, f"Слишком много участников в {chat_link}", False
            except errors.ChatWriteForbiddenError:
                logger.info(f"⏭️  {chat_link} требует заявку, пропускаю")
                return False, f"Требуется заявка для {chat_link}", True
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower():
                    return False, f"Чат/бот {chat_link} не найден", False
                if any(keyword in error_msg for keyword in ["request", "approval", "заявк", "invite", "permission", "forbidden", "not allowed"]):
                    logger.info(f"⏭️  {chat_link} требует заявку, пропускаю")
                    return False, f"Требуется заявка для {chat_link}", True
                return False, f"Ошибка присоединения: {error_msg[:50]}", False
                
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
                await self.client.send_message(entity, text)
                
                username = getattr(entity, 'username', None) or f"ID:{getattr(entity, 'id', 'unknown')}"
                logger.info(f"✅ Отправил сообщение в {username}")
                return True, f"Сообщение отправлено в {chat_link}"
                
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                if wait_time > 300:
                    logger.warning(f"FloodWait {wait_time} секунд для отправки в {chat_link} - слишком долго, пропускаю")
                    return False, f"FloodWait {wait_time} сек (слишком долго)"
                logger.info(f"FloodWait {wait_time} секунд для отправки в {chat_link}, жду...")
                await asyncio.sleep(wait_time)
                try:
                    await self.client.send_message(entity, text)
                    username = getattr(entity, 'username', None) or f"ID:{getattr(entity, 'id', 'unknown')}"
                    return True, f"Сообщение отправлено в {chat_link}"
                except Exception as retry_error:
                    error_msg = str(retry_error)
                    return False, f"Ошибка после ожидания: {error_msg[:50]}"
            except errors.ChatWriteForbiddenError:
                return False, f"Нет прав на отправку в {chat_link}"
            except errors.UserPrivacyRestrictedError:
                return False, f"Приватность ограничена для {chat_link}"
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower():
                    return False, f"Чат/бот {chat_link} не найден"
                return False, f"Ошибка отправки: {error_msg[:50]}"
                
        except Exception as e:
            error_msg = f"Ошибка отправки в {chat_link}: {str(e)[:50]}"
            logger.error(error_msg)
            return False, error_msg
    
    async def disconnect(self):
        if self.started:
            await self.client.disconnect()
            self.started = False
            logger.info("Клиент массовой рассылки отключен")
