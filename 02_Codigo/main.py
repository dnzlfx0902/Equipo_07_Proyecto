"""Mini terminal para archivos, carpetas y usuarios simulados."""

import json
import os
import shlex
import tempfile


USUARIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usuarios.json")

AYUDA = """Comandos (usa comillas para nombres con espacios):
  crear archivo RUTA       Crea un archivo vacío, sin sobrescribirlo
  modificar archivo RUTA   Sustituye el contenido de un archivo de texto
  borrar archivo RUTA      Elimina un archivo, previa confirmación
  crear carpeta RUTA       Crea una carpeta
  modificar carpeta RUTA NUEVA_RUTA  Renombra o mueve una carpeta
  borrar carpeta RUTA     Elimina una carpeta vacía, previa confirmación
  crear usuario NOMBRE     Crea un usuario simulado
  modificar usuario NOMBRE NUEVO_NOMBRE  Renombra un usuario simulado
  borrar usuario NOMBRE   Elimina un usuario simulado, previa confirmación
  listar usuarios          Muestra los usuarios simulados
  ayuda                    Muestra estos comandos
  salir                    Cierra la terminal
Las rutas relativas se resuelven desde la carpeta donde se ejecuta el programa.
"""


def cargar_usuarios():
    try:
        with open(USUARIOS, encoding="utf-8") as archivo:
            usuarios = json.load(archivo)
    except FileNotFoundError:
        return []
    if not isinstance(usuarios, list) or any(not isinstance(u, str) for u in usuarios):
        raise ValueError("El archivo de usuarios no contiene una lista de nombres válida")
    return usuarios


def guardar_usuarios(usuarios):
    directorio = os.path.dirname(USUARIOS)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directorio,
                                         delete=False) as archivo:
            temporal = archivo.name
            json.dump(usuarios, archivo, ensure_ascii=False, indent=2)
        os.replace(temporal, USUARIOS)
    finally:
        if temporal and os.path.exists(temporal):
            os.remove(temporal)


def confirmar(mensaje):
    return input(f"{mensaje} [s/N]: ").strip().lower() == "s"


def ejecutar(partes):
    if not partes:
        return True
    if partes == ["salir"]:
        return False
    if partes == ["ayuda"]:
        print(AYUDA)
        return True
    if partes == ["listar", "usuarios"]:
        usuarios = cargar_usuarios()
        print("\n".join(usuarios) if usuarios else "No hay usuarios.")
        return True
    if len(partes) < 3:
        raise ValueError("Comando incompleto. Escribe ayuda para ver los comandos.")

    accion, tipo, *argumentos = partes
    if tipo == "archivo" and len(argumentos) == 1:
        ruta = argumentos[0]
        if accion == "crear":
            with open(ruta, "x", encoding="utf-8"):
                pass
        elif accion == "modificar":
            if not os.path.isfile(ruta):
                raise ValueError("El archivo no existe o no es un archivo normal")
            if not confirmar("Se reemplazará todo el contenido. ¿Continuar?"):
                print("Operación cancelada.")
                return True
            contenido = input("Nuevo contenido (una línea): ")
            with open(ruta, "w", encoding="utf-8") as archivo:
                archivo.write(contenido)
        elif accion == "borrar":
            if not confirmar(f"¿Borrar el archivo {ruta}?"):
                print("Operación cancelada.")
                return True
            os.remove(ruta)
        else:
            raise ValueError("Acción desconocida. Escribe ayuda.")
    elif tipo == "carpeta":
        if accion == "crear" and len(argumentos) == 1:
            os.mkdir(argumentos[0])
        elif accion == "modificar" and len(argumentos) == 2:
            origen, destino = argumentos
            if not os.path.isdir(origen):
                raise ValueError("La carpeta de origen no existe")
            if os.path.lexists(destino):
                raise FileExistsError("El destino ya existe")
            os.rename(origen, destino)
        elif accion == "borrar" and len(argumentos) == 1:
            if not confirmar(f"¿Borrar la carpeta vacía {argumentos[0]}?"):
                print("Operación cancelada.")
                return True
            os.rmdir(argumentos[0])
        else:
            raise ValueError("Comando de carpeta incorrecto. Escribe ayuda.")
    elif tipo == "usuario":
        if accion not in ("crear", "modificar", "borrar") or len(argumentos) != (2 if accion == "modificar" else 1):
            raise ValueError("Comando de usuario incorrecto. Escribe ayuda.")
        if any(not nombre.strip() for nombre in argumentos):
            raise ValueError("El nombre de usuario no puede estar vacío")
        usuarios = cargar_usuarios()
        nombre = argumentos[0]
        if accion == "crear":
            if nombre in usuarios:
                raise ValueError("El usuario ya existe")
            usuarios.append(nombre)
        else:
            if nombre not in usuarios:
                raise ValueError("El usuario no existe")
            if accion == "modificar":
                if argumentos[1] in usuarios:
                    raise ValueError("El nuevo nombre ya existe")
                usuarios[usuarios.index(nombre)] = argumentos[1]
            else:
                if not confirmar(f"¿Borrar el usuario {nombre}?"):
                    print("Operación cancelada.")
                    return True
                usuarios.remove(nombre)
        guardar_usuarios(usuarios)
    else:
        raise ValueError("Comando desconocido. Escribe ayuda.")
    print("Operación completada.")
    return True


def main():
    print("Mini terminal. Escribe ayuda para ver los comandos.")
    while True:
        try:
            linea = input("mini> ")
            # posix=False conserva las barras inversas de las rutas de Windows.
            partes = shlex.split(linea, posix=False)
            partes = [p[1:-1] if len(p) >= 2 and p[0] in "\"'" and p[-1] == p[0] else p for p in partes]
            if not ejecutar(partes):
                break
        except (OSError, ValueError) as error:
            print(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break


if __name__ == "__main__":
    main()
