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

La app admite dos formas de configuracion:

- `MYSQL_PUBLIC_URL` para conexiones externas al cluster de Railway, como el `.exe` en Windows
- `MYSQL_URL` para conexiones internas dentro de Railway
- variables individuales `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`

El orden de prioridad es `MYSQL_PUBLIC_URL`, luego `MYSQL_URL` y por ultimo las variables individuales.

Tambien se carga automaticamente un archivo `.env` si existe en alguno de estos lugares:

- el directorio actual desde el que se ejecuta la app
- la raiz del proyecto durante desarrollo
- el bundle temporal extraido por PyInstaller desde `CaffPOS.exe`
- la carpeta que contiene `CaffPOS.exe`
- `%LOCALAPPDATA%\CaffPOS\.env`

La app ya no usa credenciales MySQL por defecto. Si falta la configuracion, el arranque falla con un error explicito para evitar conexiones inseguras o ambiguas.

### Empaquetar `.env` dentro del `.exe`

Si existe un `.env` en la raiz del proyecto al momento de compilar, `desktop.spec` lo incluye dentro del ejecutable y la app lo carga al arrancar.

Para este modo, basta compilar con el `.env` correcto presente en la raiz del proyecto.

Ejemplo de `%LOCALAPPDATA%\CaffPOS\.env`:

```dotenv
MYSQL_PUBLIC_URL=mysql://usuario:password@host:puerto/base
DJANGO_SECRET_KEY=un-secreto-largo-y-aleatorio
DJANGO_DEBUG=False
```

Si el `.exe` va a seguir conectando directo a MySQL, crea un usuario dedicado con privilegios minimos y rota las credenciales periodicamente. Para una arquitectura realmente segura, mueve el acceso a MySQL a un backend/API y deja que el `.exe` consuma solo ese backend.

## Alternativa con Nuitka

Si quieres probar Nuitka para un ejecutable mas optimizado, la logica de `main.py` y `settings.py` ya queda lista. La ruta de build equivalente seria:

```powershell
pip install nuitka ordered-set zstandard
python -m nuitka --standalone --onefile --windows-console-mode=disable --enable-plugin=tk-inter --output-filename=CaffPOS.exe main.py
```

Con Nuitka tendras que agregar manualmente `staticfiles/` como datos incluidos si no detecta todo automaticamente.
