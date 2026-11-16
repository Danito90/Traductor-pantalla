# Traductor de pantalla

Traduce al español el texto en inglés visible en un monitor de Windows 11 x64. La traducción aparece sobre el original. El reconocimiento y la traducción se ejecutan en CPU. La configuración guarda únicamente el monitor y los dos atajos en `%LOCALAPPDATA%\TraductorPantalla\settings.json`.

## Descargar e instalar

Abrí [GitHub Releases](https://github.com/Danito90/Traductor-pantalla/releases/latest) y descargá `TraductorPantalla-Setup-vX.Y.Z-x64.exe` desde **Assets**. Ejecutalo y seguí el asistente de instalación. Después podés abrir la app desde el menú Inicio.

## Ejecutar desde el código fuente

Abrí PowerShell en la raíz del proyecto. Usá Python 3.11–3.13 de 64 bits. Los comandos usan la versión 3.13, la misma con la que se compiló el ejecutable. Si tenés 3.11 o 3.12, cambiá `-3.13` por la versión instalada.

La primera vez, creá el entorno virtual, instalá la aplicación en modo editable y prepará los modelos. Esta preparación requiere acceso a PyPI, Hugging Face y al sitio de Apache.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe .\packaging\prepare_models.py
```

Una vez que aparezca `Modelos locales verificados.`, iniciá la app con este comando. Usalo también para los siguientes arranques. La ruta explícita al Python de `.venv` evita tener que activar el entorno.

```powershell
.\.venv\Scripts\python.exe -m traductor_pantalla
```

### Usar la aplicación

1. La app arranca en pausa. Buscá **ES** en la bandeja de Windows o entre los iconos ocultos junto al reloj.
2. Si tenés varias pantallas, elegí la que querés traducir desde **ES → Monitor**.
3. Pulsá **Ctrl+Alt+F8** para iniciar o pausar. El menú también ofrece **Iniciar traducción**.
4. Pulsá **Ctrl+Alt+F9** para mostrar el original y volver a la traducción mientras la sesión sigue activa.

Con doble clic en **ES**, o desde **Configuración…** en el menú, podés editar los atajos y activar **Iniciar con Windows**. Cuando esa opción está activa, el traductor se abre en pausa al iniciar sesión.

### iRacing y otros juegos

Usá el modo ventana sin bordes para que Windows pueda mostrar la traducción sobre el simulador. En iRacing, elegí el modo ventana en **Settings → Display** y desactivá **Border**. Elegí en **ES → Monitor** la pantalla donde se ve el menú que querés traducir. [Guía de iRacing](https://support.iracing.com/support/solutions/articles/31000171395-setting-up-three-monitors)

## Compilar una nueva versión del `.exe` con PyInstaller

Usá el entorno del paso anterior. Cerrá el traductor desde **ES → Salir** si estás ejecutando una versión dentro de `dist\release`, para que Windows libere los archivos que PyInstaller va a reemplazar.

La primera vez que compiles, instalá las dependencias de compilación en el mismo entorno:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[build]'
```

Para cada compilación, prepará los modelos y las licencias y ejecutá el [archivo `.spec`](packaging/traductor-pantalla.spec) desde la raíz del proyecto. La preparación reutiliza los modelos descargados que pasan la verificación.

```powershell
.\.venv\Scripts\python.exe .\packaging\prepare_models.py
.\.venv\Scripts\python.exe .\packaging\prepare_licenses.py
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean `
    --workpath .\build\release --distpath .\dist\release `
    .\packaging\traductor-pantalla.spec
```

El `.spec` incluye los modelos, las licencias y las dependencias nativas. También acota la búsqueda de DLL durante la compilación para evitar conflictos con otros entornos del sistema.

El resultado queda en **`dist\release\TraductorPantalla\TraductorPantalla.exe`**. Abrilo desde esa carpeta con **`_internal`** a su lado. Para distribuir la versión portable, copiá o comprimí la carpeta `TraductorPantalla` completa. En la PC de destino podés usarla sin instalar Python.

Si ya tenías un ZIP de una versión anterior, generá uno nuevo después de verificar el ejecutable:

```powershell
Compress-Archive -LiteralPath .\dist\release\TraductorPantalla `
    -DestinationPath .\dist\release\TraductorPantalla-Windows-x64.zip -Force
```

### Verificar el ejecutable compilado

Este comando prueba el OCR y la traducción con los modelos incluidos en el ejecutable. El código de salida `0` indica que la prueba pasó.

```powershell
$prueba = Start-Process -FilePath .\dist\release\TraductorPantalla\TraductorPantalla.exe `
    -ArgumentList '--verificar' -Wait -PassThru
$prueba.ExitCode
```

## Publicar un instalador creado con InstallForge

1. Creá el instalador en InstallForge a partir de la carpeta `dist\release\TraductorPantalla` completa, incluida `_internal`.
2. Guardalo en `releases/` con el nombre `TraductorPantalla-Setup-vX.Y.Z-x64.exe`. Por ejemplo, `releases/TraductorPantalla-Setup-v0.1.0-x64.exe`.
3. Enviá el archivo a `main` con Git. Ejecutá `git lfs install` una vez antes de agregarlo. `.gitattributes` configura Git LFS para estos archivos, que pueden superar el límite de 100 MiB de GitHub. En el primer envío, incluí también el workflow y `.gitattributes` en el commit.

```powershell
git lfs install
git add releases/TraductorPantalla-Setup-v0.1.0-x64.exe
git commit -m "Publicar instalador v0.1.0"
git push origin main
```

[GitHub Actions](https://github.com/Danito90/Traductor-pantalla/actions) toma la versión del nombre del archivo, crea la release si hace falta y adjunta el instalador en **Assets**. Para distribuir un instalador distinto, usá una versión nueva en el nombre.

## Verificación en Windows

Las pruebas de configuración y procesamiento se ejecutan con `python -m unittest discover -s tests` desde el entorno de desarrollo.

Los [criterios de aceptación](specs/01-traduccion-continua-de-pantalla.md#criterios-de-aceptación) incluyen una instalación limpia sin red, la exclusión de la superposición de la captura y dos monitores con escala mixta. Para medir los 2 segundos, usá diez vistas nuevas de entre 5 y 10 líneas en 1080p y registrá el tiempo hasta que se dibuja el último bloque de cada vista, con los modelos ya cargados.
