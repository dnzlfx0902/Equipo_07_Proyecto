"""Mini terminal de teoría computacional.

El programa recorre tres capas de la teoría de lenguajes formales:

1. Léxico (expresiones regulares). Las tres regex de ``REGEX_*`` deciden si una
   palabra pertenece a cada categoría, y el alfabeto Sigma se valida carácter a
   carácter junto con la separación por un único espacio.
2. Sintáctico (AFD). Un autómata finito determinista explícito reconoce la
   forma de los comandos simples: los estados D0..D8 acumulan prefijos válidos
   y Dt es la trampa absorbente, de modo que una vez dentro ningún token
   posterior permite salir. Ese AFD se deriva del AFN declarado en ``AFN`` con
   la construcción por subconjuntos (``construir_afd``), y al arrancar se
   contrasta que ambos aceptan el mismo lenguaje (``verificar_automatas``).
3. Sintáctico de jerarquías (AP). Un autómata de pila manual valida la forma
   ``Raiz(Sub1, Sub2(Sub3))``: empuja ``X`` al encontrar ``(``, la extrae con
   ``)`` y solo acepta por epsilon desde p5 con la pila en ``['Z0']``.

La semántica (QT2) aplica después los efectos reales. Todos ellos quedan
confinados en ``entorno_windows/`` y los usuarios se guardan en ``usuarios.json``.
"""

import itertools
import json
import os
import re
import shutil
from datetime import datetime

SANDBOX = "entorno_windows"
USUARIOS = os.path.join(SANDBOX, "usuarios.json")

ACCIONES = ("crear", "borrar", "buscar", "inspeccionar", "editar")
ENTIDADES = ("usuario", "archivo", "carpeta")

REGEX_ACCION = r"^(crear|borrar|buscar|inspeccionar|editar)$"
REGEX_ENTIDAD = r"^(usuario|archivo|carpeta)$"
REGEX_PARAMETRO = r"^[a-zA-Z0-9_.-]+$"
# R4: validación cruzada del sub-lenguaje simple, no de la entrada.
REGEX_COMANDO_COMPLETO = (
    r"^(help|salir|(crear|borrar|buscar|inspeccionar|editar) "
    r"(--help|(usuario|archivo|carpeta) [a-zA-Z0-9_.-]+))$"
)

# Sigma se arma por partes para dejar visible qué caracteres lo componen.
LETRAS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITOS = "0123456789"
SIGNOS_NOMBRE = "_.-"
ALFABETO = set(LETRAS + DIGITOS + SIGNOS_NOMBRE + "(), ")
CARACTERES_NOMBRE = set(LETRAS + DIGITOS + SIGNOS_NOMBRE)

# Palabras que nunca pueden usarse como parámetro: quedarían fuera del AFD.
RESERVADAS = {"help", "--help", "salir"} | set(ACCIONES) | set(ENTIDADES)

AYUDA = {
    "crear": "crear usuario|archivo|carpeta NOMBRE  (carpeta admite Raiz(Sub1, Sub2(Sub3)))",
    "borrar": "borrar usuario|archivo|carpeta NOMBRE",
    "buscar": "buscar usuario|archivo|carpeta NOMBRE",
    "inspeccionar": "inspeccionar usuario  |  inspeccionar usuario|archivo|carpeta NOMBRE",
    "editar": "editar usuario|archivo|carpeta NOMBRE",
    "salir": "salir",
}

# AFD: un estado por prefijo válido; toda transición ausente cae en Dt, la trampa.
TRANSICIONES = {
    ("D0", "help"): "D1",
    ("D0", "a"): "D2",
    ("D0", "i"): "D6",
    ("D0", "s"): "D8",
    ("D2", "--help"): "D3",
    ("D2", "e"): "D4",
    ("D2", "eu"): "D4",
    ("D4", "p"): "D5",
    ("D6", "--help"): "D3",
    ("D6", "e"): "D4",
    ("D6", "eu"): "D7",
    ("D7", "p"): "D5",
}
FINALES = ("D1", "D3", "D5", "D7", "D8")

# AFN: δ(q0, a) y δ(q0, i) abren dos ramas; el AFD de arriba sale por subconjuntos.
AFN_INICIAL = "q0"
AFN_FINALES = frozenset({"q1", "q4", "q6", "q9", "q10"})
AFN = {
    ("q0", "help"): {"q1"},
    ("q0", "a"): {"q2", "q3"},
    ("q0", "i"): {"q7", "q8"},
    ("q0", "s"): {"q10"},
    ("q2", "--help"): {"q4"},
    ("q7", "--help"): {"q4"},
    ("q3", "e"): {"q5"},
    ("q3", "eu"): {"q5"},
    ("q8", "e"): {"q5"},
    ("q8", "eu"): {"q9"},
    ("q5", "p"): {"q6"},
    ("q9", "p"): {"q6"},
}
SIMBOLOS_AFD = ("help", "a", "i", "--help", "e", "eu", "p", "s")


class ErrorLexico(Exception):
    """Símbolo fuera del alfabeto o separación incorrecta."""


class ErrorSintactico(Exception):
    """La forma del comando no pertenece al lenguaje del AFD o del AP."""


class ErrorSemantico(Exception):
    """El comando es válido, pero el estado del sandbox no lo permite."""


def validar_alfabeto(linea: str) -> None:
    """Comprueba que la línea pertenezca a Sigma* con un único espacio separador.

    Args:
        linea: Texto crudo leído de la consola, sin recortar.

    Raises:
        ErrorLexico: Si la línea está vacía, tiene espacios en los extremos o
            junto más de un espacio, o contiene un símbolo ajeno a Sigma.
    """
    if not linea:
        raise ErrorLexico("la línea está vacía")
    if linea != linea.strip():
        raise ErrorLexico("hay espacios al inicio o al final")
    if "  " in linea:
        raise ErrorLexico("se admite un único espacio como separador")
    for caracter in linea:
        if caracter not in ALFABETO:
            raise ErrorLexico(f"el símbolo {caracter!r} no pertenece a Sigma")


def dividir_campos(linea: str) -> list[str]:
    """Parte la línea en tokens respetando la forma jerárquica.

    La expresión ``Raiz(Sub1, Sub2(Sub3))`` contiene espacios internos, así que
    se conserva completa como tercer campo en lugar de tokenizarla.

    Args:
        linea: Línea ya validada contra Sigma.

    Returns:
        Lista de tokens.

    Raises:
        ErrorSintactico: Si la forma jerárquica no llega a tres campos.
    """
    if "(" in linea or ")" in linea:
        partes = linea.split(" ", 2)
        if len(partes) != 3:
            raise ErrorSintactico(
                "la forma jerárquica es: crear carpeta Raiz(Sub1, Sub2(Sub3))"
            )
        return partes
    return linea.split(" ")


def parametro_valido(campo: str) -> bool:
    """Indica si un campo sirve como parámetro: cumple la regex y no es reservado."""
    return bool(re.match(REGEX_PARAMETRO, campo)) and campo not in RESERVADAS


def simbolo_afd(posicion: int, campo: str, jerarquia: bool) -> str:
    """Traduce un token a su símbolo abstracto del AFD según su posición.

    Args:
        posicion: Índice del token dentro de la línea.
        campo: Texto del token.
        jerarquia: True si la línea declara una jerarquía de carpetas.

    Returns:
        Símbolo del alfabeto abstracto del AFD; ``"INVALIDO"`` si el token no
        encaja en la posición esperada.
    """
    if posicion == 0:
        if campo == "help":
            return "help"
        if campo == "salir":
            return "s"
        if campo == "inspeccionar":
            return "i"
        return "a" if re.match(REGEX_ACCION, campo) else "INVALIDO"
    if posicion == 1:
        if campo == "--help":
            return "--help"
        if campo == "usuario":
            return "eu"
        return "e" if re.match(REGEX_ENTIDAD, campo) else "INVALIDO"
    if posicion == 2:
        if jerarquia:
            return "p"
        return "p" if parametro_valido(campo) else "INVALIDO"
    return "INVALIDO"


def recorrer_afd(simbolos: list[str]) -> tuple[str, list[str]]:
    """Recorre el AFD símbolo a símbolo y devuelve el estado final y la traza.

    Args:
        simbolos: Símbolos abstractos obtenidos de los tokens.

    Returns:
        Tupla con el estado alcanzado y la lista de estados visitados, que
        empieza en D0.
    """
    estado = "D0"
    recorrido = [estado]
    for simbolo_actual in simbolos:
        estado = TRANSICIONES.get((estado, simbolo_actual), "Dt")
        recorrido.append(estado)
    return estado, recorrido


def construir_afd() -> tuple[dict, frozenset, set]:
    """Construye el AFD por subconjuntos a partir de ``AFN``.

    El AFN no usa transiciones épsilon, así que el cierre-ε de cada subconjunto
    es el subconjunto mismo y basta con propagar los destinos símbolo a símbolo.

    Returns:
        Tupla con las transiciones ``{(subconjunto, símbolo): subconjunto}``,
        el subconjunto inicial y el conjunto de subconjuntos finales.
    """
    inicial = frozenset({AFN_INICIAL})
    transiciones = {}
    vistos = [inicial]
    pendientes = [inicial]
    while pendientes:
        subconjunto = pendientes.pop()
        for simbolo in SIMBOLOS_AFD:
            destino = frozenset(
                siguiente
                for estado in subconjunto
                for siguiente in AFN.get((estado, simbolo), ())
            )
            transiciones[(subconjunto, simbolo)] = destino
            if destino and destino not in vistos:
                vistos.append(destino)
                pendientes.append(destino)
    finales = {subconjunto for subconjunto in vistos if subconjunto & AFN_FINALES}
    return transiciones, inicial, finales


def verificar_automatas() -> None:
    """Contrasta AFN, AFD construido y R4, y comprueba la alcanzabilidad.

    Se ejecuta al arrancar: si el AFD explícito, el AFD construido por
    subconjuntos y la regex R4 dejan de aceptar el mismo lenguaje, el programa
    no atiende comandos.

    Raises:
        AssertionError: Si AFN y AFD discrepan en alguna cadena, si R4 no
            coincide con el AFD en el sub-lenguaje simple o si algún estado
            declarado del AFD es inalcanzable desde D0.
    """
    construidas, inicial, finales_construidos = construir_afd()
    palabras = ("help", "salir", "crear", "inspeccionar", "usuario", "archivo",
                "carpeta", "x1", "--help")
    for largo in range(4):
        for combinacion in itertools.product(palabras, repeat=largo):
            simbolos = [simbolo_afd(i, campo, False) for i, campo in enumerate(combinacion)]
            estado, _ = recorrer_afd(simbolos)
            subconjunto = inicial
            for simbolo in simbolos:
                subconjunto = construidas.get((subconjunto, simbolo), frozenset())
            assert (subconjunto in finales_construidos) == (estado in FINALES), combinacion
    # R4 se contrasta con el AFD solo en el sub-lenguaje simple, sin paréntesis.
    for linea in (
        "help", "salir", "crear --help", "inspeccionar --help",
        "crear usuario juan_perez", "buscar archivo reporte-2026.pdf",
        "editar carpeta fotos", "inspeccionar archivo tarea1.txt",
        "help crear", "crear usuario", "usuario crear pedro",
        "crear --help usuario", "editar archivo mi archivo.txt",
    ):
        simbolos = [simbolo_afd(i, campo, False) for i, campo in enumerate(linea.split(" "))]
        estado, _ = recorrer_afd(simbolos)
        assert bool(re.match(REGEX_COMANDO_COMPLETO, linea)) == (estado in FINALES), linea
    alcanzables, pendientes = {"D0"}, ["D0"]
    while pendientes:
        actual = pendientes.pop()
        for (origen, _simbolo), destino in TRANSICIONES.items():
            if origen == actual and destino not in alcanzables:
                alcanzables.add(destino)
                pendientes.append(destino)
    declarados = {"Dt"} | set(FINALES) | set(TRANSICIONES.values())
    declarados |= {origen for origen, _simbolo in TRANSICIONES}
    if any((estado, simbolo) not in TRANSICIONES
           for estado in alcanzables for simbolo in SIMBOLOS_AFD):
        alcanzables.add("Dt")
    assert alcanzables == declarados, declarados - alcanzables


def cerrar_grupo_ap(pila: list[str], padres: list[list]) -> None:
    """Aplica la transición de cierre ``)`` del AP.

    Args:
        pila: Pila del autómata, con ``Z0`` en el fondo y una ``X`` por grupo.
        padres: Pila auxiliar de listas de hijos donde se acumula el árbol.

    Raises:
        ErrorSintactico: Si se cierra un grupo que nunca se abrió, es decir, si
            la pila solo conserva el marcador de fondo.
    """
    if len(pila) == 1:
        raise ErrorSintactico(f"paréntesis de cierre sin apertura: pila {pila}")
    pila.pop()
    padres.pop()


def validar_jerarquia_ap(expresion: str) -> dict:
    """Valida la expresión de carpetas con el AP manual y arma el árbol.

    Estados: p0 nombre de la raíz, p1 primer elemento de un grupo, p2 dentro de
    un nombre, p3 justo después de una coma, p4 justo después de un cierre y p5
    expresión completa. La aceptación es por epsilon desde p5 con ``['Z0']``.

    Args:
        expresion: Texto ``Raiz(Sub1, Sub2(Sub3))`` sin espacios externos.

    Returns:
        Nodo raíz ``{"nombre": str, "hijos": list}`` con toda la jerarquía.

    Raises:
        ErrorSintactico: Ante un carácter inesperado, un grupo vacío, una
            expresión incompleta o paréntesis desbalanceados.
    """
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
                raise ErrorSintactico(
                    f"carácter {caracter!r} inesperado en p0: falta el nombre raíz"
                )
        elif estado == "p1":
            if caracter in CARACTERES_NOMBRE:
                actual = caracter
                estado = "p2"
            else:
                raise ErrorSintactico(
                    f"grupo vacío: se esperaba un elemento tras '(' y llegó {caracter!r}"
                )
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
                cerrar_grupo_ap(pila, padres)
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
        else:
            if caracter == ")":
                cerrar_grupo_ap(pila, padres)
            elif caracter == ",":
                estado = "p3"
            else:
                raise ErrorSintactico(f"carácter {caracter!r} inesperado tras ')'")
        print(f"  {anterior} --{caracter!r}--> {estado} | pila {pila}")

    # p2 cierra el último nombre y p4 ya venía de un cierre; el resto queda incompleto.
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


def comprobar_arbol_disponible(nodo: dict, padre: str) -> None:
    """Verifica que ninguna carpeta del árbol exista ya en disco.

    Se recorre el árbol completo antes de crear nada, de modo que un choque a
    mitad de la jerarquía no deje carpetas a medias.

    Args:
        nodo: Nodo actual del árbol.
        padre: Ruta de la carpeta que lo contendrá.

    Raises:
        ErrorSemantico: Si la carpeta del nodo ya existe.
    """
    ruta = os.path.join(padre, nodo["nombre"])
    if os.path.exists(ruta):
        raise ErrorSemantico(f"ya existe la carpeta {nodo['nombre']}")
    for hijo in nodo["hijos"]:
        comprobar_arbol_disponible(hijo, ruta)


def crear_arbol_en_disco(nodo: dict, padre: str) -> None:
    """Crea en disco el nodo y, recursivamente, toda su descendencia.

    Args:
        nodo: Nodo actual del árbol ya validado.
        padre: Ruta de la carpeta que lo contendrá.
    """
    ruta = os.path.join(padre, nodo["nombre"])
    os.mkdir(ruta)
    for hijo in nodo["hijos"]:
        crear_arbol_en_disco(hijo, ruta)


def ruta_sandbox(nombre: str) -> str:
    """Resuelve un nombre dentro del sandbox y bloquea escapes y datos internos.

    Args:
        nombre: Parámetro del comando, ya validado por el AFD.

    Returns:
        Ruta normalizada dentro de ``entorno_windows/``.

    Raises:
        ErrorSemantico: Si el nombre es ``.`` o ``..``, o si la ruta resuelta
            termina fuera del sandbox.
    """
    if nombre in (".", ".."):
        raise ErrorSemantico(f"componente de ruta no permitido: {nombre!r}")
    ruta = os.path.normpath(os.path.join(SANDBOX, nombre))
    if os.path.dirname(ruta) != os.path.normpath(SANDBOX):
        raise ErrorSemantico(f"la ruta {nombre!r} sale de {SANDBOX}/")
    return ruta


def cargar_usuarios() -> list[str]:
    """Lee la lista de usuarios registrados.

    Returns:
        Lista de nombres; vacía si el archivo aún no existe.

    Raises:
        ValueError: Si el archivo no contiene una lista de cadenas.
    """
    if not os.path.exists(USUARIOS):
        return []
    with open(USUARIOS, encoding="utf-8") as archivo:
        usuarios = json.load(archivo)
    if not isinstance(usuarios, list) or not all(isinstance(u, str) for u in usuarios):
        raise ValueError(f"{USUARIOS} no contiene una lista de nombres")
    return usuarios


def guardar_usuarios(usuarios: list[str]) -> None:
    """Persiste la lista de usuarios mediante escritura atómica.

    Se escribe un archivo temporal y se reemplaza al final para que una
    interrupción no deje el store truncado.

    Args:
        usuarios: Lista completa de nombres a guardar.
    """
    os.makedirs(SANDBOX, exist_ok=True)
    temporal = USUARIOS + ".tmp"
    with open(temporal, "w", encoding="utf-8") as archivo:
        json.dump(usuarios, archivo, ensure_ascii=False, indent=2)
    os.replace(temporal, USUARIOS)


def confirmar_accion(pregunta: str) -> bool:
    """Pide confirmación en consola antes de una operación destructiva.

    Args:
        pregunta: Texto que se muestra al usuario.

    Returns:
        True si la operación debe continuar; False si se canceló.
    """
    # En una tubería no hay usuario interactivo: la orden ya es explícita.
    if not os.isatty(0):
        return True
    if input(f"{pregunta} [s/N]: ").strip().lower() == "s":
        return True
    print("Operación cancelada.")
    return False


def operar_usuario(accion: str, nombre: str) -> None:
    """Aplica una de las cinco acciones sobre el registro de usuarios.

    Args:
        accion: Acción semántica ya validada.
        nombre: Nombre del usuario destino.

    Raises:
        ErrorSemantico: Si el usuario ya existe y se intenta crear, si no
            existe en cualquier otra acción, o si el renombrado choca con otro.
    """
    usuarios = cargar_usuarios()
    existe = nombre in usuarios
    if accion == "crear":
        if existe:
            raise ErrorSemantico(f"el usuario {nombre} ya existe")
        usuarios.append(nombre)
    elif accion == "borrar":
        if not existe:
            raise ErrorSemantico(f"el usuario {nombre} no existe")
        if not confirmar_accion(f"¿Borrar el usuario {nombre}?"):
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
    else:  # editar: renombra con el sufijo _editado
        if not existe:
            raise ErrorSemantico(f"el usuario {nombre} no existe")
        nuevo = nombre + "_editado"
        if nuevo in usuarios:
            raise ErrorSemantico(f"el usuario {nuevo} ya existe")
        usuarios[usuarios.index(nombre)] = nuevo
        print(f"Usuario actualizado: {nombre} -> {nuevo}")
    guardar_usuarios(usuarios)
    print("Operación completada.")


def listar_usuarios() -> None:
    """Muestra los usuarios registrados sin pedir nombre (forma corta).

    Raises:
        ValueError: Si el store no contiene una lista de nombres.
        OSError: Si el store no se puede leer.
    """
    usuarios = cargar_usuarios()
    print(f"Usuarios registrados: {len(usuarios)}")
    for usuario in usuarios:
        print(f"  - {usuario}")
    if not usuarios:
        print("  (no hay usuarios registrados)")


def operar_archivo(accion: str, nombre: str, ruta: str) -> None:
    """Aplica una de las cinco acciones sobre un archivo del sandbox.

    Args:
        accion: Acción semántica ya validada.
        nombre: Nombre con el que se reporta al usuario.
        ruta: Ruta resuelta y confinada al sandbox.

    Raises:
        ErrorSemantico: Si el archivo ya existe al crear o falta en el resto.
    """
    existe = os.path.isfile(ruta)
    if accion == "crear":
        if os.path.exists(ruta):
            raise ErrorSemantico(f"ya existe {nombre}")
        os.makedirs(SANDBOX, exist_ok=True)
        open(ruta, "x").close()
    elif accion == "borrar":
        if not existe:
            raise ErrorSemantico(f"no existe el archivo {nombre}")
        if not confirmar_accion(f"¿Borrar el archivo {nombre}?"):
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
        try:
            with open(ruta, encoding="utf-8", errors="replace") as archivo:
                contenido = archivo.read()
        except OSError as error:
            raise ErrorSemantico(f"no se pudo leer {nombre}: {error}") from error
        print(f"Contenido: {contenido!r}" if contenido else "Contenido: (vacío)")
        return
    else:
        if not existe:
            raise ErrorSemantico(f"no existe el archivo {nombre}")
        with open(ruta, "a", encoding="utf-8") as archivo:
            archivo.write(f"editado {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        print(f"Archivo actualizado: {nombre}")
    print("Operación completada.")


def operar_carpeta(accion: str, nombre: str, ruta: str) -> None:
    """Aplica una de las cinco acciones sobre una carpeta del sandbox.

    Args:
        accion: Acción semántica ya validada.
        nombre: Nombre con el que se reporta al usuario.
        ruta: Ruta resuelta y confinada al sandbox.

    Raises:
        ErrorSemantico: Si la carpeta ya existe al crear, falta en el resto o
            el nombre renombrado ya está ocupado.
    """
    existe = os.path.isdir(ruta)
    if accion == "crear":
        if os.path.exists(ruta):
            raise ErrorSemantico(f"ya existe {nombre}")
        os.makedirs(SANDBOX, exist_ok=True)
        os.mkdir(ruta)
    elif accion == "borrar":
        if not existe:
            raise ErrorSemantico(f"no existe la carpeta {nombre}")
        if not confirmar_accion(f"¿Borrar la carpeta {nombre}?"):
            return
        shutil.rmtree(ruta)
    elif accion == "buscar":
        if not existe:
            raise ErrorSemantico(f"no existe la carpeta {nombre}")
        print(f"Encontrado: carpeta {nombre}")
        return
    elif accion == "inspeccionar":
        if not existe:
            if os.path.exists(ruta):
                raise ErrorSemantico(f"{nombre} existe pero no es una carpeta")
            raise ErrorSemantico(f"no existe la carpeta {nombre}")
        hijos = sorted(os.listdir(ruta))
        print(f"Carpeta: {nombre}")
        print(f"Ruta: {ruta}")
        print(f"Elementos: {len(hijos)}")
        for hijo in hijos:
            print(f"  - {hijo}")
        if not hijos:
            print("  (carpeta vacía)")
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


def aplicar_accion(accion: str, entidad: str, parametro: str, arbol: dict | None = None) -> None:
    """Despacha la acción ya validada hacia los efectos concretos.

    Args:
        accion: Acción semántica.
        entidad: Entidad destino.
        parametro: Nombre o expresión jerárquica.
        arbol: Árbol de carpetas del AP cuando la línea lo declaró.

    Raises:
        ErrorSemantico: Si la ruta escapa del sandbox, si toca datos internos o
            si el estado del sandbox no admite la operación.
    """
    if entidad == "usuario":
        return operar_usuario(accion, parametro)
    if arbol is not None:
        os.makedirs(SANDBOX, exist_ok=True)
        comprobar_arbol_disponible(arbol, SANDBOX)
        crear_arbol_en_disco(arbol, SANDBOX)
        print(f"Jerarquía creada dentro de {SANDBOX}/: {parametro}")
        print("Operación completada.")
        return
    ruta = ruta_sandbox(parametro)
    # usuarios.json es dato interno: solo lectura, escribir falla cerrado.
    es_dato_interno = os.path.normpath(ruta) == os.path.normpath(USUARIOS)
    if es_dato_interno and accion not in ("buscar", "inspeccionar"):
        raise ErrorSemantico(f"{parametro} es un dato interno protegido")
    if entidad == "archivo":
        return operar_archivo(accion, parametro, ruta)
    return operar_carpeta(accion, parametro, ruta)


def procesar_linea(linea: str) -> bool:
    """Procesa una línea completa y reporta su ruta por el grafo de estados.

    Las excepciones no se propagan: cada familia de error se traduce a la ruta
    QT1 (léxico/sintáctico) o QT2 (semántica/datos).

    Args:
        linea: Línea leída de la consola.

    Returns:
        False cuando la línea pide cerrar la sesión; True en cualquier otro caso.
    """
    try:
        validar_alfabeto(linea)
        tokens = dividir_campos(linea)
        print(f"Tokens: {tokens}")

        jerarquia = "(" in linea or ")" in linea
        simbolos = [simbolo_afd(i, campo, jerarquia) for i, campo in enumerate(tokens)]
        estado, _ = recorrer_afd(simbolos)
        if estado not in FINALES:
            if estado == "Dt":
                print("Dt es la trampa absorbente: los tokens restantes se consumen sin salir de ella.")
            raise ErrorSintactico(f"la entrada queda en {estado}, que no es estado final")

        if estado == "D8":
            print("Sesión finalizada.")
            return False

        if estado == "D1":
            print(f"Acciones: {', '.join(ACCIONES)}")
            print("Uso: ACCION --help   |   salir")
            return True

        if estado == "D3":
            print(f"Uso: {AYUDA[tokens[0]]}")
            return True

        if estado == "D7":
            listar_usuarios()
            return True

        accion, entidad, parametro = tokens[0], tokens[1], tokens[2]
        if jerarquia:
            if accion != "crear" or entidad != "carpeta":
                raise ErrorSintactico("la forma jerárquica solo aplica a crear carpeta")
            arbol = validar_jerarquia_ap(parametro)
        else:
            arbol = None
        aplicar_accion(accion, entidad, parametro, arbol)
    except (ErrorLexico, ErrorSintactico) as error:
        print(f"Error léxico/sintáctico (QT1): {error}")
    except ErrorSemantico as error:
        print(f"Error semántico (QT2): {error}")
    except (OSError, ValueError) as error:
        print(f"Error de datos (QT2): {error}")
    return True


def main() -> None:
    """Bucle de lectura y evaluación hasta ``salir``, EOF o interrupción."""
    verificar_automatas()
    print("Bienvenido a la terminal, escribe help para ver comandos")
    while True:
        try:
            if not procesar_linea(input("> ")):
                break
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break


if __name__ == "__main__":
    main()
