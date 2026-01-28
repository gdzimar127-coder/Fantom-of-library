import arcade
import random
import math
import time

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

INTERACTION_DISTANCE = 80


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
            Button("Продолжить", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 50),
            Button("В главное меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50, color=arcade.color.DARK_RED)
        ]

    def on_draw(self):
        self.game_view.on_draw()
        self.window.default_camera.use()
        rect = arcade.rect.XYWH(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, SCREEN_WIDTH, SCREEN_HEIGHT)
        arcade.draw_rect_filled(rect, (0, 0, 0, 150))
        for button in self.buttons:
            button.draw()
        arcade.draw_text("ПАУЗА", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100,
                         arcade.color.WHITE, font_size=48, anchor_x="center")

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        for btn in self.buttons:
            if btn.is_clicked(x, y):
                if btn.text == "Продолжить":
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

        self.all_sprites = arcade.SpriteList()
        self.tables = arcade.SpriteList()
        self.bookshelves = arcade.SpriteList()

        self.player_texture_right = arcade.load_texture('ghost.png')
        self.player_texture_left = arcade.load_texture('ghost_l.png')
        self.visitor_texture = arcade.load_texture('visitor_1.png')
        self.book_texture = arcade.load_texture('book.png')
        self.bookshelf_texture = arcade.load_texture('bookshelf.png')
        self.table_texture = arcade.load_texture('table.png')

        self.world_camera = arcade.camera.Camera2D()
        self.map_width = self.tile_map.width * self.tile_map.tile_width
        self.map_height = self.tile_map.height * self.tile_map.tile_height

        # Мана
        self.mana = 100.0
        self.max_mana = 100.0
        self.mana_regen_rate = 1.0

        # Квест и посетители
        self.quest_active = False
        self.target_bookshelf = None
        self.visitor = None
        self.current_table = None
        self.score = 0

        self.floating_books = arcade.SpriteList()

        self.pulse_time = 0.0
        self.visitor_spawn_timer = random.uniform(5.0, 15.0)
        self.quest_timer = None
        self.quest_delay = None

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

        self.physics_engine = arcade.PhysicsEngineSimple(self.player, self.collision_list)

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

    def on_draw(self):
        self.clear()
        self.world_camera.use()

        self.walls_behind_list.draw()
        self.wall_list.draw()
        self.object_list.draw()
        self.all_sprites.draw()
        self.floating_books.draw()

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

        # UI: задания
        self.window.default_camera.use()
        if self.quest_active:
            panel_width = 400
            panel_height = 120
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
            arcade.draw_text(
                "• Урони книгу из шкафа (E)",  # ← ИЗМЕНЕНО
                panel_x + 30, panel_y + panel_height - 70,
                arcade.color.WHITE, 14
            )

        # Счётчик очков
        arcade.draw_text(
            f"Очки: {self.score}",
            SCREEN_WIDTH - 20,
            SCREEN_HEIGHT - 40,
            arcade.color.GOLD,
            16,
            anchor_x="right"
        )

        # Шкала маны — ПРОЗРАЧНЫЙ ФОН
        mana_bar_width = 200
        mana_bar_height = 20
        mana_bar_x = 20
        mana_bar_y = 20

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
        arcade.draw_text("Мана", mana_bar_x + mana_bar_width + 10, mana_bar_y + 5, arcade.color.WHITE, 14)

    def on_update(self, delta_time: float):
        self.physics_engine.update()

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

        # Восстановление маны
        self.mana = min(self.max_mana, self.mana + self.mana_regen_rate * delta_time)

        # Спавн посетителя
        self.visitor_spawn_timer -= delta_time
        if self.visitor_spawn_timer <= 0 and self.visitor is None:
            self.spawn_visitor()

        # Движение и логика посетителя
        if self.visitor:
            # Фиксируем Y на уровне пола
            self.visitor.center_y = 118

            if self.visitor.state == "arriving":
                dx = self.visitor.target_x - self.visitor.center_x
                if abs(dx) < 5:
                    self.visitor.state = "waiting"
                else:
                    self.visitor.center_x += math.copysign(100 * delta_time, dx)

            elif self.visitor.state == "waiting":
                # Проверяем: можно ли взять книгу прямо сейчас?
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
                    self.visitor.state = "returning_to_table"
                    self.visitor.target_x = self.current_table.center_x
                else:
                    # Ищем ближайшую книгу и идём к ней
                    closest_book = None
                    min_dx = float('inf')
                    for book in self.floating_books:
                        dx = abs(self.visitor.center_x - book.center_x)
                        if dx < min_dx:
                            min_dx = dx
                            closest_book = book

                    if closest_book and min_dx > 10:
                        # Двигаемся к книге
                        direction = 1 if closest_book.center_x > self.visitor.center_x else -1
                        self.visitor.center_x += direction * 100 * delta_time
                    else:
                        # Нет книг — ждём квест
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
            book.center_y = 90  # ← КНИГА НА ВЫСОТЕ 90
            self.floating_books.append(book)
            self.object_list.append(book)
            self.mana -= 10
            self.quest_active = False

    def on_close(self):
        super().on_close()


class MainMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.buttons = [
            Button("Играть", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 50),
            Button("Выйти", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50, color=arcade.color.DARK_RED)
        ]

    def on_draw(self):
        self.clear(arcade.color.DARK_BLUE)
        arcade.draw_text("FANTOM OF LIBRARY", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100,
                         arcade.color.WHITE, font_size=50, anchor_x="center")
        for button in self.buttons:
            button.draw()

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        for btn in self.buttons:
            if btn.is_clicked(x, y):
                if btn.text == "Играть":
                    game = GameView()
                    game.setup()
                    self.window.show_view(game)
                elif btn.text == "Выйти":
                    arcade.exit()


def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    main_menu = MainMenu()
    window.show_view(main_menu)
    arcade.run()


if __name__ == "__main__":
    main()