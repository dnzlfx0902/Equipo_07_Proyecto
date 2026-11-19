import json
import os
import shlex
import tempfile

# Los usuarios simulados se guardan junto a este programa.
USUARIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usuarios.json")
# Sintaxis que se muestra con help y --help.
AYUDA = {
    "crear": "crear archivo|carpeta|usuario NOMBRE",
    "modificar": "modificar archivo RUTA | modificar carpeta|usuario NOMBRE NUEVO_NOMBRE",
    "borrar": "borrar archivo|carpeta|usuario NOMBRE",
    "listar": "listar usuarios",
    "help": "help | COMANDO --help",
    "salir": "salir",
}


# Lee la lista de nombres; si aún no hay archivo, empieza vacía.
def cargar_usuarios():
    try:
        with open(USUARIOS, encoding="utf-8") as archivo:
            usuarios = json.load(archivo)
    except FileNotFoundError:
        return []
    if not isinstance(usuarios, list) or not all(isinstance(u, str) for u in usuarios):
        raise ValueError("El archivo de usuarios no contiene una lista de nombres")
    return usuarios


# Guarda primero en un temporal para no dejar el JSON a medias.
def guardar_usuarios(usuarios):
    archivo = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=os.path.dirname(USUARIOS), delete=False
    )
    try:
        with archivo:
            json.dump(usuarios, archivo, ensure_ascii=False, indent=2)
        os.replace(archivo.name, USUARIOS)
    finally:
        if os.path.exists(archivo.name):
            os.remove(archivo.name)


# Solo una «s» confirma el cambio; cualquier otra respuesta lo cancela.
def confirmar(pregunta):
    if input(f"{pregunta} [s/N]: ").lower() == "s":
        return True
    print("Operación cancelada.")
    return False


def ejecutar(partes):
    if not partes:
        return
    # Atiende la ayuda y la lista de usuarios sin modificar datos.
    if partes == ["help"]:
        print("Comandos:", ", ".join(AYUDA))
        print("Uso: COMANDO --help")
        return
    if len(partes) == 2 and partes[1] == "--help" and partes[0] in AYUDA:
        print(f"Uso: {AYUDA[partes[0]]}")
        return
    if partes == ["listar", "usuarios"]:
        usuarios = cargar_usuarios()
        print("\n".join(usuarios) if usuarios else "No hay usuarios.")
        return

    # Valida la acción, el tipo y los argumentos antes de hacer cambios.
    if len(partes) < 3:
        raise ValueError("Comando incorrecto. Escribe help.")
    accion, tipo, *datos = partes
    if accion not in ("crear", "modificar", "borrar"):
        raise ValueError("Comando desconocido. Escribe help.")
    if tipo not in ("archivo", "carpeta", "usuario"):
        raise ValueError("Tipo desconocido. Escribe help.")
    cantidad = 2 if accion == "modificar" and tipo != "archivo" else 1
    if len(datos) != cantidad:
        raise ValueError("Cantidad de argumentos incorrecta. Escribe help.")
    if any(not dato.strip() for dato in datos):
        raise ValueError("El nombre o la ruta no puede estar vacío")

    # Los cambios de usuarios solo afectan el JSON, no las cuentas del sistema.
    nombre = datos[0]
    if tipo == "usuario":
        usuarios = cargar_usuarios()
        if accion == "crear":
            if nombre in usuarios:
                raise ValueError("El usuario ya existe")
            usuarios.append(nombre)
        elif nombre not in usuarios:
            raise ValueError("El usuario no existe")
        elif accion == "modificar":
            if datos[1] in usuarios:
                raise ValueError("El nuevo nombre ya existe")
            usuarios[usuarios.index(nombre)] = datos[1]
        elif not confirmar(f"¿Borrar el usuario {nombre}?"):
            return
        else:
            usuarios.remove(nombre)
        guardar_usuarios(usuarios)
    # Los archivos y las carpetas se crean sin sobrescribir lo existente.
    elif accion == "crear":
        if tipo == "archivo":
            open(nombre, "x").close()
        else:
            os.mkdir(nombre)
    # Para borrar se pide permiso; solo se borran carpetas vacías.
    elif accion == "borrar":
        if not confirmar(f"¿Borrar {nombre}?"):
            return
        (os.remove if tipo == "archivo" else os.rmdir)(nombre)
    # Modificar un archivo reemplaza todo su contenido por una línea.
    elif tipo == "archivo":
        if not os.path.isfile(nombre):
            raise ValueError("El archivo no existe")
        if not confirmar("¿Reemplazar todo el contenido?"):
            return
        contenido = input("Nuevo contenido (una línea): ")
        with open(nombre, "w", encoding="utf-8") as archivo:
            archivo.write(contenido)
    # Modificar una carpeta cambia su nombre sin sobrescribir el destino.
    else:
        if not os.path.isdir(nombre):
            raise ValueError("La carpeta no existe")
        if os.path.lexists(datos[1]):
            raise ValueError("El destino ya existe")
        os.rename(nombre, datos[1])
    print("Operación completada.")


# Lee y ejecuta comandos hasta que el usuario salga de la terminal.
def main():
    print("Escribe help para ver los comandos.")
    while True:
        try:
            # Las comillas agrupan nombres con espacios y se conservan las barras de Windows.
            partes = [
                palabra[1:-1] if palabra[0] in "\"'" and palabra[-1] == palabra[0] else palabra
                for palabra in shlex.split(input("> "), posix=False)
            ]
            if partes == ["salir"]:
                break
            ejecutar(partes)
        # Los errores de un comando no cierran la terminal.
        except (OSError, ValueError) as error:
            print(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break


# Inicia la terminal solo si se ejecuta este archivo directamente.
if __name__ == "__main__":
    main()
