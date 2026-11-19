"""Mini terminal de teoría computacional.

Cubre tres capas: léxico con expresiones regulares, un AFD explícito para la
forma de los comandos simples y un autómata de pila para las jerarquías de
carpetas. Todos los efectos quedan dentro de entorno_windows/.
"""

import json
import os
import re
import shutil
from datetime import datetime

SANDBOX = "entorno_windows"
USUARIOS = os.path.join(SANDBOX, "usuarios.json")

ACCIONES = ("crear", "borrar", "buscar", "inspeccionar", "editar")
ENTIDADES = ("usuario", "archivo", "carpeta")

# Las tres expresiones regulares del analizador léxico.
REGEX_ACCION = r"^(crear|borrar|buscar|inspeccionar|editar)$"
REGEX_ENTIDAD = r"^(usuario|archivo|carpeta)$"
REGEX_PARAMETRO = r"^[a-zA-Z0-9_.-]+$"

ALFABETO = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-(), ")
CARACTERES_NOMBRE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
RESERVADAS = {"help", "--help", "salir"} | set(ACCIONES) | set(ENTIDADES)

AYUDA = {
    "crear": "crear usuario|archivo|carpeta NOMBRE  (carpeta admite Raiz(Sub1, Sub2(Sub3)))",
    "borrar": "borrar usuario|archivo|carpeta NOMBRE",
    "buscar": "buscar usuario|archivo|carpeta NOMBRE",
    "inspeccionar": "inspeccionar usuario|archivo|carpeta NOMBRE",
    "editar": "editar usuario|archivo|carpeta NOMBRE",
    "salir": "salir",
}

# AFD: un estado por prefijo válido; cualquier transición ausente cae en Dt,
# que es la trampa absorbente del autómata.
TRANSICIONES = {
    ("D0", "help"): "D1",
    ("D0", "a"): "D2",
    ("D2", "--help"): "D3",
    ("D2", "e"): "D4",
    ("D4", "p"): "D5",
}
FINALES = ("D1", "D3", "D5")


class ErrorLexico(Exception):
    """Símbolo fuera del alfabeto o separación incorrecta."""


class ErrorSintactico(Exception):
    """La forma del comando no pertenece al lenguaje del AFD o del AP."""


class ErrorSemantico(Exception):
    """El comando es válido, pero el estado del sandbox no lo permite."""


# --------------------------------------------------------------------------
# Entrada: alfabeto, separación y tokens
# --------------------------------------------------------------------------

def validar_alfabeto(linea):
    if not linea:
        raise ErrorLexico("la línea está vacía")
    if linea != linea.strip():
        raise ErrorLexico("hay espacios al inicio o al final")
    if "  " in linea:
        raise ErrorLexico("se admite un único espacio como separador")
    for caracter in linea:
        if caracter not in ALFABETO:
            raise ErrorLexico(f"el símbolo {caracter!r} no pertenece a Sigma")


def dividir(linea):
    # La forma jerárquica conserva su expresión como un solo campo.
    if "(" in linea or ")" in linea:
        partes = linea.split(" ", 2)
        if len(partes) != 3:
            raise ErrorSintactico("la forma jerárquica es: crear carpeta Raiz(Sub1, Sub2(Sub3))")
        return partes
    return linea.split(" ")


def parametro_valido(campo):
    return bool(re.match(REGEX_PARAMETRO, campo)) and campo not in RESERVADAS


def simbolo(posicion, campo, jerarquia):
    """Traduce cada token al alfabeto abstracto del AFD."""
    if posicion == 0:
        if campo == "help":
            return "help"
        return "a" if re.match(REGEX_ACCION, campo) else "INVALIDO"
    if posicion == 1:
        if campo == "--help":
            return "--help"
        return "e" if re.match(REGEX_ENTIDAD, campo) else "INVALIDO"
    if posicion == 2:
        if jerarquia:
            return "p"
        return "p" if parametro_valido(campo) else "INVALIDO"
    return "INVALIDO"


def recorrer_afd(simbolos):
    estado = "D0"
    recorrido = [estado]
    for simbolo_actual in simbolos:
        estado = TRANSICIONES.get((estado, simbolo_actual), "Dt")
        recorrido.append(estado)
    return estado, recorrido


# --------------------------------------------------------------------------
# Autómata de pila para crear carpeta Raiz(Sub1, Sub2(Sub3))
# --------------------------------------------------------------------------

def cerrar_grupo(pila, padres):
    if len(pila) == 1:
        raise ErrorSintactico(f"paréntesis de cierre sin apertura: pila {pila}")
    pila.pop()
    padres.pop()


def validar_jerarquia(expresion):
    """Recorre la expresión con el AP manual y devuelve el árbol de carpetas."""
    print(f"Expresión jerárquica: {expresion}")
    pila = ["Z0"]
    estado = "p0"
    actual = ""
    raiz = {"nombre": "", "hijos": []}
    padres = []

    for posicion, caracter in enumerate(expresion):
        anterior = estado
        if estado == "p0":
            if caracter in CARACTERES_NOMBRE:
                actual += caracter
            elif caracter == "(" and actual:
                raiz["nombre"] = actual
                actual = ""
                padres.append(raiz["hijos"])
                pila.append("X")
                estado = "p1"
            else:
                raise ErrorSintactico(f"carácter {caracter!r} inesperado en p0: falta el nombre raíz")
        elif estado == "p1":
            if caracter in CARACTERES_NOMBRE:
                actual = caracter
                estado = "p2"
            else:
                raise ErrorSintactico(f"grupo vacío: se esperaba un elemento tras '(' y llegó {caracter!r}")
        elif estado == "p2":
            if caracter in CARACTERES_NOMBRE:
                actual += caracter
            elif caracter == "(":
                nodo = {"nombre": actual, "hijos": []}
                padres[-1].append(nodo)
                actual = ""
                padres.append(nodo["hijos"])
                pila.append("X")
                estado = "p1"
            elif caracter == ",":
                padres[-1].append({"nombre": actual, "hijos": []})
                actual = ""
                estado = "p3"
            elif caracter == ")":
                padres[-1].append({"nombre": actual, "hijos": []})
                actual = ""
                cerrar_grupo(pila, padres)
                estado = "p4"
            else:
                raise ErrorSintactico(f"carácter {caracter!r} inesperado dentro de un nombre")
        elif estado == "p3":
            if caracter == " " and expresion[posicion - 1] == ",":
                pass
            elif caracter in CARACTERES_NOMBRE:
                actual = caracter
                estado = "p2"
            else:
                raise ErrorSintactico(f"elemento vacío tras la coma y llegó {caracter!r}")
        else:  # p4: se acaba de cerrar un grupo
            if caracter == ")":
                cerrar_grupo(pila, padres)
            elif caracter == ",":
                estado = "p3"
            else:
                raise ErrorSintactico(f"carácter {caracter!r} inesperado tras ')'")
        print(f"  {anterior} --{caracter!r}--> {estado} | pila {pila}")

    if estado == "p2":
        padres[-1].append({"nombre": actual, "hijos": []})
        estado = "p5"
    elif estado == "p4":
        estado = "p5"
    elif estado == "p0":
        raise ErrorSintactico("falta la lista de subcarpetas entre paréntesis")
    else:
        raise ErrorSintactico(f"expresión incompleta en el estado {estado}")
    if pila != ["Z0"]:
        raise ErrorSintactico(f"paréntesis desbalanceados: pila {pila}")
    print(f"Estado final: p5 | pila {pila}")
    print("Transición epsilon: p5 -> pf (aceptada)")
    return raiz


def comprobar_arbol(nodo, padre):
    ruta = os.path.join(padre, nodo["nombre"])
    if os.path.exists(ruta):
        raise ErrorSemantico(f"ya existe la carpeta {nodo['nombre']}")
    for hijo in nodo["hijos"]:
        comprobar_arbol(hijo, ruta)


def crear_arbol(nodo, padre):
    ruta = os.path.join(padre, nodo["nombre"])
    os.mkdir(ruta)
    for hijo in nodo["hijos"]:
        crear_arbol(hijo, ruta)


# --------------------------------------------------------------------------
# Sandbox y datos
# --------------------------------------------------------------------------

def ruta_sandbox(nombre):
    if nombre in (".", ".."):
        raise ErrorSemantico(f"componente de ruta no permitido: {nombre!r}")
    ruta = os.path.normpath(os.path.join(SANDBOX, nombre))
    if os.path.dirname(ruta) != os.path.normpath(SANDBOX):
        raise ErrorSemantico(f"la ruta {nombre!r} sale de {SANDBOX}/")
    return ruta


def cargar_usuarios():
    if not os.path.exists(USUARIOS):
        return []
    with open(USUARIOS, encoding="utf-8") as archivo:
        usuarios = json.load(archivo)
    if not isinstance(usuarios, list) or not all(isinstance(u, str) for u in usuarios):
        raise ValueError(f"{USUARIOS} no contiene una lista de nombres")
    return usuarios


def guardar_usuarios(usuarios):
    os.makedirs(SANDBOX, exist_ok=True)
    temporal = USUARIOS + ".tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(usuarios, archivo, ensure_ascii=False, indent=2)
    os.replace(temporal, USUARIOS)


def confirmar(pregunta):
    # En una tubería no hay usuario interactivo: la orden ya es explícita.
    if not os.isatty(0):
        return True
    if input(f"{pregunta} [s/N]: ").strip().lower() == "s":
        return True
    print("Operación cancelada.")
    return False


# --------------------------------------------------------------------------
# Semántica de las cinco acciones sobre las tres entidades
# --------------------------------------------------------------------------

def operar_usuario(accion, nombre):
    usuarios = cargar_usuarios()
    existe = nombre in usuarios
    if accion == "crear":
        if existe:
            raise ErrorSemantico(f"el usuario {nombre} ya existe")
        usuarios.append(nombre)
    elif accion == "borrar":
        if not existe:
            raise ErrorSemantico(f"el usuario {nombre} no existe")
        if not confirmar(f"¿Borrar el usuario {nombre}?"):
            return
        usuarios.remove(nombre)
    elif accion == "buscar":
        if not existe:
            raise ErrorSemantico(f"el usuario {nombre} no existe")
        print(f"Encontrado: usuario {nombre}")
        return
    elif accion == "inspeccionar":
        if not existe:
            raise ErrorSemantico(f"el usuario {nombre} no existe")
        print(f"Usuario: {nombre}")
        print(f"Total de usuarios registrados: {len(usuarios)}")
        print(f"Archivo: {USUARIOS}")
        return
    else:  # editar
        if not existe:
            raise ErrorSemantico(f"el usuario {nombre} no existe")
        nuevo = nombre + "_editado"
        if nuevo in usuarios:
            raise ErrorSemantico(f"el usuario {nuevo} ya existe")
        usuarios[usuarios.index(nombre)] = nuevo
        print(f"Usuario actualizado: {nombre} -> {nuevo}")
    guardar_usuarios(usuarios)
    print("Operación completada.")


def operar_archivo(accion, nombre, ruta):
    existe = os.path.isfile(ruta)
    if accion == "crear":
        if os.path.exists(ruta):
            raise ErrorSemantico(f"ya existe {nombre}")
        os.makedirs(SANDBOX, exist_ok=True)
        open(ruta, "x").close()
    elif accion == "borrar":
        if not existe:
            raise ErrorSemantico(f"no existe el archivo {nombre}")
        if not confirmar(f"¿Borrar el archivo {nombre}?"):
            return
        os.remove(ruta)
    elif accion == "buscar":
        if not existe:
            raise ErrorSemantico(f"no existe el archivo {nombre}")
        print(f"Encontrado: archivo {nombre} ({os.path.getsize(ruta)} bytes)")
        return
    elif accion == "inspeccionar":
        if not existe:
            raise ErrorSemantico(f"no existe el archivo {nombre}")
        print(f"Archivo: {nombre}")
        print(f"Ruta: {ruta}")
        print(f"Tamaño: {os.path.getsize(ruta)} bytes")
        print(f"Modificado: {datetime.fromtimestamp(os.path.getmtime(ruta)):%Y-%m-%d %H:%M:%S}")
        with open(ruta, encoding="utf-8", errors="replace") as archivo:
            contenido = archivo.read(200)
        print(f"Contenido: {contenido!r}" if contenido else "Contenido: (vacío)")
        return
    else:  # editar: agrega una línea con la marca de tiempo del cambio
        if not existe:
            raise ErrorSemantico(f"no existe el archivo {nombre}")
        with open(ruta, "a", encoding="utf-8") as archivo:
            archivo.write(f"editado {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        print(f"Archivo actualizado: {nombre}")
    print("Operación completada.")


def operar_carpeta(accion, nombre, ruta):
    existe = os.path.isdir(ruta)
    if accion == "crear":
        if os.path.exists(ruta):
            raise ErrorSemantico(f"ya existe {nombre}")
        os.makedirs(SANDBOX, exist_ok=True)
        os.mkdir(ruta)
    elif accion == "borrar":
        if not existe:
            raise ErrorSemantico(f"no existe la carpeta {nombre}")
        if not confirmar(f"¿Borrar la carpeta {nombre}?"):
            return
        shutil.rmtree(ruta)
    elif accion == "buscar":
        if not existe:
            raise ErrorSemantico(f"no existe la carpeta {nombre}")
        print(f"Encontrado: carpeta {nombre}")
        return
    elif accion == "inspeccionar":
        if not existe:
            raise ErrorSemantico(f"no existe la carpeta {nombre}")
        hijos = sorted(os.listdir(ruta))
        print(f"Carpeta: {nombre}")
        print(f"Ruta: {ruta}")
        print(f"Elementos: {len(hijos)}")
        for hijo in hijos:
            print(f"  - {hijo}")
        return
    else:  # editar: renombra con el sufijo _editada para no sobrescribir nada
        if not existe:
            raise ErrorSemantico(f"no existe la carpeta {nombre}")
        destino = nombre + "_editada"
        if os.path.exists(os.path.join(SANDBOX, destino)):
            raise ErrorSemantico(f"ya existe {destino}")
        os.rename(ruta, os.path.join(SANDBOX, destino))
        print(f"Carpeta renombrada: {nombre} -> {destino}")
    print("Operación completada.")


def ejecutar(accion, entidad, parametro, arbol=None):
    if entidad == "usuario":
        return operar_usuario(accion, parametro)
    if arbol is not None:
        os.makedirs(SANDBOX, exist_ok=True)
        comprobar_arbol(arbol, SANDBOX)
        crear_arbol(arbol, SANDBOX)
        print(f"Jerarquía creada dentro de {SANDBOX}/: {parametro}")
        print("Operación completada.")
        return
    ruta = ruta_sandbox(parametro)
    # usuarios.json es dato interno: solo lectura; cualquier acción que escriba falla cerrado
    if os.path.normpath(ruta) == os.path.normpath(USUARIOS) and accion not in ("buscar", "inspeccionar"):
        raise ErrorSemantico(f"{parametro} es un dato interno protegido")
    if entidad == "archivo":
        return operar_archivo(accion, parametro, ruta)
    return operar_carpeta(accion, parametro, ruta)


# --------------------------------------------------------------------------
# Flujo de una línea: léxico -> AFD -> AP -> semántica -> ejecución
# --------------------------------------------------------------------------

def ejecutar_linea(linea):
    """Procesa una línea. Devuelve False cuando hay que cerrar la sesión."""
    ruta_grafo = ["Q0"]
    try:
        validar_alfabeto(linea)
        tokens = dividir(linea)
        print(f"Tokens: {tokens}")
        if tokens == ["salir"]:
            print("Ruta: Q0 -> Q7")
            print("Sesión finalizada.")
            return False

        jerarquia = "(" in linea or ")" in linea
        simbolos = [simbolo(i, campo, jerarquia) for i, campo in enumerate(tokens)]
        estado, recorrido = recorrer_afd(simbolos)
        print(f"Recorrido AFD: {' -> '.join(recorrido)}")
        if estado not in FINALES:
            if estado == "Dt":
                print("Dt es la trampa absorbente: los tokens restantes se consumen sin salir de ella.")
            raise ErrorSintactico(f"la entrada queda en {estado}, que no es estado final")

        if estado == "D1":
            ruta_grafo += ["Q1", "Q7"]
            print(f"Acciones: {', '.join(ACCIONES)}")
            print("Uso: ACCION --help   |   salir")
            print(f"Ruta: {' -> '.join(ruta_grafo)}")
            return True

        if estado == "D3":
            ruta_grafo += ["Q2", "Q3", "Q7"]
            print(f"Uso: {AYUDA[tokens[0]]}")
            print(f"Ruta: {' -> '.join(ruta_grafo)}")
            return True

        accion, entidad, parametro = tokens[0], tokens[1], tokens[2]
        ruta_grafo += ["Q2", "Q3", "Q4"]
        if jerarquia:
            if accion != "crear" or entidad != "carpeta":
                raise ErrorSintactico("la forma jerárquica solo aplica a crear carpeta")
            arbol = validar_jerarquia(parametro)
        else:
            arbol = None
        ruta_grafo += ["Q5", "Q6"]
        ejecutar(accion, entidad, parametro, arbol)
        ruta_grafo.append("Q7")
        print(f"Ruta: {' -> '.join(ruta_grafo)}")
    except (ErrorLexico, ErrorSintactico) as error:
        ruta_grafo.append("QT1")
        print(f"Ruta: {' -> '.join(ruta_grafo)}")
        print(f"Error léxico/sintáctico (QT1): {error}")
    except ErrorSemantico as error:
        ruta_grafo.append("QT2")
        print(f"Ruta: {' -> '.join(ruta_grafo)}")
        print(f"Error semántico (QT2): {error}")
    except (OSError, ValueError) as error:
        ruta_grafo.append("QT2")
        print(f"Ruta: {' -> '.join(ruta_grafo)}")
        print(f"Error de datos (QT2): {error}")
    return True


def main():
    print("Mini terminal teórica. Escribe help para ver los comandos.")
    while True:
        try:
            if not ejecutar_linea(input("> ")):
                break
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break


if __name__ == "__main__":
    main()
