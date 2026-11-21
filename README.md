# OLV — Open Live Video

**Tu imaginación en vida.**

OLV es una aplicación de escritorio libre para producir YouTube Shorts de forma local en Windows y Linux, con una interfaz minimalista centrada en la historia.

> El nombre que se muestra en la aplicación es **OLV**. El nombre desarrollado, **Open Live Video**, se utiliza en esta documentación y en la descripción del proyecto.

## Licencia

OLV se distribuye bajo **GNU AGPL-3.0-or-later**. Puedes usarlo, estudiarlo, modificarlo y redistribuirlo gratuitamente o cobrar por copias, siempre respetando la licencia copyleft: las versiones derivadas distribuidas deben conservar la misma licencia y ofrecer el código fuente correspondiente. Si una versión modificada se ofrece como servicio a través de una red, también debe ofrecer su código fuente a quienes interactúen con ella. La licencia no impide mantener modificaciones privadas que no se distribuyan; una licencia libre no puede prohibir ese uso privado.

Consulta el texto completo en [LICENSE](LICENSE).

## Identidad visual

- Marca: **OLV**
- Nombre completo: **Open Live Video**
- Eslogan: **Tu imaginación en vida.**
- Estilo: industrial / cinematográfico
- Paleta: fondo `#0d1117`, paneles `#121820` y `#19222b`, texto `#edf0f2`, carmesí `#790018`, acento `#d14a68`
- Logo vectorial editable: `assets/branding/olv-master.svg` (composición principal, escalable y fácil de modificar). Icono compacto: `assets/branding/olv-icon.svg`. El SVG maestro también se incluye dentro del paquete instalado. CairoSVG lo renderiza al iniciar; si el renderizador falla, la interfaz genera un emblema de emergencia con Tkinter, sin depender de recursos externos.

### Vista previa de marca

![OLV — Tu imaginación en vida](assets/branding/olv-master.svg)

## Qué hace

Escribe o pega una historia, pulsa **Crear Short** y deja que OLV busque clips, genere la narración, prepare subtítulos y monte el vídeo. La salida es un MP4 vertical 1080×1920 listo para revisar. La publicación siempre requiere aprobación manual.

## Interfaz
- Editor principal de historia con título, autoguardado y apertura/guardado.
- Ajustes esenciales de voz, música y carpeta de salida en la vista principal.
- Revisión previa al renderizado: lista de escenas, edición del texto, reproducción externa de cada clip y reordenación.
- Preparación y renderizado separados: no se genera el MP4 final hasta confirmar la revisión.
- Progreso por fases y cancelación de descargas, narración y renderizado FFmpeg.
- Menús compactos: Archivo, Ajustes y Ayuda.
- Accesos rápidos: Ctrl+N, Ctrl+O, Ctrl+S y F5.
- Barra de progreso, mensajes claros y apertura de la carpeta de resultados.

## Instalación

### Windows (recomendado)
Descarga y ejecuta `OLV-Setup-0.4.0.exe`. El asistente muestra la licencia, exige aceptarla para continuar y permite elegir la carpeta de instalación. La aplicación empaquetada incluye sus dependencias de ejecución.

### Windows (desde código fuente)
1. Instala Python 3.10+ y FFmpeg (incluyendo FFprobe) y asegúrate de que están en PATH.
2. Clona el repositorio.
3. En PowerShell:
   ```powershell
   .\scripts\setup.ps1
   .\scripts\run.ps1
   ```

### Linux (Debian/Ubuntu)
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-tk ffmpeg
git clone https://github.com/Noocoks/OpenLiveVideo.git
cd OpenLiveVideo
bash scripts/setup.sh
bash scripts/run.sh
```

## Configuración inicial (una sola vez)
1. Consigue una API key gratuita de Pixabay: https://pixabay.com/api/docs/
2. En OLV, abre **Ajustes → Clave de Pixabay…** y guárdala.
3. La clave de Pixabay se guarda en el almacén seguro de credenciales del sistema (Windows Credential Manager o Secret Service/KWallet en Linux). Si Linux no tiene un almacén de escritorio activo, define `PIXABAY_API_KEY` como variable de entorno. Las preferencias restantes se guardan localmente.
4. Opcional: elige una voz, una pista musical y una carpeta de salida.

## Crear un Short
1. Pega tu historia y, si quieres, escribe un título. Si lo dejas vacío, se propone uno automáticamente.
2. Deja una línea en blanco entre párrafos para separar escenas.
3. Pulsa **Crear Short** (o F5).
4. OLV busca vídeos en Pixabay, genera voz española con Edge TTS, añade subtítulos y monta un MP4 vertical 1080×1920 con FFmpeg.
5. Revisa el MP4 y el manifiesto `.sources.json` en la carpeta de salida. Nada se publica automáticamente.

## Automatización y límites
- En el primer inicio, OLV copia los borradores que encuentre en la antigua carpeta del repositorio (sin sobrescribir los nuevos). Los borradores se guardan automáticamente en la carpeta de datos del usuario (`%LOCALAPPDATA%/OLV/drafts` en Windows o `$XDG_DATA_HOME/olv/drafts` en Linux; por defecto `~/.local/share/olv/drafts`). Los archivos temporales y la salida predeterminada también quedan fuera de `site-packages`.
- La preparación de recursos y el montaje final son fases separadas; puedes revisar, editar y reordenar las escenas antes de renderizar.
- Los registros rotativos se guardan en la carpeta de datos del usuario, dentro de `logs/`; abre **Ayuda → Abrir registros de diagnóstico** para consultarlos.
- Edge TTS y Pixabay son servicios externos gratuitos, sujetos a disponibilidad, condiciones y límites propios. No se promete disponibilidad ilimitada.
- No se generan historias automáticamente ni vídeo generativo IA. Puedes redactar historias con ChatGPT y pegarlas aquí.
- No se usa ninguna API de pago ni se suben vídeos a YouTube.

## Crear paquetes instalables (OLV 0.4.0)

Los scripts de empaquetado copian FFmpeg y FFprobe en el directorio de distribución. Instala ambos en PATH antes de compilar. El paquete DEB declara además las bibliotecas de sistema que necesita la versión de FFmpeg empaquetada.

- Windows: ejecuta `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`. Produce `dist/OLV/` (portable). Si Inno Setup está instalado, también genera `dist/installer/OLV-Setup-0.4.0.exe`.
- Linux Debian/Ubuntu x86_64: ejecuta `bash scripts/build_linux.sh`. Produce `.deb` instalable y un archivo `.tar.gz` portable en `dist/`.

La compilación debe realizarse en el sistema operativo de destino. No es una compilación cruzada.

## Desarrollo
```bash
python -m pip install -e ".[dev]"
python -m compileall -q shortsfactory tests
python -m pytest -q
```
