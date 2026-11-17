# Proyecto 5: Intérprete de comandos para un asistente

## Integrantes
- 

## Descripción
Mini terminal interactiva para administrar archivos y carpetas reales y usuarios simulados.

## Lenguaje utilizado
- Python 3

## Requisitos
Python 3. La mini terminal usa únicamente la biblioteca estándar.

## Estructura del proyecto
- `main.py`
- `src/`
- `tests/`

## Instrucciones para ejecutar
Desde la carpeta `02_Codigo` en Windows:
```bat
python main.py
```
Escribe `ayuda` para ver todos los comandos y `salir` para terminar.
Usa comillas para rutas o nombres con espacios.

```text
crear carpeta "Mis documentos"
crear archivo "Mis documentos\nota.txt"
modificar archivo "Mis documentos\nota.txt"
crear usuario Ana
modificar usuario Ana Maria
listar usuarios
borrar usuario Maria
```

Los usuarios son simulados y se guardan en `usuarios.json` junto a `main.py`; no son cuentas de Windows. Las rutas relativas parten de la carpeta desde la que se inició el programa. Las operaciones sobre archivos y carpetas afectan archivos reales: borrar pide confirmación y solo permite eliminar carpetas vacías. Modificar un archivo reemplaza todo su contenido con una línea, después de pedir confirmación.
