import pygame
import sys

# Инициализация Pygame
pygame.init()

# Константы
WIDTH, HEIGHT = 800, 600
FPS = 60
PLAYER_SPEED = 5

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 50, 50)
GREEN = (50, 255, 50)
BLUE = (50, 100, 255)
GRAY = (200, 200, 200)
MENU_BG = (240, 240, 240)
GAME_BG = (245, 245, 220)
DARK_OVERLAY = (0, 0, 0, 180)

# Создание окна
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Простая игра с паузой")
clock = pygame.time.Clock()

# Шрифты
font_large = pygame.font.SysFont('arial', 48, bold=True)
font_medium = pygame.font.SysFont('arial', 36)
font_small = pygame.font.SysFont('arial', 24)
font_button = pygame.font.SysFont('arial', 28)  # Новый шрифт для кнопок меню паузы


class Button:
    """Класс для создания кнопок"""

    def __init__(self, x, y, width, height, text, color, hover_color, text_color=BLACK, font=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color

        # Используем переданный шрифт или шрифт по умолчанию
        if font is None:
            self.font = font_medium
        else:
            self.font = font

        self.current_color = color
        self.text_surf = self.font.render(text, True, text_color)

        # Масштабируем текст если он не помещается
        text_width = self.text_surf.get_width()
        if text_width > width - 20:  # Оставляем отступы по 10px с каждой стороны
            scale_factor = (width - 20) / text_width
            new_size = max(16, int(self.font.get_height() * scale_factor))  # Минимальный размер 16
            # Создаем временный шрифт для масштабирования
            temp_font = pygame.font.SysFont('arial', new_size)
            self.text_surf = temp_font.render(text, True, text_color)

        self.text_rect = self.text_surf.get_rect(center=self.rect.center)

    def draw(self, surface, offset_x=0, offset_y=0):
        # Рисуем кнопку со смещением если нужно
        draw_rect = self.rect.copy()
        if offset_x != 0 or offset_y != 0:
            draw_rect.x += offset_x
            draw_rect.y += offset_y

        text_rect = self.text_rect.copy()
        if offset_x != 0 or offset_y != 0:
            text_rect.x += offset_x
            text_rect.y += offset_y

        pygame.draw.rect(surface, self.current_color, draw_rect, border_radius=10)
        pygame.draw.rect(surface, self.text_color, draw_rect, 2, border_radius=10)
        surface.blit(self.text_surf, text_rect)

        return draw_rect

    def check_hover(self, pos, offset_x=0, offset_y=0):
        # Проверяем наведение с учетом смещения
        check_rect = self.rect.copy()
        if offset_x != 0 or offset_y != 0:
            check_rect.x += offset_x
            check_rect.y += offset_y

        if check_rect.collidepoint(pos):
            self.current_color = self.hover_color
            return True
        else:
            self.current_color = self.color
            return False

    def is_clicked(self, pos, event, offset_x=0, offset_y=0):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Проверяем клик с учетом смещения
            check_rect = self.rect.copy()
            if offset_x != 0 or offset_y != 0:
                check_rect.x += offset_x
                check_rect.y += offset_y

            if check_rect.collidepoint(pos):
                return True
        return False


class Player:
    """Класс игрока (черный квадрат)"""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 50
        self.height = 50
        self.speed = PLAYER_SPEED
        self.color = BLACK

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

        # Ограничиваем движение в пределах экрана
        self.x = max(0, min(self.x, WIDTH - self.width))
        self.y = max(0, min(self.y, HEIGHT - self.height))

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, WHITE, self.rect, 2)


def create_pause_menu():
    """Создает меню паузы (только 2 кнопки)"""
    pause_menu_width = 400
    pause_menu_height = 300
    pause_menu_x = (WIDTH - pause_menu_width) // 2
    pause_menu_y = (HEIGHT - pause_menu_height) // 2

    # Создаем поверхность для меню паузы с прозрачностью
    pause_surface = pygame.Surface((pause_menu_width, pause_menu_height), pygame.SRCALPHA)

    # Фон меню паузы (слегка прозрачный белый)
    pygame.draw.rect(pause_surface, (255, 255, 255, 230), pause_surface.get_rect(), border_radius=15)
    pygame.draw.rect(pause_surface, BLACK, pause_surface.get_rect(), 3, border_radius=15)

    # Создаем кнопки для меню паузы
    button_width = 250
    button_height = 60
    button_x = (pause_menu_width - button_width) // 2

    # Кнопка "Вернуться в игру" с подогнанным шрифтом
    resume_button = Button(
        button_x, 90,
        button_width, button_height,
        "ВЕРНУТЬСЯ В ИГРУ",
        GREEN, (40, 180, 40), WHITE, font_button
    )

    # Кнопка "В главное меню" с подогнанным шрифтом
    menu_button = Button(
        button_x, 170,
        button_width, button_height,
        "В ГЛАВНОЕ МЕНЮ",
        BLUE, (40, 90, 180), WHITE, font_button
    )

    return {
        'surface': pause_surface,
        'rect': pygame.Rect(pause_menu_x, pause_menu_y, pause_menu_width, pause_menu_height),
        'resume_button': resume_button,
        'menu_button': menu_button
    }


def draw_pause_menu(pause_menu, screen, player):
    """Рисует меню паузы поверх игры"""
    # Создаем полупрозрачную поверхность для затемнения фона
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill(DARK_OVERLAY)
    screen.blit(overlay, (0, 0))

    # Рисуем затемненную игру на фоне
    temp_surface = pygame.Surface((WIDTH, HEIGHT))
    temp_surface.fill(GAME_BG)
    player.draw(temp_surface)
    temp_surface.set_alpha(100)
    screen.blit(temp_surface, (0, 0))

    # Рисуем панель меню паузы
    screen.blit(pause_menu['surface'], pause_menu['rect'].topleft)

    # Рисуем заголовок
    title = font_large.render("ПАУЗА", True, BLACK)
    title_rect = title.get_rect(center=(WIDTH // 2, pause_menu['rect'].y + 50))
    screen.blit(title, title_rect)

    # Рисуем кнопки с правильным смещением
    pause_menu['resume_button'].draw(screen, pause_menu['rect'].x, pause_menu['rect'].y)
    pause_menu['menu_button'].draw(screen, pause_menu['rect'].x, pause_menu['rect'].y)

    return pause_menu


def main_menu():
    """Главное меню с белым фоном"""
    play_button = Button(WIDTH // 2 - 100, HEIGHT // 2 - 50, 200, 60, "ИГРАТЬ", GREEN, (40, 180, 40))
    quit_button = Button(WIDTH // 2 - 100, HEIGHT // 2 + 50, 200, 60, "ВЫЙТИ", RED, (180, 40, 40))

    menu_running = True
    while menu_running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if play_button.is_clicked(mouse_pos, event):
                return "play"

            if quit_button.is_clicked(mouse_pos, event):
                pygame.quit()
                sys.exit()

        play_button.check_hover(mouse_pos)
        quit_button.check_hover(mouse_pos)

        screen.fill(WHITE)

        title = font_large.render("ГЛАВНОЕ МЕНЮ", True, BLACK)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))

        subtitle = font_small.render("Простая игра с управлением WASD", True, (50, 50, 50))
        screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 170))

        play_button.draw(screen)
        quit_button.draw(screen)

        instruction = font_small.render("Нажмите 'ИГРАТЬ' чтобы начать", True, (100, 100, 100))
        screen.blit(instruction, (WIDTH // 2 - instruction.get_width() // 2, HEIGHT - 80))

        pause_info = font_small.render("В игре: ESC - меню паузы", True, (100, 100, 100))
        screen.blit(pause_info, (WIDTH // 2 - pause_info.get_width() // 2, HEIGHT - 120))

        pygame.display.flip()
        clock.tick(FPS)


def game_loop():
    """Игровой цикл с меню паузы"""
    player = Player(WIDTH // 2 - 25, HEIGHT // 2 - 25)
    paused = False
    pause_menu = create_pause_menu()

    game_running = True
    while game_running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    paused = not paused

            if paused:
                # Проверяем клики по кнопкам меню паузы с учетом смещения
                offset_x = pause_menu['rect'].x
                offset_y = pause_menu['rect'].y

                if pause_menu['resume_button'].is_clicked(mouse_pos, event, offset_x, offset_y):
                    paused = False

                if pause_menu['menu_button'].is_clicked(mouse_pos, event, offset_x, offset_y):
                    return "menu"

        if not paused:
            # Управление игроком
            keys = pygame.key.get_pressed()
            dx, dy = 0, 0

            if keys[pygame.K_w] or keys[pygame.K_UP]:
                dy -= player.speed
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                dy += player.speed
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                dx -= player.speed
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                dx += player.speed

            player.move(dx, dy)

        # Отрисовка
        screen.fill(GAME_BG)
        player.draw(screen)

        if not paused:
            # Только информация об управлении (без координат)
            controls_text = font_small.render("WASD: движение | ESC: пауза", True, BLACK)
            screen.blit(controls_text, (10, 10))
            # УБРАН показ координат игрока
        else:
            # Обновляем hover состояние для кнопок в меню паузы
            offset_x = pause_menu['rect'].x
            offset_y = pause_menu['rect'].y
            pause_menu['resume_button'].check_hover(mouse_pos, offset_x, offset_y)
            pause_menu['menu_button'].check_hover(mouse_pos, offset_x, offset_y)

            # Рисуем меню паузы
            draw_pause_menu(pause_menu, screen, player)

        pygame.display.flip()
        clock.tick(FPS)


def main():
    """Основная функция игры"""
    current_screen = "menu"

    while True:
        if current_screen == "menu":
            action = main_menu()
            if action == "play":
                current_screen = "game"

        elif current_screen == "game":
            action = game_loop()
            if action == "menu":
                current_screen = "menu"


if __name__ == "__main__":
    main()