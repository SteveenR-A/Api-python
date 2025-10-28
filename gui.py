import os
import customtkinter as ctk
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import subprocess
import threading
import time
import sys
from tkinter import messagebox
from tkinter import ttk
from tkinter import simpledialog

# Allow overriding API URL via env var; default to 127.0.0.1:5000
API_URL = os.getenv('API_URL', 'http://127.0.0.1:5000')


def make_session(retries: int = 3, backoff_factor: float = 0.5, status_forcelist=(429, 500, 502, 503, 504)):
    """Crear una requests.Session con reintentos configurados para reducir errores de conexión transitoria.
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=frozenset(['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


# Sesión global usada por la GUI para todas las llamadas HTTP
SESSION = make_session()


def ensure_api_running(timeout=5):
    """Asegura que la API esté corriendo; si no, la arranca con el mismo python."""
    global API_URL
    def is_up(url):
        try:
            r = SESSION.get(f"{url}/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    # si API_URL ya responde, no hacemos nada
    if is_up(API_URL):
        return None

    # Intentar arrancar la API en puertos comunes (5000, 5001).
    # Pasamos la variable de entorno PORT al subprocess para que `app.py` la respete.
    for port in (5000, 5001):
        target = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env['PORT'] = str(port)
        # arrancar el servidor en background y capturar stderr a un pipe para debug opcional
        try:
            p = subprocess.Popen([sys.executable, "app.py"], cwd='.', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except Exception:
            p = None

        # esperar hasta que responda /health o hasta timeout
        start = time.time()
        while time.time() - start < timeout:
            if is_up(target):
                # actualizar API_URL global para que el resto de la app use el puerto correcto
                API_URL = target
                return p
            time.sleep(0.25)

        # si no arrancó en este puerto, intentar obtener stderr para diagnóstico y terminar proceso
        if p:
            try:
                err = p.stderr.read().decode('utf-8', errors='ignore') if p.stderr else ''
            except Exception:
                err = ''
            try:
                p.terminate()
                p.wait(timeout=1)
            except Exception:
                pass

    # Si no pudo arrancar automáticamente, pedir al usuario una URL alternativa
    attempts = 0
    while attempts < 3:
        attempts += 1
        answer = simpledialog.askstring("Configurar API", "No se pudo iniciar la API automáticamente. Introduce la URL de la API (ej: http://127.0.0.1:5001) o pulsa Cancel para abortar:")
        if not answer:
            break
        answer = answer.strip()
        if not answer.startswith('http'):
            messagebox.showerror('URL inválida', 'La URL debe comenzar con http:// o https://')
            continue
        if is_up(answer):
            API_URL = answer
            return None
        else:
            messagebox.showerror('No accesible', f'La URL {answer} no responde en /health')

    # No se pudo conectar o el usuario canceló
    return None


def api_is_up(url, timeout=2):
    """Comprobar si la API responde en /health y devolver (up, error_message)."""
    try:
        r = SESSION.get(f"{url}/health", timeout=timeout)
        if r.status_code == 200:
            return True, None
        return False, f"HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)



class LoginWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Login")
        self.geometry("300x200")
        self.parent = parent
        self.user = None

        self.username_entry = ctk.CTkEntry(self, placeholder_text="Username")
        self.username_entry.pack(pady=10)
        self.password_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*")
        self.password_entry.pack(pady=10)

        login_button = ctk.CTkButton(self, text="Login", command=self.login)
        login_button.pack(pady=20)

        # Botón temporal para crear un usuario de prueba
        create_user_button = ctk.CTkButton(self, text="Crear Usuario de Prueba", command=self.create_test_user)
        create_user_button.pack(pady=10)

    def create_test_user(self):
        def worker():
            try:
                r = SESSION.post(f"{API_URL}/usuarios", json={"username": "test", "password": "test", "rol": "administrador"}, timeout=4)
                status = r.status_code
                text = r.text
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}"))
                return
            if status == 201 or status == 409:
                self.after(0, lambda: messagebox.showinfo("Usuario Creado", "Usuario de prueba 'test' con contraseña 'test' creado exitosamente o ya existe."))
            else:
                self.after(0, lambda: messagebox.showerror("Error", f"No se pudo crear el usuario: {text}"))

        threading.Thread(target=worker, daemon=True).start()

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        def worker():
            try:
                r = SESSION.post(f"{API_URL}/login", json={"username": username, "password": password}, timeout=4)
                status = r.status_code
                data = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}"))
                return
            if status == 200:
                user = data.get('user') if isinstance(data, dict) else None
                def ok():
                    self.user = user
                    self.destroy()
                self.after(0, ok)
            else:
                self.after(0, lambda: messagebox.showerror("Error", "Credenciales inválidas"))

        threading.Thread(target=worker, daemon=True).start()


class ReportWindow(ctk.CTkToplevel):
    def __init__(self, parent, report_type):
        super().__init__(parent)
        self.title(f"Reporte de {report_type}")
        self.geometry("800x600")
        self.report_type = report_type

        self.create_widgets()
        self.load_report()

    def create_widgets(self):
        if self.report_type in ["Ventas", "Ganancias"]:
            filter_frame = ctk.CTkFrame(self)
            filter_frame.pack(pady=10)

            ctk.CTkLabel(filter_frame, text="Desde (YYYY-MM-DD):").pack(side="left", padx=5)
            self.desde_entry = ctk.CTkEntry(filter_frame)
            self.desde_entry.pack(side="left", padx=5)

            ctk.CTkLabel(filter_frame, text="Hasta (YYYY-MM-DD):").pack(side="left", padx=5)
            self.hasta_entry = ctk.CTkEntry(filter_frame)
            self.hasta_entry.pack(side="left", padx=5)

            ctk.CTkButton(filter_frame, text="Filtrar", command=self.load_report).pack(side="left", padx=5)

        self.tree = ttk.Treeview(self, show="headings")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

    def load_report(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        endpoint = f"{API_URL}/reportes/{self.report_type.lower().replace(' ', '_')}"
        params = {}
        if self.report_type in ["Ventas", "Ganancias"]:
            desde = self.desde_entry.get()
            hasta = self.hasta_entry.get()
            if not desde or not hasta:
                messagebox.showwarning("Filtro requerido", "Por favor ingrese un rango de fechas.")
                return
            params = {"desde": desde, "hasta": hasta}

        def worker():
            try:
                r = SESSION.get(endpoint, params=params, timeout=6)
                status = r.status_code
                data = r.json() if r.headers.get('content-type','').startswith('application/json') else None
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}"))
                return

            def update_ui():
                if status == 200 and data is not None:
                    if self.report_type == "Ventas":
                        self.configure_tree([('id', 'ID', 50), ('fecha_venta', 'Fecha', 100), ('total', 'Total', 100), ('cliente', 'Cliente', 150)])
                        for item in data.get('ventas', []):
                            self.tree.insert("", "end", values=(item['id'], item['fecha_venta'], item['total'], item['cliente']))
                    elif self.report_type == "Ganancias":
                        self.configure_tree([('producto', 'Producto', 150), ('cantidad_vendida', 'Cantidad Vendida', 100), ('total_ventas', 'Total Ventas', 100), ('total_costo', 'Total Costo', 100), ('ganancia', 'Ganancia', 100)])
                        for item in data.get('ganancias_por_producto', []):
                            self.tree.insert("", "end", values=(item['producto'], item['cantidad_vendida'], item['total_ventas'], item['total_costo'], item['ganancia']))
                    elif self.report_type == "Existencias Mínimas":
                        self.configure_tree([('nombre', 'Nombre', 150), ('stock', 'Stock', 100), ('stock_minimo', 'Stock Mínimo', 100)])
                        for item in data:
                            self.tree.insert("", "end", values=(item['nombre'], item['stock'], item['stock_minimo']))
                    elif self.report_type == "Existencias":
                        self.configure_tree([('nombre', 'Nombre', 150), ('stock', 'Stock', 100)])
                        for item in data:
                            self.tree.insert("", "end", values=(item['nombre'], item['stock']))
                else:
                    messagebox.showerror("Error", f"API error {status}: {r.text if 'r' in locals() else 'no response'}")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def configure_tree(self, columns):
        self.tree.config(columns=[c[0] for c in columns])
        for col, text, width in columns:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width)

class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Inventario")
        self.geometry("1024x768")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        # Status bar / API controls
        status_frame = ctk.CTkFrame(self)
        status_frame.pack(side="top", fill="x")
        self.api_status_label = ctk.CTkLabel(status_frame, text=f"API: {API_URL}", anchor="w")
        self.api_status_label.pack(side="left", padx=8, pady=4)
        ctk.CTkButton(status_frame, text="Configurar API", command=self.open_settings).pack(side="right", padx=8, pady=4)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=16, pady=16, fill="both", expand=True)

        # Resource selector
        selector_frame = ctk.CTkFrame(main_frame)
        selector_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(selector_frame, text="Módulo:", width=80).pack(side="left", padx=(8, 4))
        self.resource_var = ctk.StringVar(value="Productos")
        self.resource_menu = ctk.CTkOptionMenu(selector_frame, values=["Productos", "Clientes", "Proveedores"], variable=self.resource_var, command=self.on_resource_change)
        self.resource_menu.pack(side="left")

        # Reports menu
        reports_button = ctk.CTkButton(selector_frame, text="Reportes", command=self.open_reports_menu)
        reports_button.pack(side="left", padx=10)

        table_frame = ctk.CTkFrame(main_frame)
        table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        form_frame = ctk.CTkFrame(main_frame)
        form_frame.pack(side="right", fill="y")

        self.tree = ttk.Treeview(table_frame, show="headings")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        self.form_title = ctk.CTkLabel(form_frame, text="Detalle", font=ctk.CTkFont(size=14, weight="bold"))
        self.form_title.pack(pady=(8, 12))

        self.form_labels = []
        self.form_entries = []
        for _ in range(6):
            lbl = ctk.CTkLabel(form_frame, text="")
            lbl.pack(anchor="w", padx=8)
            ent = ctk.CTkEntry(form_frame, width=260)
            ent.pack(padx=8, pady=4)
            self.form_labels.append(lbl)
            self.form_entries.append(ent)

        self._current_id = None

        ctk.CTkButton(form_frame, text="Nuevo", command=self.clear_form).pack(fill="x", padx=8, pady=(12, 4))
        ctk.CTkButton(form_frame, text="Guardar", command=self.save_current).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(form_frame, text="Borrar", fg_color="#d9534f", command=self.delete_current).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(form_frame, text="Salir", fg_color="#6c757d", command=self.on_close).pack(fill="x", padx=8, pady=(12, 4))

        self._api_proc = ensure_api_running()
        # actualizar indicador de estado
        self.update_api_status()
        self.on_resource_change(self.resource_var.get())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_api_status(self):
        up, err = api_is_up(API_URL, timeout=2)
        text = f"API: {API_URL}"
        if up:
            self.api_status_label.configure(text=text + ' (OK)', text_color='green')
        else:
            self.api_status_label.configure(text=text + ' (NO CONECTA)', text_color='red')
        # Return tuple for callers
        return up, err

    def open_settings(self):
        SettingsWindow(self)

    def set_api_url(self, new_url):
        global API_URL
        API_URL = new_url
        # update displayed URL and session behavior
        self.api_status_label.configure(text=f"API: {API_URL}")
        self.update_api_status()

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Ajustes de API')
        self.geometry('420x140')
        self.parent = parent

        ctk.CTkLabel(self, text='API URL:').pack(anchor='w', padx=8, pady=(12,4))
        self.url_entry = ctk.CTkEntry(self, width=380)
        self.url_entry.pack(padx=8)
        self.url_entry.insert(0, API_URL)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill='x', pady=12, padx=8)
        ctk.CTkButton(btn_frame, text='Probar y Guardar', command=self.test_and_save).pack(side='left')
        ctk.CTkButton(btn_frame, text='Probar', command=self.test_only).pack(side='left', padx=8)
        ctk.CTkButton(btn_frame, text='Cancelar', command=self.destroy).pack(side='right')

    def test_only(self):
        url = self.url_entry.get().strip()
        if not url.startswith('http'):
            messagebox.showerror('URL inválida', 'La URL debe empezar por http:// o https://')
            return
        up, err = api_is_up(url, timeout=3)
        if up:
            messagebox.showinfo('Conexión OK', f'La API responde en {url}/health')
        else:
            messagebox.showerror('Fallo conexión', f'No responde: {err}')

    def test_and_save(self):
        url = self.url_entry.get().strip()
        if not url.startswith('http'):
            messagebox.showerror('URL inválida', 'La URL debe empezar por http:// o https://')
            return
        up, err = api_is_up(url, timeout=3)
        if up:
            # persistir en .env para próximas ejecuciones (opcional)
            try:
                env_path = os.path.join(os.getcwd(), '.env')
                # leer y reemplazar o añadir
                lines = []
                if os.path.exists(env_path):
                    with open(env_path, 'r') as f:
                        lines = f.read().splitlines()
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith('API_URL='):
                        lines[i] = f'API_URL={url}'
                        updated = True
                if not updated:
                    lines.append(f'API_URL={url}')
                with open(env_path, 'w') as f:
                    f.write('\n'.join(lines) + '\n')
            except Exception as e:
                messagebox.showwarning('Aviso', f'No se pudo escribir .env: {e}')

            # Propagar al parent
            self.parent.set_api_url(url)
            messagebox.showinfo('Guardado', 'URL guardada y configurada')
            self.destroy()
        else:
            messagebox.showerror('Fallo conexión', f'No responde: {err}')

    def open_reports_menu(self):
        menu = ctk.CTkToplevel(self)
        menu.title("Reportes")
        menu.geometry("200x200")
        ctk.CTkButton(menu, text="Ventas por Fecha", command=lambda: self.open_report_window("Ventas")).pack(pady=5)
        ctk.CTkButton(menu, text="Ganancias por Fecha", command=lambda: self.open_report_window("Ganancias")).pack(pady=5)
        ctk.CTkButton(menu, text="Existencias Mínimas", command=lambda: self.open_report_window("Existencias Mínimas")).pack(pady=5)
        ctk.CTkButton(menu, text="Reporte de Existencias", command=lambda: self.open_report_window("Existencias")).pack(pady=5)

    def open_report_window(self, report_type):
        ReportWindow(self, report_type)

    def load_data_for(self, resource):
        for ch in self.tree.get_children():
            self.tree.delete(ch)
        def worker():
            try:
                r = SESSION.get(f"{API_URL}/{resource.lower()}", timeout=4)
                status = r.status_code
                data = r.json() if r.headers.get('content-type','').startswith('application/json') else None
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def update_ui():
                if status == 200 and data is not None:
                    for p in data:
                        pid = p.get('id')
                        if resource == 'Productos':
                            self.tree.insert('', 'end', values=(pid, p.get('nombre'), p.get('descripcion'), p.get('precio_compra'), p.get('porcentaje_ganancia'), p.get('precio_venta'), p.get('stock'), p.get('stock_minimo')))
                        else: # Clientes and Proveedores
                            self.tree.insert('', 'end', values=(pid, p.get('nombre'), p.get('direccion'), p.get('telefono'), p.get('email')))
                else:
                    messagebox.showerror('Error', f'API error {status}: {r.text if "r" in locals() else "no response"}')

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def clear_form(self):
        self._current_id = None
        for ent in self.form_entries:
            ent.delete(0, 'end')
        self.form_entries[0].focus()

    def on_row_select(self, _event=None):
        sel = self.tree.focus()
        if not sel:
            return
        vals = self.tree.item(sel, "values")
        if not vals:
            return
        self._current_id = vals[0]
        for i in range(min(len(self.form_entries), len(vals)-1)):
            try:
                self.form_entries[i].delete(0, 'end')
                self.form_entries[i].insert(0, vals[i+1])
            except Exception:
                pass

    def save_current(self):
        resource = self.resource_var.get()
        if resource == 'Productos':
            payload = {
                'nombre': self.form_entries[0].get(),
                'descripcion': self.form_entries[1].get(),
                'precio_compra': float(self.form_entries[2].get() or 0),
                'porcentaje_ganancia': float(self.form_entries[3].get() or 0),
                'stock': int(self.form_entries[4].get() or 0),
                'stock_minimo': int(self.form_entries[5].get() or 0)
            }
        else: # Clientes and Proveedores
            payload = {
                'nombre': self.form_entries[0].get(),
                'direccion': self.form_entries[1].get(),
                'telefono': self.form_entries[2].get(),
                'email': self.form_entries[3].get()
            }
        def worker():
            try:
                if self._current_id:
                    r = SESSION.put(f"{API_URL}/{resource.lower()}/{self._current_id}", json=payload, timeout=6)
                else:
                    r = SESSION.post(f"{API_URL}/{resource.lower()}", json=payload, timeout=6)
                status = r.status_code
                text = r.text
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def ui_after():
                if status in (200,201,204):
                    messagebox.showinfo('OK', f'{resource[:-1]} guardado')
                    self.clear_form()
                    self.load_data_for(resource)
                else:
                    messagebox.showerror('Error', f'{status} {text}')

            self.after(0, ui_after)

        threading.Thread(target=worker, daemon=True).start()

    def delete_current(self):
        if not self._current_id:
            messagebox.showwarning('Selecciona', 'Selecciona un elemento')
            return
        if not messagebox.askyesno('Confirmar', '¿Eliminar?'):
            return
        resource = self.resource_var.get()
        def worker():
            try:
                r = SESSION.delete(f"{API_URL}/{resource.lower()}/{self._current_id}", timeout=6)
                status = r.status_code
                text = r.text
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def ui_after():
                if status in (200, 204):
                    messagebox.showinfo('OK', 'Eliminado')
                    self.clear_form()
                    self.load_data_for(resource)
                else:
                    messagebox.showerror('Error', f'Borrar: {status} {text}')

            self.after(0, ui_after)

        threading.Thread(target=worker, daemon=True).start()

    def on_close(self):
        if self._api_proc:
            self._api_proc.terminate()
            self._api_proc.wait(timeout=2)
        self.destroy()

    def on_resource_change(self, new_resource):
        for widget in self.form_labels + self.form_entries:
            widget.pack_forget()

        if new_resource == 'Productos':
            self.form_title.configure(text='Detalle del Producto')
            labels = ['Nombre', 'Descripción', 'Precio Compra', 'Porcentaje Ganancia', 'Stock', 'Stock Mínimo']
            cols = [('id', 'ID', 50), ('nombre', 'Nombre', 150), ('descripcion', 'Descripción', 200), ('precio_compra', 'P. Compra', 80), ('porcentaje_ganancia', '% Ganancia', 80), ('precio_venta', 'P. Venta', 80), ('stock', 'Stock', 60), ('stock_minimo', 'Stock Min.', 70)]
        else: # Clientes and Proveedores
            self.form_title.configure(text=f'Detalle de {new_resource[:-1]}')
            labels = ['Nombre', 'Dirección', 'Teléfono', 'Correo']
            cols = [('id', 'ID', 60), ('nombre', 'Nombre', 180), ('direccion', 'Dirección', 220), ('telefono', 'Teléfono', 120), ('email', 'Correo', 180)]

        for i, text in enumerate(labels):
            self.form_labels[i].configure(text=text)
            self.form_labels[i].pack(anchor="w", padx=8)
            self.form_entries[i].pack(padx=8, pady=4)

        self.tree.config(columns=[c[0] for c in cols])
        for col, text, width in cols:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width)
        
        self.clear_form()
        self.load_data_for(new_resource)

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()

    login_window = LoginWindow(root)
    root.wait_window(login_window)

    if login_window.user:
        app = MainApp()
        app.mainloop()