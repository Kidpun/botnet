# BOTNET — управление аккаунтами Telegram

CLI для управления несколькими аккаунтами Telegram: профиль, чаты, рассылки, жалобы, безопасность. Поддержка прокси (HTTP/SOCKS5).

Репозиторий: [github.com/Kidpun/botnet](https://github.com/Kidpun/botnet)

---

## Требования

- Python 3.8+
- [Telegram API](https://my.telegram.org/apps): `api_id` и `api_hash`
- Файлы сессий Telethon (`.session`)

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Kidpun/botnet.git
cd botnet
```

### 2. Создать виртуальное окружение (рекомендуется)

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# или: venv\Scripts\activate   # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

Получите `api_id` и `api_hash` на [my.telegram.org](https://my.telegram.org/apps), затем:

```bash
export API_ID=ваш_api_id
export API_HASH=ваш_api_hash
```

В Windows (PowerShell):

```powershell
$env:API_ID="ваш_api_id"
$env:API_HASH="ваш_api_hash"
```

---

## Сессии

Положите файлы сессий Telethon в папку **`BOTNET/sessions/`**:

```bash
mkdir -p BOTNET/sessions
# скопируйте ваши .session файлы в BOTNET/sessions/
```

Сессии можно создать отдельно через Telethon (логин по номеру телефона); этот репозиторий только использует уже готовые `.session` файлы.

---

## Запуск

Из корня репозитория (после `git clone`):

```bash
python main.py
```

или

```bash
python BOTNET/botnet.py
```

Откроется меню — вводите номер пункта и следуйте подсказкам. Пункт **29** — настройки (API ID / API Hash), сохраняются в `.env` в корне репозитория.

---

## Прокси (по желанию)

Файл **`BOTNET/proxy.txt`** — одна строка = один прокси. Используются по очереди для аккаунтов (если прокси меньше, чем сессий — список прокси повторяется по циклу).

Форматы:

- `http://host:port`
- `socks5://host:port`
- `http://user:pass@host:port`
- `socks5://user:pass@host:port`

Для работы прокси нужен **PySocks** (уже указан в `requirements.txt`).

---

## Возможности меню

| Раздел | Действия |
|--------|----------|
| **Имя** | Смена имени/фамилии (одна или все сессии) |
| **Аватарка** | Установка/удаление фото профиля |
| **Username** | Рандомный username (одна или все сессии) |
| **Описание** | Изменение bio (одна или все сессии) |
| **Информация** | Просмотр профиля, проверка всех сессий |
| **Чаты** | Вступление в чат, отправка сообщений, выход из чата |
| **Инвайтер** | Приглашение участников по юзернеймам из `user.txt` в канал/чат (одна или все сессии) |
| **Боты** | Запуск бота `/start` (в т.ч. с реферальным кодом) |
| **Жалобы** | Отправка жалобы на сообщение |
| **Безопасность** | Удаление других сессий, проверка облачного пароля |
| **Рассылка** | Умная рассылка по ссылкам из поста |
| **Парсер** | Сбор чатов у @en_SearchBot (/rand) → указать пост с текстом → вступление в чаты и рассылка текста со всех сессий |
| **Управление** | Удаление невалидных сессий |
| **Настройки** | API ID / API Hash (сохраняются в `.env`) |

---

## Структура репозитория

```
botnet/
├── BOTNET/
│   ├── botnet.py          # Точка входа, меню
│   ├── profile_manager.py
│   ├── chat_manager.py
│   ├── session_checker.py
│   ├── report_manager.py
│   ├── security_manager.py
│   ├── mass_sender.py
│   ├── bot_parser.py
│   ├── proxy_loader.py
│   ├── proxy.txt          # Список прокси (создайте при необходимости)
│   └── sessions/          # Сюда класть .session файлы
├── core/
│   └── session_manager.py
├── utils/
│   └── logger.py
├── requirements.txt
└── README.md
```

---

## Лицензия

MIT.
