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
        API_URL = answer
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


class LoginWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Login")
        self.geometry("300x240")
        self.parent = parent
        self.user = None

        self.username_entry = ctk.CTkEntry(self, placeholder_text="Username")
        self.username_entry.pack(pady=10, padx=20, fill="x")
        self.password_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*")
        self.password_entry.pack(pady=10, padx=20, fill="x")

        self.login_button = ctk.CTkButton(self, text="Login", command=self.login)
        self.login_button.pack(pady=20, padx=20, fill="x")
        
        self.create_user_button = ctk.CTkButton(self, text="Crear Usuario 'admin' (pass 'admin')", command=self.create_test_user)
        self.create_user_button.pack(pady=10, padx=20, fill="x")

        self.username_entry.focus()
        self.bind("<Return>", lambda e: self.login())

    def create_test_user(self):
        self.login_button.configure(state='disabled')
        self.create_user_button.configure(state='disabled')
        
        def worker():
            try:
                # Crear un usuario 'admin' con rol 'administrador' y clave 'admin'
                r = SESSION.post(f"{API_URL}/usuarios", json={"username": "admin", "password": "admin", "rol": "administrador"}, timeout=4)
                if r.status_code == 201:
                    self.after(0, lambda: messagebox.showinfo("Usuario Creado", "Usuario 'admin' (pass 'admin') creado. Ahora puedes hacer login."))
                elif r.status_code == 409:
                    self.after(0, lambda: messagebox.showinfo("Usuario Existe", "El usuario 'admin' ya existe."))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", f"No se pudo crear: {r.text}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}"))
            finally:
                self.after(0, self.enable_buttons)
        
        threading.Thread(target=worker, daemon=True).start()

    def enable_buttons(self):
        try:
            self.login_button.configure(state='normal')
            self.create_user_button.configure(state='normal')
        except: pass # La ventana puede estar cerrada

    def login(self, event=None):
        username = self.username_entry.get()
        password = self.password_entry.get()
        if not username or not password:
            messagebox.showwarning("Login", "Por favor, ingresa usuario y contraseña.")
            return

        self.login_button.configure(state='disabled')
        self.create_user_button.configure(state='disabled')

        def worker():
            try:
                r = SESSION.post(f"{API_URL}/login", json={"username": username, "password": password}, timeout=4)
                if r.status_code == 200:
                    self.user = r.json().get('user')
                    self.after(0, self.destroy)
                elif r.status_code == 401:
                    self.after(0, lambda: messagebox.showerror("Error", "Credenciales inválidas"))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", f"Login falló: HTTP {r.status_code}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}"))
            finally:
                self.after(0, self.enable_buttons)

        threading.Thread(target=worker, daemon=True).start()


class ReportWindow(ctk.CTkToplevel):
    def __init__(self, parent, report_type):
        super().__init__(parent)
        self.title(f"Reporte de {report_type}")
        self.geometry("800x600")
        self.report_type = report_type
        self.parent = parent

        self.create_widgets()
        if self.report_type not in ["Existencias Mínimas", "Existencias"]:
            # No cargar reportes de fecha hasta que el usuario ponga fechas
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
             # Administrador puede ver todo (ej. Compras, Ventas, Usuarios)
             # modules.extend(["Compras", "Ventas", "Usuarios"]) # Descomentar si se implementan formularios
             pass

        self.resource_var = ctk.StringVar(value="Productos")
        self.resource_menu = ctk.CTkOptionMenu(selector_frame, values=modules, variable=self.resource_var, command=self.on_resource_change)
        self.resource_menu.pack(side="left", padx=5)

        # Menú de Reportes [cite: 1181-1185]
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
        
        # Solo admin puede borrar (ejemplo de restricción por rol)
        if self.user_role == 'administrador':
            self.btn_delete = ctk.CTkButton(buttons_frame, text="Borrar", fg_color="#d9534f", hover_color="#b52b27", command=self.delete_current)
            self.btn_delete.pack(fill="x", pady=4)

        self._current_id = None

    def open_reports_menu(self):
        """Abre una ventana para seleccionar reportes[cite: 1181, 1182, 1183, 1184, 1185]."""
        
        # Evitar abrir múltiples ventanas de reportes
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
            # "Catálogo de Productos": "Productos_Catalogo", # Se pueden añadir más
            # "Catálogo de Clientes": "Clientes_Catalogo",
            # "Catálogo de Proveedores": "Proveedores_Catalogo",
        }
        
        for text, report_type in report_list.items():
            # Deshabilitar reportes si el rol no lo permite
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
                    
                    # Usar las llaves del primer item para definir columnas
                    cols_map = self.get_resource_config(resource).get("cols_map", {})
                    cols = []
                    for key in data[0].keys():
                        col_config = cols_map.get(key)
                        if col_config:
                            cols.append((key, col_config[0], col_config[1]))
                        else:
                            # Default para columnas no mapeadas (opcional)
                            # cols.append((key, key.capitalize(), 100))
                            pass
                    
                    self.configure_tree(cols)
                    
                    for item in data:
                        values = tuple(item.get(c[0]) for c in cols)
                        self.tree.insert('', 'end', values=values)
                else:
                    messagebox.showerror('Error', f'API error {status}: {text}')

            self.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def clear_form(self):
        self._current_id = None
        for name, field in self.form_fields.items():
            field["entry"].delete(0, 'end')
        
        # Enfocar el primer campo
        if self.form_fields:
            first_field_key = next(iter(self.form_fields))
            self.form_fields[first_field_key]["entry"].focus()

    def on_row_select(self, _event=None):
        sel = self.tree.focus()
        if not sel: return
        vals = self.tree.item(sel, "values")
        if not vals: return
        
        # Mapear valores de la fila a los campos del formulario
        col_names = self.tree.cget("columns")
        if not col_names: return

        self.clear_form()
        
        # El ID (columna 0) se guarda, no se muestra en el formulario
        self._current_id = vals[0] 
        
        for i, col_name in enumerate(col_names):
            if col_name in self.form_fields:
                field = self.form_fields[col_name]
                field["entry"].insert(0, vals[i])

    def save_current(self):
        """Guarda el item actual (POST si es nuevo, PUT si existe)"""
        resource = self.resource_var.get()
        config = self.get_resource_config(resource)
        
        payload = {}
        try:
            for name, field in self.form_fields.items():
                value = field["entry"].get()
                # Convertir a tipo numérico si es necesario
                if field["type"] == float:
                    payload[name] = float(value or 0)
                elif field["type"] == int:
                    payload[name] = int(value or 0)
                else:
                    payload[name] = value
        except ValueError as e:
            messagebox.showerror("Error de Formato", f"Valor inválido: {e}")
            return
        
        # Validar campos requeridos
        for req_field in config.get("required_fields", []):
            if not payload.get(req_field):
                messagebox.showwarning("Campo Requerido", f"El campo '{req_field}' es requerido.")
                return

        def worker():
            try:
                endpoint = f"{API_URL}/{resource.lower()}"
                if self._current_id:
                    # Actualizar (PUT)
                    r = SESSION.put(f"{endpoint}/{self._current_id}", json=payload, timeout=6)
                else:
                    # Crear (POST)
                    r = SESSION.post(endpoint, json=payload, timeout=6)
                
                status = r.status_code
                text = r.text
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def ui_after():
                if status in (200, 201): # 200 OK (Update), 201 Created (Post)
                    messagebox.showinfo('OK', f'{resource.rstrip("s")} guardado')
                    self.clear_form()
                    self.load_data_for(resource)
                else:
                    messagebox.showerror('Error', f'{status} {text}')

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
                r = SESSION.delete(endpoint, timeout=6)
                status = r.status_code
                text = r.text
            except Exception as e:
                self.after(0, lambda: messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}'))
                return

            def ui_after():
                if status in (200, 204): # 200 OK, 204 No Content
                    messagebox.showinfo('OK', 'Eliminado')
                    self.clear_form()
                    self.load_data_for(resource)
                else:
                    messagebox.showerror('Error', f'Error al borrar: {status} {text}')

            self.after(0, ui_after)

        threading.Thread(target=worker, daemon=True).start()

    def on_close(self):
        """Maneja el cierre de la ventana principal."""
        if self._api_proc: # Si la GUI inició la API, la termina
            try:
                self._api_proc.terminate()
                self._api_proc.wait(timeout=1)
            except Exception as e:
                print(f"No se pudo terminar el proceso de la API: {e}")
        self.destroy()

    def get_resource_config(self, resource):
        """Define la configuración del formulario y la tabla para cada módulo."""
        
        # Define los campos del formulario (key: [Label, tipo, requerido])
        # Define las columnas del Treeview (key: [Header, width])
        # La 'key' debe coincidir con el JSON de la API
        
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
                    "id_proveedor": ["ID Proveedor", int, False],
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
                },
                "required_fields": ["nombre", "precio_compra", "porcentaje_ganancia"]
            }
        else: # Clientes y Proveedores [cite: 1179, 1180]
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

    def on_resource_change(self, new_resource):
        """Reconfigura el formulario y la tabla al cambiar de módulo."""
        
        # Limpiar formulario anterior
        for widget in self.fields_container.winfo_children():
            widget.destroy()
        self.form_fields = {}

        config = self.get_resource_config(new_resource)
        self.form_title.configure(text=config["title"])

        # Crear nuevos campos de formulario
        for name, (label_text, field_type, is_required) in config["fields"].items():
            label = ctk.CTkLabel(self.fields_container, text=f"{label_text}{'*' if is_required else ''}")
            label.pack(anchor="w", padx=0, pady=(10, 0))
            entry = ctk.CTkEntry(self.fields_container, width=260)
            entry.pack(fill="x", padx=0, pady=2)
            self.form_fields[name] = {"label": label, "entry": entry, "type": field_type}

        # Cargar datos en la tabla
        self.clear_form()
        self.load_data_for(new_resource)
    
    def configure_tree(self, columns):
        """Configura las columnas del Treeview."""
        self.tree.config(columns=[c[0] for c in columns])
        for col, text, width in columns:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")

# --- Bloque para ejecutar la GUI ---
if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    
    root = ctk.CTk()
    root.withdraw() # Ocultar la ventana raíz principal

    # Mostrar ventana de Login
    login_window = LoginWindow(root)
    root.wait_window(login_window) # Esperar a que se cierre el login

    if login_window.user:
        # Si el login es exitoso, mostrar la app principal
        app = MainApp(user_role=login_window.user.get('rol', 'vendedor'))
        app.mainloop()
    else:
        # Si el usuario cerró el login, salir
        root.destroy()