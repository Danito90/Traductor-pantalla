# Traductor de pantalla

Traduce al español el texto en inglés visible en un monitor de Windows 11 x64. La traducción aparece sobre el original. El reconocimiento y la traducción se ejecutan en CPU. La configuración guarda únicamente el monitor y los dos atajos en `%LOCALAPPDATA%\TraductorPantalla\settings.json`.

## Uso

1. Instalá `TraductorPantalla-Setup-x64.exe` y abrí **Traductor de pantalla** desde el menú Inicio.
2. Buscá el icono **ES** en la bandeja de Windows. Si hay varios monitores, elegí uno en **Monitor**.
3. Pulsá **Ctrl+Alt+F8** para iniciar. Pulsalo nuevamente para pausar.
4. Pulsá **Ctrl+Alt+F9** para alternar entre la traducción y el original mientras la sesión sigue activa.

El menú del icono también permite ejecutar esas acciones y salir. Abrí **Configuración…** desde el menú o con doble clic en **ES** para editar los atajos y activar **Iniciar con Windows**. Esta opción viene desactivada. Al activarla, el traductor se abre en pausa cada vez que iniciás sesión en tu cuenta de Windows.

Podés desinstalar la app desde **Configuración → Aplicaciones → Aplicaciones instaladas**.

## Ejecutar desde el código fuente

Usá Python 3.11–3.13 de 64 bits y PowerShell en la raíz del proyecto. La preparación inicial requiere PyPI para las dependencias, Hugging Face para los modelos y el sitio de Apache para la licencia del OCR. La atribución y el enlace a la licencia de traducción están en `packaging/THIRD-PARTY-NOTICES.txt`.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[build]'
.\.venv\Scripts\python.exe packaging/prepare_models.py
.\.venv\Scripts\python.exe -m traductor_pantalla
```

## Generar el instalador

Con el entorno anterior e Inno Setup 6.3 o posterior, ejecutá:

```powershell
.\packaging\build_installer.ps1
```

El resultado se genera en `dist/TraductorPantalla-Setup-x64.exe`. Podés indicar `-Compiler` si ISCC está en otra carpeta y `-Redistributable` para usar una copia local del redistribuible firmado por Microsoft. La compilación prepara los modelos y registra sus SHA-256. El instalador contiene los modelos y el redistribuible para una instalación sin red.

## Verificación en Windows

Las pruebas de configuración y procesamiento se ejecutan con `python -m unittest discover -s tests` desde el entorno de desarrollo.

Los [criterios de aceptación](specs/01-traduccion-continua-de-pantalla.md#criterios-de-aceptación) incluyen una instalación limpia sin red, la exclusión de la superposición de la captura y dos monitores con escala mixta. Para medir los 2 segundos, usá diez vistas nuevas de entre 5 y 10 líneas en 1080p y registrá el tiempo hasta que se dibuja el último bloque de cada vista, con los modelos ya cargados.
