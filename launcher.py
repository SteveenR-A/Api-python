import threading
import time
import os
import sys

# Iniciar la API en un hilo y luego arrancar la GUI
def start_api_in_thread(host='127.0.0.1', port=5000):
    try:
        from app_compacto import create_app
    except Exception as e:
        print(f"No se pudo importar app_compacto: {e}")
        return None

    app = create_app()

    def run_app():
        # Evitar debug=True en build distribuido
        app.run(host=host, port=port, debug=False)

    t = threading.Thread(target=run_app, daemon=True)
    t.start()
    # Dar un breve tiempo para que el server arranque
    time.sleep(0.5)
    return t


def start_gui():
    # Importar gui y reproducir su flujo de inicio (login -> MainApp)
    try:
        import gui
        import customtkinter as ctk
    except Exception as e:
        print(f"No se pudo importar gui o customtkinter: {e}")
        raise

    # Crear root y mostrar login (copiado del bloque __main__ de gui.py)
    root = ctk.CTk()
    root.withdraw()

    login_window = gui.LoginWindow(root)

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
        app = gui.MainApp(user_role=login_window.user.get('rol', 'vendedor'))
        app.mainloop()
    else:
        root.destroy()


def main():
    # Permitir anular puerto/host con variables de entorno
    host = os.getenv('API_HOST', '127.0.0.1')
    port = int(os.getenv('API_PORT', '5000'))

    print(f"Iniciando API en background en {host}:{port}...")
    start_api_in_thread(host=host, port=port)
    print("Lanzando GUI...")
    start_gui()


if __name__ == '__main__':
    main()
