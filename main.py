import os
import subprocess
import numpy as np
import wave
import threading
import shutil
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.core.window import Window
from kivy.clock import Clock

OUTPUT_DIR = "/storage/emulated/0/TwitchClips"
os.makedirs(OUTPUT_DIR, exist_ok=True)
Window.clearcolor = (0.05, 0.05, 0.1, 1)


def find_ffmpeg():
    """Ищет ffmpeg в разных местах"""
    candidates = [
        "ffmpeg",
        "/data/data/com.errorpromts.twitchclipper/files/ffmpeg",
        "/data/data/org.test.twitchclipper/files/ffmpeg",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg"),
    ]
    for c in candidates:
        if shutil.which(c) or os.path.exists(c):
            return c
    return "ffmpeg"


FFMPEG = find_ffmpeg()


def extract_audio(video):
    wav = "/tmp/a.wav"
    try:
        subprocess.run([FFMPEG, "-y", "-i", video, "-ac", "1", "-ar", "16000", wav],
                       capture_output=True, timeout=600)
        return wav if os.path.exists(wav) else None
    except:
        return None


def analyze(wav):
    try:
        with wave.open(wav, "rb") as w:
            sr = w.getframerate()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    except:
        return []
    out, prev = [], 0
    for i in range(0, len(data) - sr, sr):
        rms = float(np.sqrt(np.mean(data[i:i+sr] ** 2)))
        out.append({"t": i // sr, "v": rms, "s": prev > 0 and rms / prev > 3})
        prev = rms
    if out:
        mx = max(x["v"] for x in out)
        if mx > 0:
            for x in out:
                x["v"] /= mx
    return out


def peaks(vol):
    p, last = [], -45000
    for i, x in enumerate(vol):
        if (x["v"] >= 0.75 or x["s"]) and (i - last) >= 45:
            p.append(x)
            last = i
    return p


def cut(video, start, out):
    try:
        subprocess.run([FFMPEG, "-y", "-ss", str(start), "-i", video, "-t", "30",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", out],
                       capture_output=True, timeout=600)
        return os.path.exists(out)
    except:
        return False


def overlay(inp, out, name):
    n = name.replace(":", "").replace("'", "")[:30]
    f = ("[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
         "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[bg];"
         "[bg]drawtext=text='" + n + "':fontcolor=white:fontsize=64:"
         "x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.6:boxborderw=20[f]")
    try:
        subprocess.run([FFMPEG, "-y", "-i", inp, "-filter_complex", f, "-map", "[f]",
                        "-map", "0:a?", "-c:v", "libx264", "-preset", "ultrafast",
                        "-c:a", "aac", "-shortest", out], capture_output=True, timeout=600)
        return os.path.exists(out)
    except:
        return False


def run(video, name, cb):
    cb("Аудио...", 5)
    wav = extract_audio(video)
    if not wav:
        cb("Ошибка аудио", 0)
        return []
    cb("Анализ...", 20)
    vol = analyze(wav)
    if not vol:
        cb("Ошибка", 0)
        return []
    cb("Поиск...", 40)
    p = peaks(vol)
    if not p:
        cb("Не найдено", 0)
        return []
    p = sorted(p, key=lambda x: x["v"], reverse=True)[:10]
    p.sort(key=lambda x: x["t"])
    clips = []
    total = len(p)
    for i, x in enumerate(p):
        start = max(0, x["t"] - 15)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw = os.path.join(OUTPUT_DIR, "r" + str(i) + ".mp4")
        fin = os.path.join(OUTPUT_DIR, "clip_" + str(i+1) + "_" + ts + ".mp4")
        if cut(video, start, raw):
            overlay(raw, fin, name)
            try:
                os.remove(raw)
            except:
                pass
            clips.append(fin)
        cb("Клип " + str(i+1) + "/" + str(total), 40 + int(60 * (i+1) / total))
    try:
        os.remove(wav)
    except:
        pass
    cb("Готово! " + str(len(clips)), 100)
    return clips


class App1(App):
    def build(self):
        self.video = None
        box = BoxLayout(orientation="vertical", padding=20, spacing=10)
        box.add_widget(Label(text="TWITCH CLIPPER", font_size=28, color=(1, 0.8, 0.2, 1), size_hint=(1, 0.1)))
        self.ch = TextInput(text="Twitch", multiline=False, size_hint=(1, 0.1))
        box.add_widget(self.ch)
        b1 = Button(text="ВЫБРАТЬ ВИДЕО", size_hint=(1, 0.15), background_color=(0.2, 0.3, 0.6, 1))
        b1.bind(on_press=self.pick)
        box.add_widget(b1)
        b2 = Button(text="НАРЕЗАТЬ", size_hint=(1, 0.15), background_color=(0.5, 0.2, 0.8, 1))
        b2.bind(on_press=self.go)
        box.add_widget(b2)
        self.pb = ProgressBar(max=100, size_hint=(1, 0.05))
        box.add_widget(self.pb)
        self.st = Label(text="Готов", size_hint=(1, 0.1))
        box.add_widget(self.st)
        return box

    def pick(self, x):
        c = BoxLayout(orientation="vertical")
        fc = FileChooserListView(filters=["*.mp4", "*.mkv", "*.mov"], path="/storage/emulated/0")
        c.add_widget(fc)
        p = Popup(title="Видео", content=c, size_hint=(0.95, 0.95))

        def sel(_):
            if fc.selection:
                self.video = fc.selection[0]
                self.st.text = "OK " + os.path.basename(self.video)[:25]
            p.dismiss()

        b = Button(text="ОК", size_hint=(1, 0.2))
        b.bind(on_press=sel)
        c.add_widget(b)
        p.open()

    def go(self, x):
        if not self.video:
            self.st.text = "Выбери видео"
            return
        threading.Thread(target=self.work, daemon=True).start()

    def work(self):
        def cb(t, v):
            Clock.schedule_once(lambda dt: self.upd(t, v))
        run(self.video, self.ch.text or "Twitch", cb)

    def upd(self, t, v):
        self.st.text = t
        self.pb.value = v


if __name__ == "__main__":
    App1().run()
