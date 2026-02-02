"""
ФАНТОМ БИБЛИОТЕКИ — Полная версия на PyGame (исправленная)
Использует ваши ресурсы, но при ошибках загрузки создаёт заглушки.
"""
import pygame
import sys
import sqlite3
import os
import datetime
import random
import math
from contextlib import contextmanager
from typing import List, Dict, Optional

# === КОНСТАНТЫ ИГРЫ ===
SCREEN_WIDTH, SCREEN_HEIGHT = 1024, 768
FPS = 60
GAME_DAY_DURATION = 120.0  # 2 минуты реального времени = 1 игровой день
DB_PATH = "library_phantom.db"

# Пути к ресурсам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
PNG_DIR = os.path.join(ASSETS_DIR, "png")
SOUNDS_DIR = os.path.join(ASSETS_DIR, "sounds")

# === МЕНЕДЖЕР БАЗЫ ДАННЫХ ===
class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    total_playtime REAL DEFAULT 0,
                    completed_tasks INTEGER DEFAULT 0,
                    restored_books INTEGER DEFAULT 0,
                    energy_level INTEGER DEFAULT 100,
                    game_time REAL DEFAULT 0,
                    current_location TEXT DEFAULT 'modern_hall'
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    is_damaged BOOLEAN DEFAULT 1,
                    location TEXT NOT NULL DEFAULT 'modern_hall',
                    FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS visitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    target_book_id INTEGER,
                    state TEXT DEFAULT 'searching',
                    location TEXT NOT NULL DEFAULT 'modern_hall',
                    FOREIGN KEY (account_id) REFERENCES accounts (id) ON DELETE CASCADE
                )
            ''')

    def create_account(self, username: str, password: str) -> bool:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO accounts (username, password, energy_level) VALUES (?, ?, 100)', (username, password))
                account_id = cursor.lastrowid

                default_books = [
                    (account_id, 300, 400, 0, 'modern_hall'),
                    (account_id, 600, 350, 1, 'modern_hall'),
                    (account_id, 400, 500, 1, 'historical_archive'),
                    (account_id, 700, 450, 0, 'reading_room'),
                ]
                cursor.executemany('INSERT INTO books (account_id, x, y, is_damaged, location) VALUES (?, ?, ?, ?, ?)', default_books)

                default_visitors = [
                    (account_id, 100, 300, None, 'searching', 'modern_hall'),
                    (account_id, 200, 500, None, 'searching', 'modern_hall'),
                ]
                cursor.executemany('INSERT INTO visitors (account_id, x, y, target_book_id, state, location) VALUES (?, ?, ?, ?, ?, ?)', default_visitors)

                return True
        except sqlite3.IntegrityError:
            return False

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, energy_level, restored_books, completed_tasks, game_time, current_location, total_playtime FROM accounts WHERE username = ? AND password = ?', (username, password))
            result = cursor.fetchone()
            if result:
                cursor.execute('UPDATE accounts SET last_login = CURRENT_TIMESTAMP WHERE username = ?', (username,))
                return {
                    "id": result[0],
                    "username": result[1],
                    "energy": result[2],
                    "restored_books": result[3],
                    "completed_tasks": result[4],
                    "game_time": result[5],
                    "current_location": result[6],
                    "total_playtime": result[7]
                }
            return None

    def save_progress(self, account_id: int, energy: int, restored: int, completed: int, game_time: float, location: str, playtime: float):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE accounts SET energy_level = ?, restored_books = ?, completed_tasks = ?, game_time = ?, current_location = ?, total_playtime = total_playtime + ? WHERE id = ?',
                          (energy, restored, completed, game_time, location, playtime, account_id))

    def load_books(self, account_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, x, y, is_damaged, location FROM books WHERE account_id = ?', (account_id,))
            return [{"id": r[0], "x": r[1], "y": r[2], "is_damaged": bool(r[3]), "location": r[4], "highlight_timer": 0.0, "restoring": False} for r in cursor.fetchall()]

    def save_books(self, account_id: int, books: List[Dict]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM books WHERE account_id = ?', (account_id,))
            for b in books:
                cursor.execute('INSERT INTO books (account_id, x, y, is_damaged, location) VALUES (?, ?, ?, ?, ?)', (account_id, b["x"], b["y"], int(b["is_damaged"]), b["location"]))

    def load_visitors(self, account_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, x, y, target_book_id, state, location FROM visitors WHERE account_id = ?', (account_id,))
            return [{"id": r[0], "x": r[1], "y": r[2], "target_book_id": r[3], "state": r[4], "location": r[5], "speed": 1.5} for r in cursor.fetchall()]

    def save_visitors(self, account_id: int, visitors: List[Dict]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM visitors WHERE account_id = ?', (account_id,))
            for v in visitors:
                cursor.execute('INSERT INTO visitors (account_id, x, y, target_book_id, state, location) VALUES (?, ?, ?, ?, ?, ?)', (account_id, v["x"], v["y"], v["target_book_id"], v["state"], v["location"]))

    def get_account_stats(self, account_id: int) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT total_playtime, completed_tasks, restored_books, energy_level, created_at, last_login FROM accounts WHERE id = ?', (account_id,))
            r = cursor.fetchone()
            return {"total_playtime": r[0], "completed_tasks": r[1], "restored_books": r[2], "energy_level": r[3], "created_at": r[4], "last_login": r[5]}


# === ЗАГРУЗКА РЕСУРСОВ С ЗАЩИТОЙ ОТ ОШИБОК ===
def create_placeholder_image(width: int, height: int, color: tuple, text: str = "") -> pygame.Surface:
    """Создание заглушки-изображения"""
    surf = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.rect(surf, color, surf.get_rect())
    if text:
        font = pygame.font.SysFont("Arial", 16)
        text_surf = font.render(text, True, (255, 255, 255))
        surf.blit(text_surf, (width//2 - text_surf.get_width()//2, height//2 - text_surf.get_height()//2))
    return surf

def load_sprite(filename: str, scale: float = 1.0) -> pygame.Surface:
    """Безопасная загрузка изображения с созданием заглушки при ошибке"""
    path = os.path.join(PNG_DIR, filename)
    if not os.path.exists(path):
        print(f"⚠️ Файл не найден: {path}")
        return create_placeholder_image(50, 70, (139, 69, 19), filename[:8])

    try:
        image = pygame.image.load(path).convert_alpha()
        if scale != 1.0:
            new_size = (int(image.get_width() * scale), int(image.get_height() * scale))
            image = pygame.transform.scale(image, new_size)
        return image
    except Exception as e:
        print(f"❌ Ошибка загрузки {filename}: {e}")
        return create_placeholder_image(50, 70, (139, 69, 19), "ERROR")

def load_sound(filename: str) -> pygame.mixer.Sound | None:
    """Безопасная загрузка звука"""
    path = os.path.join(SOUNDS_DIR, filename)
    if not os.path.exists(path):
        print(f"⚠️ Звук не найден: {path}")
        return None
    try:
        return pygame.mixer.Sound(path)
    except Exception as e:
        print(f"❌ Ошибка загрузки звука {filename}: {e}")
        return None

class ResourceManager:
    def __init__(self):
        # Загрузка изображений с защитой от ошибок
        self.ghost = load_sprite("ghost.png", 0.8)
        self.ghost_phasing = load_sprite("ghost_phasing.png", 0.8)
        self.book = load_sprite("book.png", 0.7)
        self.book_damaged = load_sprite("book_damaged.png", 0.7)
        self.book_restored = load_sprite("book_restored.png", 0.7)
        self.bookshelf = load_sprite("bookshelf.png", 1.0)
        self.power_zone = load_sprite("power_zone.png", 0.8)

        # Загрузка посетителей (1-10)
        self.visitors = []
        for i in range(1, 11):
            visitor_img = load_sprite(f"visitor_{i}.png", 0.6)
            self.visitors.append(visitor_img)

        # Фоны меню
        self.login_background = load_sprite("login_background.png", 1.0)
        self.main_menu_background = load_sprite("main_menu_background.png", 1.0)

        # Звуки
        self.ambience_day = load_sound("library_ambience.wav")
        self.ambience_night = load_sound("night_ambience.wav")
        self.book_drop = load_sound("book_drop.wav")
        self.ghost_whisper = load_sound("ghost_whisper.wav")
        self.menu_click = load_sound("menu_click.wav")

        # Запуск фонового звука
        if self.ambience_day:
            pygame.mixer.Channel(0).play(self.ambience_day, -1)
            pygame.mixer.Channel(0).set_volume(0.4)

        self.sound_enabled = True

    def play_sound(self, sound: pygame.mixer.Sound | None, volume: float = 0.5):
        if sound and self.sound_enabled:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.play(sound)
                channel.set_volume(volume)

    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        if not self.sound_enabled:
            pygame.mixer.Channel(0).stop()
        elif self.ambience_day:
            pygame.mixer.Channel(0).play(self.ambience_day, -1)
            pygame.mixer.Channel(0).set_volume(0.4)


# === ЭКРАН ВХОДА ===
class LoginScreen:
    def __init__(self, db: DatabaseManager, resources: ResourceManager):
        self.db = db
        self.resources = resources
        self.username = ""
        self.password = ""
        self.focus = "username"
        self.mode = "login"
        self.error = ""
        self.blink_timer = 0

    def handle_event(self, event) -> Optional[Dict]:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self.focus = "password" if self.focus == "username" else "username"
                self.error = ""
            elif event.key == pygame.K_BACKSPACE:
                if self.focus == "username" and self.username:
                    self.username = self.username[:-1]
                elif self.focus == "password" and self.password:
                    self.password = self.password[:-1]
            elif event.key == pygame.K_RETURN:
                if self.mode == "login":
                    return self.attempt_login()
                else:
                    return self.attempt_register()
            elif event.unicode.isalnum() or event.unicode in "_-.":
                if self.focus == "username" and len(self.username) < 20:
                    self.username += event.unicode
                elif self.focus == "password" and len(self.password) < 20:
                    self.password += event.unicode
        elif event.type == pygame.MOUSEBUTTONDOWN:
            x, y = event.pos
            if 300 <= x <= 724 and 220 <= y <= 280:
                self.focus = "username"
                self.error = ""
            elif 300 <= x <= 724 and 320 <= y <= 380:
                self.focus = "password"
                self.error = ""
            elif 350 <= x <= 500 and 450 <= y <= 510:
                if self.mode == "login":
                    return self.attempt_login()
                else:
                    return self.attempt_register()
            elif 524 <= x <= 674 and 450 <= y <= 510:
                self.mode = "register" if self.mode == "login" else "login"
                self.error = ""
                self.username = ""
                self.password = ""
        return None

    def attempt_login(self) -> Optional[Dict]:
        if not self.username or not self.password:
            self.error = "❌ Заполните все поля!"
            return None
        account = self.db.authenticate(self.username, self.password)
        if account:
            return account
        else:
            self.error = "❌ Неверное имя или пароль!"
            return None

    def attempt_register(self) -> Optional[Dict]:
        if len(self.username) < 3:
            self.error = "❌ Имя должно быть от 3 символов!"
            return None
        if len(self.password) < 4:
            self.error = "❌ Пароль должен быть от 4 символов!"
            return None
        if self.db.create_account(self.username, self.password):
            self.mode = "login"
            self.password = ""
            self.error = "✅ Аккаунт создан! Войдите."
            return None
        else:
            self.error = "❌ Аккаунт уже существует!"
            return None

    def draw(self, screen, font_large, font_medium, font_small, font_tiny):
        if self.resources.login_background:
            screen.blit(self.resources.login_background, (0, 0))
        else:
            screen.fill((25, 20, 40))

        title = font_large.render(
            "ФАНТОМ БИБЛИОТЕКИ" if self.mode == "login" else "СОЗДАНИЕ АККАУНТА",
            True, (255, 215, 0)
        )
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 60))

        for i, (label, text, y) in enumerate([
            ("Имя пользователя:", self.username, 250),
            ("Пароль:", "*" * len(self.password), 350)
        ]):
            is_focused = self.focus == ["username", "password"][i]
            color_border = (255, 215, 0) if is_focused else (150, 150, 150)
            pygame.draw.rect(screen, (40, 40, 60), (300, y-30, 424, 60), border_radius=12)
            pygame.draw.rect(screen, color_border, (300, y-30, 424, 60), 3, border_radius=12)

            label_surf = font_small.render(label, True, (180, 180, 200))
            screen.blit(label_surf, (320, y-25))

            display_text = text if text else "____________________"
            text_surf = font_medium.render(display_text, True, (255, 255, 255))
            screen.blit(text_surf, (320, y+5))

            if is_focused and self.blink_timer % 60 < 30:
                cursor_x = 320 + text_surf.get_width() + 5
                pygame.draw.line(screen, (255, 255, 255), (cursor_x, y+5), (cursor_x, y+35), 2)

        pygame.draw.rect(screen, (50, 120, 50) if self.mode == "login" else (50, 80, 150),
                        (350, 450, 150, 60), border_radius=15)
        pygame.draw.rect(screen, (120, 50, 50) if self.mode == "login" else (80, 50, 120),
                        (524, 450, 150, 60), border_radius=15)

        btn1_text = font_medium.render("ВОЙТИ" if self.mode == "login" else "СОЗДАТЬ", True, (255, 255, 255))
        btn2_text = font_medium.render("РЕГИСТРАЦИЯ" if self.mode == "login" else "НАЗАД", True, (255, 255, 255))
        screen.blit(btn1_text, (425 - btn1_text.get_width()//2, 475))
        screen.blit(btn2_text, (600 - btn2_text.get_width()//2, 475))

        if self.error:
            error_surf = font_small.render(self.error, True, (255, 100, 100))
            screen.blit(error_surf, (SCREEN_WIDTH//2 - error_surf.get_width()//2, 400))

        hint = font_tiny.render("TAB — переключить поле | ENTER — подтвердить", True, (150, 150, 180))
        screen.blit(hint, (SCREEN_WIDTH//2 - hint.get_width()//2, SCREEN_HEIGHT - 40))
        self.blink_timer += 1


# === ГЛАВНОЕ МЕНЮ ===
class MainMenu:
    def __init__(self, db: DatabaseManager, account_data: Dict, resources: ResourceManager):
        self.db = db
        self.account_data = account_data
        self.stats = db.get_account_stats(account_data["id"])
        self.resources = resources

    def handle_event(self, event) -> Optional[str]:
        if event.type == pygame.MOUSEBUTTONDOWN:
            x, y = event.pos
            if 362 <= x <= 662 and 320 <= y <= 390:
                return "play"
            elif 362 <= x <= 662 and 420 <= y <= 490:
                return "stats"
            elif 362 <= x <= 662 and 520 <= y <= 590:
                return "logout"
        return None

    def draw(self, screen, font_large, font_medium, font_small, font_tiny):
        if self.resources.main_menu_background:
            screen.blit(self.resources.main_menu_background, (0, 0))
        else:
            screen.fill((35, 30, 50))

        title = font_large.render(f"Добро пожаловать, {self.account_data['username']}!", True, (255, 215, 0))
        screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 70))

        stats_y = 180
        stats = [
            f"Время в игре: {int(self.stats['total_playtime'] // 60)} мин {int(self.stats['total_playtime'] % 60)} сек",
            f"Выполнено заданий: {self.stats['completed_tasks']}",
            f"Восстановлено книг: {self.stats['restored_books']}",
            f"⚡ Текущая энергия: {self.stats['energy_level']}",
            f"Последний вход: {self.stats['last_login'][:16]}",
            f"Аккаунт создан: {self.stats['created_at'][:10]}"
        ]

        for i, text in enumerate(stats):
            surf = font_medium.render(text, True, (220, 220, 240))
            screen.blit(surf, (SCREEN_WIDTH//2 - surf.get_width()//2, stats_y + i * 45))

        buttons = [("🎮 ИГРАТЬ", 320), ("📊 СТАТИСТИКА", 420), ("🚪 ВЫХОД", 520)]
        for text, y in buttons:
            pygame.draw.rect(screen, (60, 80, 120), (362, y, 300, 70), border_radius=15)
            pygame.draw.rect(screen, (255, 215, 0), (362, y, 300, 70), 3, border_radius=15)
            btn_text = font_medium.render(text, True, (255, 255, 255))
            screen.blit(btn_text, (SCREEN_WIDTH//2 - btn_text.get_width()//2, y + 20))

        hint = font_tiny.render("Кликните по кнопке для выбора действия", True, (180, 180, 200))
        screen.blit(hint, (SCREEN_WIDTH//2 - hint.get_width()//2, SCREEN_HEIGHT - 40))


# === ИГРОВОЙ ПРОЦЕСС ===
class Game:
    def __init__(self, db: DatabaseManager, account_data: Dict, resources: ResourceManager):
        self.db = db
        self.account_data = account_data
        self.resources = resources

        self.ghost_x, self.ghost_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        self.ghost_energy, self.is_phasing, self.phasing_cooldown = account_data["energy"], False, 0.0

        self.books, self.visitors = db.load_books(account_data["id"]), db.load_visitors(account_data["id"])
        self.current_location, self.game_time = account_data["current_location"], account_data["game_time"]
        self.start_real_time, self.last_save_time = datetime.datetime.now(), datetime.datetime.now()
        self.task_timer, self.is_lunar_thursday = 30.0, datetime.datetime.now().weekday() == 3
        self.generate_task()

    def generate_task(self):
        available_visitors = [v for v in self.visitors if v["state"] == "searching" and v["location"] == self.current_location]
        if not available_visitors: return
        visitor = random.choice(available_visitors)
        available_books = [b for b in self.books if not b["is_damaged"] and b["location"] == self.current_location]
        if not available_books: return
        target_book = random.choice(available_books)
        visitor["target_book_id"] = target_book["id"]
        visitor["state"] = "moving"
        target_book["highlight_timer"] = 10.0

    def update(self, dt: float):
        real_elapsed = (datetime.datetime.now() - self.start_real_time).total_seconds()
        self.game_time = (real_elapsed / GAME_DAY_DURATION) * 86400

        hour = (self.game_time / 3600) % 24
        is_night = hour < 6 or hour > 20

        # Обновление фонового звука
        if is_night and self.resources.ambience_night:
            pygame.mixer.Channel(0).play(self.resources.ambience_night, -1)
            pygame.mixer.Channel(0).set_volume(0.3)
        elif not is_night and self.resources.ambience_day:
            pygame.mixer.Channel(0).play(self.resources.ambience_day, -1)
            pygame.mixer.Channel(0).set_volume(0.4)

        if self.phasing_cooldown > 0:
            self.phasing_cooldown -= dt

        # Восстановление энергии
        if 700 <= self.ghost_x <= 850 and 500 <= self.ghost_y <= 650:
            self.ghost_energy = min(100, self.ghost_energy + 1.0 * dt)
        else:
            self.ghost_energy = min(100, self.ghost_energy + 0.2 * dt)

        # Восстановление книг в лунную ночь
        if self.is_lunar_thursday and is_night:
            for book in self.books:
                if book["is_damaged"] and book["location"] == self.current_location:
                    dist = math.hypot(self.ghost_x - book["x"], self.ghost_y - book["y"])
                    if dist < 120 and self.ghost_energy >= 5:
                        book["restoring"] = True
                        book["is_damaged"] = False
                        self.account_data["restored_books"] += 1
                        self.ghost_energy -= 5
                        self.resources.play_sound(self.resources.ghost_whisper, 0.4)

        # Движение посетителей
        for visitor in self.visitors:
            if visitor["state"] == "moving" and visitor["location"] == self.current_location:
                target = None
                for book in self.books:
                    if book["id"] == visitor["target_book_id"]:
                        target = book
                        break
                if target:
                    dx, dy = target["x"] - visitor["x"], target["y"] - visitor["y"]
                    dist = max(1, math.hypot(dx, dy))
                    visitor["x"] += (dx / dist) * visitor["speed"] * dt * 60
                    visitor["y"] += (dy / dist) * visitor["speed"] * dt * 60
                    if dist < 25:
                        visitor["state"] = "found"
                        self.account_data["completed_tasks"] += 1
                        self.generate_task()
                        self.resources.play_sound(self.resources.book_drop, 0.6)

        self.task_timer -= dt
        if self.task_timer <= 0:
            self.generate_task()
            self.task_timer = 30.0

        if (datetime.datetime.now() - self.last_save_time).total_seconds() > 30:
            self.save_progress()
            self.last_save_time = datetime.datetime.now()

    def save_progress(self):
        playtime = (datetime.datetime.now() - self.start_real_time).total_seconds()
        self.db.save_progress(
            self.account_data["id"],
            max(0, int(self.ghost_energy)),
            self.account_data["restored_books"],
            self.account_data["completed_tasks"],
            self.game_time,
            self.current_location,
            playtime
        )
        self.db.save_books(self.account_data["id"], self.books)
        self.db.save_visitors(self.account_data["id"], self.visitors)
        self.start_real_time = datetime.datetime.now()

    def draw(self, screen, font_small, font_medium, font_tiny):
        hour = (self.game_time / 3600) % 24
        is_night = hour < 6 or hour > 20

        # Фон библиотеки
        if self.resources.bookshelf:
            screen.blit(self.resources.bookshelf, (0, 0))
        else:
            screen.fill((45, 40, 35) if not is_night else (25, 20, 30))

        # Зона силы
        if self.resources.power_zone:
            screen.blit(self.resources.power_zone, (700, 500))

        # Книги
        for book in self.books:
            if book["location"] != self.current_location: continue

            texture = self.resources.book_restored if book["restoring"] else \
                     self.resources.book_damaged if book["is_damaged"] else self.resources.book

            if texture:
                screen.blit(texture, (book["x"] - texture.get_width()//2, book["y"] - texture.get_height()//2))

            if book["highlight_timer"] > 0:
                alpha = int(180 * (0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 100)))
                glow = pygame.Surface((80, 100), pygame.SRCALPHA)
                pygame.draw.rect(glow, (255, 255, 200, alpha), glow.get_rect(), border_radius=15)
                screen.blit(glow, (book["x"] - 40, book["y"] - 50))

        # Посетители
        for visitor in self.visitors:
            if visitor["location"] != self.current_location: continue

            if self.resources.visitors:
                tex = self.resources.visitors[visitor["id"] % len(self.resources.visitors)]
                screen.blit(tex, (visitor["x"] - tex.get_width()//2, visitor["y"] - tex.get_height()//2))

        # Призрак
        ghost_tex = self.resources.ghost_phasing if self.is_phasing else self.resources.ghost
        if ghost_tex:
            screen.blit(ghost_tex, (self.ghost_x - ghost_tex.get_width()//2, self.ghost_y - ghost_tex.get_height()//2))
        else:
            pygame.draw.circle(screen, (200, 200, 255), (int(self.ghost_x), int(self.ghost_y)), 30)

        # HUD
        hud = pygame.Surface((SCREEN_WIDTH, 100), pygame.SRCALPHA)
        hud.fill((30, 30, 40, 220))
        screen.blit(hud, (0, 0))

        pygame.draw.rect(screen, (60, 60, 80), (20, 25, 200, 30), border_radius=15)
        energy_color = (220, 50, 50) if self.ghost_energy < 30 else (50, 200, 50)
        pygame.draw.rect(screen, energy_color, (20, 25, max(0, 200 * self.ghost_energy / 100), 30), border_radius=15)
        pygame.draw.rect(screen, (255, 255, 255), (20, 25, 200, 30), 2, border_radius=15)
        screen.blit(font_small.render(f"⚡ Энергия: {int(self.ghost_energy)}/100", True, (255, 255, 255)), (30, 30))

        # Время в правом верхнем углу
        time_str = f"{int(hour):02d}:{int((hour % 1) * 60):02d}"
        time_color = (150, 150, 255) if is_night else (255, 255, 200)
        time_text = font_small.render(f"🕗 Время: {time_str} ({'Ночь' if is_night else 'День'})", True, time_color)
        screen.blit(time_text, (SCREEN_WIDTH - time_text.get_width() - 30, 30))

        if self.is_lunar_thursday and is_night:
            lunar = pygame.Surface((SCREEN_WIDTH, 50), pygame.SRCALPHA)
            lunar.fill((30, 50, 80, 220))
            screen.blit(lunar, (0, SCREEN_HEIGHT - 50))
            lunar_text = font_medium.render("✨ ЛУННЫЙ ЧЕТВЕРГ! Подойдите к повреждённым книгам для восстановления ✨", True, (173, 216, 230))
            screen.blit(lunar_text, (SCREEN_WIDTH//2 - lunar_text.get_width()//2, SCREEN_HEIGHT - 40))

        task_text = font_small.render("Задание: Помогите посетителю найти книгу", True, (200, 220, 255))
        screen.blit(task_text, (SCREEN_WIDTH - task_text.get_width() - 30, 65))

        controls = font_tiny.render("←→↑↓ — движение | SPACE — фазинг | E — взаимодействие", True, (180, 180, 200))
        screen.blit(controls, (SCREEN_WIDTH//2 - controls.get_width()//2, SCREEN_HEIGHT - 25))


# === ГЛАВНЫЙ ЦИКЛ ===
def main():
    pygame.init()
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("📚 Фантом библиотеки")
    clock = pygame.time.Clock()

    font_large = pygame.font.SysFont("Arial", 32, bold=True)
    font_medium = pygame.font.SysFont("Arial", 24)
    font_small = pygame.font.SysFont("Arial", 18)
    font_tiny = pygame.font.SysFont("Arial", 14)

    # Создаём папки, если их нет
    os.makedirs(PNG_DIR, exist_ok=True)
    os.makedirs(SOUNDS_DIR, exist_ok=True)

    resources = ResourceManager()
    db = DatabaseManager()
    login_screen = LoginScreen(db, resources)
    current_view = "login"
    account_data, game = None, None

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if game:
                    game.save_progress()
                running = False
                break

            if current_view == "login":
                result = login_screen.handle_event(event)
                if isinstance(result, dict):
                    account_data = result
                    current_view = "menu"
                    menu = MainMenu(db, account_data, resources)

            elif current_view == "menu":
                action = menu.handle_event(event)
                if action == "play":
                    current_view = "game"
                    game = Game(db, account_data, resources)
                elif action == "stats":
                    current_view = "stats"
                elif action == "logout":
                    current_view = "login"
                    login_screen = LoginScreen(db, resources)

            elif current_view == "game" and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game.save_progress()
                    current_view = "menu"
                    menu = MainMenu(db, account_data, resources)

        if current_view == "game":
            keys = pygame.key.get_pressed()
            speed = 6 if game.is_phasing else 4

            if keys[pygame.K_LEFT]: game.ghost_x = max(50, game.ghost_x - speed)
            if keys[pygame.K_RIGHT]: game.ghost_x = min(SCREEN_WIDTH - 50, game.ghost_x + speed)
            if keys[pygame.K_UP]: game.ghost_y = max(50, game.ghost_y - speed)
            if keys[pygame.K_DOWN]: game.ghost_y = min(SCREEN_HEIGHT - 50, game.ghost_y + speed)

            if keys[pygame.K_SPACE] and game.ghost_energy >= 20 and game.phasing_cooldown <= 0:
                game.is_phasing = True
                game.ghost_energy -= 20
                game.phasing_cooldown = 5.0
                resources.play_sound(resources.ghost_whisper, 0.3)
            else:
                game.is_phasing = False

            if keys[pygame.K_e] and game.ghost_energy >= 10:
                game.ghost_energy -= 10
                resources.play_sound(resources.book_drop, 0.4)

            game.update(dt)

        screen.fill((20, 20, 30))

        if current_view == "login":
            login_screen.draw(screen, font_large, font_medium, font_small, font_tiny)
        elif current_view == "menu":
            menu.draw(screen, font_large, font_medium, font_small, font_tiny)
        elif current_view == "game":
            game.draw(screen, font_small, font_medium, font_tiny)
        elif current_view == "stats":
            screen.fill((30, 30, 45))
            title = font_large.render("📊 СТАТИСТИКА ИГРОКА", True, (255, 215, 0))
            screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 50))

            stats = db.get_account_stats(account_data["id"])
            stats_list = [
                f"Игрок: {account_data['username']}",
                f"Время в игре: {int(stats['total_playtime'] // 60)} мин {int(stats['total_playtime'] % 60)} сек",
                f"Выполнено заданий: {stats['completed_tasks']}",
                f"Восстановлено книг: {stats['restored_books']}",
                f"Максимальная энергия: {stats['energy_level']}",
                f"Аккаунт создан: {stats['created_at'][:19]}",
                f"Последний вход: {stats['last_login'][:19]}"
            ]

            for i, text in enumerate(stats_list):
                surf = font_medium.render(text, True, (220, 220, 240))
                screen.blit(surf, (SCREEN_WIDTH//2 - surf.get_width()//2, 150 + i * 50))

            back_btn = font_medium.render("Нажмите ESC для возврата в меню", True, (150, 150, 200))
            screen.blit(back_btn, (SCREEN_WIDTH//2 - back_btn.get_width()//2, SCREEN_HEIGHT - 50))

            if pygame.key.get_pressed()[pygame.K_ESCAPE]:
                current_view = "menu"

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
