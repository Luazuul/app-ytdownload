import os
import subprocess
import shlex
import json
import re
from pytube import YouTube, Playlist
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import asyncio

CONFIG_FILE = 'config.json'

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def load_config():
    return json.load(open(CONFIG_FILE)) if os.path.exists(CONFIG_FILE) else {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as file:
        json.dump(config, file)

def download_stream(stream, output_path, filename, progress_callback=None):
    stream.download(output_path=output_path, filename=filename)
    return os.path.join(output_path, filename)

def progress_function(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    progress_bar['value'] = int(bytes_downloaded / total_size * 100)
    app.update_idletasks()

def update_status_label(message):
    status_label.config(text=message)
    app.update_idletasks()

async def baixar_video_async(url, path, resolution, download_audio_only, download_subtitles, status_label):
    try:
        yt = YouTube(url, on_progress_callback=progress_function)
        sanitized_title = sanitize_filename(yt.title)

        if download_audio_only:
            audio_stream = yt.streams.filter(only_audio=True).first()
            if not audio_stream:
                update_status_label('Stream de áudio não encontrado.')
                return

            if not os.path.exists(path):
                os.makedirs(path)

            update_status_label(f'Baixando áudio de: {yt.title}')
            progress_bar['value'] = 0

            audio_path = download_stream(audio_stream, path, 'audio.mp4')

            if download_subtitles:
                subtitle = yt.captions.get_by_language_code('en')
                if subtitle:
                    with open(os.path.join(path, sanitized_title + ".srt"), "w", encoding="utf-8") as file:
                        file.write(subtitle.generate_srt_captions())
                    update_status_label('Legendas baixadas com sucesso.')
                else:
                    update_status_label('Legendas não encontradas.')

            update_status_label('Download de áudio concluído!')
            final_path = os.path.join(path, sanitized_title + ".mp3")
            subprocess.run(shlex.split(f'ffmpeg -i "{audio_path}" -c:a libmp3lame -q:a 2 "{final_path}"'), check=True)

            os.remove(audio_path)
            update_status_label('Áudio final convertido com sucesso!')
            btn_abrir_pasta['state'] = 'normal'

        else:
            video_stream = yt.streams.filter(res=resolution, progressive=False, file_extension='mp4').first()
            if not video_stream:
                update_status_label(f'Stream de {resolution} não encontrado, tente outra resolução.')
                return

            audio_stream = yt.streams.filter(only_audio=True, file_extension='mp4').first()
            if not audio_stream:
                update_status_label('Stream de áudio não encontrado.')
                return

            if not os.path.exists(path):
                os.makedirs(path)

            update_status_label(f'Baixando vídeo: {yt.title}')
            progress_bar['value'] = 0

            loop = asyncio.get_event_loop()
            video_task = loop.run_in_executor(None, download_stream, video_stream, path, 'video.mp4', progress_function)
            audio_task = loop.run_in_executor(None, download_stream, audio_stream, path, 'audio.mp4')

            video_path, audio_path = await asyncio.gather(video_task, audio_task)

            if download_subtitles:
                subtitle = yt.captions.get_by_language_code('en')
                if subtitle:
                    with open(os.path.join(path, sanitized_title + ".srt"), "w", encoding="utf-8") as file:
                        file.write(subtitle.generate_srt_captions())
                    update_status_label('Legendas baixadas com sucesso.')
                else:
                    update_status_label('Legendas não encontradas.')

            update_status_label('Finalizando...')
            final_path = os.path.join(path, sanitized_title + ".mp4")
            subprocess.run(shlex.split(f'ffmpeg -i "{video_path}" -i "{audio_path}" -c:v copy -c:a aac "{final_path}"'), check=True)

            os.remove(video_path)
            os.remove(audio_path)
            update_status_label('Downloade concluído!')
            btn_abrir_pasta['state'] = 'normal'

    except Exception as e:
        update_status_label(f'Erro ao baixar o vídeo: {e}')

async def baixar_playlist_async(url, path, resolution, download_audio_only, download_subtitles, status_label):
    try:
        playlist = Playlist(url)
        for video_url in playlist.video_urls:
            await baixar_video_async(video_url, path, resolution, download_audio_only, download_subtitles, status_label)
        update_status_label('Download da playlist concluído!')
    except Exception as e:
        update_status_label(f'Erro ao baixar a playlist: {e}')

def iniciar_download():
    url, path = url_entry.get(), path_entry.get()
    resolution, download_audio_only, download_subtitles = resolution_var.get(), audio_only_var.get(), subtitles_var.get()
    if not url or not path:
        messagebox.showerror("Erro", "Por favor, insira a URL e o diretório de destino.")
        return
    status_label.config(text='Iniciando o download...')
    threading.Thread(target=lambda: asyncio.run(
        baixar_playlist_async(url, path, resolution, download_audio_only, download_subtitles, status_label) if 'playlist' in url else baixar_video_async(url, path, resolution, download_audio_only, download_subtitles, status_label)
    )).start()

def escolher_diretorio():
    path = filedialog.askdirectory()
    if path:
        path_entry.delete(0, tk.END)
        path_entry.insert(0, path)
        config = load_config()
        config['last_directory'] = path
        save_config(config)

def abrir_pasta_destino():
    if (path := path_entry.get()):
        subprocess.Popen(['explorer', os.path.realpath(path)])

# Carregar a última configuração
last_directory = load_config().get('last_directory', '')

app = ttk.Window(themename="darkly")
app.title("YouTube Video Downloader")
app.geometry("500x550")

ttk.Label(app, text="URL do vídeo ou playlist do YouTube:").pack(pady=5)
url_entry = ttk.Entry(app, width=50)
url_entry.pack(pady=5)

ttk.Label(app, text="Diretório de destino:").pack(pady=5)
path_entry = ttk.Entry(app, width=50)
path_entry.pack(pady=5)
path_entry.insert(0, last_directory)

ttk.Button(app, text="Escolher Diretório", command=escolher_diretorio).pack(pady=5)

ttk.Label(app, text="Resolução (somente para vídeo):").pack(pady=5)
resolution_var = tk.StringVar(value='1080p')
resolution_menu = ttk.Combobox(app, textvariable=resolution_var, values=['360p', '480p', '720p', '1080p'])
resolution_menu.pack(pady=5)

audio_only_var = tk.BooleanVar()
ttk.Checkbutton(app, text="Baixar apenas o áudio", variable=audio_only_var).pack(pady=5)

subtitles_var = tk.BooleanVar()
ttk.Checkbutton(app, text="Baixar legendas (se disponíveis)", variable=subtitles_var).pack(pady=5)

ttk.Button(app, text="Iniciar Download", command=iniciar_download).pack(pady=10)

status_label = ttk.Label(app, text="", foreground="blue")
status_label.pack(pady=5)

progress_bar = ttk.Progressbar(app, orient=HORIZONTAL, length=400, mode='determinate')
progress_bar.pack(pady=10)

btn_abrir_pasta = ttk.Button(app, text="Abrir Pasta de Destino", command=abrir_pasta_destino, state='disabled')
btn_abrir_pasta.pack(pady=5)

# Adicionando o texto "Beta 1.0" no canto inferior direito
beta_label = ttk.Label(app, text="v1.1", foreground="gray")
beta_label.place(relx=1.0, rely=1.0, anchor='se')

app.mainloop()
