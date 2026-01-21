import arcade

SPEED = 4
SCREEN_WIDTH = 1500
SCREEN_HEIGHT = 700
CAMERA_LERP = 0.13
SCREEN_TITLE = "Fantom of library"


class GridGame(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        self.cell_size = 64
        self.all_sprites = arcade.SpriteList()
        map_name = "library.tmx"
        tile_map = arcade.load_tilemap(map_name, scaling=1)
        self.object_list = tile_map.sprite_lists["objects"]
        self.walls_behind_list = tile_map.sprite_lists["walls behind"]
        self.wall_list = tile_map.sprite_lists["walls"]
        # САМЫЙ ГЛАВНЫЙ СЛОЙ: "Collision" — наши стены и платформы для физики!
        self.collision_list = tile_map.sprite_lists["collision"]
        # Загружаем текстуры из встроенных ресурсов
        self.player_texture = arcade.load_texture('ghost.png')
        self.world_camera = arcade.camera.Camera2D()  # Камера для игрового мира
        self.gui_camera = arcade.camera.Camera2D()

    def setup(self):
        self.player = arcade.Sprite(self.player_texture, scale=0.3)
        x = 7 * self.cell_size + self.cell_size // 2
        y = 5 * self.cell_size + self.cell_size // 2
        self.player.center_x = x
        self.player.center_y = y
        self.all_sprites.append(self.player)

        self.physics_engine = arcade.PhysicsEngineSimple(
            self.player, self.collision_list
        )

    def on_draw(self):
        self.clear()
        self.world_camera.use()  # Активируем камеру мира
        # Рисуем игровые объекты...
        self.walls_behind_list.draw()
        self.object_list.draw()
        self.wall_list.draw()
        self.all_sprites.draw()
        self.gui_camera.use()

    def on_update(self, delta_time: float):
        self.physics_engine.update()
        position = (
            self.player.center_x,
            self.player.center_y
        )
        self.world_camera.position = arcade.math.lerp_2d(  # Изменяем позицию камеры
            self.world_camera.position,
            position,
            CAMERA_LERP,  # Плавность следования камеры
        )

    def on_key_press(self, key, modifiers):
         if key == arcade.key.W:
             self.player.change_y = SPEED
         if key == arcade.key.S:
             self.player.change_y = -SPEED
         if key == arcade.key.A:
             self.player.change_x = -SPEED
         if key == arcade.key.D:
             self.player.change_x = SPEED

    def on_key_release(self, key, modifiers):
        if key in [arcade.key.W, arcade.key.S]:
            self.player.change_y = 0
        if key in [arcade.key.A, arcade.key.D]:
            self.player.change_x = 0


def setup_game(width=960, height=640, title="Fantom of library"):
    game = GridGame(width, height, title)
    game.setup()
    return game


def main():
    setup_game(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    arcade.run()


if __name__ == "__main__":
    main()