import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import requests
import httpx
import asyncio
import threading
import io
import os
import random
import openai

SEARCH_API = "https://tikwm.com/api/feed/search"
DETAIL_API = "https://tikwm.com/api/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

openai.api_key = "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"  # ✅ Nhập OpenAI API Key của bạn tại đây

CAPTION_BACKENDS = ["openai", "gemini", "cohere"]

class TikTokDownloaderApp:
    def save_dir_to_file(self):
        try:
            with open("save_dir.txt", "w", encoding="utf-8") as f:
                f.write(self.save_dir)
        except:
            pass

    def load_saved_dir(self):
        try:
            with open("save_dir.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            return None

    def __init__(self, root):
        self.root = root
        self.root.title("TikTok Search & Download with Thumbnails")
        self.root.geometry("1100x720")
        self.save_dir = self.load_saved_dir() or os.path.abspath("videos")
        os.makedirs(self.save_dir, exist_ok=True)
        self.thumbnail_images = {}
        self.caption_backend = tk.StringVar(value=CAPTION_BACKENDS[0])
        self.setup_ui()

    def setup_ui(self):
        top = tk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=5)

        tk.Label(top, text="🔍 Từ khóa:").pack(side="left")
        self.entry_keyword = tk.Entry(top, width=30)
        self.entry_keyword.pack(side="left", padx=5)

        tk.Label(top, text="Sắp theo:").pack(side="left")
        self.sort_by = ttk.Combobox(top, values=["likes ⬇", "likes ⬆", "views ⬇", "views ⬆"], width=10, state="readonly")
        self.sort_by.set("likes ⬇")
        self.sort_by.pack(side="left", padx=5)

        tk.Label(top, text="AI:").pack(side="left")
        self.caption_combo = ttk.Combobox(top, values=CAPTION_BACKENDS, textvariable=self.caption_backend, width=8, state="readonly")
        self.caption_combo.pack(side="left", padx=5)

        tk.Button(top, text="Tìm kiếm", command=self.search_thread).pack(side="left", padx=5)
        tk.Button(top, text="📁 Chọn thư mục lưu", command=self.choose_folder).pack(side="right")

        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=10)

        self.tree = ttk.Treeview(main, columns=("url", "title", "likes", "views"), show="headings", selectmode="extended")
        self.tree.heading("title", text="Tiêu đề")
        self.tree.heading("likes", text="❤️ Likes")
        self.tree.heading("views", text="👁 Views")
        self.tree.column("url", width=0, stretch=False)
        self.tree.column("title", width=400)
        self.tree.column("likes", width=80, anchor="e")
        self.tree.column("views", width=80, anchor="e")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        scrollbar = ttk.Scrollbar(main, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="left", fill="y")

        right = tk.Frame(main, width=200)
        right.pack(side="right", fill="y")
        self.thumb_label = tk.Label(right)
        self.thumb_label.pack(pady=20)

        bottom = tk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=5)

        tk.Button(bottom, text="⬇️ Tải video đã chọn", command=self.download_thread).pack(side="left")
        self.progress = ttk.Progressbar(bottom, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(side="left", padx=10)
        self.progress_label = tk.Label(bottom, text="Chưa tải")
        self.progress_label.pack(side="left")

        self.log_box = tk.Text(self.root, height=10, bg="#f9f9f9")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=5)

    def log(self, msg):
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.save_dir = folder
            self.save_dir_to_file()
            self.log(f"📁 Lưu video tại: {folder}")

    def search_thread(self):
        threading.Thread(target=self.search_videos, daemon=True).start()

    def search_videos(self):
        keyword = self.entry_keyword.get().strip()
        if not keyword:
            self.log("❌ Vui lòng nhập từ khóa.")
            return

        self.tree.delete(*self.tree.get_children())
        self.thumbnail_images.clear()
        self.thumb_label.config(image="")

        try:
            params = {"keywords": keyword, "count": 20, "cursor": 0}
            r = requests.get(SEARCH_API, params=params, headers=HEADERS, timeout=20)
            data = r.json()

            if data.get("code") != 0:
                self.log(f"❌ Lỗi API: {data.get('msg')}")
                return

            videos = data["data"]["videos"]
            sort_key_raw = self.sort_by.get().strip()
            if " " in sort_key_raw:
                key_part, direction = sort_key_raw.split()
                reverse = direction == "⬇"
            else:
                key_part = sort_key_raw
                reverse = True
            key_map = {"likes": "digg_count", "views": "play_count"}
            sort_field = key_map.get(key_part, "digg_count")
            sorted_videos = sorted(videos, key=lambda v: v.get(sort_field, 0), reverse=reverse)

            for v in sorted_videos[:10]:
                url = f"https://www.tiktok.com/@{v['author']['unique_id']}/video/{v['video_id']}"
                iid = self.tree.insert("", "end", values=(
                    url, v.get("title", "(no title)"), v.get("digg_count", 0), v.get("play_count", 0)
                ))
                self.thumbnail_images[iid] = v.get("cover")

            self.log(f"✅ Tìm thấy {len(sorted_videos[:10])} video.")

        except Exception as e:
            self.log(f"❌ Lỗi tìm kiếm: {e}")

    def on_select(self, event):
        selected = self.tree.focus()
        if selected in self.thumbnail_images:
            thumb_url = self.thumbnail_images[selected]
            try:
                img_data = requests.get(thumb_url).content
                img = Image.open(io.BytesIO(img_data)).resize((180, 320))
                tk_img = ImageTk.PhotoImage(img)
                self.thumb_label.config(image=tk_img)
                self.thumb_label.image = tk_img
            except Exception as e:
                self.log(f"⚠️ Lỗi hiển thị ảnh: {e}")

    def get_selected_urls(self):
        return [self.tree.item(iid)["values"][0] for iid in self.tree.selection()]

    def generate_caption_ai(self, title, views=0, likes=0):
        backend = self.caption_backend.get()
        prompt = (
            f"Write a catchy TikTok caption in English for a video titled: '{title}', "
            f"with {likes} likes and {views} views. Make it no more than 150 characters and include 2-3 trending hashtags."
        )

        try:
            if backend == "openai":
                response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.8,
                )
                return response.choices[0].message.content.strip()[:150]
            else:
                return f"[AI-{backend}] {title}"  # Giả lập nếu chưa tích hợp backend khác
        except Exception as e:
            self.log(f"⚠️ Lỗi tạo caption AI ({backend}): {e}")
            return title

    def download_thread(self):
        threading.Thread(target=self.download_selected_videos, daemon=True).start()

    async def download_video(self, client, url):
        try:
            r = await client.get(DETAIL_API, params={"url": url, "hd": 1}, headers=HEADERS)
            data = r.json()
            if data.get("code") != 0:
                return f"❌ {url} → {data.get('msg')}"

            info = data["data"]
            video_url = info["play"]
            username = info["author"]["unique_id"]
            title = info.get("title", "video")
            safe_title = "".join(c if c.isalnum() or c in " -_()" else "_" for c in title)[:80]
            filename = f"{username} - {safe_title}.mp4"
            filepath = os.path.join(self.save_dir, filename)

            caption = self.generate_caption_ai(title, info.get("play_count", 0), info.get("digg_count", 0))
            caption_file = filepath.replace(".mp4", ".txt")
            with open(caption_file, "w", encoding="utf-8") as f:
                f.write(caption)

            video_data = await client.get(video_url)
            with open(filepath, "wb") as f:
                f.write(video_data.content)

            return f"✅ Đã tải: {filename}"

        except Exception as e:
            return f"⚠️ {url} lỗi: {e}"

    def download_selected_videos(self):
        urls = self.get_selected_urls()
        if not urls:
            self.log("⚠️ Hãy chọn ít nhất 1 video.")
            return

        self.progress["maximum"] = len(urls)
        self.progress["value"] = 0
        self.progress_label.config(text="Đang tải...")

        async def run_all():
            async with httpx.AsyncClient() as client:
                for i, url in enumerate(urls, 1):
                    await asyncio.sleep(1)
                    msg = await self.download_video(client, url)
                    self.log(msg)
                    self.progress["value"] = i
                    self.progress_label.config(text=f"{i}/{len(urls)}")
                    self.root.update_idletasks()
            self.progress_label.config(text="✅ Hoàn tất.")

        asyncio.run(run_all())


if __name__ == "__main__":
    root = tk.Tk()
    app = TikTokDownloaderApp(root)
    root.mainloop()
