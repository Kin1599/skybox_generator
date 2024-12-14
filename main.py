import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk, ImageFilter
import numpy as np
import os
import random
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import opensimplex
from tkinter.colorchooser import askcolor
from scipy.ndimage import binary_erosion, binary_dilation
import time


class SkyboxGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Skybox Generator")

        # Frame for parameters
        self.param_frame = ttk.LabelFrame(root, text="Parameters")
        self.param_frame.grid(row=0, column=0, padx=10, pady=10, sticky="n")

        # Saturation
        ttk.Label(self.param_frame, text="Saturation:").grid(row=0, column=0, sticky="w")
        self.saturation = tk.DoubleVar(value=0.5)
        ttk.Scale(self.param_frame, from_=0.0, to=1.0, variable=self.saturation).grid(row=0, column=1, sticky="ew")

        # Time of day
        ttk.Label(self.param_frame, text="Time of Day:").grid(row=1, column=0, sticky="w")
        self.time_of_day = ttk.Combobox(self.param_frame, values=["Day", "Night", "Sunrise", "Sunset"], state="readonly")
        self.time_of_day.set("Day")
        self.time_of_day.grid(row=1, column=1, sticky="ew")

        # Weather
        ttk.Label(self.param_frame, text="Weather:").grid(row=2, column=0, sticky="w")
        self.weather = ttk.Combobox(self.param_frame, values=["Calm", "Storm", "Foggy"], state="readonly")
        self.weather.set("Calm")
        self.weather.grid(row=2, column=1, sticky="ew")

        # Storm intensity
        ttk.Label(self.param_frame, text="Storm Intensity:").grid(row=3, column=0, sticky="w")
        self.storm_intensity = tk.DoubleVar(value=0.5)
        ttk.Scale(self.param_frame, from_=0.0, to=1.0, variable=self.storm_intensity).grid(row=3, column=1, sticky="ew")

        # Seed
        ttk.Label(self.param_frame, text="Seed:").grid(row=4, column=0, sticky="w")
        self.seed_entry = ttk.Entry(self.param_frame)
        self.seed_entry.grid(row=4, column=1, sticky="ew")

        # Color picker for clouds
        ttk.Label(self.param_frame, text="Cloud Color:").grid(row=5, column=0, sticky="w")
        self.cloud_color_button = ttk.Button(self.param_frame, text="Select Color", command=self.choose_cloud_color)
        self.cloud_color_button.grid(row=5, column=1, sticky="ew")
        self.cloud_color = (255, 255, 255)  # Default cloud color

        # Generate Button
        self.generate_button = ttk.Button(self.param_frame, text="Generate Skybox", command=self.start_generation)
        self.generate_button.grid(row=6, column=0, columnspan=2, pady=10)

        # Seed display
        self.seed_display = ttk.Label(self.param_frame, text="Seed: N/A")
        self.seed_display.grid(row=7, column=0, columnspan=2, sticky="w")

        # Frame for canvas
        self.canvas_frame = ttk.LabelFrame(root, text="Skybox Preview")
        self.canvas_frame.grid(row=0, column=1, padx=10, pady=10, sticky="n")

        self.canvas = tk.Canvas(self.canvas_frame, width=512, height=512, bg="black")
        self.canvas.pack()

        # Export Button
        self.export_button = ttk.Button(root, text="Export Skybox", command=self.export_skybox)
        self.export_button.grid(row=1, column=0, columnspan=2, pady=10)

        # Progress Label
        self.progress_label = ttk.Label(root, text="")
        self.progress_label.grid(row=2, column=0, columnspan=2, pady=10)

        # Time Label
        self.time_label = ttk.Label(root, text="Generation Time: N/A")
        self.time_label.grid(row=3, column=0, columnspan=2, pady=10)

        # Placeholder for skybox images
        self.skybox_images = {}

    def start_generation(self):
        self.progress_label.config(text="Generating skybox, please wait...")
        self.root.update_idletasks()

        self.generate_button.config(state="disabled")

        Thread(target=self.generate_skybox).start()

    def add_fog(self, img, width, height):
        fog_intensity = self.storm_intensity.get()
        if fog_intensity > 0.5:
            draw = ImageDraw.Draw(img)
            for y in range(height):
                alpha = int(255 * (1 - y / height) * fog_intensity)
                draw.line([(0, y), (width, y)], fill=(200, 200, 200, alpha))

    def generate_skybox(self):
        start_time = time.time()  # Record start time
        seed = self.seed_entry.get()
        if seed:
            random.seed(seed)
            np.random.seed(int(seed))
        else:
            seed = random.randint(0, 1000000)  # Generate a random seed if none is provided
            random.seed(seed)
            np.random.seed(seed)
            self.seed_entry.insert(0, str(seed))  # Fill the seed entry

        self.seed_display.config(text=f"Seed: {seed}")  # Display the seed

        self.skybox_images = {}
        faces = ["left", "right", "front", "back", "top", "bottom"]

        with ThreadPoolExecutor(max_workers=os.cpu_count() * 2) as executor:
            futures = {executor.submit(self.create_realistic_texture, 512, 512, face): face for face in faces}
            for i, future in enumerate(futures):
                face = futures[future]
                self.skybox_images[face] = future.result()

        self.display_image(self.skybox_images["front"])
        self.progress_label.config(text="Skybox generation completed!")

        self.generate_button.config(state="normal")

        end_time = time.time()  # Record end time
        generation_time = end_time - start_time
        self.time_label.config(text=f"Generation Time: {generation_time:.2f} seconds")

    def create_realistic_texture(self, width, height, face):
        img = Image.new("RGB", (width, height), "black")

        # Add unique sky color for each face
        self.add_sky_color(img, width, height, face)

        # Add clouds with unique noise offset for each face
        cloud_texture = self.generate_clouds(width, height, face)
        img.paste(cloud_texture, (0, 0), cloud_texture)

        # Add weather effects
        if self.weather.get() == "Storm":
            self.add_lightning(img, width, height)
        elif self.weather.get() == "Foggy":
            self.add_fog(img, width, height)

        # Add stars and moon at night
        if self.time_of_day.get() == "Night":
            if face == "top":  # Add moon only on the top face
                self.add_stars_and_moon(img, width, height)
            else:
                self.add_stars(img, width, height, face)  # Add stars on all faces

        return img

    def add_sky_color(self, img, width, height, face):
        draw = ImageDraw.Draw(img)
        if self.weather.get() == "Storm":
            # Dark and gloomy sky for storm
            storm_intensity = self.storm_intensity.get()
            sky_color_top = (20, 20, 40 + int(storm_intensity * 50))  # Very dark blue
            sky_color_bottom = (50, 50, 60 + int(storm_intensity * 50))  # Dark gray
        elif self.time_of_day.get() == "Day":
            sky_color_top = (0, 102, 204)  # Dark blue for day sky
            sky_color_bottom = (135, 206, 235)  # Light blue for day sky
        elif self.time_of_day.get() == "Night":
            sky_color_top = (0, 0, 51)  # Very dark blue for night sky
            sky_color_bottom = (0, 0, 102)  # Dark blue for night sky
        elif self.time_of_day.get() == "Sunrise":
            sky_color_top = (255, 102, 0)  # Orange for sunrise
            sky_color_bottom = (255, 178, 102)  # Light orange for sunrise
        elif self.time_of_day.get() == "Sunset":
            sky_color_top = (153, 51, 0)  # Dark orange for sunset
            sky_color_bottom = (255, 102, 102)  # Light orange for sunset

        # Add gradient background
        for y in range(height):
            t = y / height
            color = (
                int(sky_color_top[0] * (1 - t) + sky_color_bottom[0] * t),
                int(sky_color_top[1] * (1 - t) + sky_color_bottom[1] * t),
                int(sky_color_top[2] * (1 - t) + sky_color_bottom[2] * t)
            )
            draw.line([(0, y), (width, y)], fill=color)

    def add_stars(self, img, width, height, face):
        """Add stars to the skybox."""
        draw = ImageDraw.Draw(img)
        num_stars = 100  # Number of stars to generate

        for _ in range(num_stars):
            # Randomly place stars on the image with varying sizes and brightness
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            brightness = random.randint(180, 255)  # Random brightness for stars
            size = random.randint(1, 3)  # Random size for stars
            draw.ellipse([x - size, y - size, x + size, y + size], fill=(brightness, brightness, brightness))

        # Optionally, you could add a small moon on the top face (not all faces)
        if face == 'top':  # Only add the moon to the top face
            self.add_moon(img, width, height)

    def add_moon(self, img, width, height):
        """Add moon to the top face of the skybox."""
        draw = ImageDraw.Draw(img)
        moon_x = random.randint(width // 4, 3 * width // 4)
        moon_y = random.randint(height // 4, height // 2)
        moon_size = random.randint(20, 40)
        draw.ellipse([moon_x - moon_size, moon_y - moon_size, moon_x + moon_size, moon_y + moon_size],
                    fill=(255, 255, 255))  # White color for the moon

    def add_stars_and_moon(self, img, width, height):
        """Add stars and moon to the skybox."""
        # Add stars first
        self.add_stars(img, width, height, 'top')  # Only add stars to all faces
        # Add the moon to the top face
        self.add_moon(img, width, height)

    def add_lightning(self, img, width, height):
        draw = ImageDraw.Draw(img)
        storm_intensity = self.storm_intensity.get()
        num_lightnings = random.randint(5, 10 + int(storm_intensity * 20))  # Increase the number of lightnings

        for _ in range(num_lightnings):
            # Generate random parameters for the lightning
            x1 = random.randint(0, width)
            y1 = random.randint(0, height // 2)
            x2 = x1 + random.randint(-50, 50)
            y2 = y1 + random.randint(100, 200)

            # Generate a random lightning curve
            points = [(x1, y1)]
            for _ in range(random.randint(5, 10)):  # Increase the number of points in the lightning
                x_new = points[-1][0] + random.randint(-20, 20)
                y_new = points[-1][1] + random.randint(20, 40)
                points.append((x_new, y_new))

            # Lightning color
            lightning_color = (255, 255, 255)
            draw.line(points, fill=lightning_color, width=random.randint(2, 4))  # Random thickness

            # Add glow effect
            glow_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Create a transparent image
            glow_draw = ImageDraw.Draw(glow_img)
            glow_draw.line(points, fill=(255, 255, 255, 100), width=random.randint(8, 12))  # Random thickness for glow
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=random.randint(3, 6)))  # Random blur radius

            # Composite the glow onto the original image
            img.paste(glow_img, (0, 0), glow_img)

    def generate_clouds(self, width, height, face):
        # Генерация первичного шума для облаков
        opensimplex.seed(random.randint(0, 100000))
        noise = np.zeros((height, width))
        offset_x = random.uniform(0, 100)  # Уникальный сдвиг для каждого лица
        offset_y = random.uniform(0, 100)  # Уникальный сдвиг для каждого лица

        for y in range(height):
            for x in range(width):
                noise[y, x] = opensimplex.noise2(x / 100 + offset_x, y / 100 + offset_y)

        # Добавление дополнительных слоев шума для деталей
        detail_noise = np.zeros((height, width))
        for y in range(height):
            for x in range(width):
                detail_noise[y, x] = opensimplex.noise2(x / 50 + offset_x, y / 50 + offset_y)  # Высокая частота

        # Смешивание основного шума и детализированного шума
        noise = (noise + 0.5 * detail_noise) / 1.5
        noise = (noise + 1) / 2  # Нормализация до диапазона [0, 1]

        # Преобразуем шум в изображение с прозрачным фоном
        cloud_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Прозрачный фон
        draw = ImageDraw.Draw(cloud_img)

        # Генерация облаков с помощью шума и прозрачности
        for y in range(height):
            for x in range(width):
                alpha = int(noise[y, x] * 255)  # Прозрачность на основе шума
                if self.weather.get() == "Storm":
                # Dark clouds for storm
                    storm_intensity = self.storm_intensity.get()
                    color = (50 + int(storm_intensity * 100), 50 + int(storm_intensity * 100), 50 + int(storm_intensity * 100), alpha)  # Dark gray clouds
                else:
                    color = (255, 255, 255, alpha)  # Белые облака с разной прозрачностью
                draw.point((x, y), fill=color)

        # Применение цвета облаков
        cloud_img = self.apply_color_to_image(cloud_img, self.cloud_color)

        # Добавление мягких контуров облаков
        self.add_cloud_contours(cloud_img, width, height)

        # Применение размытия для создания эффекта мягкости облаков
        cloud_img = cloud_img.filter(ImageFilter.GaussianBlur(radius=2))  # Уменьшенный радиус размытия

        return cloud_img


    def apply_color_to_image(self, img, color):
        img = img.convert("RGBA")
        data = img.getdata()
        new_data = []
        for item in data:
            # If noise value is high, replace the color (clouds are white in the original noise)
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                new_data.append(color + (item[3],))  # Replace with selected color
            else:
                new_data.append(item)
        img.putdata(new_data)
        return img

    def add_cloud_shadows(self, img, width, height):
        draw = ImageDraw.Draw(img)
        for y in range(height):
            for x in range(width):
                if img.getpixel((x, y))[:3] == self.cloud_color:
                    # Add shadow effect
                    shadow_color = (
                        max(0, self.cloud_color[0] - 50),
                        max(0, self.cloud_color[1] - 50),
                        max(0, self.cloud_color[2] - 50),
                        100
                    )
                    draw.point((x, y), fill=shadow_color)

    def add_cloud_contours(self, img, width, height):
        """Add soft edges (contours) to clouds."""
        mask = img.split()[3]  # Extract alpha channel
        mask = mask.filter(ImageFilter.GaussianBlur(radius=3))  # Apply blur to create soft edges
        img.putalpha(mask)

    def choose_cloud_color(self):
        color = askcolor()[0]  # Open color picker
        if color:
            self.cloud_color = color
            # Update button style to reflect the selected color
            style = ttk.Style()
            style.configure("CloudColor.TButton", background=self.rgb_to_hex(color))
            self.cloud_color_button.config(style="CloudColor.TButton")

    def rgb_to_hex(self, rgb):
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def display_image(self, img):
        img_tk = ImageTk.PhotoImage(img.resize((512, 512)))
        self.canvas.img_tk = img_tk
        self.canvas.create_image(0, 0, anchor="nw", image=img_tk)

    def export_skybox(self):
        if not self.skybox_images:
            return

        output_dir = filedialog.askdirectory(title="Select Export Directory")
        if not output_dir:
            return

        for face, img in self.skybox_images.items():
            img.save(os.path.join(output_dir, f"{face}.png"))

        messagebox.showinfo("Export Complete", f"Skybox exported to {output_dir}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SkyboxGeneratorApp(root)
    root.mainloop()