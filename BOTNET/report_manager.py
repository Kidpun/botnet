import os
import re
from typing import Optional, Tuple
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import ReportRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonChildAbuse,
    InputReportReasonPornography,
    InputReportReasonCopyright,
    InputReportReasonPersonalDetails,
    InputReportReasonGeoIrrelevant,
    InputReportReasonFake,
    InputReportReasonIllegalDrugs,
    InputReportReasonOther,
)

from core.session_manager import SessionManager
from utils.logger import get_logger

logger = get_logger(__name__)

class ReportManager:
    
    REASON_CLASSES = {
        '1': ("Спам", InputReportReasonSpam),
        '2': ("Насилие", InputReportReasonViolence),
        '3': ("Насилие над детьми", InputReportReasonChildAbuse),
        '4': ("Порнография", InputReportReasonPornography),
        '5': ("Нарушение авторских прав", InputReportReasonCopyright),
        '6': ("Раскрытие личных данных", InputReportReasonPersonalDetails),
        '7': ("Геонерелевантный контент", InputReportReasonGeoIrrelevant),
        '8': ("Фальшивка", InputReportReasonFake),
        '9': ("Незаконные наркотики", InputReportReasonIllegalDrugs),
    }
    
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
    
    @classmethod
    def get_reason(cls, option: str):
        if option not in cls.REASON_CLASSES:
            return None, None
        reason_name, reason_class = cls.REASON_CLASSES[option]
        return reason_name, reason_class()
    
    def _parse_message_link(self, link: str) -> Tuple[Optional[str], Optional[int]]:
        link = link.strip().replace('\n', '').replace('\r', '')
        
        match = re.search(r't\.me/([^/]+)/(\d+)', link)
        if match:
            channel = match.group(1)
            message_id = int(match.group(2))
            return channel, message_id
        
        match = re.search(r't\.me/c/(\d+)/(\d+)', link)
        if match:
            channel_id = int(match.group(1))
            message_id = int(match.group(2))
            return f"-100{channel_id}", message_id
        
        return None, None
    
    async def send_report(self, message_link: str, reason_option: str, comment: str = "") -> Tuple[bool, str]:
        if not self.started:
            return False, "Клиент не запущен"
        
        channel_identifier, message_id = self._parse_message_link(message_link)
        if not channel_identifier or not message_id:
            return False, "Неверный формат ссылки (используйте t.me/channel/message_id)"
        
        reason_name, report_option = self.get_reason(reason_option)
        if report_option is None:
            return False, "Неверный код причины (1-9)"
        
        try:
            try:
                chat = await self.client.get_entity(channel_identifier)
            except errors.UsernameNotOccupiedError:
                return False, f"Канал {channel_identifier} не найден"
            except Exception as e:
                error_msg = str(e)
                if "as username" in error_msg.lower():
                    return False, f"Канал не найден: {error_msg}"
                return False, f"Ошибка получения канала: {error_msg[:50]}"
            
            try:
                target_message = await self.client.get_messages(chat, ids=message_id)
                if not target_message:
                    return False, "Сообщение не найдено"
            except Exception as e:
                logger.error(f"Ошибка получения сообщения: {e}")
                return False, f"Ошибка получения сообщения: {str(e)[:50]}"
            
            from telethon.tl.tlobject import TLObject
            
            report_comment = comment if comment else ""
            if reason_name:
                if report_comment:
                    report_comment = f"[{reason_name}] {report_comment}"
                else:
                    report_comment = f"[{reason_name}]"
            
            other_reason = InputReportReasonOther()
            
            try:
                if isinstance(other_reason, TLObject):
                    option_bytes = other_reason._bytes()
                elif hasattr(other_reason, '_bytes'):
                    option_bytes = other_reason._bytes()
                else:
                    option_bytes = bytes(other_reason)
                
                await self.client(ReportRequest(
                    peer=chat,
                    id=[message_id],
                    option=option_bytes,
                    message=report_comment
                ))
                logger.info(f"✅ Жалоба отправлена: {reason_name} (через InputReportReasonOther)")
                return True, f"Жалоба '{reason_name}' успешно отправлена"
            except errors.RPCError as e:
                error_msg = str(e)
                error_type = type(e).__name__
                logger.error(f"Ошибка Telegram API ({error_type}): {error_msg}")
                
                if "OptionInvalidError" in error_type or "option specified is invalid" in error_msg.lower() or "target poll" in error_msg.lower():
                    return False, "API не поддерживает жалобы на посты в каналах"
                
                return False, f"Ошибка API: {error_msg[:80]}"
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                logger.error(f"Ошибка отправки жалобы ({error_type}): {error_msg}", exc_info=True)
                return False, f"Ошибка отправки: {error_msg[:80]}"
            
        except errors.FloodWaitError as e:
            error_msg = f"FloodWait: нужно подождать {e.seconds} секунд"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Ошибка: {str(e)[:50]}"
            logger.error(error_msg)
            return False, error_msg
    
    async def disconnect(self):
        if self.started:
            await self.client.disconnect()
            self.started = False
            logger.info("Клиент отключен")
