import arcade
import random
import math

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

        self.has_book = False
        self.quest_active = False
        self.target_bookshelf = None
        self.visitor = None
        self.current_table = None

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

        if len(self.tables) == 0:
            return
        self.current_table = random.choice(self.tables)
        self.visitor.target_x = self.current_table.center_x
        self.visitor.target_y = entrance_y
        self.visitor.arrived = False

        self.all_sprites.append(self.visitor)
        self.quest_delay = random.uniform(3.0, 8.0)
        self.quest_timer = 0.0

    def start_quest(self):
        if self.quest_active or self.visitor is None:
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

        # Подсветка шкафа
        if self.quest_active and self.target_bookshelf and not self.has_book:
            arcade.draw_circle_filled(
                self.target_bookshelf.center_x,
                self.target_bookshelf.center_y + 30,
                20, arcade.color.YELLOW
            )

        # Инвентарь — книга в правом нижнем углу
        if self.has_book:
            self.window.default_camera.use()
            book_x = SCREEN_WIDTH - 60
            book_y = 60
            rect = arcade.rect.XYWH(book_x, book_y, 50, 60)
            arcade.draw_texture_rect(self.book_texture, rect)  # ← ПРАВИЛЬНЫЙ ПОРЯДОК!

        # Задание
        self.window.default_camera.use()
        if self.quest_active and not self.has_book:
            arcade.draw_text(
                "Посетителю нужна книга! Подойдите к подсвеченному шкафу и нажмите E",
                20, SCREEN_HEIGHT - 40,
                arcade.color.WHITE, 16, bold=True
            )
        elif self.has_book:
            arcade.draw_text(
                "Отнесите книгу посетителю и нажмите E",
                20, SCREEN_HEIGHT - 40,
                arcade.color.GREEN, 16, bold=True
            )

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

        self.visitor_spawn_timer -= delta_time
        if self.visitor_spawn_timer <= 0 and self.visitor is None:
            self.spawn_visitor()

        # Движение посетителя — ТОЛЬКО ПО ГОРИЗОНТАЛИ
        if self.visitor and not self.visitor.arrived:
            dx = self.visitor.target_x - self.visitor.center_x
            dist = abs(dx)
            if dist < 5:
                self.visitor.arrived = True
            else:
                visitor_speed = 100
                self.visitor.center_x += math.copysign(visitor_speed * delta_time, dx)

        if self.visitor and self.visitor.arrived and self.quest_delay is not None:
            self.quest_timer += delta_time
            if self.quest_timer >= self.quest_delay:
                self.start_quest()
                self.quest_delay = None

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
        if not self.quest_active:
            return

        if self.quest_active and not self.has_book and self.target_bookshelf:
            dist = math.hypot(
                self.player.center_x - self.target_bookshelf.center_x,
                self.player.center_y - self.target_bookshelf.center_y
            )
            if dist < INTERACTION_DISTANCE:
                self.has_book = True
                return

        if self.has_book and self.visitor:
            dist = math.hypot(
                self.player.center_x - self.visitor.center_x,
                self.player.center_y - self.visitor.center_y
            )
            if dist < INTERACTION_DISTANCE:
                self.has_book = False
                self.quest_active = False
                self.target_bookshelf = None
                self.visitor_spawn_timer = random.uniform(10.0, 20.0)

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