import customtkinter as ctk
import requests
import subprocess
import time
import sys
from tkinter import messagebox
from tkinter import ttk

API_URL = "http://127.0.0.1:5000"


def ensure_api_running(timeout=5):
    """Asegura que la API esté corriendo; si no, la arranca con el mismo python."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=1)
        if r.status_code == 200:
            return None
    except Exception:
        pass

    # arrancar
    p = subprocess.Popen([sys.executable, "app.py"], cwd='.', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # esperar hasta que responda /health o hasta timeout
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{API_URL}/health", timeout=1)
            if r.status_code == 200:
                return p
        except Exception:
            time.sleep(0.25)
    return p


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
        try:
            r = requests.post(f"{API_URL}/usuarios", json={"username": "test", "password": "test"}, timeout=3)
            if r.status_code == 201:
                messagebox.showinfo("Usuario Creado", "Usuario de prueba 'test' con contraseña 'test' creado exitosamente.")
            else:
                messagebox.showerror("Error", f"No se pudo crear el usuario: {r.text}")
        except requests.RequestException as e:
            messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}")

    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        try:
            r = requests.post(f"{API_URL}/login", json={"username": username, "password": password}, timeout=3)
            if r.status_code == 200:
                self.user = r.json().get("user")
                self.destroy()
            else:
                messagebox.showerror("Error", "Credenciales inválidas")
        except requests.RequestException as e:
            messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}")


class ProveedoresApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestión de Proveedores")
        self.geometry("900x600")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        # Layout
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=16, pady=16, fill="both", expand=True)

        # Resource selector (Proveedores / Productos / Clientes)
        selector_frame = ctk.CTkFrame(main_frame)
        selector_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(selector_frame, text="Recurso:", width=80).pack(side="left", padx=(8, 4))
        self.resource_var = ctk.StringVar(value="Proveedores")
        self.resource_menu = ctk.CTkOptionMenu(selector_frame, values=["Proveedores", "Productos", "Clientes"], variable=self.resource_var, command=self.on_resource_change)
        self.resource_menu.pack(side="left")

        table_frame = ctk.CTkFrame(main_frame)
        table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        form_frame = ctk.CTkFrame(main_frame)
        form_frame.pack(side="right", fill="y")

        # Treeview (configurable per recurso)
        self.tree = ttk.Treeview(table_frame, show="headings")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        # Form (reutilizable)
        self.form_title = ctk.CTkLabel(form_frame, text="Detalle", font=ctk.CTkFont(size=14, weight="bold"))
        self.form_title.pack(pady=(8, 12))

        # four generic labeled entries
        self.form_labels = []
        self.form_entries = []
        for _ in range(4):
            lbl = ctk.CTkLabel(form_frame, text="")
            lbl.pack(anchor="w", padx=8)
            ent = ctk.CTkEntry(form_frame, width=260)
            ent.pack(padx=8, pady=4)
            self.form_labels.append(lbl)
            self.form_entries.append(ent)

        # hidden id
        self._current_id = None

        ctk.CTkButton(form_frame, text="Nuevo", command=self.clear_form).pack(fill="x", padx=8, pady=(12, 4))
        ctk.CTkButton(form_frame, text="Guardar", command=self.save_current).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(form_frame, text="Borrar", fg_color="#d9534f", command=self.delete_current).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(form_frame, text="Salir", fg_color="#6c757d", command=self.on_close).pack(fill="x", padx=8, pady=(12, 4))

        # Start API if needed
        self._api_proc = ensure_api_running()

        # initial resource
        self.on_resource_change(self.resource_var.get())

        # On close handler
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_proveedores(self):
        # clear
        self.load_data_for('Proveedores')

    def load_data_for(self, resource):
        # clear
        for ch in self.tree.get_children():
            self.tree.delete(ch)
        try:
            r = requests.get(f"{API_URL}/{resource.lower()}", timeout=3)
            if r.status_code == 200:
                data = r.json()
                for p in data:
                    pid = p.get('id') or p.get('id_' + resource[:-1].lower())
                    if resource == 'Proveedores' or resource == 'Clientes':
                        self.tree.insert('', 'end', values=(pid, p.get('nombre'), p.get('direccion'), p.get('telefono'), p.get('email')))
                    elif resource == 'Productos':
                        self.tree.insert('', 'end', values=(pid, p.get('nombre'), p.get('descripcion'), p.get('precio'), p.get('cantidad')))
            else:
                messagebox.showerror('Error', f'API error {r.status_code}: {r.text}')
        except requests.RequestException as e:
            messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}')

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
        # populate form entries depending on visible columns
        for i in range(min(len(self.form_entries), len(vals)-1)):
            try:
                self.form_entries[i].delete(0, 'end')
                self.form_entries[i].insert(0, vals[i+1])
            except Exception:
                pass

    def save_proveedor(self):
        # legacy method kept for backward compatibility
        self.save_current()

    def save_current(self):
        resource = self.resource_var.get()
        # build payload based on resource
        if resource in ('Proveedores', 'Clientes'):
            payload = {
                'nombre': self.form_entries[0].get(),
                'direccion': self.form_entries[1].get(),
                'telefono': self.form_entries[2].get(),
                'email': self.form_entries[3].get()
            }
        elif resource == 'Productos':
            payload = {
                'nombre': self.form_entries[0].get(),
                'descripcion': self.form_entries[1].get(),
                'precio': float(self.form_entries[2].get() or 0),
                'cantidad': int(self.form_entries[3].get() or 0)
            }
        else:
            return
        try:
            if self._current_id:
                r = requests.put(f"{API_URL}/{resource.lower()}/{self._current_id}", json=payload, timeout=4)
            else:
                r = requests.post(f"{API_URL}/{resource.lower()}", json=payload, timeout=4)
            if r.status_code in (200, 201, 204):
                messagebox.showinfo('OK', f'{resource[:-1]} guardado')
                self.clear_form()
                self.load_data_for(resource)
            else:
                messagebox.showerror('Error', f'{r.status_code} {r.text}')
        except requests.RequestException as e:
            messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}')

    def delete_proveedor(self):
        # kept for compatibility
        self.delete_current()

    def delete_current(self):
        if not self._current_id:
            messagebox.showwarning('Selecciona', 'Selecciona un elemento')
            return
        if not messagebox.askyesno('Confirmar', '¿Eliminar?'):
            return
        resource = self.resource_var.get()
        try:
            r = requests.delete(f"{API_URL}/{resource.lower()}/{self._current_id}", timeout=4)
            if r.status_code in (200, 204):
                messagebox.showinfo('OK', 'Eliminado')
                self.clear_form()
                self.load_data_for(resource)
            else:
                messagebox.showerror('Error', f'Borrar: {r.status_code} {r.text}')
        except requests.RequestException as e:
            messagebox.showerror('Conexión', f'No se pudo conectar a la API: {e}')

    def on_close(self):
        # si arrancamos la API, intentar terminarla
        try:
            if self._api_proc:
                self._api_proc.terminate()
                self._api_proc.wait(timeout=2)
        except Exception:
            pass
        self.destroy()

    def on_resource_change(self, new_resource):
        # reconfigure UI for the selected resource
        resource = new_resource
        # configure form title and labels
        if resource == 'Proveedores':
            self.form_title.configure(text='Detalle del Proveedor')
            labels = ['Nombre', 'Dirección', 'Teléfono', 'Correo']
        elif resource == 'Productos':
            self.form_title.configure(text='Detalle del Producto')
            labels = ['Nombre', 'Descripción', 'Precio', 'Cantidad']
        elif resource == 'Clientes':
            self.form_title.configure(text='Detalle del Cliente')
            labels = ['Nombre', 'Dirección', 'Teléfono', 'Correo']
        else:
            labels = ['', '', '', '']
        for lbl, text in zip(self.form_labels, labels):
            lbl.configure(text=text)

        # configure tree columns
        cols_config = {
            'Proveedores': [('id', 'ID', 60), ('nombre', 'Nombre', 180), ('direccion', 'Dirección', 220), ('telefono', 'Teléfono', 120), ('email', 'Correo', 180)],
            'Productos': [('id', 'ID', 60), ('nombre', 'Nombre', 180), ('descripcion', 'Descripción', 220), ('precio', 'Precio', 120), ('cantidad', 'Cantidad', 80)],
            'Clientes': [('id', 'ID', 60), ('nombre', 'Nombre', 180), ('direccion', 'Dirección', 220), ('telefono', 'Teléfono', 120), ('email', 'Correo', 180)],
        }
        cfg = cols_config.get(resource, [])
        # clear existing columns
        self.tree.config(columns=[c[0] for c in cfg])
        for col, text, width in cfg:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width)
        # reload data
        self.clear_form()
        self.load_data_for(resource)


if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()  # Ocultar la ventana principal inicial

    login_window = LoginWindow(root)
    root.wait_window(login_window)

    if login_window.user:
        app = ProveedoresApp()
        app.mainloop()