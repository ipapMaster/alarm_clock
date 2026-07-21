import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk  # Импортируем ttk для современных виджетов
import threading
import time
import shutil  # Для копирования аудиофайлов в папку проекта
from tkinter import filedialog  # Для вызова окна выбора файла
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk
import pystray
import pygame
from pystray import MenuItem as item


def create_alarm_icon(transtarent=True):
    # Создаем прозрачное изображение 64x64
    img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Если не прозрачный, то рисуем белый круг
    if not transtarent:
        draw.rounded_rectangle(
            (0, 0, 64, 64),
            radius=5,
            fill="#AAFFAA",  # Цвет фона
            outline="#99FF99",  # Цвет рамки
            width=2  # Толщина рамки
        )

    # Рисуем корпус будильника (круг)
    draw.ellipse([12, 16, 52, 56], outline="black", width=4, fill="white")

    # Левое ухо (полукруг/дуга)
    draw.arc([4, 6, 24, 26], start=135, end=315, fill="black", width=4)
    # Правое ухо
    draw.arc([40, 6, 60, 26], start=225, end=45, fill="black", width=4)

    # Ножки
    draw.line([14, 54, 4, 62], fill="black", width=4)
    draw.line([50, 54, 60, 62], fill="black", width=4)

    # Стрелки (центр в точке 32, 36)
    draw.line([32, 36, 32, 24], fill="black", width=3)  # Часовая
    draw.line([32, 36, 44, 36], fill="black", width=2)  # Минутная

    return img


class AlarmApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Будильник")
        self.root.geometry("500x450")
        self.root.configure(bg="#f5f5f5")

        # Генерируем картинку и конвертируем для Tkinter
        pil_img = create_alarm_icon()
        self.tk_img = ImageTk.PhotoImage(pil_img)  # Защита от Garbage Collector

        # Устанавливаем как иконку главного окна
        self.root.iconphoto(False, self.tk_img)

        # Настройка стилей для ttk
        self.style = ttk.Style()
        self.style.theme_use("clam")  # print(self.style.theme_names()) - доступные темы
        self.style.configure("Treeview", font=("Arial", 11), rowheight=25)
        self.style.configure("Treeview.Heading", font=("Arial", 11, "bold"))

        # Подключаем микшер для воспроизведения
        pygame.mixer.init()

        if not os.path.exists('music'):
            os.mkdir('music')

        self.chosen_music_path = ""  # Переменная для временного хранения пути выбранного трека

        # Файл для воспроизведения
        """
        Freesound.org — крупнейшая библиотека бесплатных звуков.
        Что искать: Введите в поиск «alarm clock» или «digital beep».
        Плюс: Все звуки имеют бесплатные лицензии (Creative Commons).
        Звуки-тут.рф / Mixkit.co — популярные платформы с короткими звуковыми эффектами.
        Что искать: Разделы «Будильник», «Сигналы» или «Alerts».
        Плюс: Файлы сразу скачиваются в формате MP3 и обычно длятся от 2 до 10 секунд.
        """
        # self.music_file = 'alarm.mp3'

        # Список для хранения времени будильников
        self.alarms = []

        # --- Верхняя панель: Ввод данных ---
        input_frame = tk.Frame(root, bg="#f5f5f5")
        input_frame.pack(pady=15, fill="x", padx=20)

        tk.Label(input_frame, text="Время (ЧЧ:ММ):", font=("Arial", 11), bg="#f5f5f5").pack(side="left", padx=5)
        self.time_entry = tk.Entry(input_frame, font=("Arial", 12), width=8, justify="center")
        self.time_entry.pack(side="left", padx=5)
        self.time_entry.focus()

        # Новая кнопка выбора мелодии
        tk.Label(input_frame, text="Мелодия:").pack(side="left", padx=5)
        pick_btn = tk.Button(input_frame, text="Обзор...", command=self.pick_music)
        pick_btn.pack(side="left", padx=5)

        add_btn = tk.Button(input_frame, text="Добавить", font=("Arial", 10, "bold"),
                            bg="#4CAF50", fg="white", activebackground="#45a049",
                            relief="flat", command=self.add_alarm)
        add_btn.pack(side="left", padx=10, ipady=2, ipadx=10)

        # --- Средняя панель: Список будильников ---
        list_frame = tk.Frame(root, bg="#f5f5f5")
        list_frame.pack(pady=5, fill="both", expand=True, padx=20)

        tk.Label(list_frame, text="Активные будильники:", font=("Arial", 11, "bold"), bg="#f5f5f5").pack(anchor="w",
                                                                                                         pady=5)

        # Таблица для отображения
        self.tree = ttk.Treeview(list_frame, columns=("time", "music", "status"), show="headings", height=8)
        self.tree.heading("time", text="Время", anchor="center")
        self.tree.heading("music", text="Мелодия", anchor="center")
        self.tree.heading("status", text="Статус", anchor="center")
        self.tree.column("time", width=80, anchor="center")
        self.tree.column("music", width=180, anchor="center")
        self.tree.column("status", width=80, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        # Скроллбар для таблицы
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # --- Нижняя панель: Управление списком ---
        action_frame = tk.Frame(root, bg="#f5f5f5")
        action_frame.pack(pady=15, fill="x", padx=20)

        delete_btn = tk.Button(action_frame, text="Удалить выбранный", font=("Arial", 10),
                               bg="#f44336", fg="white", activebackground="#da190b",
                               relief="flat", command=self.delete_alarm)
        delete_btn.pack(side="right", ipady=3, ipadx=10)

        quit_btn = tk.Button(action_frame, text="Выход", font=("Arial", 10),
                             bg="#ff2233", fg="white", activebackground="#ff1111",
                             relief="flat", command=self.quit_app)
        quit_btn.pack(side="right", ipady=3, padx=10)

        # Горячая клавиша для удаления
        self.tree.bind("<Delete>", lambda event: self.delete_alarm())

        # --- Системные процессы ---
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)

        self.check_thread = threading.Thread(target=self.check_alarm_loop, daemon=True)
        self.check_thread.start()

        self.icon = None

    def pick_music(self):
        file_path = filedialog.askopenfilename(
            filetypes=[('Music File', '*.mp3')]
        )
        if not file_path:
            return

        filename = os.path.basename(file_path)
        destination = os.path.join("music", filename)

        try:
            shutil.copy(file_path, destination)
            selected_item = self.tree.selection()

            if selected_item:
                values = self.tree.item(selected_item, "values")
                selected_time = values[0]
                for i, alarm in enumerate(self.alarms):
                    if alarm[0] == selected_time:
                        self.alarms[i] = (selected_time, destination)
                        break

                self.update_treeview()
                messagebox.showinfo('Успешно',
                                    f'Мелодия будильника {selected_item} изменения на {filename}')
            else:
                self.chosen_music_path = destination
                messagebox.showinfo('Успешно',
                                    f'Выбрана мелодия по умолчанию для нового будильника {filename}')


        except Exception as e:
            messagebox.showerror('Ошибка', f'Не удалось открыть файл: {e}')

    def update_treeview(self):
        """Обновляет графический список на основе массива self.alarms"""
        # Очищаем старые записи
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Сортируем будильники по времени для красоты
        self.alarms.sort()

        # Вставляем актуальные данные
        for alarm_time, music_path in self.alarms:
            filename = os.path.basename(music_path) if music_path else 'По умолчанию'
            self.tree.insert("", "end", values=(alarm_time, filename, "Ожидание"))

    def add_alarm(self):
        alarm_time = self.time_entry.get().strip()
        try:
            time.strptime(alarm_time, "%H:%M")
            existing_times = [alarm[0] for alarm in self.alarms]
            if alarm_time not in existing_times:
                self.alarms.append((alarm_time, self.chosen_music_path))
                self.chosen_music_path = ''  # Сбрасываем для следующего будильника
                self.update_treeview()  # Обновляем интерфейс
            else:
                messagebox.showwarning("Внимание", "Такой будильник уже существует")
            self.time_entry.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Ошибка", "Используйте формат ЧЧ:ММ (например, 07:30)")

    def delete_alarm(self):
        """Удаляет выбранный в таблице будильник"""
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Внимание", "Выберите будильник из списка для удаления")
            return

        # Получаем значение времени из выбранной строки
        values = self.tree.item(selected_item, "values")
        alarm_time = values[0]

        # Удаляем из структуры данных и обновляем интерфейс
        for alarm in self.alarms:
            if alarm[0] == alarm_time:
                self.alarms.remove(alarm_time)
                break

        self.update_treeview()

    def check_alarm_loop(self):
        while True:
            now = datetime.now().strftime("%H:%M")
            target_alarm = None
            for alarm in self.alarms:
                if alarm[0] == now:
                    target_alarm = alarm
                    break
            if target_alarm:
                self.root.after(0, self.trigger_alarm, target_alarm)
                self.alarms.remove(target_alarm)
                self.root.after(0, self.update_treeview())
            time.sleep(5)

    def trigger_alarm(self, alarm_data):
        """Вызывается при срабатывании: разворачивает окно,
        запускает музыку и открывает окно отключения"""
        alarm_time, music_file = alarm_data
        self.show_window()
        # Проверяем наличие файла мелодии
        if music_file and os.path.exists(music_file):
            pygame.mixer.music.load(music_file)
            pygame.mixer.music.play(loops=-1)  # Бесконечный повтор, пока не остановим
        elif os.path.exists('alarm.mp3'):
            pygame.mixer.music.load('alarm.mp3')
            pygame.mixer.music.play(loops=-1)  # Бесконечный повтор, пока не остановим
        else:
            # Если файла нет, пищим стандартным системным звуком
            self.root.bell()
        # Вместо messagebox вызываем кастомное окно блокировки
        self.show_alarm_window(alarm_time)

    def show_alarm_window(self, alarm_time):
        """Создает модальное окно с кнопкой выключения музыки"""
        alarm_win = tk.Toplevel(self.root)
        alarm_win.title("БУДИЛЬНИК!")
        alarm_win.geometry("300x150")
        alarm_win.configure(bg="#fff3cd")
        alarm_win.attributes("-topmost", True)  # Всегда поверх других окон
        alarm_win.grab_set()  # Делаем окно модальным (блокирует основное окно)
        tk.Label(alarm_win, text=f"Время: {alarm_time}", font=("Arial", 16, "bold"),
                 bg="#fff3cd", fg="#856404").pack(pady=15)
        tk.Label(alarm_win, text="Пора вставать!", font=("Arial", 12),
                 bg="#fff3cd").pack(pady=5)

        def stop_music():
            # Проверяем, инициализирован ли микшер Pygame в данный момент
            if pygame.mixer.get_init() is not None:
                pygame.mixer.music.stop()  # Глушим музыку только если микшер работает

            alarm_win.destroy()  # Закрываем всплывающее окошко в любом случае

        stop_btn = tk.Button(alarm_win, text="СТОП", font=("Arial", 12, "bold"),
                             bg="#dc3545", fg="white", activebackground="#bd2130", relief="flat",
                             command=stop_music)
        stop_btn.pack(pady=10, ipadx=20)

    def hide_window(self):
        self.root.withdraw()  # скрывает главное окно приложения с экрана, но не закрывает саму программу
        menu = (
            item('Открыть', self.show_window),
            item('Выход', self.quit_app)
        )
        self.icon = pystray.Icon("alarm_app", create_alarm_icon(0), "Будильник", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def show_window(self):
        if self.icon:
            self.icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_app(self):
        pygame.mixer.quit()
        if self.icon:
            self.icon.stop()
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    app = AlarmApp(root)
    root.mainloop()
