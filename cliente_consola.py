import base64
import json
import urllib.error
import urllib.request

API_URL = "http://localhost:5000"


def pedir_json(method, path, payload=None, username=None, password=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{API_URL}{path}", data=data, method=method)
    request.add_header("Content-Type", "application/json")

    if username and password:
        auth = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {auth}")

    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read().decode("utf-8")
            if response_body:
                try:
                    return response.status, json.loads(response_body)
                except json.JSONDecodeError:
                    return response.status, response_body
            return response.status, {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(error_body)
        except json.JSONDecodeError:
            return exc.code, {"error": error_body}


def registrar_usuario():
    usuario = input("Nombre de usuario: ").strip()
    contraseña = input("Contraseña: ").strip()
    status, response = pedir_json("POST", "/registro", {"usuario": usuario, "contraseña": contraseña})
    print("Respuesta:", response)
    if status == 201:
        print("Usuario registrado correctamente.")


def iniciar_sesion():
    usuario = input("Usuario: ").strip()
    contraseña = input("Contraseña: ").strip()
    status, response = pedir_json("POST", "/login", {"usuario": usuario, "contraseña": contraseña})
    print("Respuesta:", response)
    if status == 200:
        return usuario, contraseña
    return None, None


def listar_tareas(username, password):
    status, response = pedir_json("GET", "/tareas", username=username, password=password)
    print("Respuesta:")
    if isinstance(response, str):
        print(response)
    else:
        print(response)


def crear_tarea(username, password):
    titulo = input("Título de la tarea: ").strip()
    descripcion = input("Descripción (opcional): ").strip()
    status, response = pedir_json(
        "POST",
        "/tareas",
        {"titulo": titulo, "descripcion": descripcion},
        username=username,
        password=password,
    )
    print("Respuesta:", response)


def menu():
    print("=== Sistema de Gestión de Tareas ===")
    print("1. Registrar usuario")
    print("2. Iniciar sesión")
    print("3. Salir")

    opcion = input("Elegí una opción: ").strip()
    if opcion == "1":
        registrar_usuario()
    elif opcion == "2":
        username, password = iniciar_sesion()
        if username and password:
            while True:
                print("\n=== Menú de tareas ===")
                print("1. Ver tareas")
                print("2. Crear tarea")
                print("3. Cerrar sesión")
                subopcion = input("Elegí una opción: ").strip()

                if subopcion == "1":
                    listar_tareas(username, password)
                elif subopcion == "2":
                    crear_tarea(username, password)
                elif subopcion == "3":
                    break
                else:
                    print("Opción inválida.")
    elif opcion == "3":
        print("Hasta luego.")
        return False
    else:
        print("Opción inválida.")
    return True


if __name__ == "__main__":
    while True:
        if not menu():
            break
