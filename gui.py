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

        table_frame = ctk.CTkFrame(main_frame)
        table_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        form_frame = ctk.CTkFrame(main_frame)
        form_frame.pack(side="right", fill="y")

        # Treeview
        columns = ("id", "nombre", "direccion", "telefono", "email")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        for col, text, width in [("id", "ID", 60), ("nombre", "Nombre", 180), ("direccion", "Dirección", 220), ("telefono", "Teléfono", 120), ("email", "Correo", 180)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        # Form
        ctk.CTkLabel(form_frame, text="Detalle del Proveedor", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(8, 12))
        ctk.CTkLabel(form_frame, text="Nombre:").pack(anchor="w", padx=8)
        self.entry_nombre = ctk.CTkEntry(form_frame, width=260)
        self.entry_nombre.pack(padx=8, pady=4)

        ctk.CTkLabel(form_frame, text="Dirección:").pack(anchor="w", padx=8)
        self.entry_direccion = ctk.CTkEntry(form_frame, width=260)
        self.entry_direccion.pack(padx=8, pady=4)

        ctk.CTkLabel(form_frame, text="Teléfono:").pack(anchor="w", padx=8)
        self.entry_telefono = ctk.CTkEntry(form_frame, width=260)
        self.entry_telefono.pack(padx=8, pady=4)

        ctk.CTkLabel(form_frame, text="Correo:").pack(anchor="w", padx=8)
        self.entry_correo = ctk.CTkEntry(form_frame, width=260)
        self.entry_correo.pack(padx=8, pady=4)

        # hidden id
        self._current_id = None

        ctk.CTkButton(form_frame, text="Nuevo", command=self.clear_form).pack(fill="x", padx=8, pady=(12, 4))
        ctk.CTkButton(form_frame, text="Guardar", command=self.save_proveedor).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(form_frame, text="Borrar", fg_color="#d9534f", command=self.delete_proveedor).pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(form_frame, text="Salir", fg_color="#6c757d", command=self.on_close).pack(fill="x", padx=8, pady=(12, 4))

        # Start API if needed
        self._api_proc = ensure_api_running()

        # Load data
        self.load_proveedores()

        # On close handler
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_proveedores(self):
        # clear
        for ch in self.tree.get_children():
            self.tree.delete(ch)
        try:
            r = requests.get(f"{API_URL}/proveedores", timeout=3)
            if r.status_code == 200:
                data = r.json()
                for p in data:
                    # normalize: if backend returns id_proveedor or id
                    pid = p.get("id") or p.get("id_proveedor")
                    self.tree.insert("", "end", values=(pid, p.get("nombre"), p.get("direccion"), p.get("telefono"), p.get("email")))
            else:
                messagebox.showerror("Error", f"API error {r.status_code}: {r.text}")
        except requests.RequestException as e:
            messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}")

    def clear_form(self):
        self._current_id = None
        self.entry_nombre.delete(0, "end")
        self.entry_direccion.delete(0, "end")
        self.entry_telefono.delete(0, "end")
        self.entry_correo.delete(0, "end")
        self.entry_nombre.focus()

    def on_row_select(self, _event=None):
        sel = self.tree.focus()
        if not sel:
            return
        vals = self.tree.item(sel, "values")
        if not vals:
            return
        self._current_id = vals[0]
        self.entry_nombre.delete(0, "end")
        self.entry_nombre.insert(0, vals[1])
        self.entry_direccion.delete(0, "end")
        self.entry_direccion.insert(0, vals[2])
        self.entry_telefono.delete(0, "end")
        self.entry_telefono.insert(0, vals[3])
        self.entry_correo.delete(0, "end")
        self.entry_correo.insert(0, vals[4])

    def save_proveedor(self):
        payload = {
            "nombre": self.entry_nombre.get(),
            "direccion": self.entry_direccion.get(),
            "telefono": self.entry_telefono.get(),
            "email": self.entry_correo.get(),
        }
        try:
            if self._current_id:
                r = requests.put(f"{API_URL}/proveedores/{self._current_id}", json=payload, timeout=4)
                if r.status_code in (200, 204):
                    messagebox.showinfo("OK", "Proveedor actualizado")
                    self.clear_form()
                    self.load_proveedores()
                else:
                    messagebox.showerror("Error", f"Actualizar: {r.status_code} {r.text}")
            else:
                r = requests.post(f"{API_URL}/proveedores", json=payload, timeout=4)
                if r.status_code == 201:
                    messagebox.showinfo("OK", "Proveedor creado")
                    self.clear_form()
                    self.load_proveedores()
                else:
                    messagebox.showerror("Error", f"Crear: {r.status_code} {r.text}")
        except requests.RequestException as e:
            messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}")

    def delete_proveedor(self):
        if not self._current_id:
            messagebox.showwarning("Selecciona", "Selecciona un proveedor")
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar proveedor?"):
            return
        try:
            r = requests.delete(f"{API_URL}/proveedores/{self._current_id}", timeout=4)
            if r.status_code in (200, 204):
                messagebox.showinfo("OK", "Eliminado")
                self.clear_form()
                self.load_proveedores()
            else:
                messagebox.showerror("Error", f"Borrar: {r.status_code} {r.text}")
        except requests.RequestException as e:
            messagebox.showerror("Conexión", f"No se pudo conectar a la API: {e}")

    def on_close(self):
        # si arrancamos la API, intentar terminarla
        try:
            if self._api_proc:
                self._api_proc.terminate()
                self._api_proc.wait(timeout=2)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = ProveedoresApp()
    app.mainloop()
