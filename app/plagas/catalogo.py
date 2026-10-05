"""Catálogo del negocio: los HECHOS que Nea puede afirmar.

Fuente: «Nea — Especificación de comportamiento» de Control de Plagas ROCA
(secciones 4 a 7). Todo lo que el agente dice de plagas, tratamientos, precios
y zonas sale de aquí; el modelo de lenguaje solo lo redacta.

PARA CAMBIAR UN PRECIO, UNA ZONA O UN TEXTO: edita este archivo y redespliega.
No hay que tocar nada más.

`None` en un precio significa «todavía no nos dieron la fórmula»: Nea junta los
datos del lead y le pasa la conversación al dueño para que cotice él, en vez de
inventar una cifra. Lo que falta está listado en `docs/roca/PENDIENTES.md`.
"""
from __future__ import annotations

from typing import Any

NEGOCIO = {
    "nombre": "Control de Plagas ROCA",
    # Con quién se le dice al CLIENTE que habla cuando se le pasa su caso. Nunca
    # se menciona al dueño ni su nombre: es «un técnico especializado». (Quién es
    # de verdad lo sabe solo el dueño, en su WhatsApp.)
    "dueno": "un técnico especializado",
    "moneda": "MXN",
    "pago": "Se liquida al término de cada visita.",
    # Solo se dice si el lead pide factura (especificación, sección 5).
    "factura": "Si necesitas factura, al precio se le agrega el IVA.",
}

# --------------------------------------------------------------- cobertura ---
# Rangos de código postal (inclusive). El nombre manda; el CP desempata
# colonias que se llaman igual en distintas alcaldías.

ZONAS_EXCLUIDAS: list[dict[str, Any]] = [
    {"nombre": "Tepito", "patrones": [r"\btepito\b"], "cps": []},
    {"nombre": "Ecatepec", "patrones": [r"\becatepec\b"], "cps": [(55000, 55549)]},
    {
        "nombre": "Gustavo A. Madero",
        "patrones": [r"\bgustavo\s+a\.?\s*madero\b", r"\bg\.?\s?a\.?\s?m\.?(?=\s|$|,)"],
        "cps": [(7000, 7999)],
    },
]

# Se atienden, pero solo el día indicado (0 = lunes … 6 = domingo).
ZONAS_DIA_RESTRINGIDO: list[dict[str, Any]] = [
    {"nombre": "Lerma", "patrones": [r"\blerma\b"], "cps": [(52000, 52059)],
     "dia": 2, "dia_nombre": "miércoles"},
    {"nombre": "Toluca", "patrones": [r"\btoluca\b"], "cps": [(50000, 50299)],
     "dia": 2, "dia_nombre": "miércoles"},
]

# Códigos postales que SÍ se atienden. Supuesto a confirmar con el negocio
# (ver PENDIENTES): Ciudad de México y Estado de México, menos lo excluido.
COBERTURA_CPS: list[tuple[int, int]] = [(1000, 16999), (50000, 57999)]

# ------------------------------------------------------------------ plagas ---
# Cada señal: `texto` (cómo se describe), `pregunta` (cómo se le pregunta al
# lead, UNA sola interrogación) y `claves` (raíces que la delatan en el texto
# del lead; sirven para auditar que el modelo no etiquete de más).

CUCARACHA_SENALES: dict[str, dict[str, Any]] = {
    "tamano_chica": {
        "especie": "cucaracha_alemana", "tipo": "tamano",
        "texto": "chica, de 1 a 2 cm, café claro con dos rayitas negras",
        "claves": ["chic", "chiq", "pequen", "1 cm", "2 cm", "rayit", "cafe claro", "clarit", "mini", "alemana", "diminut"],
    },
    # «Voladoras» y «patinadoras»: así le dice la gente a la grande de drenaje
    # (audio del dueño, 1 de octubre).
    "tamano_grande": {
        "especie": "cucaracha_americana", "tipo": "tamano",
        "texto": "grande, de 4 a 5 cm, café rojizo oscuro (le dicen voladora o patinadora)",
        "claves": ["grand", "enorm", "4 cm", "5 cm", "rojiz", "oscur", "vuela", "volador", "patinador", "gigant", "americana"],
    },
    "ubicacion_cocina": {
        "especie": "cucaracha_alemana", "tipo": "ubicacion",
        "texto": "en la cocina: detrás del microondas, la licuadora o el refrigerador, en gabinetes y alacena, cerca de la tarja",
        "claves": ["cocin", "refri", "microond", "licuadora", "gabinet", "tarja", "estufa", "horno", "alacena", "fregadero", "lavatrastes", "trastes", "despensa", "electrodomestic", "contacto"],
    },
    "ubicacion_drenaje": {
        "especie": "cucaracha_americana", "tipo": "ubicacion",
        "texto": "en áreas comunes, estacionamiento, patios, sótanos, la calle o cerca de coladeras, drenajes y registros",
        "claves": ["coladera", "drenaje", "registro", "patio", "sotano", "estacionamiento", "alcantarill", "calle", "banqueta", "area comun", "areas comun", "cisterna"],
    },
    # El baño NO distingue: las dos especies pueden estar ahí.
    "ubicacion_bano": {
        "especie": None, "tipo": "ubicacion",
        "texto": "en el baño o sanitario (no distingue la especie)",
        "claves": ["bano", "sanitario", "regadera", "wc", "lavabo"],
    },
    # Solo vale después de la tarjeta comparativa: el lead eligió una.
    "eligio_alemana": {
        "especie": "cucaracha_alemana", "tipo": "eleccion",
        "texto": "tras ver la comparación, dijo que se parece a la alemana (la chica de cocina)",
        "claves": ["alemana", "primera", "chica", "cocina", "la 1", "chiquita", "pequena"],
    },
    "eligio_americana": {
        "especie": "cucaracha_americana", "tipo": "eleccion",
        "texto": "tras ver la comparación, dijo que se parece a la americana (la grande de drenaje)",
        "claves": ["americana", "segunda", "grande", "drenaje", "la 2", "grandota"],
    },
    # Comportamiento e incidencia: cuando tamaño y lugar no cierran, se sigue
    # identificando por cómo se comportan (no se pide foto: muchas salen
    # borrosas y ni un experto puede decidir con ellas).
    "comp_vuela_patina": {
        "especie": "cucaracha_americana", "tipo": "comportamiento",
        "texto": "las ha visto volar o patinar por el piso",
        "claves": ["vuel", "volad", "patin", "planea"],
    },
    "comp_aisladas": {
        "especie": "cucaracha_americana", "tipo": "comportamiento",
        "texto": "se ven de una en una, aisladas, o salen cuando llueve",
        "claves": ["una sola", "de una en una", "una a la vez", "aislad", "solitar", "de vez en cuando", "ocasional", "lluvia", "llueve", "una que otra"],
    },
    "comp_se_esconden": {
        "especie": "cucaracha_alemana", "tipo": "comportamiento",
        "texto": "se esconden rápido cuando prende la luz y salen de noche",
        "claves": ["escond", "huyen", "corren rapido", "corre rapido", "prendo la luz", "enciendo la luz", "de noche", "por la noche"],
    },
    "comp_muchas_juntas": {
        "especie": "cucaracha_alemana", "tipo": "comportamiento",
        "texto": "se ven muchas juntas, de varios tamaños (también bebés)",
        "claves": ["muchas", "varias", "juntas", "bebe", "ninfa", "distintos tamanos", "varios tamanos", "todos los tamanos", "bolitas"],
    },
}

# Preguntas de comportamiento, en orden; cada una se hace UNA vez.
PREGUNTAS_CUCARACHA_COMPORTAMIENTO: list[tuple[str, str]] = [
    (
        "comportamiento_1",
        "¿Las has visto volar o patinar por el piso, o más bien se esconden "
        "rápido cuando prendes la luz?",
    ),
    (
        "comportamiento_2",
        "¿Se ven muchas juntas, de varios tamaños (también chiquitas), o "
        "aparecen de una en una?",
    ),
]

PREGUNTA_CUCARACHA_TAMANO = (
    "¿De qué tamaño son: chiquitas 🤏 (1 a 2 cm, café claro) o grandes 🚀 "
    "(4 a 5 cm, café rojizo oscuro)?"
)

# Cuando el cliente solo dice «cucarachas» y no cuenta nada más: se le presentan
# las dos especies comunes (texto del profesor, 4 oct) y se le pide que cuente
# cuál ha visto y dónde. Las dos preguntas del final reemplazan a «¿de qué tamaño?».
INTRO_CUCARACHAS = (
    "Para darte el tratamiento y el costo exactos 🎯 necesito saber qué cucaracha tienes. "
    "Hay dos comunes 🪳\n\n"
    "1️⃣ *De cocina (alemana)* 🏠: chica (1 a 2 cm), café claro con dos rayitas negras. "
    "Sale bajo la tarja, el refri o en gabinetes, sobre todo de noche 🌙\n"
    "2️⃣ *De drenaje (americana)* 🌧️: grande (4 a 5 cm), café rojizo oscuro. Sale en "
    "patios, coladeras y registros 🚪\n\n"
    "📌 ¿Cuál has visto y dónde? ¿Más dentro de casa o afuera? 🔍"
)
# Pregunta con pistas concretas, no «¿en la cocina o en el drenaje?»: quien ya dijo
# «de la cocina» no debe sentir que se le repite, y lo que contesta confirma.
PREGUNTA_CUCARACHA_UBICACION = (
    "¿Las has visto detrás del refrigerador o de otros electrodomésticos, en "
    "gabinetes, contactos de luz o cerca de la tarja — o más bien cerca de "
    "coladeras, drenajes o el patio?"
)

TARJETA_CUCARACHAS = (
    "Para ubicarla bien, compárala con estas dos 🪳🔍\n\n"
    "*Alemana (de cocina)*: chica, de 1 a 2 cm, café claro con dos rayitas "
    "negras. Se ve sobre todo en la cocina: detrás del refri o el microondas, "
    "en gabinetes, cerca de la tarja.\n\n"
    "*Americana (de drenaje)*: grande, de 4 a 5 cm, café rojizo oscuro. Sale "
    "en patios, sótanos, estacionamiento o áreas comunes, cerca de coladeras "
    "y drenajes.\n\n"
    "¿A cuál se parece más la que has visto?"
)

OFERTA_FOTO = (
    "Para no fallarle al diagnóstico, lo más fácil es verla 📸 "
    "¿Me puedes mandar una foto de una de ellas (aunque esté muerta)?"
)

PLAGAS: dict[str, dict[str, Any]] = {
    "cucaracha_alemana": {
        "nombre": "Cucaracha alemana", "apodo": "la chica, de cocina", "emoji": "🪳",
        "expectativa": "erradicación",
        # Lo primero que el dueño le dice a quien la tiene (audio del 1 de
        # octubre): que no es por falta de higiene y que tiene solución. Va
        # arriba del tratamiento al confirmar la plaga.
        "tranquilidad": (
            "No te preocupes: no es por falta de higiene 🧼. Es un insecto que "
            "suele entrar a casa sin que nos demos cuenta, y tiene solución ✅."
        ),
        "visitas": "2 visitas (entre 8 y 10 días entre una y otra)",
        "resumen": (
            "No es una aspersión general: el técnico aplica un cebo en polvo fino en huecos "
            "y grietas, en las zonas de refugio que ya sabe identificar 🔍. Son dos dosis 💉: la 1ª "
            "elimina a los adultos 🪳 y la 2ª ataca a los recién nacidos 🐣 antes de su edad "
            "reproductiva, rompiendo el ciclo reproductivo 🔄."
        ),
        "procedimiento": (
            "Tras una inspección el técnico aplica un cebo en polvo fino en huecos y "
            "grietas, en las zonas de refugio que ya sabe identificar (no es una "
            "aspersión general). La 1ª visita elimina a los adultos; la 2ª ataca a los "
            "recién nacidos y jóvenes antes de que lleguen a la edad reproductiva, y "
            "así se rompe el ciclo reproductivo y se logra el control."
        ),
        "contencion": (
            "Antes y entre visitas, no uses aerosol ni remedios caseros 🚫. No limpies "
            "las zonas tratadas por 24 horas y cubre los alimentos 🍞."
        ),
        "precio": {
            "tipo": "por_inmueble",
            "variables": ["tipo_inmueble"],
            "inmuebles": {"casa": 1200, "departamento": 1100, "local_comercial": 1500},
            # Más de 4 refrigeradores/congeladores → inspección en sitio.
            "max_refrigeradores": 4,
        },
    },
    "cucaracha_americana": {
        "nombre": "Cucaracha americana", "apodo": "la grande, de drenaje", "emoji": "🪳",
        "expectativa": "control sostenido (no es permanente)",
        "visitas": "2 visitas (la segunda a los 15 días)",
        "resumen": (
            "Tratamos el drenaje por pasos 🔧: caídas de agua y pluviales ☔ (barrera "
            "descendente), nebulización dentro de ductos 🌀 y registros de planta baja 🔍, "
            "trabajando contra su entrada para sacarlas por donde llegaron ⬆️. La 2ª "
            "visita sostiene el control ✅."
        ),
        "procedimiento": (
            "1) Aplicación en caídas de agua y pluviales, desde la parte superior del "
            "sistema, para crear una barrera descendente. 2) Nebulización con producto "
            "profesional dentro de ductos y cañerías. 3) Apertura de registros y "
            "coladeras de planta baja para aplicar en las zonas de mayor actividad. "
            "4) Presión hacia el exterior: se trabaja en dirección contraria a su "
            "entrada, forzándolas a salir por donde llegaron. La 2ª visita, a los 15 "
            "días, sostiene el control. Aplica si es la primera vez o si llevas un año "
            "o más sin control."
        ),
        "contencion": "Antes y entre visitas, no uses aerosol ni remedios caseros 🚫.",
        "precio": {
            "tipo": "calculadora_sanitarios",
            "variables": ["tipo_inmueble", "registros", "sanitarios"],
            "inmuebles_validos": ["casa", "departamento", "edificio"],
            # PENDIENTE: la tarifa base por tipo de inmueble no venía en la
            # especificación. Con None, Nea junta los datos y cotiza el dueño.
            "base": {"casa": None, "departamento": None, "edificio": None},
            "sanitarios_incluidos": 3,
            "extra_por_sanitario": 100,
        },
    },
    "hormiga": {
        "nombre": "Hormiga común", "emoji": "🐜",
        "expectativa": "control con seguimiento",
        "visitas": "1 visita (no es un esquema cerrado de dos)",
        "resumen": "Se coloca cebo en gel sobre el camino de las hormigas: las obreras lo llevan al nido y alimentan con él a la reina y a las larvas.",
        "procedimiento": (
            "Se coloca cebo insecticida en gel sobre el camino activo de las "
            "hormigas: las obreras lo cargan al nido y con eso alimentan a la "
            "reina y a las larvas."
        ),
        "contencion": (
            "MUY IMPORTANTE: no uses aerosol ni laves la zona tratada con "
            "detergente o cloro. Eso rompe el cebo y dispersa a la colonia."
        ),
        "contencion_obligatoria": True,
        "precio": {
            "tipo": "por_inmueble_m2",
            "variables": ["tipo_inmueble", "m2"],
            "tramos": {
                "casa": [(120, 200, 1700), (201, 300, 2000)],
                "departamento": [(50, 100, 1300), (101, 250, 2200)],
            },
        },
        "senales": {
            "fila_visible": {
                "texto": "se ve una fila o camino de hormigas",
                "pregunta": "¿Las ves caminando en fila, como siguiendo un caminito?",
                "claves": ["fila", "camin", "hilera", "linea", "siguen"],
            },
            "zonas": {
                "texto": "se sabe en qué zonas andan (cocina, jardín, coladeras)",
                "pregunta": "¿En qué zonas las ves: cocina, jardín, coladeras?",
                "claves": ["cocina", "jardin", "coladera", "azucar", "comida", "patio", "bano", "sala", "recamara", "mesa", "barra"],
            },
            "punto_entrada": {
                "texto": "se identificó por dónde entran",
                "pregunta": "¿Has notado por dónde entran (una grieta, una ventana, un enchufe)?",
                "claves": ["entran", "salen de", "grieta", "ventana", "enchufe", "hoyo", "agujero", "pared", "rendija"],
            },
            "constancia": {
                "texto": "el camino es constante (aparecen todos los días)",
                "pregunta": "¿Aparecen todos los días o solo de vez en cuando?",
                "claves": ["todos los dias", "diario", "siempre", "constante", "a diario", "cada dia", "todo el tiempo"],
            },
        },
    },
    "roedores": {
        "nombre": "Roedores", "emoji": "🐭",
        "expectativa": "control",
        "visitas": "1 visita, con monitoreo posterior",
        "resumen": "Cajas cebadero en el perímetro exterior y, adentro, monitoreo con trampas adhesivas (no se ceban ductos ni entradas internas, por las mascotas).",
        "procedimiento": (
            "Se colocan cajas cebadero en el perímetro exterior y, adentro, "
            "monitoreo con trampas adhesivas. No se ceban ductos ni entradas "
            "internas, por el riesgo para las mascotas."
        ),
        "precio": {
            "tipo": "calculadora_area",
            "variables": ["m2"],
            # PENDIENTE: fórmula de cajas cebadero y su precio. El número de
            # cajas lo calcula el sistema; JAMÁS se le pregunta al lead.
            "precio_por_caja": None,
            "m_por_caja": None,
        },
        "senales": {
            "excremento": {
                "texto": "excremento pequeño y oscuro",
                "pregunta": "¿Has encontrado excremento chiquito y oscuro, como granitos de arroz negros?",
                "claves": ["excrement", "caca", "popo", "heces", "bolit", "granit"],
            },
            "ruidos_nocturnos": {
                "texto": "ruidos por la noche",
                "pregunta": "¿Escuchas ruidos de noche, como que rascan o corren?",
                "claves": ["ruido", "rasc", "corren", "se oye", "se escucha", "noche"],
            },
            "empaques_roidos": {
                "texto": "empaques o cosas roídas",
                "pregunta": "¿Has encontrado empaques, cables o comida mordisqueados?",
                "claves": ["roid", "mordi", "mordisq", "empaque", "cable", "bolsa", "comid", "royeron", "roen"],
            },
            "avistamiento": {
                "texto": "los han visto (tamaño ratón o rata)",
                "pregunta": "¿Has visto alguno, y era chiquito como ratón o grande como rata?",
                "claves": ["vi un", "vi una", "vimos", "raton", "rata", "he visto", "lo vi", "paso corriendo"],
            },
        },
    },
    "alacran": {
        "nombre": "Alacrán", "emoji": "🦂",
        "expectativa": "control (mantenimiento continuo)",
        "visitas": "sin esquema cerrado de visitas (es mantenimiento)",
        "resumen": "Aspersión residual en zonas de tránsito y refugio: jardín, cochera, patio y bardas (no incluye sellado de grietas ni trampas).",
        "procedimiento": (
            "Aspersión residual en las zonas de tránsito y refugio: jardín, "
            "cochera, patio y bardas. No incluye sellado de grietas ni trampas."
        ),
        "precio": {
            "tipo": "por_m2",
            "variables": ["tipo_inmueble", "m2"],
            "inmuebles_validos": ["casa", "departamento"],
            "tramos": [(100, 200, 1800), (201, 300, 2500)],
            "promo": "Promo 2x1: incluye control de araña sin costo adicional en la misma visita.",
        },
        "senales": {
            "cola_aguijon": {
                "texto": "cola curva con aguijón",
                "pregunta": "¿Tiene la cola levantada y curva, con un aguijón en la punta?",
                "claves": ["cola", "aguijon", "colita", "pica con"],
            },
            "pinzas": {
                "texto": "pinzas visibles al frente",
                "pregunta": "¿Le viste pinzas al frente, como tenazas?",
                "claves": ["pinza", "tenaza"],
            },
            "actividad_nocturna": {
                "texto": "sale de noche",
                "pregunta": "¿Los has visto sobre todo de noche?",
                "claves": ["noche", "nocturn", "madrugada", "oscur"],
            },
            "escondites": {
                "texto": "aparece en escondites típicos (macetas, piedras, baño)",
                "pregunta": "¿Dónde aparecen: entre macetas, piedras, en el baño?",
                "claves": ["maceta", "piedra", "bano", "zapato", "ropa", "lena", "escombro", "debajo", "tabique", "patio", "jardin", "cochera", "barda", "pared"],
            },
        },
    },
    "arana": {
        "nombre": "Araña", "emoji": "🕷️",
        "expectativa": "control (mantenimiento continuo)",
        "visitas": "sin esquema cerrado de visitas (es mantenimiento)",
        "resumen": "Aspersión residual en el exterior y protección complementaria adentro; las telarañas visibles se retiran como parte del servicio.",
        "procedimiento": (
            "Aspersión residual en el exterior y protección complementaria en "
            "el interior. Las telarañas visibles se retiran como parte del servicio."
        ),
        "precio": {
            "tipo": "por_m2",
            "variables": ["m2"],
            "tramos": [(1, 100, 1800), (101, 200, 2500)],
            "promo": "Promo 2x1: incluye control de alacrán sin costo adicional.",
        },
        "senales": {
            # Lo primero que se pregunta (4 oct): ¿en el jardín o dentro de casa? Dónde
            # las ve dice mucho de dónde viven y por dónde entran.
            "ubicacion_arana": {
                "texto": "dónde las ve: en el jardín o exterior, o dentro de la casa",
                "pregunta": "¿Las has visto más en el jardín o en el exterior, o dentro de tu casa?",
                "claves": ["jardin", "exterior", "afuera", "patio", "azotea", "terraza", "interior", "adentro", "dentro", "sala", "cocina", "recamara", "cuarto", "bano", "closet", "techo"],
                "detecta": (
                    r"\b(jardin\w*|exterior|afuera|patio|azotea|terraza|interior|adentro|sala|"
                    r"cocina|recamara|cuarto|bano|closet)\b|\bdentro de (mi|la|el|casa|tu)\b"
                ),
            },
            "patas_largas": {
                "texto": "patas largas y delgadas",
                "pregunta": "¿Tienen las patas largas y delgaditas?",
                "claves": ["patas", "patona", "patas largas", "delgad"],
            },
            "telarana": {
                "texto": "telarañas visibles",
                "pregunta": "¿Has visto telarañas en rincones o ventanas?",
                "claves": ["telara", "tela de ara", "telas"],
            },
            "cuerpo_chico": {
                "texto": "cuerpo chico, del tamaño de una moneda",
                "pregunta": "¿El cuerpo es chico, más o menos del tamaño de una moneda?",
                "claves": ["moneda", "chic", "pequen", "chiquit"],
            },
            "escondites": {
                "texto": "aparece en rincones, closets o zapatos",
                "pregunta": "¿Dónde las encuentras: rincones, closets, zapatos?",
                "claves": ["rincon", "closet", "zapato", "esquina", "techo", "ropero", "bodega", "caja"],
            },
        },
        # Seguridad (sección 4.3): sin alarmar ni diagnosticar picaduras. Se dice
        # SOLO si el lead nombra una araña peligrosa (ARANA_PELIGROSA: violinista,
        # viuda negra…). Texto del dueño (4 oct): no se puede saber a distancia cuál
        # es; se le da tranquilidad de que se controla sea la que sea.
        "tranquilidad_peligrosa": (
            "Entiendo tu preocupación 🙏 Saber si es violinista o viuda negra solo se "
            "puede capturándola para que un técnico especializado la identifique en el "
            "momento de la visita, o con una foto muy nítida, porque se distinguen por "
            "rasgos muy específicos. Lo importante es que nosotros las controlamos sea "
            "cual sea la especie: las arañas viven y se desarrollan en el exterior, y van "
            "entrando a los domicilios para refugiarse de condiciones del clima que no les "
            "favorecen."
        ),
    },
    "tijerilla": {
        "nombre": "Tijerilla", "emoji": "✂️",
        "expectativa": "control",
        "visitas": "2 visitas (entre 8 y 10 días entre una y otra; las dos son indispensables)",
        "resumen": "1ª visita: barrera en marcos, puertas, ventanas y zócalos. 2ª visita: se repite para cortar el ciclo antes de que lo que eclosiona llegue a adulto.",
        "procedimiento": (
            "En la 1ª visita se hace una barrera en marcos, puertas, ventanas "
            "y zócalos. Los huevecillos eclosionan después de esa primera "
            "aplicación, así que la 2ª visita repite el tratamiento para "
            "cortar el ciclo antes de que lleguen a adultos."
        ),
        "precio": {
            "tipo": "por_m2",
            "variables": ["m2"],
            "tramos": [(1, 100, 1000)],
        },
        # PROPUESTA (no venía en la especificación): confirmar con el negocio.
        "senales": {
            "pinzas_cola": {
                "texto": "dos pincitas (tenazas) en la punta de la cola",
                "pregunta": "¿Tiene dos pincitas en la punta de la cola, como unas tijeritas?",
                "claves": ["pinc", "pinza", "tijer", "tenaza", "cola"],
            },
            "cuerpo_alargado": {
                "texto": "cuerpo alargado, café oscuro",
                "pregunta": "¿Es alargadita y de color café oscuro?",
                "claves": ["alargad", "larguit", "cafe", "oscur", "delgad"],
            },
            "zonas_humedas": {
                "texto": "aparece en zonas húmedas o entra por puertas y ventanas",
                "pregunta": "¿Dónde aparecen: cerca de puertas, ventanas o zonas húmedas?",
                "claves": ["humed", "puerta", "ventana", "bano", "jardin", "maceta", "zocalo", "piso"],
            },
        },
    },
    "chinches": {
        "nombre": "Chinches de cama", "emoji": "🛏️",
        "expectativa": "erradicación",
        "visitas": "2 visitas en el 95% de los casos (una 3ª solo si la infestación es alta)",
        "resumen": (
            "Inspección 🔍 de refugios (cama, colchón, cabecera, closets), vapor de agua a "
            "alta temperatura ♨️ para eliminar por calor a las presentes, y aspersión "
            "líquida 💧 que al secar deja una capa protectora 🛡️. Sillones y sillas, solo "
            "con líquido."
        ),
        "procedimiento": (
            "Inspección de los sitios de refugio; vapor y calor focalizado en las 6 "
            "caras de cada colchón, base, cabecera y closets, y aspersión líquida "
            "complementaria que deja una capa protectora al secar. Sillones y sillas "
            "se tratan solo con líquido, por el textil. La 2ª visita, entre 8 y 10 días "
            "después, elimina a las crías recién nacidas y rompe el ciclo."
        ),
        # Fórmula del dueño (3 oct 2026), POR VISITA: 1 colchón $1,300; 2 colchones
        # $1,500; cada colchón adicional +$250. Hasta 3 sillones y 6 sillas de
        # comedor están incluidos; cada sillón de más +$100 y cada silla de más +$20.
        "precio": {
            "tipo": "calculadora_colchones",
            "variables": ["colchones", "sillones", "sillas_comedor", "sillas_secretariales"],
            "un_colchon": 1300, "dos_colchones": 1500, "colchon_adicional": 250,
            "sillones_incluidos": 3, "sillon_extra": 100,
            "sillas_incluidas": 6, "silla_extra": 20,
            # Sillas secretariales: hasta 2 sin costo; de la 3ª en adelante +$50 c/u.
            "secretariales_incluidas": 2, "secretarial_extra": 50,
            # Se preguntan juntos, en UN mensaje (antes eran tres preguntas seguidas).
            "pregunta_conjunta": (
                "¿Cuántos colchones, sillones, sillas de comedor tapizadas y sillas "
                "secretariales hay en total en toda la casa? Cuento todos, no solo "
                "los del problema, y si no hay de alguno dime 0."
            ),
        },
        "senales": {
            # Cualquier DOS bastan. Dos de las que el cliente ya contó en sus
            # primeras respuestas confirman: no se le interroga por las demás.
            "dice_chinches": {
                "texto": "el cliente dice que son chinches",
                "pregunta": "",
                "claves": ["chinche"],
                "no_preguntar": True,
                # `detecta`: el servidor la reconoce en lo que el lead ESCRIBIÓ,
                # aunque el modelo no la haya etiquetado (texto normalizado).
                "detecta": r"chinche",
            },
            "bicho_visto": {
                "texto": "vio los insectos (cabecera, costuras, colchón)",
                "pregunta": "¿Has visto los insectos, por ejemplo detrás de la cabecera o en las costuras del colchón?",
                "claves": ["chinche", "animalit", "bichit", "bicho", "insect", "los vi", "las vi", "vi unos", "vi una", "encontr"],
                "detecta": (
                    r"\b(vi|vimos|veo|vemos|encontr\w*|salen|aparecen|andan|hay)\b[^.?!]{0,40}"
                    r"\b(animalit\w*|bichit\w*|bicho\w*|insect\w*|chinche\w*)\b"
                    r"|\b(animalit\w*|bichit\w*|bicho\w*|insect\w*)\b[^.?!]{0,30}\b(cabecera|colchon|costura\w*|cama|sabana\w*)\b"
                ),
            },
            "piquetes_linea": {
                "texto": "piquetes en línea al despertar",
                "pregunta": "¿Amanecen con piquetes en línea o en hilera?",
                "claves": ["piquete", "ronch", "linea", "hilera", "amanec", "despert", "picad"],
                "detecta": r"\bpiquete\w*|\bpicadura\w*|\bronch\w*|\bme (pican|picaron|amanezco picad\w*)",
            },
            "manchas_sabanas": {
                "texto": "manchas oscuras o de sangre en las sábanas",
                "pregunta": "¿Has visto manchitas oscuras o de sangre en las sábanas?",
                "claves": ["mancha", "sangre", "sabana"],
                "detecta": r"\bmanch\w*[^.?!]{0,40}\b(sabana\w*|cama|colchon|almohada|cabecera|sangre)\b|\bsangre\b[^.?!]{0,30}\b(sabana\w*|cama|colchon)\b",
            },
            "puntos_colchon": {
                "texto": "puntos negros en las costuras del colchón",
                "pregunta": "¿Has visto puntitos negros en las costuras del colchón?",
                "claves": ["punto", "puntit", "costura", "colchon"],
                "detecta": r"\bpuntos? negros?\b|\bpuntit\w* negr\w*|\bexcremento\w*|\bcostura\w*[^.?!]{0,30}\bpuntit\w*",
            },
            "viaje_o_mueble": {
                "texto": "viaje reciente o mueble usado",
                "pregunta": "¿Hubo un viaje reciente o llegó algún mueble usado a casa?",
                "claves": ["viaj", "hotel", "mueble usad", "segunda mano", "usado", "airbnb", "mudanza"],
                # Si lo cuenta, suma; pero no se le interroga por esto.
                "no_preguntar": True,
            },
        },
    },
    "pulgas": {
        "nombre": "Pulgas", "emoji": "🐕",
        "expectativa": "erradicación",
        "visitas": "2 visitas (entre 8 y 12 días entre una y otra; puede requerir una 3ª)",
        "resumen": "Aspersión con bomba neumática donde anda y descansa la mascota (sin calor); el intervalo entre visitas va por el ciclo de la pupa.",
        "procedimiento": (
            "Aspersión con bomba neumática en las zonas donde anda y descansa "
            "la mascota. No se usa calor. El intervalo entre visitas es fijo "
            "por el ciclo de vida de la pupa."
        ),
        "precio": {
            "tipo": "calculadora_muebles",
            "variables": ["colchones", "sillones", "sillas_comedor"],
            # PENDIENTE: precio por colchón, sillón y silla.
            "por_colchon": None, "por_sillon": None, "por_silla": None, "base": None,
        },
        "senales": {
            "piquetes_tobillos": {
                "texto": "piquetes en tobillos y pantorrillas",
                "pregunta": "¿Los piquetes les salen sobre todo en tobillos y pantorrillas?",
                "claves": ["tobillo", "pantorrilla", "pierna", "pies", "piquete"],
            },
            "saltan": {
                "texto": "insectos que saltan",
                "pregunta": "¿Has visto que los bichitos saltan?",
                "claves": ["salta", "brinc"],
            },
            "mascotas": {
                "texto": "hay mascotas en casa",
                "pregunta": "¿Tienen mascotas en casa?",
                "claves": ["mascota", "perr", "gat", "cachorr"],
            },
            "zona_mascota": {
                "texto": "hay más actividad donde duerme la mascota",
                "pregunta": "¿Los notas más donde duerme o se echa la mascota?",
                "claves": ["duerme", "cama del", "camita", "donde se echa", "tapete", "cojin"],
            },
        },
    },
    "termita_madera_seca": {
        "nombre": "Termita de madera seca", "emoji": "🪵",
        "expectativa": "erradicación",
        "visitas": "se define tras la inspección",
        "resumen": "Primero una inspección técnica en sitio identifica las piezas dañadas y se presupuesta por pieza; incluye garantía de 3 años.",
        "procedimiento": (
            "Primero va una inspección técnica en sitio para identificar las "
            "piezas dañadas; se presupuesta por pieza. Incluye garantía de 3 años."
        ),
        "precio": {"tipo": "inspeccion", "variables": []},
        "senales": {
            "frass": {
                "texto": "granitos tipo arena o café molido (frass)",
                "pregunta": "¿Has visto montoncitos de granitos, como arena o café molido, junto a la madera?",
                "claves": ["granit", "arena", "cafe molido", "polvito", "aserrin", "polvo"],
            },
            "madera_hueca": {
                "texto": "madera que suena hueca",
                "pregunta": "¿La madera suena hueca si la golpeas?",
                "claves": ["hueca", "hueco", "suena"],
            },
            "agujeritos": {
                "texto": "agujeritos de 2 mm o menos",
                "pregunta": "¿Tiene agujeritos muy chiquitos, como de alfiler?",
                "claves": ["agujer", "hoyit", "hoyo", "orifici", "perforac"],
            },
            "alas_sueltas": {
                "texto": "alas sueltas cerca de ventanas o puertas",
                "pregunta": "¿Has encontrado alitas sueltas cerca de ventanas o puertas?",
                "claves": ["alas", "alitas", "palomilla"],
            },
        },
    },
    # Siempre con una persona: no se identifican ni se cotizan por chat.
    "termita_subterranea": {
        "nombre": "Termita subterránea", "emoji": "🪵",
        "siempre_dueno": (
            "Es un servicio distinto al de madera seca y siempre requiere "
            "asistencia humana: no se cotiza por chat."
        ),
    },
    "moscas_mosquitos": {
        "nombre": "Moscas y mosquitos", "emoji": "🦟",
        "siempre_dueno": (
            "Es un servicio de control (no de erradicación) y siempre requiere "
            "una evaluación humana: no se cotiza por chat."
        ),
    },
}

# Lo que el lead dice → clave del catálogo. `cucaracha` es genérica: la
# especie la decide el diagnóstico. `no_se_sabe`: todavía no dijo qué es.
PLAGAS_PARA_MODELO = [
    "cucaracha", "hormiga", "roedores", "alacran", "arana", "tijerilla",
    "chinches", "pulgas", "termita_madera_seca", "termita_subterranea",
    "moscas_mosquitos", "otra", "no_se_sabe",
]

# Cómo le dice la gente → plaga del catálogo. Sirve para que una descripción
# que SÍ es del catálogo («araña negra con mancha roja») no termine como
# «otra plaga» y en un pase al dueño que no hacía falta.
ALIAS: list[tuple[str, str]] = [
    (r"cucarach", "cucaracha"),
    (r"hormig", "hormiga"),
    (r"\b(rata|ratas|raton|ratones|ratoncit\w*|roedor\w*|ratita\w*)\b", "roedores"),
    (r"alacr|escorpi", "alacran"),
    (r"arana|viuda negra|violinista|tarantul", "arana"),
    (r"tijerill|tijeret", "tijerilla"),
    (r"chinche", "chinches"),
    (r"pulga", "pulgas"),
    (r"termita(s)? subterrane|termitas? de (tierra|suelo)", "termita_subterranea"),
    (r"termit|carcoma|polilla de (la )?madera|polilla en (el|los) mueble", "termita_madera_seca"),
    (r"\bmosca|mosquit|zancud", "moscas_mosquitos"),
]

# Lo que se sabe que NO está en el catálogo (sección 4.3): pase al dueño a la
# primera, sin improvisar.
# Sin «palomilla»: así le dicen también a las termitas con alas.
FUERA_DE_CATALOGO = (
    r"piojo|garrapat|comej|grillo|avispa|abeja|paloma\b|palomas|murcielag|vibora|"
    r"serpiente|culebra|ciempies|caracol|babosa|gorgojo|cochinilla|lagartija|"
    r"tlacuache|zarigueya|acaro|chapulin|pececillo|mapache|ardilla|tuza"
)

# Violinista (mancha de violín en el lomo) o viuda negra (negra con mancha roja
# de reloj de arena): cuándo va la precaución de la araña.
ARANA_PELIGROSA = r"violin|reloj de arena|viuda|mancha roja|manchita roja"

# ------------------------------------------------------ dudas del servicio ---
# Lo que el lead pregunta para quedarse tranquilo («¿es tóxico?», «¿sí
# funciona?», «¿cuándo puedo volver a entrar?»). Fuente: audio del dueño del 1
# de octubre. Es lo ÚNICO aprobado para contestar esas dudas: el modelo lo dice
# con sus palabras y un candado revisa que no agregue nada (app/plagas/candados.py).
DUDAS: dict[str, str] = {
    "seguridad": (
        "Los productos que se usan no ponen en riesgo la salud de quienes "
        "viven en el inmueble."
    ),
    "reingreso": (
        "Se puede volver a entrar al área tratada en poco tiempo: de 15 a 20 "
        "minutos después de la aplicación."
    ),
    "eficacia": "El tratamiento sí es efectivo contra la plaga.",
    # Mascotas (texto del profesor para chinches, 4 oct). Sin cifras de dosis letal
    # ni «100 % seguro»: la indicación de un caso particular la confirma un técnico.
    "mascotas": (
        "Es de bajo riesgo para personas y animales en las condiciones de aplicación 🐾; "
        "no hay que desalojar. Por precaución, mantén a las mascotas lejos del área "
        "tratada mientras seca."
    ),
    # Edificios y áreas comunes (texto del profesor, 4 oct). El reingreso es el
    # aprobado (15 a 20 min), no los 10 minutos del texto original.
    "edificios": (
        "Aplicación focalizada 🎯 en áreas comunes (escaleras, estacionamiento, pasillos, "
        "azotea) y en coladeras de planta baja, con productos autorizados por la "
        "Secretaría de Salud ✅; sin riesgo para los habitantes. Mascotas 🐕🐈: dentro de "
        "casa durante la aplicación y esperar 15 a 20 minutos para transitar por las áreas "
        "tratadas. Atendemos arañas 🕷️, alacranes 🦂, cucaracha de drenaje 🪳 y roedores 🐭."
    ),
}
# El único tiempo de reingreso aprobado, en minutos (el candado rechaza otro).
REINGRESO_MINUTOS = (15, 20)

PREGUNTA_QUE_PLAGA ="¿Qué bicho es el que has visto, y en qué parte de tu casa?"
PREGUNTA_URGENCIA = "¿Has notado si han aumentado estos días?"

VARIABLES: dict[str, dict[str, Any]] = {
    "tipo_inmueble": {
        "pregunta": "¿Es casa, departamento o local comercial?",
        "descripcion": "casa | departamento | local_comercial | edificio",
    },
    "m2": {
        "pregunta": "¿Cuántos metros cuadrados son, más o menos, los que hay que tratar?",
        "descripcion": "metros cuadrados a tratar (número)",
    },
    "refrigeradores": {
        "pregunta": "¿Cuántos refrigeradores o congeladores hay en el local?",
        "descripcion": "refrigeradores/congeladores del local (número)",
    },
    "registros": {
        "pregunta": "¿Cuántos registros o coladeras hay que tratar?",
        "descripcion": "registros/coladeras a tratar (número)",
    },
    "sanitarios": {
        "pregunta": "¿Cuántos baños tiene en total el inmueble?",
        "descripcion": "sanitarios totales del inmueble (número)",
    },
    "colchones": {
        "pregunta": (
            "¿Cuántos colchones hay en total en toda la casa? Cuento todos, no "
            "solo el del problema: no se puede garantizar uno que no se trató."
        ),
        "descripcion": "colchones TOTALES de toda la casa (número)",
    },
    "sillones": {
        "pregunta": "¿Cuántos sillones hay en total?",
        "descripcion": "sillones totales (número)",
    },
    "sillas_comedor": {
        "pregunta": "¿Cuántas sillas de comedor tapizadas hay?",
        "descripcion": "sillas de comedor totales (número)",
    },
    "sillas_secretariales": {
        "pregunta": "¿Cuántas sillas secretariales (de oficina) hay?",
        "descripcion": "sillas secretariales o de oficina totales (número)",
    },
}

INMUEBLES = {
    "casa": "casa", "departamento": "departamento", "depto": "departamento",
    "local_comercial": "local comercial", "edificio": "edificio",
}
