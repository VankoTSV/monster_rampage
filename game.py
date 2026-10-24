"""
MONSTER RAMPAGE - top-down arena shooter (pygame-ce)

Управление:
    WASD / стрелки  - движение
    Мишка           - прицелване
    Ляв бутон / SPACE - стрелба
    ESC             - пауза

Старт:  pip install -r requirements.txt   и после   python game.py
"""
import json
import math
import os
import random
import sys

import pygame
from pygame import Vector2

# ----------------------------------------------------------------------------
# Константи
# ----------------------------------------------------------------------------
VW, VH = 1280, 720                      # виртуална резолюция (скалира се към прозореца)
HUD_H = 96
ARENA = pygame.Rect(0, HUD_H, VW, VH - HUD_H)
FPS = 60
MAX_HP = 5
BORDER = 6

APP_FOLDER = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
              else os.path.dirname(os.path.abspath(__file__)))
SAVE_FILE = os.path.join(APP_FOLDER, "savegame.json")
DISPLAY_MODES = ["Fullscreen", "Windowed Fullscreen", "Windowed"]

# Фонът е до този файл
BG_FOLDER = ""
BG_FILE = "castle.jpg"
SOUND_FOLDER = "sound effects"
BG_ABSOLUTE = os.path.join(
    getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
    BG_FOLDER,
    BG_FILE
)
BG_DARKEN = 110          # 0 = без затъмняване, 255 = изцяло черно

MENU_STATES = {"menu", "settings", "paused", "gameover"}

WHITE = (240, 240, 240)
GRAY = (150, 155, 165)
YELLOW = (255, 214, 64)
RED = (235, 70, 70)


# ----------------------------------------------------------------------------
# Запис на рекорд и настройки
# ----------------------------------------------------------------------------
def load_save():
    data = {"record_score": 0, "record_coins": 0, "record_level": 0,
            "display_mode": "Windowed", "volume": 0.8}
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            data.update(loaded)
    except (OSError, ValueError):
        pass
    if data["display_mode"] not in DISPLAY_MODES:
        data["display_mode"] = "Windowed"
    try:
        volume = float(data["volume"])
        if not math.isfinite(volume):
            raise ValueError
    except (TypeError, ValueError):
        volume = 0.8
    data["volume"] = round(max(0.0, min(1.0, volume)), 2)
    return data


def write_save(data):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ----------------------------------------------------------------------------
# Геометрия
# ----------------------------------------------------------------------------
def circle_hits_rect(pos, r, rect):
    cx = max(rect.left, min(pos.x, rect.right))
    cy = max(rect.top, min(pos.y, rect.bottom))
    dx, dy = pos.x - cx, pos.y - cy
    return dx * dx + dy * dy < r * r


def push_out(pos, r, rect):
    """Избутва кръг (pos, r) извън правоъгълник. Връща True при колизия."""
    cx = max(rect.left, min(pos.x, rect.right))
    cy = max(rect.top, min(pos.y, rect.bottom))
    dx, dy = pos.x - cx, pos.y - cy
    d2 = dx * dx + dy * dy
    if d2 >= r * r:
        return False
    if d2 > 1e-6:
        d = math.sqrt(d2)
        pos.x += dx / d * (r - d)
        pos.y += dy / d * (r - d)
    else:
        left, right = pos.x - rect.left, rect.right - pos.x
        top, bottom = pos.y - rect.top, rect.bottom - pos.y
        m = min(left, right, top, bottom)
        if m == left:
            pos.x = rect.left - r
        elif m == right:
            pos.x = rect.right + r
        elif m == top:
            pos.y = rect.top - r
        else:
            pos.y = rect.bottom + r
    return True


def clamp_to_arena(pos, r):
    pos.x = max(ARENA.left + BORDER + r, min(ARENA.right - BORDER - r, pos.x))
    pos.y = max(ARENA.top + BORDER + r, min(ARENA.bottom - BORDER - r, pos.y))


# ----------------------------------------------------------------------------
# Обекти в играта
# ----------------------------------------------------------------------------
class Obstacle:
    def __init__(self, rect, moving=False, axis=0, amp=0, speed=0.0, phase=0.0):
        self.rect = rect.copy()
        self.base = Vector2(rect.topleft)
        self.moving = moving
        self.axis = axis
        self.amp = amp
        self.speed = speed
        self.phase = phase
        self.t = 0.0

    def update(self, dt):
        if not self.moving:
            return
        self.t += dt
        off = math.sin(self.t * self.speed + self.phase) * self.amp
        if self.axis == 0:
            self.rect.x = int(self.base.x + off)
        else:
            self.rect.y = int(self.base.y + off)


class Hazard:
    """Опасна зона - не спира куршуми, но нанася щети на играча."""
    def __init__(self, rect):
        self.rect = rect.copy()


class Bullet:
    def __init__(self, pos, vel, owner, radius=4):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.owner = owner
        self.r = radius
        self.life = 3.0
        self.dead = False

    def update(self, dt, obstacles):
        self.pos += self.vel * dt
        self.life -= dt
        if self.life <= 0 or not ARENA.collidepoint(self.pos):
            self.dead = True
            return
        for ob in obstacles:
            if circle_hits_rect(self.pos, self.r, ob.rect):
                self.dead = True
                return


class Coin:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.age = 0.0
        self.life = 15.0
        self.phase = random.uniform(0, 6.28)


class Player:
    RADIUS = 14

    def __init__(self):
        self.pos = Vector2(ARENA.centerx, ARENA.bottom - 90)
        self.hp = MAX_HP
        self.cd = 0.0
        self.invuln = 0.0
        self.angle = -math.pi / 2


class Enemy:
    RADIUS = 17

    def __init__(self, pos, level):
        self.pos = Vector2(pos)
        self.r = Enemy.RADIUS
        self.max_hp = min(2 + level // 3, 6)
        self.hp = self.max_hp
        self.speed = min(70 + 6 * level, 150) * random.uniform(0.85, 1.15)
        self.interval = max(0.6, 2.4 - 0.2 * (level - 1))
        self.shoot_t = random.uniform(0.8, self.interval + 0.8)
        self.target = Vector2(pos)
        self.retarget = 0.0
        self.flash = 0.0
        self.phase = random.uniform(0, 6.28)


class Particle:
    def __init__(self, pos, color):
        ang = random.uniform(0, 6.28)
        sp = random.uniform(40, 220)
        self.pos = Vector2(pos)
        self.vel = Vector2(math.cos(ang), math.sin(ang)) * sp
        self.life = random.uniform(0.25, 0.6)
        self.max_life = self.life
        self.color = color


# ----------------------------------------------------------------------------
# Генериране на ниво
# ----------------------------------------------------------------------------
def gen_level(level, avoid_pos):
    """Връща (obstacles, hazards). С нивото препятствията стават по-сложни."""
    obstacles, hazards, occupied = [], [], []
    area = ARENA.inflate(-80, -80)

    def try_place(w, h, pad=(0, 0), margin=46, tries=80):
        px, py = pad
        for _ in range(tries):
            if area.width - w - 2 * px <= 0 or area.height - h - 2 * py <= 0:
                return None
            x = random.randint(area.left + px, area.right - w - px)
            y = random.randint(area.top + py, area.bottom - h - py)
            r = pygame.Rect(x, y, w, h)
            bound = r.inflate(2 * px, 2 * py)
            if circle_hits_rect(avoid_pos, 130, bound):
                continue
            if any(bound.inflate(margin * 2, margin * 2).colliderect(o) for o in occupied):
                continue
            occupied.append(bound)
            return r
        return None

    p_complex = min(0.15 * (level - 1), 0.65)
    for _ in range(min(3 + level, 11)):
        roll = random.random()
        if roll < p_complex * 0.5:                       # L-образна стена
            w, h, t = random.randint(110, 200), random.randint(110, 190), 26
            r = try_place(w, h)
            if r:
                top, left = random.random() < 0.5, random.random() < 0.5
                hbar = pygame.Rect(r.x, r.y if top else r.bottom - t, w, t)
                vbar = pygame.Rect(r.x if left else r.right - t, r.y, t, h)
                obstacles += [Obstacle(hbar), Obstacle(vbar)]
        elif roll < p_complex:                           # дълга тънка стена
            length, t = random.randint(160, 300), 24
            w, h = (length, t) if random.random() < 0.5 else (t, length)
            r = try_place(w, h)
            if r:
                obstacles.append(Obstacle(r))
        else:                                            # обикновен блок
            r = try_place(random.randint(56, 110), random.randint(56, 110))
            if r:
                obstacles.append(Obstacle(r))

    for _ in range(max(0, min(level - 2, 5))):           # движещи се стени (от ниво 3)
        axis = random.randint(0, 1)
        length, thick = random.randint(100, 150), 28
        w, h = (thick, length) if axis == 0 else (length, thick)
        amp = random.randint(70, 140)
        r = try_place(w, h, pad=(amp, 0) if axis == 0 else (0, amp))
        if r:
            obstacles.append(Obstacle(r, True, axis, amp,
                                      random.uniform(0.8, 1.8), random.uniform(0, 6.28)))

    for _ in range(max(0, min(level - 4, 4))):           # опасни зони (от ниво 5)
        s = random.randint(90, 130)
        r = try_place(s, s, margin=30)
        if r:
            hazards.append(Hazard(r))

    return obstacles, hazards


# ----------------------------------------------------------------------------
# Рисуване (помощни функции)
# ----------------------------------------------------------------------------
def draw_text(surf, text, font, color, pos, anchor="topleft", shadow=True):
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        surf.blit(font.render(text, True, (0, 0, 0)), rect.move(2, 2))
    surf.blit(img, rect)
    return rect


def draw_heart(surf, x, y, size, color):
    r = size // 4
    pygame.draw.circle(surf, color, (x + r, y + r), r)
    pygame.draw.circle(surf, color, (x + 3 * r, y + r), r)
    pygame.draw.polygon(surf, color, [(x, y + r + 2), (x + 4 * r, y + r + 2), (x + 2 * r, y + 4 * r + 2)])


def draw_monster(surf, pos, r, t, look, phase=0.0, flash=0.0, hp_frac=1.0):
    x, y = int(pos.x), int(pos.y)
    wob = math.sin(t * 6 + phase) * 2
    body = (70, 200, 70) if flash <= 0 else (230, 255, 230)
    dark = (28, 105, 38)
    pygame.draw.ellipse(surf, (0, 0, 0, 0) if False else (15, 20, 15),
                        (x - r, y + r - 6, 2 * r, 10))                       # сянка
    # рога
    pygame.draw.polygon(surf, dark, [(x - r + 3, y - r + 6), (x - r + 1, y - r - 9), (x - r // 2, y - r + 2)])
    pygame.draw.polygon(surf, dark, [(x + r - 3, y - r + 6), (x + r - 1, y - r - 9), (x + r // 2, y - r + 2)])
    pygame.draw.circle(surf, dark, (x, int(y + wob * 0.3)), r + 2)
    pygame.draw.circle(surf, body, (x, int(y + wob * 0.3)), r)
    # очи
    ex = r // 2
    ey = int(y - r * 0.2 + wob * 0.3)
    for sx in (-ex, ex):
        pygame.draw.circle(surf, WHITE, (x + sx, ey), max(4, r // 3))
        px = x + sx + math.cos(look) * 2
        py = ey + math.sin(look) * 2
        pygame.draw.circle(surf, (170, 20, 20), (int(px), int(py)), max(2, r // 6))
    # уста със зъби
    my = int(y + r * 0.45 + wob * 0.3)
    pygame.draw.line(surf, (20, 50, 25), (x - ex, my), (x + ex, my), 3)
    for tx in (-ex + 4, 0, ex - 4):
        pygame.draw.polygon(surf, WHITE, [(x + tx - 3, my), (x + tx + 3, my), (x + tx, my + 5)])
    if hp_frac < 1.0:
        w = 2 * r
        pygame.draw.rect(surf, (60, 0, 0), (x - r, y - r - 14, w, 4))
        pygame.draw.rect(surf, (230, 60, 60), (x - r, y - r - 14, int(w * hp_frac), 4))


# ----------------------------------------------------------------------------
# Играта
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        self.audio_enabled = False
        self.sounds = {}
        self.music_tracks = {"menu": [], "playing": []}
        self.music_orders = {"menu": [], "playing": []}
        self.music_last = {"menu": None, "playing": None}
        self.music_category = None
        self.load_audio()
        pygame.display.set_caption("Monster Shooter")
        self.save = load_save()
        self.volume = self.save["volume"]
        self.apply_volume()
        self.canvas = pygame.Surface((VW, VH))
        self.clock = pygame.time.Clock()
        self.scale = 1.0
        self.off = (0, 0)
        self.mouse_pos = pygame.mouse.get_pos()
        self.cursor_inside = True
        self.window_focused = True
        self.dragging_volume = False
        self.menu_cursor = self.make_menu_cursor()
        self.game_cursor = self.make_game_cursor()

        fam = "segoeui,arial,dejavusans,freesans"
        self.f_title = pygame.font.SysFont(fam, 84, bold=True)
        self.f_big = pygame.font.SysFont(fam, 52, bold=True)
        self.f_mid = pygame.font.SysFont(fam, 34, bold=True)
        self.f_small = pygame.font.SysFont(fam, 22)
        self.f_tiny = pygame.font.SysFont(fam, 16, bold=True)

        self.bg = self.make_background()
        self.red_overlay = pygame.Surface(ARENA.size)
        self.red_overlay.fill((225, 0, 0))

        self.apply_display_mode(self.save["display_mode"])

        self.running = True
        self.state = "menu"
        self.sel = 0
        self.t = 0.0
        self.run_active = False
        self.new_record = False
        self.deco = [{"pos": Vector2(random.uniform(60, VW - 60), random.uniform(60, VH - 60)),
                      "vel": Vector2(random.uniform(-60, 60), random.uniform(-60, 60)),
                      "phase": random.uniform(0, 6.28)} for _ in range(7)]
        self.reset_run()
        self.sync_music(force=True)

    def load_audio(self):
        """Load background playlists and event sounds from the bundled assets."""
        root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        sound_root = os.path.join(root, SOUND_FOLDER)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            pygame.mixer.music.set_volume(0.55)
            self.audio_enabled = True
        except pygame.error:
            # Keep the game playable on systems without an available audio device.
            return

        for category, folder in (("menu", "menu"), ("playing", "in game")):
            folder_path = os.path.join(sound_root, folder)
            if not os.path.isdir(folder_path):
                continue
            tracks = [os.path.join(folder_path, name) for name in os.listdir(folder_path)
                      if name.lower().endswith((".mp3", ".ogg", ".wav"))]
            self.music_tracks[category] = sorted(tracks)

        effect_folder = os.path.join(sound_root, "effects")
        for name in ("coin", "laser_player", "losing", "monster_dying", "new_record",
                     "player_hit"):
            path = os.path.join(effect_folder, name + ".mp3")
            if os.path.isfile(path):
                try:
                    self.sounds[name] = pygame.mixer.Sound(path)
                    self.sounds[name].set_volume(0.75)
                except pygame.error:
                    pass

    def play_sfx(self, name):
        sound = self.sounds.get(name)
        if self.audio_enabled and sound is not None:
            sound.play()

    def apply_volume(self):
        if not self.audio_enabled:
            return
        pygame.mixer.music.set_volume(0.55 * self.volume)
        for sound in self.sounds.values():
            sound.set_volume(0.75 * self.volume)

    def set_volume(self, volume, persist=False):
        self.volume = round(max(0.0, min(1.0, float(volume))), 2)
        self.save["volume"] = self.volume
        self.apply_volume()
        if persist:
            write_save(self.save)

    @staticmethod
    def volume_slider_rect():
        return pygame.Rect(VW // 2 - 235, 244, 470, 44)

    def set_volume_from_mouse(self, x, persist=False):
        left = VW // 2 - 210
        right = VW // 2 + 210
        self.set_volume((x - left) / (right - left), persist)

    @staticmethod
    def make_menu_cursor():
        cursor = pygame.Surface((28, 32), pygame.SRCALPHA)
        outline = [(1, 1), (1, 25), (8, 18), (14, 29), (19, 26),
                   (14, 16), (25, 16)]
        inside = [(3, 5), (3, 21), (8, 16), (14, 25), (16, 24),
                  (11, 14), (21, 14)]
        pygame.draw.polygon(cursor, WHITE, outline)
        pygame.draw.polygon(cursor, (0, 75, 38), inside)
        return cursor

    @staticmethod
    def make_game_cursor():
        cursor = pygame.Surface((36, 36), pygame.SRCALPHA)
        red = (245, 35, 45)
        center = (18, 18)
        pygame.draw.circle(cursor, red, center, 9, 2)
        pygame.draw.line(cursor, red, (18, 1), (18, 7), 2)
        pygame.draw.line(cursor, red, (18, 29), (18, 35), 2)
        pygame.draw.line(cursor, red, (1, 18), (7, 18), 2)
        pygame.draw.line(cursor, red, (29, 18), (35, 18), 2)
        pygame.draw.circle(cursor, red, center, 2)
        return cursor

    def update_cursor_visibility(self):
        pygame.mouse.set_visible(not (self.cursor_inside and self.window_focused))

    def draw_cursor(self, window):
        if not (self.cursor_inside and self.window_focused):
            return
        if self.state == "playing":
            cursor = self.game_cursor
            pos = (self.mouse_pos[0] - cursor.get_width() // 2,
                   self.mouse_pos[1] - cursor.get_height() // 2)
        else:
            cursor = self.menu_cursor
            pos = self.mouse_pos
        window.blit(cursor, pos)

    def next_music_track(self, category):
        tracks = self.music_tracks.get(category, [])
        if not tracks or not self.audio_enabled:
            return
        if not self.music_orders[category]:
            order = tracks[:]
            random.shuffle(order)
            last = self.music_last[category]
            if len(order) > 1 and order[0] == last:
                order[0], order[1] = order[1], order[0]
            self.music_orders[category] = order
        track = self.music_orders[category].pop(0)
        self.music_last[category] = track
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play()
        except pygame.error:
            self.music_orders[category] = []

    def sync_music(self, force=False):
        if not self.audio_enabled:
            return
        category = "playing" if self.state == "playing" else "menu"
        if force or category != self.music_category:
            pygame.mixer.music.stop()
            self.music_category = category
            self.next_music_track(category)
        elif not pygame.mixer.music.get_busy():
            self.next_music_track(category)

    # ------------------------------------------------------------ дисплей
    def desktop_size(self):
        try:
            return pygame.display.get_desktop_sizes()[0]
        except (AttributeError, pygame.error, IndexError):
            info = pygame.display.Info()
            return info.current_w, info.current_h

    def apply_display_mode(self, mode):
        dw, dh = self.desktop_size()
        # Пресъздаваме прозореца, за да се приложат позицията и флаговете
        pygame.display.quit()
        pygame.display.init()
        pygame.display.set_caption("Monster Shooter")
        if mode == "Fullscreen":
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
            pygame.display.set_mode((dw, dh), pygame.FULLSCREEN)
        elif mode == "Windowed Fullscreen":
            os.environ.pop("SDL_VIDEO_CENTERED", None)
            os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
            pygame.display.set_mode((dw, dh), pygame.NOFRAME)
        else:
            os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
            os.environ["SDL_VIDEO_CENTERED"] = "1"
            k = min(1.0, (dw - 80) / VW, (dh - 140) / VH)
            pygame.display.set_mode((int(VW * k), int(VH * k)), pygame.RESIZABLE)
        self.mouse_pos = pygame.mouse.get_pos()
        self.save["display_mode"] = mode
        write_save(self.save)
        self.update_cursor_visibility()

    def present(self):
        win = pygame.display.get_surface()
        ww, wh = win.get_size()
        s = min(ww / VW, wh / VH)
        sw, sh = int(VW * s), int(VH * s)
        self.scale = s
        self.off = ((ww - sw) // 2, (wh - sh) // 2)
        win.fill((0, 0, 0))
        if (sw, sh) == (VW, VH):
            win.blit(self.canvas, self.off)
        else:
            win.blit(pygame.transform.smoothscale(self.canvas, (sw, sh)), self.off)
        self.draw_cursor(win)
        pygame.display.flip()

    def vmouse(self, pos=None):
        if pos is None:
            pos = self.mouse_pos
        return Vector2((pos[0] - self.off[0]) / self.scale, (pos[1] - self.off[1]) / self.scale)

    # ------------------------------------------------------------ фон
    def make_background(self):
        base = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base, BG_FOLDER, BG_FILE),
            os.path.join(base, BG_FILE),
            os.path.join(BG_ABSOLUTE),
        ]
        for path in candidates:
            if not os.path.isfile(path):
                print("тук търся файла")
                continue
            try:
                # This runs before set_mode(); keep the loaded surface as-is because
                # convert()/convert_alpha() require a display format in pygame-ce.
                img = pygame.image.load(path)
            except pygame.error:
                continue
            # мащабиране "cover" - запълва целия кадър без изкривяване
            iw, ih = img.get_size()
            k = max(VW / iw, VH / ih)
            img = pygame.transform.smoothscale(img, (max(VW, int(iw * k)), max(VH, int(ih * k))))
            s = pygame.Surface((VW, VH))
            s.blit(img, ((VW - img.get_width()) // 2, (VH - img.get_height()) // 2))
            shade = pygame.Surface((VW, VH))
            shade.set_alpha(BG_DARKEN)          # затъмняване, за да се виждат обектите
            s.blit(shade, (0, 0))
            return s
        return self.make_procedural_background()

    def make_procedural_background(self):
        s = pygame.Surface((VW, VH))
        # Keep a neutral fallback if the image is unavailable; avoid the old purple screen.
        s.fill((24, 38, 52))
        rnd = random.Random(7)
        for _ in range(500):
            c = rnd.randint(30, 44)
            s.set_at((rnd.randint(0, VW - 1), rnd.randint(0, VH - 1)), (c, c + 4, c + 10))
        return s

    # ------------------------------------------------------------ игра
    def reset_run(self):
        self.level = 1
        self.coins_collected = 0
        self.kills = 0
        self.player = Player()
        self.bullets, self.coins, self.enemies, self.particles = [], [], [], []
        self.obstacles, self.hazards = [], []
        self.coin_timer = 2.0
        self.clear_t = 0.0
        self.intro_t = 0.0
        self.hurt_t = 0.0

    def new_game(self):
        self.reset_run()
        self.start_level(1)
        self.state = "playing"
        self.run_active = True
        self.new_record = False
        self.sync_music()

    def start_level(self, n):
        self.level = n
        self.obstacles, self.hazards = gen_level(n, self.player.pos)
        self.bullets.clear()
        self.coins = [c for c in self.coins
                      if not any(circle_hits_rect(c.pos, 12, o.rect) for o in self.obstacles)]
        self.enemies = []
        count = min(3 + n, 14)
        for _ in range(count):
            for _try in range(120):
                p = Vector2(random.uniform(ARENA.left + 50, ARENA.right - 50),
                            random.uniform(ARENA.top + 50, ARENA.bottom - 50))
                if p.distance_to(self.player.pos) < 300:
                    continue
                if any(circle_hits_rect(p, 30, o.rect) for o in self.obstacles):
                    continue
                if any(circle_hits_rect(p, 20, h.rect) for h in self.hazards):
                    continue
                self.enemies.append(Enemy(p, n))
                break
        self.clear_t = 0.0
        self.intro_t = 1.6

    @property
    def score(self):
        return self.coins_collected * 10 + self.kills * 25 + (self.level - 1) * 100

    def finish_run(self):
        if not self.run_active:
            return
        self.run_active = False
        if self.score > self.save["record_score"]:
            self.save["record_score"] = self.score
            self.save["record_coins"] = self.coins_collected
            self.save["record_level"] = self.level
            self.new_record = True
            write_save(self.save)
            self.play_sfx("new_record")

    def quit(self):
        self.finish_run()
        self.running = False

    # ------------------------------------------------------------ менюта
    def items(self):
        if self.state == "menu":
            return [("Start new game", self.new_game),
                    ("Settings", lambda: self.set_state("settings")),
                    ("Quit to Windows", self.quit)]
        if self.state == "settings":
            cur = self.save["display_mode"]
            its = [(("> " if m == cur else "   ") + m, (lambda mm=m: self.apply_display_mode(mm)))
                   for m in DISPLAY_MODES]
            its.append(("Back", lambda: self.set_state("menu")))
            return its
        if self.state == "paused":
            return [("Resume", lambda: self.set_state("playing")),
                    ("End run", self.end_run)]
        if self.state == "gameover":
            return [("Play again", self.new_game),
                    ("Main menu", lambda: self.set_state("menu"))]
        return []

    def set_state(self, s):
        self.state = s
        self.sel = 0
        self.sync_music()

    def end_run(self):
        self.finish_run()
        self.set_state("gameover")

    def item_rect(self, i):
        y0 = {"menu": 330, "settings": 360, "paused": 360, "gameover": 540}.get(self.state, 330)
        return pygame.Rect(VW // 2 - 200, y0 + i * 66, 400, 54)

    # ------------------------------------------------------------ събития
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.quit()
            elif e.type == pygame.WINDOWLEAVE:
                self.cursor_inside = False
                self.update_cursor_visibility()
            elif e.type == pygame.WINDOWENTER:
                self.cursor_inside = True
                self.update_cursor_visibility()
            elif e.type == pygame.WINDOWFOCUSLOST:
                self.window_focused = False
                self.update_cursor_visibility()
            elif e.type == pygame.WINDOWFOCUSGAINED:
                self.window_focused = True
                self.update_cursor_visibility()
            elif e.type == pygame.KEYDOWN:
                self.on_key(e.key)
            elif e.type == pygame.MOUSEMOTION:
                # Keep the latest SDL motion event for aiming; polling the cursor
                # after many simultaneous key presses can lag on some touchpads.
                self.mouse_pos = e.pos
                self.cursor_inside = True
                self.update_cursor_visibility()
                p = self.vmouse(e.pos)
                if self.dragging_volume and self.state == "settings":
                    self.set_volume_from_mouse(p.x)
                if self.state in MENU_STATES:
                    for i in range(len(self.items())):
                        if self.item_rect(i).collidepoint(p):
                            self.sel = i
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                if self.dragging_volume:
                    self.dragging_volume = False
                    write_save(self.save)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                p = self.vmouse(e.pos)
                if self.state == "settings" and self.volume_slider_rect().collidepoint(p):
                    self.dragging_volume = True
                    self.set_volume_from_mouse(p.x)
                elif self.state in MENU_STATES:
                    its = self.items()
                    for i in range(len(its)):
                        if self.item_rect(i).collidepoint(p):
                            self.sel = i
                            its[i][1]()
                            break

    def on_key(self, key):
        if self.state in MENU_STATES:
            its = self.items()
            if self.state == "settings" and key in (pygame.K_LEFT, pygame.K_RIGHT):
                delta = -0.05 if key == pygame.K_LEFT else 0.05
                self.set_volume(self.volume + delta, persist=True)
            elif key in (pygame.K_UP, pygame.K_w) and its:
                self.sel = (self.sel - 1) % len(its)
            elif key in (pygame.K_DOWN, pygame.K_s) and its:
                self.sel = (self.sel + 1) % len(its)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and its:
                its[min(self.sel, len(its) - 1)][1]()
            elif key == pygame.K_ESCAPE:
                if self.state == "settings":
                    self.set_state("menu")
                elif self.state == "paused":
                    self.set_state("playing")
                elif self.state == "gameover":
                    self.set_state("menu")
        elif self.state == "playing" and key == pygame.K_ESCAPE:
            self.set_state("paused")

    # ------------------------------------------------------------ ъпдейт
    def update(self, dt):
        self.t += dt
        self.sync_music()
        if self.state in ("menu", "settings"):
            for d in self.deco:
                d["pos"] += d["vel"] * dt
                if d["pos"].x < 40 or d["pos"].x > VW - 40:
                    d["vel"].x *= -1
                if d["pos"].y < 40 or d["pos"].y > VH - 40:
                    d["vel"].y *= -1
            return
        if self.state != "playing":
            return
        self.update_world(dt)

    def spawn_particles(self, pos, color, n):
        for _ in range(n):
            self.particles.append(Particle(pos, color))

    def damage_player(self):
        p = self.player
        if p.invuln > 0:
            return
        p.hp -= 1
        self.play_sfx("player_hit")
        p.invuln = 1.2
        self.hurt_t = 0.3
        self.spawn_particles(p.pos, (90, 160, 255), 12)

    @staticmethod
    def enemy_volley_angles(level, base):
        """Return a random fan volley, adding one possible bullet every two levels."""
        max_shots = min(7, 1 + (level - 1) // 2)
        shot_count = random.randint(1, max_shots)
        if shot_count == 1:
            return [base]
        angle_step = min(0.49, 0.14 + (shot_count - 2) * 0.07)
        center = (shot_count - 1) / 2
        return [base + (i - center) * angle_step for i in range(shot_count)]

    def update_world(self, dt):
        p = self.player
        keys = pygame.key.get_pressed()
        for ob in self.obstacles:
            ob.update(dt)

        # --- играч
        move = Vector2(int(keys[pygame.K_d] or keys[pygame.K_RIGHT]) - int(keys[pygame.K_a] or keys[pygame.K_LEFT]),
                       int(keys[pygame.K_s] or keys[pygame.K_DOWN]) - int(keys[pygame.K_w] or keys[pygame.K_UP]))
        if move.length_squared() > 0:
            p.pos += move.normalize() * 270 * dt
        for ob in self.obstacles:
            push_out(p.pos, Player.RADIUS, ob.rect)
        clamp_to_arena(p.pos, Player.RADIUS)

        aim_keys = Vector2(int(keys[pygame.K_l]) - int(keys[pygame.K_j]),
                           int(keys[pygame.K_k]) - int(keys[pygame.K_i]))
        if aim_keys.length_squared() > 0:
            p.angle = math.atan2(aim_keys.y, aim_keys.x)
        else:
            aim = self.vmouse() - p.pos
            if aim.length_squared() > 4:
                p.angle = math.atan2(aim.y, aim.x)
        p.cd -= dt
        p.invuln = max(0.0, p.invuln - dt)
        self.hurt_t = max(0.0, self.hurt_t - dt)
        if (pygame.mouse.get_pressed()[0] or keys[pygame.K_SPACE]) and p.cd <= 0:
            d = Vector2(math.cos(p.angle), math.sin(p.angle))
            self.bullets.append(Bullet(p.pos + d * 22, d * 680, "player", 4))
            self.play_sfx("laser_player")
            p.cd = 0.17

        # --- противници
        level = self.level
        bspeed = min(210 + 14 * level, 400)
        spread = max(0.04, 0.2 - level * 0.015)
        for e in self.enemies:
            e.flash = max(0.0, e.flash - dt)
            e.retarget -= dt
            if e.retarget <= 0 or e.pos.distance_to(e.target) < 10:
                e.target = Vector2(random.uniform(ARENA.left + 50, ARENA.right - 50),
                                   random.uniform(ARENA.top + 50, ARENA.bottom - 50))
                e.retarget = random.uniform(0.8, 2.2)
            dv = e.target - e.pos
            if dv.length_squared() > 1:
                e.pos += dv.normalize() * e.speed * dt
            for ob in self.obstacles:
                push_out(e.pos, e.r, ob.rect)
            clamp_to_arena(e.pos, e.r)

            e.shoot_t -= dt
            if e.shoot_t <= 0:
                e.shoot_t = e.interval * random.uniform(0.7, 1.3)
                base = math.atan2(p.pos.y - e.pos.y, p.pos.x - e.pos.x) + random.uniform(-spread, spread)
                angles = self.enemy_volley_angles(level, base)
                for a in angles:
                    v = Vector2(math.cos(a), math.sin(a))
                    self.bullets.append(Bullet(e.pos + v * (e.r + 4), v * bspeed, "enemy", 5))

            if e.pos.distance_to(p.pos) < e.r + Player.RADIUS - 2:
                self.damage_player()

        # --- куршуми
        for b in self.bullets:
            b.update(dt, self.obstacles)
            if b.dead:
                continue
            if b.owner == "player":
                for e in self.enemies:
                    if b.pos.distance_to(e.pos) < e.r + b.r:
                        b.dead = True
                        e.hp -= 1
                        e.flash = 0.1
                        self.spawn_particles(b.pos, (120, 255, 120), 4)
                        break
            elif b.pos.distance_to(p.pos) < Player.RADIUS + b.r:
                b.dead = True
                self.damage_player()
        self.bullets = [b for b in self.bullets if not b.dead]

        # --- умрели противници
        alive = []
        for e in self.enemies:
            if e.hp > 0:
                alive.append(e)
                continue
            self.kills += 1
            self.play_sfx("monster_dying")
            self.spawn_particles(e.pos, (90, 220, 90), 18)
            for _ in range(random.randint(1, 2)):
                off = Vector2(random.uniform(-14, 14), random.uniform(-14, 14))
                cp = e.pos + off
                clamp_to_arena(cp, 10)
                self.coins.append(Coin(cp))
        self.enemies = alive

        # --- опасни зони
        for h in self.hazards:
            if circle_hits_rect(p.pos, Player.RADIUS - 2, h.rect):
                self.damage_player()

        # --- монети
        self.coin_timer -= dt
        if self.coin_timer <= 0:
            self.coin_timer = random.uniform(2.5, 4.5)
            if len(self.coins) < 6:
                for _ in range(40):
                    cp = Vector2(random.uniform(ARENA.left + 40, ARENA.right - 40),
                                 random.uniform(ARENA.top + 40, ARENA.bottom - 40))
                    if any(circle_hits_rect(cp, 16, o.rect) for o in self.obstacles):
                        continue
                    if any(circle_hits_rect(cp, 12, h.rect) for h in self.hazards):
                        continue
                    self.coins.append(Coin(cp))
                    break
        kept = []
        for c in self.coins:
            c.age += dt
            if c.age >= c.life:
                continue
            if c.pos.distance_to(p.pos) < Player.RADIUS + 10:
                self.coins_collected += 1
                self.play_sfx("coin")
                self.spawn_particles(c.pos, YELLOW, 8)
                continue
            kept.append(c)
        self.coins = kept

        # --- частици
        for pt in self.particles:
            pt.life -= dt
            pt.pos += pt.vel * dt
            pt.vel *= 0.94
        self.particles = [pt for pt in self.particles if pt.life > 0]

        # --- край / следващо ниво
        self.intro_t = max(0.0, self.intro_t - dt)
        if p.hp <= 0:
            self.finish_run()
            self.play_sfx("losing")
            self.set_state("gameover")
            return
        if not self.enemies:
            if self.clear_t <= 0:
                self.clear_t = 2.2
            else:
                self.clear_t -= dt
                if self.clear_t <= 0:
                    p.hp = min(MAX_HP, p.hp + 1)
                    self.start_level(self.level + 1)

    # ------------------------------------------------------------ рисуване
    def draw(self):
        c = self.canvas
        if self.state in ("menu", "settings"):
            self.draw_menu_bg()
        else:
            self.draw_world()
            self.draw_hud()
            if self.state == "paused":
                self.dim(150)
                draw_text(c, "PAUSED", self.f_big, WHITE, (VW // 2, 270), "center")
            elif self.state == "gameover":
                self.dim(190)
                self.draw_gameover()
        if self.state in MENU_STATES:
            self.draw_buttons()

    def dim(self, alpha):
        s = pygame.Surface((VW, VH))
        s.set_alpha(alpha)
        self.canvas.blit(s, (0, 0))

    def draw_menu_bg(self):
        c = self.canvas
        c.blit(self.bg, (0, 0))
        for d in self.deco:
            look = math.atan2(VH / 2 - d["pos"].y, VW / 2 - d["pos"].x)
            draw_monster(c, d["pos"], 30, self.t, look, d["phase"])
        self.dim(110)
        if self.state == "menu":
            draw_text(c, "MONSTER RAMPAGE", self.f_title, (110, 235, 110), (VW // 2, 150), "center")
            draw_text(c, "Time to defeat the monsters hiding under your bed!!!", self.f_small, (110, 235, 110), (VW // 2, 215), "center")
            rs = self.save
            if rs["record_score"] > 0:
                draw_text(c, f"Record: {rs['record_score']}   (Coins collected: {rs['record_coins']};"
                             f" Level: {rs['record_level']})",
                          self.f_small, YELLOW, (VW // 2, 270), "center")
            else:
                draw_text(c, "No record yet - go set one!", self.f_small, GRAY, (VW // 2, 270), "center")
            draw_text(c, "WASD move  |  Mouse or IJKL aim  |  LMB / SPACE shoot  |  ESC pause",
                      self.f_small, GRAY, (VW // 2, VH - 40), "center")
        else:
            draw_text(c, "SETTINGS", self.f_big, WHITE, (VW // 2, 125), "center")
            draw_text(c, f"MASTER VOLUME  {round(self.volume * 100)}%", self.f_mid, WHITE,
                      (VW // 2, 207), "center")
            x1, x2, y = VW // 2 - 210, VW // 2 + 210, 266
            knob_x = int(x1 + (x2 - x1) * self.volume)
            pygame.draw.line(c, (70, 78, 91), (x1, y), (x2, y), 10)
            pygame.draw.line(c, (110, 235, 110), (x1, y), (knob_x, y), 10)
            pygame.draw.circle(c, WHITE, (knob_x, y), 15)
            pygame.draw.circle(c, (70, 140, 255), (knob_x, y), 9)
            draw_text(c, "Drag the slider or use Left / Right", self.f_tiny, GRAY,
                      (VW // 2, 302), "center")
            draw_text(c, "Display mode", self.f_mid, GRAY, (VW // 2, 337), "center")

    def draw_buttons(self):
        c = self.canvas
        for i, (label, _) in enumerate(self.items()):
            r = self.item_rect(i)
            sel = i == self.sel
            pygame.draw.rect(c, (50, 120, 55) if sel else (38, 44, 56), r, border_radius=8)
            pygame.draw.rect(c, (140, 255, 140) if sel else (90, 98, 115), r, 3, border_radius=8)
            draw_text(c, label, self.f_mid, WHITE if sel else (200, 205, 215), r.center, "center")

    def draw_gameover(self):
        c = self.canvas
        draw_text(c, "GAME OVER", self.f_big, RED, (VW // 2, 130), "center")
        draw_text(c, f"Coins collected: {self.coins_collected}", self.f_mid, YELLOW, (VW // 2, 215), "center")
        draw_text(c, f"Level: {self.level}", self.f_mid, WHITE, (VW // 2, 262), "center")
        draw_text(c, f"Monsters killed: {self.kills}", self.f_small, GRAY, (VW // 2, 305), "center")
        draw_text(c, f"Score: {self.score}", self.f_big, WHITE, (VW // 2, 365), "center")
        rs = self.save
        if self.new_record:
            draw_text(c, "NEW RECORD!", self.f_big, (110, 255, 110), (VW // 2, 440), "center")
        else:
            diff = rs["record_score"] - self.score
            draw_text(c, f"Record: {rs['record_score']}  (Coins collected: {rs['record_coins']};"
                         f" Level: {rs['record_level']})", self.f_small, YELLOW, (VW // 2, 430), "center")
            draw_text(c, f"{diff} points to beat the record", self.f_small, GRAY, (VW // 2, 465), "center")

    def draw_world(self):
        c = self.canvas
        t = self.t
        c.blit(self.bg, ARENA.topleft, ARENA)

        for h in self.hazards:
            pulse = 0.5 + 0.5 * math.sin(t * 4)
            col = (int(110 + 80 * pulse), 25, 25)
            pygame.draw.rect(c, col, h.rect)
            pygame.draw.rect(c, (255, 90, 60), h.rect, 3)
            for k in range(-h.rect.height, h.rect.width, 26):
                a = (max(h.rect.left, h.rect.left + k), max(h.rect.top, h.rect.top - k))
                b = (min(h.rect.right, h.rect.left + k + h.rect.height),
                     min(h.rect.bottom, h.rect.top - k + h.rect.width))
                if a[0] < b[0] and a[1] < b[1]:
                    pygame.draw.line(c, (60, 8, 8), a, b, 3)

        for ob in self.obstacles:
            if ob.moving:
                pygame.draw.rect(c, (150, 105, 40), ob.rect)
                pygame.draw.rect(c, (255, 195, 70), ob.rect, 3)
                pygame.draw.rect(c, (95, 65, 25), ob.rect.inflate(-12, -12), 2)
            else:
                pygame.draw.rect(c, (84, 90, 104), ob.rect)
                pygame.draw.rect(c, (150, 158, 174), ob.rect, 3)
                pygame.draw.rect(c, (60, 65, 78), ob.rect.inflate(-12, -12), 2)

        for co in self.coins:
            if co.life - co.age < 3 and int(t * 8) % 2:
                continue
            bob = math.sin(t * 5 + co.phase)
            w = max(3, int(9 * abs(math.cos(t * 3 + co.phase))))
            x, y = int(co.pos.x), int(co.pos.y + bob * 2)
            pygame.draw.ellipse(c, (150, 105, 10), (x - w - 1, y - 11, 2 * w + 2, 22))
            pygame.draw.ellipse(c, YELLOW, (x - w, y - 10, 2 * w, 20))

        for b in self.bullets:
            if b.owner == "player":
                pygame.draw.circle(c, (90, 220, 255), b.pos, b.r + 2)
                pygame.draw.circle(c, WHITE, b.pos, b.r - 1)
            else:
                pygame.draw.circle(c, (255, 90, 40), b.pos, b.r + 3)
                pygame.draw.circle(c, (255, 220, 120), b.pos, b.r - 1)

        pl = self.player
        for e in self.enemies:
            look = math.atan2(pl.pos.y - e.pos.y, pl.pos.x - e.pos.x)
            draw_monster(c, e.pos, e.r, t, look, e.phase, e.flash, e.hp / e.max_hp)

        if not (pl.invuln > 0 and int(t * 20) % 2):
            x, y = int(pl.pos.x), int(pl.pos.y)
            d = Vector2(math.cos(pl.angle), math.sin(pl.angle))
            pygame.draw.ellipse(c, (10, 12, 14), (x - 14, y + 8, 28, 10))
            pygame.draw.line(c, (60, 65, 75), (x, y), (x + d.x * 28, y + d.y * 28), 8)
            pygame.draw.line(c, (170, 175, 190), (x, y), (x + d.x * 26, y + d.y * 26), 4)
            pygame.draw.circle(c, (25, 55, 120), (x, y), Player.RADIUS + 2)
            pygame.draw.circle(c, (70, 140, 255), (x, y), Player.RADIUS)
            pygame.draw.circle(c, (180, 215, 255), (x - 4, y - 4), 5)

        for pt in self.particles:
            sz = max(1, int(4 * pt.life / pt.max_life))
            pygame.draw.circle(c, pt.color, pt.pos, sz)

        # рамка на арената
        pygame.draw.rect(c, (120, 128, 145), ARENA, BORDER)
        pygame.draw.rect(c, (60, 66, 80), ARENA.inflate(-BORDER * 2, -BORDER * 2), 2)

        if self.hurt_t > 0:
            self.red_overlay.set_alpha(int(110 * self.hurt_t / 0.3))
            c.blit(self.red_overlay, ARENA.topleft)

        if self.state == "playing":
            if self.clear_t > 0:
                draw_text(c, "LEVEL CLEARED!", self.f_big, (110, 255, 110), ARENA.center, "center")
                draw_text(c, "+1 heart  -  grab the coins!", self.f_small, WHITE,
                          (ARENA.centerx, ARENA.centery + 46), "center")
            elif self.intro_t > 0:
                img = self.f_big.render(f"LEVEL {self.level}", True, WHITE)
                img.set_alpha(int(255 * min(1.0, self.intro_t / 0.6)))
                c.blit(img, img.get_rect(center=ARENA.center))

    def draw_hud(self):
        c = self.canvas
        pygame.draw.rect(c, (0, 0, 0), (0, 0, VW, HUD_H))
        pygame.draw.line(c, (90, 98, 115), (0, HUD_H - 1), (VW, HUD_H - 1), 3)

        for i in range(MAX_HP):
            col = (235, 60, 80) if i < self.player.hp else (60, 40, 48)
            draw_heart(c, 20 + i * 38, 30, 28, col)
        draw_text(c, "HEALTH", self.f_tiny, GRAY, (20, 10))

        def stat(x, label, value, color=WHITE):
            draw_text(c, label, self.f_tiny, GRAY, (x, 10))
            draw_text(c, str(value), self.f_big, color, (x, 28))

        stat(250, "LEVEL", self.level)
        stat(390, "COINS", self.coins_collected, YELLOW)
        stat(560, "SCORE", self.score)
        stat(760, "MONSTERS", len(self.enemies), (110, 235, 110))
        stat(930, "RECORD", max(self.save["record_score"], 0), GRAY)

        # --- live миникарта: само рамка, препятствия и позиция на играча
        mm = pygame.Rect(VW - 180, 8, 164, 80)
        pygame.draw.rect(c, (10, 12, 16), mm)

        def to_mm(x, y):
            return (mm.x + (x - ARENA.x) / ARENA.w * mm.w,
                    mm.y + (y - ARENA.y) / ARENA.h * mm.h)

        for h in self.hazards:
            x, y = to_mm(h.rect.x, h.rect.y)
            pygame.draw.rect(c, (150, 50, 50), (x, y, max(2, h.rect.w / ARENA.w * mm.w),
                                                 max(2, h.rect.h / ARENA.h * mm.h)))
        for ob in self.obstacles:
            x, y = to_mm(ob.rect.x, ob.rect.y)
            col = (230, 170, 60) if ob.moving else (170, 178, 195)
            pygame.draw.rect(c, col, (x, y, max(2, ob.rect.w / ARENA.w * mm.w),
                                      max(2, ob.rect.h / ARENA.h * mm.h)))
        px, py = to_mm(self.player.pos.x, self.player.pos.y)
        pygame.draw.circle(c, (70, 150, 255), (int(px), int(py)), 4)
        pygame.draw.circle(c, WHITE, (int(px), int(py)), 4, 1)
        pygame.draw.rect(c, WHITE, mm, 2)

    # ------------------------------------------------------------ основен цикъл
    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
            self.present()
        pygame.mouse.set_visible(True)
        pygame.quit()


def main():
    Game().run()


if __name__ == "__main__":
    main()
