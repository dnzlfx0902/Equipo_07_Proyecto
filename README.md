# Proyecto 5: Intérprete de comandos para un asistente

Mini terminal interactiva para administrar archivos y carpetas reales y usuarios simulados.

## Uso
Desde la raíz del repositorio, ejecuta con Python 3. No hay dependencias externas.
```bat
cd 02_Codigo
python main.py
```
Escribe `help` para ver los comandos, `crear --help` (o `modificar --help`, `borrar --help`, `listar --help`) para consultar su uso y `salir` para terminar.
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
