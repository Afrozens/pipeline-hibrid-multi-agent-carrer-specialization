# Career Path Advisor — LangGraph Pipeline

**Career Path Advisor** es un sistema conversacional multi-agente basado en LangGraph que guía a estudiantes universitarios (Ing. Informática, Ing. Sistemas, autodidactas) a descubrir su especialización ideal en tecnología. Evalúa su perfil académico, experiencia laboral, habilidades técnicas, intereses personales y los cruza con tendencias actuales del mercado laboral tech para generar hasta 3 recomendaciones personalizadas.

## Stack

| Componente | Tecnología |
|---|---|
| Framework | FastAPI (Python ≥3.12) + LangGraph |
| LLM | OpenAI GPT-4o-mini (extractor/mapper) + GPT-4o (writer/recommendation) |
| Base de Datos | PostgreSQL + AsyncSession |
| PDF Processing | `pymupdf4llm` (CV → Markdown) |
| WebSearch | MCP / Tavily (tendencias de mercado) |
| Observabilidad | LangSmith (opcional) |
| Package Manager | `uv` |

## Commands

### Iniciar en desarrollo
```bash
uv run fastapi dev
```

### Iniciar en producción
```bash
uv run python -m app
```

### Aplicar migraciones
```bash
uv run python -m alembic upgrade head
```

### Generar nueva migración
```bash
uv run python -m alembic revision --autogenerate -m "msg"
```

## Arquitectura

```
app/
├── assistant_chat/               # Controladores, servicios y rutas de chat
│   ├── services/chat_service.py
│   ├── controllers/chat_controller.py
│   └── routes/chat.py
├── core/                          # Infraestructura transversal (DB, config)
├── profile_student/         # Perfil de usuario y validaciones
│   └── utils/
│       ├── field_content_rules.py
│       └── critical_field_validator.py
├── profile_student_attribute/  # Atributos key-value del perfil
├── generation/                    # Pipeline LangGraph + prompts + servicios
│   ├── graph/profile_graph.py
│   ├── services/
│   │   ├── pipeline_service.py
│   │   ├── extractor_service.py
│   │   ├── mapper_service.py
│   │   ├── orchestrator_service.py
│   │   ├── writer_service.py
│   │   ├── pdf_upload_service.py
│   │   └── recommendation_service.py
│   ├── system_prompts/
│   │   ├── extractor.py
│   │   ├── mapper.py
│   │   ├── writer.py
│   │   ├── cv_upload.py
│   │   ├── career_recommendation.py
│   │   └── market_trends.py
│   └── constants/
│       ├── categories.py
│       ├── paths.py
│       └── tracing.py
└── docs/
    ├── career_fields.json         ← Schema de campos del perfil
    ├── career_specializations.json ← Catálogo de especializaciones
    └── CAREER_SPECIALIZATION_PLAN.md ← Plan de implementación
```

## Pipeline LangGraph

El sistema usa un grafo de 4 nodos LangGraph que procesa cada mensaje del usuario:

```
Usuario (chat o CV subido)
         │
         ▼
┌────────────────────────────────┐
│ 1. EXTRACTOR (LLM)             │
│    Extrae campos del mensaje   │
└──────────┬─────────────────────┘
           │
     ┌─────┴─────────────────────┐
     ▼                           ▼
  ¿Extrajo                  No extrajo
  campos?                     campos
     │                          │
     ▼                          │
┌──────────────────────┐        │
│ 2. MAPPER (LLM)      │        │
│    Normaliza valores │        │
│    (solo si hay      │        │
│     propiedades)     │        │
└──────────┬───────────┘        │
           │                    │
           ▼                    │
┌──────────────────────────┐    │
│ 3. ORCHESTRATOR (Python) │    │
│    Merge + Validate      │    │
│    + Navegar             │    │
└──────────┬───────────────┘    │
           │                    │
           └──────┬─────────────┘
                  ▼
┌──────────────────────────────┐
│ 4. WRITER (LLM)              │
│    Respuesta humana + tool   │
│    (usa system prompt,       │
│     context e input del      │
│     usuario para responder)  │
└──────────┬───────────────────┘
           │
    ┌─── ¿Profile Complete? ───┐
    │     + Confirmación       │
    │     + Tool ejecutado     │
    ▼                          │
┌──────────────────┐           │
│ Recommendation   │           │
│ Engine           │           │
│ (MCP + WebSearch)│           │
└──────────────────┘           │
    │                          │
    ▼                          ▼
Respuesta final +        Sigue conversando
3 recomendaciones        (pregunta siguiente campo)
```

### Flujo Detallado

1. **Conversación turno a turno**: El usuario conversa con el asistente. Cada mensaje pasa por el pipeline LangGraph. Si el extractor encuentra campos nuevos en el mensaje, se activa el mapper y orchestrator para normalizar, validar y persistir. Si el usuario solo hace una pregunta o comenta sobre campos previos sin aportar datos nuevos, el flujo salta directamente al **Writer**, que responde basado en el system prompt, el historial de contexto y el input del usuario.

2. **Upload de CV**: El estudiante puede subir su CV en PDF. Se convierte a Markdown vía `pymupdf4llm`, se extraen campos estructurados con LLM, y se persisten. Luego continúa la conversación para llenar campos faltantes.

3. **Cierre + Recomendación**: Cuando el perfil está completo y el usuario confirma, el sistema ejecuta el **Recommendation Engine**: recolecta el perfil completo, consulta tendencias del mercado laboral vía MCP/WebSearch, carga el catálogo de especializaciones, y genera máximo 3 recomendaciones personalizadas.

## Schema de Datos del Perfil

Los atributos se recolectan en 5 categorías con orden definido:

```python
CATEGORY_ORDER = [
    "personal_info",
    "education",
    "experience",
    "skills",
    "interests_projects",
]
```

| Categoría | Campos principales |
|---|---|
| `personal_info` | `full_name`, `date_of_birth`, `email`, `phone`, `location.country`, `location.city` |
| `education` | `highest_degree.type`, `field_of_study`, `university_or_source`, `graduation_year`, `if_bachelor_or_higher.gpa` |
| `experience` | `years_of_experience`, `current_role`, `current_company`, `work_history_summary`, `if_experienced.primary_technologies`, `if_experienced.team_size_led` |
| `skills` | `programming_languages`, `frameworks_libraries`, `tools_platforms`, `soft_skills`, `languages_spoken` |
| `interests_projects` | `preferred_technologies`, `hobbies`, `career_goals`, `notable_projects`, `github_or_portfolio` |

### Branching Condicional

| Key | Condición |
|---|---|
| `if_bachelor_or_higher` | Solo aplica si `highest_degree.type` ∈ `["bachelor", "master", "phd"]` |
| `if_experienced` | Solo aplica si `years_of_experience` > 0 |

## Catálogo de Especializaciones

El sistema recomienda entre las siguientes especializaciones (archivo: `docs/career_specializations.json`):

| Especialización | Demanda | Rango Salarial |
|---|---|---|
| AI Agents Developer | Muy Alta | $90k-$220k+ |
| Prompt Engineer | Alta | $70k-$180k+ |
| AI Engineer | Muy Alta | $100k-$220k+ |
| Data Engineer | Muy Alta | $80k-$180k |
| AI and Data Scientist | Muy Alta | $90k-$200k+ |
| Frontend Engineer (Micro Frontend) | Alta | $70k-$160k |
| Backend Engineer (Arquitectura Sistemas) | Muy Alta | $80k-$180k |
| DevOps / SRE Engineer | Muy Alta | $80k-$190k |
| Mobile Engineer (iOS - Android) | Alta | $60k-$150k |
| Game Developer | Media-Alta | $50k-$140k |
| Cybersecurity Engineer | Muy Alta | $75k-$180k |
| Fullstack Engineer (Enfoque Moderno) | Alta | $60k-$150k |
| Blockchain / Web3 Developer | Media-Alta | $70k-$200k |
| Cloud Architect | Muy Alta | $100k-$200k+ |

## Recommendation Engine

Cuando el perfil está completo y el usuario confirma:

1. Se construye el perfil completo desde los atributos persistidos
2. Se consultan tendencias del mercado laboral vía MCP/WebSearch (búsquedas como *"top tech specializations 2026"*, *"highest paying tech jobs 2026"*)
3. Se carga el catálogo de especializaciones disponible
4. El LLM genera máximo 3 recomendaciones con:
   - Nombre de la especialización
   - Razón de alineación con el perfil
   - Top 3-5 skills a desarrollar
   - Recursos sugeridos (cursos, plataformas)
   - Nivel de demanda (Alta/Media/Baja)

> Si MCP/WebSearch falla, se usa solo el catálogo local como fuente de verdad.

## Reglas de Validación

Cada campo del perfil tiene reglas de contenido definidas en `field_content_rules.py`:

| Campo | Validación |
|---|---|
| `full_name` | not_empty, not_numeric, min_words(2), regex solo letras/espacios/apóstrofes |
| `date_of_birth` | not_empty, date format, min_age=16, max_age=60 |
| `email` | not_empty, regex email pattern |
| `phone` | not_empty, regex phone pattern |
| `years_of_experience` | not_empty, number_range(0, 50) |
| `career_goals` | min_words(5) |
| `work_history_summary` | min_words(10) |

## API Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/conversations/{id}/chat/start` | Iniciar conversación (mensaje de bienvenida) |
| `POST` | `/api/v1/conversations/{id}/chat` | Enviar mensaje (procesa via LangGraph) |
| `POST` | `/api/v1/conversations/{id}/chat/upload-pdf` | Subir CV en PDF para extracción automática |
| `GET` | `/health` | Health check |

## Setup

### 1. Requisitos

- Python ≥3.12
- PostgreSQL 16+
- API key de OpenAI

### 2. Instalación

```bash
uv sync
```

### 3. Variables de entorno (`.env`)

```env
# LLM
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o-mini

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=xxx
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=career_advisor
DATABASE_URI=

# WebSearch (opcional — para tendencias de mercado)
TAVILY_API_KEY=tvly-xxx

# LangSmith (opcional)
LANGCHAIN_TRACING_V2=false
LANG_SMITH_KEY=ls-xxx
LANGCHAIN_PROJECT=career-path-advisor

# App
DEBUG=true
APP_NAME=Career Path Advisor
```

### 4. Ejecutar

```bash
# Desarrollo (con reload)
uv run fastapi dev

# Producción
uv run python -m app
```

## Prompts del Sistema

Cada nodo del grafo tiene su propio system prompt:

- **Extractor**: Extrae campos estructurados del mensaje del usuario en JSON
- **Mapper**: Normaliza valores coloquiales a canónicos (ej. "licenciatura" → "bachelor", "JS" → "JavaScript")
- **Writer**: Career Path Advisor — genera respuestas cálidas en español, solicita campos faltantes, maneja confirmación
- **CV Extraction**: Extrae campos desde el Markdown del CV subido
- **Career Recommendation**: Genera recomendaciones personalizadas basadas en perfil + tendencias de mercado

## Calidad > Cantidad

- **Pipeline LangGraph de 4 nodos** separa extracción, normalización, validación y generación para máxima precisión
- **Validación progresiva**: cada campo se valida individualmente antes de persistirse
- **Branching condicional** evita preguntas irrelevantes (ej. GPA solo si tiene título universitario)
- **Recommendation Engine híbrido**: combina perfil del usuario + catálogo de especializaciones + tendencias de mercado en tiempo real
- **Máximo 3 recomendaciones** para evitar sobrecarga cognitiva
- **Soporte multi-formato**: entrada por chat conversacional o subiendo CV en PDF
