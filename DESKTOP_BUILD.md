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
- `staticfiles/` como activos empaquetados
- recoleccion de modulos de Django, `PyMySQL`, `waitress`, `pywebview` y la app `cafeteria`

Compila asi:

```powershell
pyinstaller --clean --noconfirm desktop.spec
```

El ejecutable quedara en `dist\CaffPOS.exe`.

## Comportamiento del ejecutable

- inicia `waitress` en `127.0.0.1` con un puerto libre
- abre la app en una ventana nativa usando `pywebview`
- usa `/health/` para comprobar que el servidor esta listo antes de abrir la ventana
- crea `db.sqlite3` en `%LOCALAPPDATA%\CaffPOS\db.sqlite3` para sesiones y metadatos internos de Django
- ejecuta `migrate` al iniciar para mantener actualizado ese esquema interno
- consulta los datos funcionales del POS en MySQL usando `PyMySQL`

Los errores de arranque quedan registrados en `%LOCALAPPDATA%\CaffPOS\logs\desktop.log`.

`_MEIPASS` se usa solo para leer archivos empaquetados temporales; la base de datos persistente nunca se guarda ahi.

## Variables de entorno MySQL

Si no defines variables, la app intentara conectarse con estos valores por defecto:

- `MYSQL_HOST=127.0.0.1`
- `MYSQL_PORT=3306`
- `MYSQL_USER=root`
- `MYSQL_PASSWORD=170424`
- `MYSQL_DATABASE=casa_tueste`

## Alternativa con Nuitka

Si quieres probar Nuitka para un ejecutable mas optimizado, la logica de `main.py` y `settings.py` ya queda lista. La ruta de build equivalente seria:

```powershell
pip install nuitka ordered-set zstandard
python -m nuitka --standalone --onefile --windows-console-mode=disable --enable-plugin=tk-inter --output-filename=CaffPOS.exe main.py
```

Con Nuitka tendras que agregar manualmente `staticfiles/` como datos incluidos si no detecta todo automaticamente.
