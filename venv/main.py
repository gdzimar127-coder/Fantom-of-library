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
        self.tile_map = arcade.load_tilemap(map_name, scaling=1)  # Сохраняем tile_map!

        self.object_list = self.tile_map.sprite_lists["objects"]
        self.walls_behind_list = self.tile_map.sprite_lists["walls behind"]
        self.wall_list = self.tile_map.sprite_lists["walls"]
        self.collision_list = self.tile_map.sprite_lists["collision"]

        self.player_texture = arcade.load_texture('ghost.png')
        self.world_camera = arcade.camera.Camera2D()
        self.gui_camera = arcade.camera.Camera2D()

        # Границы карты в пикселях
        self.map_width = self.tile_map.width * self.tile_map.tile_width
        self.map_height = self.tile_map.height * self.tile_map.tile_height

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
        self.world_camera.use()
        self.walls_behind_list.draw()
        self.object_list.draw()
        self.wall_list.draw()
        self.all_sprites.draw()
        self.gui_camera.use()

    def on_update(self, delta_time: float):
        self.physics_engine.update()

        # Желаемая позиция камеры — за игроком
        target_x = self.player.center_x
        target_y = self.player.center_y

        # Плавное перемещение
        cam_x, cam_y = self.world_camera.position
        new_x = arcade.math.lerp(cam_x, target_x, CAMERA_LERP)
        new_y = arcade.math.lerp(cam_y, target_y, CAMERA_LERP)

        # Ограничение по краям карты
        half_viewport_width = self.world_camera.viewport_width / 2
        half_viewport_height = self.world_camera.viewport_height / 2

        # Минимум: чтобы не уйти левее/ниже начала карты
        new_x = max(half_viewport_width, new_x)
        new_y = max(half_viewport_height, new_y)

        # Максимум: чтобы не уйти правее/выше конца карты
        new_x = min(self.map_width - half_viewport_width, new_x)
        new_y = min(self.map_height - half_viewport_height, new_y)

        self.world_camera.position = (new_x, new_y)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.W:
            self.player.change_y = SPEED
        elif key == arcade.key.S:
            self.player.change_y = -SPEED
        elif key == arcade.key.A:
            self.player.change_x = -SPEED
        elif key == arcade.key.D:
            self.player.change_x = SPEED

    def on_key_release(self, key, modifiers):
        if key in [arcade.key.W, arcade.key.S]:
            self.player.change_y = 0
        if key in [arcade.key.A, arcade.key.D]:
            self.player.change_x = 0


def main():
    game = GridGame(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    game.setup()
    arcade.run()


if __name__ == "__main__":
    main()