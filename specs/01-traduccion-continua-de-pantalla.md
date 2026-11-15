# SPEC 01 - Traducción continua de pantalla

> **Estado:** Aprobado  
> **Dependencias:** Ninguna  
> **Fecha:** 2026-11-15  
> **Objetivo:** Traducir continuamente al español el texto en inglés visible en un monitor de Windows 11 y mostrar la traducción encima del original, con todo el procesamiento en el equipo.

## Alcance

### Incluido

- Windows 11 x64, con un monitor activo por vez. El usuario lo selecciona desde el icono de la bandeja. En el primer inicio se preselecciona el monitor principal y la app abre en pausa.
- Captura continua del monitor elegido. La misma sesión sigue el texto visible al cambiar de aplicación, abrir un menú o desplazarse por un documento. El OCR detecta texto a partir de los píxeles visibles, incluso dentro de imágenes.
- Traducción inglés → español mediante OCR e inferencia en CPU. El instalador incluye los modelos y los componentes necesarios para funcionar desde el primer inicio sin Internet.
- Superposición sobre las líneas o bloques traducidos, con fondo opaco para cubrir el original y texto de alto contraste. La ventana de superposición permite que los clics, el desplazamiento y el foco lleguen a la aplicación de abajo.
- Dos atajos globales configurables. `Ctrl+Alt+F8` inicia o pausa la sesión. `Ctrl+Alt+F9` alterna entre el original y la traducción mientras la captura sigue activa. Las dos acciones también están disponibles en la bandeja.
- Los únicos datos persistentes de la app son el monitor elegido y los atajos. Los fotogramas, el texto reconocido, las traducciones y su caché se mantienen en memoria.

### Fuera de alcance

- Otros idiomas, autodetección de idioma, traducción de voz y transcripción de audio.
- Captura simultánea de varios monitores, selección de regiones y seguimiento de una ventana específica.
- Historial, exportación, servicios de traducción en la nube, inicio automático con Windows e integración con las aplicaciones traducidas.
- Compatibilidad garantizada con video protegido, escritorios seguros, juegos a pantalla completa exclusiva y versiones de Windows anteriores a Windows 11.

## Comportamiento y estados

| Estado | Captura y procesamiento | Resultado visible |
| --- | --- | --- |
| `PAUSED` | Detenidos. Se invalidan los trabajos pendientes y se descartan los resultados que lleguen tarde. | Se ve el original. La bandeja ofrece iniciar. |
| `TRANSLATING` | Activos sobre el monitor elegido. | Se superponen las traducciones vigentes. La bandeja permite pausar y ver el original. |
| `SHOWING_ORIGINAL` | Activos sobre el mismo monitor. | Se ve el original. Al volver a traducción se muestra solo el resultado válido para el contenido actual. |
| `ERROR` | Detenidos. | Se ve el original. La bandeja muestra la causa recuperable y permite reintentar o elegir otro monitor según corresponda. |

- Iniciar desde pausa intenta abrir la captura y validar su exclusión antes de mostrar resultados. Pausar o salir oculta inmediatamente la superposición y libera la sesión de captura. Un trabajo de OCR o traducción que ya empezó puede terminar en segundo plano, pero su resultado se descarta.
- Mostrar el original no pausa la captura. El atajo de alternancia se ignora mientras la app esté en pausa o error. Una sesión nueva empieza en modo traducción.
- Cambiar de monitor durante una sesión limpia los resultados y abre una sesión para el nuevo monitor. Si el monitor activo se desconecta o deja de estar disponible, se detiene la captura y se pide seleccionar un monitor o reintentar. En un inicio nuevo, si la preferencia ya no corresponde a un monitor conectado, se preselecciona el principal y se mantiene la pausa.
- Si el contenido cambia o desaparece, se retiran los bloques afectados. Si el OCR devuelve texto insuficiente, se conserva el original. Si una traducción no entra en el espacio disponible a tamaño legible, se ajusta a varias líneas si caben. En caso contrario, queda visible el original.
- Si Windows rechaza un atajo por estar ocupado, se informa el conflicto y las acciones quedan accesibles desde la bandeja. Un cambio de atajo se persiste únicamente cuando los dos atajos son distintos y Windows confirma que se registraron. Si falla el cambio, se recupera la última configuración válida.
- Si faltan modelos o componentes, el mensaje identifica cuál falta e indica reinstalar la app. Si falla la exclusión de la superposición, se detiene la sesión para evitar que el OCR vuelva a leer el resultado traducido.

## Modelo de datos

| Estructura | Ubicación | Campos y convenciones |
| --- | --- | --- |
| `Settings` | `%LOCALAPPDATA%\TraductorPantalla\settings.json` | `monitor_device_path` admite nulo. `toggle_translation_hotkey` y `toggle_original_hotkey` contienen una combinación validada. La escritura es atómica. Ante un JSON ilegible se cargan los valores por defecto y se informa en la bandeja. |
| `CaptureFrame` | Memoria, máximo un fotograma pendiente y uno en procesamiento | `session_id`, `frame_id`, `captured_at_monotonic`, `monitor_device_path`, `width_px`, `height_px`, `pixels_bgra`. Coordenadas con origen en la esquina superior izquierda del monitor capturado. |
| `TextBlock` | Memoria, vinculado a la sesión y al fotograma | `session_id`, `frame_id`, `bounds_px`, `source_text`, `ocr_confidence`, `region_fingerprint`. `bounds_px` se expresa en píxeles físicos del monitor. |
| `OverlayBlock` | Memoria, hasta que cambia la región o termina la sesión | `session_id`, `frame_id`, `bounds_px`, `region_fingerprint`, `translated_text`. La conversión a coordenadas lógicas de Qt se hace al renderizar, con la escala del monitor activo. |
| `TranslationCache` | Memoria, caché LRU de hasta 512 textos durante la sesión activa | La clave es el texto reconocido con espacios normalizados. El valor es la traducción. Las posiciones se toman del fotograma que se va a mostrar. |

## Plan de implementación

| Paso | Archivos principales | Resultado ejecutable |
| --- | --- | --- |
| 1. Arranque y bandeja | `pyproject.toml`, `src/traductor_pantalla/__main__.py`, `src/traductor_pantalla/tray.py`, `src/traductor_pantalla/settings.py`, `src/traductor_pantalla/hotkeys.py` | El comando `python -m traductor_pantalla`, con el paquete instalado en el entorno de desarrollo, abre la bandeja en pausa, permite seleccionar el monitor y registrar los atajos. |
| 2. Captura y superposición | `src/traductor_pantalla/capture.py`, `src/traductor_pantalla/overlay.py` | Windows Graphics Capture abre el monitor seleccionado mediante `windows-capture`. Una marca de prueba comprueba que la ventana cubre la zona esperada, pasa los clics y queda excluida del fotograma. Vincular la selección de Windows con la enumeración de captura y Qt sin asumir que sus índices coinciden. |
| 3. Reconocimiento | `src/traductor_pantalla/ocr.py`, `models/models.lock.json` | RapidOCR con ONNX Runtime en CPU carga desde rutas locales el detector y el reconocedor. Una imagen de prueba devuelve líneas, coordenadas y niveles de confianza. Registrar la revisión, licencia y SHA-256 de los modelos distribuidos. |
| 4. Traducción local | `src/traductor_pantalla/translation.py`, `models/models.lock.json` | Preparar `Helsinki-NLP/opus-mt-en-es` en formato CTranslate2 INT8 durante el empaquetado. Cargar el modelo y sus tokenizadores SentencePiece desde disco. Una frase de prueba se traduce sin red y se verifica el uso de los tokenizadores de entrada y salida. |
| 5. Flujo continuo | `src/traductor_pantalla/session.py`, `capture.py`, `ocr.py`, `translation.py`, `overlay.py`, `tray.py` | Procesar en segundo plano, con un trabajo en curso y un solo fotograma pendiente que se reemplaza por el más reciente. Evitar OCR en imágenes equivalentes y aprovechar la caché de traducciones. Comparar la región del resultado con la más reciente antes de dibujar. Descartar solo los bloques que hayan cambiado o pertenezcan a una sesión anterior. |
| 6. Distribución | `packaging/traductor-pantalla.spec`, `packaging/traductor-pantalla.iss`, `packaging/THIRD-PARTY-NOTICES.txt`, `README.md` | Empaquetar con PyInstaller en modo carpeta y construir un instalador x64 con Inno Setup. Incluir Python, las dependencias nativas y sus prerrequisitos redistribuibles, los modelos y sus licencias. Crear un acceso en el menú Inicio y documentar cómo instalar, usar y desinstalar. |

La exclusión de la ventana se valida antes de integrar la traducción continua. Se aplica `WDA_EXCLUDEFROMCAPTURE` al identificador nativo de la superposición y se verifica que la marca de prueba no figure en el fotograma del monitor. Durante el uso normal, se vuelve a comprobar la configuración al recrear la ventana nativa. La captura no incluye el cursor para evitar que su movimiento invalide trabajo de OCR.

## Criterios de aceptación

- [ ] En Windows 11 x64 sin Python, el instalador se ejecuta con la red desactivada. El acceso en el menú Inicio abre la app y traduce desde el primer uso sin descargar modelos.
- [ ] Al abrir la app, la bandeja indica pausa y no hay una sesión de captura activa. `Ctrl+Alt+F8` inicia y vuelve a pausar con otra pulsación. Al pausar se ve inmediatamente el original, incluso si había una traducción en curso.
- [ ] En un equipo con dos monitores, seleccionar el secundario traduce solo en ese monitor. El resultado queda alineado a escala de Windows de 100 % y 150 %, incluida una disposición con el secundario a la izquierda del principal.
- [ ] Se traduce un menú en inglés de una aplicación de escritorio y una frase visible dentro de una imagen abierta en otra aplicación. Cambiar de aplicación y desplazar el contenido elimina los bloques que quedaron fuera de pantalla.
- [ ] `Ctrl+Alt+F9` muestra el original. Si cambia el texto mientras el original está visible, al alternar nuevamente nunca se muestra la traducción anterior en la región modificada.
- [ ] Se puede hacer clic en un botón cubierto y desplazar la aplicación con la rueda del ratón sin que la superposición tome el foco. Una marca visible en la superposición no aparece en fotogramas analizados por el OCR.
- [ ] Tras desconectar el monitor durante la captura, se oculta la superposición y la bandeja permite seleccionar otro monitor y reanudar manualmente. Con un modelo ausente se muestra el error correspondiente y el original queda visible.
- [ ] Cambiar ambos atajos y reiniciar conserva las combinaciones y el monitor elegido, y la app vuelve a abrir en pausa. Ante un atajo ocupado, se informa el conflicto y el menú de la bandeja sigue funcionando.
- [ ] Durante una sesión de prueba sin red, la app no crea archivos con capturas, texto reconocido o traducciones. Los datos de configuración contienen solo el monitor y los dos atajos.
- [ ] Con los modelos precargados, en la PC de referencia del usuario y a 1920 × 1080, diez cambios consecutivos de una vista de escritorio con entre 5 y 10 líneas legibles en inglés muestran la traducción en un máximo de 2 segundos por cambio. Medir desde que aparece el texto hasta que se dibuja el último bloque del cambio. Mantener cada vista fija durante la medición y registrar CPU, versión de Windows, escala y tiempos.
- [ ] Una secuencia de cambios sucesivos no acumula más de un fotograma pendiente. Cuando la pantalla se estabiliza, se traduce el contenido vigente.

## Decisiones

- **Python y PySide6.** Base acordada para construir la aplicación de bandeja y la superposición. Windows Graphics Capture proporciona los fotogramas del monitor.
- **RapidOCR y OPUS-MT en CPU.** El OCR da coordenadas para ubicar los bloques. El modelo de traducción se ejecuta localmente y el instalador incorpora los pesos y tokenizadores.
- **Control manual y alternancia independiente.** Pausar detiene la captura. Mostrar el original mantiene activa la sesión para que el usuario pueda volver a la traducción actual.
- **Instalador completo.** PyInstaller e Inno Setup permiten entregar un único instalador con archivos locales, adecuado para el primer uso sin conexión.
- **Valores iniciales de la especificación.** Se fijan Windows 11 x64, los atajos por defecto, el límite de 512 textos en caché y la prueba de 10 cambios a 1080p. El objetivo de 2 segundos se valida en la PC del usuario durante la implementación.

## Riesgos

| Riesgo | Tratamiento |
| --- | --- |
| La capa vuelve a aparecer en la captura. | Probar la exclusión con el backend elegido antes de integrar OCR. Si falla en ejecución, ocultar la capa y detener la sesión. |
| El escalado de Windows desplaza el resultado. | Conservar las coordenadas del OCR en píxeles del monitor hasta renderizar. Verificar escalado mixto y origen negativo. |
| Los cambios rápidos generan resultados fuera de fecha. | Mantener un único fotograma pendiente y comparar el estado de cada región antes de mostrar el resultado. |
| Los textos breves, pequeños o ambiguos producen resultados imprecisos. | Usar la confianza del OCR y conservar el original cuando no se pueda mostrar una traducción legible. El atajo permite consultar el original en cualquier momento de la sesión. |
| El empaquetado omite modelos o bibliotecas nativas. | Revisar el manifiesto y validar el instalador en una instalación limpia de Windows 11 con la red desactivada. |

## Referencias técnicas

- [Microsoft Learn: exclusión de ventanas de la captura](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity)
- [Windows Capture: API de Python](https://github.com/NiiightmareXD/windows-capture/blob/main/windows-capture-python/README.md)
- [Qt: escalado de pantalla](https://doc.qt.io/qt-6/highdpi.html)
- [RapidOCR: salida de reconocimiento y coordenadas](https://github.com/RapidAI/RapidOCRDocs/blob/main/docs/quickstart.en.md)
- [CTranslate2: conversión de OPUS-MT](https://opennmt.net/CTranslate2/guides/opus_mt.html)
- [Helsinki-NLP: modelo inglés a español](https://huggingface.co/Helsinki-NLP/opus-mt-en-es)
