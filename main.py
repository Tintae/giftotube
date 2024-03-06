import threading
from tkinter import filedialog, messagebox, PhotoImage
from moviepy.editor import *
import tkinter as tk
from tkinter import ttk
import queue
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import webbrowser
import configparser

from tkcalendar import DateEntry


def load_api_keys():
    config = configparser.ConfigParser()
    config.read("config.ini")
    client_id = config.get("API", "client_id", fallback="")
    client_secret = config.get("API", "client_secret", fallback="")
    return client_id, client_secret

def save_api_keys(client_id, client_secret):
    config = configparser.ConfigParser()
    config.read("config.ini")
    if not config.has_section("API"):
        config.add_section("API")
    config.set("API", "client_id", client_id)
    config.set("API", "client_secret", client_secret)
    with open("config.ini", "w") as config_file:
        config.write(config_file)

def create_video(audio_path, gif_path, output_path, progress_queue, settings):
    try:
        audio_clip = AudioFileClip(audio_path)
        progress_queue.put(10)

        gif_clip = VideoFileClip(gif_path)
        gif_width, gif_height = gif_clip.size
        aspect_ratio = gif_width / gif_height
        new_height = settings["height"] if settings["custom_resolution"] else 720
        new_width = int(new_height * aspect_ratio)
        gif_clip = gif_clip.resize((new_width, new_height))
        progress_queue.put(40)

        video_width = settings["width"] if settings["custom_resolution"] else 1280
        video_height = settings["height"] if settings["custom_resolution"] else 720
        position = ((video_width - new_width) // 2, (video_height - new_height) // 2)
        background_clip = ColorClip(size=(video_width, video_height), color=(0, 0, 0))
        background_clip = background_clip.set_duration(audio_clip.duration)
        gif_clip = gif_clip.loop(duration=audio_clip.duration)
        final_clip = CompositeVideoClip(
            [background_clip, gif_clip.set_position(position)]
        )
        final_clip = final_clip.set_audio(audio_clip)
        progress_queue.put(70)

        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="ultrafast" if not settings["high_quality"] else "slow",
        )
        progress_queue.put(100)

        messagebox.showinfo("Success", "Video created successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create video: {e}")
        progress_queue.put(-1)


class YouTubeUploaderFrame(tk.Toplevel):
    def __init__(self, master=None, video_path=None):
        super().__init__(master)
        self.video_path = video_path
        self.title("Upload to YouTube")
        self.geometry("400x750")  # Increase the height to accommodate new widgets
        self.configure(bg="#f0f0f0")
        self.create_widgets()
        self.load_api_keys()

    def create_widgets(self):
        style = ttk.Style()
        style.configure(
            "TLabel", background="#f0f0f0", foreground="#333333", font=("Helvetica", 12)
        )
        style.configure(
            "TButton", background="#4CAF50", foreground="white", font=("Helvetica", 12)
        )
        style.map("TButton", background=[("active", "#3e8e41")])
        style.configure(
            "TEntry", fieldbackground="white", foreground="#333333", padding=5
        )

        self.client_id_label = ttk.Label(self, text="Client ID:")
        self.client_id_label.pack(side="top", pady=10)
        CreateToolTip(self.client_id_label, "Enter your Google API Client ID")

        self.client_id_entry = ttk.Entry(self, width=40)
        self.client_id_entry.pack(side="top", pady=5)

        self.client_secret_label = ttk.Label(self, text="Client Secret:")
        self.client_secret_label.pack(side="top", pady=10)
        CreateToolTip(self.client_secret_label, "Enter your Google API Client Secret")

        self.client_secret_entry = ttk.Entry(self, width=40, show="*")
        self.client_secret_entry.pack(side="top", pady=5)

        self.api_button_frame = ttk.Frame(self)
        self.api_button_frame.pack(side="top", pady=5)

        self.api_button = ttk.Button(
            self.api_button_frame,
            text="Google API Console",
            command=self.open_api_console,
        )
        self.api_button.pack(side="left", padx=5)
        CreateToolTip(
            self.api_button,
            "Open the Google API Console to create or manage your API credentials",
        )

        self.title_label = ttk.Label(self, text="Title:")
        self.title_label.pack(side="top", pady=10)
        CreateToolTip(self.title_label, "Enter the title for your YouTube video")

        self.title_entry = ttk.Entry(self, width=40)
        self.title_entry.pack(side="top", pady=5)

        self.description_label = ttk.Label(self, text="Description:")
        self.description_label.pack(side="top", pady=10)
        CreateToolTip(
            self.description_label, "Enter the description for your YouTube video"
        )

        self.description_entry = ttk.Entry(self, width=40)
        self.description_entry.pack(side="top", pady=5)

        self.tags_label = ttk.Label(self, text="Tags (comma-separated):")
        self.tags_label.pack(side="top", pady=10)
        CreateToolTip(
            self.tags_label, "Enter tags for your YouTube video, separated by commas"
        )

        self.tags_entry = ttk.Entry(self, width=40)
        self.tags_entry.pack(side="top", pady=5)

        self.privacy_label = ttk.Label(self, text="Privacy:")
        self.privacy_label.pack(side="top", pady=10)
        CreateToolTip(self.privacy_label, "Select the privacy setting for your video")

        self.privacy_var = tk.StringVar(value="private")
        self.privacy_frame = ttk.Frame(self)
        self.privacy_frame.pack(side="top", pady=5)

        self.private_radio = ttk.Radiobutton(
            self.privacy_frame,
            text="Private",
            variable=self.privacy_var,
            value="private"
        )
        self.private_radio.pack(side="left", padx=5)

        self.unlisted_radio = ttk.Radiobutton(
            self.privacy_frame,
            text="Unlisted",
            variable=self.privacy_var,
            value="unlisted"
        )
        self.unlisted_radio.pack(side="left", padx=5)

        self.public_radio = ttk.Radiobutton(
            self.privacy_frame,
            text="Public",
            variable=self.privacy_var,
            value="public"
        )
        self.public_radio.pack(side="left", padx=5)

        self.schedule_label = ttk.Label(self, text="Schedule:")
        self.schedule_label.pack(side="top", pady=10)
        CreateToolTip(self.schedule_label, "Select the date and time to schedule your video (optional)")

        self.schedule_frame = ttk.Frame(self)
        self.schedule_frame.pack(side="top", pady=5)

        self.date_label = ttk.Label(self.schedule_frame, text="Date:")
        self.date_label.pack(side="left", padx=5)
        self.date_entry = DateEntry(self.schedule_frame, width=12, background='darkblue', foreground='white', borderwidth=2)
        self.date_entry.pack(side="left", padx=5)

        self.time_label = ttk.Label(self.schedule_frame, text="Time (HH:MM):")
        self.time_label.pack(side="left", padx=5)
        self.time_entry = ttk.Entry(self.schedule_frame, width=8)
        self.time_entry.pack(side="left", padx=5)

        self.upload_button = ttk.Button(self, text="Upload", command=self.start_upload)
        self.upload_button.pack(side="top", pady=20)
        CreateToolTip(self.upload_button, "Start the video upload to YouTube")

        self.cancel_button = ttk.Button(self, text="Cancel", command=self.destroy)
        self.cancel_button.pack(side="top", pady=10)
        CreateToolTip(self.cancel_button, "Cancel the upload and close the window")

    def load_api_keys(self):
        client_id, client_secret = load_api_keys()
        self.client_id_entry.delete(0, tk.END)
        self.client_id_entry.insert(0, client_id)
        self.client_secret_entry.delete(0, tk.END)
        self.client_secret_entry.insert(0, client_secret)

    def open_api_console(self):
        webbrowser.open("https://console.developers.google.com/apis/dashboard")

    def start_upload(self):
        client_id = self.client_id_entry.get()
        client_secret = self.client_secret_entry.get()
        title = self.title_entry.get()
        description = self.description_entry.get()
        tags = [tag.strip() for tag in self.tags_entry.get().split(",")]
        privacy_status = self.privacy_var.get()

        schedule_date = self.date_entry.get_date()
        schedule_time = self.time_entry.get()

        if schedule_date and schedule_time:
            publish_at = f"{schedule_date.isoformat()}T{schedule_time}:00.000Z"
        else:
            publish_at = None

        client_secrets = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        uploader = YouTubeUploader(
            self.video_path, title, description, tags, privacy_status, publish_at, client_secrets
        )
        threading.Thread(target=uploader.upload_video).start()
        save_api_keys(client_id, client_secret)
        # Clear the entry fields for the next upload
        self.title_entry.delete(0, tk.END)
        self.description_entry.delete(0, tk.END)
        self.tags_entry.delete(0, tk.END)

class YouTubeUploader:
    def __init__(self, video_path, title, description, tags, privacy_status, publish_at, client_secrets):
        self.video_path = video_path
        self.title = title
        self.description = description
        self.tags = tags
        self.privacy_status = privacy_status
        self.publish_at = publish_at
        self.client_secrets = client_secrets
        self.youtube = self.get_authenticated_service()

    def get_authenticated_service(self):
        credentials = None
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                credentials = pickle.load(token)
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(
                    self.client_secrets, ["https://www.googleapis.com/auth/youtube.upload"]
                )
                credentials = flow.run_local_server(port=0)
            with open("token.pickle", "wb") as token:
                pickle.dump(credentials, token)
        return build("youtube", "v3", credentials=credentials)

    def upload_video(self):
        body = {
            "snippet": {
                "title": self.title,
                "description": self.description,
                "tags": self.tags,
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": self.privacy_status,
                "publishAt": self.publish_at
            }
        }

        insert_request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=MediaFileUpload(self.video_path, chunksize=-1, resumable=True)
        )

        response = None
        while response is None:
            status, response = insert_request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%.")

        print(f"Video uploaded successfully. Video ID: {response['id']}")


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("Audio GIF Converter 3.0")
        self.master.geometry("600x600")
        self.master.configure(bg="#f0f0f0")
        self.pack(fill="both", expand=True, padx=20, pady=20)
        self.settings = {
            "high_quality": False,
            "custom_resolution": False,
            "width": 1280,
            "height": 720,
        }
        self.create_widgets()
        self.youtube_frame = None

    def create_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TLabel", background="#f0f0f0", foreground="#333333", font=("Helvetica", 12)
        )
        style.configure(
            "TButton",
            background="#4CAF50",
            foreground="white",
            font=("Helvetica", 12),
            padding=10,
        )
        style.map(
            "TButton", background=[("active", "#3e8e41"), ("disabled", "#cccccc")]
        )
        style.configure(
            "TEntry", fieldbackground="white", foreground="#333333", padding=5
        )
        style.configure("TProgressbar", background="#4CAF50", troughcolor="#f0f0f0")

        self.audio_frame = ttk.Frame(self)
        self.audio_frame.pack(side="top", pady=10)

        self.audio_label = ttk.Label(self.audio_frame, text="Audio File:")
        self.audio_label.pack(side="left", padx=10)
        CreateToolTip(self.audio_label, "Select the audio file for your video")

        self.audio_entry = ttk.Entry(self.audio_frame, width=40)
        self.audio_entry.pack(side="left", padx=10)

        self.browse_audio_button = ttk.Button(
            self.audio_frame, text="Browse", command=self.browse_audio
        )
        self.browse_audio_button.pack(side="left", padx=10)

        self.gif_frame = ttk.Frame(self)
        self.gif_frame.pack(side="top", pady=10)

        self.gif_label = ttk.Label(self.gif_frame, text="GIF File:")
        self.gif_label.pack(side="left", padx=10)
        CreateToolTip(self.gif_label, "Select the GIF file for your video")

        self.gif_entry = ttk.Entry(self.gif_frame, width=40)
        self.gif_entry.pack(side="left", padx=10)

        self.browse_gif_button = ttk.Button(
            self.gif_frame, text="Browse", command=self.browse_gif
        )
        self.browse_gif_button.pack(side="left", padx=10)

        self.output_frame = ttk.Frame(self)
        self.output_frame.pack(side="top", pady=10)

        self.output_label = ttk.Label(self.output_frame, text="Output File:")
        self.output_label.pack(side="left", padx=10)
        CreateToolTip(self.output_label, "Specify the output video file path")

        self.output_entry = ttk.Entry(self.output_frame, width=40)
        self.output_entry.pack(side="left", padx=10)

        self.browse_output_button = ttk.Button(
            self.output_frame, text="Browse", command=self.browse_output
        )
        self.browse_output_button.pack(side="left", padx=10)

        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side="top", pady=20)

        self.start_button = ttk.Button(
            self.button_frame, text="Start Conversion", command=self.start_conversion
        )
        self.start_button.pack(side="left", padx=10)
        CreateToolTip(self.start_button, "Start the video conversion process")

        self.preview_button = ttk.Button(
            self.button_frame, text="Preview", command=self.preview_video
        )
        self.preview_button.pack(side="left", padx=10)
        self.preview_button.state(["disabled"])
        CreateToolTip(self.preview_button, "Preview the converted video")

        self.settings_button = ttk.Button(
            self.button_frame, text="Settings", command=self.open_settings
        )
        self.settings_button.pack(side="left", padx=10)
        CreateToolTip(self.settings_button, "Open the settings window")

        self.youtube_button = ttk.Button(
            self.button_frame,
            text="Post",
            command=self.open_youtube_uploader,
        )
        self.youtube_button.pack(side="left", padx=10)
        self.youtube_button.state(["disabled"])
        CreateToolTip(self.youtube_button, "Open the YouTube upload window")

        self.progress_bar = ttk.Progressbar(
            self, orient="horizontal", length=500, mode="determinate"
        )
        self.progress_bar.pack(side="top", pady=10)

        self.status_label = ttk.Label(self, text="", font=("Helvetica", 12))
        self.status_label.pack(side="top", pady=10)

    def browse_audio(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Audio Files", "*.mp3;*.wav;*.m4a")]
        )
        self.audio_entry.delete(0, tk.END)
        self.audio_entry.insert(0, file_path)

    def browse_gif(self):
        file_path = filedialog.askopenfilename(filetypes=[("GIF Files", "*.gif")])
        self.gif_entry.delete(0, tk.END)
        self.gif_entry.insert(0, file_path)

    def browse_output(self):
        output_path = filedialog.asksaveasfilename(
            defaultextension=".mp4", filetypes=[("Video Files", "*.mp4")]
        )
        self.output_entry.delete(0, tk.END)
        self.output_entry.insert(0, output_path)

    def start_conversion(self):
        if self.audio_entry.get() and self.gif_entry.get() and self.output_entry.get():
            self.status_label.config(text="Converting...")
            self.start_button.state(["disabled"])
            self.progress_bar["value"] = 0
            self.convert_video(
                self.audio_entry.get(), self.gif_entry.get(), self.output_entry.get()
            )
        else:
            messagebox.showwarning("Warning", "Please select all required files.")

    def convert_video(self, audio_path, gif_path, output_path):
        progress_queue = queue.Queue()

        def update_progress():
            try:
                progress = progress_queue.get(block=False)
                if progress == -1:
                    self.status_label.config(text="Failed to create video.")
                    self.start_button.state(["!disabled"])
                    self.preview_button.state(["disabled"])
                    self.youtube_button.state(["disabled"])
                elif progress == 100:
                    self.progress_bar["value"] = progress
                    self.status_label.config(text="Conversion completed.")
                    self.start_button.state(["!disabled"])
                    self.preview_button.state(["!disabled"])
                    self.youtube_button.state(["!disabled"])
                else:
                    self.progress_bar["value"] = progress
                    self.master.after(100, update_progress)
            except queue.Empty:
                self.master.after(100, update_progress)

        threading.Thread(
            target=create_video,
            args=(audio_path, gif_path, output_path, progress_queue, self.settings),
        ).start()
        update_progress()

    def preview_video(self):
        output_path = self.output_entry.get()
        if os.path.isfile(output_path):
            os.startfile(output_path)
        else:
            messagebox.showerror("Error", "Output video file not found.")

    def open_settings(self):
        settings_window = SettingsWindow(self.master, self.settings)
        self.master.wait_window(settings_window)

    def open_youtube_uploader(self):
        self.youtube_frame = YouTubeUploaderFrame(
            self.master, self.output_entry.get()
        )


class SettingsWindow(tk.Toplevel):
    def __init__(self, master=None, settings=None):
        super().__init__(master)
        self.settings = settings
        self.title("Settings")
        self.geometry("400x300")
        self.configure(bg="#f0f0f0")
        self.create_widgets()

    def create_widgets(self):
        style = ttk.Style()
        style.configure(
            "TLabel", background="#f0f0f0", foreground="#333333", font=("Helvetica", 12)
        )
        style.configure(
            "TButton", background="#4CAF50", foreground="white", font=("Helvetica", 12)
        )
        style.map("TButton", background=[("active", "#3e8e41")])
        style.configure("TCheckbutton", background="#f0f0f0", foreground="#333333")

        self.high_quality_var = tk.BooleanVar(value=self.settings["high_quality"])
        self.high_quality_checkbox = ttk.Checkbutton(
            self, text="High Quality Output", variable=self.high_quality_var
        )
        self.high_quality_checkbox.pack(side="top", pady=10)
        CreateToolTip(
            self.high_quality_checkbox, "Enable high quality output (slower conversion)"
        )

        self.custom_resolution_var = tk.BooleanVar(
            value=self.settings["custom_resolution"]
        )
        self.custom_resolution_checkbox = ttk.Checkbutton(
            self,
            text="Custom Resolution",
            variable=self.custom_resolution_var,
            command=self.toggle_resolution_fields,
        )
        self.custom_resolution_checkbox.pack(side="top", pady=10)
        CreateToolTip(
            self.custom_resolution_checkbox, "Set custom output video resolution"
        )

        self.resolution_frame = ttk.Frame(self)
        self.resolution_frame.pack(side="top", pady=10)

        self.width_label = ttk.Label(self.resolution_frame, text="Width:")
        self.width_label.pack(side="left", padx=5)

        self.width_entry = ttk.Entry(self.resolution_frame, width=10)
        self.width_entry.pack(side="left", padx=5)
        self.width_entry.insert(0, str(self.settings["width"]))

        self.height_label = ttk.Label(self.resolution_frame, text="Height:")
        self.height_label.pack(side="left", padx=5)

        self.height_entry = ttk.Entry(self.resolution_frame, width=10)
        self.height_entry.pack(side="left", padx=5)
        self.height_entry.insert(0, str(self.settings["height"]))

        self.toggle_resolution_fields()

        self.save_button = ttk.Button(self, text="Save", command=self.save_settings)
        self.save_button.pack(side="top", pady=20)
        CreateToolTip(self.save_button, "Save the settings")

    def toggle_resolution_fields(self):
        if self.custom_resolution_var.get():
            self.width_entry.state(["!disabled"])
            self.height_entry.state(["!disabled"])
        else:
            self.width_entry.state(["disabled"])
            self.height_entry.state(["disabled"])

    def save_settings(self):
        self.settings["high_quality"] = self.high_quality_var.get()
        self.settings["custom_resolution"] = self.custom_resolution_var.get()
        self.settings["width"] = int(self.width_entry.get())
        self.settings["height"] = int(self.height_entry.get())
        self.destroy()





class CreateToolTip(object):
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(
            self.tw,
            text=self.text,
            justify="left",
            background="#ffffff",
            relief="solid",
            borderwidth=1,
            font=("tahoma", "8", "normal"),
        )
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()


root = tk.Tk()
app = Application(master=root)
app.mainloop()
