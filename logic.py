import openai
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
import json
import aiohttp

logger = logging.getLogger(__name__)


class ChatGPTHandler:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.user_histories: Dict[int, List[Dict]] = {}
        self.max_history_length = 20  # Максимальное количество сообщений в истории

    def _get_system_message(self) -> Dict[str, str]:
        return {
            "role": "system",
            "content": """Ты — умный и дружелюбный ИИ-ассистент в Telegram-боте, предназначенный исключительно для помощи с программированием. 
Ты объясняешь код, помогаешь писать функции, находишь и исправляешь ошибки, а также даёшь советы по языкам программирования. 
Отвечай ясно, логично и немного подробнее, чтобы пользователь лучше понял тему, но избегай лишней воды. 
Если нужно — приводи примеры кода и объясняй шаг за шагом. 
Не обсуждай темы, не связанные с программированием (например, политику, здоровье, развлечения и т.п.). 
Не помогай писать или распространять вредоносный, незаконный или опасный код. 
Если вопрос выходит за рамки твоей специализации, вежливо откажись и напомни, чем ты можешь помочь. 
Отвечай на русском языке, если не попросят иначе. 
Ты хорошо разбираешься в Python, JavaScript, Java, C++, C#, HTML, CSS, Dart, TypeScript и других популярных языках."""
        }

    def _get_user_history(self, user_id: int) -> List[Dict]:
        if user_id not in self.user_histories:
            self.user_histories[user_id] = [self._get_system_message()]
        return self.user_histories[user_id]

    def _add_to_history(self, user_id: int, role: str, content: str):
        history = self._get_user_history(user_id)
        history.append({"role": role, "content": content})

        if len(history) > self.max_history_length:
            system_msg = history[0]  # Сохраняем системное сообщение
            recent_messages = history[-(self.max_history_length - 1):]
            self.user_histories[user_id] = [system_msg] + recent_messages

    async def get_response(self, user_id: int, message: str) -> str:
        try:
            self._add_to_history(user_id, "user", message)

            history = self._get_user_history(user_id)

            response = await self.client.chat.completions.create(
                model="gpt-4.1",
                messages=history,
                max_tokens=1000,
                temperature=0.7
            )

            assistant_response = response.choices[0].message.content

            self._add_to_history(user_id, "assistant", assistant_response)

            return assistant_response

        except openai.RateLimitError:
            return "⚠️ Превышен лимит запросов к ChatGPT. Попробуйте позже."
        except openai.AuthenticationError:
            return "❌ Ошибка аутентификации с ChatGPT API. Проверьте API ключ."
        except Exception as e:
            logger.error(f"Ошибка ChatGPT API: {e}")
            return "❌ Произошла ошибка при обращении к ChatGPT. Попробуйте позже."

    def clear_history(self, user_id: int):
        self.user_histories[user_id] = [self._get_system_message()]

    def get_history_length(self, user_id: int) -> int:
        return len(self._get_user_history(user_id)) - 1


class ImageGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = openai.AsyncOpenAI(api_key=api_key)

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> Optional[str]:
        try:
            enhanced_prompt = self._enhance_prompt(prompt)

            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size=size,
                quality="standard",
                n=1
            )

            return response.data[0].url

        except openai.RateLimitError:
            logger.error("Rate limit exceeded for image generation")
            return None
        except openai.AuthenticationError:
            logger.error("Authentication error for image generation")
            return None
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return None

    def _enhance_prompt(self, prompt: str) -> str:
        quality_words = ["high quality", "detailed", "professional", "beautiful", "stunning"]

        if not any(word in prompt.lower() for word in quality_words):
            prompt += ", high quality, detailed"

        return prompt[:1000]


class UserManager:
    def __init__(self):
        self.users: Dict[int, Dict] = {}
        self.load_users()

    def register_user(self, user_id: int, username: str):
        if user_id not in self.users:
            self.users[user_id] = {
                "username": username,
                "registration_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "messages_sent": 0,
                "images_generated": 0,
                "last_activity": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            self.save_users()

    def update_activity(self, user_id: int):
        if user_id in self.users:
            self.users[user_id]["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.save_users()

    def increment_messages(self, user_id: int):
        if user_id in self.users:
            self.users[user_id]["messages_sent"] += 1
            self.update_activity(user_id)

    def increment_images(self, user_id: int):
        if user_id in self.users:
            self.users[user_id]["images_generated"] += 1
            self.update_activity(user_id)

    def get_user_stats(self, user_id: int) -> Dict:
        if user_id in self.users:
            return self.users[user_id].copy()
        else:
            return {
                "username": "Неизвестный",
                "registration_date": "Не зарегистрирован",
                "messages_sent": 0,
                "images_generated": 0,
                "last_activity": "Никогда"
            }

    def get_total_stats(self) -> Dict:
        total_users = len(self.users)
        total_messages = sum(user["messages_sent"] for user in self.users.values())
        total_images = sum(user["images_generated"] for user in self.users.values())

        return {
            "total_users": total_users,
            "total_messages": total_messages,
            "total_images": total_images
        }

    def save_users(self):
        try:
            with open("users.json", "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных пользователей: {e}")

    def load_users(self):
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                self.users = json.load(f)
                # Конвертируем ключи обратно в int (JSON сохраняет их как строки)
                self.users = {int(k): v for k, v in self.users.items()}
        except FileNotFoundError:
            self.users = {}
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных пользователей: {e}")
            self.users = {}


class MessageFormatter:
    @staticmethod
    def format_error(error_message: str) -> str:
        return f"❌ <b>Ошибка:</b> {error_message}"

    @staticmethod
    def format_success(success_message: str) -> str:
        return f"✅ <b>Успешно:</b> {success_message}"

    @staticmethod
    def format_info(info_message: str) -> str:
        return f"ℹ️ <b>Информация:</b> {info_message}"

    @staticmethod
    def format_stats(stats: Dict) -> str:
        return (
            f"📊 <b>Статистика:</b>\n\n"
            f"👤 Пользователь: {stats['username']}\n"
            f"📅 Регистрация: {stats['registration_date']}\n"
            f"💬 Сообщений: {stats['messages_sent']}\n"
            f"🎨 Изображений: {stats['images_generated']}\n"
            f"🕒 Последняя активность: {stats['last_activity']}"
        )


class ConfigManager:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self) -> Dict:
        default_config = {
            "max_message_length": 4000,
            "max_history_length": 20,
            "image_sizes": ["256x256", "512x512", "1024x1024"],
            "allowed_image_formats": ["png", "jpg", "jpeg"],
            "rate_limits": {
                "messages_per_minute": 10,
                "images_per_hour": 5
            },
            "features": {
                "image_generation": True,
                "chat_history": True,
                "user_stats": True
            }
        }

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
                default_config.update(loaded_config)
                return default_config
        except FileNotFoundError:
            self.save_config(default_config)
            return default_config
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return default_config

    def save_config(self, config: Dict = None):
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config or self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self.save_config()

config_manager = ConfigManager()
message_formatter = MessageFormatter()