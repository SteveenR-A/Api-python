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

# Usar API_URL del entorno, o default
API_URL = os.getenv('API_URL', 'http://127.0.0.1:5000')


def make_session(retries: int = 3, backoff_factor: float = 0.5, status_forcelist=(429, 500, 502, 503, 504)):
    """Crear una requests.Session con reintentos."""
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


# Sesión global usada por la GUI
SESSION = make_session()


def ensure_api_running(timeout=5):
    """Asegura que la API esté corriendo; si no, la arranca."""
    global API_URL
    def is_up(url):
        try:
            r = SESSION.get(f"{url}/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    if is_up(API_URL):
        return None

    # Intentar arrancar la API en puerto 5000 (usando el app_compacto.py)
    target = f"http://127.0.0.1:5000"
    env = os.environ.copy()
    env['PORT'] = '5000'
    p = None
    try:
        # Asume que el servidor se llama 'app_compacto.py'
        p = subprocess.Popen([sys.executable, "app_compacto.py"], cwd='.', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except Exception as e:
        print(f"No se pudo iniciar app_compacto.py: {e}")

    start = time.time()
    while time.time() - start < timeout:
        if is_up(target):
            API_URL = target
            return p # Retorna el proceso para que pueda ser terminado al salir
        time.sleep(0.25)

    if p:
        p.terminate()

    # Si falla, preguntar al usuario
    answer = simpledialog.askstring("Configurar API", "No se pudo iniciar la API. Introduce la URL (ej: http://127.0.0.1:5000):", initialvalue=API_URL)
    if answer and is_up(answer):
    
        # En algunos entornos `wait_window` no mantiene el bucle de eventos
        # y los callbacks `after` desde hilos fallan con "main thread is not in main loop".
        # Usamos un pequeño loop que procesa eventos en el hilo principal hasta que
        # la ventana de login se cierre. Esto permite que `self.after(...)` funcione
        # correctamente desde hilos worker.
        try:
            import time as _time
            while True:
                if not login_window.winfo_exists():
                    break
                root.update()
                _time.sleep(0.05)
        except Exception:
            # En caso de que update falle, intentar fallback a wait_window
            try:
                root.wait_window(login_window)
            except Exception:
                pass
        return None

    messagebox.showerror("Error", "No se pudo conectar a la API. La aplicación se cerrará.")
    sys.exit(1)


def api_is_up(url, timeout=2):
    """Comprobar si la API responde en /health."""
    try:
        r = SESSION.get(f"{url}/health", timeout=timeout)
        if r.status_code == 200:
            return True, None
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


# --- CLASE LOGINWINDOW CON CORRECCIÓN DE CIERRE ---
class LoginWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Login")
        self.geometry("300x320")
        self.parent = parent
        self.user = None
        self.resizable(False, False)

        # Cola de tareas que los hilos pueden encolar para que el hilo
        # principal las ejecute de forma segura. Usamos un lock simple
        # para proteger la cola al acceder desde otros hilos.
        self._task_queue = []
        self._queue_lock = threading.Lock()
        # Iniciar el procesador de la cola en el hilo principal
        self.after(100, self._process_queue)

        title_label = ctk.CTkLabel(self, text="Iniciar Sesión", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(25, 15))

        self.username_entry = ctk.CTkEntry(self, placeholder_text="Username", width=240)
        self.username_entry.pack(pady=10, padx=30)

        self.password_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*", width=240)
        self.password_entry.pack(pady=10, padx=30)

        self.login_button = ctk.CTkButton(self, text="Login", command=self.login, width=240)
        self.login_button.pack(pady=(20, 10), padx=30)

        self.create_user_button = ctk.CTkButton(self,
                                                text="Crear 'admin' (pass 'admin')",
                                                command=self.create_test_user,
                                                width=240,
                                                fg_color="#555",
                                                hover_color="#666")
        self.create_user_button.pack(pady=10, padx=30)

        self.username_entry.focus()
        self.bind("<Return>", lambda e: self.login())

    def create_test_user(self):
        self.login_button.configure(state='disabled')
        self.create_user_button.configure(state='disabled')

        def worker():
            try:
                r = SESSION.post(f"{API_URL}/usuarios", json={"username": "admin", "password": "admin", "rol": "administrador"}, timeout=4)
                if r.status_code == 201:
                    self._enqueue(lambda: messagebox.showinfo("Usuario Creado", "Usuario 'admin' (pass 'admin') creado. Ahora puedes hacer login."))
                elif r.status_code == 409:
                    self._enqueue(lambda: messagebox.showinfo("Usuario Existe", "El usuario 'admin' ya existe."))
                else:
                    self._enqueue(lambda: messagebox.showerror("Error", f"No se pudo crear: {r.text}"))
            except Exception as e:
                self._enqueue(lambda e=e: messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}"))
            finally:
                # Encolar la reactivación de botones en el hilo principal
                self._enqueue(self.enable_buttons)

        threading.Thread(target=worker, daemon=True).start()

    def enable_buttons(self):
        try:
            self.login_button.configure(state='normal')
            self.create_user_button.configure(state='normal')
        except: pass # Evitar error si la ventana ya no existe

    # --- FUNCIÓN LOGIN CORREGIDA ---
    def login(self, event=None):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showwarning("Login", "Por favor, ingresa usuario y contraseña.")
            return

        self.login_button.configure(state='disabled')
        self.create_user_button.configure(state='disabled')

        # Función para procesar el resultado en el hilo principal de la GUI
        def process_login_result(result):
            # Siempre reactivar botones primero
            self.enable_buttons()

            status = result.get("status")
            data = result.get("data")
            error = result.get("error")

            if status == 200:
                self.user = data.get('user') if isinstance(data, dict) else None
                if self.user:
                    print("Login exitoso, cerrando ventana...") # Mensaje de depuración
                    self.destroy() # <<< CIERRA LA VENTANA AL TENER ÉXITO
                else:
                    messagebox.showerror("Error", "Login exitoso pero no se recibieron datos del usuario.")
            elif status == 401:
                messagebox.showerror("Error", "Credenciales inválidas")
            elif error:
                 messagebox.showerror("Conexión", f"No se pudo conectar a la API: {error}")
            else:
                 # Otro tipo de error del servidor
                 error_detail = data if isinstance(data, str) else data.get('error', 'Error desconocido')
                 messagebox.showerror("Error", f"Login falló: HTTP {status} - {error_detail}")

        # Función que se ejecuta en el hilo secundario
        def worker():
            result = {"status": None, "data": None, "error": None}
            try:
                print(f"Intentando login para '{username}' en {API_URL}/login") # Mensaje de depuración
                r = SESSION.post(f"{API_URL}/login", json={"username": username, "password": password}, timeout=4)
                result["status"] = r.status_code
                try:
                    # Intentar obtener JSON si es posible
                    if r.headers.get('content-type','').startswith('application/json'):
                        result["data"] = r.json()
                    else:
                        result["data"] = r.text # Guardar texto plano si no es JSON
                except requests.exceptions.JSONDecodeError:
                     result["data"] = r.text # Guardar texto plano si falla el JSON
            except requests.exceptions.RequestException as e:
                print(f"Error de conexión durante el login: {e}") # Mensaje de depuración
                result["error"] = str(e)
            except Exception as e: # Captura otros errores inesperados
                 print(f"Error inesperado durante el login: {e}") # Mensaje de depuración
                 result["error"] = f"Error inesperado: {e}"

            # Encolar la función process_login_result para que la ejecute el hilo principal
            self._enqueue(lambda res=result: process_login_result(res))

        # Iniciar el hilo de trabajo
        threading.Thread(target=worker, daemon=True).start()

    # ---------------- Cola de tareas para comunicación thread->UI ----------------
    def _enqueue(self, fn):
        """Encola una función para que sea ejecutada en el hilo principal.

        Los worker threads pueden llamar a esta función sin usar self.after.
        """
        with self._queue_lock:
            self._task_queue.append(fn)

    def _process_queue(self):
        """Ejecuta tareas encoladas por worker threads. Debe llamarse en el hilo principal."""
        # Sacar todas las tareas y ejecutarlas
        tasks = []
        with self._queue_lock:
            if self._task_queue:
                tasks = list(self._task_queue)
                self._task_queue.clear()

        for fn in tasks:
            try:
                fn()
            except Exception as e:
                print(f"Error ejecutando tarea en cola: {e}")

        # Volver a llamarse periódicamente mientras la ventana exista
        try:
            if self.winfo_exists():
                self.after(100, self._process_queue)
        except Exception:
            pass

# --- FIN DE LA FUNCIÓN LOGIN CORREGIDA ---


class ReportWindow(ctk.CTkToplevel):
    def __init__(self, parent, report_type):
        super().__init__(parent)
        self.title(f"Reporte de {report_type}")
        self.geometry("800x600")
        self.report_type = report_type
        self.parent = parent

        self.create_widgets()
        if self.report_type not in ["Existencias Mínimas", "Existencias"]:
            pass
        else:
            self.load_report()

    def create_widgets(self):
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(pady=10, padx=10, fill="x")

        if self.report_type in ["Ventas", "Ganancias", "Compras"]:
            ctk.CTkLabel(top_frame, text="Desde (YYYY-MM-DD):").pack(side="left", padx=5)
            self.desde_entry = ctk.CTkEntry(top_frame, placeholder_text="2023-01-01")
            self.desde_entry.pack(side="left", padx=5)
            ctk.CTkLabel(top_frame, text="Hasta (YYYY-MM-DD):").pack(side="left", padx=5)
            self.hasta_entry = ctk.CTkEntry(top_frame, placeholder_text="2023-12-31")
            self.hasta_entry.pack(side="left", padx=5)
            ctk.CTkButton(top_frame, text="Filtrar", command=self.load_report).pack(side="left", padx=5)
        else:
             ctk.CTkLabel(top_frame, text=f"Reporte: {self.report_type}").pack(side="left", padx=5)

        self.tree = ttk.Treeview(self, show="headings")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.summary_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.summary_label.pack(pady=5, padx=10, fill="x")

    def load_report(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.summary_label.configure(text="")

        endpoint_map = {
            "Ventas": "ventas",
            "Compras": "compras",
            "Ganancias": "ganancias",
            "Existencias Mínimas": "existencias_minimas",
            "Existencias": "existencias"
        }
        endpoint = f"{API_URL}/reportes/{endpoint_map.get(self.report_type)}"

        params = {}
        if self.report_type in ["Ventas", "Ganancias", "Compras"]:
            desde = self.desde_entry.get()
            hasta = self.hasta_entry.get()
            if not desde or not hasta:
                messagebox.showwarning("Filtro requerido", "Por favor ingrese un rango de fechas.")
                return
            params = {"desde": desde, "hasta": hasta}

        def worker():
            try:
                r = SESSION.get(endpoint, params=params, timeout=10)
                status = r.status_code
                data = r.json() if r.headers.get('content-type','').startswith('application/json') else None
                text = r.text
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}"))
                return

            def update_ui():
                if status == 200 and data is not None:
                    summary_text = ""
                    list_data = []

                    if self.report_type == "Ventas":
                        cols = [('id', 'ID', 50), ('fecha_venta', 'Fecha', 100), ('total', 'Total', 100), ('id_cliente', 'ID Cliente', 80), ('cliente', 'Cliente', 150)]
                        list_data = data.get('ventas', [])
                        summary_text = f"Total Ventas: {data.get('suma_total', 0):.2f}"
                    elif self.report_type == "Compras":
                        cols = [('id', 'ID', 50), ('fecha_compra', 'Fecha', 100), ('total', 'Total', 100), ('id_proveedor', 'ID Prov', 80), ('proveedor', 'Proveedor', 150)]
                        list_data = data.get('compras', [])
                        summary_text = f"Total Compras: {data.get('suma_total', 0):.2f}"
                    elif self.report_type == "Ganancias":
                        cols = [('producto', 'Producto', 150), ('cantidad_vendida', 'Cant.', 80), ('total_ventas', 'T. Ventas', 100), ('total_costo', 'T. Costo', 100), ('ganancia', 'Ganancia', 100)]
                        list_data = data.get('ganancias_por_producto', [])
                        summary_text = f"Ganancia Total: {data.get('ganancia_total', 0):.2f}"
                    elif self.report_type == "Existencias Mínimas":
                        cols = [('nombre', 'Nombre', 150), ('stock', 'Stock', 100), ('stock_minimo', 'Stock Mínimo', 100)]
                        list_data = data
                    elif self.report_type == "Existencias":
                        cols = [('nombre', 'Nombre', 150), ('stock', 'Stock', 100)]
                        list_data = data

                    self.configure_tree(cols)
                    for item in list_data:
                        self.tree.insert("", "end", values=tuple(item.get(c[0]) for c in cols))

                    self.summary_label.configure(text=summary_text)

                else:
                    messagebox.showerror("Error", f"API error {status}: {text}")

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def configure_tree(self, columns):
        self.tree.config(columns=[c[0] for c in columns])
        for col, text, width in columns:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")


class MainApp(ctk.CTk):
    def __init__(self, user_role='vendedor'):
        super().__init__()
        self.title("Sistema de Inventario")
        self.geometry("1024x768")
        self.user_role = user_role
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._api_proc = None # Para guardar el proceso de la API si la GUI lo inicia

        # Iniciar API en background
        threading.Thread(target=self._start_api_check, daemon=True).start()

        self.create_widgets()
        self.on_resource_change(self.resource_var.get()) # Cargar productos por defecto
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _start_api_check(self):
        """Wrapper que ejecuta ensure_api_running en background."""
        proc = ensure_api_running()
        def cb():
            self._api_proc = proc
        self.after(0, cb)

    def create_widgets(self):
        # Frame principal
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        main_frame.grid_columnconfigure(0, weight=3) # Columna para la tabla
        main_frame.grid_columnconfigure(1, weight=1) # Columna para el formulario
        main_frame.grid_rowconfigure(0, weight=0) # Fila para selectores
        main_frame.grid_rowconfigure(1, weight=1) # Fila para tabla/formulario

        # --- Selectores y Menús (Fila 0) ---
        selector_frame = ctk.CTkFrame(main_frame)
        selector_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(selector_frame, text="Módulo:", width=60).pack(side="left", padx=(10, 5))

        # Módulos permitidos
        modules = ["Productos", "Clientes", "Proveedores"]
        if self.user_role == 'administrador':
             pass

        self.resource_var = ctk.StringVar(value="Productos")
        self.resource_menu = ctk.CTkOptionMenu(selector_frame, values=modules, variable=self.resource_var, command=self.on_resource_change)
        self.resource_menu.pack(side="left", padx=5)

        # Menú de Reportes
        reports_button = ctk.CTkButton(selector_frame, text="Reportes", command=self.open_reports_menu)
        reports_button.pack(side="left", padx=20)

        # Botón de Salir
        ctk.CTkButton(selector_frame, text="Salir", fg_color="#6c757d", command=self.on_close).pack(side="right", padx=10)

        # --- Tabla (Fila 1, Columna 0) ---
        table_frame = ctk.CTkFrame(main_frame)
        table_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        table_frame.pack_propagate(False) # Evitar que el frame se encoja

        self.tree = ttk.Treeview(table_frame, show="headings")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        # --- Formulario (Fila 1, Columna 1) ---
        self.form_frame = ctk.CTkFrame(main_frame)
        self.form_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        self.form_title = ctk.CTkLabel(self.form_frame, text="Detalle", font=ctk.CTkFont(size=16, weight="bold"))
        self.form_title.pack(pady=(10, 15), padx=10)

        # Contenedor para los campos del formulario
        self.fields_container = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        self.fields_container.pack(fill="x", expand=True, padx=10)

        # Diccionario para guardar etiquetas y campos
        self.form_fields = {}

        # Botones del formulario
        buttons_frame = ctk.CTkFrame(self.form_frame)
        buttons_frame.pack(side="bottom", fill="x", padx=10, pady=10)

        self.btn_new = ctk.CTkButton(buttons_frame, text="Nuevo", command=self.clear_form)
        self.btn_new.pack(fill="x", pady=4)
        self.btn_save = ctk.CTkButton(buttons_frame, text="Guardar", command=self.save_current)
        self.btn_save.pack(fill="x", pady=4)

        if self.user_role == 'administrador':
            self.btn_delete = ctk.CTkButton(buttons_frame, text="Borrar", fg_color="#d9534f", hover_color="#b52b27", command=self.delete_current)
            self.btn_delete.pack(fill="x", pady=4)

        self._current_id = None

    def open_reports_menu(self):
        """Abre una ventana para seleccionar reportes."""

        if hasattr(self, 'report_menu_window') and self.report_menu_window.winfo_exists():
            self.report_menu_window.focus()
            return

        self.report_menu_window = ctk.CTkToplevel(self)
        self.report_menu_window.title("Reportes")
        self.report_menu_window.geometry("250x300")

        report_list = {
            "Ventas por Fecha": "Ventas",
            "Compras por Fecha": "Compras",
            "Ganancias por Fecha": "Ganancias",
            "Existencias Mínimas": "Existencias Mínimas",
            "Catálogo de Existencias": "Existencias",
        }

        for text, report_type in report_list.items():
            disabled = False
            if self.user_role != 'administrador' and report_type in ["Ganancias", "Compras"]:
                disabled = True

            btn = ctk.CTkButton(
                self.report_menu_window,
                text=text,
                command=lambda rt=report_type: self.open_report_window(rt),
                state="disabled" if disabled else "normal"
            )
            btn.pack(pady=5, padx=10, fill="x")

    def open_report_window(self, report_type):
        ReportWindow(self, report_type)

    def load_data_for(self, resource):
        """Carga datos en el Treeview para el recurso (Productos, Clientes, etc.)"""
        for ch in self.tree.get_children():
            self.tree.delete(ch)

        endpoint = f"{API_URL}/{resource.lower()}"

        def worker():
            try:
                r = SESSION.get(endpoint, timeout=4)
                status = r.status_code
                data = r.json() if r.headers.get('content-type','').startswith('application/json') else None
                text = r.text
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def update_ui():
                if status == 200 and data is not None:
                    if not data: return # No hay datos

                    cols_map = self.get_resource_config(resource).get("cols_map", {})
                    cols = []
                    # Asegurar que el ID sea la primera columna si existe
                    if 'id' in data[0] and 'id' in cols_map:
                         cols.append(('id', cols_map['id'][0], cols_map['id'][1]))

                    # Añadir el resto de columnas según el mapeo
                    for key in data[0].keys():
                        if key == 'id': continue # Ya se añadió
                        col_config = cols_map.get(key)
                        if col_config:
                            cols.append((key, col_config[0], col_config[1]))

                    self.configure_tree(cols)

                    for item in data:
                        values = tuple(item.get(c[0]) for c in cols)
                        self.tree.insert('', 'end', values=values)
                elif status >= 400: # Mostrar error si la API responde con error
                     messagebox.showerror('Error de API', f'Error al cargar {resource}: {status} - {text}')

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def clear_form(self):
        self._current_id = None
        for name, field in self.form_fields.items():
            field["entry"].delete(0, 'end')

        if self.form_fields:
            first_field_key = next(iter(self.form_fields))
            self.form_fields[first_field_key]["entry"].focus()

    def on_row_select(self, _event=None):
        sel = self.tree.focus()
        if not sel: return
        vals = self.tree.item(sel, "values")
        if not vals: return

        col_names = self.tree.cget("columns")
        if not col_names: return

        self.clear_form()

        # Asignar ID
        if col_names[0] == 'id': # Verificar si la primera columna es 'id'
             self._current_id = vals[0]
        else:
             self._current_id = None # O manejar como error si se espera siempre un ID

        # Llenar formulario (empezando desde el segundo valor si el primero es ID)
        start_index = 1 if self._current_id is not None and col_names[0] == 'id' else 0
        form_keys = list(self.form_fields.keys())

        for i in range(len(form_keys)):
             col_index = i + start_index
             if col_index < len(vals) and i < len(form_keys):
                 form_key = form_keys[i]
                 # Convertir None a cadena vacía para la entrada
                 value_to_insert = vals[col_index] if vals[col_index] is not None else ""
                 self.form_fields[form_key]["entry"].insert(0, value_to_insert)


    def save_current(self):
        """Guarda el item actual (POST si es nuevo, PUT si existe)"""
        resource = self.resource_var.get()
        config = self.get_resource_config(resource)

        payload = {}
        try:
            for name, field in self.form_fields.items():
                value_str = field["entry"].get()
                field_type = field["type"]

                # Manejar valores vacíos o None
                if not value_str:
                    # Si el campo no es requerido y está vacío, enviarlo como None o omitirlo
                    # (Depende de cómo la API maneje los nulos)
                    # Aquí lo enviaremos como None si el tipo no es string
                    if field_type != str:
                         payload[name] = None
                    else:
                         payload[name] = "" # Enviar cadena vacía para strings
                    continue

                # Convertir a tipo numérico si es necesario
                if field_type == float:
                    payload[name] = float(value_str)
                elif field_type == int:
                    payload[name] = int(value_str)
                else:
                    payload[name] = value_str
        except ValueError as e:
            messagebox.showerror("Error de Formato", f"Valor inválido para {name}: {e}. Asegúrese de usar números donde corresponda.")
            return

        # Validar campos requeridos (ahora con el payload procesado)
        for req_field in config.get("required_fields", []):
             # Considera 0 como un valor válido para campos numéricos requeridos
            if payload.get(req_field) is None or (isinstance(payload.get(req_field), str) and not payload.get(req_field)):
                 # Verificar si el tipo es numérico y el valor es 0, lo cual es válido
                 field_config = config["fields"].get(req_field)
                 is_numeric = field_config and field_config[1] in [int, float]
                 if not (is_numeric and payload.get(req_field) == 0):
                    messagebox.showwarning("Campo Requerido", f"El campo '{req_field}' es requerido.")
                    return


        def worker():
            nonlocal payload # Permitir modificar payload si la API devuelve el objeto creado/actualizado
            try:
                endpoint = f"{API_URL}/{resource.lower()}"
                if self._current_id:
                    # Actualizar (PUT)
                    print(f"PUT {endpoint}/{self._current_id} with payload: {payload}") # Debug
                    r = SESSION.put(f"{endpoint}/{self._current_id}", json=payload, timeout=6)
                else:
                    # Crear (POST)
                    print(f"POST {endpoint} with payload: {payload}") # Debug
                    r = SESSION.post(endpoint, json=payload, timeout=6)

                status = r.status_code
                try:
                    response_data = r.json() if r.headers.get('content-type','').startswith('application/json') else r.text
                except requests.exceptions.JSONDecodeError:
                    response_data = r.text

            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def ui_after():
                print(f"Save response: {status} - {response_data}") # Debug
                if status in (200, 201): # 200 OK (Update), 201 Created (Post)
                    messagebox.showinfo('OK', f'{resource.rstrip("s")} guardado')
                    self.clear_form()
                    self.load_data_for(resource) # Recargar la tabla
                else:
                     error_msg = response_data if isinstance(response_data, str) else response_data.get('error', 'Error desconocido')
                     messagebox.showerror('Error', f'Error al guardar: {status} - {error_msg}')


            self.after(0, ui_after)

        threading.Thread(target=worker, daemon=True).start()

    def delete_current(self):
        if not self._current_id:
            messagebox.showwarning('Selecciona', 'Selecciona un elemento de la tabla para borrar.')
            return
        if not messagebox.askyesno('Confirmar', f'¿Eliminar el registro {self._current_id}?'):
            return

        resource = self.resource_var.get()

        def worker():
            try:
                endpoint = f"{API_URL}/{resource.lower()}/{self._current_id}"
                print(f"DELETE {endpoint}") # Debug
                r = SESSION.delete(endpoint, timeout=6)
                status = r.status_code
                try:
                    response_data = r.json() if r.headers.get('content-type','').startswith('application/json') else r.text
                except requests.exceptions.JSONDecodeError:
                    response_data = r.text

            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def ui_after():
                print(f"Delete response: {status} - {response_data}") # Debug
                if status in (200, 204): # 200 OK, 204 No Content
                    messagebox.showinfo('OK', 'Eliminado')
                    self.clear_form()
                    self.load_data_for(resource) # Recargar la tabla
                elif status == 404:
                     messagebox.showerror('Error', 'Error al borrar: Registro no encontrado (404)')
                else:
                    error_msg = response_data if isinstance(response_data, str) else response_data.get('error', 'Error desconocido')
                    messagebox.showerror('Error', f'Error al borrar: {status} - {error_msg}')


            self.after(0, ui_after)

        threading.Thread(target=worker, daemon=True).start()

    def on_close(self):
        """Maneja el cierre de la ventana principal."""
        if self._api_proc: # Si la GUI inició la API, la termina
            try:
                print("Terminando proceso de API...")
                self._api_proc.terminate()
                self._api_proc.wait(timeout=1)
                print("Proceso de API terminado.")
            except Exception as e:
                print(f"No se pudo terminar el proceso de la API: {e}")
        self.destroy()

    def get_resource_config(self, resource):
        """Define la configuración del formulario y la tabla para cada módulo."""

        if resource == 'Productos':
            return {
                "title": "Detalle del Producto",
                "fields": {
                    "nombre": ["Nombre", str, True],
                    "descripcion": ["Descripción", str, False],
                    "precio_compra": ["Precio Compra", float, True],
                    "porcentaje_ganancia": ["% Ganancia", float, True],
                    "stock": ["Stock", int, True],
                    "stock_minimo": ["Stock Mínimo", int, True],
                    "id_proveedor": ["ID Proveedor (Opcional)", int, False], # Campo añadido
                },
                "cols_map": {
                    "id": ["ID", 50],
                    "nombre": ["Nombre", 150],
                    "descripcion": ["Descripción", 200],
                    "precio_compra": ["P. Compra", 80],
                    "porcentaje_ganancia": ["% Ganancia", 80],
                    "precio_venta": ["P. Venta", 80],
                    "stock": ["Stock", 60],
                    "stock_minimo": ["Stock Min.", 70],
                     "id_proveedor": ["ID Prov.", 60], # Columna añadida
                },
                "required_fields": ["nombre", "precio_compra", "porcentaje_ganancia", "stock", "stock_minimo"]
            }
        elif resource == 'Clientes':
             title = f'Detalle de {resource.rstrip("s")}'
             return {
                "title": title,
                "fields": {
                    "nombre": ["Nombre", str, True],
                    "direccion": ["Dirección", str, False],
                    "telefono": ["Teléfono", str, False],
                    "email": ["Correo", str, False],
                },
                "cols_map": {
                    "id": ["ID", 60],
                    "nombre": ["Nombre", 180],
                    "direccion": ["Dirección", 220],
                    "telefono": ["Teléfono", 120],
                    "email": ["Correo", 180],
                },
                "required_fields": ["nombre"]
             }
        elif resource == 'Proveedores':
             title = f'Detalle de {resource.rstrip("s")}'
             return {
                "title": title,
                "fields": {
                    "nombre": ["Nombre", str, True],
                    "direccion": ["Dirección", str, False],
                    "telefono": ["Teléfono", str, False],
                    "email": ["Correo", str, False],
                },
                "cols_map": {
                    "id": ["ID", 60],
                    "nombre": ["Nombre", 180],
                    "direccion": ["Dirección", 220],
                    "telefono": ["Teléfono", 120],
                    "email": ["Correo", 180],
                },
                "required_fields": ["nombre"]
             }
        else:
             # Default o para otros recursos no completamente implementados
             return {"title": f"Detalle de {resource.rstrip('s')}", "fields": {}, "cols_map": {}, "required_fields": []}


    def on_resource_change(self, new_resource):
        """Reconfigura el formulario y la tabla al cambiar de módulo."""

        for widget in self.fields_container.winfo_children():
            widget.destroy()
        self.form_fields = {}

        config = self.get_resource_config(new_resource)
        self.form_title.configure(text=config["title"])

        for name, (label_text, field_type, is_required) in config["fields"].items():
            label = ctk.CTkLabel(self.fields_container, text=f"{label_text}{'*' if is_required else ''}")
            label.pack(anchor="w", padx=0, pady=(10, 0))
            entry = ctk.CTkEntry(self.fields_container, width=260)
            entry.pack(fill="x", padx=0, pady=2)
            self.form_fields[name] = {"label": label, "entry": entry, "type": field_type}

        self.clear_form()
        self.load_data_for(new_resource)

    def configure_tree(self, columns):
        """Configura las columnas del Treeview."""
        # Limpiar columnas anteriores por si acaso
        self.tree.config(columns=[])
        self.tree.config(columns=[c[0] for c in columns])

        # Configurar cada columna
        for col, text, width in columns:
            try:
                self.tree.heading(col, text=text)
                self.tree.column(col, width=width, anchor="w")
            except Exception as e:
                print(f"Error configurando columna '{col}': {e}")


# --- Bloque para ejecutar la GUI ---
if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw() # Ocultar la ventana raíz principal

    # Mostrar ventana de Login
    login_window = LoginWindow(root)
    
    # Mantener el bucle de eventos activo para permitir callbacks desde hilos
    try:
        import time as _time
        while True:
            if not login_window.winfo_exists():
                break
            root.update()
            _time.sleep(0.05)
    except Exception:
        try:
            root.wait_window(login_window)
        except Exception:
            pass

    if getattr(login_window, 'user', None):
        # Si el login es exitoso, mostrar la app principal
        app = MainApp(user_role=login_window.user.get('rol', 'vendedor'))
        app.mainloop()
    else:
        # Si el usuario cerró el login, salir
        print("Login cancelado o fallido. Saliendo.")
        root.destroy()