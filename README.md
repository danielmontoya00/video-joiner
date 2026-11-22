# Estudio de grabación del Equipo 10

[Estudio público](https://danielmontoya00.github.io/video-joiner/). La presentación *Llegadas sin fricción* incluye dos demos y ocho diapositivas. El guion editable se cotejó con las notas de la versión 2 al preparar los recursos.

Cada integrante abre su enlace individual, activa cámara y micrófono, ensaya y graba una sola toma. El teleprompter y el video siguen la misma línea de tiempo. El navegador guarda el borrador en ese dispositivo. También admite un MP4, MOV o WebM con cámara y audio, hasta 22 MiB y con un margen de tres segundos alrededor de la duración indicada. Si una llamada o el bloqueo del dispositivo interrumpen la grabación, la toma en curso se descarta. El borrador anterior sigue disponible.

| Presentador | Intervalo | Duración |
|---|---|---|
| Daniel Montoya | 0:00–1:12 | 72 s |
| Josué Águila Ramos | 1:12–2:16 | 64 s |
| Edmundo Carmona | 2:16–3:41 | 85 s |

## Entrega y montaje

La web es pública. El enlace individual lleva en el fragmento las claves de su integrante y de lectura del resultado. Compártelo en privado. Al entregar, el navegador cifra la toma con AES-256-GCM y prepara un ZIP. Desde «Abrir entrega» el participante adjunta el ZIP al cuerpo del issue y confirma en GitHub. Funciona con una cuenta de GitHub sin permisos de escritura en el proyecto. Los colaboradores también pueden subir desde el estudio con un token granular de Contents de escritura limitado al repositorio.

Actions valida el cifrado, la duración y ambas pistas. Cuando están las tres tomas, FFmpeg las sincroniza con la presentación y produce un MP4 1920×1080 a 24 fps, H.264 y AAC estéreo. El montaje usa el mismo fondo animado que el ensayo, una columna para el presentador y nivelación de voz. Una nueva toma válida sustituye a la anterior y activa un nuevo montaje. Para descargar, cada integrante abre su invitación y selecciona «Descargar video final».

El repositorio conserva los paquetes cifrados y el montaje cifrado. Los originales descifrados sólo se usan en el directorio temporal del runner. El estado público presenta la recepción por integrante. El secreto de Actions `STUDIO_KEYS` contiene cuatro claves generadas específicamente para este proyecto. El estado persistente se guarda en la rama `studio-state`. El workflow publica con GitHub Pages en modo GitHub Actions. La descarga del MP4 ocurre en el navegador del integrante.

Para repetir una validación o recuperar un despliegue fallido, ejecuta el workflow **Estudio · recepción y montaje** sobre `main`. Para probar la interfaz localmente, sirve la carpeta `site` sobre localhost o HTTPS.
