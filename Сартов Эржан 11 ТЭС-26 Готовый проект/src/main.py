import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


class ExcursionApp:
    # Разрешенные переходы статусов
    STATUS_TRANSITIONS = {
        "Новая": ["Подтверждена", "Отменена"],
        "Подтверждена": ["Завершена", "Отменена"],
        "Завершена": [],
        "Отменена": [],
    }
    ALL_STATUSES = ["Новая", "Подтверждена", "Завершена", "Отменена"]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MyГид — Регистрация на экскурсии (v1.0)")
        self.root.geometry("980x620")
        self.root.minsize(900, 560)

        # Хранилище в памяти (список словарей)
        self.bookings: list[dict] = []
        self.next_id: int = 1
        self.selected_id: int | None = None

        self._setup_ui()
        self._load_demo_data()

    def _setup_ui(self):
        # --- Верхняя панель: Поиск и фильтрация ---
        search_frame = ttk.LabelFrame(self.root, text="Поиск и фильтрация", padding=10)
        search_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(search_frame, text="Поиск (ФИО / экскурсия / номер):").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).pack(side="left", padx=(0, 15))

        ttk.Label(search_frame, text="Статус:").pack(side="left", padx=(0, 5))
        self.filter_status_var = tk.StringVar(value="Все")
        status_filter = ttk.Combobox(
            search_frame,
            textvariable=self.filter_status_var,
            values=["Все"] + self.ALL_STATUSES,
            state="readonly",
            width=15,
        )
        status_filter.pack(side="left", padx=(0, 15))
        status_filter.bind("<<ComboboxSelected>>", lambda _: self.refresh_table())

        ttk.Button(search_frame, text="Сбросить фильтры", command=self.reset_filters).pack(side="left")

        # --- Основная область: Таблица (слева) + Форма (справа) ---
        main_pane = ttk.PanedWindow(self.root, orient="horizontal")
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # Левая часть: Таблица записей
        table_frame = ttk.Frame(main_pane)
        main_pane.add(table_frame, weight=3)

        columns = ("id", "excursion", "date", "client", "phone", "tickets", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        headers = {
            "id": ("№", 45),
            "excursion": ("Экскурсия", 190),
            "date": ("Дата", 95),
            "client": ("Турист (ФИО)", 160),
            "phone": ("Телефон", 120),
            "tickets": ("Мест", 55),
            "status": ("Статус", 110),
        }
        for col, (text, width) in headers.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="center" if col in ("id", "date", "tickets", "status") else "w")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

        # Правая часть: Карточка записи
        form_frame = ttk.LabelFrame(main_pane, text="Карточка записи на экскурсию", padding=12)
        main_pane.add(form_frame, weight=1)

        self.vars = {
            "excursion": tk.StringVar(),
            "date": tk.StringVar(),
            "client": tk.StringVar(),
            "phone": tk.StringVar(),
            "tickets": tk.StringVar(value="1"),
            "status": tk.StringVar(value="Новая"),
        }

        fields = [
            ("Название экскурсии *:", "excursion"),
            ("Дата (ДД.ММ.ГГГГ) *:", "date"),
            ("ФИО туриста *:", "client"),
            ("Телефон *:", "phone"),
            ("Количество мест (1–20) *:", "tickets"),
        ]

        for row_idx, (label_text, key) in enumerate(fields):
            ttk.Label(form_frame, text=label_text).grid(row=row_idx * 2, column=0, sticky="w", pady=(4, 0))
            ttk.Entry(form_frame, textvariable=self.vars[key], width=32).grid(
                row=row_idx * 2 + 1, column=0, sticky="ew", pady=(2, 6)
            )

        ttk.Label(form_frame, text="Статус записи:").grid(row=10, column=0, sticky="w", pady=(4, 0))
        self.status_combo = ttk.Combobox(
            form_frame, textvariable=self.vars["status"], values=self.ALL_STATUSES, state="readonly", width=30
        )
        self.status_combo.grid(row=11, column=0, sticky="ew", pady=(2, 12))

        # Кнопки управления
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=12, column=0, sticky="ew", pady=5)

        ttk.Button(btn_frame, text="Добавить новую", command=self.add_booking).pack(fill="x", pady=3)
        ttk.Button(btn_frame, text="Сохранить изменения", command=self.update_booking).pack(fill="x", pady=3)
        ttk.Button(btn_frame, text="Удалить запись", command=self.delete_booking).pack(fill="x", pady=3)
        ttk.Separator(btn_frame, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(btn_frame, text="Очистить форму", command=self.clear_form).pack(fill="x", pady=3)

        # --- Нижняя строка состояния ---
        self.status_bar = ttk.Label(
            self.root,
            text="Готово к работе. Внимание: данные хранятся в оперативной памяти до закрытия окна.",
            relief="sunken",
            anchor="w",
            padding=(8, 4),
        )
        self.status_bar.pack(fill="x", side="bottom")

    def _validate_inputs(self) -> dict | None:
        excursion = self.vars["excursion"].get().strip()
        date_str = self.vars["date"].get().strip()
        client = self.vars["client"].get().strip()
        phone = self.vars["phone"].get().strip()
        tickets_str = self.vars["tickets"].get().strip()

        if not all([excursion, date_str, client, phone, tickets_str]):
            messagebox.showerror("Ошибка ввода", "Заполните все обязательные поля, отмеченные символом *.")
            return None

        try:
            datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            messagebox.showerror("Ошибка формата даты", "Введите дату в формате ДД.ММ.ГГГГ (например, 25.11.2026).")
            return None

        if not tickets_str.isdigit() or not (1 <= int(tickets_str) <= 20):
            messagebox.showerror("Ошибка количества мест", "Количество мест должно быть целым числом от 1 до 20.")
            return None

        if len(phone) < 6:
            messagebox.showerror("Ошибка телефона", "Введите корректный номер телефона (минимум 6 символов).")
            return None

        return {
            "excursion": excursion,
            "date": date_str,
            "client": client,
            "phone": phone,
            "tickets": int(tickets_str),
        }

    def add_booking(self):
        data = self._validate_inputs()
        if not data:
            return

        new_record = {
            "id": self.next_id,
            **data,
            "status": "Новая",
        }
        self.bookings.append(new_record)
        self.next_id += 1
        self.clear_form()
        self.refresh_table()
        self.status_bar.config(text=f"Запись №{new_record['id']} успешно добавлена.")

    def update_booking(self):
        if self.selected_id is None:
            messagebox.showwarning("Не выбрана запись", "Выберите запись в таблице слева для редактирования.")
            return

        record = next((b for b in self.bookings if b["id"] == self.selected_id), None)
        if not record:
            return

        data = self._validate_inputs()
        if not data:
            return

        new_status = self.vars["status"].get()
        current_status = record["status"]

        if new_status != current_status:
            allowed = self.STATUS_TRANSITIONS.get(current_status, [])
            if new_status not in allowed:
                messagebox.showerror(
                    "Недопустимый переход статуса",
                    f"Нельзя изменить статус с «{current_status}» на «{new_status}».\n"
                    f"Доступные переходы: {', '.join(allowed) if allowed else 'нет (конечный статус)'}.",
                )
                self.vars["status"].set(current_status)
                return

        record.update(data)
        record["status"] = new_status
        self.refresh_table()
        self.status_bar.config(text=f"Запись №{record['id']} обновлена.")

    def delete_booking(self):
        if self.selected_id is None:
            messagebox.showwarning("Не выбрана запись", "Выберите запись в таблице для удаления.")
            return

        confirm = messagebox.askyesno(
            "Подтверждение удаления",
            f"Вы действительно хотите удалить запись №{self.selected_id}?",
        )
        if not confirm:
            return

        self.bookings = [b for b in self.bookings if b["id"] != self.selected_id]
        deleted_id = self.selected_id
        self.clear_form()
        self.refresh_table()
        self.status_bar.config(text=f"Запись №{deleted_id} удалена.")

    def on_select_row(self, _event):
        selected = self.tree.selection()
        if not selected:
            return
        item_values = self.tree.item(selected, "values")
        record_id = int(item_values)
        record = next((b for b in self.bookings if b["id"] == record_id), None)
        if not record:
            return

        self.selected_id = record["id"]
        self.vars["excursion"].set(record["excursion"])
        self.vars["date"].set(record["date"])
        self.vars["client"].set(record["client"])
        self.vars["phone"].set(record["phone"])
        self.vars["tickets"].set(str(record["tickets"]))
        self.vars["status"].set(record["status"])

    def clear_form(self):
        self.selected_id = None
        for key in ("excursion", "date", "client", "phone"):
            self.vars[key].set("")
        self.vars["tickets"].set("1")
        self.vars["status"].set("Новая")
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())

    def reset_filters(self):
        self.search_var.set("")
        self.filter_status_var.set("Все")
        self.refresh_table()

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        query = self.search_var.get().strip().lower()
        status_filter = self.filter_status_var.get()

        count = 0
        for b in self.bookings:
            if status_filter != "Все" and b["status"] != status_filter:
                continue
            if query:
                haystack = f"{b['id']} {b['excursion']} {b['client']} {b['phone']}".lower()
                if query not in haystack:
                    continue

            self.tree.insert(
                "",
                "end",
                values=(b["id"], b["excursion"], b["date"], b["client"], b["phone"], b["tickets"], b["status"]),
            )
            count += 1

        self.status_bar.config(text=f"Отображено записей: {count} из {len(self.bookings)}")

    def _load_demo_data(self):
        demo = [
            {
                "id": 1,
                "excursion": "Огни вечерней Москвы",
                "date": "22.11.2026",
                "client": "Иванов Алексей Петрович",
                "phone": "+7 (900) 111-22-33",
                "tickets": 2,
                "status": "Подтверждена",
            },
            {
                "id": 2,
                "excursion": "Тайны Московского Кремля",
                "date": "23.11.2026",
                "client": "Смирнова Елена Викторовна",
                "phone": "+7 (900) 444-55-66",
                "tickets": 4,
                "status": "Новая",
            },
            {
                "id": 3,
                "excursion": "Усадьба Царицыно: прогулка с гидом",
                "date": "20.11.2026",
                "client": "Козлов Дмитрий Сергеевич",
                "phone": "+7 (900) 777-88-99",
                "tickets": 1,
                "status": "Завершена",
            },
        ]
        self.bookings.extend(demo)
        self.next_id = 4
        self.refresh_table()


if __name__ == "__main__":
    root = tk.Tk()
    app = ExcursionApp(root)
    root.mainloop()
