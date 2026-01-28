import arcade
import random
import math
import time
import json
import os

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
BOOK_SCALE = 0.5
FLOATING_BOOK_SCALE = 0.1
POWER_ZONE_SCALE = 0.4

INTERACTION_DISTANCE = 80
PHASING_COST = 15  # Стоимость прохождения сквозь стены
PHASING_DURATION = 1.5  # Секунды фазинга

# Время суток
DAY_DURATION = 60.0  # 60 секунд = 1 игровой день
MOON_PHASE_DURATION = 7 * DAY_DURATION  # Лунный цикл = 7 дней


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
            Button("Загрузить игру", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 60, color=arcade.color.DARK_BLUE),
            Button("В главное меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 140, color=arcade.color.DARK_RED)
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
                    arcade.draw_text("Сохранено!", SCREEN_WIDTH/2, 100, arcade.color.GREEN, 24, anchor_x="center")
                elif btn.text == "Загрузить игру":
                    if self.game_view.load_game():
                        self.window.show_view(self.game_view)
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
        self.power_zone_list = self.tile_map.sprite_lists.get("power_zones", arcade.SpriteList())  # Места силы

        self.all_sprites = arcade.SpriteList()
        self.tables = arcade.SpriteList()
        self.bookshelves = arcade.SpriteList()
        self.damaged_books = arcade.SpriteList()  # Повреждённые книги

        # Текстуры
        self.player_texture_right = arcade.load_texture('ghost.png')
        self.player_texture_left = arcade.load_texture('ghost_l.png')
        self.player_texture_phasing = arcade.load_texture('ghost_phasing.png')  # Для фазинга
        self.visitor_texture = arcade.load_texture('visitor_1.png')
        self.book_texture = arcade.load_texture('book.png')
        self.damaged_book_texture = arcade.load_texture('book_damaged.png')
        self.bookshelf_texture = arcade.load_texture('bookshelf.png')
        self.table_texture = arcade.load_texture('table.png')
        self.power_zone_texture = arcade.load_texture('power_zone.png')

        self.world_camera = arcade.camera.Camera2D()
        self.map_width = self.tile_map.width * self.tile_map.tile_width
        self.map_height = self.tile_map.height * self.tile_map.tile_height

        # Система времени
        self.game_time = 0.0  # Секунды с начала игры
        self.is_night = False
        self.is_moon_thursday = False
        self.last_moon_check = -1

        # Мана
        self.mana = 100.0
        self.max_mana = 100.0
        self.mana_regen_rate = 1.0
        self.is_phasing = False
        self.phasing_timer = 0.0

        # Квест и посетители
        self.quest_active = False
        self.target_bookshelf = None
        self.visitor = None
        self.current_table = None
        self.score = 0
        self.visitors_helped = 0

        self.floating_books = arcade.SpriteList()

        self.pulse_time = 0.0
        self.visitor_spawn_timer = random.uniform(5.0, 15.0)
        self.quest_timer = None
        self.quest_delay = None

        # Звуки (безопасная загрузка)
        try:
            self.sound_book_drop = arcade.load_sound("sounds/book_drop.wav")
            self.sound_phasing = arcade.load_sound("sounds/phasing.wav")
            self.sound_restore = arcade.load_sound("sounds/restore.wav")
            self.sound_power_zone = arcade.load_sound("sounds/power_zone.wav")
        except:
            self.sound_book_drop = None
            self.sound_phasing = None
            self.sound_restore = None
            self.sound_power_zone = None

    def setup(self):
        # Игрок
        self.player = arcade.Sprite(self.player_texture_right, scale=PLAYER_SCALE)
        self.player.center_x = 7 * self.cell_size + self.cell_size // 2
        self.player.center_y = 5 * self.cell_size + self.cell_size // 2
        self.all_sprites.append(self.player)

        # Столы
        num_tables = 4
        margin = 150
        usable_width = self.map_width - 2 * margin
        for i in range(num_tables):
            if num_tables > 1:
                x = margin + i * (usable_width / (num_tables - 1))
            else:
                x = self.map_width / 2
            table = arcade.Sprite(self.table_texture, scale=TABLE_SCALE)
            table.left = x
            table.bottom = 70
            self.tables.append(table)
            self.all_sprites.append(table)

        # Шкафы
        num_shelves = 5
        for i in range(num_shelves):
            if num_shelves > 1:
                x = margin + i * (usable_width / (num_shelves - 1))
            else:
                x = self.map_width / 2
            shelf = arcade.Sprite(self.bookshelf_texture, scale=BOOKSHELF_SCALE)
            shelf.left = x
            shelf.bottom = 68
            self.bookshelves.append(shelf)
            self.object_list.append(shelf)

        # Места силы (пример размещения)
        for i in range(3):
            zone = arcade.Sprite(self.power_zone_texture, scale=POWER_ZONE_SCALE)
            zone.center_x = 300 + i * 400
            zone.center_y = 200 + random.randint(-50, 50)
            self.power_zone_list.append(zone)
            self.object_list.append(zone)

        # Повреждённые книги (для восстановления в лунный четверг)
        if self.is_moon_thursday:
            for i in range(3):
                book = arcade.Sprite(self.damaged_book_texture, scale=BOOK_SCALE * 0.7)
                book.center_x = 400 + i * 300
                book.center_y = 150
                book.is_restored = False
                self.damaged_books.append(book)
                self.object_list.append(book)

        self.physics_engine = arcade.PhysicsEngineSimple(self.player, self.collision_list)

    def update_time_system(self, delta_time):
        """Система времени суток и лунного цикла"""
        self.game_time += delta_time
        
        # Смена дня/ночи
        day_progress = (self.game_time % DAY_DURATION) / DAY_DURATION
        self.is_night = day_progress > 0.5  # Ночь = вторая половина цикла
        
        # Проверка "лунного четверга" (каждый 7-й день в полночь)
        current_day = int(self.game_time / DAY_DURATION)
        if current_day != self.last_moon_check:
            self.last_moon_check = current_day
            # Четверг = 4-й день недели (0=понедельник)
            is_thursday = (current_day % 7) == 3
            is_midnight = 0.7 < day_progress < 0.8  # Примерно полночь
            
            if is_thursday and is_midnight:
                self.is_moon_thursday = True
                # Создаём повреждённые книги для восстановления
                self.spawn_damaged_books()
            else:
                self.is_moon_thursday = False

    def spawn_damaged_books(self):
        """Создаёт повреждённые книги для восстановления в лунный четверг"""
        self.damaged_books = arcade.SpriteList()
        for i in range(random.randint(2, 4)):
            book = arcade.Sprite(self.damaged_book_texture, scale=BOOK_SCALE * 0.7)
            book.center_x = 400 + i * 300
            book.center_y = 150
            book.is_restored = False
            self.damaged_books.append(book)
            self.object_list.append(book)

    def start_phasing(self):
        """Активация фазинга через стены"""
        if self.mana >= PHASING_COST and not self.is_phasing:
            self.is_phasing = True
            self.phasing_timer = PHASING_DURATION
            self.mana -= PHASING_COST
            if self.sound_phasing:
                arcade.play_sound(self.sound_phasing)
            # Временно убираем стены из физики
            self.physics_engine = arcade.PhysicsEngineSimple(self.player, arcade.SpriteList())

    def stop_phasing(self):
        """Завершение фазинга"""
        self.is_phasing = False
        # Возвращаем стены в физику
        self.physics_engine = arcade.PhysicsEngineSimple(self.player, self.collision_list)

    def handle_restore_book(self):
        """Восстановление повреждённой книги (только в лунный четверг)"""
        if not self.is_moon_thursday:
            return
            
        for book in self.damaged_books:
            if not book.is_restored:
                dist = math.hypot(self.player.center_x - book.center_x, 
                                self.player.center_y - book.center_y)
                if dist < INTERACTION_DISTANCE and self.mana >= 25:
                    book.is_restored = True
                    book.alpha = 128  # Полупрозрачность как индикатор восстановления
                    self.mana -= 25
                    self.score += 25
                    self.visitors_helped += 1
                    if self.sound_restore:
                        arcade.play_sound(self.sound_restore)
                    break

    def get_time_display(self):
        """Форматированное отображение времени"""
        total_seconds = int(self.game_time)
        days = total_seconds // int(DAY_DURATION)
        seconds_in_day = total_seconds % int(DAY_DURATION)
        hours = seconds_in_day // 5  # 12 часов в игровом дне
        
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        day_name = day_names[days % 7]
        
        period = "Ночь" if self.is_night else "День"
        moon = "🌕" if self.is_moon_thursday else ""
        
        return f"{day_name} {hours:02d}:00 | {period} {moon}"

    def on_draw(self):
        self.clear()
        
        # Фон в зависимости от времени суток
        if self.is_night:
            bg_color = (10, 10, 30) if not self.is_moon_thursday else (20, 10, 40)  # Фиолетовый в лунную ночь
        else:
            bg_color = (40, 40, 60)
        arcade.set_background_color(bg_color)
        
        self.world_camera.use()

        self.walls_behind_list.draw()
        self.wall_list.draw()
        self.object_list.draw()
        self.all_sprites.draw()
        self.floating_books.draw()
        self.damaged_books.draw()
        self.power_zone_list.draw()

        # Подсветка целевого шкафа
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

        # Визуализация фазинга
        if self.is_phasing:
            arcade.draw_circle_filled(
                self.player.center_x, self.player.center_y,
                40, (100, 100, 255, 80)
            )

        # UI
        self.window.default_camera.use()
        
        # Панель заданий
        panel_width = 400
        panel_height = 160 if self.is_moon_thursday else 120
        panel_x = 20
        panel_y = SCREEN_HEIGHT - panel_height - 20

        arcade.draw_lrbt_rectangle_filled(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            (20, 20, 40, 220)
        )
        arcade.draw_lrbt_rectangle_outline(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            arcade.color.GOLD, 2
        )
        arcade.draw_text(
            "АКТИВНЫЕ ЗАДАНИЯ",
            panel_x + 20, panel_y + panel_height - 30,
            arcade.color.GOLD, 18, bold=True
        )
        
        if self.quest_active:
            arcade.draw_text(
                "• Уронь книгу из шкафа (E)", 
                panel_x + 30, panel_y + panel_height - 70,
                arcade.color.WHITE, 14
            )
        
        if self.is_moon_thursday:
            arcade.draw_text(
                "🌕 ЛУННЫЙ ЧЕТВЕРГ! 🌕",
                panel_x + 20, panel_y + panel_height - 100,
                arcade.color.LIGHT_BLUE, 16, bold=True
            )
            arcade.draw_text(
                "• Восстанови книги (R)",
                panel_x + 30, panel_y + panel_height - 130,
                arcade.color.WHITE, 14
            )

        # Счётчик очков
        arcade.draw_text(
            f"Очки: {self.score} | Помог: {self.visitors_helped}",
            SCREEN_WIDTH - 20,
            SCREEN_HEIGHT - 40,
            arcade.color.GOLD,
            16,
            anchor_x="right"
        )

        # Шкала маны
        mana_bar_width = 200
        mana_bar_height = 20
        mana_bar_x = 20
        mana_bar_y = 60

        fill_width = (self.mana / self.max_mana) * mana_bar_width
        if fill_width > 0:
            arcade.draw_lrbt_rectangle_filled(
                mana_bar_x, mana_bar_x + fill_width,
                mana_bar_y, mana_bar_y + mana_bar_height,
                arcade.color.BLUE
            )
        arcade.draw_lrbt_rectangle_outline(
            mana_bar_x, mana_bar_x + mana_bar_width,
            mana_bar_y, mana_bar_y + mana_bar_height,
            arcade.color.WHITE, 2
        )
        arcade.draw_text(f"Мана: {int(self.mana)}/{int(self.max_mana)}", 
                        mana_bar_x + mana_bar_width + 10, mana_bar_y + 5, 
                        arcade.color.WHITE, 14)

        # Индикатор времени
        time_display = self.get_time_display()
        arcade.draw_text(
            time_display,
            SCREEN_WIDTH - 20, 20,
            arcade.color.GOLD if self.is_moon_thursday else (200, 200, 255),
            16,
            anchor_x="right"
        )

        # Подсказки управления
        hints = [
            "WASD - движение",
            "E - взаимодействие",
            "F - фазинг через стены",
            "R - восстановить книгу (в ночь)",
            "ESC - пауза"
        ]
        for i, hint in enumerate(hints):
            arcade.draw_text(hint, 20, SCREEN_HEIGHT - 80 - i * 20, 
                           arcade.color.GRAY, 12)

    def on_update(self, delta_time: float):
        self.update_time_system(delta_time)
        
        # Обновление фазинга
        if self.is_phasing:
            self.phasing_timer -= delta_time
            if self.phasing_timer <= 0:
                self.stop_phasing()
        
        # Регенерация маны (ускоренная в зонах силы)
        regen_mult = 1.0
        for zone in self.power_zone_list:
            dist = math.hypot(self.player.center_x - zone.center_x,
                            self.player.center_y - zone.center_y)
            if dist < 100:
                regen_mult = 3.0  # Ускоренная регенерация
                break
        self.mana = min(self.max_mana, self.mana + self.mana_regen_rate * regen_mult * delta_time)

        self.physics_engine.update()

        # Плавная камера
        cam_x, cam_y = self.world_camera.position
        target_x = self.player.center_x
        target_y = self.player.center_y
        new_x = arcade.math.lerp(cam_x, target_x, CAMERA_LERP)
        new_y = arcade.math.lerp(cam_y, target_y, CAMERA_LERP)

        half_w = self.world_camera.viewport_width / 2
        half_h = self.world_camera.viewport_height / 2
        new_x = max(half_w, min(self.map_width - half_w, new_x))
        new_y = max(half_h, min(self.map_height - half_h, new_y))
        self.world_camera.position = (new_x, new_y)

        # Спавн посетителя
        self.visitor_spawn_timer -= delta_time
        if self.visitor_spawn_timer <= 0 and self.visitor is None and not self.is_night:
            self.spawn_visitor()

        # Движение и логика посетителя
        if self.visitor:
            self.visitor.center_y = 118

            if self.visitor.state == "arriving":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.state = "waiting"
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "waiting":
                book_to_take = None
                for book in self.floating_books:
                    dist = math.hypot(
                        self.visitor.center_x - book.center_x,
                        self.visitor.center_y - book.center_y
                    )
                    if dist < INTERACTION_DISTANCE:
                        book_to_take = book
                        break

                if book_to_take:
                    book_to_take.remove_from_sprite_lists()
                    self.score += 10
                    self.visitors_helped += 1
                    if self.sound_book_drop:
                        arcade.play_sound(self.sound_book_drop)
                    self.visitor.state = "returning_to_table"
                    self.visitor.target_x = self.current_table.center_x
                else:
                    if self.quest_delay is not None:
                        self.quest_timer += delta_time
                        if self.quest_timer >= self.quest_delay:
                            self.start_quest()
                            self.quest_delay = None

            elif self.visitor.state == "returning_to_table":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.state = "reading"
                    self.visitor.read_end_time = time.time() + 15
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "reading":
                if time.time() >= self.visitor.read_end_time:
                    if random.random() < 0.5:
                        self.visitor.state = "leaving"
                        self.visitor.target_x = 50
                    else:
                        self.visitor.state = "waiting"
                        self.quest_delay = random.uniform(5.0, 10.0)
                        self.quest_timer = 0.0

            elif self.visitor.state == "leaving":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.remove_from_sprite_lists()
                    self.visitor = None
                    self.visitor_spawn_timer = random.uniform(10.0, 20.0)

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
        elif key == arcade.key.E:
            self.handle_interaction()
        elif key == arcade.key.F and not self.is_phasing:
            self.start_phasing()
        elif key == arcade.key.R:
            self.handle_restore_book()
        elif key == arcade.key.ESCAPE:
            pause = PauseView(self)
            self.window.show_view(pause)

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.S):
            self.player.change_y = 0
        if key in (arcade.key.A, arcade.key.D):
            self.player.change_x = 0

    def handle_interaction(self):
        if not self.quest_active or self.target_bookshelf is None:
            return

        dist_to_shelf = math.hypot(
            self.player.center_x - self.target_bookshelf.center_x,
            self.player.center_y - self.target_bookshelf.center_y
        )

        if dist_to_shelf < INTERACTION_DISTANCE and self.mana >= 10:
            book = arcade.Sprite(self.book_texture, scale=FLOATING_BOOK_SCALE)
            book.center_x = self.target_bookshelf.center_x
            book.center_y = 90
            self.floating_books.append(book)
            self.object_list.append(book)
            self.mana -= 10
            self.quest_active = False
            if self.sound_book_drop:
                arcade.play_sound(self.sound_book_drop)

    def spawn_visitor(self):
        if self.visitor is not None:
            return

        entrance_x = 100
        entrance_y = 118

        self.visitor = arcade.Sprite(self.visitor_texture, scale=VISITOR_SCALE)
        self.visitor.center_x = entrance_x
        self.visitor.center_y = entrance_y
        self.visitor.state = "arriving"
        self.current_table = random.choice(self.tables)
        self.visitor.target_x = self.current_table.center_x

        self.object_list.append(self.visitor)
        self.quest_delay = random.uniform(3.0, 8.0)
        self.quest_timer = 0.0

    def start_quest(self):
        if self.quest_active or self.visitor is None or self.visitor.state != "waiting":
            return
        self.quest_active = True
        self.target_bookshelf = random.choice(self.bookshelves)

    def save_game(self):
        """Сохранение прогресса в JSON"""
        save_data = {
            "score": self.score,
            "visitors_helped": self.visitors_helped,
            "game_time": self.game_time,
            "player_x": self.player.center_x,
            "player_y": self.player.center_y,
            "mana": self.mana
        }
        try:
            with open("savegame.json", "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
            print("Игра сохранена!")
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def load_game(self):
        """Загрузка прогресса из JSON"""
        try:
            if not os.path.exists("savegame.json"):
                print("Файл сохранения не найден!")
                return False
                
            with open("savegame.json", "r", encoding="utf-8") as f:
                save_data = json.load(f)
            
            self.score = save_data.get("score", 0)
            self.visitors_helped = save_data.get("visitors_helped", 0)
            self.game_time = save_data.get("game_time", 0.0)
            self.mana = save_data.get("mana", 100.0)
            
            # Перемещаем игрока
            self.player.center_x = save_data.get("player_x", self.player.center_x)
            self.player.center_y = save_data.get("player_y", self.player.center_y)
            
            print("Игра загружена!")
            return True
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return False


class MainMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.buttons = [
            Button("Новая игра", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 80),
            Button("Загрузить игру", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, color=arcade.color.DARK_BLUE),
            Button("Выход", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 80, color=arcade.color.DARK_RED)
        ]
        self.title_alpha = 255

    def on_draw(self):
        self.clear(arcade.color.DARK_BLUE)
        
        # Анимированный фон
        for i in range(20):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            size = random.randint(1, 3)
            arcade.draw_circle_filled(x, y, size, (100, 100, 150, 100))
        
        arcade.draw_text("FANTOM OF LIBRARY", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100,
                         arcade.color.WHITE, font_size=50, anchor_x="center",
                         start_x=SCREEN_WIDTH/2 - 250, width=500, align="center")
        arcade.draw_text("Защитник знаний в вечной тишине...", 
                        SCREEN_WIDTH / 2, SCREEN_HEIGHT - 140,
                        arcade.color.GRAY, font_size=20, anchor_x="center")
        
        for button in self.buttons:
            button.draw()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        for btn in self.buttons:
            if btn.is_clicked(x, y):
                if btn.text == "Новая игра":
                    game = GameView()
                    game.setup()
                    self.window.show_view(game)
                elif btn.text == "Загрузить игру":
                    game = GameView()
                    game.setup()
                    if game.load_game():
                        self.window.show_view(game)
                    else:
                        # Показать сообщение об ошибке
                        pass
                elif btn.text == "Выход":
                    arcade.exit()


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    main_menu = MainMenu()
    window.show_view(main_menu)
    arcade.run()


if __name__ == "__main__":
    main()import arcade
import random
import math
import time
import json
import os

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
BOOK_SCALE = 0.5
FLOATING_BOOK_SCALE = 0.1
POWER_ZONE_SCALE = 0.4

INTERACTION_DISTANCE = 80
PHASING_COST = 15  # Стоимость прохождения сквозь стены
PHASING_DURATION = 1.5  # Секунды фазинга

# Время суток
DAY_DURATION = 60.0  # 60 секунд = 1 игровой день
MOON_PHASE_DURATION = 7 * DAY_DURATION  # Лунный цикл = 7 дней


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
            Button("Загрузить игру", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 60, color=arcade.color.DARK_BLUE),
            Button("В главное меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 140, color=arcade.color.DARK_RED)
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
                    arcade.draw_text("Сохранено!", SCREEN_WIDTH/2, 100, arcade.color.GREEN, 24, anchor_x="center")
                elif btn.text == "Загрузить игру":
                    if self.game_view.load_game():
                        self.window.show_view(self.game_view)
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
        self.power_zone_list = self.tile_map.sprite_lists.get("power_zones", arcade.SpriteList())  # Места силы

        self.all_sprites = arcade.SpriteList()
        self.tables = arcade.SpriteList()
        self.bookshelves = arcade.SpriteList()
        self.damaged_books = arcade.SpriteList()  # Повреждённые книги

        # Текстуры
        self.player_texture_right = arcade.load_texture('ghost.png')
        self.player_texture_left = arcade.load_texture('ghost_l.png')
        self.player_texture_phasing = arcade.load_texture('ghost_phasing.png')  # Для фазинга
        self.visitor_texture = arcade.load_texture('visitor_1.png')
        self.book_texture = arcade.load_texture('book.png')
        self.damaged_book_texture = arcade.load_texture('book_damaged.png')
        self.bookshelf_texture = arcade.load_texture('bookshelf.png')
        self.table_texture = arcade.load_texture('table.png')
        self.power_zone_texture = arcade.load_texture('power_zone.png')

        self.world_camera = arcade.camera.Camera2D()
        self.map_width = self.tile_map.width * self.tile_map.tile_width
        self.map_height = self.tile_map.height * self.tile_map.tile_height

        # Система времени
        self.game_time = 0.0  # Секунды с начала игры
        self.is_night = False
        self.is_moon_thursday = False
        self.last_moon_check = -1

        # Мана
        self.mana = 100.0
        self.max_mana = 100.0
        self.mana_regen_rate = 1.0
        self.is_phasing = False
        self.phasing_timer = 0.0

        # Квест и посетители
        self.quest_active = False
        self.target_bookshelf = None
        self.visitor = None
        self.current_table = None
        self.score = 0
        self.visitors_helped = 0

        self.floating_books = arcade.SpriteList()

        self.pulse_time = 0.0
        self.visitor_spawn_timer = random.uniform(5.0, 15.0)
        self.quest_timer = None
        self.quest_delay = None

        # Звуки (безопасная загрузка)
        try:
            self.sound_book_drop = arcade.load_sound("sounds/book_drop.wav")
            self.sound_phasing = arcade.load_sound("sounds/phasing.wav")
            self.sound_restore = arcade.load_sound("sounds/restore.wav")
            self.sound_power_zone = arcade.load_sound("sounds/power_zone.wav")
        except:
            self.sound_book_drop = None
            self.sound_phasing = None
            self.sound_restore = None
            self.sound_power_zone = None

    def setup(self):
        # Игрок
        self.player = arcade.Sprite(self.player_texture_right, scale=PLAYER_SCALE)
        self.player.center_x = 7 * self.cell_size + self.cell_size // 2
        self.player.center_y = 5 * self.cell_size + self.cell_size // 2
        self.all_sprites.append(self.player)

        # Столы
        num_tables = 4
        margin = 150
        usable_width = self.map_width - 2 * margin
        for i in range(num_tables):
            if num_tables > 1:
                x = margin + i * (usable_width / (num_tables - 1))
            else:
                x = self.map_width / 2
            table = arcade.Sprite(self.table_texture, scale=TABLE_SCALE)
            table.left = x
            table.bottom = 70
            self.tables.append(table)
            self.all_sprites.append(table)

        # Шкафы
        num_shelves = 5
        for i in range(num_shelves):
            if num_shelves > 1:
                x = margin + i * (usable_width / (num_shelves - 1))
            else:
                x = self.map_width / 2
            shelf = arcade.Sprite(self.bookshelf_texture, scale=BOOKSHELF_SCALE)
            shelf.left = x
            shelf.bottom = 68
            self.bookshelves.append(shelf)
            self.object_list.append(shelf)

        # Места силы (пример размещения)
        for i in range(3):
            zone = arcade.Sprite(self.power_zone_texture, scale=POWER_ZONE_SCALE)
            zone.center_x = 300 + i * 400
            zone.center_y = 200 + random.randint(-50, 50)
            self.power_zone_list.append(zone)
            self.object_list.append(zone)

        # Повреждённые книги (для восстановления в лунный четверг)
        if self.is_moon_thursday:
            for i in range(3):
                book = arcade.Sprite(self.damaged_book_texture, scale=BOOK_SCALE * 0.7)
                book.center_x = 400 + i * 300
                book.center_y = 150
                book.is_restored = False
                self.damaged_books.append(book)
                self.object_list.append(book)

        self.physics_engine = arcade.PhysicsEngineSimple(self.player, self.collision_list)

    def update_time_system(self, delta_time):
        """Система времени суток и лунного цикла"""
        self.game_time += delta_time
        
        # Смена дня/ночи
        day_progress = (self.game_time % DAY_DURATION) / DAY_DURATION
        self.is_night = day_progress > 0.5  # Ночь = вторая половина цикла
        
        # Проверка "лунного четверга" (каждый 7-й день в полночь)
        current_day = int(self.game_time / DAY_DURATION)
        if current_day != self.last_moon_check:
            self.last_moon_check = current_day
            # Четверг = 4-й день недели (0=понедельник)
            is_thursday = (current_day % 7) == 3
            is_midnight = 0.7 < day_progress < 0.8  # Примерно полночь
            
            if is_thursday and is_midnight:
                self.is_moon_thursday = True
                # Создаём повреждённые книги для восстановления
                self.spawn_damaged_books()
            else:
                self.is_moon_thursday = False

    def spawn_damaged_books(self):
        """Создаёт повреждённые книги для восстановления в лунный четверг"""
        self.damaged_books = arcade.SpriteList()
        for i in range(random.randint(2, 4)):
            book = arcade.Sprite(self.damaged_book_texture, scale=BOOK_SCALE * 0.7)
            book.center_x = 400 + i * 300
            book.center_y = 150
            book.is_restored = False
            self.damaged_books.append(book)
            self.object_list.append(book)

    def start_phasing(self):
        """Активация фазинга через стены"""
        if self.mana >= PHASING_COST and not self.is_phasing:
            self.is_phasing = True
            self.phasing_timer = PHASING_DURATION
            self.mana -= PHASING_COST
            if self.sound_phasing:
                arcade.play_sound(self.sound_phasing)
            # Временно убираем стены из физики
            self.physics_engine = arcade.PhysicsEngineSimple(self.player, arcade.SpriteList())

    def stop_phasing(self):
        """Завершение фазинга"""
        self.is_phasing = False
        # Возвращаем стены в физику
        self.physics_engine = arcade.PhysicsEngineSimple(self.player, self.collision_list)

    def handle_restore_book(self):
        """Восстановление повреждённой книги (только в лунный четверг)"""
        if not self.is_moon_thursday:
            return
            
        for book in self.damaged_books:
            if not book.is_restored:
                dist = math.hypot(self.player.center_x - book.center_x, 
                                self.player.center_y - book.center_y)
                if dist < INTERACTION_DISTANCE and self.mana >= 25:
                    book.is_restored = True
                    book.alpha = 128  # Полупрозрачность как индикатор восстановления
                    self.mana -= 25
                    self.score += 25
                    self.visitors_helped += 1
                    if self.sound_restore:
                        arcade.play_sound(self.sound_restore)
                    break

    def get_time_display(self):
        """Форматированное отображение времени"""
        total_seconds = int(self.game_time)
        days = total_seconds // int(DAY_DURATION)
        seconds_in_day = total_seconds % int(DAY_DURATION)
        hours = seconds_in_day // 5  # 12 часов в игровом дне
        
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        day_name = day_names[days % 7]
        
        period = "Ночь" if self.is_night else "День"
        moon = "🌕" if self.is_moon_thursday else ""
        
        return f"{day_name} {hours:02d}:00 | {period} {moon}"

    def on_draw(self):
        self.clear()
        
        # Фон в зависимости от времени суток
        if self.is_night:
            bg_color = (10, 10, 30) if not self.is_moon_thursday else (20, 10, 40)  # Фиолетовый в лунную ночь
        else:
            bg_color = (40, 40, 60)
        arcade.set_background_color(bg_color)
        
        self.world_camera.use()

        self.walls_behind_list.draw()
        self.wall_list.draw()
        self.object_list.draw()
        self.all_sprites.draw()
        self.floating_books.draw()
        self.damaged_books.draw()
        self.power_zone_list.draw()

        # Подсветка целевого шкафа
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

        # Визуализация фазинга
        if self.is_phasing:
            arcade.draw_circle_filled(
                self.player.center_x, self.player.center_y,
                40, (100, 100, 255, 80)
            )

        # UI
        self.window.default_camera.use()
        
        # Панель заданий
        panel_width = 400
        panel_height = 160 if self.is_moon_thursday else 120
        panel_x = 20
        panel_y = SCREEN_HEIGHT - panel_height - 20

        arcade.draw_lrbt_rectangle_filled(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            (20, 20, 40, 220)
        )
        arcade.draw_lrbt_rectangle_outline(
            panel_x, panel_x + panel_width,
            panel_y, panel_y + panel_height,
            arcade.color.GOLD, 2
        )
        arcade.draw_text(
            "АКТИВНЫЕ ЗАДАНИЯ",
            panel_x + 20, panel_y + panel_height - 30,
            arcade.color.GOLD, 18, bold=True
        )
        
        if self.quest_active:
            arcade.draw_text(
                "• Уронь книгу из шкафа (E)", 
                panel_x + 30, panel_y + panel_height - 70,
                arcade.color.WHITE, 14
            )
        
        if self.is_moon_thursday:
            arcade.draw_text(
                "🌕 ЛУННЫЙ ЧЕТВЕРГ! 🌕",
                panel_x + 20, panel_y + panel_height - 100,
                arcade.color.LIGHT_BLUE, 16, bold=True
            )
            arcade.draw_text(
                "• Восстанови книги (R)",
                panel_x + 30, panel_y + panel_height - 130,
                arcade.color.WHITE, 14
            )

        # Счётчик очков
        arcade.draw_text(
            f"Очки: {self.score} | Помог: {self.visitors_helped}",
            SCREEN_WIDTH - 20,
            SCREEN_HEIGHT - 40,
            arcade.color.GOLD,
            16,
            anchor_x="right"
        )

        # Шкала маны
        mana_bar_width = 200
        mana_bar_height = 20
        mana_bar_x = 20
        mana_bar_y = 60

        fill_width = (self.mana / self.max_mana) * mana_bar_width
        if fill_width > 0:
            arcade.draw_lrbt_rectangle_filled(
                mana_bar_x, mana_bar_x + fill_width,
                mana_bar_y, mana_bar_y + mana_bar_height,
                arcade.color.BLUE
            )
        arcade.draw_lrbt_rectangle_outline(
            mana_bar_x, mana_bar_x + mana_bar_width,
            mana_bar_y, mana_bar_y + mana_bar_height,
            arcade.color.WHITE, 2
        )
        arcade.draw_text(f"Мана: {int(self.mana)}/{int(self.max_mana)}", 
                        mana_bar_x + mana_bar_width + 10, mana_bar_y + 5, 
                        arcade.color.WHITE, 14)

        # Индикатор времени
        time_display = self.get_time_display()
        arcade.draw_text(
            time_display,
            SCREEN_WIDTH - 20, 20,
            arcade.color.GOLD if self.is_moon_thursday else (200, 200, 255),
            16,
            anchor_x="right"
        )

        # Подсказки управления
        hints = [
            "WASD - движение",
            "E - взаимодействие",
            "F - фазинг через стены",
            "R - восстановить книгу (в ночь)",
            "ESC - пауза"
        ]
        for i, hint in enumerate(hints):
            arcade.draw_text(hint, 20, SCREEN_HEIGHT - 80 - i * 20, 
                           arcade.color.GRAY, 12)

    def on_update(self, delta_time: float):
        self.update_time_system(delta_time)
        
        # Обновление фазинга
        if self.is_phasing:
            self.phasing_timer -= delta_time
            if self.phasing_timer <= 0:
                self.stop_phasing()
        
        # Регенерация маны (ускоренная в зонах силы)
        regen_mult = 1.0
        for zone in self.power_zone_list:
            dist = math.hypot(self.player.center_x - zone.center_x,
                            self.player.center_y - zone.center_y)
            if dist < 100:
                regen_mult = 3.0  # Ускоренная регенерация
                break
        self.mana = min(self.max_mana, self.mana + self.mana_regen_rate * regen_mult * delta_time)

        self.physics_engine.update()

        # Плавная камера
        cam_x, cam_y = self.world_camera.position
        target_x = self.player.center_x
        target_y = self.player.center_y
        new_x = arcade.math.lerp(cam_x, target_x, CAMERA_LERP)
        new_y = arcade.math.lerp(cam_y, target_y, CAMERA_LERP)

        half_w = self.world_camera.viewport_width / 2
        half_h = self.world_camera.viewport_height / 2
        new_x = max(half_w, min(self.map_width - half_w, new_x))
        new_y = max(half_h, min(self.map_height - half_h, new_y))
        self.world_camera.position = (new_x, new_y)

        # Спавн посетителя
        self.visitor_spawn_timer -= delta_time
        if self.visitor_spawn_timer <= 0 and self.visitor is None and not self.is_night:
            self.spawn_visitor()

        # Движение и логика посетителя
        if self.visitor:
            self.visitor.center_y = 118

            if self.visitor.state == "arriving":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.state = "waiting"
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "waiting":
                book_to_take = None
                for book in self.floating_books:
                    dist = math.hypot(
                        self.visitor.center_x - book.center_x,
                        self.visitor.center_y - book.center_y
                    )
                    if dist < INTERACTION_DISTANCE:
                        book_to_take = book
                        break

                if book_to_take:
                    book_to_take.remove_from_sprite_lists()
                    self.score += 10
                    self.visitors_helped += 1
                    if self.sound_book_drop:
                        arcade.play_sound(self.sound_book_drop)
                    self.visitor.state = "returning_to_table"
                    self.visitor.target_x = self.current_table.center_x
                else:
                    if self.quest_delay is not None:
                        self.quest_timer += delta_time
                        if self.quest_timer >= self.quest_delay:
                            self.start_quest()
                            self.quest_delay = None

            elif self.visitor.state == "returning_to_table":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.state = "reading"
                    self.visitor.read_end_time = time.time() + 15
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "reading":
                if time.time() >= self.visitor.read_end_time:
                    if random.random() < 0.5:
                        self.visitor.state = "leaving"
                        self.visitor.target_x = 50
                    else:
                        self.visitor.state = "waiting"
                        self.quest_delay = random.uniform(5.0, 10.0)
                        self.quest_timer = 0.0

            elif self.visitor.state == "leaving":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.remove_from_sprite_lists()
                    self.visitor = None
                    self.visitor_spawn_timer = random.uniform(10.0, 20.0)

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
        elif key == arcade.key.E:
            self.handle_interaction()
        elif key == arcade.key.F and not self.is_phasing:
            self.start_phasing()
        elif key == arcade.key.R:
            self.handle_restore_book()
        elif key == arcade.key.ESCAPE:
            pause = PauseView(self)
            self.window.show_view(pause)

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.S):
            self.player.change_y = 0
        if key in (arcade.key.A, arcade.key.D):
            self.player.change_x = 0

    def handle_interaction(self):
        if not self.quest_active or self.target_bookshelf is None:
            return

        dist_to_shelf = math.hypot(
            self.player.center_x - self.target_bookshelf.center_x,
            self.player.center_y - self.target_bookshelf.center_y
        )

        if dist_to_shelf < INTERACTION_DISTANCE and self.mana >= 10:
            book = arcade.Sprite(self.book_texture, scale=FLOATING_BOOK_SCALE)
            book.center_x = self.target_bookshelf.center_x
            book.center_y = 90
            self.floating_books.append(book)
            self.object_list.append(book)
            self.mana -= 10
            self.quest_active = False
            if self.sound_book_drop:
                arcade.play_sound(self.sound_book_drop)

    def spawn_visitor(self):
        if self.visitor is not None:
            return

        entrance_x = 100
        entrance_y = 118

        self.visitor = arcade.Sprite(self.visitor_texture, scale=VISITOR_SCALE)
        self.visitor.center_x = entrance_x
        self.visitor.center_y = entrance_y
        self.visitor.state = "arriving"
        self.current_table = random.choice(self.tables)
        self.visitor.target_x = self.current_table.center_x

        self.object_list.append(self.visitor)
        self.quest_delay = random.uniform(3.0, 8.0)
        self.quest_timer = 0.0

    def start_quest(self):
        if self.quest_active or self.visitor is None or self.visitor.state != "waiting":
            return
        self.quest_active = True
        self.target_bookshelf = random.choice(self.bookshelves)

    def save_game(self):
        """Сохранение прогресса в JSON"""
        save_data = {
            "score": self.score,
            "visitors_helped": self.visitors_helped,
            "game_time": self.game_time,
            "player_x": self.player.center_x,
            "player_y": self.player.center_y,
            "mana": self.mana
        }
        try:
            with open("savegame.json", "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
            print("Игра сохранена!")
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def load_game(self):
        """Загрузка прогресса из JSON"""
        try:
            if not os.path.exists("savegame.json"):
                print("Файл сохранения не найден!")
                return False
                
            with open("savegame.json", "r", encoding="utf-8") as f:
                save_data = json.load(f)
            
            self.score = save_data.get("score", 0)
            self.visitors_helped = save_data.get("visitors_helped", 0)
            self.game_time = save_data.get("game_time", 0.0)
            self.mana = save_data.get("mana", 100.0)
            
            # Перемещаем игрока
            self.player.center_x = save_data.get("player_x", self.player.center_x)
            self.player.center_y = save_data.get("player_y", self.player.center_y)
            
            print("Игра загружена!")
            return True
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return False


class MainMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.buttons = [
            Button("Новая игра", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 80),
            Button("Загрузить игру", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, color=arcade.color.DARK_BLUE),
            Button("Выход", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 80, color=arcade.color.DARK_RED)
        ]
        self.title_alpha = 255

    def on_draw(self):
        self.clear(arcade.color.DARK_BLUE)
        
        # Анимированный фон
        for i in range(20):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            size = random.randint(1, 3)
            arcade.draw_circle_filled(x, y, size, (100, 100, 150, 100))
        
        arcade.draw_text("FANTOM OF LIBRARY", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100,
                         arcade.color.WHITE, font_size=50, anchor_x="center",
                         start_x=SCREEN_WIDTH/2 - 250, width=500, align="center")
        arcade.draw_text("Защитник знаний в вечной тишине...", 
                        SCREEN_WIDTH / 2, SCREEN_HEIGHT - 140,
                        arcade.color.GRAY, font_size=20, anchor_x="center")
        
        for button in self.buttons:
            button.draw()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        for btn in self.buttons:
            if btn.is_clicked(x, y):
                if btn.text == "Новая игра":
                    game = GameView()
                    game.setup()
                    self.window.show_view(game)
                elif btn.text == "Загрузить игру":
                    game = GameView()
                    game.setup()
                    if game.load_game():
                        self.window.show_view(game)
                    else:
                        # Показать сообщение об ошибке
                        pass
                elif btn.text == "Выход":
                    arcade.exit()


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    main_menu = MainMenu()
    window.show_view(main_menu)
    arcade.run()


if __name__ == "__main__":
    main()
