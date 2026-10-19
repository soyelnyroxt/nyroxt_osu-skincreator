# nyroxt's osu! skin creator v2

    pip install -r requirements.txt
    python main.py

Archivos: main.py (interfaz), core.py (catálogo, proyecto, skin.ini, .osk), gens.py (generadores), gfx.py (formas/estilos).

- **Tema global**: forma, relleno, borde, resplandor, tipografía y paleta para todos los modos. Activa «Seguir el tema global» por elemento, o usa el botón para todos.
- **Temas listos** y **generador de paleta** (armonías) que colorea combos y tema.
- **Mania**: diseñador de notas (flecha, círculo, barra, diamante, estrella, corazón…), flechas que rotan por columna, teclas, escenario, explosiones, varias cantidades de teclas (ej. «4,7»).
- **Menú**: fondo, back, botones inferiores, paneles, logo y letras de ranking.
- **Recursos propios**: añade cualquier PNG/JPG con el nombre de archivo que quieras, o reemplaza un elemento por tu imagen.
- Al guardar se actualiza la carpeta `skin/` del proyecto; «Exportar .osk» crea el archivo final.

## Novedades v3
- Visualizadores con las mismas reglas de coordenadas que osu! (X en pantalla de alto 480, origen a la izquierda; selector de aspecto 16:9/16:10/4:3/21:9).
- Mania: arrastra con el ratón HitPosition, LightPosition, ScorePosition, ComboPosition, el escenario y su ancho (se guardan en skin.ini).
- Menú en unidades 1366x768 con imágenes @2x (ya no se salen botones/ranks) y botones "-over".
- Lienzos libres (barra superior/inferior de selección, perfil, decoración de mania) con capas de forma, texto e imagen.
- GIF -> fotogramas `nombre-0.png…` + AnimationFramerate; imágenes propias por archivo; "ocultar" exporta transparente; fuentes propias.

## Novedades v3.1
- Mania: grupo «Recursos de escenario» (imagen izquierda/derecha/base libres), 1K–20K (el ancho se estrecha solo para caber).
- Pausa, fallo y resultados: lienzos libres con texto, formas e imágenes (pause-*, fail-background, ranking-*).
- Taiko: pista y panel libres (taiko-bar-left/right). Std: contadores de teclado (inputoverlay).
- Catch: frutas por defecto = círculos. Tus imágenes de reemplazo se ajustan al tamaño esperado.

## Novedades v3.2
- Árbol con categorías propias: Imagen del menú, Pausa, Fallo y Resultados (con todas sus secciones).
- Casilla por modo: desactivado = no se exporta nada de ese modo y osu! usa su skin por defecto (tampoco se escriben sus claves en skin.ini).
- Botón «Recursos»: carpeta global de imágenes; arrástralas al visualizador de cualquier modo, o añade texto; se mueven y redimensionan libres. Los objetos de Pausa, Fallo y Menú principal se hornean en pause-overlay / fail-background / menu-background.
- Botones de pausa: «Botón con forma» o «Solo texto».
- Compatibilidad (en Tema global): stable/lazer, stable, lazer, legacy osu! (2008-2015) y totally (1x + @2x).
- Mania por defecto como tus capturas: notas círculo rosa, LN gris con punta, receptores aro.

## Novedades v3.3
- Pausa, fallo y resultados se editan desde un solo panel cada uno (sin lienzos): fondo, títulos, estilo de botón (texto, botón, píldora, contorno), textos en cualquier idioma y letras grandes.
- «Usar esta tipografía en TODO» en Estilo y paleta.
- Menú principal recolocado como en osu!; todos los jugadores aparecen como «Guest».
- Quitado lo repetido: botones «＋ Lienzo», «＋ Recurso», «Paleta aleatoria» y «Escena ⇄ Lienzo» (siguen en el árbol y en Herramientas).
- Arreglos: ColumnWidth de mania coincide con el ancho real en 11K-20K; Supr borra el objeto correcto; borrar un lienzo fijo ya no lo vuelve a crear.

## Efectos (✨)
- Sin código: eliges para qué sirve (300 animado, explosión de mania, partículas, combo burst, sección…) y un tipo de efecto (destello, onda, partículas, estrellas, pulso de texto, brillo giratorio). «Dame una idea» propone combinaciones.
- Con código: escribes `def frame(t, p):` en Python con un pincel sencillo (p.circle, p.ring, p.glow, p.star, p.line, p.text).
- osu! no ejecuta código en las skins (ni C# ni Python): se exportan los fotogramas como imágenes (hit300-0.png…), que es lo que osu! sí reproduce.
