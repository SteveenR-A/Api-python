import customtkinter as ctk
import requests  # Para hacer peticiones a la API
import json
import subprocess
import time
import sys
from tkinter import messagebox
from tkinter import ttk # Usaremos el Treeview de ttk para la tabla

# URL base de tu API (se intentará arrancar si no está corriendo)
API_URL = "http://127.0.0.1:5000"

def ensure_api_running():
    try:
        r = requests.get(f"{API_URL}/health", timeout=1)
        if r.status_code == 200:
            return None
    except Exception:
        # Intentar arrancar la API en background
        # lanzamos el mismo ejecutable de Python que está corriendo esta app
        # así nos aseguramos de usar el venv correcto
        p = subprocess.Popen([sys.executable, "app.py"], cwd='.', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # esperar un momento para que el servidor arranque
        for _ in range(10):
            try:
                r = requests.get(f"{API_URL}/health", timeout=1)
                if r.status_code == 200:
                    return p
            except Exception:
                time.sleep(0.5)
        return p
        try:
            response = requests.get(f"{API_URL}/proveedores")
            if response.status_code == 200:
                proveedores = response.json()
                for prov in proveedores:
                    # Asegurarse del orden id, nombre, direccion, telefono, email
                    values = (prov.get('id'), prov.get('nombre'), prov.get('direccion'), prov.get('telefono'), prov.get('email'))
                    self.tree.insert("", "end", values=values)
            else:
                # Mostrar información más detallada del error devuelto por la API
                text = response.text or ""
                messagebox.showerror("Error", f"No se pudieron cargar los proveedores. ({response.status_code}) {text}")
        except requests.exceptions.RequestException as e:
            # Cubre errores de conexión y timeouts
            messagebox.showerror("Error de Conexión", f"No se pudo conectar a la API. {e}")
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # --- Frame para la Tabla (Izquierda) ---
        table_frame = ctk.CTkFrame(main_frame)
        table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # --- Creación de la Tabla (Treeview) ---
        columns = ("id_proveedor", "nombre", "direccion", "telefono", "email")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        # Definir encabezados
        self.tree.heading("id_proveedor", text="ID")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("direccion", text="Dirección")
        self.tree.heading("telefono", text="Teléfono")
        self.tree.heading("email", text="Correo")
        
        # Ajustar ancho de columnas
        self.tree.column("id_proveedor", width=50)
        self.tree.column("nombre", width=150)

        self.tree.pack(fill="both", expand=True)
        # Evento para cuando se selecciona una fila
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        # --- Frame para el Formulario (Derecha) ---
        form_frame = ctk.CTkFrame(main_frame)
        form_frame.pack(side="right", fill="y", expand=False)

        # --- Widgets del Formulario ---
        label_form = ctk.CTkLabel(form_frame, text="Detalle del Proveedor", font=ctk.CTkFont(size=16, weight="bold"))
        label_form.pack(pady=10)

        # Nombre
        ctk.CTkLabel(form_frame, text="Nombre:").pack(anchor="w", padx=20)
        self.entry_nombre = ctk.CTkEntry(form_frame, width=200)
        self.entry_nombre.pack(pady=5, padx=20)

        # Dirección
        ctk.CTkLabel(form_frame, text="Dirección:").pack(anchor="w", padx=20)
        self.entry_direccion = ctk.CTkEntry(form_frame, width=200)
        self.entry_direccion.pack(pady=5, padx=20)

        # Teléfono
        ctk.CTkLabel(form_frame, text="Teléfono:").pack(anchor="w", padx=20)
        self.entry_telefono = ctk.CTkEntry(form_frame, width=200)
        self.entry_telefono.pack(pady=5, padx=20)

        # Correo
        ctk.CTkLabel(form_frame, text="Correo:").pack(anchor="w", padx=20)
        self.entry_correo = ctk.CTkEntry(form_frame, width=200)
        self.entry_correo.pack(pady=5, padx=20)

        # Campo oculto para el ID
        self.entry_id = ctk.CTkEntry(form_frame) # No lo mostramos con .pack()

        # --- Botones ---
        btn_nuevo = ctk.CTkButton(form_frame, text="Nuevo", command=self.limpiar_formulario)
        btn_nuevo.pack(pady=10, padx=20, fill="x")

        btn_guardar = ctk.CTkButton(form_frame, text="Guardar", command=self.guardar_proveedor)
        btn_guardar.pack(pady=10, padx=20, fill="x")

        btn_borrar = ctk.CTkButton(form_frame, text="Borrar", fg_color="red", command=self.borrar_proveedor)
        btn_borrar.pack(pady=10, padx=20, fill="x")

        btn_salir = ctk.CTkButton(form_frame, text="Salir", fg_color="gray", command=self.destroy)
        btn_salir.pack(pady=(20,10), padx=20, fill="x")
        # Asegurar que la API esté corriendo; arrancarla si es necesario
        self._api_process = ensure_api_running()

        # Cargar los datos iniciales al abrir la app
        self.cargar_proveedores()

    # --- Funciones de Lógica (Comunicación con la API) ---

    def cargar_proveedores(self):
        # Limpiar tabla antes de cargar
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        try:
            response = requests.get(f"{API_URL}/proveedores")
            if response.status_code == 200:
                proveedores = response.json()
                for prov in proveedores:
                    # Asegurarse del orden id, nombre, direccion, telefono, email
                    values = (prov.get('id'), prov.get('nombre'), prov.get('direccion'), prov.get('telefono'), prov.get('email'))
                    self.tree.insert("", "end", values=values)
            else:
                messagebox.showerror("Error", "No se pudieron cargar los proveedores.")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error de Conexión", "No se pudo conectar a la API. Asegúrate de que esté en ejecución.")

    def limpiar_formulario(self):
        self.entry_id.delete(0, "end")
        self.entry_nombre.delete(0, "end")
        self.entry_direccion.delete(0, "end")
        self.entry_telefono.delete(0, "end")
        self.entry_correo.delete(0, "end")
        self.entry_nombre.focus()

    def guardar_proveedor(self):
        datos = {
            "nombre": self.entry_nombre.get(),
            "direccion": self.entry_direccion.get(),
            "telefono": self.entry_telefono.get(),
            "email": self.entry_correo.get()
        }
        # Si hay un id (entrada oculta), entonces actualizamos
        prov_id = self.entry_id.get().strip()
        if prov_id:
            response = requests.put(f"{API_URL}/proveedores/{prov_id}", json=datos)
            if response.status_code == 200:
                messagebox.showinfo("Éxito", "Proveedor actualizado correctamente.")
                self.limpiar_formulario()
                self.cargar_proveedores()
            else:
                messagebox.showerror("Error", f"No se pudo actualizar el proveedor. {response.text}")
            return

        # Si no hay id, creamos nuevo
        response = requests.post(f"{API_URL}/proveedores", json=datos)

        if response.status_code == 201:
            messagebox.showinfo("Éxito", "Proveedor guardado correctamente.")
            self.limpiar_formulario()
            self.cargar_proveedores()
        else:
            messagebox.showerror("Error", f"No se pudo guardar el proveedor. {response.text}")
    
    def borrar_proveedor(self):
        # Borrar proveedor seleccionado
        prov_id = self.entry_id.get().strip()
        if not prov_id:
            messagebox.showwarning("Selecciona", "Selecciona un proveedor para borrar.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar el proveedor seleccionado?"):
            resp = requests.delete(f"{API_URL}/proveedores/{prov_id}")
            if resp.status_code in (200, 204):
                messagebox.showinfo("Borrado", "Proveedor eliminado.")
                self.limpiar_formulario()
                self.cargar_proveedores()
            else:
                messagebox.showerror("Error", f"No se pudo eliminar. {resp.text}")

    def on_row_select(self, event):
        # Obtiene el item seleccionado
        selected_item = self.tree.focus()
        if not selected_item:
            return
            
        # Obtiene los valores de la fila
        valores = self.tree.item(selected_item, "values")
        
        # Limpia el formulario antes de llenarlo
        self.limpiar_formulario()
        
        # Llena los campos con los datos de la fila seleccionada
        self.entry_id.insert(0, valores[0]) # id
        self.entry_nombre.insert(0, valores[1]) # nombre
        self.entry_direccion.insert(0, valores[2]) # direccion
        self.entry_telefono.insert(0, valores[3]) # telefono
        self.entry_correo.insert(0, valores[4]) # email

# --- Ejecutar la Aplicación ---
if __name__ == "__main__":
    app = ProveedoresApp()
    app.mainloop()
