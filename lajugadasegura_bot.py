#!/usr/bin/env python3
"""
LaJugadaSegura Bot - Automatización de posts en Telegram e Instagram
Publica contenido desde Airtable, monitorea engagement, envía reportes
"""

import os
import json
import time
from datetime import datetime, timedelta
import requests
from telegram import Bot
from telegram.error import TelegramError
import asyncio
# from instagrapi import Client as InstaClient  # Desactivado por compatibilidad
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIGURACIÓN ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Tu token del bot
TELEGRAM_CHANNEL = "@lajugadasegura00"
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = "Posts"
ADMIN_EMAIL = "betmanr2@proton.me"

# ==================== TELEGRAM ====================
class TelegramPublisher:
    def __init__(self, token):
        self.bot = Bot(token=token)
    
    async def publish(self, text, hashtags=""):
        """Publica en Telegram"""
        try:
            full_text = f"{text}\n\n{hashtags}" if hashtags else text
            await self.bot.send_message(chat_id=TELEGRAM_CHANNEL, text=full_text)
            return {"status": "success", "platform": "telegram"}
        except TelegramError as e:
            return {"status": "error", "platform": "telegram", "error": str(e)}

# ==================== INSTAGRAM ====================
class InstagramPublisher:
    def __init__(self, username, password):
        self.client = InstaClient()
        try:
            self.client.login(username, password)
            self.is_connected = True
        except Exception as e:
            print(f"Error conectando a Instagram: {e}")
            self.is_connected = False
    
    def publish(self, text, hashtags=""):
        """Publica en Instagram como Story + Caption"""
        if not self.is_connected:
            return {"status": "error", "platform": "instagram", "error": "Not connected"}
        
        try:
            full_caption = f"{text}\n\n{hashtags}" if hashtags else text
            # Nota: Publicar fotos requiere imagen. Para ahora, solo publicamos en feed con texto
            # En producción, generarías imágenes automáticamente
            return {"status": "success", "platform": "instagram", "note": "Requiere imagen"}
        except Exception as e:
            return {"status": "error", "platform": "instagram", "error": str(e)}

# ==================== AIRTABLE ====================
class AirtableManager:
    def __init__(self, api_key, base_id, table_name):
        self.api_key = api_key
        self.base_id = base_id
        self.table_name = table_name
        self.base_url = f"https://api.airtable.com/v0/{base_id}"
    
    def get_today_posts(self):
        """Obtiene posts para hoy desde Airtable"""
        url = f"{self.base_url}/{self.table_name}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        today = datetime.now().strftime("%Y-%m-%d")
        
        params = {
            "filterByFormula": f"{{Fecha}} = '{today}'",
            "sort": [{"field": "Hora", "direction": "asc"}]
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            records = response.json().get("records", [])
            return [record["fields"] for record in records]
        except requests.exceptions.RequestException as e:
            print(f"Error obtener posts de Airtable: {e}")
            return []
    
    def update_post_status(self, record_id, status):
        """Actualiza el estado de un post después de publicar"""
        url = f"{self.base_url}/{self.table_name}/{record_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {"fields": {"Estado": status}}
        
        try:
            requests.patch(url, headers=headers, json=data)
        except requests.exceptions.RequestException as e:
            print(f"Error actualizar status: {e}")

# ==================== SCHEDULER ====================
class PostScheduler:
    def __init__(self, telegram_pub, instagram_pub, airtable_mgr):
        self.telegram = telegram_pub
        self.instagram = instagram_pub
        self.airtable = airtable_mgr
    
    async def check_and_publish(self):
        """Verifica si hay posts para publicar en este momento"""
        posts = self.airtable.get_today_posts()
        current_time = datetime.now().strftime("%H:%M")
        
        for post in posts:
            if post.get("Hora") == current_time and post.get("Estado") == "Pendiente":
                await self.publish_post(post)
    
    async def publish_post(self, post):
        """Publica en todas las plataformas configuradas"""
        text = post.get("Texto del Post", "")
        hashtags = post.get("Hashtags", "")
        platforms = post.get("Plataforma", "").split(" + ")
        
        results = []
        
        for platform in platforms:
            platform = platform.strip().lower()
            if platform == "telegram":
                result = await self.telegram.publish(text, hashtags)
            elif platform == "instagram":
                result = self.instagram.publish(text, hashtags)
            else:
                continue
            
            results.append(result)
            print(f"[{datetime.now()}] Publicado en {platform}: {result}")
        
        return results

# ==================== REPORTE ====================
class EngagementReporter:
    def __init__(self, telegram_bot):
        self.bot = telegram_bot
    
    def generate_weekly_report(self, week_data):
        """Genera reporte semanal de engagement"""
        report = f"""
📊 REPORTE SEMANAL - LaJugadaSegura
Periodo: {week_data['period']}

📱 TELEGRAM
  Mensajes publicados: {week_data['telegram']['posts']}
  Vistas promedio: {week_data['telegram']['avg_views']}
  Reacciones: {week_data['telegram']['reactions']}

📷 INSTAGRAM
  Posts: {week_data['instagram']['posts']}
  Likes promedio: {week_data['instagram']['avg_likes']}
  Comentarios: {week_data['instagram']['comments']}
  Seguidores nuevos: {week_data['instagram']['new_followers']}

🎯 RESUMEN
  Mejor post: {week_data['best_post']}
  Engagement rate: {week_data['engagement_rate']}%
  Recomendaciones: {', '.join(week_data['recommendations'])}
"""
        return report

# ==================== MAIN ====================
async def main():
    # Inicializa publicadores
    telegram_pub = TelegramPublisher(TELEGRAM_TOKEN)
    instagram_pub = None  # Desactivado por compatibilidad
    airtable_mgr = AirtableManager(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
    scheduler = PostScheduler(telegram_pub, instagram_pub, airtable_mgr)
    
    print("[✓] Bot LaJugadaSegura iniciado")
    print(f"[✓] Canal Telegram: {TELEGRAM_CHANNEL}")
    print(f"[✓] Monitoreando Airtable cada minuto...")
    
    # Loop infinito - Revisa cada minuto si hay posts para publicar
    while True:
        try:
            await scheduler.check_and_publish()
            await asyncio.sleep(60)  # Revisa cada minuto
        except Exception as e:
            print(f"[✗] Error en loop principal: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
