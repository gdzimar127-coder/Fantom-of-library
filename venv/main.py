import arcade

# Константы
SPEED = 4
SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 700
CAMERA_LERP = 0.13
SCREEN_TITLE = "Fantom of library"

# Размеры кнопок
BUTTON_WIDTH = 300
BUTTON_HEIGHT = 80


class Button:
    """Простая кнопка без использования спрайтов"""
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
    def left(self):
        return self.center_x - self.width / 2

    @property
    def right(self):
        return self.center_x + self.width / 2

    @property
    def top(self):
        return self.center_y + self.height / 2

    @property
    def bottom(self):
        return self.center_y - self.height / 2

    def draw(self):
        rect = arcade.rect.XYWH(self.center_x, self.center_y, self.width, self.height)
        arcade.draw_rect_filled(rect, self.color)
        arcade.draw_text(
            self.text,
            self.center_x,
            self.center_y,
            self.text_color,
            self.font_size,
            anchor_x="center",
            anchor_y="center"
        )

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
        # Рисуем игру (она использует свою камеру)
        self.game_view.on_draw()

        # Переключаемся на экранную (UI) систему координат
        self.window.default_camera.use()

        # Полупрозрачный оверлей (затемнение)
        rect = arcade.rect.XYWH(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, SCREEN_WIDTH, SCREEN_HEIGHT)
        arcade.draw_rect_filled(rect, (0, 0, 0, 150))  # RGBA: чёрный с alpha=150

        # Рисуем кнопки
        for button in self.buttons:
            button.draw()

        # Заголовок
        arcade.draw_text("ПАУЗА", SCREEN_WIDTH / 2, SCREEN_HEIGHT - 100,
                         arcade.color.WHITE, font_size=48, anchor_x="center")

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        for btn in self.buttons:
            if btn.is_clicked(x, y):
                if btn.text == "Продолжить":
                    self.window.show_view(self.game_view)
                elif btn.text == "В главное меню":
                    from main import MainMenu
                    self.window.show_view(MainMenu())

    def on_key_press(self, key, modifiers):
        if key == arcade.key.ESCAPE:
            self.window.show_view(self.game_view)


class GameView(arcade.View):
    def __init__(self):
        super().__init__()
        self.cell_size = 64
        self.all_sprites = arcade.SpriteList()
        map_name = "library.tmx"
        self.tile_map = arcade.load_tilemap(map_name, scaling=1)

        self.object_list = self.tile_map.sprite_lists["objects"]
        self.walls_behind_list = self.tile_map.sprite_lists["walls behind"]
        self.wall_list = self.tile_map.sprite_lists["walls"]
        self.collision_list = self.tile_map.sprite_lists["collision"]

        # Загружаем ОБЕ текстуры
        self.player_texture_right = arcade.load_texture('ghost.png')   # вправо
        self.player_texture_left = arcade.load_texture('ghost_l.png')  # влево

        self.world_camera = arcade.camera.Camera2D()

        self.map_width = self.tile_map.width * self.tile_map.tile_width
        self.map_height = self.tile_map.height * self.tile_map.tile_height

    def setup(self):
        # Создаём спрайт с текстурой "вправо" по умолчанию
        self.player = arcade.Sprite(self.player_texture_right, scale=0.3)
        x = 7 * self.cell_size + self.cell_size // 2
        y = 5 * self.cell_size + self.cell_size // 2
        self.player.center_x = x
        self.player.center_y = y
        self.all_sprites.append(self.player)

        self.physics_engine = arcade.PhysicsEngineSimple(self.player, self.collision_list)

    def on_draw(self):
        self.clear()
        self.world_camera.use()
        self.walls_behind_list.draw()
        self.object_list.draw()
        self.wall_list.draw()
        self.all_sprites.draw()

    def on_update(self, delta_time: float):
        self.physics_engine.update()

        target_x = self.player.center_x
        target_y = self.player.center_y

        cam_x, cam_y = self.world_camera.position
        new_x = arcade.math.lerp(cam_x, target_x, CAMERA_LERP)
        new_y = arcade.math.lerp(cam_y, target_y, CAMERA_LERP)

        half_w = self.world_camera.viewport_width / 2
        half_h = self.world_camera.viewport_height / 2

        new_x = max(half_w, min(self.map_width - half_w, new_x))
        new_y = max(half_h, min(self.map_height - half_h, new_y))

        self.world_camera.position = (new_x, new_y)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.W:
            self.player.change_y = SPEED
        elif key == arcade.key.S:
            self.player.change_y = -SPEED
        elif key == arcade.key.A:
            self.player.change_x = -SPEED
            self.player.texture = self.player_texture_left   # ← влево
        elif key == arcade.key.D:
            self.player.change_x = SPEED
            self.player.texture = self.player_texture_right  # ← вправо
        elif key == arcade.key.ESCAPE:
            pause = PauseView(self)
            self.window.show_view(pause)

    def on_key_release(self, key, modifiers):
        if key in (arcade.key.W, arcade.key.S):
            self.player.change_y = 0
        if key in (arcade.key.A, arcade.key.D):
            self.player.change_x = 0
            # НЕ меняем текстуру — остаёмся в последнем направлении


class MainMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.buttons = [
            Button("Играть", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 50),
            Button("Выйти", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50, color=arcade.color.DARK_RED)
        ]

    def on_draw(self):
        self.clear(arcade.color.DARK_BLUE)
        # В главном меню мы уже в default-камере — ничего переключать не нужно
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