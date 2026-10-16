import sys
import os
import json
import random
import subprocess
import pygame
from datetime import datetime

try:
    # -------------------------------------------------------------------------
    # 1. INITIALIZATION & SETUP
    # -------------------------------------------------------------------------
    pygame.init()
    pygame.mixer.init()

    # Window Settings (Standard 480x320 Touch Display)
    WIDTH, HEIGHT = 480, 320
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Alarmo Smart Clock + Jellyfin Hub")

    # Dynamic Color Palette Defaults (Will adapt to active theme art)
    BG_COLOR = (25, 25, 35)
    TEXT_COLOR = (255, 255, 255)
    ACCENT_COLOR = (255, 90, 90)
    NIGHT_COLOR = (90, 140, 255)
    BTN_COLOR = (45, 45, 65)
    BTN_HOVER = (65, 65, 95)
    BTN_SELECT = (40, 110, 80)

    # Fonts
    font_xlarge = pygame.font.SysFont(None, 64)
    font_large = pygame.font.SysFont(None, 46)
    font_med = pygame.font.SysFont(None, 20)
    font_small = pygame.font.SysFont(None, 14)

    # Configuration Defaults & Persistence
    JELLYFIN_SERVER_URL = "http://192.168.1.100:8096"

    # Ensure working directory is set to script location for path safety
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    CONFIG_FILE = "alarm_config.json"

    target_alarm_hour = 7
    target_alarm_minute = 0
    target_night_hour = 22
    target_night_minute = 30

    def load_schedule():
        global target_alarm_hour, target_alarm_minute, target_night_hour, target_night_minute
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    target_alarm_hour = data.get("alarm_hour", 7)
                    target_alarm_minute = data.get("alarm_minute", 0)
                    target_night_hour = data.get("night_hour", 22)
                    target_night_minute = data.get("night_minute", 30)
                    print("Successfully loaded saved schedule.")
            except Exception as e:
                print(f"Failed to load config: {e}")

    def save_schedule():
        data = {
            "alarm_hour": target_alarm_hour,
            "alarm_minute": target_alarm_minute,
            "night_hour": target_night_hour,
            "night_minute": target_night_minute
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f)
            print("Schedule saved successfully.")
        except Exception as e:
            print(f"Failed to save config: {e}")

    load_schedule()

    # -------------------------------------------------------------------------
    # 2. UI CLASSES & DYNAMIC THEME ENGINE
    # -------------------------------------------------------------------------
    class StandardButton:
        """Chunky action button for navigation and controls."""
        def __init__(self, x, y, w, h, text, color=BTN_COLOR, hover_color=BTN_HOVER):
            self.rect = pygame.Rect(x, y, w, h)
            self.text = text
            self.color = color
            self.hover_color = hover_color

        def draw(self, surface, font, is_selected=False):
            mouse_pos = pygame.mouse.get_pos()
            current_color = BTN_SELECT if is_selected else (self.hover_color if self.rect.collidepoint(mouse_pos) else self.color)

            pygame.draw.rect(surface, current_color, self.rect, border_radius=10)
            pygame.draw.rect(surface, (110, 110, 150), self.rect, 2, border_radius=10)

            text_surf = font.render(self.text, True, TEXT_COLOR)
            surface.blit(text_surf, (self.rect.centerx - text_surf.get_width() // 2,
                                     self.rect.centery - text_surf.get_height() // 2))

        def is_clicked(self, event):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return self.rect.collidepoint(event.pos)
            return False

    class VerticalCardButton:
        """Ryujinx-style theme selection card with boxart support."""
        def __init__(self, x, y, w, h, text, color=BTN_COLOR, hover_color=BTN_HOVER, logo_surface=None):
            self.rect = pygame.Rect(x, y, w, h)
            self.text = text
            self.color = color
            self.hover_color = hover_color
            self.logo_surface = logo_surface

        def draw(self, surface, font, is_selected=False):
            mouse_pos = pygame.mouse.get_pos()
            current_color = BTN_SELECT if is_selected else (self.hover_color if self.rect.collidepoint(mouse_pos) else self.color)

            pygame.draw.rect(surface, current_color, self.rect, border_radius=10)
            pygame.draw.rect(surface, (100, 100, 140), self.rect, 2, border_radius=10)

            if self.logo_surface:
                logo_rect = self.logo_surface.get_rect(midtop=(self.rect.centerx, self.rect.top + 8))
                surface.blit(self.logo_surface, logo_rect)
            else:
                placeholder_rect = pygame.Rect(self.rect.left + 8, self.rect.top + 8, self.rect.width - 16, 75)
                pygame.draw.rect(surface, (30, 30, 45), placeholder_rect, border_radius=6)
                ph_text = font.render("No Art", True, (130, 130, 150))
                surface.blit(ph_text, (placeholder_rect.centerx - ph_text.get_width() // 2, placeholder_rect.centery - ph_text.get_height() // 2))

            text_surf = font.render(self.text, True, TEXT_COLOR)
            if text_surf.get_width() > self.rect.width - 10:
                truncated_text = self.text
                while font.render(truncated_text + "..", True, TEXT_COLOR).get_width() > self.rect.width - 10 and len(truncated_text) > 0:
                    truncated_text = truncated_text[:-1]
                text_surf = font.render(truncated_text + "..", True, TEXT_COLOR)

            surface.blit(text_surf, (self.rect.centerx - text_surf.get_width() // 2, self.rect.bottom - 20))

        def is_clicked(self, event):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return self.rect.collidepoint(event.pos)
            return False

    def update_dynamic_palette(logo_surface):
        """Extracts dominant color from logo art via 1x1 downscale and updates theme palette."""
        global BG_COLOR, BTN_COLOR, BTN_HOVER, BTN_SELECT
        if not logo_surface:
            BG_COLOR = (25, 25, 35)
            BTN_COLOR = (45, 45, 65)
            BTN_HOVER = (65, 65, 95)
            BTN_SELECT = (40, 110, 80)
            return

        tiny = pygame.transform.smoothscale(logo_surface, (1, 1))
        r, g, b = tiny.get_at((0, 0))[:3]

        bg_r = max(15, int(r * 0.15))
        bg_g = max(15, int(g * 0.15))
        bg_b = max(20, int(b * 0.15))
        BG_COLOR = (bg_r, bg_g, bg_b)

        btn_r = min(220, max(35, int(r * 0.35)))
        btn_g = min(220, max(35, int(g * 0.35)))
        btn_b = min(220, max(45, int(b * 0.35)))
        BTN_COLOR = (btn_r, btn_g, btn_b)

        hover_r = min(255, btn_r + 25)
        hover_g = min(255, btn_g + 25)
        hover_b = min(255, btn_b + 25)
        BTN_HOVER = (hover_r, hover_g, hover_b)

        sel_r = min(255, max(30, int(r * 0.7)))
        sel_g = min(255, max(30, int(g * 0.7)))
        sel_b = min(255, max(40, int(b * 0.7)))
        BTN_SELECT = (sel_r, sel_g, sel_b)

    # -------------------------------------------------------------------------
    # 3. SOUND & LOCAL STORAGE SCANNER
    # -------------------------------------------------------------------------
    SOUNDS_ROOT = "sounds"
    alarm_playlists = {}
    alarm_logos = {}
    night_playlists = {}
    night_logos = {}

    current_alarm_theme = "None"
    current_night_theme = "None"
    alarm_queue = []
    night_queue = []
    current_track_name = "No tracks loaded"

    def scan_sound_folders():
        global alarm_playlists, alarm_logos, night_playlists, night_logos
        global current_alarm_theme, current_night_theme

        alarm_playlists, alarm_logos = {}, {}
        night_playlists, night_logos = {}, {}

        alarm_dir = os.path.join(SOUNDS_ROOT, "alarms")
        if not os.path.exists(alarm_dir):
            alarm_dir = os.path.join(SOUNDS_ROOT, "alarm")

        night_dir = os.path.join(SOUNDS_ROOT, "night")
        if not os.path.exists(night_dir):
            night_dir = os.path.join(SOUNDS_ROOT, "nights")

        os.makedirs(alarm_dir, exist_ok=True)
        os.makedirs(night_dir, exist_ok=True)

        def parse_category_dir(category_path, playlist_dict, logo_dict):
            if not os.path.exists(category_path):
                return
            for sub in os.listdir(category_path):
                sub_path = os.path.join(category_path, sub)
                if os.path.isdir(sub_path):
                    tracks = [os.path.join(sub_path, f) for f in os.listdir(sub_path) if f.endswith('.mp3')]
                    if tracks:
                        playlist_dict[sub] = tracks

                    for file in os.listdir(sub_path):
                        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                            img_path = os.path.join(sub_path, file)
                            try:
                                raw_img = pygame.image.load(img_path).convert_alpha()
                                logo_dict[sub] = pygame.transform.smoothscale(raw_img, (96, 75))
                            except Exception as e:
                                print(f"Could not load image {img_path}: {e}")
                            break

        parse_category_dir(alarm_dir, alarm_playlists, alarm_logos)
        parse_category_dir(night_dir, night_playlists, night_logos)

        if alarm_playlists:
            set_alarm_theme(list(alarm_playlists.keys())[0])
        if night_playlists:
            set_night_theme(list(night_playlists.keys())[0])

    def set_alarm_theme(name):
        global current_alarm_theme, alarm_queue
        if name in alarm_playlists:
            current_alarm_theme = name
            alarm_queue = list(alarm_playlists[name])
            random.shuffle(alarm_queue)
            update_dynamic_palette(alarm_logos.get(name, None))

    def set_night_theme(name):
        global current_night_theme, night_queue
        if name in night_playlists:
            current_night_theme = name
            night_queue = list(night_playlists[name])
            random.shuffle(night_queue)

    def play_alarm_track():
        global current_track_name, alarm_queue
        if not alarm_playlists or current_alarm_theme not in alarm_playlists:
            current_track_name = "No alarm tracks!"
            return
        if not alarm_queue:
            alarm_queue = list(alarm_playlists[current_alarm_theme])
            random.shuffle(alarm_queue)

        if alarm_queue:
            track_path = alarm_queue.pop(0)
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.play(fade_ms=3000)
            current_track_name = os.path.basename(track_path)

    def play_night_track():
        global current_track_name, night_queue
        if not night_playlists or current_night_theme not in night_playlists:
            current_track_name = "No night tracks!"
            return
        if not night_queue:
            night_queue = list(night_playlists[current_night_theme])
            random.shuffle(night_queue)

        if night_queue:
            track_path = night_queue.pop(0)
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.play(-1, fade_ms=5000)
            current_track_name = os.path.basename(track_path)

    def launch_jellyfin_client():
        """Launches external browser stream pointed at Jellyfin."""
        try:
            subprocess.Popen(["xdg-open", JELLYFIN_SERVER_URL])
            print("Successfully launched Jellyfin via xdg-open.")
        except Exception as err:
            print(f"Failed to launch Jellyfin client: {err}")

    scan_sound_folders()

    # -------------------------------------------------------------------------
    # 4. APP STATE & UI ELEMENT DECLARATION
    # -------------------------------------------------------------------------
    app_state = "MAIN"

    # Main Clock Screen Controls
    btn_settings     = StandardButton(20, 260, 215, 45, "Settings")
    btn_toggle_night = StandardButton(245, 260, 215, 45, "Toggle Night")

    # Dismiss / Stop controls when active
    btn_settings_small = StandardButton(20, 260, 215, 45, "Settings")
    btn_stop_small     = StandardButton(245, 260, 215, 45, "Dismiss Alarm")

    # Settings Hub Menu Controls (Adjusted vertical spacing to fit 5 options neatly)
    btn_set_alarm_th  = StandardButton(20, 35,  440, 40, "Alarm Theme Setup")
    btn_set_night_th  = StandardButton(20, 80,  440, 40, "Night Sounds Setup")
    btn_set_schedule  = StandardButton(20, 125, 440, 40, "Edit Alarm / Bedtime Schedule")
    btn_jellyfin_menu = StandardButton(20, 170, 440, 40, "Jellyfin TV Mode")
    btn_test_alarm    = StandardButton(20, 215, 440, 40, "Test Alarm Now")
    btn_settings_back = StandardButton(20, 265, 440, 40, "Back to Clock")

    # Sub-Menu Back Buttons
    btn_alarm_back  = StandardButton(20, 265, 440, 40, "Back to Settings")
    btn_night_back  = StandardButton(20, 265, 440, 40, "Back to Settings")
    btn_jelly_back  = StandardButton(20, 265, 440, 40, "Back to Settings")

    # Jellyfin Menu Launch Button
    btn_jelly_launch = StandardButton(20, 180, 440, 60, "Launch Jellyfin Player")

    # Time Picker Controls
    picker_mode = "ALARM"
    btn_toggle_mode = StandardButton(20, 45, 440, 35, "Editing: Alarm Time")
    btn_hour_up     = StandardButton(110, 105, 60, 45, "+")
    btn_hour_dn     = StandardButton(110, 195, 60, 45, "-")
    btn_min_up      = StandardButton(310, 105, 60, 45, "+")
    btn_min_dn      = StandardButton(310, 195, 60, 45, "-")
    btn_time_save   = StandardButton(20, 260, 440, 40, "Save & Back")

    # State variables
    alarm_active = False
    night_active = False
    motion_detected = False

    alarm_enabled = True
    night_enabled = True

    clock = pygame.time.Clock()

    # -------------------------------------------------------------------------
    # 5. MAIN EVENT & DISPLAY LOOP
    # -------------------------------------------------------------------------
    running = True
    while running:
        # Build Ryujinx theme cards dynamically with current button colors
        alarm_buttons = []
        for i, key in enumerate(alarm_playlists.keys()):
            col, row = i % 3, i // 3
            bx, by = 20 + col * 148, 50 + row * 125
            if by < 250:
                logo = alarm_logos.get(key, None)
                alarm_buttons.append((key, VerticalCardButton(bx, by, 132, 115, key.capitalize(), color=BTN_COLOR, hover_color=BTN_HOVER, logo_surface=logo)))

        night_buttons = []
        for i, key in enumerate(night_playlists.keys()):
            col, row = i % 3, i // 3
            bx, by = 20 + col * 148, 50 + row * 125
            if by < 250:
                logo = night_logos.get(key, None)
                night_buttons.append((key, VerticalCardButton(bx, by, 132, 115, key.capitalize(), color=BTN_COLOR, hover_color=BTN_HOVER, logo_surface=logo)))

        # Update button colors dynamically
        for btn in [btn_settings, btn_toggle_night, btn_settings_small, btn_stop_small,
                    btn_set_alarm_th, btn_set_night_th, btn_set_schedule, btn_jellyfin_menu, btn_test_alarm,
                    btn_settings_back, btn_alarm_back, btn_night_back, btn_jelly_back,
                    btn_jelly_launch, btn_toggle_mode, btn_hour_up, btn_hour_dn,
                    btn_min_up, btn_min_dn, btn_time_save]:
            btn.color = BTN_COLOR
            btn.hover_color = BTN_HOVER

        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if app_state == "MAIN":
                if alarm_active or night_active or motion_detected:
                    if btn_stop_small.is_clicked(event):
                        motion_detected = False
                        alarm_active = False
                        night_active = False
                        pygame.mixer.music.fadeout(2000)
                    elif btn_settings_small.is_clicked(event):
                        motion_detected = False
                        alarm_active = False
                        night_active = False
                        pygame.mixer.music.fadeout(2000)
                        app_state = "SETTINGS"
                else:
                    if btn_settings.is_clicked(event):
                        app_state = "SETTINGS"
                    elif btn_toggle_night.is_clicked(event):
                        if night_active:
                            night_active = False
                            pygame.mixer.music.fadeout(2000)
                        else:
                            if night_playlists:
                                night_active = True
                                alarm_active = False
                                play_night_track()

            elif app_state == "SETTINGS":
                if btn_settings_back.is_clicked(event):
                    app_state = "MAIN"
                elif btn_set_alarm_th.is_clicked(event):
                    app_state = "ALARM_MENU"
                elif btn_set_night_th.is_clicked(event):
                    app_state = "NIGHT_MENU"
                elif btn_set_schedule.is_clicked(event):
                    app_state = "TIME_PICKER"
                elif btn_jellyfin_menu.is_clicked(event):
                    app_state = "JELLYFIN_MENU"
                elif btn_test_alarm.is_clicked(event):
                    alarm_active = True
                    night_active = False
                    motion_detected = False
                    play_alarm_track()
                    app_state = "MAIN"

            elif app_state == "ALARM_MENU":
                if btn_alarm_back.is_clicked(event):
                    app_state = "SETTINGS"
                for key, btn in alarm_buttons:
                    if btn.is_clicked(event):
                        set_alarm_theme(key)
                        app_state = "SETTINGS"

            elif app_state == "NIGHT_MENU":
                if btn_night_back.is_clicked(event):
                    app_state = "SETTINGS"
                for key, btn in night_buttons:
                    if btn.is_clicked(event):
                        set_night_theme(key)
                        night_active = True
                        play_night_track()
                        app_state = "SETTINGS"

            elif app_state == "JELLYFIN_MENU":
                if btn_jelly_back.is_clicked(event):
                    app_state = "SETTINGS"
                elif btn_jelly_launch.is_clicked(event):
                    launch_jellyfin_client()

            elif app_state == "TIME_PICKER":
                if btn_toggle_mode.is_clicked(event):
                    picker_mode = "NIGHT" if picker_mode == "ALARM" else "ALARM"
                    btn_toggle_mode.text = f"Editing: {'Bedtime (Night)' if picker_mode == 'NIGHT' else 'Alarm Time'}"

                if picker_mode == "ALARM":
                    if btn_hour_up.is_clicked(event):
                        target_alarm_hour = (target_alarm_hour + 1) % 24
                    elif btn_hour_dn.is_clicked(event):
                        target_alarm_hour = (target_alarm_hour - 1) % 24
                    elif btn_min_up.is_clicked(event):
                        target_alarm_minute = (target_alarm_minute + 5) % 60
                    elif btn_min_dn.is_clicked(event):
                        target_alarm_minute = (target_alarm_minute - 5) % 60
                        if target_alarm_minute < 0: target_alarm_minute = 55
                else:
                    if btn_hour_up.is_clicked(event):
                        target_night_hour = (target_night_hour + 1) % 24
                    elif btn_hour_dn.is_clicked(event):
                        target_night_hour = (target_night_hour - 1) % 24
                    elif btn_min_up.is_clicked(event):
                        target_night_minute = (target_night_minute + 5) % 60
                    elif btn_min_dn.is_clicked(event):
                        target_night_minute = (target_night_minute - 5) % 60
                        if target_night_minute < 0: target_night_minute = 55

                if btn_time_save.is_clicked(event):
                    save_schedule()
                    app_state = "SETTINGS"

        # Scheduled Alarm Checks
        now = datetime.now()
        if alarm_enabled and not alarm_active and not motion_detected:
            if now.hour == target_alarm_hour and now.minute == target_alarm_minute and now.second == 0:
                alarm_active = True
                night_active = False
                play_alarm_track()

        if night_enabled and not night_active and not alarm_active and not motion_detected:
            if now.hour == target_night_hour and now.minute == target_night_minute and now.second == 0:
                if night_playlists:
                    night_active = True
                    play_night_track()

        if alarm_active and not pygame.mixer.music.get_busy():
            play_alarm_track()

        # Rendering
        screen.fill(BG_COLOR)

        if app_state == "MAIN":
            current_time = now.strftime("%H:%M:%S")

            # Big Bold Center Clock Face
            time_surface = font_xlarge.render(current_time, True, TEXT_COLOR)
            screen.blit(time_surface, (WIDTH // 2 - time_surface.get_width() // 2, 45))

            # Schedule & Theme Summary Subtitle
            schedule_str = f"Alarm: {target_alarm_hour:02d}:{target_alarm_minute:02d} | Bed: {target_night_hour:02d}:{target_night_minute:02d}"
            sched_surface = font_small.render(schedule_str, True, (200, 200, 230))
            screen.blit(sched_surface, (WIDTH // 2 - sched_surface.get_width() // 2, 115))

            if alarm_active:
                status_surface = font_med.render("ALARM SOUNDING!", True, ACCENT_COLOR)
            elif night_active:
                status_surface = font_med.render("Night Sounds Active (Sleeping...)", True, NIGHT_COLOR)
            elif motion_detected:
                status_surface = font_med.render("Motion Detected! Good morning!", True, (100, 255, 100))
            else:
                status_surface = font_med.render(f"Theme: {current_alarm_theme.capitalize()}", True, (170, 170, 200))

            screen.blit(status_surface, (WIDTH // 2 - status_surface.get_width() // 2, 155))

            # Bottom Controls
            if alarm_active or night_active or motion_detected:
                btn_settings_small.draw(screen, font_med)
                btn_stop_small.draw(screen, font_med)
            else:
                btn_settings.draw(screen, font_med)
                btn_toggle_night.draw(screen, font_med, is_selected=night_active)

        elif app_state == "SETTINGS":
            title_surface = font_med.render("Smart Clock Settings", True, TEXT_COLOR)
            screen.blit(title_surface, (WIDTH // 2 - title_surface.get_width() // 2, 10))

            btn_set_alarm_th.draw(screen, font_med)
            btn_set_night_th.draw(screen, font_med)
            btn_set_schedule.draw(screen, font_med)
            btn_jellyfin_menu.draw(screen, font_med)
            btn_test_alarm.draw(screen, font_med)
            btn_settings_back.draw(screen, font_med)

        elif app_state == "ALARM_MENU":
            title_surface = font_med.render("Select Alarm Theme", True, TEXT_COLOR)
            screen.blit(title_surface, (WIDTH // 2 - title_surface.get_width() // 2, 15))

            if not alarm_buttons:
                empty_surface = font_small.render("No theme subfolders found in alarms/!", True, ACCENT_COLOR)
                screen.blit(empty_surface, (WIDTH // 2 - empty_surface.get_width() // 2, 130))
            else:
                for key, btn in alarm_buttons:
                    btn.draw(screen, font_small, is_selected=(key == current_alarm_theme))

            btn_alarm_back.draw(screen, font_med)

        elif app_state == "NIGHT_MENU":
            title_surface = font_med.render("Select Night Sound Theme", True, TEXT_COLOR)
            screen.blit(title_surface, (WIDTH // 2 - title_surface.get_width() // 2, 15))

            if not night_buttons:
                empty_surface = font_small.render("No theme subfolders found in night/!", True, ACCENT_COLOR)
                screen.blit(empty_surface, (WIDTH // 2 - empty_surface.get_width() // 2, 130))
            else:
                for key, btn in night_buttons:
                    btn.draw(screen, font_small, is_selected=(key == current_night_theme))

            btn_night_back.draw(screen, font_med)

        elif app_state == "JELLYFIN_MENU":
            title_surface = font_med.render("Jellyfin TV Streaming Mode", True, TEXT_COLOR)
            screen.blit(title_surface, (WIDTH // 2 - title_surface.get_width() // 2, 15))

            info_surface = font_small.render(f"Target Server: {JELLYFIN_SERVER_URL}", True, (180, 180, 220))
            screen.blit(info_surface, (WIDTH // 2 - info_surface.get_width() // 2, 80))

            btn_jelly_launch.draw(screen, font_med)
            btn_jelly_back.draw(screen, font_med)

        elif app_state == "TIME_PICKER":
            title_surface = font_med.render("Schedule Settings", True, TEXT_COLOR)
            screen.blit(title_surface, (WIDTH // 2 - title_surface.get_width() // 2, 15))

            btn_toggle_mode.draw(screen, font_med)

            active_hour = target_alarm_hour if picker_mode == "ALARM" else target_night_hour
            active_min = target_alarm_minute if picker_mode == "ALARM" else target_night_minute

            hour_surf = font_large.render(f"{active_hour:02d}", True, TEXT_COLOR)
            colon_surf = font_large.render(":", True, TEXT_COLOR)
            min_surf = font_large.render(f"{active_min:02d}", True, TEXT_COLOR)

            screen.blit(hour_surf, (120 - hour_surf.get_width() // 2, 155))
            screen.blit(colon_surf, (WIDTH // 2 - colon_surf.get_width() // 2, 150))
            screen.blit(min_surf, (360 - min_surf.get_width() // 2, 155))

            btn_hour_up.draw(screen, font_large)
            btn_hour_dn.draw(screen, font_large)
            btn_min_up.draw(screen, font_large)
            btn_min_dn.draw(screen, font_large)
            btn_time_save.draw(screen, font_med)

        pygame.display.flip()
        clock.tick(30)

except Exception as e:
    import traceback
    print("\n--- CRITICAL ERROR ON STARTUP / RUNTIME ---")
    traceback.print_exc()

pygame.quit()
sys.exit()
