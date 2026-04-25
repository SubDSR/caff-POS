# Build de escritorio

## Dependencias

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-desktop.txt
```

## Preparar estaticos

Antes de empaquetar, genera `staticfiles/` para que el ejecutable sirva CSS, JS e imagenes desde el bundle.

```powershell
python manage.py collectstatic --noinput
```

## Generar el `.exe` con PyInstaller

El archivo `desktop.spec` ya incluye:

- `main.py` como punto de entrada
- `db.sqlite3` como base inicial
- `staticfiles/` como activos empaquetados
- recoleccion de modulos de Django, `waitress`, `pywebview` y la app `cafeteria`

Compila asi:

```powershell
pyinstaller --clean --noconfirm desktop.spec
```

El ejecutable quedara en `dist\CaffPOS.exe`.

## Comportamiento del ejecutable

- inicia `waitress` en `127.0.0.1` con un puerto libre
- abre la app en una ventana nativa usando `pywebview`
- usa `/health/` para comprobar que el servidor esta listo antes de abrir la ventana
- copia `db.sqlite3` desde el bundle solo en el primer inicio
- guarda la base persistente en `%LOCALAPPDATA%\CaffPOS\db.sqlite3`
- ejecuta `migrate` al iniciar para mantener el esquema actualizado

Los errores de arranque quedan registrados en `%LOCALAPPDATA%\CaffPOS\logs\desktop.log`.

`_MEIPASS` se usa solo para leer archivos empaquetados temporales; la base de datos persistente nunca se guarda ahi.

## Alternativa con Nuitka

Si quieres probar Nuitka para un ejecutable mas optimizado, la logica de `main.py` y `settings.py` ya queda lista. La ruta de build equivalente seria:

```powershell
pip install nuitka ordered-set zstandard
python -m nuitka --standalone --onefile --windows-console-mode=disable --enable-plugin=tk-inter --output-filename=CaffPOS.exe main.py
```

Con Nuitka tendras que agregar manualmente `db.sqlite3` y `staticfiles/` como datos incluidos si no detecta todo automaticamente.
