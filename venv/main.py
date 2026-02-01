import arcade
import random
import math
import time
import json
import os
from pathlib import Path

# Попытка импорта tkinter для диалога выбора файла
try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# Константы
SPEED = 4
SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 700
CAMERA_LERP = 0.13
SCREEN_TITLE = "Fantom of library"

BUTTON_WIDTH = 300
BUTTON_HEIGHT = 80
VISITOR_SCALE = 6
PLAYER_SCALE = 0.35
TABLE_SCALE = 0.3
BOOKSHELF_SCALE = 0.25
FLOATING_BOOK_SCALE = 0.1
POWER_ZONE_SCALE = 0.2
POWER_ZONE_SIZE = 80

INTERACTION_DISTANCE = 80
MANA_COST_INTERACTION = 20
DAY_DURATION = 60.0  # 1 игровой день = 60 сек реального времени

SAVE_FOLDER = Path.home() / "Documents" / "FantomOfLibrary"
SAVE_FOLDER.mkdir(parents=True, exist_ok=True)


class Button:
    def __init__(self, text: str, center_x: float, center_y: float,
                 width=BUTTON_WIDTH, height=BUTTON_HEIGHT, color=arcade.color.DARK_GREEN):
        self.text = text
        self.center_x = center_x
        self.center_y = center_y
        self.width = width
        self.height = height
        self.color = color
        self.text_color = arcade.color.WHITE
        self.font_size = 24

    @property
    def left(self): return self.center_x - self.width / 2
    @property
    def right(self): return self.center_x + self.width / 2
    @property
    def top(self): return self.center_y + self.height / 2
    @property
    def bottom(self): return self.center_y - self.height / 2

    def draw(self):
        rect = arcade.rect.XYWH(self.center_x, self.center_y, self.width, self.height)
        arcade.draw_rect_filled(rect, self.color)
        arcade.draw_text(self.text, self.center_x, self.center_y, self.text_color,
                         self.font_size, anchor_x="center", anchor_y="center")

    def is_clicked(self, x: float, y: float) -> bool:
        return self.left < x < self.right and self.bottom < y < self.top


class PauseView(arcade.View):
    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view
        self.buttons = [
            Button("Продолжить", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 100),
            Button("Сохранить игру", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 20, color=arcade.color.DARK_BLUE),
            Button("В главное меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 60, color=arcade.color.DARK_RED)
        ]

    def on_draw(self):
        self.game_view.on_draw()
        self.window.default_camera.use()
        rect = arcade.rect.XYWH(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, SCREEN_WIDTH * 0.8, SCREEN_HEIGHT * 0.8)
        arcade.draw_rect_filled(rect, (20, 20, 40, 220))
        arcade.draw_rect_outline(rect, arcade.color.GOLD, 3)

        for button in self.buttons:
            button.draw()
        arcade.draw_text("ПАУЗА", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100,
                         arcade.color.WHITE, font_size=48, anchor_x="center")
        arcade.draw_text(f"Время: {self.game_view.get_time_display()}",
                         SCREEN_WIDTH / 2, SCREEN_HEIGHT - 150,
                         arcade.color.GOLD, 24, anchor_x="center")

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        for btn in self.buttons:
            if btn.is_clicked(x, y):
                if btn.text == "Продолжить":
                    self.window.show_view(self.game_view)
                elif btn.text == "Сохранить игру":
                    self.game_view.save_game()
                    self.game_view.notification = "Игра сохранена!"
                    self.game_view.notification_timer = 3.0
                elif btn.text == "В главное меню":
                    main_menu = MainMenu()
                    self.window.show_view(main_menu)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE:
            self.window.show_view(self.game_view)


class GameView(arcade.View):
    def __init__(self):
        super().__init__()
        self.cell_size = 64
        map_name = "library.tmx"
        self.tile_map = arcade.load_tilemap(map_name, scaling=1)

        self.walls_behind_list = self.tile_map.sprite_lists.get("walls behind", arcade.SpriteList())
        self.wall_list = self.tile_map.sprite_lists.get("walls", arcade.SpriteList())
        self.object_list = self.tile_map.sprite_lists.get("objects", arcade.SpriteList())
        self.collision_list = self.tile_map.sprite_lists.get("collision", arcade.SpriteList())
        self.power_zone_list = self.tile_map.sprite_lists.get("power_zones", arcade.SpriteList())

        self.all_sprites = arcade.SpriteList()
        self.tables = arcade.SpriteList()
        self.bookshelves = arcade.SpriteList()
        self.floating_books = arcade.SpriteList()

        self.player_texture_right = arcade.load_texture('ghost.png')
        self.player_texture_left = arcade.load_texture('ghost_l.png')
        self.visitor_texture = arcade.load_texture('visitor_1.png')
        self.book_texture = arcade.load_texture('book.png')
        self.bookshelf_texture = arcade.load_texture('bookshelf.png')
        self.table_texture = arcade.load_texture('table.png')
        self.power_zone_texture = arcade.load_texture('power_zone.png')

        self.world_camera = arcade.camera.Camera2D()
        self.map_width = self.tile_map.width * self.tile_map.tile_width
        self.map_height = self.tile_map.height * self.tile_map.tile_height

        # Игрок
        self.player = arcade.Sprite(self.player_texture_right, scale=PLAYER_SCALE)
        self.player.center_x = 7 * self.cell_size + self.cell_size // 2
        self.player.center_y = 5 * self.cell_size + self.cell_size // 2
        self.all_sprites.append(self.player)
        self.physics_engine = arcade.PhysicsEngineSimple(self.player, self.collision_list)

        # Игровые переменные
        self.game_time = 0.0
        self.is_night = False
        self.mana = 100.0
        self.max_mana = 100.0
        self.mana_regen_rate = 1.0
        self.score = 0
        self.visitors_helped = 0
        self.pulse_time = 0.0
        self.notification = None
        self.notification_timer = 0.0
        self.is_sprinting = False
        self.quest_active = False
        self.target_bookshelf = None
        self.visitor = None
        self.current_table = None

        # Посетители: 1 в день
        self.current_day = -1
        self.visitor_spawned_today = False
        self.visitor_spawn_timer = random.uniform(3.0, 6.0)

        # Звук (только при сбросе книги)
        try:
            self.sound_book_drop = arcade.load_sound("book_drop.wav")
        except Exception:
            self.sound_book_drop = None

        self.setup_objects()

    def setup_objects(self):
        num_tables = 4
        margin = 150
        usable_width = self.map_width - 2 * margin
        for i in range(num_tables):
            x = margin + i * (usable_width / (num_tables - 1)) if num_tables > 1 else self.map_width / 2
            table = arcade.Sprite(self.table_texture, scale=TABLE_SCALE)
            table.left = x
            table.bottom = 70
            self.tables.append(table)
            self.all_sprites.append(table)

        num_shelves = 5
        for i in range(num_shelves):
            x = margin + i * (usable_width / (num_shelves - 1)) if num_shelves > 1 else self.map_width / 2
            shelf = arcade.Sprite(self.bookshelf_texture, scale=BOOKSHELF_SCALE)
            shelf.left = x
            shelf.bottom = 68
            self.bookshelves.append(shelf)
            self.object_list.append(shelf)

        zone = arcade.Sprite(self.power_zone_texture, scale=POWER_ZONE_SCALE)
        zone.center_x = self.map_width - 300
        zone.center_y = 130
        self.power_zone_list.append(zone)
        self.object_list.append(zone)

    def update_time_system(self, delta_time):
        self.game_time += delta_time
        day_progress = (self.game_time % DAY_DURATION) / DAY_DURATION
        self.is_night = day_progress > 0.5

        current_day = int(self.game_time // DAY_DURATION)
        if current_day != self.current_day:
            self.current_day = current_day
            self.visitor_spawned_today = False

    def get_time_display(self):
        total_seconds = int(self.game_time)
        days = total_seconds // int(DAY_DURATION)
        seconds_in_day = total_seconds % int(DAY_DURATION)
        hours = seconds_in_day // 5
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        day_name = day_names[days % 7]
        period = "Ночь" if self.is_night else "День"
        return f"{day_name} {hours:02d}:00 | {period}"

    def on_draw(self):
        self.clear()
        bg_color = (10, 10, 30) if self.is_night else (40, 40, 60)
        arcade.set_background_color(bg_color)

        self.world_camera.use()
        self.walls_behind_list.draw()
        self.wall_list.draw()
        self.object_list.draw()
        self.all_sprites.draw()
        self.floating_books.draw()
        self.power_zone_list.draw()

        if self.quest_active and self.target_bookshelf:
            pulse = math.sin(self.pulse_time * 6) * 0.3 + 0.7
            radius = 25 + 10 * pulse
            arcade.draw_circle_filled(
                self.target_bookshelf.center_x,
                self.target_bookshelf.center_y + 30,
                radius, (255, 255, 0, int(100 * pulse))
            )
            arcade.draw_circle_outline(
                self.target_bookshelf.center_x,
                self.target_bookshelf.center_y + 30,
                radius, arcade.color.YELLOW, 3
            )

        self.window.default_camera.use()

        panel_width, panel_height = 400, 120
        panel_x, panel_y = 20, SCREEN_HEIGHT - panel_height - 20
        arcade.draw_lrbt_rectangle_filled(panel_x, panel_x + panel_width, panel_y, panel_y + panel_height, (20, 20, 40, 220))
        arcade.draw_lrbt_rectangle_outline(panel_x, panel_x + panel_width, panel_y, panel_y + panel_height, arcade.color.GOLD, 2)
        arcade.draw_text("АКТИВНЫЕ ЗАДАНИЯ", panel_x + 20, panel_y + panel_height - 30, arcade.color.GOLD, 18, bold=True)
        if self.quest_active:
            arcade.draw_text("• Уронь книгу из шкафа (E)", panel_x + 30, panel_y + panel_height - 70, arcade.color.WHITE, 14)

        arcade.draw_text(f"Очки: {self.score} | Помог: {self.visitors_helped}", SCREEN_WIDTH - 20, SCREEN_HEIGHT - 40, arcade.color.GOLD, 16, anchor_x="right")

        mana_bar_x, mana_bar_y = 20, 60
        fill_width = (self.mana / self.max_mana) * 200
        if fill_width > 0:
            arcade.draw_lrbt_rectangle_filled(mana_bar_x, mana_bar_x + fill_width, mana_bar_y, mana_bar_y + 20, arcade.color.BLUE)
        arcade.draw_lrbt_rectangle_outline(mana_bar_x, mana_bar_x + 200, mana_bar_y, mana_bar_y + 20, arcade.color.WHITE, 2)
        arcade.draw_text(f"Мана: {int(self.mana)}/{int(self.max_mana)}", mana_bar_x + 210, mana_bar_y + 5, arcade.color.WHITE, 14)

        arcade.draw_text(self.get_time_display(), SCREEN_WIDTH - 20, 20, (200, 200, 255), 16, anchor_x="right")

        hints = ["WASD - движение", "SHIFT - бег", "E - взаимодействие", "ESC - пауза"]
        for i, hint in enumerate(hints):
            arcade.draw_text(hint, SCREEN_WIDTH - 20, SCREEN_HEIGHT - 80 - i * 20, arcade.color.GRAY, 12, anchor_x="right")

        if self.notification and self.notification_timer > 0:
            arcade.draw_text(self.notification, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 200, arcade.color.GREEN, 28, anchor_x="center", bold=True)

    def on_update(self, delta_time: float):
        self.update_time_system(delta_time)

        if self.notification_timer > 0:
            self.notification_timer -= delta_time
            if self.notification_timer <= 0:
                self.notification = None

        # Спринт
        current_speed = SPEED * 2 if self.is_sprinting else SPEED
        if self.player.change_x != 0:
            self.player.change_x = current_speed if self.player.change_x > 0 else -current_speed
        if self.player.change_y != 0:
            self.player.change_y = current_speed if self.player.change_y > 0 else -current_speed

        if self.is_sprinting:
            self.mana = max(0.0, self.mana - 2.0 * delta_time)

        # Реген маны
        regen_mult = 1.0
        for zone in self.power_zone_list:
            dist = math.hypot(self.player.center_x - zone.center_x, self.player.center_y - zone.center_y)
            if dist < POWER_ZONE_SIZE:
                regen_mult = 3.0
                break
        self.mana = min(self.max_mana, self.mana + self.mana_regen_rate * regen_mult * delta_time)

        self.physics_engine.update()

        cam_x, cam_y = self.world_camera.position
        target_x, target_y = self.player.center_x, self.player.center_y
        new_x = arcade.math.lerp(cam_x, target_x, CAMERA_LERP)
        new_y = arcade.math.lerp(cam_y, target_y, CAMERA_LERP)
        half_w = self.world_camera.viewport_width / 2
        half_h = self.world_camera.viewport_height / 2
        new_x = max(half_w, min(self.map_width - half_w, new_x))
        new_y = max(half_h, min(self.map_height - half_h, new_y))
        self.world_camera.position = (new_x, new_y)

        # Спавн посетителя (1 в день)
        if not self.is_night and not self.visitor_spawned_today:
            self.visitor_spawn_timer -= delta_time
            if self.visitor_spawn_timer <= 0:
                self.spawn_visitor()
                self.visitor_spawned_today = True
                self.visitor_spawn_timer = float('inf')

        # === ЛОГИКА ПОСЕТИТЕЛЯ ===
        if self.visitor:
            self.visitor.center_y = 118

            if self.visitor.state == "arriving":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.state = "waiting"
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "waiting":
                closest_book = None
                min_dist = float('inf')
                for book in self.floating_books:
                    dist = math.hypot(self.visitor.center_x - book.center_x, self.visitor.center_y - book.center_y)
                    if dist < min_dist:
                        min_dist = dist
                        closest_book = book

                if closest_book and min_dist < INTERACTION_DISTANCE:
                    # Берёт книгу
                    closest_book.remove_from_sprite_lists()
                    if closest_book in self.floating_books:
                        self.floating_books.remove(closest_book)
                    self.score += 10
                    self.visitors_helped += 1
                    self.visitor.state = "returning_to_table"
                    self.visitor.target_x = self.current_table.center_x
                elif closest_book:
                    self.visitor.state = "going_to_book"
                    self.visitor.target_x = closest_book.center_x
                else:
                    # Запускаем квест, если его ещё нет
                    if not self.quest_active and self.quest_delay is not None:
                        self.quest_timer += delta_time
                        if self.quest_timer >= self.quest_delay:
                            self.start_quest()
                            self.quest_delay = None

            elif self.visitor.state == "going_to_book":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    for book in self.floating_books:
                        dist = math.hypot(self.visitor.center_x - book.center_x, self.visitor.center_y - book.center_y)
                        if dist < INTERACTION_DISTANCE:
                            book.remove_from_sprite_lists()
                            if book in self.floating_books:
                                self.floating_books.remove(book)
                            self.score += 10
                            self.visitors_helped += 1
                            break
                    self.visitor.state = "returning_to_table"
                    self.visitor.target_x = self.current_table.center_x
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "returning_to_table":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.state = "post_interaction_wait"
                    self.visitor.wait_end_time = time.time() + 5
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "post_interaction_wait":
                if time.time() >= self.visitor.wait_end_time:
                    self.visitor.state = "leaving"
                    self.visitor.target_x = 50

            elif self.visitor.state == "leaving":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.remove_from_sprite_lists()
                    if self.visitor in self.object_list:
                        self.object_list.remove(self.visitor)
                    self.visitor = None
                    self.quest_active = False
                    self.target_bookshelf = None
                    # Разрешаем нового посетителя в тот же день!
                    self.visitor_spawned_today = False
                    self.visitor_spawn_timer = random.uniform(4.0, 8.0)
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

        self.pulse_time += delta_time

    def on_key_press(self, key, modifiers):
        if key == arcade.key.W:
            self.player.change_y = SPEED
        elif key == arcade.key.S:
            self.player.change_y = -SPEED
        elif key == arcade.key.A:
            self.player.change_x = -SPEED
            self.player.texture = self.player_texture_left
        elif key == arcade.key.D:
            self.player.change_x = SPEED
            self.player.texture = self.player_texture_right
        elif key == arcade.key.LSHIFT or key == arcade.key.RSHIFT:
            self.is_sprinting = True
        elif key == arcade.key.E:
            self.handle_interaction()
        elif key == arcade.key.ESCAPE:
            pause = PauseView(self)
            self.window.show_view(pause)

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.S):
            self.player.change_y = 0
        if key in (arcade.key.A, arcade.key.D):
            self.player.change_x = 0
        if key in (arcade.key.LSHIFT, arcade.key.RSHIFT):
            self.is_sprinting = False

    def handle_interaction(self):
        if not self.quest_active or self.target_bookshelf is None:
            return

        dist_to_shelf = math.hypot(
            self.player.center_x - self.target_bookshelf.center_x,
            self.player.center_y - self.target_bookshelf.center_y
        )

        if dist_to_shelf < INTERACTION_DISTANCE and self.mana >= MANA_COST_INTERACTION:
            book = arcade.Sprite(self.book_texture, scale=FLOATING_BOOK_SCALE)
            book.center_x = self.target_bookshelf.center_x
            book.center_y = 90
            self.floating_books.append(book)
            self.object_list.append(book)
            self.mana -= MANA_COST_INTERACTION
            self.quest_active = False

            # 🔊 Только при сбросе!
            if self.sound_book_drop:
                arcade.play_sound(self.sound_book_drop)

    def spawn_visitor(self):
        if self.visitor is not None:
            return

        available_tables = [t for t in self.tables]
        if not available_tables:
            return

        table = random.choice(available_tables)
        visitor = arcade.Sprite(self.visitor_texture, scale=VISITOR_SCALE)
        visitor.center_x = 100
        visitor.center_y = 118
        visitor.state = "arriving"
        visitor.target_x = table.center_x
        self.current_table = table
        self.object_list.append(visitor)
        self.visitor = visitor

        # Сбрасываем квест и запускаем таймер
        self.quest_active = False
        self.target_bookshelf = None
        self.quest_delay = random.uniform(3.0, 8.0)
        self.quest_timer = 0.0

    def start_quest(self):
        if self.visitor is None or self.visitor.state != "waiting":
            return
        self.quest_active = True
        self.target_bookshelf = random.choice(self.bookshelves)

    def save_game(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"save_{timestamp}.json"
        filepath = SAVE_FOLDER / filename

        save_data = {
            "score": self.score,
            "visitors_helped": self.visitors_helped,
            "game_time": self.game_time,
            "player_x": self.player.center_x,
            "player_y": self.player.center_y,
            "mana": self.mana
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
        except Exception:
            pass

    def load_game(self):
        if not TKINTER_AVAILABLE:
            return False

        root = tk.Tk()
        root.withdraw()
        filepath = filedialog.askopenfilename(
            title="Выберите файл сохранения",
            initialdir=SAVE_FOLDER,
            filetypes=[("Файлы сохранений", "*.json"), ("Все файлы", "*.*")]
        )

        if not filepath:
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                save_data = json.load(f)
            self.score = save_data.get("score", 0)
            self.visitors_helped = save_data.get("visitors_helped", 0)
            self.game_time = save_data.get("game_time", 0.0)
            self.mana = save_data.get("mana", 100.0)
            self.player.center_x = save_data.get("player_x", self.player.center_x)
            self.player.center_y = save_data.get("player_y", self.player.center_y)
            return True
        except Exception:
            return False


class MainMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.buttons = [
            Button("Новая игра", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 80),
            Button("Загрузить игру", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, color=arcade.color.DARK_BLUE),
            Button("Выход", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 80, color=arcade.color.DARK_RED)
        ]

    def on_draw(self):
        self.clear(arcade.color.DARK_BLUE)
        for i in range(20):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            size = random.randint(1, 3)
            arcade.draw_circle_filled(x, y, size, (100, 100, 150, 100))

        arcade.draw_text(
            "FANTOM OF LIBRARY",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT - 100,
            arcade.color.WHITE,
            font_size=50,
            anchor_x="center"
        )
        arcade.draw_text(
            "Защитник знаний в вечной тишине...",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT - 140,
            arcade.color.GRAY,
            font_size=20,
            anchor_x="center"
        )

        for button in self.buttons:
            button.draw()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        for btn in self.buttons:
            if btn.is_clicked(x, y):
                if btn.text == "Новая игра":
                    game = GameView()
                    game.setup_objects()
                    self.window.show_view(game)
                elif btn.text == "Загрузить игру":
                    game = GameView()
                    game.setup_objects()
                    if game.load_game():
                        self.window.show_view(game)
                elif btn.text == "Выход":
                    arcade.exit()


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    main_menu = MainMenu()
    window.show_view(main_menu)
    arcade.run()


if __name__ == "__main__":
    main()