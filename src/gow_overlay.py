import os
import sys
import json
import time
import queue
import ctypes
from ctypes import wintypes
import threading
import subprocess
import webbrowser
import io
import re
import socket
import hmac
import math
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from datetime import datetime

import requests
import websocket
import win32gui
import win32con
import win32api
import obsws_python as obs

import pystray
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageSequence

try:
    import qrcode
except ImportError:
    qrcode = None



# =========================================================
# CONSTANTES
# =========================================================

CLIENT_ID = "bt2yx4ahm7tx6ty4a6m1x4ido1y71d"

OBS_HOST = "127.0.0.1"
OBS_PORT = 4455
OBS_PASSWORD = ""

GAME_EXE = "GoW.exe"

VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A

WDA_EXCLUDEFROMCAPTURE = 0x00000011

REQUIRED_CHAT_SCOPE = "user:read:chat"
REQUIRED_REWARD_SCOPE = "channel:read:redemptions"
REQUIRED_SUB_SCOPE = "channel:read:subscriptions"
REQUIRED_BITS_SCOPE = "bits:read"

REQUIRED_TWITCH_SCOPES = (
    REQUIRED_CHAT_SCOPE,
    REQUIRED_REWARD_SCOPE,
    REQUIRED_SUB_SCOPE,
    REQUIRED_BITS_SCOPE,
)


# =========================================================
# UMA INSTÂNCIA SÓ
# =========================================================

mutex = ctypes.windll.kernel32.CreateMutexW(
    None,
    False,
    "GoW_Twitch_Overlay_plxq_SINGLE_INSTANCE"
)

if ctypes.windll.kernel32.GetLastError() == 183:
    ctypes.windll.user32.MessageBoxW(
        0,
        "O GoW Overlay já está aberto.",
        "GoW Overlay",
        0x40
    )
    sys.exit()


# =========================================================
# PASTAS
# =========================================================

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resource_path(name):
    """Localiza arquivos incluídos pelo PyInstaller ou ao lado do .py."""
    bundle_dir = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(bundle_dir, name)


if getattr(sys, "frozen", False):
    ICON_FILE = resource_path("GoW_Overlay.ico")
    SPLASH_IMAGE_FILE = resource_path("GoW_Overlay.png")
else:
    PROJECT_DIR = os.path.dirname(BASE_DIR)
    ICON_FILE = os.path.join(PROJECT_DIR, "assets", "GoW_Overlay.ico")
    SPLASH_IMAGE_FILE = os.path.join(PROJECT_DIR, "assets", "GoW_Overlay.png")

# Dados pessoais ficam numa pasta gravável de cada usuário. Isso permite que o
# EXE rode de Program Files, da Área de Trabalho ou de qualquer outra pasta.
DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "GoW Overlay"
)
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
TOKEN_FILE = os.path.join(DATA_DIR, "tokens.txt")

# Migra automaticamente os arquivos das versões antigas, se existirem.
for old_name, new_path in (
    ("config.json", CONFIG_FILE),
    ("tokens.txt", TOKEN_FILE),
):
    old_path = os.path.join(BASE_DIR, old_name)
    if old_path != new_path and os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            with open(old_path, "rb") as source, open(new_path, "wb") as target:
                target.write(source.read())
        except OSError:
            pass


# =========================================================
# TELA DE CARREGAMENTO
# =========================================================

splash = tk.Tk()
splash.title("GoW Overlay")
splash.overrideredirect(True)
splash.configure(bg="#121212")
splash.attributes("-topmost", True)

try:
    splash.iconbitmap(ICON_FILE)
except Exception:
    pass

splash_width = 430
splash_height = 270
splash_x = (splash.winfo_screenwidth() - splash_width) // 2
splash_y = (splash.winfo_screenheight() - splash_height) // 2
splash.geometry(
    f"{splash_width}x{splash_height}+{splash_x}+{splash_y}"
)
splash.withdraw()

try:
    splash_icon_image = Image.open(SPLASH_IMAGE_FILE).convert("RGBA")
    splash_icon_image.thumbnail((118, 118), Image.Resampling.LANCZOS)
    splash_icon_photo = ImageTk.PhotoImage(splash_icon_image)
    tk.Label(
        splash,
        image=splash_icon_photo,
        bg="#121212",
        bd=0
    ).pack(pady=(24, 8))
except Exception:
    splash_icon_photo = None

tk.Label(
    splash,
    text="GoW Overlay",
    bg="#121212",
    fg="white",
    font=("Segoe UI", 18, "bold")
).pack()

splash_status_label = tk.Label(
    splash,
    text="Iniciando...",
    bg="#121212",
    fg="#b8b8c0",
    font=("Segoe UI", 9)
)
splash_status_label.pack(pady=(5, 10))

splash_style = ttk.Style(splash)
splash_style.theme_use("clam")
splash_style.configure(
    "GoW.Horizontal.TProgressbar",
    troughcolor="#29292f",
    background="#b62828",
    bordercolor="#29292f",
    lightcolor="#d84141",
    darkcolor="#8d1d1d"
)

splash_progress = ttk.Progressbar(
    splash,
    mode="determinate",
    maximum=100,
    value=0,
    length=330,
    style="GoW.Horizontal.TProgressbar"
)
splash_progress.pack()
splash.update()


def start_splash_drag(event):
    splash._drag_x = event.x_root - splash.winfo_x()
    splash._drag_y = event.y_root - splash.winfo_y()


def move_splash(event):
    x = event.x_root - getattr(splash, "_drag_x", 0)
    y = event.y_root - getattr(splash, "_drag_y", 0)
    splash.geometry(f"+{x}+{y}")


def bind_splash_drag(widget):
    widget.bind("<ButtonPress-1>", start_splash_drag)
    widget.bind("<B1-Motion>", move_splash)
    for child in widget.winfo_children():
        bind_splash_drag(child)


bind_splash_drag(splash)


def splash_status(text):
    try:
        splash_status_label.configure(text=text)
        splash.update()
    except Exception:
        pass


def run_while_splash_moves(callback, ceiling=94.0):
    """Executa a etapa real em paralelo enquanto a barra avança suavemente."""
    result_box = {}
    error_box = {}

    def worker():
        try:
            result_box["value"] = callback()
        except BaseException as error:
            error_box["error"] = error

    task = threading.Thread(target=worker, daemon=True)
    task.start()

    while task.is_alive():
        current = float(splash_progress["value"])
        remaining = max(0.0, ceiling - current)
        if remaining > 0.01:
            # Aproxima-se lentamente do teto da etapa sem alcançá-lo antes dela.
            splash_progress["value"] = min(
                ceiling,
                current + max(0.01, remaining * 0.0018)
            )
        splash.update_idletasks()
        splash.update()
        time.sleep(0.02)

    if "error" in error_box:
        raise error_box["error"]
    return result_box.get("value")


# =========================================================
# CONFIG
# =========================================================

REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080
SCALABLE_SETTING_KEYS = (
    "font_size",
    "outline_size",
    "message_gap",
    "text_width",
    "overlay_width",
    "overlay_height",
    "position_x_offset",
    "position_y_offset"
)


def system_monitor_rects():
    try:
        rects = [
            tuple(win32api.GetMonitorInfo(handle)["Monitor"])
            for handle, _, _ in win32api.EnumDisplayMonitors(None, None)
        ]
        return sorted(rects, key=lambda rect: (rect[0], rect[1]))
    except Exception:
        return [(0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT)]


def monitor_scale(monitor_number, rects=None):
    rects = rects or system_monitor_rects()
    index = min(max(1, int(monitor_number)), len(rects)) - 1
    left, top, right, bottom = rects[index]
    width_scale = (right - left) / REFERENCE_WIDTH
    height_scale = (bottom - top) / REFERENCE_HEIGHT
    return max(0.25, min(width_scale, height_scale))

DEFAULT_CONFIG = {
    "config_version": 67,
    "settings_scale": 1.0,
    "channel": "",
    "obs_source": "DP",
    "max_messages": 10,
    "text_opacity": 0.55,
    "font": "Arial",
    "font_size": 16,
    "outline_size": 2,
    "message_gap": 6,
    "text_width": 450,
    "overlay_width": 500,
    "overlay_height": 850,
    "position_x_offset": 0,
    "position_y_offset": 0,
    "overlay_monitor": 1,
    "control_dp": True,
    "show_chat": True,
    "animate_emotes": True,
    "third_party_emotes": True,
    "log_to_file": True,
    "show_hint": True,
    "f9_initial_time": 2,
    "f9_repeat_time": 1.5,
    "always_show_overlay": False,
    "auto_delete_messages": False,
    "auto_delete_seconds": 30,
    "show_startup_info": True,
    "remote_port": 8765,
    "remote_token": "",
    "always_on_top": True
}


def load_config():
    cfg = DEFAULT_CONFIG.copy()

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Migra o antigo padrão de 3 s sem alterar valores personalizados.
                if (
                    int(loaded.get("config_version", 0)) < 55
                    and float(loaded.get("f9_initial_time", 3.0)) == 3.0
                ):
                    loaded["f9_initial_time"] = 2.0
                cfg.update(loaded)

                # Converte automaticamente da escala em que os valores foram
                # salvos para a resolução atual do monitor escolhido.
                current_scale = monitor_scale(cfg.get("overlay_monitor", 1))
                if "settings_scale" in loaded:
                    saved_scale = max(0.25, float(loaded["settings_scale"]))
                elif int(loaded.get("config_version", 0)) < 57:
                    saved_scale = 1.0
                else:
                    # Migração das versões 57/58: identifica se os números já
                    # estavam proporcionais ou ainda eram os valores de 1080p.
                    samples = []
                    for key in (
                        "font_size", "outline_size", "message_gap",
                        "text_width", "overlay_width", "overlay_height"
                    ):
                        default_value = float(DEFAULT_CONFIG[key])
                        if default_value:
                            samples.append(float(cfg[key]) / default_value)
                    samples.sort()
                    estimated_scale = samples[len(samples) // 2] if samples else 1.0
                    saved_scale = (
                        current_scale
                        if abs(estimated_scale - current_scale) < abs(estimated_scale - 1.0)
                        else 1.0
                    )

                ratio = current_scale / saved_scale if saved_scale else 1.0
                if abs(ratio - 1.0) > 0.001:
                    for key in SCALABLE_SETTING_KEYS:
                        cfg[key] = int(round(float(cfg[key]) * ratio))
                cfg["settings_scale"] = current_scale
        else:
            # Primeira execução: os próprios padrões de 1080p já nascem
            # convertidos para a resolução do monitor inicial.
            current_scale = monitor_scale(cfg.get("overlay_monitor", 1))
            for key in SCALABLE_SETTING_KEYS:
                cfg[key] = int(round(float(cfg[key]) * current_scale))
            cfg["settings_scale"] = current_scale
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Erro no config.json:\n\n{e}",
            "GoW Overlay",
            0x10
        )

    return cfg


splash_status("Carregando configurações...")
config = load_config()

CHANNEL_LOGIN = str(config["channel"])
SOURCE_NAME = str(config["obs_source"])

MAX_MESSAGES = int(config["max_messages"])
TEXT_OPACITY = float(config["text_opacity"])

FONT_NAME = str(config["font"])
FONT_SIZE = int(config["font_size"])
OUTLINE_SIZE = int(config["outline_size"])

MESSAGE_GAP = int(config["message_gap"])
TEXT_WIDTH = int(config["text_width"])

OVERLAY_WIDTH = int(config["overlay_width"])
OVERLAY_HEIGHT = int(config["overlay_height"])

POSITION_X_OFFSET = int(config["position_x_offset"])
POSITION_Y_OFFSET = int(config["position_y_offset"])
OVERLAY_MONITOR = max(1, int(config.get("overlay_monitor", 1)))
CONTROL_DP = bool(config.get("control_dp", True))
SHOW_CHAT = bool(config.get("show_chat", True))
ANIMATE_EMOTES = bool(config.get("animate_emotes", True))
THIRD_PARTY_EMOTES = bool(config.get("third_party_emotes", True))
LOG_TO_FILE = bool(config.get("log_to_file", True))
SHOW_HINT = bool(config.get("show_hint", True))
CURRENT_SETTINGS_SCALE = float(
    config.get("settings_scale", monitor_scale(OVERLAY_MONITOR))
)

# O Resetar respeita o monitor e a escala usados na abertura do aplicativo.
STARTUP_OVERLAY_MONITOR = OVERLAY_MONITOR
STARTUP_MONITOR_SCALE = monitor_scale(STARTUP_OVERLAY_MONITOR)

F9_INITIAL_TIME = float(config["f9_initial_time"])
F9_REPEAT_TIME = float(config["f9_repeat_time"])
ALWAYS_SHOW_OVERLAY = bool(config.get("always_show_overlay", False))
AUTO_DELETE_MESSAGES = bool(config.get("auto_delete_messages", False))
AUTO_DELETE_SECONDS = max(1, int(config.get("auto_delete_seconds", 30)))
SHOW_STARTUP_INFO = bool(config.get("show_startup_info", True))
# Mantém as janelas do app (Live Control, Configurações, Suporte e Remoto)
# sempre por cima das outras. O overlay do chat não é afetado.
ALWAYS_ON_TOP = bool(config.get("always_on_top", True))

# Porta preferida do controle remoto (celular). Se estiver ocupada por outro
# programa, o aplicativo usa outra porta livre automaticamente.
try:
    REMOTE_PORT_PREFERRED = int(config.get("remote_port", 8765))
    if not 1024 <= REMOTE_PORT_PREFERRED <= 65535:
        raise ValueError
except (TypeError, ValueError):
    REMOTE_PORT_PREFERRED = 8765

# Código secreto do link do celular. Fica salvo para o link/QR não mudar a
# cada ativação. "Novo link" na janela Remoto gera outro.
REMOTE_TOKEN_SAVED = str(config.get("remote_token", "") or "")
if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", REMOTE_TOKEN_SAVED):
    REMOTE_TOKEN_SAVED = ""


def save_config():
    data = {
        "config_version": 67,
        "settings_scale": CURRENT_SETTINGS_SCALE,
        "channel": CHANNEL_LOGIN,
        "obs_source": SOURCE_NAME,
        "max_messages": MAX_MESSAGES,
        "text_opacity": TEXT_OPACITY,
        "font": FONT_NAME,
        "font_size": FONT_SIZE,
        "outline_size": OUTLINE_SIZE,
        "message_gap": MESSAGE_GAP,
        "text_width": TEXT_WIDTH,
        "overlay_width": OVERLAY_WIDTH,
        "overlay_height": OVERLAY_HEIGHT,
        "position_x_offset": POSITION_X_OFFSET,
        "position_y_offset": POSITION_Y_OFFSET,
        "overlay_monitor": OVERLAY_MONITOR,
        "control_dp": CONTROL_DP,
        "show_chat": SHOW_CHAT,
        "animate_emotes": ANIMATE_EMOTES,
        "third_party_emotes": THIRD_PARTY_EMOTES,
        "log_to_file": LOG_TO_FILE,
        "show_hint": SHOW_HINT,
        "f9_initial_time": F9_INITIAL_TIME,
        "f9_repeat_time": F9_REPEAT_TIME,
        "always_show_overlay": ALWAYS_SHOW_OVERLAY,
        "auto_delete_messages": AUTO_DELETE_MESSAGES,
        "auto_delete_seconds": AUTO_DELETE_SECONDS,
        "show_startup_info": SHOW_STARTUP_INFO,
        "remote_port": REMOTE_PORT_PREFERRED,
        "remote_token": REMOTE_TOKEN_SAVED,
        "always_on_top": ALWAYS_ON_TOP
    }

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def show_startup_information():
    """Explica o funcionamento e permite ocultar o aviso futuramente."""
    global SHOW_STARTUP_INFO

    if not SHOW_STARTUP_INFO:
        return

    info_window = tk.Toplevel(splash)
    info_window.overrideredirect(True)
    info_window.configure(bg="#121212")
    info_window.resizable(False, False)
    info_window.attributes("-topmost", True)

    try:
        info_window.iconbitmap(ICON_FILE)
    except Exception:
        pass

    width = 590
    height = 620
    x = (info_window.winfo_screenwidth() - width) // 2
    y = (info_window.winfo_screenheight() - height) // 2
    info_window.geometry(f"{width}x{height}+{x}+{y}")

    tk.Label(
        info_window,
        text="Antes de começar",
        bg="#121212",
        fg="white",
        font=("Segoe UI", 18, "bold")
    ).pack(pady=(22, 12))

    tk.Label(
        info_window,
        text=(
            "O GoW Overlay nasceu para as speedruns de God of War, evitando "
            "o hook da Captura de Jogo do OBS que pode causar crashes, especialmente "
            "em placas de vídeo AMD. Depois, ele foi ampliado para permitir a leitura "
            "do chat por quem possui apenas um monitor ou usa telas menores."
        ),
        justify="left",
        anchor="nw",
        wraplength=530,
        bg="#121212",
        fg="#dedee4",
        font=("Segoe UI", 10),
        padx=8
    ).pack(fill="x", padx=22, pady=(0, 20))

    tk.Label(
        info_window,
        text="Configuração no OBS",
        bg="#121212",
        fg="#f4f4f6",
        font=("Segoe UI", 11, "bold"),
        anchor="w"
    ).pack(fill="x", padx=30)

    tk.Label(
        info_window,
        text=(
            "• Para o controle automático de vídeo, a fonte captura de tela deve se chamar DP.\n"
            "  Você pode desligar esse controle nas Configurações e usar apenas o chat.\n"
            "\n"
            "• Som: use Captura de Áudio do Aplicativo."
        ),
        justify="left",
        anchor="w",
        bg="#121212",
        fg="#dedee4",
        font=("Segoe UI", 10)
    ).pack(fill="x", padx=38, pady=(9, 22))

    tk.Label(
        info_window,
        text="Twitch",
        bg="#121212",
        fg="#f4f4f6",
        font=("Segoe UI", 11, "bold"),
        anchor="w"
    ).pack(fill="x", padx=30)

    tk.Label(
        info_window,
        text=(
            "Quando necessário, a Twitch abrirá no navegador para autorizar "
            "apenas a leitura do chat, resgates de pontos, inscrições e "
            "Cheers/Bits. O "
            "overlay não acessa sua senha, e os tokens ficam salvos somente "
            "neste computador."
        ),
        justify="left",
        anchor="nw",
        wraplength=510,
        bg="#121212",
        fg="#dedee4",
        font=("Segoe UI", 10)
    ).pack(fill="x", padx=38, pady=(9, 16))

    hide_again_var = tk.BooleanVar(value=False)

    hide_holder = tk.Frame(info_window, bg="#121212", cursor="hand2")
    hide_holder.pack(anchor="w", padx=30, pady=(14, 12))

    def render_info_circle(enabled):
        scale = 6
        size = 24
        image = Image.new("RGBA", (size * scale, size * scale), "#121212")
        draw = ImageDraw.Draw(image)
        # Caixa perfeitamente quadrada e com margem igual em todos os lados.
        bounds = (2 * scale, 2 * scale, (size - 2) * scale - 1, (size - 2) * scale - 1)
        if enabled:
            draw.ellipse(bounds, fill="#b62828", outline="#d44a4a", width=scale)
            draw.line(
                [(6 * scale, 12 * scale), (10 * scale, 16 * scale), (18 * scale, 8 * scale)],
                fill="#ffffff", width=2 * scale, joint="curve"
            )
        else:
            draw.ellipse(bounds, fill="#242426", outline="#606067", width=scale)
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    hide_off_image = render_info_circle(False)
    hide_on_image = render_info_circle(True)
    hide_dot = tk.Label(hide_holder, bg="#121212", bd=0, cursor="hand2")
    hide_dot.pack(side="left", padx=(0, 8))
    hide_label = tk.Label(
        hide_holder,
        text="Não mostrar esta mensagem novamente",
        bg="#121212",
        fg="white",
        font=("Segoe UI", 10),
        cursor="hand2"
    )
    hide_label.pack(side="left")

    def redraw_hide_circle(*_):
        hide_dot.configure(
            image=hide_on_image if hide_again_var.get() else hide_off_image
        )

    def toggle_hide_again(event=None):
        hide_again_var.set(not hide_again_var.get())

    for widget in (hide_holder, hide_dot, hide_label):
        widget._no_window_drag = True
        widget.bind("<Button-1>", toggle_hide_again)
    hide_holder._circle_images = (hide_off_image, hide_on_image)
    hide_again_var.trace_add("write", redraw_hide_circle)
    redraw_hide_circle()

    def continue_startup():
        global SHOW_STARTUP_INFO

        if hide_again_var.get():
            SHOW_STARTUP_INFO = False
            save_config()

        info_window.grab_release()
        info_window.destroy()

    def info_rounded_rect(canvas_obj, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius, y1, x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2,
            x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius, x1, y1
        ]
        return canvas_obj.create_polygon(
            points, smooth=True, splinesteps=36, **kwargs
        )

    continue_width = 150
    continue_height = 44
    continue_canvas = tk.Canvas(
        info_window,
        width=continue_width,
        height=continue_height,
        bg="#121212",
        highlightthickness=0,
        bd=0,
        cursor="hand2"
    )
    continue_canvas.pack(pady=(0, 20))
    continue_canvas._no_window_drag = True

    def draw_continue_button(color="#a52424", outline="#cf4545"):
        continue_canvas.delete("button_bg")
        info_rounded_rect(
            continue_canvas,
            2, 2, continue_width - 2, continue_height - 2, 21,
            fill=color,
            outline=outline,
            width=1,
            tags="button_bg"
        )
        continue_canvas.tag_lower("button_bg")

    draw_continue_button()
    continue_canvas.create_text(
        continue_width // 2,
        continue_height // 2,
        text="Continuar",
        fill="white",
        font=("Segoe UI", 10, "bold")
    )
    continue_canvas.bind("<Button-1>", lambda event: continue_startup())
    continue_canvas.bind(
        "<Enter>",
        lambda event: draw_continue_button("#bd2d2d", "#e35a5a")
    )
    continue_canvas.bind(
        "<Leave>",
        lambda event: draw_continue_button()
    )

    # A mensagem pode ser movida pelo fundo ou pelos textos. Mantém o botão e
    # a opção "não mostrar" livres para clique normal.
    info_drag = {"x": 0, "y": 0}

    def start_info_drag(event):
        info_drag["x"] = event.x_root - info_window.winfo_x()
        info_drag["y"] = event.y_root - info_window.winfo_y()

    def move_info_drag(event):
        new_x = event.x_root - info_drag["x"]
        new_y = event.y_root - info_drag["y"]
        info_window.geometry(f"+{new_x}+{new_y}")

    def bind_info_drag(widget):
        if getattr(widget, "_no_window_drag", False):
            return
        widget.bind("<ButtonPress-1>", start_info_drag)
        widget.bind("<B1-Motion>", move_info_drag)
        for child in widget.winfo_children():
            bind_info_drag(child)

    bind_info_drag(info_window)

    # Cartão obrigatório: sem barra de título, sem X, Escape ou Alt+F4.
    info_window.protocol("WM_DELETE_WINDOW", lambda: None)
    info_window.bind("<Escape>", lambda event: "break")
    info_window.bind("<Alt-F4>", lambda event: "break")
    info_window.grab_set()
    info_window.focus_force()

    # Recorte arredondado para parecer um cartão/bubble, não uma página.
    try:
        info_window.update_idletasks()
        info_internal_hwnd = info_window.winfo_id()
        info_parent_hwnd = win32gui.GetParent(info_internal_hwnd)
        info_hwnd = info_parent_hwnd if info_parent_hwnd else info_internal_hwnd
        info_region = ctypes.windll.gdi32.CreateRoundRectRgn(
            0, 0, width + 1, height + 1, 30, 30
        )
        ctypes.windll.user32.SetWindowRgn(
            info_hwnd, info_region, True
        )
    except Exception:
        pass

    splash.wait_window(info_window)


show_startup_information()

# A barra sempre começa vazia; a primeira metade representa a preparação básica.
splash_status_label.configure(text="Carregando...")
splash_progress["value"] = 0
splash.update_idletasks()

# Recorta o próprio carregamento como uma grande bolha.
try:
    splash_internal_hwnd = splash.winfo_id()
    splash_parent_hwnd = win32gui.GetParent(splash_internal_hwnd)
    splash_hwnd = splash_parent_hwnd if splash_parent_hwnd else splash_internal_hwnd
    splash_region = ctypes.windll.gdi32.CreateRoundRectRgn(
        0, 0,
        splash_width + 1, splash_height + 1,
        42, 42
    )
    ctypes.windll.user32.SetWindowRgn(
        splash_hwnd, splash_region, True
    )
except Exception:
    pass

splash.deiconify()
splash.lift()
splash.focus_force()
splash.update()

# Exibe o loading imediatamente em 0% e preenche a preparação inicial até 50%.
initial_duration = 0.35
initial_frames = 24
for frame in range(1, initial_frames + 1):
    t = frame / initial_frames
    eased = t * t * (3.0 - 2.0 * t)
    splash_progress["value"] = 50.0 * eased
    splash.update_idletasks()
    splash.update()
    time.sleep(initial_duration / initial_frames)


# =========================================================
# TOKENS
# =========================================================

def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        return {}

    tokens = {}

    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if "=" in line:
                key, value = line.split("=", 1)
                tokens[key.strip()] = value.strip()

    return tokens


def save_tokens(access_token, refresh_token):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(f"access_token={access_token}\n")
        f.write(f"refresh_token={refresh_token}\n")


tokens = load_tokens()
ACCESS_TOKEN = tokens.get("access_token", "")
REFRESH_TOKEN = tokens.get("refresh_token", "")


def validate_token(token):
    try:
        r = requests.get(
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {token}"},
            timeout=10
        )

        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    return None


def refresh_token():
    global ACCESS_TOKEN, REFRESH_TOKEN

    try:
        r = requests.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN,
                "client_id": CLIENT_ID
            },
            timeout=10
        )

        if r.status_code != 200:
            return False

        data = r.json()

        ACCESS_TOKEN = data["access_token"]
        REFRESH_TOKEN = data.get("refresh_token", REFRESH_TOKEN)

        save_tokens(ACCESS_TOKEN, REFRESH_TOKEN)
        return True
    except Exception:
        return False


def device_login():
    """Login universal da Twitch sem exigir tokens.txt nem client secret."""
    global ACCESS_TOKEN, REFRESH_TOKEN

    scopes = " ".join(REQUIRED_TWITCH_SCOPES)

    try:
        response = requests.post(
            "https://id.twitch.tv/oauth2/device",
            data={"client_id": CLIENT_ID, "scopes": scopes},
            timeout=15
        )
        response.raise_for_status()
        device = response.json()

        user_code = device["user_code"]
        verification_uri = device["verification_uri"]
        device_code = device["device_code"]
        interval = max(1, int(device.get("interval", 5)))
        deadline = time.time() + int(device.get("expires_in", 600))

        # Copia o código para facilitar e abre a página oficial da Twitch.
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Set-Clipboard", user_code],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        except Exception:
            pass

        webbrowser.open(verification_uri)

        # A caixa pertence ao loading: fica sempre acima dele e não se perde
        # atrás da janela enquanto a pessoa volta do navegador.
        try:
            win32gui.SetForegroundWindow(splash_hwnd)
        except Exception:
            pass

        ctypes.windll.user32.MessageBoxW(
            splash_hwnd,
            f"Autorize o GoW Overlay na Twitch.\n\n"
            f"Código: {user_code}\n\n"
            "O código já foi copiado. Após autorizar no navegador, clique OK.",
            "Entrar com Twitch",
            0x1040
        )

        while time.time() < deadline:
            token_response = requests.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": CLIENT_ID,
                    "scopes": scopes,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                },
                timeout=15
            )

            if token_response.status_code == 200:
                data = token_response.json()
                ACCESS_TOKEN = data["access_token"]
                REFRESH_TOKEN = data.get("refresh_token", "")
                save_tokens(ACCESS_TOKEN, REFRESH_TOKEN)
                return True

            try:
                error_name = token_response.json().get("message", "").lower()
            except Exception:
                error_name = ""

            if "slow_down" in error_name:
                interval += 1
            elif not any(x in error_name for x in ("authorization_pending", "pending")):
                return False

            time.sleep(interval)

    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Não foi possível abrir o login da Twitch.\n\n{e}",
            "GoW Overlay",
            0x10
        )

    return False


splash_status("Conectando à Twitch...")
validation = (
    run_while_splash_moves(lambda: validate_token(ACCESS_TOKEN), 56)
    if ACCESS_TOKEN else None
)


def token_has_required_scopes(validation_data):
    if not validation_data:
        return False

    granted_scopes = set(validation_data.get("scopes", []))
    return set(REQUIRED_TWITCH_SCOPES).issubset(granted_scopes)

# Tokens pertencem ao Client ID que os criou. Ao atualizar o aplicativo da
# Twitch, ignora automaticamente tokens antigos e solicita uma nova autorização.
if validation is not None and validation.get("client_id") != CLIENT_ID:
    validation = None
    ACCESS_TOKEN = ""
    REFRESH_TOKEN = ""

# Novas versões podem solicitar recursos adicionais. Um refresh token não
# consegue ampliar permissões já concedidas, então o aplicativo abre o fluxo
# oficial de autorização novamente quando faltar algum scope obrigatório.
if validation is not None and not token_has_required_scopes(validation):
    splash_status("Atualizando permissões da Twitch...")
    validation = None
    ACCESS_TOKEN = ""
    REFRESH_TOKEN = ""

if validation is None:
    refreshed = bool(REFRESH_TOKEN) and run_while_splash_moves(refresh_token, 61)

    if refreshed:
        validation = run_while_splash_moves(
            lambda: validate_token(ACCESS_TOKEN),
            65
        )

        if validation is not None and not token_has_required_scopes(validation):
            validation = None
            ACCESS_TOKEN = ""
            REFRESH_TOKEN = ""

    if validation is None:
        splash_status("Aguardando autorização da Twitch...")
        logged_in = run_while_splash_moves(device_login, 82)
        if logged_in:
            validation = run_while_splash_moves(
                lambda: validate_token(ACCESS_TOKEN),
                85
            )

            if not token_has_required_scopes(validation):
                validation = None

    if validation is None:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Não foi possível autenticar na Twitch.",
            "GoW Overlay",
            0x10
        )
        sys.exit()

USER_ID = validation["user_id"]
TOKEN_SCOPES = set(validation.get("scopes", []))

# Cada pessoa usa automaticamente o próprio canal autorizado.
CHANNEL_LOGIN = validation.get("login") or CHANNEL_LOGIN
config["channel"] = CHANNEL_LOGIN
save_config()


def twitch_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Client-Id": CLIENT_ID,
        "Content-Type": "application/json"
    }


# =========================================================
# CANAL
# =========================================================

splash_status("Localizando seu canal...")

try:
    r = run_while_splash_moves(
        lambda: requests.get(
            "https://api.twitch.tv/helix/users",
            params={"login": CHANNEL_LOGIN},
            headers=twitch_headers(),
            timeout=10
        ),
        90
    )

    channel_data = r.json()
    BROADCASTER_ID = channel_data["data"][0]["id"]

except Exception:
    ctypes.windll.user32.MessageBoxW(
        0,
        "Não consegui localizar seu canal na Twitch.",
        "GoW Overlay",
        0x10
    )
    sys.exit()


# =========================================================
# ESTADO AO VIVO
# =========================================================

state = {
    "gow_focus": False,
    "dp": False,
    "twitch": False,
    "chat": False,
    "rewards": False,
    "subs": False,
    "raids": False,
    "bits": False,

    "last_message": "-",
    "last_reward": "-",
    "last_sub": "-",
    "last_raid": "-",
    "last_bits": "-",

    "chat_count": 0,
    "reward_count": 0,
    "sub_count": 0,
    "raid_count": 0,
    "bits_count": 0
}

ui_queue = queue.Queue()


def queue_ui(kind, value=None):
    ui_queue.put((kind, value))


LOG_DIR = os.path.join(DATA_DIR, "Logs")
LOG_FILE_PREFIX = "overlay_"
LOG_FILE_SUFFIX = ".log"
LOG_MAX_FILES = 10
LOG_MAX_BYTES = 20_000_000  # trava de segurança por sessão

# Um arquivo por uso do aplicativo, criado só quando a primeira linha é gravada.
LOG_FILE = os.path.join(
    LOG_DIR,
    f"{LOG_FILE_PREFIX}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    f"{LOG_FILE_SUFFIX}"
)
_log_file_ready = False
_log_file_full = False


def _prune_old_logs():
    """Mantém no máximo LOG_MAX_FILES arquivos, apagando os mais antigos."""
    try:
        names = sorted(
            name for name in os.listdir(LOG_DIR)
            if name.startswith(LOG_FILE_PREFIX)
            and name.endswith(LOG_FILE_SUFFIX)
            and os.path.join(LOG_DIR, name) != LOG_FILE
        )
        # O arquivo desta sessão também conta no limite.
        excess = len(names) - (LOG_MAX_FILES - 1)
        for name in names[:max(0, excess)]:
            try:
                os.remove(os.path.join(LOG_DIR, name))
            except OSError:
                pass
    except OSError:
        pass


def _write_log_file(line):
    """Grava o log em disco para ele sobreviver ao fechamento do app."""
    global _log_file_ready, _log_file_full

    if not LOG_TO_FILE or _log_file_full:
        return

    try:
        if not _log_file_ready:
            os.makedirs(LOG_DIR, exist_ok=True)
            _prune_old_logs()
            _log_file_ready = True

        if (
            os.path.exists(LOG_FILE)
            and os.path.getsize(LOG_FILE) > LOG_MAX_BYTES
        ):
            _log_file_full = True
            line = "Log desta sessão atingiu o tamanho máximo; parando de gravar"

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def log(text):
    now = datetime.now()
    stamp = now.strftime("%H:%M:%S")
    queue_ui("log", f"{stamp}  {text}")
    _write_log_file(f"{now.strftime('%Y-%m-%d %H:%M:%S')}  {text}")


# =========================================================
# OBS
# =========================================================

splash_status("Detectando OBS...")

client = None
OBS_CONNECTED = False
OBS_LOCK = threading.Lock()


def connect_obs():
    """Tenta conectar ao OBS sem impedir o funcionamento do overlay."""
    global client, OBS_CONNECTED, last_active

    try:
        # Não instancia obsws-python enquanto a porta estiver fechada, pois a
        # biblioteca imprime um traceback de timeout mesmo quando o erro é
        # tratado pelo aplicativo.
        with socket.create_connection(
            (OBS_HOST, OBS_PORT),
            timeout=0.25
        ):
            pass

        new_client = obs.ReqClient(
            host=OBS_HOST,
            port=OBS_PORT,
            password=OBS_PASSWORD,
            timeout=2
        )

        # Uma chamada real confirma que o WebSocket está respondendo.
        new_client.get_version()

        with OBS_LOCK:
            was_connected = OBS_CONNECTED
            client = new_client
            OBS_CONNECTED = True

        # Força a próxima verificação a reaplicar o estado do DP.
        last_active = None

        if not was_connected:
            log("OBS WebSocket conectado")

        queue_ui("status")
        return True

    except Exception:
        with OBS_LOCK:
            client = None
            OBS_CONNECTED = False

        state["dp"] = False
        queue_ui("status")
        return False


def obs_connection_worker():
    """Reconecta automaticamente quando o OBS for aberto posteriormente."""
    global client, OBS_CONNECTED

    while True:
        if not CONTROL_DP:
            state["dp"] = False
            queue_ui("status")
            time.sleep(1)
            continue

        if not OBS_CONNECTED:
            connect_obs()
        else:
            try:
                with OBS_LOCK:
                    current_client = client

                if current_client is None:
                    raise RuntimeError("OBS sem cliente")

                current_client.get_version()
            except Exception:
                with OBS_LOCK:
                    client = None
                    OBS_CONNECTED = False

                state["dp"] = False
                queue_ui("status")
                log("OBS fechado; overlay continua funcionando")

        time.sleep(5)


# A detecção do OBS acontece somente no worker e nunca segura o loading.
threading.Thread(target=obs_connection_worker, daemon=True).start()


def set_dp(enabled, force=False):
    global client, OBS_CONNECTED

    try:
        if not CONTROL_DP and not force:
            state["dp"] = False
            queue_ui("status")
            return False

        with OBS_LOCK:
            current_client = client

        if not OBS_CONNECTED or current_client is None:
            state["dp"] = False
            queue_ui("status")
            return False

        scene = current_client.get_current_program_scene()
        items = current_client.get_scene_item_list(scene.scene_name)

        found = False

        for item in items.scene_items:
            if item["sourceName"] == SOURCE_NAME:
                current_client.set_scene_item_enabled(
                    scene.scene_name,
                    item["sceneItemId"],
                    enabled
                )
                found = True

        state["dp"] = bool(enabled and found)
        queue_ui("status")
        return found
    except Exception:
        with OBS_LOCK:
            client = None
            OBS_CONNECTED = False

        state["dp"] = False
        queue_ui("status")
        return False


# =========================================================
# TK ROOT / OVERLAY
# =========================================================

# =========================================================
# MOUSE CLICK-THROUGH
# =========================================================

def make_mouse_passthrough(hwnd):
    """
    Faz uma janela de overlay ignorar mouse/cursor.
    Não usa subclass/WndProc via ctypes para evitar problemas
    de callback/GIL no Python 3.13.
    """
    if not hwnd:
        return

    try:
        ex_style = win32gui.GetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE
        )

        ex_style |= (
            win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_NOACTIVATE
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TOOLWINDOW
        )

        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style
        )

        # Reaplica os estilos sem mover/redimensionar.
        win32gui.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_FRAMECHANGED
        )

    except Exception as e:
        log(
            f"Erro mouse passthrough: {e}"
        )



try:
    # Completa apenas o trecho restante depois das etapas reais.
    start_progress = float(splash_progress["value"])
    duration = 0.45
    frames = 30
    for frame in range(1, frames + 1):
        t = frame / frames
        eased = t * t * (3.0 - 2.0 * t)
        splash_progress["value"] = (
            start_progress + ((100.0 - start_progress) * eased)
        )
        splash.update_idletasks()
        splash.update()
        time.sleep(duration / frames)

    splash_status_label.configure(text="Tudo pronto")
    splash.update()
    time.sleep(0.1)
    # Reaproveita a própria janela do loading; não cria um segundo Tk que pisca.
    splash.withdraw()
    for child in splash.winfo_children():
        child.destroy()
except Exception:
    pass

root = splash
root.withdraw()

# Remove o recorte arredondado usado somente pela tela de loading.
try:
    root_internal_hwnd = root.winfo_id()
    root_parent_hwnd = win32gui.GetParent(root_internal_hwnd)
    root_initial_hwnd = root_parent_hwnd if root_parent_hwnd else root_internal_hwnd
    ctypes.windll.user32.SetWindowRgn(root_initial_hwnd, 0, True)
except Exception:
    pass
try:
    root.iconbitmap(ICON_FILE)
except Exception:
    pass
root.overrideredirect(True)
root.attributes("-topmost", True)

TRANSPARENT = "#010101"

root.configure(bg=TRANSPARENT)
root.attributes("-transparentcolor", TRANSPARENT)
root.attributes("-alpha", TEXT_OPACITY)

canvas = tk.Canvas(
    root,
    bg=TRANSPARENT,
    highlightthickness=0,
    bd=0
)

canvas.pack(fill="both", expand=True)

chat_font = tkfont.Font(
    family=FONT_NAME,
    size=FONT_SIZE,
    weight="bold"
)

messages = []


def get_monitor_rects():
    """Retorna os monitores na ordem esquerda->direita e cima->baixo."""
    return system_monitor_rects()


def update_overlay_geometry():
    monitors = get_monitor_rects()
    monitor_index = min(max(1, OVERLAY_MONITOR), len(monitors)) - 1
    left, top, right, bottom = monitors[monitor_index]
    sw = right - left
    sh = bottom - top

    x = left + sw - OVERLAY_WIDTH + POSITION_X_OFFSET
    y = top + ((sh - OVERLAY_HEIGHT) // 2) + POSITION_Y_OFFSET

    root.geometry(
        f"{OVERLAY_WIDTH}x{OVERLAY_HEIGHT}{x:+d}{y:+d}"
    )

    canvas.configure(
        width=OVERLAY_WIDTH,
        height=OVERLAY_HEIGHT
    )

    return x, y


overlay_x, overlay_y = update_overlay_geometry()
root.update()


def get_real_hwnd(window):
    window.update_idletasks()
    internal = window.winfo_id()
    parent = win32gui.GetParent(internal)
    return parent if parent else internal


def exclude_from_capture(window):
    hwnd = get_real_hwnd(window)

    result = ctypes.windll.user32.SetWindowDisplayAffinity(
        hwnd,
        WDA_EXCLUDEFROMCAPTURE
    )

    return hwnd, bool(result)


hwnd_overlay, _ = exclude_from_capture(root)

style = win32gui.GetWindowLong(
    hwnd_overlay,
    win32con.GWL_EXSTYLE
)

style |= (
    win32con.WS_EX_NOACTIVATE |
    win32con.WS_EX_TOOLWINDOW |
    win32con.WS_EX_TRANSPARENT
)

win32gui.SetWindowLong(
    hwnd_overlay,
    win32con.GWL_EXSTYLE,
    style
)

root.withdraw()


# =========================================================
# ATALHOS VISÍVEIS NO JOGO
# =========================================================

hint_root = tk.Toplevel(root)
hint_root.title("GoW Overlay - Dica")
hint_root.withdraw()
hint_root.overrideredirect(True)
hint_root.attributes("-topmost", True)
hint_root.configure(bg=TRANSPARENT)
hint_root.attributes("-transparentcolor", TRANSPARENT)

# bem transparente
hint_root.attributes("-alpha", 0.28)

hint_text = tk.Label(
    hint_root,
    text="Share: limpar mensagens  |  F10: configurações  |  F11: mostrar/ocultar painel",
    bg=TRANSPARENT,
    fg="white",
    font=("Segoe UI", 9),
    anchor="w"
)

hint_text.pack(
    padx=(2, 0),
    pady=4,
    anchor="w"
)

hint_root.update_idletasks()

hint_width = 610
hint_height = 32

hint_x = 0
hint_y = root.winfo_screenheight() - hint_height - 2

hint_root.geometry(
    f"{hint_width}x{hint_height}+{hint_x}+{hint_y}"
)

hint_hwnd, _ = exclude_from_capture(hint_root)

make_mouse_passthrough(
    hint_hwnd
)

hint_style = win32gui.GetWindowLong(
    hint_hwnd,
    win32con.GWL_EXSTYLE
)

hint_style |= (
    win32con.WS_EX_NOACTIVATE |
    win32con.WS_EX_TOOLWINDOW |
    win32con.WS_EX_TRANSPARENT
)

win32gui.SetWindowLong(
    hint_hwnd,
    win32con.GWL_EXSTYLE,
    hint_style
)


# =========================================================
# TEXTO DO OVERLAY
# =========================================================

# =========================================================
# TEXTO / EMOTES DO OVERLAY
# =========================================================

EMOTE_SIZE = max(24, FONT_SIZE + 8)
EMOTE_GAP = 3
EMOTE_CACHE = {}
EMOTE_PHOTO_CACHE = {}
EMOTE_LOCK = threading.Lock()
ACTIVE_EMOTE_ANIMATIONS = []
THIRD_PARTY_EMOTE_GLOBALS = {}
THIRD_PARTY_EMOTE_CHANNEL = {}
THIRD_PARTY_EMOTE_LOCK = threading.Lock()
THIRD_PARTY_EMOTES_LOADING = False
THIRD_PARTY_EMOTES_LOADED = False

THIRD_PARTY_PROVIDER_PRIORITY = {
    "FFZ": 1,
    "BTTV": 2,
    "7TV": 3
}


def _absolute_emote_url(url):
    url = str(url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    return url


def _best_scaled_url(urls):
    if not isinstance(urls, dict):
        return ""

    for scale in ("2", "4", "3", "1"):
        if urls.get(scale):
            return _absolute_emote_url(urls[scale])

    for url in urls.values():
        if url:
            return _absolute_emote_url(url)

    return ""


def _register_third_party_emotes(emotes, channel=False):
    target = THIRD_PARTY_EMOTE_CHANNEL if channel else THIRD_PARTY_EMOTE_GLOBALS

    with THIRD_PARTY_EMOTE_LOCK:
        for emote in emotes:
            code = str(emote.get("code") or "")
            if not code:
                continue

            current = target.get(code)
            new_priority = THIRD_PARTY_PROVIDER_PRIORITY.get(
                emote.get("provider"),
                0
            )
            current_priority = THIRD_PARTY_PROVIDER_PRIORITY.get(
                current.get("provider") if current else None,
                -1
            )

            if current is None or new_priority >= current_priority:
                target[code] = emote


def _bttv_emotes(payload):
    if not isinstance(payload, list):
        return []

    emotes = []

    for item in payload:
        if not isinstance(item, dict) or item.get("modifier"):
            continue

        emote_id = str(item.get("id") or "")
        code = str(item.get("code") or "")
        if not emote_id or not code:
            continue

        emotes.append({
            "kind": "emote",
            "id": f"bttv:{emote_id}",
            "source_id": emote_id,
            "code": code,
            "provider": "BTTV",
            "third_party": True,
            "animated": bool(item.get("animated"))
            or str(item.get("imageType", "")).lower() == "gif",
            "url": f"https://cdn.betterttv.net/emote/{emote_id}/2x",
            "fallback_url": f"https://cdn.betterttv.net/emote/{emote_id}/1x"
        })

    return emotes


def _ffz_emotes(payload, global_sets=False):
    if not isinstance(payload, dict):
        return []

    sets = payload.get("sets", {})
    if not isinstance(sets, dict):
        return []

    allowed_sets = None
    if global_sets:
        allowed_sets = {
            str(set_id)
            for set_id in payload.get("default_sets", [])
        }

    emotes = []

    for set_id, emote_set in sets.items():
        if allowed_sets is not None and str(set_id) not in allowed_sets:
            continue
        if not isinstance(emote_set, dict):
            continue

        for item in emote_set.get("emoticons", []):
            if not isinstance(item, dict) or item.get("modifier"):
                continue

            emote_id = str(item.get("id") or "")
            code = str(item.get("name") or "")
            animated_urls = item.get("animated") or {}
            static_urls = item.get("urls") or {}
            animated_url = _best_scaled_url(animated_urls)
            static_url = _best_scaled_url(static_urls)
            url = animated_url or static_url

            if not emote_id or not code or not url:
                continue

            emotes.append({
                "kind": "emote",
                "id": f"ffz:{emote_id}",
                "source_id": emote_id,
                "code": code,
                "provider": "FFZ",
                "third_party": True,
                "animated": bool(animated_url),
                "url": url,
                "fallback_url": static_url or url
            })

    return emotes


def _seventv_host_url(item):
    data = item.get("data") if isinstance(item, dict) else None
    data = data if isinstance(data, dict) else {}
    host = data.get("host") if isinstance(data.get("host"), dict) else {}
    base_url = _absolute_emote_url(host.get("url"))
    files = host.get("files") if isinstance(host.get("files"), list) else []

    preferred_names = (
        "2x.webp", "3x.webp", "4x.webp", "1x.webp",
        "2x.gif", "3x.gif", "1x.gif",
        "2x.png", "3x.png", "1x.png"
    )

    selected = None
    for name in preferred_names:
        selected = next(
            (file for file in files if file.get("name") == name),
            None
        )
        if selected:
            break

    if selected and base_url:
        return (
            f"{base_url.rstrip('/')}/{selected['name']}",
            int(selected.get("frame_count", 1) or 1) > 1
        )

    return "", False


def _seventv_emotes(payload):
    if not isinstance(payload, dict):
        return []

    items = payload.get("emotes")
    if not isinstance(items, list):
        emote_set = payload.get("emote_set")
        if isinstance(emote_set, dict):
            items = emote_set.get("emotes")
    if not isinstance(items, list):
        return []

    emotes = []

    for item in items:
        if not isinstance(item, dict):
            continue

        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        emote_id = str(item.get("id") or data.get("id") or "")
        code = str(item.get("name") or data.get("name") or "")
        url, file_is_animated = _seventv_host_url(item)

        if not url and emote_id:
            url = f"https://cdn.7tv.app/emote/{emote_id}/2x.webp"

        if not emote_id or not code or not url:
            continue

        emotes.append({
            "kind": "emote",
            "id": f"7tv:{emote_id}",
            "source_id": emote_id,
            "code": code,
            "provider": "7TV",
            "third_party": True,
            "animated": bool(data.get("animated")) or file_is_animated,
            "url": url,
            "fallback_url": f"https://cdn.7tv.app/emote/{emote_id}/1x.webp"
        })

    return emotes


def _load_third_party_provider(provider):
    loaded_count = 0

    try:
        if provider == "BTTV":
            global_response = requests.get(
                "https://api.betterttv.net/3/cached/emotes/global",
                timeout=7
            )
            global_response.raise_for_status()
            global_emotes = _bttv_emotes(global_response.json())
            _register_third_party_emotes(global_emotes)
            loaded_count += len(global_emotes)

            channel_response = requests.get(
                "https://api.betterttv.net/3/cached/users/twitch/"
                f"{BROADCASTER_ID}",
                timeout=7
            )
            if channel_response.status_code == 200:
                channel_payload = channel_response.json()
                channel_items = (
                    (channel_payload.get("channelEmotes") or [])
                    + (channel_payload.get("sharedEmotes") or [])
                )
                channel_emotes = _bttv_emotes(channel_items)
                _register_third_party_emotes(channel_emotes, channel=True)
                loaded_count += len(channel_emotes)

        elif provider == "FFZ":
            global_response = requests.get(
                "https://api.frankerfacez.com/v1/set/global",
                timeout=7
            )
            global_response.raise_for_status()
            global_emotes = _ffz_emotes(
                global_response.json(),
                global_sets=True
            )
            _register_third_party_emotes(global_emotes)
            loaded_count += len(global_emotes)

            channel_response = requests.get(
                "https://api.frankerfacez.com/v1/room/id/"
                f"{BROADCASTER_ID}",
                timeout=7
            )
            if channel_response.status_code == 200:
                channel_emotes = _ffz_emotes(channel_response.json())
                _register_third_party_emotes(channel_emotes, channel=True)
                loaded_count += len(channel_emotes)

        elif provider == "7TV":
            global_response = requests.get(
                "https://7tv.io/v3/emote-sets/global",
                timeout=7
            )
            global_response.raise_for_status()
            global_emotes = _seventv_emotes(global_response.json())
            _register_third_party_emotes(global_emotes)
            loaded_count += len(global_emotes)

            channel_response = requests.get(
                f"https://7tv.io/v3/users/twitch/{BROADCASTER_ID}",
                timeout=7
            )
            if channel_response.status_code == 200:
                channel_emotes = _seventv_emotes(channel_response.json())
                _register_third_party_emotes(channel_emotes, channel=True)
                loaded_count += len(channel_emotes)

        log(f"{provider}: {loaded_count} emotes carregados")

    except Exception as e:
        log(f"{provider}: emotes indisponíveis ({e})")


def load_third_party_emotes():
    global THIRD_PARTY_EMOTES_LOADING
    global THIRD_PARTY_EMOTES_LOADED

    with THIRD_PARTY_EMOTE_LOCK:
        if THIRD_PARTY_EMOTES_LOADING or THIRD_PARTY_EMOTES_LOADED:
            return
        THIRD_PARTY_EMOTES_LOADING = True

    workers = []
    for provider in ("BTTV", "FFZ", "7TV"):
        worker = threading.Thread(
            target=_load_third_party_provider,
            args=(provider,),
            daemon=True
        )
        workers.append(worker)
        worker.start()

    for worker in workers:
        worker.join()

    with THIRD_PARTY_EMOTE_LOCK:
        THIRD_PARTY_EMOTES_LOADING = False
        THIRD_PARTY_EMOTES_LOADED = True

    log("Emotes de terceiros prontos")


def _third_party_parts(text):
    """Substitui códigos exatos por emotes, preservando espaços e texto."""
    if not text:
        return []

    parts = []
    for chunk in re.findall(r"\S+|\s+", str(text)):
        if chunk.isspace():
            parts.append({"kind": "text", "text": chunk})
            continue

        with THIRD_PARTY_EMOTE_LOCK:
            emote = (
                THIRD_PARTY_EMOTE_CHANNEL.get(chunk)
                or THIRD_PARTY_EMOTE_GLOBALS.get(chunk)
            )

        if emote:
            parts.append(dict(emote))
        else:
            parts.append({"kind": "text", "text": chunk})

    return parts


def _download_emote(
    cache_key,
    animated=False,
    url=None,
    fallback_url=None,
    source_id=None
):
    """Baixa e cacheia emotes da Twitch, BTTV, FFZ e 7TV."""
    if not cache_key:
        return None

    with EMOTE_LOCK:
        if cache_key in EMOTE_CACHE:
            return EMOTE_CACHE[cache_key]

    if not url:
        twitch_id = source_id or cache_key
        emote_format = "animated" if animated else "default"
        url = (
            "https://static-cdn.jtvnw.net/emoticons/v2/"
            f"{twitch_id}/{emote_format}/dark/3.0"
        )
        if animated:
            fallback_url = (
                "https://static-cdn.jtvnw.net/emoticons/v2/"
                f"{twitch_id}/default/dark/3.0"
            )

    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200 and fallback_url:
            r = requests.get(fallback_url, timeout=5)
        r.raise_for_status()

        source = Image.open(io.BytesIO(r.content))

        # Mantém a proporção e limita o tamanho para não estourar o chat.
        scale = min(
            EMOTE_SIZE / max(1, source.width),
            EMOTE_SIZE / max(1, source.height)
        )
        new_size = (
            max(1, int(source.width * scale)),
            max(1, int(source.height * scale))
        )

        frames = []
        durations = []
        for index, frame in enumerate(ImageSequence.Iterator(source)):
            if index >= 120:
                break
            frames.append(
                frame.convert("RGBA").resize(new_size, Image.Resampling.LANCZOS)
            )
            duration = int(frame.info.get("duration", source.info.get("duration", 100)))
            durations.append(max(33, min(500, duration or 100)))

        if not frames:
            return None

        emote_data = {
            "frames": frames,
            "durations": durations,
            "width": new_size[0],
            "height": new_size[1]
        }

        with EMOTE_LOCK:
            EMOTE_CACHE[cache_key] = emote_data

        return emote_data

    except Exception as e:
        log(f"Falha ao baixar emote {cache_key}: {e}")
        return None


def _emote_photo(
    cache_key,
    frame_index=0,
    animated=False,
    url=None,
    fallback_url=None,
    source_id=None
):
    emote_data = _download_emote(
        cache_key,
        animated,
        url,
        fallback_url,
        source_id
    )

    if emote_data is None:
        return None

    with EMOTE_LOCK:
        frames = emote_data["frames"]
        frame_index = frame_index % len(frames)
        photo_key = (cache_key, frame_index)
        photo = EMOTE_PHOTO_CACHE.get(photo_key)

        if photo is None:
            photo = ImageTk.PhotoImage(frames[frame_index])
            EMOTE_PHOTO_CACHE[photo_key] = photo

        return photo


def _message_tokens(message):
    """
    Converte uma mensagem estruturada em tokens:
      {"kind":"text","text":"..."}
      {"kind":"emote","id":"..."}
    """
    if isinstance(message, str):
        return [{"kind": "text", "text": message}]

    if not isinstance(message, dict):
        return [{"kind": "text", "text": str(message)}]

    parts = message.get("parts", [])

    if not parts:
        return [{"kind": "text", "text": message.get("text", "")}]

    tokens = []

    for part in parts:
        kind = part.get("kind")

        if kind == "emote":
            if part.get("third_party") and not THIRD_PARTY_EMOTES:
                code = str(part.get("code") or "")
                if code:
                    tokens.append({
                        "kind": "text",
                        "text": code
                    })
                continue

            tokens.append({
                "kind": "emote",
                "id": str(part.get("id", "")),
                "source_id": str(part.get("source_id", "")),
                "code": str(part.get("code", "")),
                "provider": str(part.get("provider", "")),
                "third_party": bool(part.get("third_party", False)),
                "animated": bool(part.get("animated", False)),
                "url": str(part.get("url", "")),
                "fallback_url": str(part.get("fallback_url", ""))
            })
        else:
            text = part.get("text", "")
            if text:
                # Divide o texto para permitir quebra simples de linha.
                chunks = re.findall(r"\S+|\s+", text)
                for chunk in chunks:
                    tokens.append({
                        "kind": "text",
                        "text": chunk
                    })

    return tokens


def _token_width(token):
    if token["kind"] == "emote":
        image = EMOTE_CACHE.get(token["id"])

        if image:
            return image["width"] + EMOTE_GAP

        return EMOTE_SIZE + EMOTE_GAP

    return chat_font.measure(token.get("text", ""))


def _layout_message(message):
    """
    Layout da direita para a esquerda, mantendo a ordem normal do chat.
    Retorna linhas contendo tokens e a altura de cada linha.
    """
    tokens = _message_tokens(message)

    lines = [[]]
    current_width = 0
    line_height = max(FONT_SIZE + 8, EMOTE_SIZE + 4)

    # Como o texto é desenhado ancorado à direita, montamos os tokens
    # normalmente e depois calculamos cada linha pela largura acumulada.
    for token in tokens:
        width = _token_width(token)

        if (
            lines[-1]
            and current_width + width > TEXT_WIDTH
        ):
            lines.append([])
            current_width = 0

        # Evita começar uma linha somente com espaços.
        if (
            token["kind"] == "text"
            and token["text"].isspace()
            and not lines[-1]
        ):
            continue

        lines[-1].append(token)
        current_width += width

    # Remove espaços no começo/fim das linhas.
    for line in lines:
        while line and line[0]["kind"] == "text" and line[0]["text"].isspace():
            line.pop(0)
        while line and line[-1]["kind"] == "text" and line[-1]["text"].isspace():
            line.pop()

    return lines, line_height


def calculate_message_height(message):
    lines, line_height = _layout_message(message)
    return max(line_height, len(lines) * line_height)


def _draw_token_row(tokens, y, line_height):
    total_width = sum(_token_width(t) for t in tokens)

    # Direita do texto do overlay.
    right = OVERLAY_WIDTH - 10

    # Começa no ponto correto e vai da direita para a esquerda.
    x = right

    for token in reversed(tokens):
        if token["kind"] == "emote":
            photo = _emote_photo(
                token["id"],
                animated=token.get("animated", False),
                url=token.get("url") or None,
                fallback_url=token.get("fallback_url") or None,
                source_id=token.get("source_id") or None
            )

            if photo is not None:
                w = photo.width()
                h = photo.height()

                image_item = canvas.create_image(
                    x - w,
                    y + (line_height - h) / 2,
                    image=photo,
                    anchor="nw"
                )

                emote_data = EMOTE_CACHE.get(token["id"])
                if (
                    ANIMATE_EMOTES
                    and emote_data
                    and len(emote_data["frames"]) > 1
                ):
                    ACTIVE_EMOTE_ANIMATIONS.append({
                        "item": image_item,
                        "id": token["id"],
                        "source_id": token.get("source_id"),
                        "url": token.get("url"),
                        "fallback_url": token.get("fallback_url"),
                        "animated": token.get("animated", False),
                        "frame": 0,
                        "next_at": time.monotonic()
                        + emote_data["durations"][0] / 1000.0
                    })

                x -= w + EMOTE_GAP
                continue

            # Se o download falhar, mantém o código visível no chat.
            fallback = token.get("code") or "[emote]"
            width = chat_font.measure(fallback)

            canvas.create_text(
                x,
                y + line_height / 2,
                text=fallback,
                fill="white",
                font=chat_font,
                anchor="e"
            )
            x -= width

        else:
            text = token.get("text", "")
            if not text:
                continue

            width = chat_font.measure(text)

            # Texto com outline preto.
            for ox, oy in [
                (-OUTLINE_SIZE, 0),
                (OUTLINE_SIZE, 0),
                (0, -OUTLINE_SIZE),
                (0, OUTLINE_SIZE),
                (-OUTLINE_SIZE, -OUTLINE_SIZE),
                (OUTLINE_SIZE, -OUTLINE_SIZE),
                (-OUTLINE_SIZE, OUTLINE_SIZE),
                (OUTLINE_SIZE, OUTLINE_SIZE)
            ]:
                canvas.create_text(
                    x + ox,
                    y + line_height / 2 + oy,
                    text=text,
                    fill="black",
                    font=chat_font,
                    anchor="e"
                )

            canvas.create_text(
                x,
                y + line_height / 2,
                text=text,
                fill="white",
                font=chat_font,
                anchor="e"
            )

            x -= width


def draw_chat():
    ACTIVE_EMOTE_ANIMATIONS.clear()
    canvas.delete("all")

    if not messages:
        return

    layouts = []
    total_height = 0

    for message in messages:
        lines, line_height = _layout_message(message)
        height = max(line_height, len(lines) * line_height)

        layouts.append((lines, line_height))
        total_height += height

    if len(layouts) > 1:
        total_height += MESSAGE_GAP * (len(layouts) - 1)

    current_y = (OVERLAY_HEIGHT - total_height) // 2

    for lines, line_height in layouts:
        for line in lines:
            _draw_token_row(
                line,
                current_y,
                line_height
            )
            current_y += line_height

        current_y += MESSAGE_GAP


def animate_visible_emotes():
    """Atualiza somente emotes animados que ainda existem no Canvas."""
    if ANIMATE_EMOTES and ACTIVE_EMOTE_ANIMATIONS:
        now = time.monotonic()
        alive = []

        for animation in ACTIVE_EMOTE_ANIMATIONS:
            try:
                if not canvas.type(animation["item"]):
                    continue

                emote_data = EMOTE_CACHE.get(animation["id"])
                if not emote_data or len(emote_data["frames"]) < 2:
                    continue

                if now >= animation["next_at"]:
                    frame_count = len(emote_data["frames"])
                    animation["frame"] = (animation["frame"] + 1) % frame_count
                    photo = _emote_photo(
                        animation["id"],
                        animation["frame"],
                        animated=animation.get("animated", False),
                        url=animation.get("url") or None,
                        fallback_url=animation.get("fallback_url") or None,
                        source_id=animation.get("source_id") or None
                    )
                    if photo is not None:
                        canvas.itemconfig(animation["item"], image=photo)
                    duration = emote_data["durations"][animation["frame"]]
                    animation["next_at"] = now + duration / 1000.0

                alive.append(animation)
            except Exception:
                continue

        ACTIVE_EMOTE_ANIMATIONS[:] = alive

    root.after(33, animate_visible_emotes)


root.after(33, animate_visible_emotes)


def add_overlay_message(message):
    overlay_queue.put(message)



overlay_queue = queue.Queue()


def add_overlay_message(text):
    overlay_queue.put(text)


def process_overlay_queue():
    try:
        while True:
            text = overlay_queue.get_nowait()

            # Toda mensagem recebe horário próprio, mesmo com a opção desligada.
            # Assim, ativar o temporizador também funciona nas mensagens atuais.
            if isinstance(text, dict):
                text = dict(text)
            else:
                text = {"text": str(text)}
            text["_created_at"] = time.monotonic()

            messages.append(text)

            while len(messages) > MAX_MESSAGES:
                messages.pop(0)

            draw_chat()

    except queue.Empty:
        pass

    now = time.monotonic()
    before = len(messages)
    messages[:] = [
        message for message in messages
        if not (
            AUTO_DELETE_MESSAGES
            and isinstance(message, dict)
            and message.get("_created_at") is not None
            and (now - message["_created_at"]) >= AUTO_DELETE_SECONDS
        )
    ]
    if len(messages) != before:
        draw_chat()

    root.after(100, process_overlay_queue)


# =========================================================
# REAPLICAR PROTEÇÃO DE CAPTURA
# =========================================================

def protect_window_from_capture(window):
    """
    Reaplica WDA_EXCLUDEFROMCAPTURE.
    Necessário após deiconify/iconify/overrideredirect,
    porque o Windows pode recriar ou trocar o HWND real.
    """
    try:
        window.update_idletasks()

        hwnd = get_real_hwnd(
            window
        )

        result = ctypes.windll.user32.SetWindowDisplayAffinity(
            hwnd,
            WDA_EXCLUDEFROMCAPTURE
        )

        return hwnd, bool(result)

    except Exception as e:
        log(
            f"Erro protegendo janela da captura: {e}"
        )

        return None, False


# =========================================================
# DASHBOARD
# =========================================================

dashboard_dragging = False


dashboard = tk.Toplevel(root)
dashboard.title("GoW Overlay - Live Control")
# Oculta antes de iconbitmap/overrideredirect para impedir o flash 1x1 do Windows.
dashboard.withdraw()
try:
    dashboard.iconbitmap(ICON_FILE)
except Exception:
    pass
dashboard.overrideredirect(True)
dashboard.attributes("-topmost", ALWAYS_ON_TOP)
dashboard.configure(bg="#121212")
dashboard_width = 760
dashboard_height = 720

dashboard_x = max(
    0,
    (dashboard.winfo_screenwidth() - dashboard_width) // 2 - 100
)

dashboard_y = max(
    0,
    (dashboard.winfo_screenheight() - dashboard_height) // 2
)

dashboard.geometry(
    f"{dashboard_width}x{dashboard_height}+{dashboard_x}+{dashboard_y}"
)
dashboard.minsize(700, 670)
dashboard.configure(bg="#121212")

dashboard.columnconfigure(0, weight=1)
dashboard.rowconfigure(4, weight=1)

# -------------------------
# helpers visuais
# -------------------------

def rounded_rect(canvas_obj, x1, y1, x2, y2, radius=18, **kwargs):
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1
    ]
    return canvas_obj.create_polygon(
        points,
        smooth=True,
        splinesteps=36,
        **kwargs
    )


def make_circle_check(parent, text, variable, bg, fg, command=None):
    """Checkbox circular consistente entre o painel e as configurações."""
    holder = tk.Frame(parent, bg=bg, cursor="hand2")

    def render_circle(enabled):
        scale = 6
        size = 24
        image = Image.new("RGBA", (size * scale, size * scale), bg)
        draw = ImageDraw.Draw(image)
        bounds = (2 * scale, 2 * scale, (size - 2) * scale - 1, (size - 2) * scale - 1)
        if enabled:
            draw.ellipse(
                bounds,
                fill="#b62828",
                outline="#d44a4a",
                width=scale
            )
            draw.line(
                [(6 * scale, 12 * scale), (10 * scale, 16 * scale),
                 (18 * scale, 8 * scale)],
                fill="#ffffff",
                width=2 * scale,
                joint="curve"
            )
        else:
            draw.ellipse(
                bounds,
                fill="#242426",
                outline="#606067",
                width=scale
            )
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    off_image = render_circle(False)
    on_image = render_circle(True)
    def render_disabled_circle(enabled):
        scale = 6
        size = 24
        image = Image.new("RGBA", (size * scale, size * scale), bg)
        draw = ImageDraw.Draw(image)
        bounds = (2 * scale, 2 * scale, (size - 2) * scale - 1, (size - 2) * scale - 1)
        draw.ellipse(
            bounds,
            fill="#29292c" if enabled else "#222225",
            outline="#55555b" if enabled else "#444449",
            width=scale
        )
        if enabled:
            draw.line(
                [(6 * scale, 12 * scale), (10 * scale, 16 * scale),
                 (18 * scale, 8 * scale)],
                fill="#8a8a90",
                width=2 * scale,
                joint="curve"
            )
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)

    disabled_off_image = render_disabled_circle(False)
    disabled_on_image = render_disabled_circle(True)
    dot = tk.Label(
        holder,
        image=off_image,
        bg=bg,
        bd=0,
        cursor="hand2"
    )
    dot.pack(side="left", padx=(0, 7))
    label = tk.Label(
        holder,
        text=text,
        bg=bg,
        fg=fg,
        font=("Segoe UI", 9),
        cursor="hand2"
    )
    label.pack(side="left")

    def redraw(*_):
        if holder._enabled:
            dot.configure(image=on_image if variable.get() else off_image)
        else:
            dot.configure(
                image=disabled_on_image if variable.get() else disabled_off_image
            )

    def toggle(_event=None):
        if not holder._enabled:
            return
        variable.set(not bool(variable.get()))
        if command is not None:
            command()

    for widget in (holder, dot, label):
        widget.bind("<Button-1>", toggle)

    variable.trace_add("write", redraw)
    holder._enabled = True

    def set_enabled(enabled):
        holder._enabled = bool(enabled)
        cursor = "hand2" if holder._enabled else "arrow"
        holder.configure(cursor=cursor)
        dot.configure(cursor=cursor)
        label.configure(
            cursor=cursor,
            fg=fg if holder._enabled else "#5e5e64"
        )
        dot.configure(
            image=(
                on_image if variable.get() else off_image
            ) if holder._enabled else (
                disabled_on_image if variable.get() else disabled_off_image
            )
        )

    holder._set_enabled = set_enabled
    holder._circle_images = (
        off_image, on_image, disabled_off_image, disabled_on_image
    )
    redraw()
    return holder


def make_card(parent, height):
    c = tk.Canvas(
        parent,
        height=height,
        bg="#121212",
        highlightthickness=0,
        bd=0
    )
    c.pack(fill="x", padx=14, pady=7)

    def redraw_card(event=None):
        width = event.width if event is not None else max(c.winfo_width(), 680)
        c.delete("card_background")
        rounded_rect(
            c,
            4, 4,
            max(8, width - 4), height - 4,
            radius=26,
            fill="#1c1c1e",
            outline="#303035",
            width=1,
            tags="card_background"
        )
        c.tag_lower("card_background")

    redraw_card()
    c.bind("<Configure>", redraw_card, add="+")
    return c


def make_round_button(parent, text, command, width=130):
    outer = tk.Canvas(
        parent,
        width=width,
        height=38,
        bg="#121212",
        highlightthickness=0,
        bd=0,
        cursor="hand2"
    )

    rounded_rect(
        outer,
        2, 2,
        width - 2, 36,
        radius=18,
        fill="#262629",
        outline="#343438"
    )

    outer.create_text(
        width // 2,
        19,
        text=text,
        fill="#f4f4f5",
        font=("Segoe UI", 10, "bold")
    )

    outer.bind(
        "<Button-1>",
        lambda e: command()
    )

    return outer


# -------------------------
# titlebar custom
# -------------------------

titlebar = tk.Frame(
    dashboard,
    bg="#121212",
    height=72
)
titlebar.grid(
    row=0,
    column=0,
    sticky="ew",
    padx=12,
    pady=(8, 4)
)
titlebar.grid_propagate(False)
titlebar.columnconfigure(0, weight=1)

title_center = tk.Frame(
    titlebar,
    bg="#121212"
)
title_center.grid(
    row=0,
    column=0,
    sticky="nsew"
)

tk.Label(
    title_center,
    text="GoW Overlay",
    bg="#121212",
    fg="#f5f5f7",
    font=("Segoe UI", 21, "bold")
).pack(anchor="center", pady=(2, 0))

tk.Label(
    title_center,
    text="Live Control",
    bg="#121212",
    fg="#737377",
    font=("Segoe UI", 9)
).pack(anchor="center", pady=(2, 2))


# -------------------------
# controles estilo macOS
# -------------------------

window_controls = tk.Frame(
    titlebar,
    bg="#121212"
)

window_controls.place(
    relx=1.0,
    x=-12,
    y=7,
    anchor="ne"
)


def make_window_dot(parent, color, command):

    label = tk.Label(
        parent,
        text="●",
        bg="#121212",
        fg=color,
        font=("Segoe UI Symbol", 13),
        bd=0,
        padx=0,
        pady=0,
        cursor="hand2"
    )

    label.bind(
        "<Button-1>",
        lambda e: command()
    )

    return label


def _restore_borderless_after_map(event=None):
    # volta ao visual sem barra quando a janela for restaurada
    try:
        if dashboard.state() == "normal":
            dashboard.after(
                60,
                lambda: dashboard.overrideredirect(True)
            )
    except Exception:
        pass


def minimize_dashboard():
    global dashboard_panel_visible

    dashboard_panel_visible = False

    try:
        # Garante presença na taskbar.
        hwnd = get_real_hwnd(
            dashboard
        )

        ex_style = win32gui.GetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE
        )

        ex_style &= ~win32con.WS_EX_TOOLWINDOW
        ex_style |= win32con.WS_EX_APPWINDOW

        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style
        )

        # Minimiza diretamente pelo Windows.
        # Não mexe em overrideredirect, evitando flash/borda/preto.
        win32gui.ShowWindow(
            hwnd,
            win32con.SW_MINIMIZE
        )

    except Exception:
        try:
            dashboard.iconify()
        except Exception:
            pass


def confirm_close_dashboard():

    try:
        owner_hwnd = get_real_hwnd(
            dashboard
        )
    except Exception:
        owner_hwnd = 0

    # YES/NO + question + topmost + set foreground
    flags = (
        0x00000004
        | 0x00000020
        | 0x00010000
        | 0x00040000
    )

    try:
        dashboard.lift()
        dashboard.focus_force()
    except Exception:
        pass

    result = ctypes.windll.user32.MessageBoxW(
        owner_hwnd,
        "Tem certeza que deseja fechar o GoW Overlay?",
        "GoW Overlay",
        flags
    )

    if result == 6:
        quit_program()


make_window_dot(
    window_controls,
    "#f2f2f2",
    minimize_dashboard
).pack(
    side="left",
    padx=4
)

make_window_dot(
    window_controls,
    "#ff5f57",
    confirm_close_dashboard
).pack(
    side="left",
    padx=4
)


# -------------------------
# arrastar janela - seguro no Python 3.13
# -------------------------

_drag_offset_x = 0
_drag_offset_y = 0
_drag_last_update = 0.0
_drag_hwnd = None
dashboard_dragging = False


def start_dashboard_drag(event):
    global _drag_offset_x
    global _drag_offset_y
    global dashboard_dragging
    global _drag_last_update
    global _drag_hwnd

    dashboard_dragging = True
    _drag_last_update = 0.0
    try:
        _drag_hwnd = get_real_hwnd(dashboard)
    except Exception:
        _drag_hwnd = None

    _drag_offset_x = (
        event.x_root
        - dashboard.winfo_x()
    )

    _drag_offset_y = (
        event.y_root
        - dashboard.winfo_y()
    )


def drag_dashboard(event):
    global _drag_last_update

    now = time.monotonic()

    # Até ~120 FPS, acompanhando melhor monitores de alta frequência.
    if now - _drag_last_update < (1 / 120):
        return

    _drag_last_update = now

    new_x = (
        event.x_root
        - _drag_offset_x
    )

    new_y = (
        event.y_root
        - _drag_offset_y
    )

    try:
        if _drag_hwnd:
            win32gui.SetWindowPos(
                _drag_hwnd,
                0,
                new_x,
                new_y,
                0,
                0,
                win32con.SWP_NOSIZE
                | win32con.SWP_NOZORDER
                | win32con.SWP_NOACTIVATE
            )
        else:
            dashboard.geometry(f"+{new_x}+{new_y}")
    except Exception:
        dashboard.geometry(f"+{new_x}+{new_y}")


def stop_dashboard_drag(event=None):
    global dashboard_dragging
    global _drag_hwnd
    dashboard_dragging = False
    _drag_hwnd = None


def bind_drag_recursive(widget):

    if widget is window_controls:
        return

    widget.bind(
        "<ButtonPress-1>",
        start_dashboard_drag
    )

    widget.bind(
        "<B1-Motion>",
        drag_dashboard
    )

    widget.bind(
        "<ButtonRelease-1>",
        stop_dashboard_drag
    )

    for child in widget.winfo_children():

        if child is window_controls:
            continue

        bind_drag_recursive(
            child
        )


bind_drag_recursive(
    titlebar
)


# -------------------------
# status
# -------------------------

status_container = tk.Frame(
    dashboard,
    bg="#121212"
)
status_container.grid(
    row=1,
    column=0,
    sticky="ew"
)

status_card = make_card(
    status_container,
    150
)

status_vars = {
    "gow": tk.StringVar(),
    "dp": tk.StringVar(),
    "twitch": tk.StringVar(),
    "chat": tk.StringVar(),
    "rewards": tk.StringVar(),
    "subs": tk.StringVar()
}

status_positions = [
    ("gow", 30, 40),
    ("dp", 255, 40),
    ("twitch", 480, 40),
    ("chat", 30, 95),
    ("rewards", 255, 95),
    ("subs", 480, 95)
]

status_labels = {}
status_value_labels = {}
status_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")

for key, sx, sy in status_positions:
    label_item = status_card.create_text(
        sx,
        sy,
        text="",
        anchor="w",
        fill="#a0a0a6",
        font=status_font
    )
    value_item = status_card.create_text(
        sx,
        sy,
        text="",
        anchor="w",
        fill="#a0a0a6",
        font=status_font
    )
    status_labels[key] = label_item
    status_value_labels[key] = value_item

no_live_option_label = status_card.create_text(
    340,
    68,
    text="",
    anchor="center",
    fill="#8e8e93",
    font=("Segoe UI", 10, "bold")
)


# -------------------------
# atividade
# -------------------------

activity_container = tk.Frame(
    dashboard,
    bg="#121212"
)
activity_container.grid(
    row=2,
    column=0,
    sticky="ew"
)

tk.Label(
    activity_container,
    text="Atividade recente",
    bg="#121212",
    fg="#737377",
    font=("Segoe UI", 9)
).pack(anchor="center", pady=(3, 0))

activity_card = make_card(
    activity_container,
    150
)

last_message_var = tk.StringVar(value="-")
last_reward_var = tk.StringVar(value="-")
last_sub_var = tk.StringVar(value="-")
counter_var = tk.StringVar(value="")

# Lado esquerdo: mesmos rótulos fixos e valores separados usados à direita.
activity_card.create_text(
    28, 50,
    text="Mensagem",
    anchor="w",
    fill="#8e8e93",
    font=("Segoe UI", 9, "bold")
)

activity_card.create_text(
    28, 85,
    text="Resgate",
    anchor="w",
    fill="#8e8e93",
    font=("Segoe UI", 9, "bold")
)

activity_card.create_text(
    28, 120,
    text="Sub",
    anchor="w",
    fill="#8e8e93",
    font=("Segoe UI", 9, "bold")
)

activity_message = activity_card.create_text(
    105, 50,
    text="",
    anchor="w",
    width=235,
    fill="#d8d8dc",
    font=("Segoe UI", 9)
)

activity_reward = activity_card.create_text(
    105, 85,
    text="",
    anchor="w",
    width=235,
    fill="#d8d8dc",
    font=("Segoe UI", 9)
)

activity_sub = activity_card.create_text(
    105, 120,
    text="",
    anchor="w",
    width=235,
    fill="#d8d8dc",
    font=("Segoe UI", 9)
)

# Separação discreta dentro da mesma bolha de Atividade recente.
activity_card.create_line(
    365, 24,
    365, 126,
    fill="#303035",
    width=1
)

# lado direito: status Chat / Resgates / Subs
activity_card.create_text(
    400, 50,
    text="Chat",
    anchor="w",
    fill="#8e8e93",
    font=("Segoe UI", 9, "bold")
)

activity_card.create_text(
    400, 85,
    text="Resgates",
    anchor="w",
    fill="#8e8e93",
    font=("Segoe UI", 9, "bold")
)

activity_card.create_text(
    400, 120,
    text="Subs",
    anchor="w",
    fill="#8e8e93",
    font=("Segoe UI", 9, "bold")
)

activity_counter = activity_card.create_text(
    470, 50,
    text="",
    anchor="w",
    fill="#d8d8dc",
    font=("Segoe UI", 9)
)

activity_reward_count = activity_card.create_text(
    470, 85,
    text="",
    anchor="w",
    fill="#d8d8dc",
    font=("Segoe UI", 9)
)

activity_sub_count = activity_card.create_text(
    470, 120,
    text="",
    anchor="w",
    fill="#d8d8dc",
    font=("Segoe UI", 9)
)


# -------------------------
# botões
# -------------------------

button_frame = tk.Frame(
    dashboard,
    bg="#121212"
)
button_frame.grid(
    row=3,
    column=0,
    sticky="ew",
    padx=18,
    pady=(6, 8)
)

button_frame.columnconfigure(
    0,
    weight=1
)

button_frame.columnconfigure(
    1,
    weight=0
)

button_frame.columnconfigure(
    2,
    weight=1
)

settings_window = None
settings_hwnd = None


def clear_messages():
    messages.clear()
    draw_chat()
    log("Mensagens do overlay limpas")


def _finish_hide_dashboard_after_focus(
    attempts=0
):
    global menu_hold_dp
    global release_hold_when_gow_returns

    # Quando o jogo já voltou, aí sim minimiza.
    if is_gow_foreground():
        minimize_dashboard()

        menu_hold_dp = False
        release_hold_when_gow_returns = False

        # Mantém DP ON porque agora o próprio GoW é foreground.
        set_dp(
            True
        )

        return

    # Tenta novamente por até ~900 ms.
    if attempts < 30:
        restore_gow_focus()

        root.after(
            30,
            lambda: _finish_hide_dashboard_after_focus(
                attempts + 1
            )
        )

        return

    # Segurança: se o Windows não devolver o foco,
    # não minimiza o painel para não gerar tela preta no OBS.
    release_hold_when_gow_returns = False

    log(
        "Não consegui devolver foco ao GoW; painel mantido aberto para evitar tela preta"
    )


def hide_dashboard():
    global dashboard_panel_visible
    global release_hold_when_gow_returns
    dashboard_panel_visible = False

    came_from_gow = bool(
        menu_hold_dp
    )

    if came_from_gow:
        # Mantém o DP ligado durante TODA a transição.
        release_hold_when_gow_returns = True

        set_dp(
            True
        )

        restore_gow_focus()

        root.after(
            20,
            lambda: _finish_hide_dashboard_after_focus(
                0
            )
        )

    else:
        minimize_dashboard()


support_window = None
support_hwnd = None


SUPPORT_TEXT = r"""GoW Overlay v1.02 - Suporte
========================

OBS
---
- Para controlar a captura automaticamente, use uma fonte com o nome DP.
- Para usar somente o chat, desligue o controle DP nas Configurações.
- Ative o WebSocket na porta 4455, sem senha.
- Use Captura de Áudio do Aplicativo para o som do jogo.

TWITCH
------
O login, os tokens e a renovação são automáticos. Basta autorizar a conta
quando a página oficial da Twitch abrir.

ATALHOS
-------
F9: remove mensagens.
F10: abre as Configurações.
F11: mostra ou oculta o Live Control.

AJUDA RÁPIDA
------------
- OBS não detectado: confira WebSocket, porta 4455 e senha vazia.
- Captura automática não funciona: confirme que a fonte se chama DP.
- Twitch não conecta: confira a internet e reinicie o aplicativo.

Versão: GoW Overlay v1.02
"""


def open_support_link(url):
    try:
        webbrowser.open(url)
    except Exception:
        try:
            os.startfile(url)
        except Exception:
            pass


def hide_support_window():
    try:
        support_window.withdraw()
    except Exception:
        pass


def open_support():
    global support_window
    global support_hwnd

    if (
        support_window is not None
        and support_window.winfo_exists()
    ):
        support_window.deiconify()
        support_window.lift()
        support_window.focus_force()

        try:
            support_hwnd, _ = protect_window_from_capture(
                support_window
            )
        except Exception:
            pass

        return

    support_window = tk.Toplevel(root)
    support_window.title("GoW Overlay - Suporte")
    support_window.withdraw()
    support_window.configure(bg="#161618")
    support_window.overrideredirect(True)
    support_window.attributes("-topmost", ALWAYS_ON_TOP)

    support_width = 720
    support_height = 560

    support_x = max(
        0,
        (support_window.winfo_screenwidth() - support_width) // 2 - 100
    )

    support_y = max(
        0,
        (support_window.winfo_screenheight() - support_height) // 2
    )

    support_window.geometry(
        f"{support_width}x{support_height}+{support_x}+{support_y}"
    )

    titlebar = tk.Frame(
        support_window,
        bg="#161618",
        height=58
    )
    titlebar.pack(
        fill="x",
        padx=10,
        pady=(8, 4)
    )
    titlebar.pack_propagate(False)

    tk.Label(
        titlebar,
        text="Suporte",
        bg="#161618",
        fg="#f5f5f7",
        font=("Segoe UI", 18, "bold")
    ).pack(
        anchor="center",
        pady=(3, 0)
    )

    tk.Label(
        titlebar,
        text="GoW Overlay",
        bg="#161618",
        fg="#707075",
        font=("Segoe UI", 9)
    ).pack(
        anchor="center"
    )

    controls = tk.Frame(
        titlebar,
        bg="#161618"
    )
    controls.place(
        relx=1.0,
        x=-8,
        y=7,
        anchor="ne"
    )

    close_dot = tk.Label(
        controls,
        text="●",
        bg="#161618",
        fg="#ff5f57",
        font=("Segoe UI Symbol", 13),
        cursor="hand2"
    )
    close_dot.pack(side="left", padx=4)
    close_dot.bind(
        "<Button-1>",
        lambda e: hide_support_window()
    )

    warning = tk.Label(
        support_window,
        text='A fonte deve se chamar "DP" somente quando o controle automático do OBS estiver ativado.',
        bg="#251b1b",
        fg="#ffb4ae",
        font=("Segoe UI", 10, "bold"),
        padx=12,
        pady=10,
        wraplength=660,
        justify="left"
    )
    warning.pack(
        fill="x",
        padx=18,
        pady=(4, 10)
    )

    link_frame = tk.Frame(
        support_window,
        bg="#161618"
    )
    link_frame.pack(
        fill="x",
        padx=18,
        pady=(0, 10)
    )

    for text, url in [
        ("OBS Studio", "https://obsproject.com/download"),
    ]:
        b = make_round_button(
            link_frame,
            text,
            lambda u=url: open_support_link(u),
            155
        )
        b.pack(
            side="left",
            padx=(0, 8)
        )

    text_frame = tk.Frame(
        support_window,
        bg="#1b1b1d"
    )
    text_frame.pack(
        fill="both",
        expand=True,
        padx=18,
        pady=(0, 18)
    )

    support_text_widget = tk.Text(
        text_frame,
        bg="#1b1b1d",
        fg="#b7b7bc",
        insertbackground="#b7b7bc",
        selectbackground="#34343a",
        selectforeground="#ffffff",
        relief="flat",
        bd=0,
        wrap="word",
        font=("Consolas", 9),
        padx=12,
        pady=12
    )

    scroll = tk.Scrollbar(
        text_frame,
        command=support_text_widget.yview
    )

    support_text_widget.configure(
        yscrollcommand=scroll.set
    )

    support_text_widget.pack(
        side="left",
        fill="both",
        expand=True
    )

    scroll.pack(
        side="right",
        fill="y"
    )

    support_text_widget.insert(
        "1.0",
        SUPPORT_TEXT
    )
    support_text_widget.configure(
        state="disabled"
    )

    support_window.update_idletasks()

    support_hwnd, protected = protect_window_from_capture(
        support_window
    )

    apply_bubble_window_shape(
        support_window,
        support_hwnd
    )

    if not protected:
        log("AVISO: janela de Suporte não pôde ser excluída da captura")

    drag = {
        "x": 0,
        "y": 0
    }

    def start_drag(event):
        drag["x"] = event.x_root - support_window.winfo_x()
        drag["y"] = event.y_root - support_window.winfo_y()

    def move_drag(event):
        new_x = event.x_root - drag["x"]
        new_y = event.y_root - drag["y"]
        support_window.geometry(
            f"+{new_x}+{new_y}"
        )

    titlebar.bind(
        "<ButtonPress-1>",
        start_drag
    )
    titlebar.bind(
        "<B1-Motion>",
        move_drag
    )

    support_window.deiconify()
    support_window.lift()
    support_window.focus_force()

    support_window.after(
        80,
        lambda: protect_window_from_capture(
            support_window
        )
    )


def quit_program():
    stop_tray_icon()

    try:
        stop_remote_server()
    except Exception:
        pass

    try:
        set_dp(False)
    except Exception:
        pass

    root.destroy()


# =========================================================
# CONTROLE REMOTO PELO CELULAR (QR CODE)
# =========================================================
# Servidor HTTP mínimo, só na rede local, protegido por um token aleatório
# gerado a cada ativação. Fica desligado até o usuário ativar na janela
# "Remoto". As ações são enfileiradas e executadas na thread da interface.

REMOTE_SERVER = None
REMOTE_THREAD = None
REMOTE_TOKEN = None
REMOTE_URL = ""
REMOTE_IP = ""
REMOTE_PORT = 0
REMOTE_PORT_BUSY = None       # porta preferida que estava ocupada (se houve troca)
REMOTE_LAST_SEEN = None       # último contato autorizado do celular
REMOTE_LOST_REASON = ""       # motivo da perda de conexão ("" = tudo certo)
REMOTE_HEALTH_JOB = None
REMOTE_CONTACT_TIMEOUT = 8    # segundos sem contato até avisar "sem contato"
REMOTE_FONTS = []
REMOTE_MONITORS = []
REMOTE_ACTIONS = ("clear", "toggle_always", "toggle_dp")

# Campos numéricos da janela de Configurações:
# chave, rótulo, inteiro?, mínimo aceito, máximo aceito
REMOTE_NUMBER_FIELDS = (
    ("max_messages", "Máximo de mensagens", True, 1, 100),
    ("text_opacity", "Opacidade", False, 0.05, 1.0),
    ("font_size", "Tamanho da fonte", True, 1, 200),
    ("outline_size", "Borda preta", True, 0, 50),
    ("message_gap", "Espaço entre mensagens", True, -100, 500),
    ("text_width", "Largura do texto", True, 50, 4000),
    ("overlay_width", "Largura do overlay", True, 100, 8000),
    ("overlay_height", "Altura do overlay", True, 100, 8000),
    ("position_x_offset", "Posição X", True, -8000, 8000),
    ("position_y_offset", "Posição Y", True, -8000, 8000),
    ("f9_initial_time", "F9 - primeira remoção", False, 0.1, 60),
    ("f9_repeat_time", "F9 - próximas remoções", False, 0.1, 60),
    ("auto_delete_seconds", "Tempo para apagar (segundos)", True, 1, 600),
)

# Opções liga/desliga da janela de Configurações
REMOTE_BOOL_FIELDS = (
    ("always_show_overlay", "Sempre mostrar mensagens"),
    ("auto_delete_messages", "Apagar mensagens automaticamente"),
    ("control_dp", "Controle automático DP/OBS"),
    ("animate_emotes", "Animar emotes"),
    ("show_chat", "Exibir chat no overlay"),
    ("third_party_emotes", "Emotes BTTV, FFZ e 7TV"),
    ("log_to_file", "Salvar log em arquivo (AppData)"),
    ("show_hint", "Exibir dica de atalhos na tela"),
    ("always_on_top", "Janelas do app sempre por cima"),
)

REMOTE_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta name="referrer" content="no-referrer">
<title>GoW Overlay</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;padding:20px;background:#121212;color:#f4f4f5;font:16px system-ui,sans-serif}
h1{margin:0 0 4px;font-size:22px}
.sub{color:#737377;font-size:13px;margin-bottom:18px}
button,summary{display:block;width:100%;margin:0 0 12px;padding:18px;border:1px solid #343438;
border-radius:16px;background:#262629;color:#f4f4f5;font-size:17px;font-weight:600;text-align:left;list-style:none}
button{text-align:center}
summary::-webkit-details-marker{display:none}
summary::after{content:'\\25BE';float:right;color:#737377}
details[open]>summary::after{content:'\\25B4'}
button:active{background:#34343a}
button.on{border-color:#2ea043}
button.apply{background:#1f6f34;border-color:#2ea043}
button.ghost{background:transparent;color:#9b9ba1;padding:12px;font-size:14px}
.card{background:#1b1b1d;border-radius:14px;padding:14px;margin-top:8px;font-size:14px;color:#b7b7bc}
.row{display:flex;justify-content:space-between;padding:3px 0}
.ok{color:#7ee787}.bad{color:#ff7b72}
#msg,#cmsg{height:20px;margin-top:10px;font-size:13px;color:#9b9ba1;text-align:center}
#cmsg{height:auto;min-height:20px}
.fld{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;
border-bottom:1px solid #262629;font-size:14px;color:#d4d4d8}
.fld span{flex:1}
.fld input[type=number],.fld select{width:46%;max-width:210px;padding:10px;border:1px solid #343438;
border-radius:10px;background:#262629;color:#f4f4f5;font-size:15px;text-align:center}
.fld select{text-align:left}
.sw input{appearance:none;-webkit-appearance:none;width:50px;height:30px;border-radius:15px;
background:#3a3a3f;position:relative;flex:none;outline:none}
.sw input::after{content:'';position:absolute;top:3px;left:3px;width:24px;height:24px;border-radius:50%;
background:#f4f4f5;transition:left .15s}
.sw input:checked{background:#2ea043}
.sw input:checked::after{left:23px}
</style></head><body>
<h1>GoW Overlay</h1><div class="sub">Controle remoto</div>
<button id="clear">Limpar mensagens</button>
<button id="toggle_always">Sempre mostrar mensagens</button>
<button id="toggle_dp">Controle automático DP/OBS</button>
<details id="cfg"><summary>Configurações</summary>
<div class="card" id="form">Carregando...</div>
<div id="cmsg"></div>
<button class="apply" id="apply" style="margin-top:12px">Aplicar e salvar</button>
<button class="ghost" id="discard">Descartar alterações</button>
</details>
<div class="card" id="status">Conectando...</div>
<div id="msg"></div>
<script>
const T=new URLSearchParams(location.search).get('t')||'';
const q='?t='+encodeURIComponent(T);
const $=id=>document.getElementById(id);
let dirty=false,built=false,meta=null;
function dot(v){return '<span class="'+(v?'ok':'bad')+'">'+(v?'● ligado':'● desligado')+'</span>'}
function row(a,b){return '<div class="row"><span>'+a+'</span><span>'+b+'</span></div>'}
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}
function el(tag,props,kids){const e=document.createElement(tag);Object.assign(e,props||{});(kids||[]).forEach(k=>e.append(k));return e}
function mark(){dirty=true}
function field(label,ctrl,cls){return el('label',{className:'fld'+(cls?' '+cls:'')},[el('span',{textContent:label}),ctrl])}
function buildForm(){
  const box=$('form');box.textContent='';
  const fs=el('select',{id:'f_font',onchange:mark});
  meta.fonts.forEach(f=>fs.append(new Option(f,f)));
  box.append(field('Fonte',fs));
  const ms=el('select',{id:'f_overlay_monitor',onchange:mark});
  meta.monitors.forEach((m,i)=>ms.append(new Option(m,String(i+1))));
  box.append(field('Monitor do chat',ms));
  meta.numbers.forEach(n=>box.append(field(n.label,el('input',{
    id:'f_'+n.key,type:'number',step:n.int?'1':'any',inputMode:n.int?'numeric':'decimal',oninput:mark}))));
  meta.bools.forEach(b=>box.append(field(b.label,el('input',{id:'f_'+b.key,type:'checkbox',onchange:mark}),'sw')));
  built=true;
}
function fillForm(){
  const v=meta.values;
  $('f_font').value=v.font;
  $('f_overlay_monitor').value=String(v.overlay_monitor);
  meta.numbers.forEach(n=>{$('f_'+n.key).value=v[n.key]});
  meta.bools.forEach(b=>{$('f_'+b.key).checked=!!v[b.key]});
}
async function loadSettings(force){
  if(dirty&&!force)return;
  try{
    const r=await fetch('/api/settings'+q,{cache:'no-store'});
    if(!r.ok)throw 0;
    meta=await r.json();
    if(!built)buildForm();
    fillForm();
    dirty=false;
  }catch(e){$('cmsg').textContent='Não foi possível carregar as configurações'}
}
async function applySettings(){
  if(!built)return;
  const body={font:$('f_font').value,overlay_monitor:parseInt($('f_overlay_monitor').value,10)};
  for(const n of meta.numbers){
    const raw=$('f_'+n.key).value;
    const num=parseFloat(raw);
    if(raw===''||isNaN(num)){$('cmsg').textContent='Preencha: '+n.label;return}
    body[n.key]=num;
  }
  meta.bools.forEach(b=>{body[b.key]=$('f_'+b.key).checked});
  try{
    const r=await fetch('/api/settings'+q,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const j=await r.json().catch(()=>({}));
    $('cmsg').textContent=r.ok?'Configurações aplicadas e salvas':(j.error||'Erro ao aplicar');
    if(r.ok){dirty=false;setTimeout(()=>loadSettings(true),600)}
  }catch(e){$('cmsg').textContent='Erro de conexão'}
  setTimeout(()=>{$('cmsg').textContent=''},3500);
}
async function refresh(){
  try{
    const r=await fetch('/api/status'+q,{cache:'no-store'});
    if(!r.ok)throw 0;
    const s=await r.json();
    $('toggle_always').classList.toggle('on',s.always);
    $('toggle_dp').classList.toggle('on',s.control_dp);
    $('status').innerHTML=
      row('Twitch',dot(s.twitch))+row('OBS',dot(s.obs))+
      row('Raids',dot(s.raids))+row('Resgates',dot(s.rewards))+
      row('Última raid',esc(s.last_raid))+row('Último resgate',esc(s.last_reward));
    if($('cfg').open)loadSettings(false);
  }catch(e){$('status').textContent='Sem conexão com o PC — tentando reconectar...';}
}
async function act(a){
  try{
    const r=await fetch('/api/'+a+q,{method:'POST'});
    $('msg').textContent=r.ok?'Enviado':'Erro';
  }catch(e){$('msg').textContent='Erro de conexão';}
  setTimeout(()=>$('msg').textContent='',1500);
  setTimeout(refresh,300);
  if(a!=='clear')setTimeout(()=>{if($('cfg').open)loadSettings(false)},500);
}
['clear','toggle_always','toggle_dp'].forEach(a=>$(a).onclick=()=>act(a));
$('apply').onclick=applySettings;
$('discard').onclick=()=>loadSettings(true);
$('cfg').addEventListener('toggle',()=>{if($('cfg').open)loadSettings(true)});
refresh();setInterval(refresh,2500);
</script></body></html>
"""


def get_lan_ip():
    """Descobre o IP do PC na rede local (não envia nenhum dado)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def remote_status_payload():
    return {
        "twitch": bool(state.get("twitch")),
        "obs": bool(OBS_CONNECTED),
        "raids": bool(state.get("raids")),
        "rewards": bool(state.get("rewards")),
        "always": bool(ALWAYS_SHOW_OVERLAY),
        "control_dp": bool(CONTROL_DP),
        "last_raid": str(state.get("last_raid", "-")),
        "last_reward": str(state.get("last_reward", "-")),
    }


def remote_settings_snapshot():
    """Valores atuais de TODAS as opções da janela de Configurações."""
    return {
        "font": FONT_NAME,
        "overlay_monitor": OVERLAY_MONITOR,
        "max_messages": MAX_MESSAGES,
        "text_opacity": round(TEXT_OPACITY, 2),
        "font_size": FONT_SIZE,
        "outline_size": OUTLINE_SIZE,
        "message_gap": MESSAGE_GAP,
        "text_width": TEXT_WIDTH,
        "overlay_width": OVERLAY_WIDTH,
        "overlay_height": OVERLAY_HEIGHT,
        "position_x_offset": POSITION_X_OFFSET,
        "position_y_offset": POSITION_Y_OFFSET,
        "f9_initial_time": F9_INITIAL_TIME,
        "f9_repeat_time": F9_REPEAT_TIME,
        "auto_delete_seconds": AUTO_DELETE_SECONDS,
        "always_show_overlay": bool(ALWAYS_SHOW_OVERLAY),
        "auto_delete_messages": bool(AUTO_DELETE_MESSAGES),
        "control_dp": bool(CONTROL_DP),
        "animate_emotes": bool(ANIMATE_EMOTES),
        "show_chat": bool(SHOW_CHAT),
        "third_party_emotes": bool(THIRD_PARTY_EMOTES),
        "log_to_file": bool(LOG_TO_FILE),
        "show_hint": bool(SHOW_HINT),
        "always_on_top": bool(ALWAYS_ON_TOP),
    }


def remote_settings_payload():
    return {
        "values": remote_settings_snapshot(),
        "fonts": list(REMOTE_FONTS),
        "monitors": list(REMOTE_MONITORS),
        "numbers": [
            {"key": key, "label": label, "int": is_int}
            for key, label, is_int, _lo, _hi in REMOTE_NUMBER_FIELDS
        ],
        "bools": [
            {"key": key, "label": label}
            for key, label in REMOTE_BOOL_FIELDS
        ],
    }


def refresh_remote_choices():
    """Lista fontes e monitores. Roda na thread da interface (usa o Tk)."""
    global REMOTE_FONTS, REMOTE_MONITORS

    try:
        fonts = sorted(set(tkfont.families()), key=str.lower)
    except Exception:
        fonts = []
    if FONT_NAME not in fonts:
        fonts.insert(0, FONT_NAME)
    REMOTE_FONTS = fonts

    monitors = []
    try:
        for index, (left, top, right, bottom) in enumerate(
            get_monitor_rects(), start=1
        ):
            monitors.append(f"Monitor {index} — {right - left}×{bottom - top}")
    except Exception:
        pass
    REMOTE_MONITORS = monitors or ["Monitor 1"]


def parse_remote_settings(data):
    """Valida o que veio do celular. Retorna (valores, erro)."""
    if not isinstance(data, dict):
        return None, "Dados inválidos"

    clean = {}

    for key, label, is_int, low, high in REMOTE_NUMBER_FIELDS:
        if key not in data:
            continue
        raw = data[key]
        if isinstance(raw, bool):
            return None, f"Valor inválido em {label}"
        try:
            number = float(str(raw).replace(",", "."))
        except (TypeError, ValueError):
            return None, f"Valor inválido em {label}"
        if not math.isfinite(number):
            return None, f"Valor inválido em {label}"
        if not low <= number <= high:
            return None, f"{label}: use um valor entre {low} e {high}"
        clean[key] = int(round(number)) if is_int else number

    for key, label in REMOTE_BOOL_FIELDS:
        if key in data:
            if not isinstance(data[key], bool):
                return None, f"Valor inválido em {label}"
            clean[key] = data[key]

    if "font" in data:
        font = data["font"]
        if not isinstance(font, str) or font not in REMOTE_FONTS:
            return None, "Fonte não encontrada neste PC"
        clean["font"] = font

    if "overlay_monitor" in data:
        try:
            monitor = int(data["overlay_monitor"])
        except (TypeError, ValueError):
            return None, "Monitor inválido"
        if not 1 <= monitor <= max(1, len(REMOTE_MONITORS)):
            return None, "Monitor inválido"
        clean["overlay_monitor"] = monitor

    return clean, None


class _RemoteValue:
    """Imita a interface .get() das variáveis do Tk usada por apply_settings."""

    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


def apply_remote_settings(changes):
    """Executa na thread da interface: aplica e salva as opções do celular."""
    snapshot = remote_settings_snapshot()
    merged = dict(snapshot)
    merged.update(changes)

    # Trocar de monitor reescala os tamanhos, igual à janela de Configurações.
    # Valores que o usuário mexeu no celular são respeitados como digitados.
    new_monitor = int(merged["overlay_monitor"])
    if new_monitor != OVERLAY_MONITOR:
        old_scale = CURRENT_SETTINGS_SCALE or 1.0
        ratio = monitor_scale(new_monitor) / old_scale
        for key in SCALABLE_SETTING_KEYS:
            if key not in changes or changes[key] == snapshot[key]:
                merged[key] = int(round(float(snapshot[key]) * ratio))

    apply_settings(
        {key: _RemoteValue(value) for key, value in merged.items()},
        save=True,
        log_result=False
    )
    log("Controle remoto: configurações alteradas pelo celular")


class RemoteServer(ThreadingHTTPServer):
    daemon_threads = True

    # O HTTPServer padrão liga SO_REUSEADDR. No Windows isso deixa DOIS
    # programas escutarem a mesma porta sem erro, e o celular pode acabar
    # falando com o outro script. Desligado, a porta ocupada gera erro e o
    # aplicativo troca para uma porta livre.
    allow_reuse_address = False


class RemoteHandler(BaseHTTPRequestHandler):
    server_version = "GoWOverlay"
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _authorized(self, query):
        global REMOTE_LAST_SEEN

        token = REMOTE_TOKEN
        given = (query.get("t") or [""])[0]
        ok = bool(token) and hmac.compare_digest(
            given.encode("utf-8"), token.encode("utf-8")
        )
        if ok:
            REMOTE_LAST_SEEN = time.time()
        return ok

    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length <= 0 or length > 16384:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, OSError):
            return None

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)

        if not self._authorized(query):
            self._send(403, "Acesso negado", "text/plain; charset=utf-8")
        elif url.path == "/":
            self._send(200, REMOTE_PAGE)
        elif url.path == "/api/status":
            self._send(
                200,
                json.dumps(remote_status_payload()),
                "application/json"
            )
        elif url.path == "/api/settings":
            self._send(
                200,
                json.dumps(remote_settings_payload()),
                "application/json"
            )
        else:
            self._send(404, "Não encontrado", "text/plain; charset=utf-8")

    def do_POST(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)

        if not self._authorized(query):
            self._send(403, "Acesso negado", "text/plain; charset=utf-8")
            return

        action = url.path.removeprefix("/api/")

        if action == "settings":
            data = self._read_json()
            if data is None:
                clean, error = None, "Dados inválidos"
            else:
                clean, error = parse_remote_settings(data)

            if error:
                self._send(
                    400,
                    json.dumps({"ok": False, "error": error}),
                    "application/json"
                )
            else:
                if clean:
                    queue_ui("remote_settings", clean)
                self._send(200, '{"ok": true}', "application/json")

        elif action in REMOTE_ACTIONS:
            queue_ui("remote", action)
            self._send(200, '{"ok": true}', "application/json")

        else:
            self._send(404, "Não encontrado", "text/plain; charset=utf-8")


def get_saved_remote_token():
    """Token fixo do link: criado uma vez e guardado no config.json."""
    global REMOTE_TOKEN_SAVED

    if not REMOTE_TOKEN_SAVED:
        REMOTE_TOKEN_SAVED = secrets.token_urlsafe(16)
        try:
            save_config()
        except Exception as error:
            log(f"Erro ao salvar o código do controle remoto: {error}")
    return REMOTE_TOKEN_SAVED


def start_remote_server(reuse_token=None):
    global REMOTE_SERVER, REMOTE_THREAD, REMOTE_TOKEN, REMOTE_URL
    global REMOTE_IP, REMOTE_PORT, REMOTE_PORT_BUSY
    global REMOTE_LAST_SEEN, REMOTE_LOST_REASON

    if REMOTE_SERVER is not None:
        return True

    refresh_remote_choices()

    server = None
    busy_port = None

    # Tenta a porta preferida; se outro programa já a usa, pega uma livre.
    for port in (REMOTE_PORT_PREFERRED, 0):
        try:
            server = RemoteServer(("0.0.0.0", port), RemoteHandler)
            break
        except OSError as error:
            log(
                f"Controle remoto: porta {port or 'automática'} "
                f"indisponível ({error})"
            )
            if port:
                busy_port = port

    if server is None:
        return False

    REMOTE_PORT_BUSY = busy_port
    REMOTE_IP = get_lan_ip()
    REMOTE_PORT = server.server_address[1]
    REMOTE_TOKEN = reuse_token or get_saved_remote_token()
    REMOTE_URL = f"http://{REMOTE_IP}:{REMOTE_PORT}/?t={REMOTE_TOKEN}"
    REMOTE_LAST_SEEN = None
    REMOTE_LOST_REASON = ""
    REMOTE_SERVER = server

    REMOTE_THREAD = threading.Thread(target=server.serve_forever, daemon=True)
    REMOTE_THREAD.start()

    schedule_remote_health()

    if busy_port:
        log(
            f"Controle remoto ativado na porta {REMOTE_PORT} "
            f"(a {busy_port} estava ocupada por outro programa)"
        )
    else:
        log(f"Controle remoto ativado na porta {REMOTE_PORT}")
    return True


def stop_remote_server(wait=False):
    global REMOTE_SERVER, REMOTE_THREAD, REMOTE_TOKEN, REMOTE_URL
    global REMOTE_HEALTH_JOB, REMOTE_LOST_REASON

    server = REMOTE_SERVER
    if server is None:
        return

    REMOTE_SERVER = None
    REMOTE_THREAD = None
    REMOTE_TOKEN = None
    REMOTE_URL = ""
    REMOTE_LOST_REASON = ""

    if REMOTE_HEALTH_JOB is not None:
        try:
            root.after_cancel(REMOTE_HEALTH_JOB)
        except Exception:
            pass
        REMOTE_HEALTH_JOB = None

    def _close():
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass

    closer = threading.Thread(target=_close, daemon=True)
    closer.start()
    if wait:
        # Reconectar precisa da porta livre antes de abrir de novo.
        closer.join(3.0)

    log("Controle remoto desativado")


def reconnect_remote_server(new_token=None):
    """Reinicia o servidor, atualiza o IP do QR e mantém o mesmo código
    secreto (um celular com a página aberta volta sozinho se o IP não mudou)."""
    token = new_token or (REMOTE_TOKEN if REMOTE_SERVER is not None else None)

    if REMOTE_SERVER is not None:
        stop_remote_server(wait=True)

    ok = start_remote_server(reuse_token=token)
    if ok:
        log("Controle remoto: reconectado")
    return ok


def schedule_remote_health():
    global REMOTE_HEALTH_JOB

    if REMOTE_HEALTH_JOB is not None:
        try:
            root.after_cancel(REMOTE_HEALTH_JOB)
        except Exception:
            pass
    REMOTE_HEALTH_JOB = root.after(1500, remote_health_tick)


def remote_health_tick():
    """Detecta servidor parado ou IP do PC diferente do que está no QR."""
    global REMOTE_LOST_REASON, REMOTE_HEALTH_JOB

    REMOTE_HEALTH_JOB = None
    if REMOTE_SERVER is None:
        return

    reason = ""
    if REMOTE_THREAD is not None and not REMOTE_THREAD.is_alive():
        reason = "o servidor parou"
    else:
        current_ip = get_lan_ip()
        if current_ip != REMOTE_IP:
            reason = (
                "o PC está sem rede"
                if current_ip == "127.0.0.1"
                else f"o IP do PC mudou ({REMOTE_IP} → {current_ip})"
            )

    if reason != REMOTE_LOST_REASON:
        REMOTE_LOST_REASON = reason
        if reason:
            log(f"Controle remoto: conexão perdida — {reason}")

    try:
        refresh_remote_status()
    except Exception:
        pass

    REMOTE_HEALTH_JOB = root.after(1500, remote_health_tick)


def handle_remote_action(action):
    """Executa na thread da interface uma ação pedida pelo celular."""
    global CONTROL_DP, last_active

    if action == "clear":
        clear_messages()

    elif action == "toggle_always":
        always_overlay_live_var.set(not bool(always_overlay_live_var.get()))
        toggle_always_overlay_live()

    elif action == "toggle_dp":
        previous = CONTROL_DP
        CONTROL_DP = not CONTROL_DP
        last_active = None

        if previous and not CONTROL_DP:
            set_dp(False, force=True)

        log(
            "Controle automático do DP ligado"
            if CONTROL_DP
            else "Controle automático do DP desligado"
        )
        save_config()

    log(f"Controle remoto: {action}")
    refresh_dashboard()


def make_rounded_note(parent, text, bg, fg, outline, width, font, bg_parent="#161618"):
    """Caixa de aviso com bordas curvas, no mesmo estilo dos botões."""
    pad = 12
    canvas_obj = tk.Canvas(
        parent,
        width=width,
        height=40,
        bg=bg_parent,
        highlightthickness=0,
        bd=0
    )
    text_id = canvas_obj.create_text(
        pad,
        pad,
        text=text,
        fill=fg,
        font=font,
        anchor="nw",
        width=width - pad * 2
    )
    bbox = canvas_obj.bbox(text_id)
    height = (bbox[3] - bbox[1]) + pad * 2
    canvas_obj.configure(height=height)
    rounded_rect(
        canvas_obj,
        1, 1,
        width - 1, height - 1,
        radius=18,
        fill=bg,
        outline=outline
    )
    canvas_obj.tag_raise(text_id)
    return canvas_obj


remote_window = None
remote_hwnd = None
remote_widgets = {}


def make_qr_photo(text, size=240):
    if qrcode is None:
        return None

    try:
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2
        )
        qr.add_data(text)
        qr.make(fit=True)
        qr_image = qr.make_image(
            fill_color="black",
            back_color="white"
        )
        if hasattr(qr_image, "get_image"):
            qr_image = qr_image.get_image()
        image = qr_image.convert("RGB")
        image = image.resize((size, size), Image.NEAREST)
        return ImageTk.PhotoImage(image)
    except Exception as error:
        log(f"Erro ao gerar QR code: {error}")
        return None


def remote_connection_state():
    """Texto e cor do estado da conexão mostrado na janela do PC."""
    if REMOTE_SERVER is None:
        return "Desativado", "#ff7b72"

    if REMOTE_LOST_REASON:
        return (
            f"Conexão perdida — {REMOTE_LOST_REASON}.\n"
            "Toque em Reconectar e escaneie o QR de novo.",
            "#ff7b72"
        )

    if REMOTE_LAST_SEEN is None:
        return "Ativo — aguardando o celular (escaneie o QR)", "#f2cc60"

    idle = int(time.time() - REMOTE_LAST_SEEN)
    if idle <= REMOTE_CONTACT_TIMEOUT:
        return "Celular conectado", "#7ee787"

    waited = f"{idle}s" if idle < 60 else f"{idle // 60} min"
    return (
        f"Sem contato com o celular há {waited}.\n"
        "Se ele não voltar sozinho, use Reconectar.",
        "#f2cc60"
    )


def refresh_remote_status():
    """Atualização leve (só textos); roda a cada ~1,5 s com o servidor ativo."""
    widgets = remote_widgets

    try:
        if remote_window is None or not remote_window.winfo_exists():
            return
    except Exception:
        return

    text, color = remote_connection_state()
    widgets["status"].configure(text=text, fg=color)

    if REMOTE_SERVER is not None and REMOTE_PORT_BUSY:
        widgets["info"].configure(
            text=(
                f"A porta {REMOTE_PORT_BUSY} está ocupada por outro programa. "
                f"Usando a porta {REMOTE_PORT}."
            )
        )
    else:
        widgets["info"].configure(text="")


def refresh_remote_window():
    widgets = remote_widgets

    try:
        if remote_window is None or not remote_window.winfo_exists():
            return
    except Exception:
        return

    refresh_remote_status()

    if REMOTE_SERVER is not None:
        widgets["url"].configure(text=REMOTE_URL)
        widgets["toggle"].itemconfig(widgets["toggle_text"], text="Desativar")

        # Só refaz o QR quando o endereço mudou.
        if widgets.get("qr_for") != REMOTE_URL:
            photo = make_qr_photo(REMOTE_URL)
            widgets["qr_for"] = REMOTE_URL

            if photo is not None:
                widgets["qr"].configure(image=photo, text="")
                widgets["qr"].image = photo
            else:
                widgets["qr"].configure(
                    image="",
                    text="QR indisponível.\nAbra o endereço abaixo no celular."
                )
                widgets["qr"].image = None
    else:
        widgets["qr_for"] = None
        widgets["url"].configure(text="-")
        widgets["qr"].configure(image="", text="Desativado")
        widgets["qr"].image = None
        widgets["toggle"].itemconfig(widgets["toggle_text"], text="Ativar")


def apply_remote_port_entry():
    """Lê a porta digitada na janela. Retorna False se for inválida."""
    global REMOTE_PORT_PREFERRED

    var = remote_widgets.get("port_var")
    if var is None:
        return True

    try:
        port = int(str(var.get()).strip())
        if not 1024 <= port <= 65535:
            raise ValueError
    except ValueError:
        var.set(str(REMOTE_PORT_PREFERRED))
        ctypes.windll.user32.MessageBoxW(
            0,
            "Porta inválida.\n\nUse um número entre 1024 e 65535.",
            "GoW Overlay",
            0x10
        )
        return False

    if port != REMOTE_PORT_PREFERRED:
        REMOTE_PORT_PREFERRED = port
        try:
            save_config()
        except Exception as error:
            log(f"Erro ao salvar a porta do controle remoto: {error}")
        log(f"Porta preferida do controle remoto: {port}")

    return True


def show_remote_start_error():
    ctypes.windll.user32.MessageBoxW(
        0,
        "Não foi possível iniciar o controle remoto.\n\n"
        "Confira o log para detalhes.",
        "GoW Overlay",
        0x10
    )


def toggle_remote_server():
    if REMOTE_SERVER is not None:
        stop_remote_server()
    else:
        if not apply_remote_port_entry():
            return
        if not start_remote_server():
            show_remote_start_error()

    refresh_remote_window()


def new_remote_link_clicked():
    """Gera outro código secreto (invalida o link/QR antigo)."""
    global REMOTE_TOKEN_SAVED

    answer = ctypes.windll.user32.MessageBoxW(
        0,
        "Gerar um novo link?\n\n"
        "O link e o QR atuais deixam de funcionar. "
        "Será preciso escanear o QR novo no celular.",
        "GoW Overlay",
        0x24
    )
    if answer != 6:
        return

    REMOTE_TOKEN_SAVED = secrets.token_urlsafe(16)
    try:
        save_config()
    except Exception as error:
        log(f"Erro ao salvar o código do controle remoto: {error}")
    log("Controle remoto: novo link gerado")

    if REMOTE_SERVER is not None:
        if not reconnect_remote_server(new_token=REMOTE_TOKEN_SAVED):
            show_remote_start_error()

    refresh_remote_window()


def reconnect_remote_clicked():
    if not apply_remote_port_entry():
        return

    if not reconnect_remote_server():
        show_remote_start_error()

    refresh_remote_window()


def hide_remote_window():
    try:
        remote_window.withdraw()
    except Exception:
        pass


def open_remote():
    global remote_window
    global remote_hwnd

    if remote_window is not None and remote_window.winfo_exists():
        remote_window.deiconify()
        remote_window.lift()
        remote_window.focus_force()

        try:
            remote_hwnd, _ = protect_window_from_capture(remote_window)
        except Exception:
            pass

        refresh_remote_window()
        return

    remote_window = tk.Toplevel(root)
    remote_window.title("GoW Overlay - Remoto")
    remote_window.withdraw()
    remote_window.configure(bg="#161618")
    remote_window.overrideredirect(True)
    remote_window.attributes("-topmost", ALWAYS_ON_TOP)

    remote_width = 440
    remote_height = 860

    remote_x = max(
        0,
        (remote_window.winfo_screenwidth() - remote_width) // 2 - 100
    )
    remote_y = max(
        0,
        (remote_window.winfo_screenheight() - remote_height) // 2
    )
    remote_window.geometry(
        f"{remote_width}x{remote_height}+{remote_x}+{remote_y}"
    )

    titlebar = tk.Frame(remote_window, bg="#161618", height=58)
    titlebar.pack(fill="x", padx=10, pady=(8, 4))
    titlebar.pack_propagate(False)

    tk.Label(
        titlebar,
        text="Controle remoto",
        bg="#161618",
        fg="#f5f5f7",
        font=("Segoe UI", 18, "bold")
    ).pack(anchor="center", pady=(3, 0))

    tk.Label(
        titlebar,
        text="Celular na mesma rede Wi-Fi",
        bg="#161618",
        fg="#707075",
        font=("Segoe UI", 9)
    ).pack(anchor="center")

    controls = tk.Frame(titlebar, bg="#161618")
    controls.place(relx=1.0, x=-8, y=7, anchor="ne")

    close_dot = tk.Label(
        controls,
        text="●",
        bg="#161618",
        fg="#ff5f57",
        font=("Segoe UI Symbol", 13),
        cursor="hand2"
    )
    close_dot.pack(side="left", padx=4)
    close_dot.bind("<Button-1>", lambda e: hide_remote_window())

    remote_widgets["status"] = tk.Label(
        remote_window,
        text="",
        bg="#161618",
        fg="#ff7b72",
        font=("Segoe UI", 11, "bold"),
        wraplength=400,
        justify="center"
    )
    remote_widgets["status"].pack(pady=(6, 4))

    remote_widgets["info"] = tk.Label(
        remote_window,
        text="",
        bg="#161618",
        fg="#f2cc60",
        font=("Segoe UI", 9),
        wraplength=400,
        justify="center"
    )
    remote_widgets["info"].pack(pady=(0, 4))

    qr_holder = tk.Frame(remote_window, bg="#161618", width=250, height=250)
    qr_holder.pack()
    qr_holder.pack_propagate(False)
    remote_widgets["qr"] = tk.Label(
        qr_holder,
        text="",
        bg="#ffffff",
        fg="#555555",
        font=("Segoe UI", 10),
        justify="center"
    )
    remote_widgets["qr"].pack(fill="both", expand=True, padx=5, pady=5)

    remote_widgets["url"] = tk.Label(
        remote_window,
        text="-",
        bg="#161618",
        fg="#9b9ba1",
        font=("Consolas", 8),
        wraplength=400,
        justify="center"
    )
    remote_widgets["url"].pack(padx=16, pady=(10, 8))

    port_row = tk.Frame(remote_window, bg="#161618")
    port_row.pack(pady=(0, 10))

    tk.Label(
        port_row,
        text="Porta",
        bg="#161618",
        fg="#f4f4f5",
        font=("Segoe UI", 9)
    ).pack(side="left", padx=(0, 6))

    remote_widgets["port_var"] = tk.StringVar(value=str(REMOTE_PORT_PREFERRED))
    tk.Entry(
        port_row,
        textvariable=remote_widgets["port_var"],
        width=7,
        justify="center",
        bg="#242426",
        fg="#f4f4f5",
        insertbackground="#f4f4f5",
        relief="flat"
    ).pack(side="left")

    tk.Label(
        port_row,
        text="vale ao ativar/reconectar",
        bg="#161618",
        fg="#707075",
        font=("Segoe UI", 8)
    ).pack(side="left", padx=(8, 0))

    buttons_row = tk.Frame(remote_window, bg="#161618")
    buttons_row.pack(pady=(0, 12))

    toggle_button = make_round_button(
        buttons_row,
        "Ativar",
        toggle_remote_server,
        110
    )
    toggle_button.configure(bg="#161618")
    toggle_button.pack(side="left", padx=6)
    remote_widgets["toggle"] = toggle_button
    remote_widgets["toggle_text"] = toggle_button.find_all()[-1]

    reconnect_button = make_round_button(
        buttons_row,
        "Reconectar",
        reconnect_remote_clicked,
        120
    )
    reconnect_button.configure(bg="#161618")
    reconnect_button.pack(side="left", padx=6)
    remote_widgets["reconnect"] = reconnect_button

    new_link_button = make_round_button(
        buttons_row,
        "Novo link",
        new_remote_link_clicked,
        110
    )
    new_link_button.configure(bg="#161618")
    new_link_button.pack(side="left", padx=6)

    make_rounded_note(
        remote_window,
        (
            "O link é fixo: o código secreto fica salvo e você pode favoritar a "
            "página no celular. Quem tiver o link controla o overlay; se ele "
            "vazar, use Novo link. Não mostre este QR na live: esta janela fica "
            "fora da captura do OBS.\n\n"
            "O link só muda se o IP do PC mudar. Para ele ficar sempre igual, "
            "reserve o IP do PC no roteador (reserva de DHCP).\n\n"
            "Funciona só na mesma rede Wi-Fi do PC e usa HTTP sem criptografia. "
            "Evite redes públicas. Na primeira vez, permita o aplicativo no "
            "Firewall do Windows (rede privada)."
        ),
        bg="#251b1b",
        fg="#ffb4ae",
        outline="#3a2626",
        width=404,
        font=("Segoe UI", 9)
    ).pack(padx=18, pady=(0, 14))

    remote_window.update_idletasks()

    remote_hwnd, protected = protect_window_from_capture(remote_window)
    apply_bubble_window_shape(remote_window, remote_hwnd)

    if not protected:
        log("AVISO: janela Remoto não pôde ser excluída da captura")

    drag = {"x": 0, "y": 0}

    def start_drag(event):
        drag["x"] = event.x_root - remote_window.winfo_x()
        drag["y"] = event.y_root - remote_window.winfo_y()

    def move_drag(event):
        remote_window.geometry(
            f"+{event.x_root - drag['x']}+{event.y_root - drag['y']}"
        )

    titlebar.bind("<ButtonPress-1>", start_drag)
    titlebar.bind("<B1-Motion>", move_drag)

    refresh_remote_window()

    remote_window.deiconify()
    remote_window.lift()
    remote_window.focus_force()

    remote_window.after(
        80,
        lambda: protect_window_from_capture(remote_window)
    )


# grupo central
button_center = tk.Frame(
    button_frame,
    bg="#121212"
)

button_center.grid(
    row=0,
    column=1,
    sticky="n"
)


for b in [
    make_round_button(
        button_center,
        "Remoto",
        open_remote,
        95
    ),

    make_round_button(
        button_center,
        "Configurações",
        lambda: open_settings(),
        135
    ),

    make_round_button(
        button_center,
        "Limpar mensagens",
        clear_messages,
        145
    ),

    make_round_button(
        button_center,
        "Suporte",
        open_support,
        95
    ),

    make_round_button(
        button_center,
        "Sair",
        confirm_close_dashboard,
        80
    ),

    make_round_button(
        button_center,
        "Ocultar",
        hide_dashboard,
        95
    ),
]:

    b.pack(
        side="left",
        padx=4
    )


always_overlay_live_var = tk.BooleanVar(
    value=ALWAYS_SHOW_OVERLAY
)


def toggle_always_overlay_live():

    global ALWAYS_SHOW_OVERLAY


    ALWAYS_SHOW_OVERLAY = bool(
        always_overlay_live_var.get()
    )


    save_config()


    apply_overlay_visibility()


    if ALWAYS_SHOW_OVERLAY:

        log(
            "Sempre mostrar mensagens: ativado"
        )

    else:

        log(
            "Sempre mostrar mensagens: desativado"
        )


    refresh_dashboard()


always_check = make_circle_check(
    button_frame,
    "Sempre mostrar mensagens",
    always_overlay_live_var,
    bg="#121212",
    fg="#9b9ba1",
    command=toggle_always_overlay_live
)

always_check.grid(
    row=1,
    column=0,
    columnspan=3,
    pady=(8, 0)
)


# -------------------------
# log
# -------------------------

log_outer = tk.Frame(
    dashboard,
    bg="#121212"
)
log_outer.grid(
    row=4,
    column=0,
    sticky="nsew"
)
log_outer.rowconfigure(1, weight=1)
log_outer.columnconfigure(0, weight=1)

tk.Label(
    log_outer,
    text="Live Log",
    bg="#121212",
    fg="#737377",
    font=("Segoe UI", 9)
).grid(row=0, column=0, sticky="ew", pady=(3, 0))

log_canvas = tk.Canvas(
    log_outer,
    bg="#121212",
    highlightthickness=0,
    bd=0
)
log_canvas.grid(
    row=1,
    column=0,
    sticky="nsew",
    padx=14,
    pady=(4, 8)
)

log_canvas.update_idletasks()

rounded_rect(
    log_canvas,
    4, 4,
    724, 230,
    radius=26,
    fill="#1c1c1e",
    outline="#303035",
    tags="log_card_background"
)

log_inner = tk.Frame(
    log_canvas,
    bg="#171719",
    bd=0,
    highlightthickness=0
)

log_scroll_style = ttk.Style(dashboard)
try:
    log_scroll_style.theme_use("clam")
except tk.TclError:
    pass
log_scroll_style.configure(
    "GoW.Vertical.TScrollbar",
    troughcolor="#171719",
    background="#3a3a3f",
    bordercolor="#171719",
    arrowcolor="#8e8e93",
    lightcolor="#3a3a3f",
    darkcolor="#3a3a3f",
    relief="flat",
    borderwidth=0
)
log_scroll_style.map(
    "GoW.Vertical.TScrollbar",
    background=[("active", "#55555b"), ("pressed", "#626269")]
)

log_scroll = ttk.Scrollbar(
    log_inner,
    orient="vertical",
    style="GoW.Vertical.TScrollbar"
)

log_text = tk.Text(
    log_inner,
    state="disabled",
    wrap="word",
    bg="#171719",
    fg="#747478",
    insertbackground="#d1d1d6",
    relief="flat",
    bd=0,
    highlightthickness=0,
    font=("Consolas", 9),
    yscrollcommand=log_scroll.set,
    padx=8,
    pady=7
)

log_scroll.configure(command=log_text.yview)
log_text.pack(side="left", fill="both", expand=True)
log_scroll.pack(side="right", fill="y", padx=(7, 0))

log_window = log_canvas.create_window(
    362, 24,
    anchor="n",
    width=646,
    height=184,
    window=log_inner
)


def resize_log_card(event):
    """Mantém o Live Log alinhado com os cartões superiores."""
    width = max(120, event.width)
    height = max(120, event.height)

    log_canvas.delete("log_card_background")
    rounded_rect(
        log_canvas,
        4, 4,
        width - 4, height - 4,
        radius=26,
        fill="#1c1c1e",
        outline="#303035",
        tags="log_card_background"
    )
    log_canvas.tag_lower("log_card_background")
    log_canvas.itemconfigure(
        log_window,
        width=max(80, width - 78),
        # Mesma distância em cima e embaixo.
        height=max(105, height - 48)
    )
    log_canvas.coords(log_window, width / 2, 24)


log_canvas.bind("<Configure>", resize_log_card, add="+")




dashboard.update_idletasks()
dashboard_hwnd, dashboard_protected = exclude_from_capture(dashboard)


def apply_bubble_window_shape(window, hwnd, radius=28):
    """Recorta a janela inteira com cantos arredondados no Windows."""
    if not hwnd:
        return False

    try:
        width = max(1, window.winfo_width())
        height = max(1, window.winfo_height())
        region = ctypes.windll.gdi32.CreateRoundRectRgn(
            0, 0,
            width + 1, height + 1,
            radius, radius
        )

        if not region:
            return False

        result = ctypes.windll.user32.SetWindowRgn(
            hwnd,
            region,
            True
        )

        # Em Windows 11 também pede ao DWM o estilo de canto arredondado.
        try:
            preference = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                33,
                ctypes.byref(preference),
                ctypes.sizeof(preference)
            )
        except Exception:
            pass

        return bool(result)
    except Exception:
        return False


apply_bubble_window_shape(dashboard, dashboard_hwnd)


def reapply_dashboard_capture_protection():
    global dashboard_hwnd

    hwnd, protected = protect_window_from_capture(
        dashboard
    )

    if hwnd:
        dashboard_hwnd = hwnd

        apply_bubble_window_shape(
            dashboard,
            dashboard_hwnd
        )

        try:
            dash_ex_style = win32gui.GetWindowLong(
                dashboard_hwnd,
                win32con.GWL_EXSTYLE
            )

            # continua como aplicativo na taskbar
            dash_ex_style &= ~win32con.WS_EX_TOOLWINDOW
            dash_ex_style |= win32con.WS_EX_APPWINDOW

            win32gui.SetWindowLong(
                dashboard_hwnd,
                win32con.GWL_EXSTYLE,
                dash_ex_style
            )
        except Exception:
            pass

    return protected

dashboard.bind(
    "<FocusIn>",
    lambda e: dashboard.after(
        20,
        reapply_dashboard_capture_protection
    )
)

dashboard.bind(
    "<Map>",
    lambda e: dashboard.after(
        50,
        reapply_dashboard_capture_protection
    )
)


# força o painel a aparecer na taskbar mesmo sem barra padrão
try:
    dash_style = win32gui.GetWindowLong(
        dashboard_hwnd,
        win32con.GWL_EXSTYLE
    )

    dash_style &= ~win32con.WS_EX_TOOLWINDOW
    dash_style |= win32con.WS_EX_APPWINDOW

    win32gui.SetWindowLong(
        dashboard_hwnd,
        win32con.GWL_EXSTYLE,
        dash_style
    )

    # reaplica para o Windows atualizar a taskbar
    dashboard.withdraw()
    dashboard.after(
        120,
        dashboard.deiconify
    )

except Exception as e:
    log(f"Erro ao registrar painel na taskbar: {e}")

if not dashboard_protected:
    log("AVISO: painel principal não pôde ser excluído da captura")


def dashboard_text(text, limit=72):
    if text is None:
        return "-"

    text = str(text).replace("\n", " ").strip()

    if len(text) <= limit:
        return text

    return text[:limit - 1] + "…"


def refresh_dashboard():
    def set_status(key, label, connected, waiting_text="Desconectado"):
        if connected is True:
            value_text = "Conectado"
            color = "#34c759"
        elif connected is False:
            value_text = waiting_text
            color = "#ff5f57" if waiting_text == "Não detectado" else "#a0a0a6"
        else:
            value_text = str(connected)
            color = "#ff5f57" if value_text == "Sem permissão" else "#a0a0a6"

        status_card.itemconfig(
            status_labels[key],
            text=f"{label}:",
            fill="#a0a0a6"
        )
        label_x, label_y = status_card.coords(status_labels[key])
        status_card.coords(
            status_value_labels[key],
            label_x + status_font.measure(f"{label}:") + 5,
            label_y
        )
        status_card.itemconfig(
            status_value_labels[key],
            text=value_text,
            fill=color
        )

    def position_status(key, position):
        status_card.coords(status_labels[key], *position)
        # O valor será alinhado precisamente por set_status logo abaixo.

    def hide_status(key):
        status_card.itemconfig(status_labels[key], text="")
        status_card.itemconfig(status_value_labels[key], text="")

    status_card.itemconfig(no_live_option_label, text="")

    if CONTROL_DP and SHOW_CHAT:
        # Layout completo: seis indicadores em duas linhas.
        visible_positions = {
            "gow": (30, 40),
            "dp": (255, 40),
            "twitch": (480, 40),
            "chat": (30, 95),
            "rewards": (255, 95),
            "subs": (480, 95)
        }
        for key, position in visible_positions.items():
            position_status(key, position)

        set_status(
            "gow",
            "God of War",
            state["gow_focus"],
            "Fora de foco"
        )

        set_status(
            "dp",
            "OBS",
            OBS_CONNECTED,
            "Não detectado"
        )
    elif SHOW_CHAT:
        # Modo somente chat: remove GoW/OBS e centraliza os quatro restantes.
        hide_status("gow")
        hide_status("dp")
        chat_only_positions = {
            "twitch": (145, 40),
            "chat": (410, 40),
            "rewards": (145, 95),
            "subs": (410, 95)
        }
        for key, position in chat_only_positions.items():
            position_status(key, position)

    elif CONTROL_DP:
        # Modo somente DP/OBS: esconde tudo do chat e centraliza os dois status.
        for key in ("twitch", "chat", "rewards", "subs"):
            hide_status(key)
        dp_only_positions = {
            "gow": (190, 68),
            "dp": (410, 68)
        }
        for key, position in dp_only_positions.items():
            position_status(key, position)
        set_status("gow", "God of War", state["gow_focus"], "Fora de foco")
        set_status("dp", "OBS", OBS_CONNECTED, "Não detectado")
    else:
        for key in ("gow", "dp", "twitch", "chat", "rewards", "subs"):
            hide_status(key)
        status_card.itemconfig(
            no_live_option_label,
            text="Nenhuma opção do Live Control está selecionada"
        )

    if not SHOW_CHAT:
        return

    set_status(
        "twitch",
        "Twitch",
        state["twitch"]
    )

    if REQUIRED_CHAT_SCOPE not in TOKEN_SCOPES:
        set_status("chat", "Chat", "Sem permissão")
    else:
        set_status(
            "chat",
            "Chat",
            state["chat"],
            "Aguardando"
        )

    if REQUIRED_REWARD_SCOPE not in TOKEN_SCOPES:
        set_status("rewards", "Rewards", "Sem permissão")
    else:
        set_status(
            "rewards",
            "Rewards",
            state["rewards"],
            "Aguardando"
        )

    if REQUIRED_SUB_SCOPE not in TOKEN_SCOPES:
        set_status("subs", "Subs", "Sem permissão")
    else:
        set_status(
            "subs",
            "Subs",
            state["subs"],
            "Aguardando"
        )

    activity_card.itemconfig(
        activity_message,
        text=dashboard_text(state['last_message'], 46)
    )

    activity_card.itemconfig(
        activity_reward,
        text=dashboard_text(state['last_reward'], 46)
    )

    activity_card.itemconfig(
        activity_sub,
        text=dashboard_text(state['last_sub'], 46)
    )

    activity_card.itemconfig(
        activity_counter,
        text=f"{state['chat_count']} mensagens"
    )

    activity_card.itemconfig(
        activity_reward_count,
        text=f"{state['reward_count']} resgates"
    )

    activity_card.itemconfig(
        activity_sub_count,
        text=f"{state['sub_count']} subs"
    )


# =========================================================
# ÍCONE DA BANDEJA
# =========================================================

tray_icon = None


def show_dashboard_from_tray():
    global dashboard_panel_visible

    dashboard_panel_visible = True
    try:
        dashboard.deiconify()
        dashboard.attributes("-topmost", ALWAYS_ON_TOP)
        dashboard.overrideredirect(True)
        dashboard.lift()
        dashboard.focus_force()
        reapply_dashboard_capture_protection()
        refresh_dashboard()
        apply_overlay_visibility()
    except Exception as error:
        log(f"Erro ao abrir Live Control pela bandeja: {error}")


def stop_tray_icon():
    global tray_icon

    icon = tray_icon
    tray_icon = None
    if icon is not None:
        try:
            icon.stop()
        except Exception:
            pass


def start_tray_icon():
    global tray_icon

    if tray_icon is not None:
        return

    try:
        tray_image = Image.open(ICON_FILE).convert("RGBA")
    except Exception:
        tray_image = Image.open(SPLASH_IMAGE_FILE).convert("RGBA")

    def request(action):
        def callback(_icon=None, _item=None):
            queue_ui(action)
        return callback

    tray_menu = pystray.Menu(
        pystray.MenuItem(
            "Abrir Live Control",
            request("tray_dashboard"),
            default=True
        ),
        pystray.MenuItem(
            "Configurações",
            request("tray_settings")
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Sair",
            request("tray_quit")
        )
    )

    tray_icon = pystray.Icon(
        "gow_overlay",
        tray_image,
        "GoW Overlay",
        tray_menu
    )
    tray_icon.run_detached()


def process_ui_queue():
    changed = False

    try:
        while True:
            kind, value = ui_queue.get_nowait()

            if kind == "log":
                log_text.configure(state="normal")
                log_text.insert("end", value + "\n")
                log_text.see("end")
                log_text.configure(state="disabled")

            elif kind == "remote":
                handle_remote_action(value)

            elif kind == "remote_settings":
                apply_remote_settings(value)

            elif kind == "tray_dashboard":
                show_dashboard_from_tray()

            elif kind == "tray_settings":
                open_settings()

            elif kind == "tray_quit":
                quit_program()
                return

            changed = True

    except queue.Empty:
        pass

    if changed and dashboard.state() != "withdrawn":
        refresh_dashboard()

    root.after(100, process_ui_queue)


# =========================================================
# CONFIGURAÇÕES
# =========================================================

def apply_always_on_top():
    """Aplica 'sempre por cima' às janelas do app que já existem."""
    for window in (dashboard, settings_window, support_window, remote_window):
        try:
            if window is not None and window.winfo_exists():
                window.attributes("-topmost", ALWAYS_ON_TOP)
        except Exception:
            pass


def apply_settings(values, save=False, log_result=True):
    global MAX_MESSAGES
    global TEXT_OPACITY
    global FONT_NAME
    global FONT_SIZE
    global OUTLINE_SIZE
    global MESSAGE_GAP
    global TEXT_WIDTH
    global OVERLAY_WIDTH
    global OVERLAY_HEIGHT
    global POSITION_X_OFFSET
    global POSITION_Y_OFFSET
    global OVERLAY_MONITOR
    global CONTROL_DP
    global SHOW_CHAT
    global ANIMATE_EMOTES
    global THIRD_PARTY_EMOTES
    global LOG_TO_FILE
    global SHOW_HINT
    global EMOTE_SIZE
    global CURRENT_SETTINGS_SCALE
    global F9_INITIAL_TIME
    global F9_REPEAT_TIME
    global ALWAYS_SHOW_OVERLAY
    global ALWAYS_ON_TOP
    global AUTO_DELETE_MESSAGES
    global AUTO_DELETE_SECONDS
    global overlay_x
    global overlay_y
    global last_active

    try:
        previous_control_dp = CONTROL_DP
        previous_show_chat = SHOW_CHAT
        previous_third_party_emotes = THIRD_PARTY_EMOTES
        previous_log_to_file = LOG_TO_FILE
        previous_emote_size = EMOTE_SIZE
        previous_always_on_top = ALWAYS_ON_TOP
        MAX_MESSAGES = max(1, int(values["max_messages"].get()))

        TEXT_OPACITY = max(
            0.05,
            min(1.0, float(values["text_opacity"].get()))
        )

        FONT_NAME = values["font"].get()
        FONT_SIZE = max(1, int(values["font_size"].get()))
        OUTLINE_SIZE = max(0, int(values["outline_size"].get()))

        MESSAGE_GAP = int(values["message_gap"].get())
        TEXT_WIDTH = max(50, int(values["text_width"].get()))

        OVERLAY_WIDTH = max(100, int(values["overlay_width"].get()))
        OVERLAY_HEIGHT = max(100, int(values["overlay_height"].get()))

        POSITION_X_OFFSET = int(values["position_x_offset"].get())
        POSITION_Y_OFFSET = int(values["position_y_offset"].get())
        OVERLAY_MONITOR = max(1, int(values["overlay_monitor"].get()))
        CURRENT_SETTINGS_SCALE = monitor_scale(OVERLAY_MONITOR)

        F9_INITIAL_TIME = max(0.1, float(values["f9_initial_time"].get()))
        F9_REPEAT_TIME = max(0.1, float(values["f9_repeat_time"].get()))
        ALWAYS_SHOW_OVERLAY = bool(values["always_show_overlay"].get())
        AUTO_DELETE_MESSAGES = bool(values["auto_delete_messages"].get())
        CONTROL_DP = bool(values["control_dp"].get())
        SHOW_CHAT = bool(values["show_chat"].get())
        ANIMATE_EMOTES = bool(values["animate_emotes"].get())
        THIRD_PARTY_EMOTES = bool(values["third_party_emotes"].get())
        LOG_TO_FILE = bool(values["log_to_file"].get())
        SHOW_HINT = bool(values["show_hint"].get())
        if "always_on_top" in values:
            ALWAYS_ON_TOP = bool(values["always_on_top"].get())
        if ALWAYS_ON_TOP != previous_always_on_top:
            apply_always_on_top()
            log(
                "Janelas do app sempre por cima: ligado"
                if ALWAYS_ON_TOP
                else "Janelas do app sempre por cima: desligado"
            )
        if CONTROL_DP != previous_control_dp:
            last_active = None
        AUTO_DELETE_SECONDS = max(
            1,
            min(600, int(values["auto_delete_seconds"].get()))
        )

        EMOTE_SIZE = max(24, FONT_SIZE + 8)
        if EMOTE_SIZE != previous_emote_size:
            with EMOTE_LOCK:
                EMOTE_CACHE.clear()
                EMOTE_PHOTO_CACHE.clear()

        if previous_control_dp and not CONTROL_DP:
            set_dp(False, force=True)
            log("Controle automático do DP desligado")

        if SHOW_CHAT != previous_show_chat:
            log("Exibição do chat ligada" if SHOW_CHAT else "Exibição do chat desligada")

        if LOG_TO_FILE != previous_log_to_file:
            if LOG_TO_FILE:
                log("Log em arquivo ligado")
            else:
                # Registra antes de desligar de fato, para constar no arquivo.
                LOG_TO_FILE = True
                log("Log em arquivo desligado")
                LOG_TO_FILE = False

        if THIRD_PARTY_EMOTES != previous_third_party_emotes:
            log(
                "Emotes BTTV/FFZ/7TV ligados"
                if THIRD_PARTY_EMOTES
                else "Emotes BTTV/FFZ/7TV desligados"
            )
            if THIRD_PARTY_EMOTES and not THIRD_PARTY_EMOTES_LOADED:
                threading.Thread(
                    target=load_third_party_emotes,
                    daemon=True
                ).start()

        while len(messages) > MAX_MESSAGES:
            messages.pop(0)

        chat_font.configure(
            family=FONT_NAME,
            size=FONT_SIZE,
            weight="bold"
        )

        root.attributes("-alpha", TEXT_OPACITY)

        overlay_x, overlay_y = update_overlay_geometry()

        draw_chat()

        try:
            always_overlay_live_var.set(
                ALWAYS_SHOW_OVERLAY
            )
        except Exception:
            pass

        apply_overlay_visibility()


        try:
            always_overlay_live_var.set(
                ALWAYS_SHOW_OVERLAY
            )
        except Exception:
            pass


        # Tudo que for aplicado vira o novo padrão automaticamente.
        save_config()

        # Atualiza também o estado em memória usado como "padrão atual".
        config.update({
            "max_messages": MAX_MESSAGES,
            "text_opacity": TEXT_OPACITY,
            "font": FONT_NAME,
            "font_size": FONT_SIZE,
            "outline_size": OUTLINE_SIZE,
            "message_gap": MESSAGE_GAP,
            "text_width": TEXT_WIDTH,
            "overlay_width": OVERLAY_WIDTH,
            "overlay_height": OVERLAY_HEIGHT,
            "position_x_offset": POSITION_X_OFFSET,
            "position_y_offset": POSITION_Y_OFFSET,
            "overlay_monitor": OVERLAY_MONITOR,
            "settings_scale": CURRENT_SETTINGS_SCALE,
            "control_dp": CONTROL_DP,
            "show_chat": SHOW_CHAT,
            "animate_emotes": ANIMATE_EMOTES,
            "third_party_emotes": THIRD_PARTY_EMOTES,
            "log_to_file": LOG_TO_FILE,
            "show_hint": SHOW_HINT,
            "always_on_top": ALWAYS_ON_TOP,
            "f9_initial_time": F9_INITIAL_TIME,
            "f9_repeat_time": F9_REPEAT_TIME,
            "always_show_overlay": ALWAYS_SHOW_OVERLAY,
            "auto_delete_messages": AUTO_DELETE_MESSAGES,
            "auto_delete_seconds": AUTO_DELETE_SECONDS
        })

        if log_result:
            if save:
                log("Configurações salvadas")
            else:
                log("Configurações aplicadas")

        refresh_dashboard()

    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Valor inválido:\n\n{e}",
            "GoW Overlay",
            0x10
        )


def reapply_settings_capture_protection():
    global settings_hwnd

    if settings_window is None:
        return False

    try:
        if not settings_window.winfo_exists():
            return False
    except Exception:
        return False

    hwnd, protected = protect_window_from_capture(
        settings_window
    )

    if hwnd:
        settings_hwnd = hwnd

    return protected


def _finish_hide_settings_after_focus(
    attempts=0
):
    global menu_hold_dp
    global release_hold_when_gow_returns

    if is_gow_foreground():
        try:
            settings_window.withdraw()
        except Exception:
            pass

        menu_hold_dp = False
        release_hold_when_gow_returns = False

        set_dp(
            True
        )

        return

    if attempts < 30:
        restore_gow_focus()

        root.after(
            30,
            lambda: _finish_hide_settings_after_focus(
                attempts + 1
            )
        )

        return

    release_hold_when_gow_returns = False

    log(
        "Não consegui devolver foco ao GoW; configurações mantidas abertas para evitar tela preta"
    )


def hide_settings_window():
    global menu_hold_dp
    global release_hold_when_gow_returns

    came_from_gow = bool(
        menu_hold_dp
    )

    if came_from_gow:
        release_hold_when_gow_returns = True

        set_dp(
            True
        )

        restore_gow_focus()

        root.after(
            20,
            lambda: _finish_hide_settings_after_focus(
                0
            )
        )

    else:
        try:
            settings_window.withdraw()
        except Exception:
            pass

        menu_hold_dp = False


def open_settings():
    global settings_window
    global settings_hwnd
    global menu_hold_dp
    global gow_return_hwnd

    # O menu só segura o DP ligado se foi aberto a partir do GoW.
    opened_from_gow = capture_gow_return_window()

    menu_hold_dp = bool(
        menu_hold_dp
        or opened_from_gow
    )

    if (
        settings_window is not None
        and settings_window.winfo_exists()
    ):
        settings_window.deiconify()
        settings_window.lift()
        settings_window.focus_force()
        return

    settings_window = tk.Toplevel(root)
    settings_window.title("GoW Overlay - Configurações")
    settings_window.withdraw()
    settings_window.configure(bg="#161618")

    # sem borda branca / barra padrão do Windows
    settings_window.overrideredirect(True)

    settings_width = 620
    settings_height = 1020

    settings_x = max(
        0,
        (settings_window.winfo_screenwidth() - settings_width) // 2 - 100
    )

    settings_y = max(
        0,
        (settings_window.winfo_screenheight() - settings_height) // 2
    )

    settings_window.geometry(
        f"{settings_width}x{settings_height}+{settings_x}+{settings_y}"
    )
    settings_window.resizable(False, False)
    settings_window.attributes("-topmost", ALWAYS_ON_TOP)

    settings_window.bind(
        "<FocusIn>",
        lambda e: settings_window.after(
            20,
            reapply_settings_capture_protection
        )
    )

    settings_window.bind(
        "<Map>",
        lambda e: settings_window.after(
            50,
            reapply_settings_capture_protection
        )
    )

    # titlebar custom
    settings_titlebar = tk.Frame(
        settings_window,
        bg="#161618",
        height=58
    )

    settings_titlebar.grid(
        row=0,
        column=0,
        columnspan=3,
        sticky="ew",
        padx=10,
        pady=(8, 4)
    )

    settings_titlebar.grid_propagate(False)

    settings_titlebar.columnconfigure(
        0,
        weight=1
    )

    settings_title_center = tk.Frame(
        settings_titlebar,
        bg="#161618"
    )

    settings_title_center.grid(
        row=0,
        column=0,
        sticky="nsew"
    )

    tk.Label(
        settings_title_center,
        text="Configurações",
        bg="#161618",
        fg="#f5f5f7",
        font=("Segoe UI", 17, "bold")
    ).pack(
        anchor="center",
        pady=(4, 0)
    )

    tk.Label(
        settings_title_center,
        text="GoW Overlay",
        bg="#161618",
        fg="#6f6f74",
        font=("Segoe UI", 9)
    ).pack(
        anchor="center",
        pady=(0, 2)
    )

    settings_controls = tk.Frame(
        settings_titlebar,
        bg="#161618"
    )

    settings_controls.place(
        relx=1.0,
        x=-8,
        y=7,
        anchor="ne"
    )

    def make_settings_dot(
        parent,
        color,
        command
    ):
        dot = tk.Label(
            parent,
            text="●",
            bg="#161618",
            fg=color,
            font=("Segoe UI Symbol", 13),
            bd=0,
            padx=0,
            pady=0,
            cursor="hand2"
        )

        dot.bind(
            "<Button-1>",
            lambda e: command()
        )

        return dot

    make_settings_dot(
        settings_controls,
        "#f2f2f2",
        hide_settings_window
    ).pack(
        side="left",
        padx=4
    )

    make_settings_dot(
        settings_controls,
        "#ff5f57",
        hide_settings_window
    ).pack(
        side="left",
        padx=4
    )

    # mover janela de configurações
    settings_drag_x = 0
    settings_drag_y = 0

    def start_settings_drag(event):
        nonlocal settings_drag_x
        nonlocal settings_drag_y

        settings_drag_x = (
            event.x_root
            - settings_window.winfo_x()
        )

        settings_drag_y = (
            event.y_root
            - settings_window.winfo_y()
        )

    def drag_settings(event):
        new_x = (
            event.x_root
            - settings_drag_x
        )

        new_y = (
            event.y_root
            - settings_drag_y
        )

        settings_window.geometry(
            f"+{new_x}+{new_y}"
        )

    for widget in (
        settings_titlebar,
        settings_title_center
    ):
        widget.bind(
            "<ButtonPress-1>",
            start_settings_drag
        )

        widget.bind(
            "<B1-Motion>",
            drag_settings
        )

    for child in settings_title_center.winfo_children():
        child.bind(
            "<ButtonPress-1>",
            start_settings_drag
        )

        child.bind(
            "<B1-Motion>",
            drag_settings
        )

    settings_window.grid_columnconfigure(0, minsize=200)
    settings_window.grid_columnconfigure(1, minsize=90)
    settings_window.grid_columnconfigure(2, minsize=300)

    values = {}

    tk.Label(
        settings_window,
        text="Fonte",
        bg="#161618",
        fg="#f4f4f5",
        font=("Segoe UI", 9)
    ).grid(
        row=1,
        column=0,
        padx=14,
        pady=8,
        sticky="w"
    )

    available_fonts = sorted(
        set(
            tkfont.families()
        ),
        key=str.lower
    )

    if FONT_NAME not in available_fonts:
        available_fonts.insert(
            0,
            FONT_NAME
        )

    font_var = tk.StringVar(
        value=FONT_NAME
    )

    values["font"] = font_var


    # -----------------------------------------------------
    # dropdown custom escuro
    # fica DENTRO da janela protegida
    # -----------------------------------------------------

    font_dropdown_frame = tk.Frame(
        settings_window,
        bg="#161618",
        width=305,
        height=30
    )

    font_dropdown_frame.grid(
        row=1,
        column=1,
        columnspan=2,
        padx=(8, 14),
        pady=8,
        sticky="ew"
    )

    font_dropdown_frame.grid_propagate(
        False
    )

    font_bubble = tk.Canvas(
        font_dropdown_frame,
        bg="#161618",
        highlightthickness=0,
        bd=0,
        cursor="hand2"
    )
    font_bubble.place(x=0, y=0, relwidth=1, relheight=1)
    rounded_rect(
        font_bubble, 1, 1, 304, 29,
        radius=13,
        fill="#242426",
        outline="#343438",
        tags="bubble_bg"
    )

    def resize_font_bubble(event):
        font_bubble.delete("bubble_bg")
        rounded_rect(
            font_bubble, 1, 1, event.width - 1, event.height - 1,
            radius=13, fill="#242426", outline="#343438",
            tags="bubble_bg"
        )
        font_bubble.tag_lower("bubble_bg")


    font_display = tk.Label(
        font_bubble,
        textvariable=font_var,
        bg="#242426",
        fg="#f4f4f5",
        font=("Segoe UI", 9),
        anchor="w",
        padx=4,
        cursor="hand2"
    )

    font_display_window = font_bubble.create_window(
        12, 15, window=font_display, anchor="w", width=250, height=24
    )


    font_arrow = tk.Label(
        font_bubble,
        text="⌄",
        bg="#242426",
        fg="#8e8e93",
        font=("Segoe UI", 11, "bold"),
        padx=2,
        cursor="hand2"
    )

    font_arrow_window = font_bubble.create_window(
        286, 15, window=font_arrow, anchor="center", width=26, height=24
    )

    def resize_font_bubble_complete(event):
        resize_font_bubble(event)
        font_bubble.coords(font_arrow_window, event.width - 18, event.height // 2)
        font_bubble.itemconfig(font_display_window, width=max(80, event.width - 52))

    font_bubble.bind("<Configure>", resize_font_bubble_complete)


    font_list_frame = tk.Frame(
        settings_window,
        bg="#161618",
        bd=0,
        highlightthickness=0
    )

    font_list_backdrop = tk.Canvas(
        font_list_frame,
        bg="#161618",
        highlightthickness=0,
        bd=0
    )
    font_list_backdrop.place(x=0, y=0, relwidth=1, relheight=1)
    rounded_rect(
        font_list_backdrop, 1, 1, 304, 189,
        radius=16,
        fill="#1c1c1e",
        outline="#343438",
        tags="bubble_bg"
    )

    def resize_font_list_bubble(event):
        font_list_backdrop.delete("bubble_bg")
        rounded_rect(
            font_list_backdrop, 1, 1, event.width - 1, event.height - 1,
            radius=16, fill="#1c1c1e", outline="#343438",
            tags="bubble_bg"
        )

    font_list_backdrop.bind("<Configure>", resize_font_list_bubble)

    font_listbox = tk.Listbox(
        font_list_frame,
        bg="#1c1c1e",
        fg="#f4f4f5",
        selectbackground="#343438",
        selectforeground="#ffffff",
        activestyle="none",
        bd=0,
        highlightthickness=0,
        relief="flat",
        font=("Segoe UI", 9),
        height=9
    )

    font_scroll = tk.Scrollbar(
        font_list_frame,
        command=font_listbox.yview,
        relief="flat",
        bd=0
    )

    font_listbox.configure(
        yscrollcommand=font_scroll.set
    )

    font_listbox.pack(
        side="left",
        fill="both",
        expand=True,
        padx=(8, 0),
        pady=7
    )

    font_scroll.pack(
        side="right",
        fill="y",
        padx=(0, 7),
        pady=7
    )


    for family in available_fonts:
        font_listbox.insert(
            "end",
            family
        )


    font_dropdown_open = {
        "value": False
    }


    def close_font_dropdown():

        if not font_dropdown_open["value"]:
            return

        font_list_frame.place_forget()

        try:
            font_list_frame.grab_release()
        except Exception:
            pass

        font_dropdown_open["value"] = False

        font_arrow.configure(
            text="⌄"
        )


    def open_font_dropdown():

        if font_dropdown_open["value"]:
            close_font_dropdown()
            return

        settings_window.update_idletasks()

        # posiciona exatamente abaixo do campo
        x = font_dropdown_frame.winfo_x()
        y = (
            font_dropdown_frame.winfo_y()
            + font_dropdown_frame.winfo_height()
            + 2
        )

        width = (
            font_dropdown_frame.winfo_width()
        )

        font_list_frame.place(
            x=x,
            y=y,
            width=width,
            height=190
        )

        font_list_frame.lift()
        font_list_frame.grab_set()
        font_listbox.focus_set()

        font_dropdown_open["value"] = True

        font_arrow.configure(
            text="⌃"
        )


    def select_font(event=None):

        selection = font_listbox.curselection()

        if not selection:
            return

        selected = font_listbox.get(
            selection[0]
        )

        font_var.set(
            selected
        )

        close_font_dropdown()


    font_display.bind(
        "<Button-1>",
        lambda e: open_font_dropdown()
    )

    font_arrow.bind(
        "<Button-1>",
        lambda e: open_font_dropdown()
    )

    font_bubble.bind(
        "<Button-1>",
        lambda e: open_font_dropdown()
    )

    font_listbox.bind(
        "<<ListboxSelect>>",
        select_font
    )

    font_listbox.bind(
        "<Return>",
        select_font
    )

    font_listbox.bind("<Escape>", lambda e: close_font_dropdown())
    font_list_frame.bind(
        "<Button-1>",
        lambda e: close_font_dropdown() if e.widget is font_list_frame else None
    )


    # Seletor explícito do monitor onde o CHAT será desenhado.
    monitor_rects = get_monitor_rects()
    monitor_options = []
    for index, (left, top, right, bottom) in enumerate(monitor_rects, start=1):
        monitor_options.append(
            f"Monitor {index} — {right - left}×{bottom - top}"
        )

    selected_monitor = min(max(1, OVERLAY_MONITOR), len(monitor_options))
    monitor_display_var = tk.StringVar(
        value=monitor_options[selected_monitor - 1]
    )
    monitor_value_var = tk.IntVar(value=selected_monitor)
    values["overlay_monitor"] = monitor_value_var

    tk.Label(
        settings_window,
        text="Monitor do chat",
        bg="#161618",
        fg="#f4f4f5",
        font=("Segoe UI", 9)
    ).grid(row=2, column=0, padx=14, pady=7, sticky="w")

    monitor_dropdown_frame = tk.Frame(
        settings_window,
        bg="#161618",
        height=30
    )
    monitor_dropdown_frame.grid(
        row=2,
        column=1,
        columnspan=2,
        padx=(8, 14),
        pady=7,
        sticky="ew"
    )
    monitor_dropdown_frame.grid_propagate(False)

    monitor_bubble = tk.Canvas(
        monitor_dropdown_frame,
        bg="#161618",
        highlightthickness=0,
        bd=0,
        cursor="hand2"
    )
    monitor_bubble.place(x=0, y=0, relwidth=1, relheight=1)
    rounded_rect(
        monitor_bubble, 1, 1, 304, 29,
        radius=13,
        fill="#242426",
        outline="#343438",
        tags="bubble_bg"
    )

    def resize_monitor_bubble(event):
        monitor_bubble.delete("bubble_bg")
        rounded_rect(
            monitor_bubble, 1, 1, event.width - 1, event.height - 1,
            radius=13, fill="#242426", outline="#343438",
            tags="bubble_bg"
        )
        monitor_bubble.tag_lower("bubble_bg")
    monitor_text_item = monitor_bubble.create_text(
        12, 15,
        text=monitor_display_var.get(),
        anchor="w",
        fill="#f4f4f5",
        font=("Segoe UI", 9)
    )
    monitor_arrow_item = monitor_bubble.create_text(
        286, 15,
        text="⌄",
        fill="#8e8e93",
        font=("Segoe UI", 11, "bold")
    )

    def resize_monitor_bubble_complete(event):
        resize_monitor_bubble(event)
        monitor_bubble.coords(monitor_arrow_item, event.width - 18, event.height // 2)

    monitor_bubble.bind("<Configure>", resize_monitor_bubble_complete)

    monitor_list_frame = tk.Frame(
        settings_window,
        bg="#161618",
        bd=0,
        highlightthickness=0
    )
    monitor_list_backdrop = tk.Canvas(
        monitor_list_frame,
        bg="#161618",
        highlightthickness=0,
        bd=0
    )
    monitor_list_backdrop.place(x=0, y=0, relwidth=1, relheight=1)
    rounded_rect(
        monitor_list_backdrop, 1, 1, 304, 93,
        radius=16,
        fill="#1c1c1e",
        outline="#343438",
        tags="bubble_bg"
    )

    def resize_monitor_list_bubble(event):
        monitor_list_backdrop.delete("bubble_bg")
        rounded_rect(
            monitor_list_backdrop, 1, 1, event.width - 1, event.height - 1,
            radius=16, fill="#1c1c1e", outline="#343438",
            tags="bubble_bg"
        )

    monitor_list_backdrop.bind("<Configure>", resize_monitor_list_bubble)
    monitor_listbox = tk.Listbox(
        monitor_list_frame,
        bg="#1c1c1e",
        fg="#f4f4f5",
        selectbackground="#343438",
        selectforeground="#ffffff",
        activestyle="none",
        bd=0,
        highlightthickness=0,
        relief="flat",
        font=("Segoe UI", 9),
        height=min(4, len(monitor_options))
    )
    for option in monitor_options:
        monitor_listbox.insert("end", option)
    monitor_listbox.pack(fill="both", expand=True, padx=8, pady=7)

    monitor_dropdown_open = {"value": False}
    monitor_scale_state = {
        "value": monitor_scale(selected_monitor, monitor_rects)
    }

    def close_monitor_dropdown():
        try:
            monitor_list_frame.grab_release()
        except Exception:
            pass
        monitor_list_frame.place_forget()
        monitor_dropdown_open["value"] = False
        monitor_bubble.itemconfig(monitor_arrow_item, text="⌄")

    def open_monitor_dropdown():
        if monitor_dropdown_open["value"]:
            close_monitor_dropdown()
            return
        settings_window.update_idletasks()
        x = monitor_dropdown_frame.winfo_x()
        y = monitor_dropdown_frame.winfo_y() + monitor_dropdown_frame.winfo_height() + 2
        height = min(150, 16 + 24 * len(monitor_options))
        monitor_list_frame.place(x=x, y=y, width=monitor_dropdown_frame.winfo_width(), height=height)
        monitor_list_frame.lift()
        monitor_list_frame.grab_set()
        monitor_listbox.focus_set()
        monitor_dropdown_open["value"] = True
        monitor_bubble.itemconfig(monitor_arrow_item, text="⌃")

    def monitor_selected(event=None):
        try:
            selection = monitor_listbox.curselection()
            if not selection:
                return
            new_monitor = selection[0] + 1
            old_scale = monitor_scale_state["value"]
            new_scale = monitor_scale(new_monitor, monitor_rects)
            ratio = new_scale / old_scale if old_scale else 1.0

            # Converte todas as medidas visuais e cada slider adota o novo
            # valor como centro automaticamente.
            for key in SCALABLE_SETTING_KEYS:
                if key in values:
                    if key in slider_rescalers:
                        slider_rescalers[key](ratio)
                    current = float(values[key].get())
                    values[key].set(str(int(round(current * ratio))))

            monitor_scale_state["value"] = new_scale
            monitor_value_var.set(new_monitor)
            monitor_display_var.set(monitor_options[new_monitor - 1])
            monitor_bubble.itemconfig(
                monitor_text_item,
                text=monitor_display_var.get()
            )
            close_monitor_dropdown()
        except Exception:
            monitor_value_var.set(1)

    monitor_bubble.bind("<Button-1>", lambda e: open_monitor_dropdown())
    monitor_listbox.bind("<<ListboxSelect>>", monitor_selected)
    monitor_listbox.bind("<Return>", monitor_selected)
    monitor_listbox.bind("<Escape>", lambda e: close_monitor_dropdown())
    monitor_list_frame.bind(
        "<Button-1>",
        lambda e: close_monitor_dropdown() if e.widget is monitor_list_frame else None
    )

    # key, label, atual, mínimo absoluto, máximo absoluto, inteiro?
    fields = [
        ("max_messages", "Máximo de mensagens", MAX_MESSAGES, 1, 30, True),
        ("text_opacity", "Opacidade", TEXT_OPACITY, 0.05, 1.0, False),
        ("font_size", "Tamanho da fonte", FONT_SIZE, 8, 40, True),
        ("outline_size", "Borda preta", OUTLINE_SIZE, 0, 6, True),
        ("message_gap", "Espaço entre mensagens", MESSAGE_GAP, 0, 40, True),
        ("text_width", "Largura do texto", TEXT_WIDTH, 150, 900, True),
        ("overlay_width", "Largura do overlay", OVERLAY_WIDTH, 250, 1000, True),
        ("overlay_height", "Altura do overlay", OVERLAY_HEIGHT, 250, 1200, True),
        ("position_x_offset", "Posição X", POSITION_X_OFFSET, -1000, 1000, True),
        ("position_y_offset", "Posição Y", POSITION_Y_OFFSET, -1000, 1000, True),
        ("f9_initial_time", "F9 - primeira remoção", F9_INITIAL_TIME, 0.5, 10.0, False),
        ("f9_repeat_time", "F9 - próximas remoções", F9_REPEAT_TIME, 0.2, 5.0, False),
        ("auto_delete_seconds", "Tempo para apagar (segundos)", AUTO_DELETE_SECONDS, 1, 600, True)
    ]

    def format_setting_value(value):
        try:
            numeric = float(value)
            if numeric.is_integer():
                return str(int(numeric))
        except (TypeError, ValueError):
            pass
        return str(value)

    def setup_relative_slider(var, slider, base_value, abs_min, abs_max, integer):
        state = {
            "base": float(base_value),
            "abs_min": float(abs_min),
            "abs_max": float(abs_max),
            "busy": False
        }

        def clamp(v):
            return max(state["abs_min"], min(state["abs_max"], v))

        def slider_changed(raw):
            if state["busy"]:
                return

            # slider sempre vai de -100 a +100.
            # zero = valor atual / centro.
            pct = float(raw) / 100.0
            base = state["base"]

            if pct >= 0:
                value = base + (state["abs_max"] - base) * pct
            else:
                value = base + (base - state["abs_min"]) * pct

            value = clamp(value)

            state["busy"] = True
            try:
                if integer:
                    var.set(str(int(round(value))))
                else:
                    var.set(
                        f"{value:.2f}"
                        .rstrip("0")
                        .rstrip(".")
                    )
            finally:
                state["busy"] = False

        def entry_changed(*_):
            if state["busy"]:
                return

            try:
                typed = clamp(float(var.get()))
            except Exception:
                return

            # Qualquer valor digitado vira o novo centro imediatamente.
            state["base"] = typed

            state["busy"] = True
            try:
                slider.set(0)

                if integer:
                    var.set(str(int(round(typed))))
                else:
                    var.set(
                        f"{typed:.2f}"
                        .rstrip("0")
                        .rstrip(".")
                    )
            finally:
                state["busy"] = False

        slider.configure(
            command=slider_changed
        )

        var.trace_add(
            "write",
            entry_changed
        )

        def rescale_bounds(ratio):
            state["abs_min"] *= ratio
            state["abs_max"] *= ratio

        return rescale_bounds

    slider_rescalers = {}

    for row, (
        key,
        label_text,
        current,
        absolute_min,
        absolute_max,
        integer
    ) in enumerate(fields, start=3):

        if key in SCALABLE_SETTING_KEYS:
            absolute_min *= monitor_scale_state["value"]
            absolute_max *= monitor_scale_state["value"]

        tk.Label(
            settings_window,
            text=label_text,
            bg="#161618",
            fg="#f4f4f5",
            font=("Segoe UI", 9)
        ).grid(
            row=row,
            column=0,
            padx=14,
            pady=7,
            sticky="w"
        )

        var = tk.StringVar(value=format_setting_value(current))
        values[key] = var

        entry = tk.Entry(
            settings_window,
            textvariable=var,
            width=10,
            justify="center",
            bg="#242426",
            fg="#f4f4f5",
            insertbackground="#f4f4f5",
            relief="flat"
        )

        entry.grid(
            row=row,
            column=1,
            padx=(8, 6),
            pady=7
        )

        slider = tk.Scale(
            settings_window,
            from_=-100,
            to=100,
            resolution=1,
            orient="horizontal",
            showvalue=False,
            length=290,
            bg="#161618",
            fg="#f4f4f5",
            troughcolor="#2b2b2f",
            activebackground="#7c7c82",
            highlightthickness=0,
            bd=0
        )

        # centro exato = valor atual
        slider.set(0)

        slider.grid(
            row=row,
            column=2,
            padx=(5, 14),
            pady=7,
            sticky="ew"
        )

        slider_rescalers[key] = setup_relative_slider(
            var,
            slider,
            current,
            absolute_min,
            absolute_max,
            integer
        )

    always_var = tk.BooleanVar(
        value=ALWAYS_SHOW_OVERLAY
    )

    values["always_show_overlay"] = always_var

    auto_delete_var = tk.BooleanVar(
        value=AUTO_DELETE_MESSAGES
    )
    values["auto_delete_messages"] = auto_delete_var

    control_dp_var = tk.BooleanVar(value=CONTROL_DP)
    values["control_dp"] = control_dp_var

    show_chat_var = tk.BooleanVar(value=SHOW_CHAT)
    values["show_chat"] = show_chat_var

    animate_emotes_var = tk.BooleanVar(value=ANIMATE_EMOTES)
    values["animate_emotes"] = animate_emotes_var

    third_party_emotes_var = tk.BooleanVar(value=THIRD_PARTY_EMOTES)
    values["third_party_emotes"] = third_party_emotes_var

    log_to_file_var = tk.BooleanVar(value=LOG_TO_FILE)
    values["log_to_file"] = log_to_file_var

    show_hint_var = tk.BooleanVar(value=SHOW_HINT)
    values["show_hint"] = show_hint_var

    always_on_top_var = tk.BooleanVar(value=ALWAYS_ON_TOP)
    values["always_on_top"] = always_on_top_var

    options_grid = tk.Frame(settings_window, bg="#161618")
    options_grid.grid(
        row=len(fields) + 3,
        column=0,
        columnspan=3,
        padx=14,
        pady=(10, 8),
        sticky="ew"
    )
    options_grid.columnconfigure(0, weight=1, uniform="options")
    options_grid.columnconfigure(1, weight=1, uniform="options")

    always_option = make_circle_check(
        options_grid,
        "Sempre mostrar mensagens",
        always_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    always_option.grid(
        row=0,
        column=0,
        padx=(0, 10),
        pady=(0, 8),
        sticky="w"
    )

    auto_delete_option = make_circle_check(
        options_grid,
        "Apagar mensagens automaticamente",
        auto_delete_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    auto_delete_option.grid(
        row=0,
        column=1,
        padx=(10, 0),
        pady=(0, 8),
        sticky="w"
    )

    control_dp_option = make_circle_check(
        options_grid,
        "Controle automático DP/OBS",
        control_dp_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    control_dp_option.grid(
        row=2,
        column=0,
        padx=(0, 10),
        pady=(2, 0),
        sticky="w"
    )

    animate_option = make_circle_check(
        options_grid,
        "Animar emotes",
        animate_emotes_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    animate_option.grid(
        row=2,
        column=1,
        padx=(10, 0),
        pady=(2, 0),
        sticky="w"
    )

    show_chat_option = make_circle_check(
        options_grid,
        "Exibir chat no overlay",
        show_chat_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    show_chat_option.grid(
        row=3,
        column=0,
        padx=(0, 10),
        pady=(10, 0),
        sticky="w"
    )

    third_party_option = make_circle_check(
        options_grid,
        "Emotes BTTV, FFZ e 7TV",
        third_party_emotes_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    third_party_option.grid(
        row=3,
        column=1,
        padx=(10, 0),
        pady=(10, 0),
        sticky="w"
    )

    log_to_file_option = make_circle_check(
        options_grid,
        "Salvar log em arquivo (AppData)",
        log_to_file_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    log_to_file_option.grid(
        row=1,
        column=0,
        padx=(0, 10),
        pady=(2, 8),
        sticky="w"
    )

    show_hint_option = make_circle_check(
        options_grid,
        "Exibir dica de atalhos na tela",
        show_hint_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    show_hint_option.grid(
        row=1,
        column=1,
        padx=(10, 0),
        pady=(2, 8),
        sticky="w"
    )

    always_on_top_option = make_circle_check(
        options_grid,
        "Janelas do app sempre por cima",
        always_on_top_var,
        bg="#161618",
        fg="#f4f4f5"
    )
    always_on_top_option.grid(
        row=4,
        column=0,
        padx=(0, 10),
        pady=(10, 0),
        sticky="w"
    )

    def update_chat_dependent_options(*_):
        enabled = bool(show_chat_var.get())
        always_option._set_enabled(enabled)
        auto_delete_option._set_enabled(enabled)
        animate_option._set_enabled(enabled)
        third_party_option._set_enabled(enabled)
        show_hint_option._set_enabled(enabled)

    show_chat_var.trace_add("write", update_chat_dependent_options)
    update_chat_dependent_options()

    def reset_settings():

        defaults = DEFAULT_CONFIG.copy()


        font_var.set(
            str(
                defaults["font"]
            )
        )

        default_monitor = min(
            max(1, STARTUP_OVERLAY_MONITOR),
            len(monitor_options)
        )
        old_scale = monitor_scale_state["value"]
        default_scale = STARTUP_MONITOR_SCALE
        bounds_ratio = default_scale / old_scale if old_scale else 1.0


        for key, _, _, _, _, _ in fields:

            if (
                key in values
                and key in defaults
            ):

                value = defaults[key]
                if key in SCALABLE_SETTING_KEYS:
                    if key in slider_rescalers:
                        slider_rescalers[key](bounds_ratio)
                    value = int(round(float(value) * default_scale))
                values[key].set(format_setting_value(value))


        always_var.set(
            bool(
                defaults.get(
                    "always_show_overlay",
                    False
                )
            )
        )

        auto_delete_var.set(
            bool(defaults.get("auto_delete_messages", False))
        )

        monitor_value_var.set(default_monitor)
        monitor_display_var.set(monitor_options[default_monitor - 1])
        monitor_bubble.itemconfig(
            monitor_text_item,
            text=monitor_display_var.get()
        )
        monitor_scale_state["value"] = default_scale

        control_dp_var.set(bool(defaults.get("control_dp", True)))
        show_chat_var.set(bool(defaults.get("show_chat", True)))
        animate_emotes_var.set(bool(defaults.get("animate_emotes", True)))
        third_party_emotes_var.set(
            bool(defaults.get("third_party_emotes", True))
        )
        log_to_file_var.set(bool(defaults.get("log_to_file", True)))
        show_hint_var.set(bool(defaults.get("show_hint", True)))
        always_on_top_var.set(bool(defaults.get("always_on_top", True)))


        # Não limpa messages.
        # Só reaplica os valores padrão.
        apply_settings(
            values,
            True,
            False
        )


        try:
            always_overlay_live_var.set(
                ALWAYS_SHOW_OVERLAY
            )
        except Exception:
            pass


        apply_overlay_visibility()


        log(
            "Configurações resetadas para o padrão"
        )



    button_frame = tk.Frame(
        settings_window,
        bg="#161618"
    )

    button_frame.grid(
        row=len(fields) + 4,
        column=0,
        columnspan=3,
        pady=20
    )

    def make_settings_button(
        parent,
        text,
        command,
        width=105
    ):
        c = tk.Canvas(
            parent,
            width=width,
            height=38,
            bg="#161618",
            highlightthickness=0,
            bd=0,
            cursor="hand2"
        )

        rounded_rect(
            c,
            2,
            2,
            width - 2,
            36,
            radius=14,
            fill="#262629",
            outline="#343438"
        )

        c.create_text(
            width // 2,
            19,
            text=text,
            fill="#f4f4f5",
            font=("Segoe UI", 9, "bold")
        )

        c.bind(
            "<Button-1>",
            lambda e: command()
        )

        return c


    for b in [
        make_settings_button(
            button_frame,
            "Aplicar",
            lambda: apply_settings(
                values,
                False
            ),
            100
        ),

        make_settings_button(
            button_frame,
            "Salvar",
            lambda: apply_settings(
                values,
                True
            ),
            100
        ),

        make_settings_button(
            button_frame,
            "Resetar",
            reset_settings,
            100
        ),

        make_settings_button(
            button_frame,
            "Fechar",
            hide_settings_window,
            100
        ),
    ]:
        b.pack(
            side="left",
            padx=5
        )

    settings_window.update_idletasks()

    # A opção nova ocupa mais uma linha: se o conteúdo passar da altura
    # fixa, aumenta a janela para os botões de baixo não ficarem cortados.
    needed_height = settings_window.winfo_reqheight()
    if needed_height > settings_height:
        settings_height = needed_height
        settings_y = max(
            0,
            (settings_window.winfo_screenheight() - settings_height) // 2
        )
        settings_window.geometry(
            f"{settings_width}x{settings_height}+{settings_x}+{settings_y}"
        )
        settings_window.update_idletasks()

    settings_hwnd, protected = exclude_from_capture(
        settings_window
    )

    apply_bubble_window_shape(
        settings_window,
        settings_hwnd
    )

    if not protected:
        settings_window.destroy()
        settings_window = None
        settings_hwnd = None

        ctypes.windll.user32.MessageBoxW(
            0,
            "Não consegui proteger o menu da captura.\n"
            "Ele não será aberto por segurança.",
            "GoW Overlay",
            0x10
        )
        return

    settings_window.deiconify()

    reapply_settings_capture_protection()

    settings_window.lift()
    settings_window.focus_force()

    root.after(
        30,
        apply_overlay_visibility
    )

    settings_window.after(
        80,
        reapply_settings_capture_protection
    )

    # F10 mantém as mensagens visíveis enquanto configuramos
    root.after(
        40,
        apply_overlay_visibility
    )


# =========================================================
# HOTKEYS
# =========================================================

f9_hold_start = None
last_f9_delete = None


def check_f9():
    global f9_hold_start, last_f9_delete

    pressed = (
        win32api.GetAsyncKeyState(VK_F9)
        & 0x8000
    )

    now = time.monotonic()

    if pressed:
        if f9_hold_start is None:
            f9_hold_start = now
            last_f9_delete = None

        elif now - f9_hold_start >= F9_INITIAL_TIME:
            if last_f9_delete is None:
                if messages:
                    messages.pop(0)
                    draw_chat()
                    refresh_dashboard()

                last_f9_delete = now

            elif now - last_f9_delete >= F9_REPEAT_TIME:
                if messages:
                    messages.pop(0)
                    draw_chat()
                    refresh_dashboard()

                last_f9_delete = now

    else:
        f9_hold_start = None
        last_f9_delete = None

    root.after(50, check_f9)


last_f10_trigger = 0.0
last_f11_trigger = 0.0

f10_down_last = False
f11_down_last = False


def check_hotkeys():
    global last_f10_trigger
    global last_f11_trigger
    global f10_down_last
    global f11_down_last
    global menu_hold_dp
    global gow_return_hwnd
    global dashboard_panel_visible
    global release_hold_when_gow_returns

    now = time.monotonic()

    f10_down = bool(
        win32api.GetAsyncKeyState(VK_F10) & 0x8000
    )

    if (
        f10_down
        and not f10_down_last
        and now - last_f10_trigger > 0.15
    ):
        last_f10_trigger = now
        open_settings()

    f10_down_last = f10_down


    f11_down = bool(
        win32api.GetAsyncKeyState(VK_F11) & 0x8000
    )

    if (
        f11_down
        and not f11_down_last
        and now - last_f11_trigger > 0.15
    ):
        last_f11_trigger = now

        if not dashboard_panel_visible:

            dashboard_panel_visible = True

            opened_from_gow = capture_gow_return_window()

            if opened_from_gow:
                menu_hold_dp = True
                set_dp(True)

            try:
                dashboard.deiconify()
                dashboard.attributes(
                    "-topmost",
                    ALWAYS_ON_TOP
                )
                dashboard.overrideredirect(True)
                dashboard.lift()
                dashboard.focus_force()
            except Exception:
                pass

            try:
                reapply_dashboard_capture_protection()
            except Exception:
                pass

            # F11 is explicitly a valid chat state.
            apply_overlay_visibility()

            dashboard.after(
                80,
                reapply_dashboard_capture_protection
            )

        else:

            hide_dashboard()

    f11_down_last = f11_down

    root.after(
        20,
        check_hotkeys
    )


# =========================================================
# TWITCH EVENTSUB
# =========================================================

def create_subscription(
    session_id,
    event_type,
    condition,
    status_key=None
):
    body = {
        "type": event_type,
        "version": "1",
        "condition": condition,
        "transport": {
            "method": "websocket",
            "session_id": session_id
        }
    }

    try:
        r = requests.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers=twitch_headers(),
            json=body,
            timeout=10
        )

        if r.status_code == 401 and refresh_token():
            # Token de acesso expirado (dura poucas horas): renova e repete.
            log("Token da Twitch renovado")
            r = requests.post(
                "https://api.twitch.tv/helix/eventsub/subscriptions",
                headers=twitch_headers(),
                json=body,
                timeout=10
            )

        if r.status_code == 202:
            if status_key:
                state[status_key] = True

            log(f"Evento conectado: {event_type}")
            queue_ui("status")
            return True

        log(
            f"Falha {event_type}: "
            f"{r.status_code} {r.text}"
        )

    except Exception as e:
        log(f"Erro {event_type}: {e}")

    if status_key:
        state[status_key] = False
        queue_ui("status")

    return False


def create_all_subscriptions(session_id):
    if REQUIRED_CHAT_SCOPE in TOKEN_SCOPES:
        create_subscription(
            session_id,
            "channel.chat.message",
            {
                "broadcaster_user_id": BROADCASTER_ID,
                "user_id": USER_ID
            },
            "chat"
        )
    else:
        log("Chat sem scope user:read:chat")

    if REQUIRED_REWARD_SCOPE in TOKEN_SCOPES:
        create_subscription(
            session_id,
            "channel.channel_points_custom_reward_redemption.add",
            {
                "broadcaster_user_id": BROADCASTER_ID
            },
            "rewards"
        )
    else:
        log("Rewards sem scope channel:read:redemptions")

    # Raid recebida não exige scope adicional. A condição "to" garante que o
    # aviso seja somente para raids que chegam ao canal autorizado.
    create_subscription(
        session_id,
        "channel.raid",
        {
            "to_broadcaster_user_id": BROADCASTER_ID
        },
        "raids"
    )

    if REQUIRED_BITS_SCOPE in TOKEN_SCOPES:
        create_subscription(
            session_id,
            "channel.cheer",
            {
                "broadcaster_user_id": BROADCASTER_ID
            },
            "bits"
        )
    else:
        state["bits"] = False
        log("Bits sem scope bits:read")
        queue_ui("status")

    if REQUIRED_SUB_SCOPE in TOKEN_SCOPES:
        ok1 = create_subscription(
            session_id,
            "channel.subscribe",
            {
                "broadcaster_user_id": BROADCASTER_ID
            }
        )

        ok2 = create_subscription(
            session_id,
            "channel.subscription.message",
            {
                "broadcaster_user_id": BROADCASTER_ID
            }
        )

        ok3 = create_subscription(
            session_id,
            "channel.subscription.gift",
            {
                "broadcaster_user_id": BROADCASTER_ID
            }
        )

        state["subs"] = bool(ok1 and ok2 and ok3)
        queue_ui("status")
    else:
        state["subs"] = False
        log("Subs sem scope channel:read:subscriptions")
        queue_ui("status")


def tier_name(tier):
    mapping = {
        "1000": "Tier 1",
        "2000": "Tier 2",
        "3000": "Tier 3"
    }

    return mapping.get(str(tier), str(tier))


def on_twitch_message(ws, raw_message):
    try:
        data = json.loads(raw_message)

        message_type = (
            data
            .get("metadata", {})
            .get("message_type")
        )

        if message_type == "session_welcome":
            state["twitch"] = True
            queue_ui("status")
            log("Twitch EventSub conectado")

            session_id = (
                data["payload"]
                ["session"]
                ["id"]
            )

            if getattr(ws, "is_reconnect", False):
                # Na reconexão pedida pela Twitch as assinaturas são
                # transferidas sozinhas; recriá-las geraria erro 409.
                log("Reconexão da Twitch concluída; assinaturas mantidas")
            else:
                create_all_subscriptions(session_id)

        elif message_type == "notification":
            event_type = (
                data["payload"]
                ["subscription"]
                ["type"]
            )

            event = (
                data["payload"]
                ["event"]
            )

            if event_type != "channel.chat.message":
                log(f"Notificação recebida: {event_type}")

            if event_type == "channel.chat.message":
                username = event["chatter_user_name"]
                message_data = event.get("message", {})
                message_text = message_data.get("text", "")
                fragments = message_data.get("fragments", [])

                display = f"{username}: {message_text}"

                state["last_message"] = display
                state["chat_count"] += 1

                # EventSub já entrega os fragmentos dos emotes.
                # Convertemos para uma estrutura que o Canvas consegue
                # desenhar com as imagens oficiais da Twitch.
                overlay_parts = [
                    {
                        "kind": "text",
                        "text": f"{username}: "
                    }
                ]

                if not fragments:
                    overlay_parts.extend(_third_party_parts(message_text))

                for fragment in fragments:
                    fragment_type = fragment.get("type")

                    if fragment_type == "emote":
                        emote = fragment.get("emote", {})
                        emote_id = emote.get("id")

                        if emote_id:
                            emote_formats = emote.get("format", [])
                            overlay_parts.append({
                                "kind": "emote",
                                "id": emote_id,
                                "animated": "animated" in emote_formats
                            })
                        else:
                            overlay_parts.extend(
                                _third_party_parts(fragment.get("text", ""))
                            )
                    else:
                        overlay_parts.extend(
                            _third_party_parts(fragment.get("text", ""))
                        )

                # Quando é um Cheer, channel.cheer cria um aviso próprio com a
                # quantidade de Bits. Evita mostrar a mesma mensagem duas vezes.
                is_cheer_message = bool(event.get("cheer"))
                if not (is_cheer_message and state["bits"]):
                    add_overlay_message({
                        "parts": overlay_parts,
                        "text": display
                    })

                log(f"CHAT: {display}")
                queue_ui("status")

            elif event_type == "channel.channel_points_custom_reward_redemption.add":
                username = event["user_name"]
                reward = event["reward"]["title"]

                user_input = (
                    event.get(
                        "user_input",
                        ""
                    ).strip()
                )

                if user_input:
                    display = (
                        f"{username} — {reward} — "
                        f"{user_input}"
                    )

                    overlay_display = (
                        f"★ {username} resgatou "
                        f"{reward} — {user_input}"
                    )
                else:
                    display = f"{username} — {reward}"

                    overlay_display = (
                        f"★ {username} resgatou "
                        f"{reward}"
                    )

                state["last_reward"] = display
                state["reward_count"] += 1

                add_overlay_message(overlay_display)

                log(f"RESGATE: {display}")
                queue_ui("status")

            elif event_type == "channel.raid":
                username = event.get(
                    "from_broadcaster_user_name",
                    "Canal desconhecido"
                )

                try:
                    viewers = int(event.get("viewers", 0) or 0)
                except (TypeError, ValueError):
                    viewers = 0

                viewer_word = (
                    "espectador" if viewers == 1 else "espectadores"
                )
                display = (
                    f"{username} chegou com {viewers} {viewer_word}"
                )

                state["last_raid"] = display
                state["raid_count"] += 1

                add_overlay_message(f"RAID • {display}")

                log(f"RAID: {display}")
                queue_ui("status")

            elif event_type == "channel.cheer":
                username = event.get("user_name")
                if event.get("is_anonymous") or not username:
                    username = "Anônimo"

                try:
                    bits = int(event.get("bits", 0) or 0)
                except (TypeError, ValueError):
                    bits = 0

                bit_word = "Bit" if bits == 1 else "Bits"
                message = str(event.get("message") or "").strip()
                display = f"{username} enviou {bits} {bit_word}"

                if message:
                    display = f"{display} — {message}"

                state["last_bits"] = display
                state["bits_count"] += bits

                add_overlay_message(f"BITS • {display}")

                log(f"BITS: {display}")
                queue_ui("status")

            elif event_type == "channel.subscribe":
                if event.get("is_gift"):
                    return

                username = event.get(
                    "user_name",
                    "Desconhecido"
                )

                tier = tier_name(
                    event.get("tier", "?")
                )

                display = f"{username} — {tier}"

                state["last_sub"] = display
                state["sub_count"] += 1

                log(f"SUB: {display}")
                queue_ui("status")

            elif event_type == "channel.subscription.message":
                username = event.get(
                    "user_name",
                    "Desconhecido"
                )

                tier = tier_name(
                    event.get("tier", "?")
                )

                months = event.get(
                    "cumulative_months",
                    "?"
                )

                display = (
                    f"{username} — {tier} — "
                    f"{months} meses"
                )

                state["last_sub"] = display
                state["sub_count"] += 1

                log(f"RESUB: {display}")
                queue_ui("status")

            elif event_type == "channel.subscription.gift":
                username = event.get("user_name")

                if not username:
                    username = "Anônimo"

                total = event.get("total", 1)
                tier = tier_name(
                    event.get("tier", "?")
                )

                display = (
                    f"{username} presenteou "
                    f"{total} sub(s) — {tier}"
                )

                state["last_sub"] = display
                state["sub_count"] += int(total)

                log(f"GIFT SUB: {display}")
                queue_ui("status")

        elif message_type == "session_reconnect":
            reconnect_url = (
                data["payload"]
                ["session"]
                ["reconnect_url"]
            )

            log("Twitch solicitou reconexão")

            threading.Thread(
                target=twitch_loop,
                args=(reconnect_url, True),
                daemon=True
            ).start()

    except Exception as e:
        log(f"Erro Twitch: {e}")


def on_twitch_error(ws, error):
    if ws is not TWITCH_WS:
        return

    state["twitch"] = False
    state["chat"] = False
    state["rewards"] = False
    state["subs"] = False
    state["raids"] = False
    state["bits"] = False

    queue_ui("status")
    log(f"Erro WebSocket Twitch: {error}")


def on_twitch_close(ws, code, reason):
    if ws is not TWITCH_WS:
        # Socket antigo encerrado após a troca de sessão: é esperado.
        return

    state["twitch"] = False
    state["chat"] = False
    state["rewards"] = False
    state["subs"] = False
    state["raids"] = False
    state["bits"] = False

    queue_ui("status")
    log(f"Twitch desconectou: {code} {reason}")


TWITCH_WS = None
TWITCH_EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"
TWITCH_RETRY_SECONDS = 5


def start_twitch(url=TWITCH_EVENTSUB_URL, is_reconnect=False):
    global TWITCH_WS

    ws = websocket.WebSocketApp(
        url,
        on_message=on_twitch_message,
        on_error=on_twitch_error,
        on_close=on_twitch_close
    )
    ws.is_reconnect = is_reconnect
    TWITCH_WS = ws

    ws.run_forever()
    return ws


def twitch_loop(url=TWITCH_EVENTSUB_URL, is_reconnect=False):
    """Mantém o EventSub conectado, reconectando se a conexão cair."""
    while True:
        try:
            ws = start_twitch(url, is_reconnect)
        except Exception as e:
            log(f"Erro ao conectar na Twitch: {e}")
            ws = TWITCH_WS

        if ws is not TWITCH_WS:
            # Outra conexão assumiu (troca de sessão pedida pela Twitch).
            return

        log(
            f"Conexão com a Twitch caiu; "
            f"tentando de novo em {TWITCH_RETRY_SECONDS}s"
        )
        time.sleep(TWITCH_RETRY_SECONDS)
        url = TWITCH_EVENTSUB_URL
        is_reconnect = False


if THIRD_PARTY_EMOTES:
    threading.Thread(
        target=load_third_party_emotes,
        daemon=True
    ).start()


threading.Thread(
    target=twitch_loop,
    daemon=True
).start()



# =========================================================
# VISIBILIDADE / FOCO
# =========================================================

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_WINDOWS_PROCESS_PATH = 32768


def window_executable_name(hwnd):
    """Retorna o nome do executável responsável por uma janela do Windows."""
    if not hwnd:
        return ""

    process_id = wintypes.DWORD()
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    try:
        get_window_process_id = user32.GetWindowThreadProcessId
        get_window_process_id.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD)
        ]
        get_window_process_id.restype = wintypes.DWORD

        if not get_window_process_id(hwnd, ctypes.byref(process_id)):
            return ""

        open_process = kernel32.OpenProcess
        open_process.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD
        ]
        open_process.restype = wintypes.HANDLE

        query_process_path = kernel32.QueryFullProcessImageNameW
        query_process_path.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD)
        ]
        query_process_path.restype = wintypes.BOOL

        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        process_handle = open_process(
            PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            process_id.value
        )

        if not process_handle:
            return ""

        try:
            path_buffer = ctypes.create_unicode_buffer(
                MAX_WINDOWS_PROCESS_PATH
            )
            path_length = wintypes.DWORD(len(path_buffer))

            if not query_process_path(
                process_handle,
                0,
                path_buffer,
                ctypes.byref(path_length)
            ):
                return ""

            return os.path.basename(path_buffer.value)

        finally:
            close_handle(process_handle)

    except Exception:
        return ""


def is_gow_window(hwnd):
    """Aceita somente janelas pertencentes ao executável real do jogo."""
    return (
        window_executable_name(hwnd).casefold()
        == GAME_EXE.casefold()
    )


def capture_gow_return_window():
    global gow_return_hwnd

    try:
        hwnd = win32gui.GetForegroundWindow()

        if not hwnd:
            return False

        if is_gow_window(hwnd):
            gow_return_hwnd = hwnd
            return True

    except Exception:
        pass

    return False


def restore_gow_focus():
    """
    Tenta devolver o foreground ao God of War de forma mais robusta.
    """
    global gow_return_hwnd

    if not gow_return_hwnd:
        return False

    try:
        if not win32gui.IsWindow(
            gow_return_hwnd
        ):
            gow_return_hwnd = None
            return False

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        current_foreground = (
            win32gui.GetForegroundWindow()
        )

        current_thread = (
            kernel32.GetCurrentThreadId()
        )

        target_thread = user32.GetWindowThreadProcessId(
            gow_return_hwnd,
            None
        )

        foreground_thread = 0

        if current_foreground:
            foreground_thread = user32.GetWindowThreadProcessId(
                current_foreground,
                None
            )

        win32gui.ShowWindow(
            gow_return_hwnd,
            win32con.SW_RESTORE
        )

        # Anexa temporariamente os input queues para o Windows aceitar
        # a troca de foreground imediatamente.
        attached_target = False
        attached_foreground = False

        if target_thread and target_thread != current_thread:
            attached_target = bool(
                user32.AttachThreadInput(
                    current_thread,
                    target_thread,
                    True
                )
            )

        if (
            foreground_thread
            and foreground_thread != current_thread
            and foreground_thread != target_thread
        ):
            attached_foreground = bool(
                user32.AttachThreadInput(
                    current_thread,
                    foreground_thread,
                    True
                )
            )

        try:
            win32gui.BringWindowToTop(
                gow_return_hwnd
            )

            win32gui.SetForegroundWindow(
                gow_return_hwnd
            )

            user32.SetFocus(
                gow_return_hwnd
            )

        finally:
            if attached_target:
                user32.AttachThreadInput(
                    current_thread,
                    target_thread,
                    False
                )

            if attached_foreground:
                user32.AttachThreadInput(
                    current_thread,
                    foreground_thread,
                    False
                )

        return is_gow_foreground()

    except Exception:
        return False



def is_gow_foreground():
    try:
        hwnd = win32gui.GetForegroundWindow()

        if not hwnd:
            return False

        return is_gow_window(hwnd)

    except Exception:
        return False


def apply_overlay_visibility():
    """
    Chat visibility:
      - GoW foreground -> ON
      - F10 settings open -> ON
      - F11 Live Control open -> ON
      - Always show messages -> ON
      - OBS / Opera / desktop / other apps -> OFF
    """

    try:
        gow_focus = is_gow_foreground()
    except Exception:
        gow_focus = False

    settings_open = False

    try:
        settings_open = (
            settings_window is not None
            and settings_window.winfo_exists()
            and settings_window.state() != "withdrawn"
        )
    except Exception:
        pass

    show_messages = SHOW_CHAT and bool(
        gow_focus
        or settings_open
        or dashboard_panel_visible
        or ALWAYS_SHOW_OVERLAY
    )

    try:
        if show_messages:
            root.deiconify()
            if SHOW_HINT:
                hint_root.deiconify()
            else:
                hint_root.withdraw()
        else:
            root.withdraw()
            hint_root.withdraw()
    except Exception:
        pass


# =========================================================
# FOCO
# =========================================================

def window_or_child_is_focused(hwnd):
    if not hwnd:
        return False

    try:
        foreground = win32gui.GetForegroundWindow()

        if not foreground:
            return False

        if foreground == hwnd:
            return True

        # Sobe pela hierarquia de janelas para detectar
        # controles/filhos pertencentes ao painel.
        current = foreground

        for _ in range(12):
            parent = win32gui.GetParent(current)

            if not parent:
                break

            if parent == hwnd:
                return True

            current = parent

        # Também compara a janela raiz do foreground.
        GA_ROOT = 2

        root_hwnd = ctypes.windll.user32.GetAncestor(
            foreground,
            GA_ROOT
        )

        return root_hwnd == hwnd

    except Exception:
        return False


def gow_is_focused():
    return is_gow_foreground()


last_active = None
last_focus_text = None

menu_hold_dp = False
dashboard_panel_visible = True
release_hold_when_gow_returns = False
gow_return_hwnd = None



def update_focus():

    global last_active
    global last_focus_text
    global menu_hold_dp
    global release_hold_when_gow_returns


    gow_focus = is_gow_foreground()


    settings_focus = False

    try:
        settings_focus = (
            settings_window is not None
            and settings_window.winfo_exists()
            and window_or_child_is_focused(
                settings_hwnd
            )
        )
    except Exception:
        settings_focus = False


    dashboard_focus = False

    try:
        dashboard_focus = (
            dashboard.state() not in (
                "withdrawn",
                "iconic"
            )
            and window_or_child_is_focused(
                dashboard_hwnd
            )
        )
    except Exception:
        dashboard_focus = False


    # -----------------------------------------------------
    # DP:
    # - GoW em foco -> ON
    # - F10/F11 só mantêm ON se foram abertos A PARTIR do GoW
    # - Abrir menu a partir do OBS/desktop NÃO liga DP
    # -----------------------------------------------------

    dp_active = CONTROL_DP and (
        gow_focus
        or menu_hold_dp
    )


    if dp_active != last_active:

        set_dp(
            dp_active
        )

        last_active = dp_active


    # Se ocultamos F10/F11 vindo do GoW, NÃO desligamos DP
    # durante a transição. Só soltamos o hold quando o jogo
    # estiver confirmado como foreground.
    if (
        release_hold_when_gow_returns
        and gow_focus
    ):
        menu_hold_dp = False
        release_hold_when_gow_returns = False


    # -----------------------------------------------------
    # MENSAGENS:
    # continuam obedecendo a regra visual independente
    # -----------------------------------------------------

    apply_overlay_visibility()


    state["gow_focus"] = gow_focus


    if not SHOW_CHAT and CONTROL_DP:
        focus_text = (
            "Controle DP ativo; exibição do chat desligada"
        )

    elif not CONTROL_DP:

        focus_text = (
            "Leitura de chat ativa; controle DP desligado"
        )

    elif gow_focus:

        focus_text = (
            "God of War foco -> DP ON + Chat ON"
        )

    elif settings_focus:

        if menu_hold_dp:
            focus_text = (
                "Configurações foco -> DP mantido ON"
            )
        else:
            focus_text = (
                "Configurações foco -> DP preservado"
            )

    elif dashboard_focus:

        if menu_hold_dp:
            focus_text = (
                "Painel foco -> DP mantido ON"
            )
        else:
            focus_text = (
                "Painel foco -> DP preservado"
            )

    else:

        focus_text = (
            "GoW/Painel saiu -> DP OFF"
        )


    if focus_text != last_focus_text:

        log(
            focus_text
        )

        last_focus_text = focus_text


    if dashboard.state() != "withdrawn":

        refresh_dashboard()


    root.after(
        300,
        update_focus
    )


# =========================================================
# START
# =========================================================


log("GoW Overlay iniciado")
log(f"Canal: {CHANNEL_LOGIN}")

if REQUIRED_SUB_SCOPE not in TOKEN_SCOPES:
    log(
        "ATENÇÃO: para mostrar subs, autorize "
        "channel:read:subscriptions"
    )

if REQUIRED_BITS_SCOPE not in TOKEN_SCOPES:
    log(
        "ATENÇÃO: para mostrar Cheers/Bits, autorize bits:read"
    )

process_overlay_queue()
process_ui_queue()
check_f9()
check_hotkeys()
update_focus()

dashboard_panel_visible = False

dashboard.withdraw()

start_tray_icon()

root.mainloop()
